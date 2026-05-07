# CherryAI Testing Documentation

**Comprehensive Test Strategy and Test Reference**

---

## AI AGENT INSTRUCTIONS

This document covers the TESTING STRATEGY for CherryAI.

BEFORE MAKING CODE CHANGES:
1. Identify relevant test files in `dev/test_*.py`
2. Run tests before and after changes
3. Add tests for new functionality

CROSS-REFERENCE DOCUMENTATION:
- User features: `doc/features.md`
- Technical API: `doc/technical.md`
- Outstanding work: `doc/todo.md`

---

## Testing Philosophy

Testing is critical for maintaining code quality when working with Agent AI assistants.
The testing strategy enables automated problem detection without requiring extensive manual prompting at each step.

**Two Test Categories:**

| Test Type | Speed | LLM Required | Primary Use |
|-----------|-------|--------------|-------------|
| **Script Test** | Fast (< 8 seconds) | No | Unit tests, regression, CI/CD |
| **API Test** | Slow (30+ seconds) | Yes | Integration, full pipeline validation |

---

## Static Type Checking (mypy)

Type checks complement tests and are run ad-hoc during refactors.

Commands:
- Per-file (fast):
  `python -m mypy CherryAI/functions/mainhelper.py --hide-error-context --no-error-summary --pretty --explicit-package-bases --follow-imports=skip`
- Package scan (inventory):
  `python -m mypy CherryAI/functions --hide-error-context --no-error-summary --pretty --explicit-package-bases --follow-imports=skip`

Guidelines:
- Prefer explicit `Optional[...]` with `is not None` checks.
- Avoid returning `Any`; narrow `getattr` with annotations or `cast()`.
- Remove unused `# type: ignore` comments; keep necessary ignores targeted with codes.

---

## Static Analysis (Pylance/Pyright)

Pylance (VS Code) and Pyright (CLI) provide real-time type checking and import resolution.

### Configuration Files

**pyrightconfig.json** - Pyright/Pylance settings:
```json
{
    "include": [".", "functions", "modi", "formats", "gui"],
    "exclude": ["**/__pycache__", "**/.mypy_cache", "output", "cache", "temp"],
    "extraPaths": [".", ".."],
    "pythonVersion": "3.10",
    "typeCheckingMode": "basic"
}
```

**.vscode/settings.json** - VS Code Python analysis:
```json
{
    "python.analysis.extraPaths": [".", "${workspaceFolder}/.."],
    "python.analysis.diagnosticMode": "workspace"
}
```

### Import Resolution

CherryAI uses a parent directory import pattern (`from CherryAI.functions import ...`).
Static analyzers can't see the runtime `conftest.py` namespace setup, so `extraPaths`
must include `..` to resolve `CherryAI.*` imports.

### Common Type Narrowing Patterns

For `Optional` types, use explicit None checks:
```python
# Good: Pylance understands the narrowing
if self.session is not None:
    self.session.loaded_files.append(path)

# Also good: Use getattr with None default
global_opts = getattr(self.session, "global_options", None)
if global_opts is not None:
    auto_analyze = getattr(global_opts.session, "auto_analyze_on_load", True)
```

---

## Script Test (pytest)

**Location:** `dev/test_*.py`  
**Runner:** `pytest`  
**Count:** ~6200+ tests collected (verified 2026-Q2 — 6222 passed, 222 pre-existing failures, 30 skipped)
**Note (2026):** 33 "FAILED" entries are all pre-existing PROT-renaming regressions unrelated to
the user-folder/encryption overhaul. They do not reflect code written since January 2026.
**Configuration:** `conftest.py` - pytest hooks for CherryAI module setup

Script Tests are fast unit tests that validate internal logic without LLM API calls.
Use these for:
- Rapid iteration during development
- Pre-commit validation
- CI/CD pipelines
- Regression testing after refactoring

### Test Configuration (conftest.py)

The `conftest.py` file provides pytest hooks to properly set up CherryAI module
imports. This is required because tests run from the `dev/` directory but import
modules from `CherryAI.functions.*` and `CherryAI.modi.*`.

Key Functions:
- `pytest_configure()`: Initial setup on pytest startup
- `pytest_runtest_setup()`: Maintains module aliases before each test
- `setup_cherryai_modules()`: Registers CherryAI, CherryAI.modi, CherryAI.functions

This configuration resolves import issues like:
```
ImportError: cannot import name 'load_modes' from 'CherryAI.modi'
```

### Running Script Tests

**CRITICAL: Run from the `utility` root directory.**

**Timeout Requirement:**
All tests must have a timeout to prevent infinite loops. Use the `--timeout` flag (requires `pytest-timeout` plugin) or ensure tests have internal timeouts.

```bash
# Standard command (with 10s timeout)
python -m pytest CherryAI/dev/test_manifest_v2.py -v --timeout=10

# Run all script tests
python -m pytest CherryAI/dev/ -v --timeout=10
```

### Focused Workflow Regression

The QA-before-Wordwrap reorder plus the Full Table View `final` layer are covered by a focused regression set:

- `dev/test_manifest_fields.py` verifies the shared priority chain `final → wordwr → qa → postpro → tl → prepro → orig`, the `final` source helper used by Full Table View prefill, and the stage ceilings for QA and Wordwrap.
- `dev/test_qa_manifest.py` verifies that QA loads its Original column from `postpro → tl → prepro → orig`, loads the Quality Assurance column from `qa`, and loads Overwrite from `qa_overwrite` only.
- `dev/test_wordwrap_phase46.py` verifies that Wordwrap uses `qa → postpro → tl → prepro → orig` as input and that the Wordwrap column only restores stored `wordwr` values.
- `dev/test_table_view.py` verifies the Full Table View `Final` column, Show Latest behavior, and the sparse prefill/auto-clear edit semantics for `final`.

Verified command:

```bash
python -m pytest CherryAI/dev/test_manifest_fields.py CherryAI/dev/test_qa_manifest.py CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_table_view.py -q --timeout=10
```

### Focused Manifest Persistence Regression

The sparse-manifest, `final`, and import-preservation changes are covered by an additional focused set:

- `dev/test_input_import_fixes.py` verifies that importing Information settings does not overwrite the current `project_name`, that Import Translation can copy `final`, and that manifest canonicalization serializes `final` after `wordwr`.
- `dev/test_input_import_fixes.py` also verifies that Create Patch prunes unchanged files by identical `Original/` hash, falls back to full `orig`-match pruning when source originals are missing, deletes copied originals for removed files, and rewrites surviving `filedir` / `lines[]` indices contiguously.
- `dev/test_table_view.py` verifies the Clear Columns workflow for `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, `wordwr`, and `final`, including the second confirmation required for `tl`.
- `dev/test_postprocess_phase45.py` verifies that unchanged postprocessing output clears `postpro` instead of persisting a redundant copy.
- `dev/test_postprocess_phase45.py` also verifies flagged-case dropdown population, dedup-restoration flag clearing for duplicate rows, and Processed Lines search matching Recovery Details metadata.
- `dev/test_qa_manifest.py` verifies that QA does not auto-persist `qa` and only stores explicit `qa_overwrite` edits.
- `dev/test_wordwrap_phase46.py` verifies that Wordwrap preview/leave do not auto-write `wordwr` and that Apply persists only changed wrapped output.
- `dev/test_manifest_metadata.py` verifies metadata import and project-name preservation semantics.

Verified command:

```bash
python -m pytest CherryAI/dev/test_input_import_fixes.py CherryAI/dev/test_table_view.py CherryAI/dev/test_postprocess_phase45.py CherryAI/dev/test_qa_manifest.py CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_manifest_metadata.py -q --timeout=10
```

### Focused Manifest Loading + Canonical Tags Regression

The active-project load reset and canonical tag import changes are covered by another focused set:

- `dev/test_app_startup.py` verifies that clearing `last_manifest` removes the INI key, session-key storage uses `[session]`, and activating a loaded project flushes tab runtime state before entering the new manifest.
- `dev/test_input_import_fixes.py` verifies canonical line ordering, `tags` merge semantics, `tl`-only dedup import blocking, and that dedup rows retain imported or generated later-stage fields during manifest normalization.
- `dev/test_lightvn_fixes.py` verifies that parser tags still flow through `LoadedFile.tags` but are stored via the canonical `tags` helper instead of legacy `tag` writes, that Step 0 re-extracts LightVN parser-backed files from the staged `Original/` tree before syncing `lines[]`, and that explicit rel-path staging works even before `filedir` is rebuilt.

Verified command:

```bash
python -m pytest CherryAI/dev/test_app_startup.py CherryAI/dev/test_input_import_fixes.py CherryAI/dev/test_lightvn_fixes.py -q --timeout=10
```

### Focused Patch Editor Regression

The staged full-file Patch Editor plus its app entry points are covered by a focused regression set:

- `dev/test_patch_editor_view.py` verifies that editor file views prefer staged `Patch/` files, fall back to `Original/` when no patch exists, and persist manifest-backed editor diffs/history when a full-file save occurs.
- `dev/test_app_startup.py` verifies that opening Patch Editor requires a loaded project and that reopening it reuses the shared window instead of creating duplicates.

Verified command:

```bash
python -m pytest dev/test_patch_editor_view.py dev/test_app_startup.py -q --timeout=20
```

Latest verified result: 29 passed.

### Focused Cost Tracking + Editor Surface Regression

The currently implemented building blocks behind the planned Lifetime Cost Tracking window and Translation Workbench are covered by a focused regression set:

- `dev/test_usage_tracker.py` verifies persistent usage aggregation in `user/usage.db`
- `dev/test_api_log.py` verifies structured API log persistence, filtering, and metadata rendering
- `dev/test_patch_editor_view.py` verifies staged full-file editing, diffs, and manifest-backed editor history
- `dev/test_table_view.py` verifies the line-level editing and search/replace surface that the planned workbench will continue to reuse

These tests describe the current foundation only. The redesign plan changes the future target to a TSV-backed `Ledger` plus a merged non-modal `Editor` window, so new focused coverage will be required when implementation starts.

Verified command:

```bash
python -m pytest CherryAI/dev/test_usage_tracker.py CherryAI/dev/test_api_log.py CherryAI/dev/test_patch_editor_view.py CherryAI/dev/test_table_view.py -q --timeout=20
```

### Planned Redesign Coverage

When the Ledger, Editor, and staged-folder redesign phases begin, add focused script coverage for:

- `ledger.tsv` read/write behavior and DB-to-TSV migration from legacy `user/usage.db`
- Ledger grouping, filtering, and Step 4/menu-bar `Ledger` entry points
- Editor single-window reuse and mode switching between `Full Files` and `Lines Only`
- Shared file-context carry-over across the Editor mode switch
- `Patch/Original/` hash-first skip/diff/full-copy behavior
- `Patch/Translated/` reverse-patch capture before Editor save and Output overwrite
- Full-folder staging into `Original/`, including files without parseable content

### Focused GUI Design + Window Persistence Regression

The dark-mode GUI design rollout plus the new Application → GUI options page are covered by a focused regression set:

- `dev/test_gui_dialogs.py` verifies the Global Options dataclasses still import and serialize cleanly after the new GUI settings model was added.
- `dev/test_gui_v2.py` verifies the expanded GUI/theme constants, section ordering, dialog exports, and theme compatibility helpers.
- `dev/test_ini_persistence.py` and `dev/test_ini_sections.py` provide adjacent coverage for INI writes and required section seeding while the new `[ui]` design/window keys coexist with the rest of CherryAI.ini.
- `dev/test_app_startup.py` provides adjacent coverage for startup-time option loading, which now includes reloading the persisted GUI design.

Verified command:

```bash
python -m pytest CherryAI/dev/test_gui_dialogs.py CherryAI/dev/test_ini_persistence.py CherryAI/dev/test_ini_sections.py CherryAI/dev/test_app_startup.py CherryAI/dev/test_gui_v2.py -k "Theme or SessionSettingsDataclass or GlobalOptionsDataclass or SectionDescriptions or CategoryOrder or GlobalOptionsDialogIntegration" -q --timeout=20
```

Latest verified result: 64 passed, 663 deselected.

### Focused Workflow Regression

The affected workflow surfaces are covered by focused regression sets around the remaining import, table-editing, translation-planning, and Wordwrap behavior:

- `dev/test_input_import_fixes.py` verifies import selection handling, canonical tag merging, and dedup placeholder behavior.
- `dev/test_table_view.py` verifies Full Table View deletion tracking plus save/reset semantics after edits.
- `dev/test_edit_before_translate.py`, `dev/test_postprocess_manifest.py`, `dev/test_qa_manifest.py`, and `dev/test_wordwrap_manifest.py` provide adjacent regression coverage for the workflow steps touched during this rollback.
- `dev/test_request_preview.py` and `dev/test_estimation_skip.py` provide adjacent regression coverage so shared skip planning stays aligned across Preview Requests, Translation planning, and Estimation.

Verified commands:

```bash
python -m pytest CherryAI/dev/test_table_view.py CherryAI/dev/test_input_import_fixes.py -q --timeout=10
python -m pytest CherryAI/dev/test_edit_before_translate.py CherryAI/dev/test_postprocess_manifest.py CherryAI/dev/test_qa_manifest.py CherryAI/dev/test_wordwrap_manifest.py -q --timeout=10
python -m pytest CherryAI/dev/test_request_preview.py CherryAI/dev/test_estimation_skip.py -q
```

Latest verified results should be updated from the current focused pytest runs whenever these suites are revalidated.

Latest verified focused command for the `final` change:

```bash
python -m pytest CherryAI/dev/test_manifest_fields.py CherryAI/dev/test_table_view.py CherryAI/dev/test_input_import_fixes.py CherryAI/dev/test_output_injection.py -v --timeout=20
```

### Focused Wordwrap + LightVN Runtime Regression

The manifest-driven Step 8 Wordwrap path and LightVN textbox realization path are covered by a focused runtime set:

- `dev/test_wordwrap_phase46.py` verifies that Apply/Refresh wrap the loaded preview rows even when cached step-data lines are empty, that canonical `tags` drive tag resolution, that speaker mode `ignore` excludes only detected speaker prefixes from width counting, that translated speaker aliases from manifest `characters[]` are also honored, that parser `detect_speakers()` can seed the allowlist when manifest speaker data is absent, that manifest `code_patterns[]` entries marked `IsInvisible` contribute zero width while other code still counts normally, that leading indentation survives wrapping, that literal `\n` commands and non-RPG backslashes survive wrapping, that overflow without textbox support is not persisted to `wordwr`, that `Custom` and `Simple` mode mapping remains backward-compatible with legacy `Manual`, that Simple mode can restrict Apply to a selected file scope, and that `View in File` filters the preview to the selected source file.
- `dev/test_wordwrap_phase46.py` also verifies the `Target:` selector strategies (`Tags first`, `Tags only`, `File first`, `File only`), the removal of the obsolete Step 8 Overwrite preview column, preservation of untyped rows when no target resolves, and that switching into Simple mode does not auto-refresh the preview.
- `dev/test_lightvn_parser.py` verifies that explicit multiline wrapped dialogue is preserved during injection and split into successive LightVN textboxes with the exact `\w` + newline + `"` ordering between boxes, that LightVN injection restores a single terminal `\w` even when Step 8 stored only inter-textbox separators in `wordwr`, that whitelist-driven exact-variable extraction/injection covers assignment and `==` / `!=` comparison literals on the real Uni16 originals, that backlog choice suffixes and popup `追加項目` payloads round-trip with dedicated tags, that bare `-"...` dialogue lines still extract/inject after intervening `~画像` / `~ボイス` commands, that targeted multiline quoted assignments round-trip as one payload, and that parser injection does not perform bracket/code recovery on translated payloads such as `[3 items 60G]`.
- `dev/test_wordwrap.py` verifies the stronger PrettyWrap balancing behavior, including rebalancing a one-word orphan tail into a better punctuation-aligned two-line split.
- `dev/test_lightvn_fixes.py` remains in the set to cover LightVN parser-path and canonical tag propagation behavior used by the same workflow, including quoted ASCII-parentheses preservation for menu labels such as `回復薬(粗悪品)`, the exact-variable `ev_メイン内容` tagging regression, the optional parser rewrite hook in `ParserScript.inject_to()`, and the PYUpgrade `e_armor.txt` hardcoded-equipment rewrite path.
- `dev/test_table_view.py` verifies the Full Table View `Wrap Selection` action, reuse of the Step 8 `wordwrap` stage input chain, and stale `wordwr` clearing when overflow rows should not persist.
- Focused `dev/test_gui_v2.py` assertions verify the current QA-before-Wordwrap ordering plus the updated Wordwrap config dataclasses.

Verified commands:

```bash
python -m pytest CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_lightvn_parser.py CherryAI/dev/test_lightvn_fixes.py -q --timeout=10
python -m pytest CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_tag_wordwrap.py CherryAI/dev/test_wordwrap_manifest.py CherryAI/dev/test_gui_v2.py::TestSessionState::test_step_definitions_names CherryAI/dev/test_gui_v2.py::TestQAStepClass::test_qa_step_id CherryAI/dev/test_gui_v2.py::TestQAStepIntegration::test_qa_step_in_steps_init CherryAI/dev/test_gui_v2.py::TestWrapOptionsDataclass::test_wrap_options_defaults CherryAI/dev/test_gui_v2.py::TestFormatConfigDataclass::test_format_config_defaults CherryAI/dev/test_gui_v2.py::TestFormatConfigDataclass::test_format_config_custom_values CherryAI/dev/test_gui_v2.py::TestWordwrapOverwriteStepIntegration::test_wordwrap_step_attributes CherryAI/dev/test_gui_v2.py::TestStepNamingConsistency::test_step_ids_are_sequential -q --timeout=10
python -m pytest CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_lightvn_parser.py CherryAI/dev/test_tag_wordwrap.py CherryAI/dev/test_wordwrap_manifest.py -q --timeout=10
python -m pytest CherryAI/dev/test_wordwrap.py CherryAI/dev/test_wordwrap_manifest.py CherryAI/dev/test_tag_wordwrap.py CherryAI/dev/test_wordwrap_overhaul.py CherryAI/dev/test_gui_v2.py -k "wordwrap or WrapMode or WrapOptionsDataclass or WordwrapStepIntegration" -q --timeout=20
```

Latest verified result for the focused Step 8 + LightVN + Full Table View wrap-selection set: 250 passed.
Latest verified expanded regression result: 310 passed.

Latest verified focused LightVN parser/fix command:

```bash
python -m pytest dev/test_lightvn_parser.py dev/test_lightvn_fixes.py -q --timeout=20
```

Latest verified result: 131 passed, 2 skipped.
Latest verified compatibility regression result: 204 passed, 2 skipped.
Latest verified LightVN parser regression result: `dev/test_lightvn_fixes.py`, `dev/test_lightvn_parser.py`, `dev/test_output_injection.py` — 128 passed.

### Focused LightVN Tag + Output Sanitization Regression

The hardcoded-tag persistence and trailing-newline output guard are covered by a targeted regression slice:

- `dev/test_lightvn_parser.py` verifies composite LightVN tags such as `variable,hardcoded` / `menu,hardcoded` and the `スキル効果` limit-suffix injection case.
- `dev/test_lightvn_fixes.py` verifies that `items` remains a canonical primary content tag, that Step 0 manifest rehydration restores `LoadedFile.tags` from `lines[].tags`, and that Step 3 preprocessing merges its own tags without overwriting parser/content tags.
- `dev/test_output_injection.py` verifies that Step 9 strips trailing manifest newlines before fresh-line resolution and parser injection matching.

Verified command:

```bash
python -m pytest CherryAI/dev/test_lightvn_parser.py::TestRichMenuMarkup::test_menu_extraction_reads_button_labels_without_condition_literals CherryAI/dev/test_lightvn_parser.py::TestHardcodedMachineExtraction::test_conditional_button_line_keeps_machine_value_duplicate CherryAI/dev/test_lightvn_parser.py::TestHardcodedMachineExtraction::test_hardcoded_equipment_tags_include_special_care_marker CherryAI/dev/test_lightvn_parser.py::TestTargetedVariableExtraction::test_targeted_helper_marks_hardcoded_machine_literals CherryAI/dev/test_lightvn_parser.py::TestTargetedVariableOriginalCoverage::test_targeted_helper_covers_all_targeted_assignments_the_generic_path_would_get CherryAI/dev/test_lightvn_parser.py::TestMultilineInlineQuotedAssignments::test_limit_suffix_round_trips_for_skill_effect_assignment CherryAI/dev/test_lightvn_fixes.py::TestTagPropagation::test_items_tag_is_primary_content_tag CherryAI/dev/test_lightvn_fixes.py::TestTagPropagation::test_populate_from_manifest_restores_loaded_file_tags CherryAI/dev/test_lightvn_fixes.py::TestHardcodedEquipmentMachineKeys::test_injection_preserves_hardcoded_equipment_machine_values CherryAI/dev/test_output_injection.py::TestFreshLineReads::test_get_fresh_lines_strips_trailing_newlines CherryAI/dev/test_output_injection.py::TestWriteInjection::test_injection_strips_manifest_trailing_newlines_before_match -q --timeout=20
```

Latest verified result: 11 passed.

Current narrowed verification for the second-round fix:

```bash
python -m pytest dev/test_lightvn_fixes.py::TestTagPropagation::test_items_tag_is_primary_content_tag dev/test_lightvn_fixes.py::TestTagPropagation::test_populate_from_manifest_restores_loaded_file_tags dev/test_lightvn_fixes.py::TestTagPropagation::test_preprocessing_merges_tags_without_clobbering_parser_tags dev/test_lightvn_parser.py::TestHardcodedMachineExtraction::test_hardcoded_equipment_tags_include_special_care_marker dev/test_lightvn_parser.py::TestTargetedVariableExtraction::test_targeted_helper_marks_hardcoded_machine_literals dev/test_lightvn_parser.py::TestMultilineInlineQuotedAssignments::test_limit_suffix_round_trips_for_skill_effect_assignment dev/test_output_injection.py::TestFreshLineReads::test_get_fresh_lines_strips_trailing_newlines dev/test_output_injection.py::TestWriteInjection::test_injection_strips_manifest_trailing_newlines_before_match
```

Latest verified result: 8 passed.

Plugin installation:

```bash
python -m pip install pytest-timeout
```

Known skips in offline/dev environments:
- Local LLM discovery and healthy server assertions when no server is running
- GUI launch tests requiring Tkinter in headless environments
- Preset-name expectations that conflict with default merges
- API key summary expecting "NOT SET" when a key is configured
- Disabled rolling context behavior assertions
- Standalone integration demos (temporary replacement, unique placeholders)

**Troubleshooting:**
- Do not run `pytest` directly if `CherryAI` is not in your PYTHONPATH. Use `python -m pytest`.
- Always use `-s` flag if you need to see stdout/print debugging.

```bash
# Run specific test file
python -m pytest CherryAI/dev/test_manifest_v2.py -v --timeout=10

# Run specific test class
python -m pytest CherryAI/dev/test_manifest_v2.py::TestLineEntryCreation -v --timeout=10

# Run specific test
python -m pytest CherryAI/dev/test_manifest_v2.py::TestLineEntryCreation::test_minimal_creation -v --timeout=10
```

---

## API Test (One_Click_Test)

**Location:** `functions/One_Click_Test.py`  
**Runner:** Direct execution or via CLI  
**Stages:** 7 stages  
**Status:** ✅ All 7 stages verified passing (Session 13)

API Test validates the full pipeline including actual LLM API communication.
Use these for:
- End-to-end validation
- API connectivity verification
- Cost estimation accuracy
- Production readiness checks

### Running API Test

```bash
# Full test (includes live API call)
python CherryAI.py test

# Skip API calls (offline mode)
python CherryAI.py test --skip-api
```

### API Test Stages

| Stage | Name | Tests | Status |
|-------|------|-------|--------|
| 1 | Dependencies | Required packages installed | ✅ PASS |
| 2 | Configuration | Config file valid, API key set | ✅ PASS |
| 3 | File I/O | Read/write operations work | ✅ PASS |
| 4 | Pre-Processing | Manifest initialization, batching | ✅ PASS |
| 5 | API Connection | LLM provider connectivity | ✅ PASS |
| 6 | Translation | Live translation with sample text | ✅ PASS |
| 7 | Post-Processing | Placeholder restoration logic | ✅ PASS |

**Last Verified:** Gemini 2.0 Flash Lite, ~3.8s total duration, 2 test lines translated.

---

## Test File Reference

### dev/test_table_view.py (124 tests)

Full Table View dialog unit tests. Mocks Tkinter to test data logic independently.

#### TestDataLoading (6 tests)

| Test | Purpose |
|------|---------|
| `test_load_data_populates_all_lines` | Lines loaded from manifest |
| `test_load_data_deep_copies_lines` | Deep copy prevents mutation |
| `test_load_data_populates_filedir` | Filedir entries loaded |
| `test_find_line_exists` | Find line by idx |
| `test_find_line_not_exists` | None for missing idx |
| `test_empty_manifest_has_no_lines` | Empty manifest handled |

#### TestColumnVisibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_populated_columns_detected` | Detects columns with data |
| `test_empty_columns_hidden_by_default` | Empty columns auto-hidden |
| `test_apply_column_visibility` | Updates visible/hidden sets |
| `test_idx_is_hideable` | idx can now be hidden (all columns hideable) |

#### TestPagination (9 tests)

| Test | Purpose |
|------|---------|
| `test_get_display_lines_no_filter` | All lines without filter |
| `test_get_paginated_lines_default` | Default page size |
| `test_get_paginated_lines_offset` | Pagination offset |
| `test_show_all_returns_everything` | Show All mode |
| `test_page_next` | Next page navigation |
| `test_page_prev` | Previous page navigation |
| `test_page_prev_at_zero` | Prev at offset 0 |
| `test_toggle_show_all` | Show All toggle |
| `test_last_page_partial` | Partial last page |

#### TestFileFilter (6 tests)

| Test | Purpose |
|------|---------|
| `test_no_filter_shows_all` | No filter shows all lines |
| `test_filter_by_file` | Filter by specific file |
| `test_filter_by_folder` | Filter by folder |
| `test_filter_by_subfolder` | Filter by subfolder |
| `test_refresh_file_filter_options_builds_tree` | Folder tree built |
| `test_apply_file_filter_none_clears` | None clears filter |

#### TestSearchReplace (9 tests)

| Test | Purpose |
|------|---------|
| `test_search_plain_text` | Plain text search |
| `test_search_regex` | RegEx search |
| `test_search_specific_column` | Column-specific search |
| `test_search_invalid_regex_no_crash` | Invalid regex handling |
| `test_hide_misses_filter` | Hide misses mode |
| `test_pinned_rows_survive_hide_misses` | Pinned rows visible |
| `test_replace_all_single_column` | Replace all in column |
| `test_replace_regex_groups` | Regex capture groups |
| `test_replace_non_editable_column_blocked` | idx and orig not replaceable |

#### TestCellEditing (11 tests)

| Test | Purpose |
|------|---------|
| `test_record_change` | Record field change |
| `test_record_multiple_changes_same_line` | Multiple field changes |
| `test_record_delete` | Record field deletion |
| `test_has_changes_false_initially` | No changes at start |
| `test_has_changes_after_edit` | Changes detected after edit |
| `test_has_changes_after_delete` | Changes detected after delete |
| `test_non_editable_fields_constant` | idx and orig in NON_EDITABLE_FIELDS |
| `test_edit_updates_working_copy` | Working copy updated |
| `test_delete_clears_field` | Field cleared to empty |
| `test_clear_column_affects_all_lines` | Column clear all lines |
| `test_clear_column_respects_file_filter` | Column clear with filter |

#### TestRowSelection (4 tests)

| Test | Purpose |
|------|---------|
| `test_select_row` | Select individual row |
| `test_deselect_row` | Deselect row |
| `test_multiselect` | Multi-row selection |
| `test_range_select` | Shift-click range select |

#### TestSaveResetDiff (8 tests)

| Test | Purpose |
|------|---------|
| `test_save_all_changes` | Save all to manifest |
| `test_save_selected_only` | Save selected rows only |
| `test_reset_all` | Reset all to original |
| `test_reset_selected_only` | Reset selected rows only |
| `test_diff_mode_shows_only_changed` | Diff shows changes |
| `test_diff_mode_empty_when_no_changes` | Diff empty without changes |
| `test_save_no_changes_noop` | No-op save on clean state |
| `test_changes_cleared_after_full_save` | Tracking cleared after save |

#### TestDisplayLinesComposition (3 tests)

| Test | Purpose |
|------|---------|
| `test_file_filter_plus_search` | Combined file + search filter |
| `test_file_filter_plus_diff` | Combined file + diff filter |
| `test_all_filters_combined` | All filters + pagination |

#### TestSorting (3 tests)

| Test | Purpose |
|------|---------|
| `test_sort_by_idx` | Column sorting by idx |
| `test_sort_by_text` | Column sorting by text field |
| `test_sort_reverse` | Reverse sorting works |

#### TestConstants (6 tests)

| Test | Purpose |
|------|---------|
| `test_line_fields_starts_with_idx` | LINE_FIELDS starts with idx |
| `test_line_fields_contains_core_fields` | Essential fields present |
| `test_non_editable_contains_idx` | idx is non-editable |
| `test_metadata_fields_defined` | METADATA_FIELDS correct (idx/tag now searchable) |
| `test_default_page_size` | Default page size is 100 |
| `test_color_constants_are_hex` | Color constants validation |

#### TestFileDirEntryIntegration (4 tests), TestFileFilterDropdownLogic (3 tests), TestColumnFilterLogic (3 tests)

| Test Category | Count | Purpose |
|---------------|-------|---------|
| FileDirEntry | 4 | Integration with FileDirEntry dataclass |
| FileFilterDropdown | 3 | Folder tree, navigation, back |
| ColumnFilterLogic | 3 | Populated filter, show all, idx hideable |

#### TestEdgeCases (9 tests)

| Test | Purpose |
|------|---------|
| `test_empty_manifest_no_crash` | Handle empty manifest |
| `test_large_line_count_pagination` | 10k line pagination |
| `test_line_with_none_values` | None value handling |
| `test_find_line_with_zero_idx` | idx=0 is valid |
| `test_recording_change_creates_entry` | New change tracking entry |
| `test_search_matches_empty_on_clear` | Clear search |
| `test_diff_after_delete` | Diff includes deletions |
| `test_lines_with_special_characters` | Regex special chars safe |
| `test_multiline_content` | Multiline text handling |

#### TestColumnDisplayNames (7 tests)

| Test | Purpose |
|------|---------|
| `test_every_line_field_has_display_name` | All LINE_FIELDS have display names |
| `test_reverse_lookup_round_trips` | DISPLAY_NAME_TO_FIELD reverses correctly |
| `test_display_names_are_unique` | No display name collisions |
| `test_idx_renamed_to_line_number` | idx → Line # |
| `test_orig_renamed_to_original` | orig → Original |
| `test_context_marker_renamed_to_tags` | tags → Tags and legacy tag removed |
| `test_qa_overwrite_renamed` | qa_overwrite → Overwrite |

#### TestDefaultHidden (3 tests)

| Test | Purpose |
|------|---------|
| `test_context_marker_hidden_by_default` | Legacy tag field is not hidden because it is no longer a table column |
| `test_idx_not_hidden_by_default` | idx not hidden |
| `test_orig_not_hidden_by_default` | orig not hidden |

#### TestColumnSelection (7 tests)

| Test | Purpose |
|------|---------|
| `test_selected_columns_initially_empty` | Empty at start |
| `test_toggle_adds_column` | Toggle adds to selection |
| `test_toggle_removes_column` | Toggle removes from selection |
| `test_toggle_multiple_columns` | Multiple columns selectable |
| `test_search_respects_selected_columns` | Search scoped to selection |
| `test_search_uses_visible_when_no_selection` | Falls back to visible columns |
| `test_replace_skips_non_editable_in_selection` | Replace respects NON_EDITABLE_FIELDS |

#### TestColumnPresets (5 tests)

| Test | Purpose |
|------|---------|
| `test_preset_all_shows_all_fields` | Show All preset |
| `test_preset_visible_hides_unpopulated` | Show Visible preset |
| `test_preset_latest_finds_rightmost_column` | Show Latest preset |
| `test_compute_latest_always_includes_idx` | Latest always includes idx |
| `test_unknown_preset_is_no_op` | Invalid preset ignored |

#### TestSortIndicator (6 tests)

| Test | Purpose |
|------|---------|
| `test_initial_sort_state_is_none` | No initial sort |
| `test_sort_sets_column` | Sort sets column tracking |
| `test_sort_same_column_toggles_reverse` | Reverse toggle on same column |
| `test_sort_different_column_resets_reverse` | New column resets direction |
| `test_sort_idx_column_numeric` | idx sorts numerically |
| `test_sort_idx_reverse` | Reverse idx sort |

#### TestResultsOnly (3 tests)

| Test | Purpose |
|------|---------|
| `test_results_only_hides_non_matches` | Only matches shown |
| `test_results_only_shows_pinned_rows` | Pinned rows remain visible |
| `test_results_only_off_shows_all` | All lines when disabled |

#### TestNonEditableFields (4 tests)

| Test | Purpose |
|------|---------|
| `test_idx_is_non_editable` | idx in NON_EDITABLE_FIELDS |
| `test_orig_is_non_editable` | orig in NON_EDITABLE_FIELDS |
| `test_tl_is_editable` | tl NOT in NON_EDITABLE_FIELDS |
| `test_non_editable_fields_size` | Exactly 2 non-editable fields |

---

### dev/test_manifest_v2.py (51 tests)

Core Manifest v2.0 unit tests validating LineEntry and Manifest classes.

#### TestLineEntryCreation (4 tests)

| Test | Purpose |
|------|---------|
| `test_minimal_creation` | LineEntry with only idx and orig |
| `test_full_creation` | LineEntry with all fields populated |
| `test_prepro_ops_creation` | LineEntry with prepro_ops array |
| `test_idx_and_orig_required` | Validates required fields |

#### TestLineEntryTLCEditPasses (6 tests)

| Test | Purpose |
|------|---------|
| `test_set_get_tlc_pass` | set_tlc() and get_tlc() work correctly |
| `test_set_get_edit_pass` | set_edit() and get_edit() work correctly |
| `test_multiple_passes` | Multiple TLC/Edit passes stored correctly |
| `test_invalid_pass_numbers` | Pass numbers must be >= 1 |
| `test_highest_pass_numbers` | get_highest_tlc_pass() and get_highest_edit_pass() |
| `test_no_passes` | Returns 0 when no passes exist |

#### TestInputResolution (14 tests)

| Test | Purpose |
|------|---------|
| `test_get_input_for_translation_with_prepro` | Translation uses prepro if available |
| `test_get_input_for_translation_without_prepro` | Translation falls back to orig |
| `test_get_input_for_tlc_pass1` | TLC Pass 1 uses tl |
| `test_get_input_for_tlc_pass1_fallback` | TLC Pass 1 falls back to prepro/orig |
| `test_get_input_for_tlc_pass2_with_edit1` | TLC Pass 2 uses edit1 if available |
| `test_get_input_for_tlc_pass2_without_edit1` | TLC Pass 2 falls back to tlc1 |
| `test_get_input_for_tlc_pass3` | TLC Pass 3 backwards resolution |
| `test_get_input_for_edit_pass1_with_tlc1` | Edit Pass 1 uses tlc1 if available |
| `test_get_input_for_edit_pass1_fallback` | Edit Pass 1 falls back to tl |
| `test_get_input_for_edit_pass2` | Edit Pass 2 backwards resolution |
| `test_get_input_for_postprocessing_with_edits` | Post ignores Edit/TLC rounds and uses tl |
| `test_get_input_for_postprocessing_with_tlc_only` | Post ignores TLC-only rounds and uses tl |
| `test_get_input_for_postprocessing_fallback` | Post falls back through tl → prepro → orig |
| `test_get_input_for_wordwrap_with_postpro` | Wordwrap uses postpro if available |
| `test_get_input_for_wordwrap_fallback` | Wordwrap falls back to tl → prepro → orig |

#### TestFinalOutput (5 tests)

| Test | Purpose |
|------|---------|
| `test_get_final_output_overwrite` | Final output prefers overwrite |
| `test_get_final_output_wordwr` | Final output uses wordwr if no overwrite |
| `test_get_final_output_postpro` | Final output uses postpro if no wordwr |
| `test_get_final_output_error` | Raises ValueError if nothing available |
| `test_has_final_output` | Checks for output fields existence |

#### TestPopulatedFields (3 tests)

| Test | Purpose |
|------|---------|
| `test_minimal_entry` | Minimal entry has only orig |
| `test_full_entry` | Full entry lists all populated fields |
| `test_excludes_metadata` | get_populated_fields excludes metadata fields |

#### TestLineEntrySerialization (5 tests)

| Test | Purpose |
|------|---------|
| `test_to_dict_sparse` | to_dict only includes populated fields |
| `test_to_dict_full` | to_dict includes all populated fields |
| `test_from_dict_minimal` | from_dict creates entry from minimal data |
| `test_from_dict_full` | from_dict restores all fields including dynamic |
| `test_roundtrip` | to_dict and from_dict preserve all data |

#### TestManifestV2 (8 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_creation` | Manifest can be created with lines array |
| `test_get_line` | get_line retrieves LineEntry by index |
| `test_ensure_line` | ensure_line creates or returns existing |
| `test_set_field` | set_field updates LineEntry fields |
| `test_add_prepro_op` | add_prepro_op appends to prepro_ops |
| `test_get_prepro_ops_filtered` | get_prepro_ops can filter by mode |
| `test_initialize_from_text` | initialize_from_text creates lines |
| `test_get_original_text` | get_original_text reconstructs original |

#### TestManifestSerialization (3 tests)

| Test | Purpose |
|------|---------|
| `test_to_dict_v2` | to_dict includes v2.0 fields |
| `test_from_dict_v2` | from_dict loads v2.0 format |
| `test_roundtrip` | to_dict and from_dict preserve all data |

#### TestFieldCategories (4 tests)

| Test | Purpose |
|------|---------|
| `test_text_fields` | TEXT_FIELDS contains correct fields |
| `test_metadata_fields` | METADATA_FIELDS contains correct fields |
| `test_output_fields` | OUTPUT_FIELDS contains correct fields |
| `test_no_overlap_text_metadata` | TEXT_FIELDS and METADATA_FIELDS don't overlap |

---

### dev/test_manifest_metadata.py (23 tests)

Task 1 metadata: project metadata single source of truth in
`step_state.Information.data.metadata`. Tests info metadata CRUD,
`project_name` property, and absence of legacy top-level keys.

#### TestInfoMetadata (4 tests)

| Test | Purpose |
|------|---------|
| `test_get_info_metadata_creates_path` | Creates nested path if missing |
| `test_set_info_metadata_field` | Writes into correct path |
| `test_get_info_metadata_field_default` | Returns default when absent |
| `test_set_info_metadata_replaces_entirely` | Replaces whole dict |

#### TestProjectNameProperty (3 tests)

| Test | Purpose |
|------|---------|
| `test_reads_from_metadata` | Reads from info metadata |
| `test_fallback_to_manifest_stem` | Falls back to filename |
| `test_no_top_level_project_name` | Not stored at top level |

#### TestProjectInfoOps (3 tests)

| Test | Purpose |
|------|---------|
| `test_get_project_info_from_metadata` | Reads from info metadata |
| `test_set_project_info_writes_metadata` | Writes to info metadata |
| `test_update_project_info_kwargs` | kwargs update metadata |

#### TestGetProjectDir (2 tests)

| Test | Purpose |
|------|---------|
| `test_uses_info_metadata_name` | Uses info metadata project_name |
| `test_fallback_untitled` | Falls back to Untitled |

#### TestGetAllSettings (1 test)

| Test | Purpose |
|------|---------|
| `test_project_info_from_metadata` | Returns info metadata |

#### TestDeprecatedSourceFiles (2 tests)

| Test | Purpose |
|------|---------|
| `test_get_returns_empty` | Returns empty list |
| `test_set_does_nothing` | No-op |

#### TestEmptyManifestStructure (3 tests)

| Test | Purpose |
|------|---------|
| `test_no_project_info_key` | No project_info key |
| `test_no_top_level_project_name` | No project_name key |
| `test_no_source_files_key` | No source_files key |

#### TestCreateNew (3 tests)

| Test | Purpose |
|------|---------|
| `test_project_name_in_metadata` | Stored in info metadata |
| `test_no_top_level_project_name` | Not at top level |
| `test_no_source_files` | No source_files |

#### TestManifestFieldHelpers (2 tests)

| Test | Purpose |
|------|---------|
| `test_save_and_load` | save/load roundtrip |
| `test_load_default` | Returns default |

---

### dev/test_source_root.py (27 tests)

Task 2: source_root simplification. Tests that `source_root` stores only
a folder name (not a full path), `resolve_file_path` uses `Original/`,
`source_files` array and `source_file` per line are removed, copy and
migration work correctly.

#### TestComputeSourceRoot (5 tests)

| Test | Purpose |
|------|---------|
| `test_single_file_returns_parent_name` | Single file → parent folder name |
| `test_multiple_files_same_folder` | Same folder → folder name |
| `test_nested_files_common_ancestor` | Nested → common ancestor name |
| `test_empty_list_returns_empty` | Empty list → empty string |
| `test_string_paths` | Accepts string paths |

#### TestComputeFullRoot (3 tests)

| Test | Purpose |
|------|---------|
| `test_single_file` | Returns full parent path |
| `test_multiple_files` | Returns full common path |
| `test_empty_returns_empty` | Empty → empty string |

#### TestCreateNewSourceRoot (5 tests)

| Test | Purpose |
|------|---------|
| `test_source_root_is_folder_name` | Stores folder name only |
| `test_source_root_not_full_path` | No slashes in source_root |
| `test_no_source_files_in_manifest` | source_files absent |
| `test_lines_have_no_source_file` | No source_file per line |
| `test_filedir_has_correct_rel_paths` | Correct filedir rel_paths |

#### TestNestedSourceFiles (1 test)

| Test | Purpose |
|------|---------|
| `test_nested_rel_paths` | Preserves folder structure in rel_path |

#### TestResolveFilePath (3 tests)

| Test | Purpose |
|------|---------|
| `test_resolves_to_original_dir` | Resolves to Original/ dir |
| `test_nested_path` | Nested rel_path resolves correctly |
| `test_does_not_use_source_root` | source_root not used for resolution |

#### TestMakeRelativePath (2 tests)

| Test | Purpose |
|------|---------|
| `test_path_inside_original` | Path inside Original/ |
| `test_path_outside_original` | Path outside → filename only |

#### TestCopyOriginalsToProject (3 tests)

| Test | Purpose |
|------|---------|
| `test_copies_with_explicit_paths` | Copies with explicit source map |
| `test_skips_missing_source` | Skips nonexistent source |
| `test_fallback_to_input_step_data` | Falls back to Input step data |

#### TestMigrationSourceRoot (2 tests)

| Test | Purpose |
|------|---------|
| `test_v31_source_root_becomes_folder_name` | Full path → folder name |
| `test_migration_preserves_rel_paths` | Absolute rel_paths made relative |

#### TestSavedManifestStructure (3 tests)

| Test | Purpose |
|------|---------|
| `test_saved_json_has_no_source_files` | No source_files in JSON |
| `test_saved_json_source_root_is_folder_name` | Folder name in JSON |
| `test_saved_lines_have_no_source_file` | No source_file in lines |

---

### dev/test_line_saving.py (39 tests)

Task 3: line field saving across all steps. Tests that preprocessing,
postprocessing, and wordwrap steps persist per-line results to manifest
`lines[]`. Postprocessing and wordwrap use `set_line_field`, while preprocessing
persists `prepro` during its bulk `_update_step_data()` manifest pass. Validates round-trip persistence, field
progression, edge cases, and that the `update_line_field` bug is fixed.

#### TestSetLineField (8 tests)

| Test | Purpose |
|------|---------|
| `test_set_prepro_field` | Writes prepro to existing line |
| `test_set_postpro_field` | Writes postpro to existing line |
| `test_set_wordwr_field` | Writes wordwr to existing line |
| `test_set_tl_field` | Writes tl to existing line |
| `test_update_translation_uses_set_line_field` | update_translation delegates to set_line_field |
| `test_set_field_marks_dirty` | set_line_field marks manifest dirty |
| `test_set_field_on_nonexistent_line_creates_it` | Creates new line entry |
| `test_overwrite_existing_field` | Overwrites existing field value |

#### TestFieldProgression (4 tests)

| Test | Purpose |
|------|---------|
| `test_full_progression_on_single_line` | Line accumulates all fields |
| `test_multiple_lines_get_different_fields` | Lines get independent values |
| `test_setting_later_field_does_not_remove_earlier` | Later fields preserve earlier ones |
| `test_all_five_lines_get_all_fields` | All lines get full field set |

#### TestRoundTrip (5 tests)

| Test | Purpose |
|------|---------|
| `test_prepro_survives_save_load` | prepro persists through save/load |
| `test_postpro_survives_save_load` | postpro persists through save/load |
| `test_wordwr_survives_save_load` | wordwr persists through save/load |
| `test_full_progression_survives_save_load` | All fields survive round-trip |
| `test_edited_prepro_survives_save_load` | edited_prepro survives round-trip |

#### TestBugFixVerification (3 tests)

| Test | Purpose |
|------|---------|
| `test_update_line_field_does_not_exist` | update_line_field must NOT exist |
| `test_set_line_field_exists` | set_line_field exists and callable |
| `test_update_translation_exists` | update_translation exists and callable |

#### TestPreprocessIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_preprocess_persists_prepro` | _update_step_data writes prepro and tags fields to manifest (TASK 72) |
| `test_preprocess_does_not_call_update_line_field` | No update_line_field in source |

#### TestPostprocessIntegration (3 tests)

| Test | Purpose |
|------|---------|
| `test_postprocess_complete_has_set_line_field` | _on_postprocess_complete calls set_line_field |
| `test_mark_line_as_fixed_uses_set_line_field` | Uses set_line_field (not update_line_field) |
| `test_postprocess_no_update_line_field_anywhere` | No update_line_field in source |

#### TestWordwrapIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_save_to_session_has_set_line_field` | _save_to_session calls set_line_field |
| `test_wordwrap_does_not_call_update_line_field` | No update_line_field in source |

#### TestTranslateAlreadyCorrect (2 tests)

| Test | Purpose |
|------|---------|
| `test_translate_has_update_translation_call` | translate.py calls update_translation |
| `test_update_translation_delegates_to_set_line_field` | update_translation writes tl field |

#### TestLineFieldEdgeCases (10 tests)

| Test | Purpose |
|------|---------|
| `test_empty_string_field` | Handles empty string values |
| `test_multiline_field_value` | Handles multiline wordwrap output |
| `test_unicode_field_value` | Handles Unicode text |
| `test_field_with_special_chars` | Handles game codes like \\V[1] |
| `test_prepro_ops_list_field` | Handles list values (prepro_ops) |
| `test_none_field_value` | Handles None overwrite field |
| `test_rapid_updates_same_line` | 50 rapid updates to same field |
| `test_rapid_updates_multiple_lines` | Full field set on all lines |
| `test_field_does_not_corrupt_adjacent_lines` | Writing one line doesn't affect others |
| `test_save_load_preserves_field_order` | All fields present in saved JSON |

---

### dev/test_manifest_state.py (27 tests)

ManifestManager state management tests for Manifest 3.0 unified state.

#### TestManifestManagerCreation (6 tests)

| Test | Purpose |
|------|---------|
| `test_create_new_manifest` | Creates new manifest with project info |
| `test_create_new_sets_path` | create_new sets manifest file path |
| `test_create_new_marks_dirty` | New manifest starts dirty |
| `test_create_with_multiple_files` | Handles multiple source files |
| `test_project_name_required` | Validates project name requirement |
| `test_source_files_required` | Validates source files requirement |

#### TestManifestManagerLoadSave (7 tests)

| Test | Purpose |
|------|---------|
| `test_save_creates_file` | save() creates JSON file on disk |
| `test_save_clears_dirty` | save() clears dirty flag |
| `test_load_existing` | load() reads existing manifest |
| `test_load_sets_path` | load() sets internal path |
| `test_load_clears_dirty` | Loaded manifest starts clean |
| `test_save_load_roundtrip` | Data survives save/load cycle |
| `test_load_nonexistent_raises` | load() raises for missing file |

#### TestManifestManagerStateAccess (8 tests)

| Test | Purpose |
|------|---------|
| `test_get_project_info` | Returns project_info dict |
| `test_get_source_files` | Returns source file list |
| `test_get_status` | Returns current status |
| `test_set_status` | Updates status and marks dirty |
| `test_get_manifest_data` | Returns full manifest dict |
| `test_is_dirty` | Reports dirty state correctly |
| `test_mark_dirty` | External dirty marking works |
| `test_get_manifest_path` | Returns file path |

#### TestManifestManagerVersioning (6 tests)

| Test | Purpose |
|------|---------|
| `test_new_manifest_has_version` | New manifest has version field |
| `test_version_format` | Version is valid semver string |
| `test_loaded_manifest_preserves_version` | Load preserves version |
| `test_manifest_type_field` | Type field identifies manifest |
| `test_created_timestamp` | Created timestamp present |
| `test_modified_timestamp_updates` | Modified timestamp updates on save |

---

### dev/test_ini_manager.py (48 tests)

INI file path resolution and typed access for Manifest 3.0 defaults.

#### TestGetIniPath (14 tests)

| Test | Purpose |
|------|---------|
| `test_main_ini_path` | Returns main CherryAI.ini path |
| `test_api_ini_path` | Returns api_profiles.ini path |
| `test_unknown_ini_raises` | Raises for unknown INI names |
| `test_ini_files_exist` | Validates INI files accessible |
| `test_main_ini_content` | Main INI has expected sections |
| `test_api_ini_content` | API INI has expected format |
| `test_path_is_absolute` | Returns absolute paths |
| `test_path_normalization` | Handles path separators |
| `test_case_insensitive_name` | INI name matching is flexible |
| `test_returns_path_object` | Returns pathlib.Path |
| `test_caching_behavior` | Path resolution is efficient |
| `test_thread_safety` | Safe for concurrent access |
| `test_ini_encoding` | Handles UTF-8 encoding |
| `test_missing_ini_handling` | Clear error for missing files |

#### TestGetDefault (10 tests)

| Test | Purpose |
|------|---------|
| `test_get_string_default` | Returns string values |
| `test_get_int_default` | Returns typed integer values |
| `test_get_float_default` | Returns typed float values |
| `test_get_bool_default` | Returns typed boolean values |
| `test_get_list_default` | Parses comma-separated lists |
| `test_missing_key_returns_fallback` | Returns fallback for missing |
| `test_missing_section_returns_fallback` | Returns fallback for bad section |
| `test_type_conversion_error` | Handles bad type conversions |
| `test_empty_value_handling` | Handles empty strings |
| `test_whitespace_handling` | Trims whitespace correctly |

#### TestSetDefault (8 tests)

| Test | Purpose |
|------|---------|
| `test_set_string_value` | Writes string to INI |
| `test_set_int_value` | Writes integer to INI |
| `test_set_bool_value` | Writes boolean to INI |
| `test_set_creates_section` | Creates section if needed |
| `test_set_updates_existing` | Updates existing values |
| `test_set_preserves_other_keys` | Doesn't clobber other keys |
| `test_set_writes_to_disk` | Changes persist to file |
| `test_set_handles_special_chars` | Escapes special characters |

#### TestGetAllManifestDefaults (8 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary of defaults |
| `test_contains_all_sections` | All INI sections represented |
| `test_type_preservation` | Values have correct types |
| `test_nested_structure` | Nested dicts for sections |
| `test_list_parsing` | List values parsed correctly |
| `test_boolean_normalization` | Bools normalized to True/False |
| `test_empty_section_handling` | Empty sections return empty dict |
| `test_performance` | Bulk read is efficient |

#### TestManifestDefaultsMapping (8 tests)

| Test | Purpose |
|------|---------|
| `test_preprocessing_defaults` | Preprocessing options mapped |
| `test_request_defaults` | Request options mapped |
| `test_validation_defaults` | Validation rules mapped |
| `test_postprocessing_defaults` | Post-processing options mapped |
| `test_wordwrap_defaults` | Wordwrap settings mapped |
| `test_output_defaults` | Output options mapped |
| `test_qa_defaults` | QA options mapped |
| `test_estimation_defaults` | Estimation fields mapped |

---

### dev/test_manifest_defaults.py (44 tests)

Manifest initialization and backward compatibility tests for Manifest 3.0.

#### TestCreateManifestPopulatesAllDefaults (11 tests)

| Test | Purpose |
|------|---------|
| `test_has_project_info` | New manifest has project_info dict |
| `test_has_preprocessing_fields` | All preprocessing fields present |
| `test_has_request_options` | RequestOptions dict present |
| `test_has_validation_rules` | ValidationRules dict present |
| `test_has_qa_options` | QAOptions dict present |
| `test_has_postprocessing_fields` | PostProcessing dict present |
| `test_has_wordwrap_settings` | WordwrapSettings dict present |
| `test_has_output_format` | OutputFormat dict present |
| `test_has_estimation_fields` | Estimation fields present |
| `test_has_lines_array` | Lines array initialized |
| `test_has_version` | ManifestVersion present |

#### TestLoadedManifestHasAllFields (5 tests)

| Test | Purpose |
|------|---------|
| `test_load_adds_missing_fields` | Old manifests get new fields |
| `test_load_preserves_existing` | Existing values not overwritten |
| `test_load_adds_nested_dicts` | Nested structures created |
| `test_load_preserves_lines` | Line data preserved |
| `test_load_updates_version` | Version field updated |

#### TestDefaultValuesMatchINI (6 tests)

| Test | Purpose |
|------|---------|
| `test_temperature_from_ini` | Temperature matches INI |
| `test_lines_per_chunk_from_ini` | LinesPerChunk matches INI |
| `test_dedup_threshold_from_ini` | DeduplicationThreshold matches |
| `test_wordwrap_width_from_ini` | WordwrapWidth matches INI |
| `test_max_retries_from_ini` | MaxRetries matches INI |
| `test_bool_values_from_ini` | Boolean values match INI |

#### TestBuiltinDefaults (2 tests)

| Test | Purpose |
|------|---------|
| `test_builtin_fallback` | Uses builtin when INI missing |
| `test_builtin_complete` | Builtin has all required fields |

#### TestBackwardCompatibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_v21_manifest_loads` | v2.1 manifests load correctly |
| `test_v21_gets_v30_fields` | v2.1 manifests get v3.0 fields |
| `test_v10_manifest_loads` | v1.0 manifests load correctly |
| `test_preserve_custom_values` | User customizations preserved |

#### TestListFieldParsing (3 tests)

| Test | Purpose |
|------|---------|
| `test_protect_patterns_parsed` | ProtectCodePatterns as list |
| `test_custom_placeholders_parsed` | CustomPlaceholders as list |
| `test_anchor_removal_parsed` | AnchorRemoval as list |

#### TestHelperMethods (7 tests)

| Test | Purpose |
|------|---------|
| `test_get_manifest_defaults` | _get_manifest_defaults works |
| `test_get_builtin_defaults` | _get_builtin_defaults works |
| `test_parse_list_default` | _parse_list_default works |
| `test_create_project_info_defaults` | _create_project_info_defaults works |
| `test_empty_manifest_complete` | _create_empty_manifest complete |

#### TestFieldCountVerification (6 tests)

| Test | Purpose |
|------|---------|
| `test_total_field_count` | Total fields match expected |
| `test_preprocessing_field_count` | Preprocessing fields complete |
| `test_request_field_count` | Request fields complete |
| `test_validation_field_count` | Validation fields complete |
| `test_wordwrap_field_count` | Wordwrap fields complete |
| `test_output_field_count` | Output fields complete |

---

### dev/test_settings_flow.py (87 tests)

Settings helper methods for processing function integration (Task 21.3).

#### TestGetRequestOptions (10 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_model` | Contains Model key |
| `test_contains_temperature` | Contains Temperature (float) |
| `test_contains_lines_per_chunk` | Contains LinesPerChunk (int) |
| `test_contains_retry_strategy` | Contains RetryStrategy |
| `test_contains_max_retries` | Contains MaxRetries |
| `test_contains_caching` | Contains EnableRequestCaching (bool) |
| `test_contains_line_by_line_mode` | Contains LineByLineMode |
| `test_contains_thinking` | Contains Thinking keys |
| `test_returns_deep_copy` | Returns deep copy (mutation safe) |

#### TestSetRequestOptions (2 tests)

| Test | Purpose |
|------|---------|
| `test_set_updates_manifest` | Updates manifest data |
| `test_set_marks_dirty` | Marks manifest as dirty |

#### TestGetPreprocessingOptions (10 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_deduplication` | Contains Deduplication (bool) |
| `test_contains_deduplication_threshold` | Contains threshold (int) |
| `test_contains_ellipsis_compression` | Contains EllipsisCompression |
| `test_contains_symbol_conversion` | Contains SymbolConversion |
| `test_contains_speaker_replacement` | Contains SpeakerNameReplacement |
| `test_contains_code_spacing_rules` | Contains CodeSpacingRules |
| `test_contains_protect_patterns` | Contains ProtectCodePatterns (list) |
| `test_contains_custom_placeholders` | Contains CustomPlaceholders (list) |
| `test_contains_anchor_removal` | Contains AnchorRemoval (list) |

#### TestSetPreprocessingOptions (2 tests)

| Test | Purpose |
|------|---------|
| `test_set_updates_manifest` | Updates preprocessing fields |
| `test_set_ignores_invalid_keys` | Ignores unknown keys |

#### TestGetValidationRules (8 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_placeholder_preservation` | PlaceholderPreservation (bool) |
| `test_contains_anchor_preservation` | AnchorPreservation key |
| `test_contains_source_language_detection` | SourceLanguageDetection key |
| `test_contains_speaker_format` | SpeakerFormat key |
| `test_contains_quote_balance` | QuoteBalance key |
| `test_contains_empty_translation` | EmptyTranslation key |
| `test_returns_deep_copy` | Returns deep copy |

#### TestGetQAOptions (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_rerun_policy` | RerunPolicy key present |
| `test_contains_max_source_language_chars` | MaxSourceLanguageChars (int) |
| `test_contains_max_line_length` | MaxLineLength (int) |

#### TestGetPostprocessingOptions (10 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_placeholder_recovery` | PlaceholderRecovery (bool) |
| `test_contains_bracket_recovery` | BracketBalanceRecovery key |
| `test_contains_quote_recovery` | QuoteBalanceRecovery key |
| `test_contains_whitespace_normalization` | WhitespaceNormalization key |
| `test_contains_restore_code` | RestoreCodeCharacters key |
| `test_contains_restore_linebreaks` | RestoreLinebreaks key |
| `test_contains_symbol_conversion` | EnableSymbolConversion key |
| `test_contains_fullwidth_conversion` | FullwidthToHalfwidth key |
| `test_contains_failure_handling` | FailureHandling key |

#### TestGetWordwrapOptions (10 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_mode` | Mode key present |
| `test_contains_width` | Width (int) present |
| `test_contains_break_char` | BreakChar key present |
| `test_contains_max_lines` | MaxLines (int) present |
| `test_contains_pretty_wrap` | PrettyWrap (bool) |
| `test_contains_format_configs` | FormatConfigs key |
| `test_contains_speaker_handling` | SpeakerHandling key |
| `test_contains_ignore_patterns` | IgnorePatterns (list) |
| `test_contains_typography` | Typography key present |

#### TestGetOutputOptions (13 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_preserve_structure` | PreserveFolderStructure (bool) |
| `test_contains_format` | Format key present |
| `test_contains_pair_mode` | PairMode key present |
| `test_contains_encoding` | Encoding key present |
| `test_contains_file_naming` | FileNaming key present |
| `test_contains_text_option` | TextOption key present |
| `test_contains_overwrite` | OverwriteExistingFiles (bool) |
| `test_contains_backup` | Backup key present |
| `test_contains_backup_extension` | BackupExtension key present |
| `test_contains_export_manifest` | ExportManifestFile key |
| `test_contains_export_logs` | ExportProcessingLogs key |
| `test_contains_export_glossary` | ExportGlossaryEntries key |

#### TestGetEstimationData (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_input_lines` | InputLines (int) present |
| `test_contains_input_tokens` | InputTokens (int) present |
| `test_contains_output_tokens` | OutputTokens (int) present |

#### TestSetEstimationData (2 tests)

| Test | Purpose |
|------|---------|
| `test_set_updates_manifest` | Updates estimation fields |
| `test_set_partial_update` | Partial updates work |

#### TestGetAllSettings (10 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_project_info` | project_info key present |
| `test_contains_preprocessing` | preprocessing key present |
| `test_contains_request` | request key present |
| `test_contains_validation` | validation key present |
| `test_contains_qa` | qa key present |
| `test_contains_postprocessing` | postprocessing key present |
| `test_contains_wordwrap` | wordwrap key present |
| `test_contains_output` | output key present |
| `test_contains_estimation` | estimation key present |

#### TestSettingsPersistence (2 tests)

| Test | Purpose |
|------|---------|
| `test_request_options_persist` | Request options survive save/load |
| `test_wordwrap_options_persist` | Wordwrap options survive save/load |

---

### dev/test_app_startup.py (23 tests)

Application startup manifest loading tests (Task 21.4).

#### TestGetLastManifest (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_none_when_empty` | Returns None when no last manifest set |
| `test_returns_path_when_set` | Returns Path when last manifest is set |
| `test_returns_path_even_if_not_exists` | Returns path even if file doesn't exist |

#### TestSetLastManifest (3 tests)

| Test | Purpose |
|------|---------|
| `test_set_stores_absolute_path` | Stores path as absolute |
| `test_set_none_clears_value` | Setting None clears the last manifest |
| `test_set_returns_true_on_success` | Returns True when successful |

#### TestGetRecentManifests (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_empty_list_when_empty` | Returns empty list when no history |
| `test_returns_existing_paths_only` | Only returns paths that exist |
| `test_respects_max_count` | Limits results to max_count |

#### TestAddToRecentManifests (2 tests)

| Test | Purpose |
|------|---------|
| `test_adds_to_front` | Adds new manifest to front of list |
| `test_moves_existing_to_front` | Moves existing manifest to front when re-added |

#### TestRestoreOnLaunch (4 tests)

| Test | Purpose |
|------|---------|
| `test_default_is_true` | Default load_last is True when set in INI |
| `test_can_disable` | Can disable restore on launch |
| `test_can_enable` | Can enable restore on launch |
| `test_fallback_when_not_set` | Falls back when key not present |

#### TestWelcomeDialogConstants (2 tests)

| Test | Purpose |
|------|---------|
| `test_result_constants_defined` | Result constants are properly defined |
| `test_result_constants_unique` | Result constants are unique strings |

#### TestManifestPathStorage (2 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_path_stored_as_absolute` | Manifest path is stored as absolute path |
| `test_roundtrip_manifest_path` | Manifest path survives set/get roundtrip |

#### TestStartupFlowLogic (4 tests)

| Test | Purpose |
|------|---------|
| `test_loads_last_manifest_when_exists` | When last manifest exists, it should be loadable |
| `test_skips_restore_when_disabled` | When restore disabled, should not auto-load |
| `test_handles_missing_manifest_file` | When last manifest file is missing, returns path |
| `test_first_launch_has_no_last_manifest` | On first launch, no last manifest should be set |

#### TestPhase58_11_ManifestFixes (5 tests) - Phase 58.11

| Test | Purpose |
|------|---------|
| `test_manifest_lines_load_on_resume` | Resume loads manifest lines into InputExtractionStep |
| `test_auto_load_checkbox_saves_setting` | WelcomeDialog checkbox persists load_last |
| `test_manifest_list_sorted_by_date` | LoadManifestDialog shows newest manifests first |
| `test_global_options_syncs_restore_setting` | GlobalOptions read/write syncs with [session] section |
| `test_save_concurrent_modification_safe` | ManifestManager.save() uses deepcopy for thread safety |

#### TestPhase58_12_InputDialogUX (4 tests) - Phase 58.12

| Test | Purpose |
|------|---------|
| `test_last_dir_remembered` | UnifiedInputDialog remembers last used directory |
| `test_project_name_field_shown_when_no_manifest` | Project Name field appears when show_project_name=True |
| `test_project_name_validated` | Empty project name triggers validation error |
| `test_result_tuple_includes_project_name` | Dialog result includes project_name as 4th element |

---

### dev/test_manifest_filedir.py (51 tests) - TASK 35

TASK 35: Manifest filedir feature for input/output decoupling (updated for v3.2).
Tests for FileDirEntry dataclass, filedir operations, Original/ copy, and Patch/ output.

#### TestFileDirEntry (9 tests)

| Test | Purpose |
|------|---------|
| `test_create_basic` | Basic FileDirEntry creation |
| `test_create_with_all_fields` | FileDirEntry with all fields specified |
| `test_line_count_property` | line_count property calculates correctly |
| `test_contains_idx` | contains_idx method boundary conditions |
| `test_filename_property` | filename property extracts correctly |
| `test_to_dict_sparse_format` | to_dict only includes non-default values |
| `test_from_dict_minimal` | from_dict with minimal data |
| `test_from_dict_full` | from_dict with all fields |
| `test_roundtrip_serialization` | to_dict/from_dict roundtrip preserves data |

#### TestManifestManagerFiledir (9 tests)

| Test | Purpose |
|------|---------|
| `test_empty_manifest_has_filedir_field` | New manifests include empty filedir field |
| `test_manifest_version_is_3_2` | New manifests have version 3.2 (TASK 38) |
| `test_get_filedir_empty` | get_filedir returns empty list for new manifest |
| `test_set_filedir` | set_filedir stores entries correctly |
| `test_get_filedir_retrieves_entries` | get_filedir retrieves stored entries |
| `test_add_filedir_entry` | add_filedir_entry appends to list |
| `test_clear_filedir` | clear_filedir removes all entries |
| `test_get_filedir_entry_for_idx_found` | get_filedir_entry_for_idx finds correct entry |
| `test_get_filedir_entry_for_idx_not_found` | get_filedir_entry_for_idx returns None for invalid index |
| `test_get_lines_for_filedir_entry` | get_lines_for_filedir_entry retrieves correct lines |

#### TestBuildFiledirFromFiles (6 tests)

| Test | Purpose |
|------|---------|
| `test_single_file` | Building filedir from a single file |
| `test_multiple_files_sequential` | Multiple files with sequential indices |
| `test_common_base_detection` | Common base path is detected for relative paths |
| `test_preserves_encoding` | Encoding is preserved in filedir entries |
| `test_skips_empty_files` | Files with zero lines are skipped |
| `test_source_root_computed_for_common_path` | source_root computed correctly (TASK 38) |

#### TestFiledirMigration (4 tests)

| Test | Purpose |
|------|---------|
| `test_migrate_v30_manifest_adds_filedir` | v3.0 manifests get filedir added during migration (to v3.2) |
| `test_build_filedir_from_legacy_single_file` | _build_filedir_from_legacy with single source file |
| `test_build_filedir_from_legacy_multiple_files` | _build_filedir_from_legacy with multiple source files |
| `test_build_filedir_from_legacy_no_lines` | _build_filedir_from_legacy with empty lines |

#### TestCopyOriginalsToProject (11 tests)

| Test | Purpose |
|------|---------|
| `test_copy_creates_original_dir` | Copy creates the Original/ directory |
| `test_copy_copies_files` | Files are actually copied |
| `test_copy_preserves_content` | File content is preserved during copy |
| `test_copy_preserves_folder_structure` | Folder structure is preserved |
| `test_copy_skips_existing_without_force` | Existing files are skipped when force=False |
| `test_copy_overwrites_with_force` | Existing files are overwritten when force=True |
| `test_copy_returns_path_mapping` | Copy returns mapping of original to copied paths |
| `test_copy_handles_missing_source` | Copy handles missing source files gracefully |
| `test_copy_empty_filedir_returns_empty` | Copy returns empty dict when filedir is empty |
| `test_has_original_copies_false_initially` | has_original_copies returns False before copying |
| `test_has_original_copies_true_after_copy` | has_original_copies returns True after copying |

#### TestPathHelpers (6 tests)

| Test | Purpose |
|------|---------|
| `test_get_project_dir_uses_project_name` | get_project_dir returns correct path based on project name |
| `test_get_project_dir_sanitizes_name` | get_project_dir sanitizes project name for filesystem |
| `test_get_original_dir` | get_original_dir returns correct path |
| `test_get_patch_dir` | get_patch_dir returns correct path |
| `test_get_original_file_path` | get_original_file_path returns correct path for entry |
| `test_get_patch_file_path` | get_patch_file_path returns correct path for entry |

#### TestFiledirOutputIntegration (3 tests)

| Test | Purpose |
|------|---------|
| `test_get_lines_for_entry_returns_correct_subset` | get_lines_for_filedir_entry returns correct line subset |
| `test_filedir_covers_all_lines` | filedir entries cover all line indices |
| `test_filedir_no_overlapping_ranges` | filedir entries don't have overlapping ranges |

#### TestFiledirPersistence (2 tests)

| Test | Purpose |
|------|---------|
| `test_filedir_saved_to_disk` | filedir is saved when manifest is saved |
| `test_filedir_loaded_from_disk` | filedir is loaded when manifest is loaded |

---

### dev/test_typing_feature.py (24 tests) - Typing Feature

Tests for the Typing feature: file type classification, type resolution, prompt injection.

#### TestFileDirEntryType (7 tests)

| Test | Purpose |
|------|---------|
| `test_default_type_is_empty` | FileDirEntry type defaults to "" |
| `test_to_dict_omits_empty_type` | Sparse format omits empty type |
| `test_to_dict_includes_nonempty_type` | Non-empty type serialized |
| `test_to_dict_type_before_first_idx` | type field appears before first_idx |
| `test_from_dict_reads_type` | from_dict restores type value |
| `test_from_dict_missing_type_defaults_empty` | Missing type defaults to "" |
| `test_roundtrip` | to_dict + from_dict roundtrip |

#### TestClassifyFileType (6 tests)

| Test | Purpose |
|------|---------|
| `test_empty_lines_returns_menu` | No lines → "menu" |
| `test_no_speakers_returns_menu` | No speakers → "menu" |
| `test_above_10pct_returns_dialogue` | >10% speakers → "dialogue" |
| `test_exactly_10pct_returns_menu_question` | ≤10% ≥2 speakers → "menu?" |
| `test_one_speaker_returns_menu` | 1 speaker → "menu" |
| `test_all_speakers_returns_dialogue` | 100% speakers → "dialogue" |

#### TestResolveChunkType (7 tests)

| Test | Purpose |
|------|---------|
| `test_empty_indices_returns_unknown` | No indices → "unknown" |
| `test_tags_take_priority_over_filedir` | Tags override filedir type |
| `test_majority_tag_wins` | Most common tag wins |
| `test_filedir_used_when_no_tags` | Falls back to filedir type |
| `test_mixed_filedir_types` | Multiple file types → "mixed" |
| `test_no_tags_no_filedir_returns_unknown` | No type info → "unknown" |
| `test_lines_with_empty_tag_are_ignored` | Empty tags don't count |

#### TestBuildFullSystemPromptContextType (4 tests)

| Test | Purpose |
|------|---------|
| `test_context_type_appears_after_pov` | Context-type in breakdown after POV |
| `test_empty_context_type_omits_section` | Empty type → no section |
| `test_unknown_context_type_omits_section` | Invalid type → no section |
| `test_dialogue_context_type_adds_content` | "dialogue" → non-empty section |

---

### dev/test_manifest_v32.py (35 tests) - TASK 38

TASK 38: Manifest v3.2 optimization with source_root and compact line format.
Tests for source_root computation, path resolution, and migration from v3.1.

#### TestManifestVersionIs32 (1 test)

| Test | Purpose |
|------|---------|
| `test_manifest_version_is_32` | MANIFEST_VERSION is '3.2' |

#### TestFileDirEntryNoSourceHint (4 tests)

| Test | Purpose |
|------|---------|
| `test_filedir_entry_has_no_source_hint_attribute` | FileDirEntry has no source_hint attribute |
| `test_filedir_entry_to_dict_no_source_hint` | to_dict() doesn't include source_hint |
| `test_filedir_entry_from_dict_without_source_hint` | from_dict() works without source_hint |
| `test_filedir_entry_sparse_encoding` | to_dict() omits default encoding |

#### TestSourceRootComputation (5 tests)

| Test | Purpose |
|------|---------|
| `test_compute_source_root_single_file` | Single file returns parent directory |
| `test_compute_source_root_same_directory` | Files in same dir returns that dir |
| `test_compute_source_root_nested_directories` | Nested dirs returns common parent |
| `test_compute_source_root_deep_common_path` | Finds deepest common path |
| `test_compute_source_root_empty_list` | Empty list returns empty string |

#### TestSourcePathResolution (3 tests)

| Test | Purpose |
|------|---------|
| `test_resolve_file_path_with_source_root` | resolve_file_path combines source_root + rel_path |
| `test_resolve_file_path_no_source_root` | Returns rel_path as Path when no source_root |
| `test_make_relative_path` | Creates path relative to source_root |

#### TestGetFileForLineIdx (3 tests)

| Test | Purpose |
|------|---------|
| `test_get_file_for_line_idx_found` | Returns entry containing the index |
| `test_get_file_for_line_idx_not_found` | Returns None for invalid index |
| `test_get_source_file_for_line_resolved` | Returns resolved absolute path |

#### TestCompactLineFormat (2 tests)

| Test | Purpose |
|------|---------|
| `test_line_entry_no_source_file` | Lines don't have source_file in v3.2 |
| `test_source_root_stored_in_manifest` | Manifest has source_root field |

#### TestMigrationV31ToV32 (5 tests)

| Test | Purpose |
|------|---------|
| `test_migration_removes_source_file_from_lines` | Migration removes source_file from lines |
| `test_migration_removes_source_hint_from_filedir` | Migration removes source_hint from filedir |
| `test_migration_sets_source_root` | Migration computes and sets source_root |
| `test_migration_updates_version` | Migration updates version to 3.2 |
| `test_migration_preserves_line_data` | Migration preserves idx and orig |

#### TestFileDirEntryContainsIdx (2 tests)

| Test | Purpose |
|------|---------|
| `test_contains_idx_in_range` | Returns True for indices in range |
| `test_contains_idx_out_of_range` | Returns False for indices outside range |

#### TestFileDirEntryLineCount (2 tests)

| Test | Purpose |
|------|---------|
| `test_line_count_single_line` | line_count is 1 for single-line entry |
| `test_line_count_multiple_lines` | line_count is correct for multi-line entry |

#### TestFileDirEntryFilename (2 tests)

| Test | Purpose |
|------|---------|
| `test_filename_simple` | Returns just the file name |
| `test_filename_nested_path` | Extracts name from nested path |

#### TestSourceRootProperty (2 tests)

| Test | Purpose |
|------|---------|
| `test_source_root_property_returns_value` | Returns stored value |
| `test_source_root_property_empty_when_not_set` | Returns empty string when not set |

#### TestMigrationFromOlderVersions (2 tests)

| Test | Purpose |
|------|---------|
| `test_migration_from_v1_to_v32` | Migration from v1.x to v3.2 |
| `test_migration_from_v2_to_v32` | Migration from v2.x to v3.2 |

#### TestEmptyManifestTemplate (1 test)

| Test | Purpose |
|------|---------|
| `test_empty_manifest_has_source_root` | Empty manifest has source_root field |

#### TestSizeReduction (1 test)

| Test | Purpose |
|------|---------|
| `test_no_source_file_in_lines_reduces_size` | Compact format reduces manifest size |

---

### dev/test_blacklist_whitelist.py (57 tests) - PHASE 36

PHASE 36: Character/Word Validation (Whitelist/Blacklist + Autofix). Tests for character validation manifest fields, high-performance scanner, and logit bias integration.

#### TestManifestValidationFields (13 tests)

| Test | Purpose |
|------|---------|
| `test_new_manifest_has_character_whitelist` | New manifests have CharacterWhitelist field |
| `test_new_manifest_has_character_blacklist` | New manifests have CharacterBlacklist field |
| `test_new_manifest_has_word_blacklist` | New manifests have WordBlacklist field |
| `test_new_manifest_has_autofix_map` | New manifests have AutofixMap field |
| `test_get_set_character_whitelist` | get/set character whitelist |
| `test_get_set_character_blacklist` | get/set character blacklist |
| `test_get_set_word_blacklist` | get/set word blacklist |
| `test_add_remove_word_blacklist` | add/remove words from blacklist |
| `test_add_word_no_duplicates` | Duplicate words are not added |
| `test_get_set_autofix_map` | get/set autofix map |
| `test_add_remove_autofix_entry` | add/remove autofix entries |
| `test_get_character_validation_config` | get full validation config |
| `test_set_character_validation_config` | set full validation config |

#### TestManifestDictParsing (6 tests)

| Test | Purpose |
|------|---------|
| `test_parse_dict_empty_string` | Parse empty string returns empty dict |
| `test_parse_dict_single_pair` | Parse single key=value pair |
| `test_parse_dict_multiple_pairs` | Parse multiple key=value pairs |
| `test_parse_dict_with_whitespace` | Parse with whitespace |
| `test_parse_dict_json_format` | Parse JSON format |
| `test_parse_dict_already_dict` | Parse when already a dict |

#### TestValidationSeverity (1 test)

| Test | Purpose |
|------|---------|
| `test_severity_values` | ValidationSeverity enum values |

#### TestCharacterWordFinding (2 tests)

| Test | Purpose |
|------|---------|
| `test_create_character_finding` | Create character finding |
| `test_create_word_finding` | Create word finding |

#### TestCharacterWordValidationResult (2 tests)

| Test | Purpose |
|------|---------|
| `test_empty_result` | Empty validation result |
| `test_result_with_findings` | Result with findings |

#### TestValidateCharacterWord (10 tests)

| Test | Purpose |
|------|---------|
| `test_fast_exit_no_rules` | Fast exit when no rules configured |
| `test_character_blacklist_finds_offending` | Character blacklist finds offending characters |
| `test_character_whitelist_finds_offending` | Character whitelist finds non-whitelisted chars |
| `test_word_blacklist_finds_offending` | Word blacklist finds offending words |
| `test_word_blacklist_whole_word_only` | Word blacklist only matches whole words |
| `test_autofix_map_provides_suggestions` | Autofix map provides suggestions |
| `test_autofix_with_invalid_replacement` | Invalid replacement results in ERROR severity |
| `test_multiple_fields_checked` | Multiple fields are checked |
| `test_custom_fields_to_check` | Custom fields_to_check |
| `test_both_character_and_word_validation` | Both character and word validation |

#### TestApplyAutofix (4 tests)

| Test | Purpose |
|------|---------|
| `test_apply_autofix_basic` | Basic autofix application |
| `test_apply_autofix_multiple_replacements` | Multiple replacements |
| `test_apply_autofix_respects_whitelist` | Autofix respects whitelist |
| `test_apply_autofix_respects_blacklist` | Autofix respects blacklist |

#### TestApplyAutofixToLines (2 tests)

| Test | Purpose |
|------|---------|
| `test_apply_to_lines_basic` | Apply autofix to lines |
| `test_apply_to_multiple_fields` | Apply autofix to multiple fields |

#### TestFindingsSummary (3 tests)

| Test | Purpose |
|------|---------|
| `test_summary_no_issues` | Summary with no issues |
| `test_summary_with_warnings` | Summary with warnings |
| `test_summary_with_errors` | Summary with errors |

#### TestGroupFindings (2 tests)

| Test | Purpose |
|------|---------|
| `test_group_by_line` | Group findings by line |
| `test_group_by_token` | Group findings by token |

#### TestValidationPerformance (3 tests)

| Test | Purpose |
|------|---------|
| `test_large_batch_performance` | Scanner performance with 10K lines |
| `test_fast_exit_performance` | Fast exit with 100K lines |
| `test_two_pass_efficiency` | Two-pass algorithm efficiency |

#### TestLogitBiasFromBlacklist (5 tests)

| Test | Purpose |
|------|---------|
| `test_create_from_empty_blacklist` | Create from empty blacklist |
| `test_create_from_single_char` | Create from single character |
| `test_create_from_multiple_chars` | Create from multiple characters |
| `test_create_removes_duplicates` | Removes duplicate characters |
| `test_create_with_disabled` | Create with enabled=False |

#### TestProviderLogitBiasSupport (4 tests)

| Test | Purpose |
|------|---------|
| `test_openai_supports_logit_bias` | OpenAI supports logit bias |
| `test_anthropic_no_logit_bias` | Anthropic doesn't support logit bias |
| `test_google_no_logit_bias` | Google doesn't support logit bias |
| `test_unknown_provider_no_logit_bias` | Unknown providers default to no support |

---

### dev/test_edit_tlc_components.py (40 tests) - PHASE 37

PHASE 37: Edit/TLC Prompt Components (Configurable Input Sources). Tests for component toggles, input policies, and prompt building with selective component inclusion.

#### TestEditInputPolicy (3 tests)

| Test | Purpose |
|------|---------|
| `test_edit_input_policy_values` | All EditInputPolicy enum values exist |
| `test_edit_input_policy_count` | EditInputPolicy has exactly 4 values |
| `test_edit_input_policy_from_string` | Create EditInputPolicy from string |

#### TestTLCInputPolicy (3 tests)

| Test | Purpose |
|------|---------|
| `test_tlc_input_policy_values` | All TLCInputPolicy enum values exist |
| `test_tlc_input_policy_count` | TLCInputPolicy has exactly 4 values |
| `test_tlc_input_policy_from_string` | Create TLCInputPolicy from string |

#### TestPromptsSettingsComponents (5 tests)

| Test | Purpose |
|------|---------|
| `test_default_edit_components` | Default edit components are all True |
| `test_default_tlc_components` | Default TLC components are all True |
| `test_default_input_policies` | Default input policies are correct |
| `test_get_edit_components` | get_edit_components returns correct dict |
| `test_get_tlc_components` | get_tlc_components returns correct dict |

#### TestPromptsSettingsSerialization (4 tests)

| Test | Purpose |
|------|---------|
| `test_to_dict_includes_all_fields` | to_dict includes all component and policy fields |
| `test_from_dict_restores_all_fields` | from_dict restores all fields |
| `test_from_dict_uses_defaults_for_missing_fields` | from_dict uses defaults for missing fields |
| `test_roundtrip_serialization` | to_dict then from_dict preserves all values |

#### TestBuildEditTlcPrompt (10 tests)

| Test | Purpose |
|------|---------|
| `test_base_prompt_always_included` | Base prompt is always included |
| `test_empty_base_prompt` | Empty base prompt produces valid result |
| `test_character_notes_included_when_enabled` | Character notes included when enabled |
| `test_character_notes_excluded_when_disabled` | Character notes excluded when disabled |
| `test_code_glossary_included_when_enabled` | Code glossary included when enabled |
| `test_code_glossary_excluded_when_disabled` | Code glossary excluded when disabled |
| `test_default_components_include_all` | Default components include all sections |
| `test_game_summary_included_when_enabled` | Game summary included when enabled |
| `test_game_summary_excluded_when_disabled` | Game summary excluded when disabled |
| `test_empty_character_notes_no_section` | Empty character notes produces no section |
| `test_empty_code_glossary_no_section` | Empty code glossary produces no section |

#### TestComponentCombinations (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_components_enabled` | All components enabled includes all sections |
| `test_all_components_disabled` | All components disabled includes only base prompt |
| `test_only_character_notes_enabled` | Only character notes enabled |
| `test_only_code_glossary_enabled` | Only code glossary enabled |

#### TestCharacterNotesFormatting (4 tests)

| Test | Purpose |
|------|---------|
| `test_character_with_all_fields` | Character with all fields formats correctly |
| `test_character_with_minimal_fields` | Character with minimal fields formats correctly |
| `test_character_uses_original_name_fallback` | Uses original_name when name is missing |
| `test_character_without_notes_excluded` | Characters without notes or style are excluded |

#### TestCodeGlossaryFormatting (4 tests)

| Test | Purpose |
|------|---------|
| `test_pattern_with_preserve_action` | Preserve action is default, not shown |
| `test_pattern_with_non_preserve_action` | Non-preserve action is shown in brackets |
| `test_pattern_with_example` | Pattern example is included |
| `test_empty_pattern_excluded` | Patterns with empty pattern string excluded |

#### TestPromptsSettingsIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_edit_components_from_settings` | PromptsSettings edit components work with builder |
| `test_tlc_components_from_settings` | PromptsSettings TLC components work with builder |

---

### dev/test_manifest_fields.py (194 tests)

Manifest field type helpers for Task 22.1 and 22.2. Reusable save/load operations for different field types and complex data structures.

**Session 26 additions:** `manifest_fields.py` now also exports shared priority resolution functions used by all GUI steps: `resolve_line_field()`, `resolve_line_field_from()`, `get_latest_line_text()`, `get_all_lines_resolved()`.

**Stage-ceiling additions:** `resolve_line_field_for_stage()`, `get_line_text_for_stage()`, and `get_all_lines_for_stage()` enforce workflow-specific input ceilings while `PIPELINE_FIELDS` remains the full final-display chain: `final → wordwr → qa → postpro → tl → prepro → orig`.

#### TestLinePriorityResolution (6 tests)

| Test | Purpose |
|------|---------|
| `test_pipeline_fields_latest_chain` | Full-chain order remains final → wordwr → qa → postpro → tl → prepro → orig |
| `test_resolve_line_field_prefers_latest_display` | Final-display helper prefers final, then wordwrap, then QA |
| `test_resolve_line_field_for_stage_postprocessing_uses_tl_chain` | Postprocessing ceiling is tl → prepro → orig |
| `test_resolve_line_field_for_stage_wordwrap_uses_postpro_chain` | Wordwrap ceiling is qa → postpro → tl → prepro → orig |
| `test_resolve_line_field_for_stage_qa_ignores_qa_overwrite` | QA ceiling ignores qa_overwrite and wordwr and starts at postpro |
| `test_get_stage_helpers_resolve_all_lines` | Manager-level stage helpers resolve by idx and in bulk |

#### TestTextFieldSave (6 tests)

| Test | Purpose |
|------|---------|
| `test_save_simple_text` | Save a simple text value |
| `test_save_empty_text` | Save an empty string |
| `test_save_text_with_special_chars` | Save text with special characters |
| `test_save_converts_none_to_empty` | None is converted to empty string |
| `test_save_converts_number_to_string` | Numbers are converted to strings |
| `test_save_long_text` | Save long text value |

#### TestTextFieldLoad (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_existing_text` | Load an existing text value |
| `test_load_missing_uses_default` | Missing field returns default |
| `test_load_none_uses_default` | None value returns default |
| `test_load_converts_number_to_string` | Numbers are converted to strings |

#### TestTextFieldRoundtrip (3 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_simple` | Simple text roundtrip |
| `test_roundtrip_unicode` | Unicode text roundtrip |
| `test_roundtrip_multiline` | Multiline text roundtrip |

#### TestNestedTextFields (5 tests)

| Test | Purpose |
|------|---------|
| `test_save_nested_creates_parent` | Save creates parent dict if missing |
| `test_save_nested_preserves_siblings` | Save preserves other fields in parent |
| `test_load_nested_existing` | Load existing nested text |
| `test_load_nested_missing_parent` | Load returns default if parent missing |
| `test_load_nested_missing_child` | Load returns default if child missing |

#### TestBoolFieldSave (6 tests)

| Test | Purpose |
|------|---------|
| `test_save_true` | Save True value |
| `test_save_false` | Save False value |
| `test_save_string_true_variants` | String 'true' variants normalize to True |
| `test_save_string_false_variants` | String 'false' variants normalize to False |
| `test_save_int_truthy` | Non-zero ints normalize to True |
| `test_save_int_falsy` | Zero normalizes to False |

#### TestBoolFieldLoad (9 tests)

| Test | Purpose |
|------|---------|
| `test_load_true` | Load True value |
| `test_load_false` | Load False value |
| `test_load_missing_uses_default_true` | Missing field returns default (True) |
| `test_load_missing_uses_default_false` | Missing field returns default (False) |
| `test_load_string_true` | Load string 'true' as True |
| `test_load_string_false` | Load string 'false' as False |
| `test_load_int_nonzero` | Load non-zero int as True |
| `test_load_int_zero` | Load zero as False |
| `test_load_none_uses_default` | None value returns default |

#### TestBoolFieldRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_true` | True roundtrip |
| `test_roundtrip_false` | False roundtrip |

#### TestNestedBoolFields (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_nested_bool` | Save nested bool creates parent |
| `test_load_nested_bool_existing` | Load existing nested bool |
| `test_load_nested_bool_missing` | Load missing nested bool returns default |

#### TestIntFieldSave (9 tests)

| Test | Purpose |
|------|---------|
| `test_save_positive_int` | Save positive integer |
| `test_save_negative_int` | Save negative integer |
| `test_save_zero` | Save zero |
| `test_save_string_int` | Save string '42' as 42 |
| `test_save_float_truncates` | Save float truncates to int |
| `test_save_string_float_truncates` | Save string '3.7' truncates to 3 |
| `test_save_clamps_to_min` | Save clamps to minimum |
| `test_save_clamps_to_max` | Save clamps to maximum |
| `test_save_invalid_uses_zero` | Invalid value becomes 0 |

#### TestIntFieldLoad (8 tests)

| Test | Purpose |
|------|---------|
| `test_load_existing_int` | Load existing int |
| `test_load_missing_uses_default` | Missing field returns default |
| `test_load_none_uses_default` | None value returns default |
| `test_load_string_int` | Load string '42' as 42 |
| `test_load_float_truncates` | Load float truncates to int |
| `test_load_clamps_to_min` | Load clamps to minimum |
| `test_load_clamps_to_max` | Load clamps to maximum |
| `test_load_invalid_uses_default` | Invalid value returns default |

#### TestIntFieldRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_positive` | Positive int roundtrip |
| `test_roundtrip_with_bounds` | Int roundtrip with bounds |

#### TestNestedIntFields (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_nested_int` | Save nested int creates parent |
| `test_load_nested_int_existing` | Load existing nested int |
| `test_nested_int_with_bounds` | Nested int with bounds clamping |

#### TestFloatFieldSave (7 tests)

| Test | Purpose |
|------|---------|
| `test_save_float` | Save float value |
| `test_save_int_as_float` | Save int as float |
| `test_save_string_float` | Save string '0.5' as 0.5 |
| `test_save_clamps_to_min` | Save clamps to minimum |
| `test_save_clamps_to_max` | Save clamps to maximum |
| `test_save_with_precision` | Save rounds to precision |
| `test_save_invalid_uses_zero` | Invalid value becomes 0.0 |

#### TestFloatFieldLoad (6 tests)

| Test | Purpose |
|------|---------|
| `test_load_existing_float` | Load existing float |
| `test_load_missing_uses_default` | Missing field returns default |
| `test_load_int_as_float` | Load int as float |
| `test_load_string_float` | Load string '0.5' as 0.5 |
| `test_load_clamps_to_min` | Load clamps to minimum |
| `test_load_clamps_to_max` | Load clamps to maximum |

#### TestFloatFieldRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_simple` | Simple float roundtrip |
| `test_roundtrip_with_bounds` | Float roundtrip with bounds |

#### TestNestedFloatFields (2 tests)

| Test | Purpose |
|------|---------|
| `test_save_nested_float` | Save nested float creates parent |
| `test_load_nested_float_existing` | Load existing nested float |

#### TestEnumFieldSave (4 tests)

| Test | Purpose |
|------|---------|
| `test_save_valid_option` | Save valid enum option |
| `test_save_invalid_uses_first` | Invalid option falls back to first |
| `test_save_none_uses_first` | None value falls back to first option |
| `test_save_case_sensitive` | Enum comparison is case-sensitive |

#### TestEnumFieldLoad (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_valid_option` | Load valid enum option |
| `test_load_invalid_uses_default` | Invalid stored value returns default |
| `test_load_missing_uses_default` | Missing field returns default |
| `test_load_none_uses_default` | None value returns default |

#### TestEnumFieldRoundtrip (1 test)

| Test | Purpose |
|------|---------|
| `test_roundtrip_valid` | Valid enum roundtrip |

#### TestNestedEnumFields (2 tests)

| Test | Purpose |
|------|---------|
| `test_save_nested_enum` | Save nested enum creates parent |
| `test_load_nested_enum_existing` | Load existing nested enum |

#### TestListFieldSave (5 tests)

| Test | Purpose |
|------|---------|
| `test_save_list` | Save list value |
| `test_save_empty_list` | Save empty list |
| `test_save_tuple_converts_to_list` | Tuple is converted to list |
| `test_save_none_becomes_empty` | None becomes empty list |
| `test_save_single_value_wraps` | Single non-list value is wrapped |

#### TestListFieldLoad (5 tests)

| Test | Purpose |
|------|---------|
| `test_load_existing_list` | Load existing list |
| `test_load_missing_uses_default_empty` | Missing field returns empty list by default |
| `test_load_missing_uses_custom_default` | Missing field returns custom default |
| `test_load_comma_string_parses` | Comma-separated string is parsed to list |
| `test_load_returns_copy` | Load returns a copy, not original |

#### TestListFieldRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_simple` | Simple list roundtrip |
| `test_roundtrip_mixed_types` | Mixed type list roundtrip |

#### TestNestedListFields (2 tests)

| Test | Purpose |
|------|---------|
| `test_save_nested_list` | Save nested list creates parent |
| `test_load_nested_list_existing` | Load existing nested list |

#### TestStringListFields (5 tests)

| Test | Purpose |
|------|---------|
| `test_save_string_list` | Save string list |
| `test_save_converts_to_strings` | Non-strings are converted to strings |
| `test_load_string_list` | Load string list |
| `test_load_converts_to_strings` | Non-strings are converted on load |
| `test_load_parses_comma_string` | Comma string is parsed |

#### TestDictFieldSave (4 tests)

| Test | Purpose |
|------|---------|
| `test_save_dict` | Save dict value |
| `test_save_empty_dict` | Save empty dict |
| `test_save_non_dict_becomes_empty` | Non-dict value becomes empty dict |
| `test_save_creates_copy` | Save creates a copy of the dict |

#### TestDictFieldLoad (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_existing_dict` | Load existing dict |
| `test_load_missing_uses_default_empty` | Missing field returns empty dict by default |
| `test_load_missing_uses_custom_default` | Missing field returns custom default |
| `test_load_returns_copy` | Load returns a copy, not original |

#### TestDictFieldRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_simple` | Simple dict roundtrip |
| `test_roundtrip_nested` | Nested dict roundtrip |

#### TestDirtyTracking (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_marks_dirty` | All save operations mark dirty |
| `test_multiple_saves_increment_dirty_count` | Multiple saves increment dirty count |
| `test_load_does_not_mark_dirty` | Load operations do not mark dirty |

#### TestEdgeCases (3 tests)

| Test | Purpose |
|------|---------|
| `test_empty_key` | Empty string key works |
| `test_unicode_key` | Unicode key works |
| `test_deeply_nested_parent_not_dict` | Handles case where parent is not a dict |

#### TestTypeValidation (3 tests)

| Test | Purpose |
|------|---------|
| `test_int_field_rejects_invalid_string` | Invalid string for int field uses fallback |
| `test_float_field_rejects_invalid_string` | Invalid string for float field uses fallback |
| `test_enum_with_empty_options_logs_warning` | Empty options list is handled gracefully |

#### TestCharacterNotesSave (7 tests)

| Test | Purpose |
|------|---------|
| `test_save_single_character` | Save a single character |
| `test_save_multiple_characters` | Save multiple characters |
| `test_save_character_all_fields` | All character fields are saved |
| `test_save_empty_list` | Saving empty list clears characters |
| `test_save_missing_fields_filled_with_empty` | Missing fields are filled with empty strings |
| `test_save_non_list_becomes_empty` | Non-list input becomes empty list |
| `test_save_filters_non_dict_items` | Non-dict items in list are filtered out |

#### TestCharacterNotesLoad (5 tests)

| Test | Purpose |
|------|---------|
| `test_load_single_character` | Load a single character |
| `test_load_missing_key_returns_empty` | Missing key returns empty list |
| `test_load_non_list_returns_empty` | Non-list value returns empty list |
| `test_load_fills_missing_fields` | Missing fields are filled with empty strings |
| `test_load_filters_non_dict_items` | Non-dict items are filtered out |

#### TestCharacterNotesRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_all_fields` | Roundtrip preserves all fields |
| `test_roundtrip_multiple_characters` | Roundtrip with multiple characters |

#### TestCodeGlossarySave (4 tests)

| Test | Purpose |
|------|---------|
| `test_save_single_pattern` | Save a single code pattern |
| `test_save_all_fields` | All pattern fields are saved |
| `test_save_default_action` | Default action is preserve |
| `test_save_empty_list` | Empty list clears patterns |

#### TestCodeGlossaryLoad (3 tests)

| Test | Purpose |
|------|---------|
| `test_load_single_pattern` | Load a single pattern |
| `test_load_missing_returns_empty` | Missing key returns empty list |
| `test_load_fills_defaults` | Missing fields filled with defaults |

#### TestCodeGlossaryRoundtrip (6 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_data` | Roundtrip preserves all data |
| `test_roundtrip_with_count_and_instances` | Roundtrip preserves count, raw_type, instances |
| `test_roundtrip_omits_empty_instances_in_manifest` | Empty instances not stored in manifest |
| `test_load_legacy_without_count` | Legacy patterns without count get defaults |
| `test_roundtrip_with_instance_counts` | instance_counts via list count format |
| `test_roundtrip_no_instance_counts_stays_int` | Count stays int without instance_counts |

#### TestProtectCodePatternsSave (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_single_pattern` | Save a single protect pattern |
| `test_save_all_fields` | All fields are saved |
| `test_save_default_is_regex_false` | Default is_regex is False |

#### TestProtectCodePatternsLoad (3 tests)

| Test | Purpose |
|------|---------|
| `test_load_patterns` | Load protect patterns |
| `test_load_missing_returns_empty` | Missing key returns empty list |
| `test_load_fills_defaults` | Missing fields filled with defaults |

#### TestProtectCodePatternsRoundtrip (1 test)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_data` | Roundtrip preserves all data |

#### TestCustomPlaceholdersSave (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_single_placeholder` | Save a single placeholder |
| `test_save_all_fields` | All fields are saved |
| `test_save_default_restore_after_true` | Default restore_after is True |

#### TestCustomPlaceholdersLoad (3 tests)

| Test | Purpose |
|------|---------|
| `test_load_placeholders` | Load custom placeholders |
| `test_load_missing_returns_empty` | Missing key returns empty list |
| `test_load_fills_defaults` | Missing fields filled with defaults |

#### TestCustomPlaceholdersRoundtrip (1 test)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_data` | Roundtrip preserves all data |

#### TestAnchorRemovalSave (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_single_anchor` | Save a single anchor pattern |
| `test_save_all_fields` | All fields are saved |
| `test_save_default_action_remove` | Default action is remove |

#### TestAnchorRemovalLoad (3 tests)

| Test | Purpose |
|------|---------|
| `test_load_anchors` | Load anchor patterns |
| `test_load_missing_returns_empty` | Missing key returns empty list |
| `test_load_fills_defaults` | Missing fields filled with defaults |

#### TestAnchorRemovalRoundtrip (1 test)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_data` | Roundtrip preserves all data |

#### TestGlossaryEntriesSave (4 tests)

| Test | Purpose |
|------|---------|
| `test_save_single_entry` | Save a single glossary entry |
| `test_save_all_fields` | All fields are saved |
| `test_save_creates_glossary_if_missing` | Creates glossary key if missing |
| `test_save_empty_list` | Empty list clears entries |

#### TestGlossaryEntriesLoad (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_entries` | Load glossary entries |
| `test_load_missing_glossary_returns_empty` | Missing glossary returns empty list |
| `test_load_missing_project_entries_returns_empty` | Missing project_entries returns empty list |
| `test_load_fills_defaults` | Missing fields filled with empty strings |

#### TestGlossaryEntriesRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_data` | Roundtrip preserves all data |
| `test_roundtrip_multiple_entries` | Roundtrip with multiple entries |

#### TestSpecialFormatIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_all_special_formats_coexist` | All special format data can coexist in manifest |
| `test_dirty_tracking_multiple_formats` | Each save operation marks dirty |

---

### dev/test_manifest_binding.py (37 tests)

GUI widget binding helpers for Task 22.3. Auto-save and auto-load between widgets and manifest fields.

#### TestBindingInfo (3 tests)

| Test | Purpose |
|------|---------|
| `test_init` | BindingInfo initializes correctly |
| `test_record_save` | record_save increments counter and stores value |
| `test_record_load` | record_load increments counter and stores value |

#### TestBindingRegistry (3 tests)

| Test | Purpose |
|------|---------|
| `test_registry_starts_empty` | Registry is empty at start |
| `test_clear_registry` | clear_binding_registry removes all bindings |
| `test_get_binding_for_field` | get_binding_for_field finds the right binding |

#### TestEntryBinding (7 tests)

| Test | Purpose |
|------|---------|
| `test_saves_on_change` | Entry saves to manifest when value changes |
| `test_loads_from_manifest` | Entry loads value from manifest |
| `test_loads_default_when_missing` | Entry loads default when field missing |
| `test_loads_default_when_no_manager` | Entry loads default when manager is None |
| `test_nested_field_saves` | Nested entry field saves correctly |
| `test_on_save_callback` | on_save callback is called after save |
| `test_adds_to_registry` | Binding is added to registry |

#### TestCheckboxBinding (4 tests)

| Test | Purpose |
|------|---------|
| `test_saves_on_change` | Checkbox saves to manifest when toggled |
| `test_loads_true` | Checkbox loads True value |
| `test_loads_false` | Checkbox loads False value |
| `test_loads_default_when_missing` | Checkbox loads default when field missing |

#### TestComboboxBinding (4 tests)

| Test | Purpose |
|------|---------|
| `test_saves_valid_option` | Combobox saves valid option |
| `test_loads_valid_option` | Combobox loads valid option from manifest |
| `test_loads_default_for_invalid` | Combobox loads default for invalid stored value |
| `test_validates_options` | Combobox validates against options on save |

#### TestSpinboxBinding (4 tests)

| Test | Purpose |
|------|---------|
| `test_saves_value` | Spinbox saves integer value |
| `test_clamps_to_min` | Spinbox clamps to minimum value |
| `test_clamps_to_max` | Spinbox clamps to maximum value |
| `test_loads_value` | Spinbox loads value from manifest |

#### TestTextBinding (3 tests)

| Test | Purpose |
|------|---------|
| `test_loads_multiline_text` | Text widget loads multiline text |
| `test_manual_save` | Text widget can save manually |
| `test_loads_default_when_missing` | Text widget loads default when field missing |

#### TestRadioBinding (2 tests)

| Test | Purpose |
|------|---------|
| `test_saves_on_selection` | Radio buttons save when selection changes |
| `test_loads_selection` | Radio buttons load selection from manifest |

#### TestFloatSpinboxBinding (3 tests)

| Test | Purpose |
|------|---------|
| `test_saves_float_value` | Float spinbox saves float value |
| `test_clamps_float_to_range` | Float spinbox clamps to range |
| `test_loads_float_value` | Float spinbox loads value from manifest |

#### TestLoadAllBindings (2 tests)

| Test | Purpose |
|------|---------|
| `test_loads_multiple_bindings` | load_all_bindings loads all bound widgets |
| `test_handles_missing_load_method` | load_all_bindings handles bindings without load method |

#### TestBindingIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_multiple_bindings_same_manifest` | Multiple bindings can share the same manifest |
| `test_roundtrip_save_load` | Values roundtrip through save and load |

---

### dev/test_manifest_overwrite.py (14 tests)

Phase 80 tests for manifest overwrite prevention. Verifies that step data merges preserve existing entries, RequestOptions are not overwritten during init, and info metadata survives round-trips.

#### TestPreprocessingDataPreservation (2 tests)

| Test | Purpose |
|------|---------|
| `test_update_step_data_preserves_existing_keys` | `_update_step_data()` keeps `dedup_map` and other stored results |
| `test_update_step_data_with_stats` | `_update_step_data()` merges `_last_stats` without losing existing keys |

#### TestInputDataPreservation (1 test)

| Test | Purpose |
|------|---------|
| `test_update_step_data_preserves_existing_keys` | `_update_step_data()` keeps `manifest_path` and `suggested_project_name` |

#### TestAnalysisDataPreservation (1 test)

| Test | Purpose |
|------|---------|
| `test_on_leave_preserves_existing_keys` | `on_leave()` merges `analysis_results` without discarding other keys |

#### TestRequestOptionsPreservation (3 tests)

| Test | Purpose |
|------|---------|
| `test_init_does_not_overwrite_api_key` | `_initializing` guard prevents `ApiKeyProvider`/`ApiKeyName` overwrites |
| `test_init_does_not_overwrite_model` | `_initializing` guard prevents `Model` overwrite from trace callback |
| `test_on_key_changed_skipped_during_init` | `_on_key_changed()` is no-op while `_initializing` is True |

#### TestInfoMetadataPreservation (2 tests)

| Test | Purpose |
|------|---------|
| `test_ensure_style_tone_skips_when_no_preset` | `_ensure_style_tone_text()` preserves text when preset missing from INI |
| `test_ensure_style_tone_replaces_when_preset_exists` | `_ensure_style_tone_text()` replaces text when preset found in INI |

#### TestManifestRoundTrip (3 tests)

| Test | Purpose |
|------|---------|
| `test_step_data_roundtrip` | Step data survives save → load cycle unchanged |
| `test_request_options_roundtrip` | RequestOptions survive save → load cycle unchanged |
| `test_info_metadata_roundtrip` | Info metadata survives save → load cycle unchanged |

#### TestManifestComparisonRegression (2 tests)

| Test | Purpose |
|------|---------|
| `test_request_options_not_reset_to_defaults` | Non-default RequestOptions are preserved after simulated init |
| `test_preprocessing_results_not_lost` | Preprocessing results survive when `_last_stats` is empty |

---

### dev/test_information_manifest.py (74 tests)

Phase 23 tests for InformationStep manifest integration. Tests all fields bound to manifest.

#### TestProjectNameField (4 tests)

| Test | Purpose |
|------|---------|
| `test_project_name_binding_created` | ProjectName binding exists |
| `test_project_name_saves_to_manifest` | ProjectName saves when changed |
| `test_project_name_loads_from_manifest` | ProjectName loads from manifest |
| `test_project_name_loads_default_when_missing` | ProjectName defaults to empty |

#### TestTitleField (3 tests)

| Test | Purpose |
|------|---------|
| `test_title_binding_created` | Title binding exists |
| `test_title_saves_to_manifest` | Title saves when changed |
| `test_title_loads_from_manifest` | Title loads from manifest |

#### TestGenreField (3 tests)

| Test | Purpose |
|------|---------|
| `test_genre_binding_created` | Genre binding exists |
| `test_genre_saves_to_manifest` | Genre saves when changed |
| `test_genre_loads_from_manifest` | Genre loads from manifest |

#### TestSourceLanguageField (4 tests)

| Test | Purpose |
|------|---------|
| `test_source_language_binding_created` | SourceLanguage binding exists |
| `test_source_language_saves_to_manifest` | SourceLanguage saves when changed |
| `test_source_language_loads_from_manifest` | SourceLanguage loads from manifest |
| `test_source_language_default_is_japanese` | SourceLanguage defaults to Japanese |

#### TestTargetLanguageField (4 tests)

| Test | Purpose |
|------|---------|
| `test_target_language_binding_created` | TargetLanguage binding exists |
| `test_target_language_saves_to_manifest` | TargetLanguage saves when changed |
| `test_target_language_loads_from_manifest` | TargetLanguage loads from manifest |
| `test_target_language_default_is_english` | TargetLanguage defaults to English |

#### TestSummaryField (4 tests)

| Test | Purpose |
|------|---------|
| `test_summary_binding_created` | Summary binding exists |
| `test_summary_loads_from_manifest` | Summary loads from manifest |
| `test_summary_loads_multiline_text` | Summary supports multiline |
| `test_summary_default_is_empty` | Summary defaults to empty |

#### TestLanguageFieldsPersist (1 test)

| Test | Purpose |
|------|---------|
| `test_language_roundtrip` | Languages persist across step recreation |

#### TestBasicMetadataIntegration (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_basic_fields_coexist` | All basic fields save together |
| `test_dirty_tracking_for_all_fields` | Field changes mark manifest dirty |
| `test_binding_count` | Expected binding count after Task 23.1 |
| `test_all_bindings_have_load_method` | All bindings support loading |

#### TestManifestNotLoaded (3 tests)

| Test | Purpose |
|------|---------|
| `test_no_crash_when_manifest_none` | Step works without manifest |
| `test_load_uses_defaults_when_no_manager` | Fields use defaults without manager |
| `test_load_skipped_when_not_loaded` | Load skipped gracefully |

#### TestStylePresetField (4 tests)

| Test | Purpose |
|------|---------|
| `test_style_preset_binding_created` | StylePreset binding exists |
| `test_style_preset_saves_to_manifest` | StylePreset saves when changed |
| `test_style_preset_loads_from_manifest` | StylePreset loads from manifest |
| `test_style_preset_default_is_natural` | StylePreset defaults to Natural |

#### TestCustomStyleField (3 tests)

| Test | Purpose |
|------|---------|
| `test_custom_style_binding_created` | CustomStyle binding exists |
| `test_custom_style_saves_to_manifest` | CustomStyle saves when changed |
| `test_custom_style_loads_from_manifest` | CustomStyle loads from manifest |

#### TestTonePresetField (4 tests)

| Test | Purpose |
|------|---------|
| `test_tone_preset_binding_created` | TonePreset binding exists |
| `test_tone_preset_saves_to_manifest` | TonePreset saves when changed |
| `test_tone_preset_loads_from_manifest` | TonePreset loads from manifest |
| `test_tone_preset_default_is_neutral` | TonePreset defaults to Neutral |

#### TestCustomToneField (3 tests)

| Test | Purpose |
|------|---------|
| `test_custom_tone_binding_created` | CustomTone binding exists |
| `test_custom_tone_saves_to_manifest` | CustomTone saves when changed |
| `test_custom_tone_loads_from_manifest` | CustomTone loads from manifest |

#### TestStyleToneRoundtrip (4 tests)

| Test | Purpose |
|------|---------|
| `test_style_preset_roundtrip` | StylePreset persists across recreation |
| `test_tone_preset_roundtrip` | TonePreset persists across recreation |
| `test_custom_style_with_custom_preset` | Custom preset with custom style |
| `test_all_style_tone_fields_coexist` | All style/tone fields save together |

#### TestTask232BindingCount (1 test)

| Test | Purpose |
|------|---------|
| `test_binding_count_after_task_232` | ≥10 bindings after Tasks 23.1+23.2 (now 12 with SIPreset) |

#### TestCharacterNotesManifest (6 tests)

| Test | Purpose |
|------|---------|
| `test_add_character_saves_to_manifest` | Adding character saves |
| `test_load_characters_from_manifest` | Characters load from manifest |
| `test_empty_characters_default` | Empty default character list |
| `test_multiple_characters_roundtrip` | Multiple characters persist |
| `test_character_edit_saves_to_manifest` | Editing character saves |
| `test_character_remove_saves_to_manifest` | Removing character saves |

#### TestCodeGlossaryManifest (5 tests)

| Test | Purpose |
|------|---------|
| `test_add_code_pattern_saves_to_manifest` | Adding pattern saves |
| `test_load_code_patterns_from_manifest` | Patterns load from manifest |
| `test_multiple_patterns_roundtrip` | Multiple patterns persist |
| `test_pattern_edit_saves_to_manifest` | Editing pattern saves |
| `test_pattern_remove_saves_to_manifest` | Removing pattern saves |

#### TestTask233Integration (4 tests)

| Test | Purpose |
|------|---------|
| `test_characters_and_patterns_coexist` | Characters and patterns save together |
| `test_dirty_tracking_for_characters` | Character changes mark dirty |
| `test_dirty_tracking_for_patterns` | Pattern changes mark dirty |
| `test_no_save_when_no_manager` | Save handles missing manager |

#### TestPromptField (5 tests)

| Test | Purpose |
|------|---------|
| `test_prompt_binding_created` | Prompt binding exists |
| `test_prompt_saves_to_manifest` | Prompt saves via FocusOut |
| `test_prompt_loads_from_manifest` | Prompt loads from manifest |
| `test_prompt_default_is_empty` | Prompt defaults to empty |
| `test_prompt_multiline_text` | Prompt supports multiline |

#### TestPromptFieldRoundtrip (2 tests)

| Test | Purpose |
|------|---------|
| `test_prompt_roundtrip_persistence` | Prompt persists across recreation |
| `test_prompt_with_special_characters` | Prompt handles special chars |

#### TestTask234Integration (3 tests)

| Test | Purpose |
|------|---------|
| `test_prompt_coexists_with_other_fields` | Prompt saves with other fields |
| `test_binding_count_after_task_234` | 11 bindings after Task 23.4 |
| `test_prompt_dirty_tracking` | Prompt changes mark dirty |

---

### dev/test_preprocess_manifest.py (50 tests)

Phase 24 tests for PreprocessingStep manifest integration. Tests all preprocessing options bound to manifest.

- Includes widget/manifest binding coverage for PreprocessingStep. The helper-based passive-preview regression was reverted back to the `9721cba` bulk persistence path, so the focused rollback validation now lives in the persistence tests below.

Focused rollback validation:

- `dev/test_line_saving.py::TestSetLineField`
- `dev/test_line_saving.py::TestRoundTrip`
- `dev/test_line_saving.py::TestPreprocessIntegration`
- `dev/test_manifest_overwrite.py`

Verified command:

```bash
python -m pytest CherryAI/dev/test_line_saving.py::TestSetLineField CherryAI/dev/test_line_saving.py::TestRoundTrip CherryAI/dev/test_line_saving.py::TestPreprocessIntegration CherryAI/dev/test_manifest_overwrite.py -q --timeout=10
```

Latest verified result: 29 passed.

#### TestDeduplicationField (4 tests)

| Test | Purpose |
|------|---------|
| `test_deduplication_binding_created` | Deduplication binding exists |
| `test_deduplication_saves_to_manifest` | Deduplication saves when changed |
| `test_deduplication_loads_from_manifest` | Deduplication loads from manifest |
| `test_deduplication_default_is_true` | Deduplication defaults to True |

#### TestDeduplicationThresholdField (4 tests)

| Test | Purpose |
|------|---------|
| `test_threshold_binding_created` | Threshold binding exists |
| `test_threshold_saves_to_manifest` | Threshold saves when changed |
| `test_threshold_loads_from_manifest` | Threshold loads from manifest |
| `test_threshold_default_is_one` | Threshold defaults to 1 |

#### TestEllipsisCompressionField (3 tests)

| Test | Purpose |
|------|---------|
| `test_ellipsis_binding_created` | Ellipsis binding exists |
| `test_ellipsis_saves_to_manifest` | Ellipsis saves when changed |
| `test_ellipsis_loads_from_manifest` | Ellipsis loads from manifest |

#### TestSymbolConversionField (3 tests)

| Test | Purpose |
|------|---------|
| `test_symbol_binding_created` | Symbol binding exists |
| `test_symbol_saves_to_manifest` | Symbol saves when changed |
| `test_symbol_default_is_true` | Symbol defaults to True |

#### TestProtCompressionField (2 tests)

| Test | Purpose |
|------|---------|
| `test_prot_binding_created` | PROTECTED binding exists |
| `test_prot_saves_to_manifest` | PROTECTED saves when changed |

#### TestSpeakerReplacementField (3 tests)

| Test | Purpose |
|------|---------|
| `test_speaker_binding_created` | Speaker binding exists |
| `test_speaker_saves_to_manifest` | Speaker saves when changed |
| `test_speaker_default_is_false` | Speaker defaults to False |

#### TestCodeSpacingField (3 tests)

| Test | Purpose |
|------|---------|
| `test_spacing_binding_created` | Spacing binding exists |
| `test_spacing_saves_to_manifest` | Spacing saves when changed |
| `test_spacing_default_is_false` | Spacing defaults to False |

#### TestTask241Integration (5 tests)

| Test | Purpose |
|------|---------|
| `test_all_standard_toggles_coexist` | All toggles save together |
| `test_binding_count_after_task_241` | 7 bindings for standard toggles |
| `test_dirty_tracking_for_toggles` | Toggle changes mark dirty |
| `test_no_crash_when_manifest_not_loaded` | Handles unloaded manifest |
| `test_roundtrip_persistence` | Toggles persist across recreation |

#### TestProtectCodePatternsField (6 tests)

| Test | Purpose |
|------|---------|
| `test_save_method_exists` | Save method exists |
| `test_load_method_exists` | Load method exists |
| `test_patterns_save_to_manifest` | Patterns save to manifest |
| `test_patterns_load_from_manifest` | Patterns load from manifest |
| `test_listbox_updated_on_load` | Listbox updates on load |
| `test_manifest_format_conversion` | Format conversion works |

#### TestTask242Integration (3 tests)

| Test | Purpose |
|------|---------|
| `test_patterns_roundtrip` | Patterns persist through cycle |
| `test_empty_patterns_handled` | Empty list handled |
| `test_no_crash_when_manifest_empty` | Handles empty manifest |

#### TestCustomPlaceholdersField (5 tests)

| Test | Purpose |
|------|---------|
| `test_save_method_exists` | Save method exists |
| `test_load_method_exists` | Load method exists |
| `test_placeholders_save_to_manifest` | Placeholders save to manifest |
| `test_placeholders_load_from_manifest` | Placeholders load from manifest |
| `test_manifest_format_conversion` | Format conversion works |

#### TestAnchorRemovalField (5 tests)

| Test | Purpose |
|------|---------|
| `test_save_method_exists` | Save method exists |
| `test_load_method_exists` | Load method exists |
| `test_anchor_saves_to_manifest` | Anchor settings save |
| `test_anchor_loads_from_manifest` | Anchor settings load |
| `test_disabled_anchor_saves_empty_list` | Disabled saves empty |

#### TestTask243Integration (3 tests)

| Test | Purpose |
|------|---------|
| `test_placeholders_roundtrip` | Placeholders persist |
| `test_anchor_roundtrip` | Anchors persist |
| `test_all_task_243_features_coexist` | All features work together |

---

### dev/test_modi_v2.py (14 tests)

Modi module prepro_ops integration tests.

#### TestProtectCodePrepro (2 tests)

| Test | Purpose |
|------|---------|
| `test_prepro_ops_written_in_apply_pre` | Protect Code writes to prepro_ops during apply_pre |
| `test_prepro_ops_read_in_apply_post` | Protect Code reads from prepro_ops during apply_post |

#### TestCustomPlaceholderPrepro (2 tests)

| Test | Purpose |
|------|---------|
| `test_prepro_ops_written_in_apply_pre` | Custom Placeholder writes to prepro_ops |
| `test_roundtrip_with_prepro_ops` | Custom Placeholder roundtrips correctly |

#### TestTemporaryReplacementPrepro (2 tests)

| Test | Purpose |
|------|---------|
| `test_prepro_ops_written_in_apply_pre` | Temporary Replacement writes to prepro_ops |
| `test_roundtrip_with_prepro_ops` | Temporary Replacement roundtrips correctly |

#### TestStandardModePrepro (3 tests)

| Test | Purpose |
|------|---------|
| `test_ellipsis_prepro_ops_written` | Standard Mode writes ellipsis info to prepro_ops |
| `test_empty_line_prepro_ops_written` | Standard Mode writes empty_line flag |
| `test_ellipsis_roundtrip` | Standard Mode correctly restores ellipsis |

#### TestAnchorPrepro (2 tests)

| Test | Purpose |
|------|---------|
| `test_prepro_ops_written_in_apply_pre` | Anchor mode writes to prepro_ops |
| `test_anchor_legacy_mappings_written` | Anchor mode writes legacy mappings for compat |

#### TestPreproOpsFiltering (1 test)

| Test | Purpose |
|------|---------|
| `test_filter_by_mode` | get_prepro_ops returns only ops for specified mode |

#### TestPreproOpsDataIntegrity (2 tests)

| Test | Purpose |
|------|---------|
| `test_protect_code_data_structure` | Protect Code stores correct data structure |
| `test_custom_placeholder_data_structure` | Custom Placeholder stores correct data structure |

---

### dev/test_modi_all.py (44 tests) - NEW (TASK 15.6)

Comprehensive tests for all modi modules verifying attributes, functions, and operations.

#### TestModiLoader (3 tests)

| Test | Purpose |
|------|---------|
| `test_load_modes_populates_registry` | load_modes() populates MODE_REGISTRY |
| `test_all_registered_modes_have_name` | All registered modes have NAME attribute |
| `test_all_registered_modes_have_phase` | All registered modes have valid PHASE |

#### TestFreeMode (5 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Free mode has NAME, PHASE, PRIORITY, USES_REGEX |
| `test_apply_pre_regex_replacement` | apply_pre replaces with regex |
| `test_apply_pre_literal_replacement` | apply_pre replaces literal strings |
| `test_apply_post_replacement` | apply_post uses in3/in4 |
| `test_no_match_returns_zero` | Returns 0 when no matches |

#### TestOnlyRemoveMode (4 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Only Remove has NAME, PHASE, PRIORITY |
| `test_apply_pre_removes_pattern` | Removes matched pattern |
| `test_no_apply_post` | Has no apply_post (Pre-only) |
| `test_empty_pattern_returns_zero` | Returns 0 for empty pattern |

#### TestReplaceBeforeMode (4 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Replace Before has NAME, PHASE, PRIORITY |
| `test_apply_pre_regex` | apply_pre replaces with regex |
| `test_apply_pre_literal` | apply_pre replaces literal strings |
| `test_no_apply_post` | Has no apply_post (Pre-only) |

#### TestReplaceAfterMode (4 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Replace After has NAME, PHASE, PRIORITY |
| `test_apply_post_regex` | apply_post replaces with regex |
| `test_apply_post_literal` | apply_post replaces literal strings |
| `test_no_apply_pre` | Has no apply_pre (Post-only) |

#### TestSabotageMode (4 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Sabotage has NAME, PHASE, PRIORITY=1000, ALWAYS_ON_DRY_RUN |
| `test_apply_pre_does_nothing_when_not_dry_run` | Returns 0 when not dry run |
| `test_apply_pre_transforms_japanese_in_dry_run` | Transforms Japanese in dry run |
| `test_is_japanese_char_helper` | _is_japanese_char helper works correctly |

#### TestAnchorMode (5 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Anchor has NAME, PHASE, PRIORITY=15 |
| `test_parse_anchor_spec_boundary` | Parses line_start/line_end |
| `test_parse_anchor_spec_character` | Parses before:/after:/around: |
| `test_parse_anchor_spec_multiple` | Parses multiple anchors |
| `test_cluster_adjacent_removals` | Groups adjacent removals correctly |

#### TestProtectCodeMode (3 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Protect Code has NAME, PHASE, PRIORITY=15 |
| `test_apply_pre_replaces_with_prot` | Replaces with __PROTECTED__ |
| `test_apply_post_restores_values` | Restores protected values |

#### TestCustomPlaceholderMode (3 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Custom Placeholder has NAME, PHASE, PRIORITY=10 |
| `test_apply_pre_replaces_with_token` | Replaces pattern with token |
| `test_roundtrip` | Correctly roundtrips |

#### TestTemporaryReplacementMode (3 tests)

| Test | Purpose |
|------|---------|
| `test_attributes` | Temporary Replacement has NAME, PHASE, PRIORITY |
| `test_apply_pre_with_replacement` | Replaces with specified value |
| `test_apply_pre_with_empty_replacement` | Generates placeholder when empty |

#### TestTemplateModeDocumentation (2 tests)

| Test | Purpose |
|------|---------|
| `test_no_name_attribute` | Template mode has no NAME (documentation only) |
| `test_has_apply_functions` | Has placeholder apply functions returning 0 |

#### TestModeIntegrationConsistency (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_pre_modes_have_apply_pre` | All Pre-phase modes have apply_pre |
| `test_all_post_modes_have_apply_post` | All Post-phase modes have apply_post |
| `test_both_phase_modes_have_both_functions` | Both-phase modes have both |
| `test_all_modes_have_priority` | All modes have PRIORITY |

---

### dev/test_formats.py (57 tests) - NEW (TASK 15.7)

Comprehensive tests for all formats/ modules verifying handlers, registry, and operations.

#### TestFormatRegistry (8 tests)

| Test | Purpose |
|------|---------|
| `test_get_registry_returns_registry` | get_registry() returns FormatRegistry |
| `test_registry_has_txt_handler` | Registry includes TxtHandler |
| `test_registry_get_by_extension` | Registry finds handler by .extension |
| `test_registry_get_by_extension_with_dot` | Extension lookup handles leading dot |
| `test_registry_list_formats` | list_formats() returns format info |
| `test_registry_list_extensions` | list_extensions() returns extensions |
| `test_get_handler_by_id` | get_handler() works with format ID |
| `test_get_handler_by_extension` | get_handler() works with extension |

#### TestIOConfig (4 tests)

| Test | Purpose |
|------|---------|
| `test_ioconfig_default_values` | IOConfig default values correct |
| `test_ioconfig_to_dict` | to_dict() serializes correctly |
| `test_ioconfig_from_dict` | from_dict() deserializes correctly |
| `test_ioconfig_from_dict_missing_keys` | Missing keys use defaults |

#### TestTxtHandler (5 tests)

| Test | Purpose |
|------|---------|
| `test_txt_handler_format_id` | TxtHandler has format_id, extensions |
| `test_txt_extract` | extract() reads lines correctly |
| `test_txt_inject` | inject() writes lines correctly |
| `test_txt_roundtrip` | Extract then inject preserves content |
| `test_txt_unicode_handling` | Handles Unicode correctly |

#### TestCsvHandler (4 tests)

| Test | Purpose |
|------|---------|
| `test_csv_handler_format_id` | CsvHandler has format_id, supports_pairs |
| `test_csv_extract` | extract() reads first column |
| `test_csv_inject_with_pairs` | inject() writes both columns |
| `test_csv_inject_without_pairs` | inject() writes single column |

#### TestTsvHandler (3 tests)

| Test | Purpose |
|------|---------|
| `test_tsv_handler_format_id` | TsvHandler has format_id, supports_pairs |
| `test_tsv_extract` | extract() reads first column |
| `test_tsv_inject_with_pairs` | inject() writes tab-separated pairs |

#### TestJsonHandler (13 tests)

| Test | Purpose |
|------|---------|
| `test_json_handler_format_id` | JsonHandler has format_id, supports_pairs |
| `test_json_extract_string_array` | Handles array of strings |
| `test_json_extract_pairs_array` | Handles [original, translated] pairs |
| `test_json_extract_object_array` | Handles objects with original/translated |
| `test_json_inject_simple` | Writes array of strings |
| `test_json_inject_with_pairs` | Writes objects when original provided |
| `test_json_get_metadata` | get_metadata() returns structure info |
| `test_json_extract_dictionary_format` | extract() handles dict format (keys=source) |
| `test_json_extract_with_translations_dictionary` | extract_with_translations() returns pairs |
| `test_json_get_metadata_dictionary` | get_metadata() detects "dictionary" structure |
| `test_json_inject_dict_format` | inject_dict() writes dictionary format |
| `test_json_preserve_dict_format_on_inject` | inject(preserve_format=True) keeps dict format |

#### TestXlsxHandler (4 tests)

| Test | Purpose |
|------|---------|
| `test_xlsx_handler_format_id` | XlsxHandler has format_id |
| `test_xlsx_check_openpyxl` | _check_openpyxl() detects package |
| `test_xlsx_extract` | extract() reads column A (requires openpyxl) |
| `test_xlsx_inject` | inject() writes to Excel (requires openpyxl) |

#### TestHtmlHandler (5 tests)

| Test | Purpose |
|------|---------|
| `test_html_handler_format_id` | HtmlHandler has format_id |
| `test_html_extract_simple` | extract() extracts text (requires bs4) |
| `test_html_skip_script_style` | Skips script/style tags |
| `test_html_inline_tags_preserved` | Preserves inline tag placeholders |
| `test_html_get_metadata` | get_metadata() returns HTML info |

#### TestDocumentPlaceholders (4 tests)

| Test | Purpose |
|------|---------|
| `test_pdf_handler_is_placeholder` | PdfHandler returns empty list |
| `test_epub_handler_is_placeholder` | EpubHandler returns empty list |
| `test_pdf_get_metadata_shows_not_implemented` | PDF metadata shows not implemented |
| `test_epub_get_metadata_shows_not_implemented` | EPUB metadata shows not implemented |

#### TestRpgMakerPlaceholders (3 tests)

| Test | Purpose |
|------|---------|
| `test_rpgmaker_mv_handler_is_placeholder` | RpgMakerMVHandler placeholder |
| `test_rpgmaker_mz_handler_is_placeholder` | RpgMakerMZHandler placeholder |
| `test_rpgmaker_plugin_handler_is_placeholder` | RpgMakerPluginHandler placeholder |

#### TestFormatIntegration (5 tests)

| Test | Purpose |
|------|---------|
| `test_all_handlers_have_format_id` | All handlers define format_id |
| `test_all_handlers_have_extract_inject` | All have extract() and inject() |
| `test_txt_to_json_workflow` | Convert txt to json format |
| `test_handler_supports_original_consistency` | supports_original() matches supports_pairs |
| `test_get_handlers_returns_all_simple` | get_handlers() returns all simple handlers |

---

### dev/test_functions_v2.py (15 tests)

Functions module v2.0 integration tests.

#### TestPostanalysisV2 (4 tests)

| Test | Purpose |
|------|---------|
| `test_compare_uses_lines_array` | Compare reads from manifest.lines[idx].orig |
| `test_compare_detects_differences` | Compare detects when final text differs |
| `test_compare_with_processed_manifest` | Compare works with fully processed manifest |
| `test_compare_updates_lines_array_on_autofix` | Lines array updated on auto-fix |

#### TestManifestInitialization (3 tests)

| Test | Purpose |
|------|---------|
| `test_initialize_from_text_creates_lines` | initialize_from_text creates LineEntry per line |
| `test_initialize_sets_correct_indices` | Each LineEntry has correct idx |
| `test_get_original_text_reconstructs` | get_original_text reconstructs from lines |

#### TestLineEntryIntegration (5 tests)

| Test | Purpose |
|------|---------|
| `test_ensure_line_creates_if_missing` | ensure_line creates new LineEntry if not exists |
| `test_ensure_line_returns_existing` | ensure_line returns existing LineEntry |
| `test_set_field_works_for_translation` | set_field allows setting tl field |
| `test_add_prepro_op_to_line` | add_prepro_op adds operation data to line |
| `test_get_prepro_ops_filters_by_mode` | get_prepro_ops with mode filter returns matching |

#### TestSerializationRoundtrip (3 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_to_dict_includes_lines` | to_dict includes lines array for v2.0 |
| `test_manifest_from_dict_restores_lines` | from_dict restores lines array |
| `test_full_workflow_roundtrip` | Complete workflow: create, process, serialize, restore |

---

### dev/test_replication.py (40 tests)

Game update detection and translation update generation tests.

#### TestChangeDetectorHashing (3 tests)

| Test | Purpose |
|------|---------|
| `test_hash_text_produces_sha256` | hash_text produces consistent SHA-256 hash |
| `test_hash_text_different_for_different_content` | Different text produces different hash |
| `test_hash_text_unicode_support` | hash_text handles Unicode correctly |

#### TestChangeDetectorTextMatch (4 tests)

| Test | Purpose |
|------|---------|
| `test_texts_match_identical` | Identical texts match |
| `test_texts_match_different` | Different texts don't match |
| `test_texts_match_both_none` | Two None values match |
| `test_texts_match_one_none` | One None value doesn't match text |

#### TestChangeDetectorLineDetection (6 tests)

| Test | Purpose |
|------|---------|
| `test_detect_unchanged_line` | Detects unchanged line correctly |
| `test_detect_modified_line` | Detects modified line correctly |
| `test_detect_new_line` | Detects new line (no old entry) |
| `test_detect_deleted_line` | Detects deleted line (no new text) |
| `test_detect_has_translation_work` | Detects if line has existing translation |
| `test_detect_has_translation_with_passes` | Detects translation from TLC/Edit passes |
| `test_detect_no_translation_work` | Identifies line without translation work |

#### TestManifestComparisonWithText (5 tests)

| Test | Purpose |
|------|---------|
| `test_no_changes` | Detects no changes when text is identical |
| `test_modified_line` | Detects modified line correctly |
| `test_new_line_added` | Detects new line at end |
| `test_line_deleted` | Detects deleted line when text is shorter |
| `test_multiple_changes` | Detects multiple types of changes |

#### TestManifestComparisonBetweenManifests (2 tests)

| Test | Purpose |
|------|---------|
| `test_identical_manifests` | Detects no changes between identical manifests |
| `test_modified_between_manifests` | Detects modification between manifests |

#### TestComparisonResult (5 tests)

| Test | Purpose |
|------|---------|
| `test_total_changes` | total_changes sums modified + new + deleted |
| `test_has_changes_true` | has_changes is True when changes exist |
| `test_has_changes_false` | has_changes is False when no changes |
| `test_get_changes_by_type` | get_changes_by_type filters correctly |
| `test_to_dict_excludes_unchanged` | to_dict excludes unchanged from changes list |

#### TestUpdateOutputGeneratorManifest (3 tests)

| Test | Purpose |
|------|---------|
| `test_generates_update_manifest_with_new_lines` | Generates manifest with new lines |
| `test_preserves_translation_on_modified` | Preserves existing translation on modified |
| `test_includes_context_lines` | Includes context lines when requested |

#### TestUpdateOutputGeneratorText (2 tests)

| Test | Purpose |
|------|---------|
| `test_generates_text_with_line_numbers` | Generates text with line numbers and markers |
| `test_generates_text_without_line_numbers` | Generates plain text without markers |

#### TestUpdateOutputGeneratorMerge (2 tests)

| Test | Purpose |
|------|---------|
| `test_merge_updates_into_original` | Merges update manifest back into original |
| `test_merge_marks_deleted` | Merge preserves deleted flag |

#### TestConvenienceFunctions (2 tests)

| Test | Purpose |
|------|---------|
| `test_compare_manifest_with_source` | compare_manifest_with_source works with files |
| `test_generate_update_files` | generate_update_files creates output files |

#### TestEdgeCases (5 tests)

| Test | Purpose |
|------|---------|
| `test_empty_manifest_comparison` | Handles empty manifest correctly |
| `test_empty_text_comparison` | Handles empty new text correctly |
| `test_whitespace_differences` | Detects whitespace-only differences |
| `test_unicode_comparison` | Handles Unicode content correctly |
| `test_large_index_gaps` | Handles non-contiguous line indices |

---

## functions/One_Click_Test.py (API Test)

7-stage integration test with optional LLM API calls.

### Stage Details

#### Stage 1: Dependencies
- Checks all required packages are installed
- Uses `check_dependencies()` from dependencies.py
- Reports missing required and optional packages
- **Pass Criteria:** No fatal dependency errors

#### Stage 2: Configuration
- Validates config file existence and format
- Checks API key is set
- Ensures config auto-initialization runs
- Reports provider, model, and key status
- **Pass Criteria:** Configuration valid for API calls

#### Stage 3: File I/O
- Tests write and read cycle to temp directory
- Uses `read_text()` and `write_text()` from mainhelper
- Validates content integrity after round-trip
- Cleans up test file after validation
- **Pass Criteria:** Content matches after write/read

#### Stage 4: Pre-Processing
- Creates Manifest with sample Japanese text
- Uses `initialize_from_text()` for v2.0 lines array
- Runs `prepare_auto_translate()` pipeline
- Validates batches and estimation structure
- **Pass Criteria:** Valid batch structure, lines array populated

#### Stage 5: API Connection
- Creates APIClient instance
- Fetches available models as connectivity test
- Reports provider and model information
- **Pass Criteria:** API client initialized, connectivity confirmed
- **Skippable:** Use `--skip-api` flag

#### Stage 6: Translation
- Sends minimal sample (2 lines) to minimize cost
- Validates line count matches input
- Reports sample input/output
- **Pass Criteria:** Received translations match line count
- **Skippable:** Use `--skip-api` flag

#### Stage 7: Post-Processing
- Creates manifest with simulated translations
- Sets up prepro_ops for placeholder restoration
- Tests v2.0 lines array with translation data
- **Pass Criteria:** Post-processing logic available

### Test Samples

```python
SAMPLE_TEXT_JP = """
田中さん、おはようございます。
彼女は優しく微笑んだ。
\\n[wait:500]
今日の天気は良いです。
ありがとう。
"""

SAMPLE_TEXT_EN = """
Good morning, Mr. Tanaka.
She smiled gently.
\\n[wait:500]
The weather is nice today.
Thank you.
"""
```

---

## Test Maintenance Guidelines

### Adding New Tests

1. **Script Tests:** Add to appropriate `test_*.py` file
2. **Update counts:** Update test counts in documentation (tests.md, features.md, technical.md, MANIFEST_UPDATE_DESIGN.md)
3. **Run validation:** Execute `pytest dev/test_*.py -v` to verify all pass

### When Tests Fail

1. **Check recent changes:** What was modified since last passing run?
2. **Isolate failure:** Run single failing test with `-v` flag
3. **Review test assumptions:** Does test match current implementation?
4. **Fix code or test:** Update implementation or correct test expectation

### Test Count Summary

| File | Tests | Category |
|------|-------|----------|
| test_anchor_clustering_prot.py | 2 | Anchor clustering (integration, skipped) |
| test_api_validation.py | 52 | API response validation (TASK 4) |
| test_auto_tagger.py | 122 | Auto-tagging system (Manifest v2.1) |
| test_balanced_code_detection.py | 5 | Balanced code detection |
| test_br_protection.py | 26 | BR tag protection |
| test_chunk_optimizer.py | 31 | Chunk optimization |
| test_chunker.py | 39 | Chunker module |
| test_cli_languages.py | 32 | CLI language selection |
| test_cli_overrides.py | 38 | CLI API overrides (TASK 3) |
| test_cli_progress.py | 17 | CLI progress indicators (TASK 15.12) |
| test_common_errors.py | 31 | Common error handling |
| test_conditional_prompts.py | 86 | Conditional prompts — 11 pattern-triggered prompts, INI overrides, merged requests |
| test_config.py | 23 | Config management |
| test_dedup.py | 34 | Deduplication + tag storage + top-N limit |
| test_dependencies.py | 17 | Dependency checking (TASK 15.1) |
| test_formats.py | 57 | Formats module handlers (TASK 15.7) |
| test_functions_v2.py | 15 | Functions integration |
| test_game_summary.py | 22 | Game summary & project config |
| test_gender_inference.py | 21 | Gender inference |
| test_gender_batch.py | 31 | Batch gender inference |
| test_glossary.py | 30 | Glossary management |
| test_gui_analysis_integration.py | 45 | GUI-Analysis integration (TASK 16.6 + 18.1) |
| test_gui_chunker_integration.py | 87 | GUI-Chunker integration (TASK 16.8) |
| test_gui_glossary_integration.py | 76 | GUI-Glossary integration (TASK 16.7) |
| test_gui_modi_integration.py | 45 | GUI-Modi integration (TASK 16.5) |
| test_gui_progress.py | 24 | GUI progress indicators (TASK 15.12) |
| test_gui_v2.py | 595 | GUI v2 framework (TASK 15.8-15.14: core + theme/CLI/deprecated) |
| test_session_persistence.py | 40 | Session auto-save/load, step persistence, file restoration (Release Stabilization) |
| test_folder_loading.py | 23 | Folder loading in InputExtractionStep |
| test_input_step_phase39.py | 40 | Input step Phase 39 improvements (unified selector, treeview, format filtering, progress, parser-selected auto encoding, output default seeding) |
| test_input_step_improvements.py | 60 | Input step Phase 60 improvements (type column refresh, clickable sort headers, file filter, cross-file preview search) |
| test_costs_step_phase40.py | 57 | Costs step Phase 40+78 improvements (rename, dual estimation, dual ticks, concurrent time, prepro lines, prompt overhead, preview tokens) |
| test_costs_api_rework.py | 35 | API Requests & Costs rework (cache calculation, mode buttons, instant recalculation, model lock, settings decoupling, button rename, translation request mode, fast reprice on model change) |
| test_costs_additive_display.py | 30 | Additive cost display rework (ceil-to-cents, content-only input_cost, non-cached prompt tokens, label layout, additive total) |
| test_estimate_manifest.py | 33 | Estimation/Analysis manifest integration (TASK 25.1, 25.2) |
| test_qa_manifest.py | 19 | QA step manifest integration (TASK 26.1 + stage-bounded QA input resolution) |
| test_translate_manifest.py | 47 | Translation step manifest integration (TASK 26.2) |
| test_postprocess_manifest.py | 35 | Postprocessing step manifest integration (TASK 27.1) |
| test_wordwrap_manifest.py | 40 | Wordwrap step manifest integration (TASK 28.1) |
| test_output_manifest.py | 48 | Output step manifest integration (TASK 28.2 + output destination/defaults) |
| test_autosave.py | 24 | ManifestManager autosave system (TASK 29.1) |
| test_save_triggers.py | 17 | Save trigger functionality (TASK 29.2) |
| test_preset_manager.py | 42 | Preset save/load/delete (TASK 30.1) |
| test_preset_gui.py | 21 | GUI preset integration (TASK 30.2) |
| test_defaults.py | 45 | User defaults configuration (TASK 31.2) |
| test_paths.py | 18 | Path handling and storage (TASK 32.1) |
| test_edit_before_translate.py | 36 | Edit before translation feature (TASK 33.1) |
| test_prompts_config.py | 40 | Configurable Edit/TLC prompts (TASK 33.2) |
| test_html.py | 64 | HTML file format handling |
| test_languages.py | 87 | Language module consolidation (TASK 16.1) |
| test_api_providers.py | 60 | API providers consolidation (TASK 16.2) |
| test_line_by_line.py | 15 | Line-by-line translation |
| test_local_llm.py | 63 | Local LLM integration |
| test_logit_bias.py | 38 | Logit bias / token banning |
| test_manifest_v2.py | 51 | Core manifest |
| test_modehelper.py | 30 | Mode helper utilities (TASK 15.6) |
| test_model_encodings.py | 52 | Model encodings consolidation (TASK 16.3) |
| test_model_pricing.py | 52 | Model pricing consolidation (TASK 16.4) |
| test_model_registry.py | 140 | Model registry: fetch/save/load, structured_output filter, rate limit probing, derived concurrent, current selection, per-model settings, costs tab save settings, request mode, token breakdown, manifest estimation persistence, estimate button rename |
| test_model_selection.py | 23 | Model presets (TASK 8) |
| test_modi_all.py | 44 | Modi comprehensive (TASK 15.6) |
| test_modi_v2.py | 14 | Modi integration |
| test_options.py | 29 | Options dialog & API config |
| test_partial_translation.py | 18 | Partial translation mode (TASK 9) |
| test_postprocess.py | 79 | Post-process recovery suite |
| test_prompt_caching.py | 110 | Prompt caching (ordering, model detection, token tracking, filter logic, cached input column, reasoning/prediction logging, explicit vs. auto-generated cache key resolution, support helpers, static prompt size check, cost estimation with cached input) |
| test_project_config.py | 19 | Project configuration |
| test_quote_stripping.py | 33 | Quote stripping modes |
| test_rate_limiter.py | 70 | Rate limiting system |
| test_header_rate_limiter.py | 36 | Header-based rate limiter (duration parser, per-model counters, thread safety, monotonic timer, custom providers) |
| test_replication.py | 40 | Game updates |
| test_request_cache.py | 48 | Request caching system (modes, TTL, eviction) |
| test_retry_handler.py | 47 | Retry strategies (batch, contextual, isolated, skip) |
| test_rolling_context.py | 23 | Rolling context (TASK 7) |
| test_speaker_format.py | 45 | Speaker format preservation (TASK 10) |
| test_standard_mode.py | 37 | Standard mode processing |
| test_style_presets.py | 78 | Translation style presets |
| test_temporary_replacement.py | 2 | Temporary replacement |
| test_thinking_mode.py | 23 | Thinking mode (extended reasoning) |
| test_translation_style.py | 19 | Translation style guide (TASK 6) |
| test_unique_placeholders.py | 3 | Unique placeholders (integration) |
| test_validation.py | 81 | Pre/Post API validation |
| test_wordwrap.py | 74 | Word wrapping with speaker modes (TASK 15.5) |
| test_gui_dialogs.py | 26 | GlobalOptions dialog tests plus single-instance API Log / Global Options reuse coverage and API Log display-limit rendering helpers (TASK 18.7) |
| test_cli_estimation.py | 13 | CLI estimation verification (TASK 18.6) |
| test_manifest_automation.py | 12 | Manifest auto-creation (TASK 18.8) |
| test_glossary_integration.py | 12 | Analysis→Information integration (TASK 18.4) |
| test_gui_layout.py | 12 | 2-column layout tests (TASK 18.2) |
| test_subtask_tracking.py | 14 | Subtask progress tracking (TASK 18.3) |
| test_code_glossary_display.py | 27 | Code glossary widget + instance counts (TASK 18.5) |
| test_code_pattern_actions.py | 46 | Code pattern action overhaul: normalization, actions, sync, validation, prompts |
| test_information_step_phase41.py | 57 | Information step Phase 41 UI enhancements |
| test_preprocess_phase42.py | 80 | Preprocessing & Postprocessing Phase 42 |
| test_translation_phase43.py | 48 | Translation Tab Overhaul Phase 43 |
| test_validation_shared.py | 24 | Shared Validation Phase 44 |
| test_postprocess_phase45.py | 54 | Postprocessing Tab Overhaul Phase 45 + stage-bounded translated input + flagged-case/dedup/search regressions |
| test_wordwrap_phase46.py | 47 | Wordwrap Tab Overhaul Phase 46 + stage-bounded Latest input |
| test_output_phase47.py | 52 | Output + Pipeline Completeness + Import Phase 47 |
| test_pipeline_logging.py | 52 | Pipeline Logging System Phase 48 |
| test_request_formation.py | 50 | Request Formation 4-Step Process Phase 49 |
| test_request_preview.py | 50 | Preview Requests dialog: PreviewRequest dataclass with _format_input_lines and request_params, FILTER_PARTS, RequestPreviewDialog (Pure/Formatted/Plain views preserving {}, Jump/Search/Filter), `_build_preview_requests()` integration including prompt cache metadata visibility, skip-already-translated parity, Global Options re-sync on Preview, explicit-boolean lock guarding, CJK-aware non-source filtering, cached tab-entry coverage, and Translation-tab status summary |
| test_context_markers.py | 70 | Context Markers Full Implementation Phase 50 |
| test_speaker_dedup.py | 47 | Speaker Duplicate Removal Phase 51 |
| test_glossary_selective.py | 28 | Selective Glossary Per Chunk Phase 52 |
| test_ini_sections.py | 56 | INI section seeding: [style], [tone], [system_instructions].Default, [defaults] long-text keys, [session].last_manifest, confirmations; SystemInstruction preset-name storage and migration; _migrate_preset_values mis-assigned preset correction; dropdown INI freshness |
| test_manifest_metadata.py | 28 | Manifest metadata consolidation (Task 1) |
| test_source_root.py | 27 | source_root simplification (Task 2) |
| test_line_saving.py | 39 | Line field saving across all steps (Task 3) |
| test_knowledge_base.py | 56 | Knowledge Base widget, Active columns, collapsible design, prompt adapter (TASK 76) |
| test_estimation_skip.py | 41 | Estimation skip logic Phase 78 (Task 3), kept aligned with Translation/Preview shared skip classification |
| test_costs_step_phase40.py | 57 | Costs step Phase 40+78 improvements (rename, dual estimation, dual ticks, concurrent time, prepro lines, prompt overhead format, request preview tokens) |
| test_costs_api_rework.py | 35 | API Requests & Costs rework (cache calculation, mode buttons, instant recalculation, model lock, settings decoupling, button rename, translation request mode) |
| test_costs_additive_display.py | 30 | Additive cost display rework (ceil-to-cents, content-only input_cost, non-cached prompt tokens, label layout, additive total) |
| test_rolling_context_phase78.py | 10 | Rolling context file-boundary fix Phase 78 (Task 7) |
| test_rolling_context_merge.py | 37 | Rolling context between/after, Step 5 efficient merge, merged-request conditional prompt (Task 78) |
| test_slicing_phase78.py | 11 | Slicing efficient mode Phase 78 (Task 8) |
| test_char_filter_phase78.py | 32 | Blacklist/whitelist validation Phase 78 (Task 5): parse_filter_entries, check_filter_violations, exchange/retry/flag strategies |
| test_max_input_tokens.py | 34 | Max Input Tokens (Task 41): RequestSettings field, GlobalOptions integration, RequestFormationConfig plumbing, build_requests token splitting, costs estimation, edge cases, INI persistence |
| test_ini_persistence.py | 22 | INI persistence: atomic save (3), save_app_state delegation (3), INI wipe prevention (1), set_default routing (1), comprehensive load_from_ini (6), effective default precedence (3), case preservation (1), clear_user_defaults (1), concurrent safety (1), boolean handling (2) |
| test_prompt_overhead_fix.py | 29 | Per-Request Prompt Overhead (Task 42): FormationResult dataclass, _estimate_via_formation return type, _compute_per_request_prompt_overhead, selective filtering per chunk, _update_ui avg/request format, sum vs flat multiplication, edge cases |
| test_request_building_unification.py | 75 | Request Building Unification: is_placeholder_only (all placeholder types), PROT_PATTERN fix, build_line_infos placeholder handling, validate_line_pre (no detection_text), _count_formation_input_tokens, formation pipeline for both orig/prep, preview language skip, _apply_language_skip prioritized text with placeholder stripping, _get_skip_indices (no original_lines override), placeholder stripping regression guard |
| smoke_test/*.py | 5+ | Smoke tests |
| test_provider_handshake.py | 188 | Provider Handshake: ABC, registry, validation, OpenAI/Google/Mistral/Anthropic/Local providers, APIClient integration, options.py migration, UI constraints, structured output |
| test_provider_live_api.py | 11 | Live API tests: GPT-5-nano (no temp, reasoning) + GPT-4.1-nano (temp 0-2, no reasoning) |
| test_pricing_and_reasoning.py | 108 | Pricing + Reasoning: GPT 4.1 no flex/priority, GPT 5 all tiers, ThinkingConfig 5 modes (builtin/explicit/optional/mandatory/""), build_params Chat Completions format, reasoning_effort persistence (RequestSettings/APIConfig/TranslationOptions/INI), provider-based get_thinking_params, THINKING_MODELS, is_openai_reasoning_model |
| test_api_log.py | 52 | API Log: LogEntry serialization, APILogStore CRUD/filtering/subscription/persistence, singleton management, enum values, dataclass defaults, prompt-cache metadata preservation, status string compatibility (5), manifest save thread safety (2), structured log full-content guardrails (7) |
| test_patch_editor_view.py | 3 | Patch Editor manifest helpers: staged Patch-vs-Original resolution, parser-backed translated/edit history rows, and manifest-backed save history persistence |
| test_bugfix_batch_79.py | 33 | Bugfix Batch 79: API Log visibility (lift/non-modal), global glossary merge (4), ellipsis-only detection (14), ellipsis compression order (5), dedup/skip progress (3), cached/reasoning tokens (5) |
| test_unified_request_builder.py | 28 | Unified Request Builder: gather_prompt_data (importable, keys, None/unloaded mgr, sample_lines, metadata read, fallback field merging), build_request_prompt (importable, tuple return, language prompt, style/tone/summary/genre enabled/disabled, rolling context, chunk_lines), unified call sites (costs 3 methods, translate 2 methods, no direct build_full_system_prompt), API Log full prompt (no truncation, line-by-line system_prompt), identical prompt output (deterministic, same data same prompt) |
| test_glossary_term_link.py | 19 | Glossary ↔ Term Translation link: character round-trip (2), on_enter load order AST (3), on_leave dual-storage sync AST (2), import_analysis_speakers persistence AST (1), dual-storage simulation (4), CharacterInfo preservation (3), ProjectMetadata preservation (2), load guard (2) |
| test_code_pattern_recovery.py | 33 | Code Pattern Recovery: _detect_delimiters (8), recover_code_patterns (10, including nested `{...}` inside `{{...}}` filtering), validate_code_patterns_preserved (5, including double-curly overlap regression), validate_translation_comprehensive code_patterns check #7 (3), recover_line pipeline integration (3, including double-curly preserve recovery), idx 8 end-to-end bug scenario (2) |
| test_custom_placeholder_recovery.py | 2 | Batch custom-placeholder restoration: shifted named token restored on a different line; local per-line restore remains preferred before global fallback |
| test_request_slicing_fix.py | 50 | Request Slicing Fix: is_code_pattern_only (15: exact/multi/NUM wildcard/punctuation/placeholder/empty/no-patterns/mixed/translatable/partial/regex-chars/None/whitespace/multi-NUM/overlapping), CODE_ONLY SkipReason (2: enum value, member exists), validate_line_pre CODE_ONLY (8: skipped/whitespace/NUM/not-code-only/no-patterns/empty/prot-precedence/placeholder-precedence), Efficient Merge Parity (5: conservative stable, efficient fewer, boundaries, estimation-translation parity, default false), Merge Boundaries (2: sum equals lines, single no boundaries), Merged Request Instruction (3: multi-boundary, single-boundary, block count), Manifest Patterns (8: LightVN color/close/var/combined, RPG Maker var/with-text/multi, Wolf var), Config Propagation (4: true/false/efficient/conservative), Preserve Patterns Wiring (3: signature/default/None) |
| test_request_slicing_settings.py | 30 | Per-Model Settings Priority: TestEfficientAlwaysFewerRequests (7: chunk sizes 10-200, single file, multi file, high chunk, all same file, edge max lines, large dataset), TestMinLinesCalculation (2: conservative/efficient min_lines formula), TestStep5EfficientMerge (5: cross-file merge, no merge same file, preserves boundaries, skips when disabled, merge reduces count), TestConfigPropagation (2: efficient_merge true/false in config), TestCostsEstimationNoOverride (2: source has no go.request override, chunk_var read), TestTranslateLoadModelSettings (2: method exists, has get_model_settings call), TestPreviewUpdatesOptions (1: _translation_options assigned), TestBuildChunksPerModelSettings (4: get_model_settings call, rc_between/rc_after/chunk_max_tokens from model), TestPreviewRollingContextPerModel (1: rolling_context_before per-model), TestFormationPipelineRealWorld (3: 100/500/1000 lines), TestFormationStepsConsistency (1: conservative ≥ efficient) |
| **Total Script Tests** | **4594** | (+188 provider handshake, +11 live API, +108 pricing/reasoning, +44 API log, +33 bugfix batch 79, +28 unified builder, +19 glossary term link, +28 code pattern recovery, +14 manifest overwrite, +30 request slicing settings) |
| One_Click_Test.py | 7 stages | API integration |

### TASK 11: Integration Test - 200 Lines (Completed)

**Purpose:** End-to-end validation of the full translation pipeline with real API calls.

**Test Parameters:**
- Sample File: `temp/message (58).txt` (4947 lines total)
- Translation Scope: First 200 lines
- Languages: Japanese → English
- API: Gemini 2.0 Flash Lite

**Validation Criteria:**
| Criterion | Result |
|-----------|--------|
| Translation Success | ✅ 200/200 lines translated |
| BR Tags Preserved | ✅ 86/89 tags (96% retention) |
| Japanese Remaining | ✅ 0 lines with Japanese |
| Speaker Format | ✅ 144 lines with correct format |
| API Logging | ✅ 5 chunks logged with redacted keys |
| Unit Tests Pass | ✅ 566 tests passing |

**Code Changes for TASK 11:**
1. `functions/CLI.py`: Changed default partial translation from 100 to 200 lines
2. `functions/CLI.py`: Added API logging initialization with timestamped paths
3. `functions/api_client.py`: Added `enable_api_log` and `api_log_path` parameters
4. `functions/api_client.py`: Added `_log_api_call()` method for request/response logging
5. `functions/api_client.py`: Improved retry logic (5+ retries, 3^n backoff, jitter)
6. `functions/mainhelper.py`: Pass logging parameters to APIClient

**API Log Format:**
```
CHUNK #N - TIMESTAMP

[SYSTEM PROMPT]
----------------------------------------
# Translation Instructions
You are a professional translator...
----------------------------------------

[USER MESSAGE]
INPUT LINES:
  [  1] リオス: 「さあ、始めようか」
  [  2] エマ: 「準備はできています」

--- RESPONSE ---
OUTPUT TRANSLATIONS:
  [  1] Rios: "Now, shall we begin?"
  [  2] Ema: "I'm ready."

[USAGE]
  Prompt Tokens: 2259
  Completion Tokens: 459
  Total Tokens: 2718
```

Note: Log uses human-readable formatting with numbered lines and section headers.
Each input/output line is shown on its own row for easy debugging.
The formatting (dividers, headers) is LOG-ONLY and not part of the actual API request.

**Note:** 3 standalone integration tests are skipped during pytest collection
(test_unique_placeholders.py) - run these directly with Python.

---

### TASK 12: Prompt & API Optimization (Completed)

**Purpose:** Token cost reduction, improved prompt structure, and content safety.

**Implementation Summary:**
| Subtask | Description | Status |
|---------|-------------|--------|
| A | Glossary Injection Verification | ✅ Code verified |
| B | Translation Style Injection | ✅ Code verified |
| C | Modular Prompt Files | ✅ base_instructions.txt, output_examples.txt |
| D | Empty Section Skipping | ✅ _is_game_summary_empty() |
| E | Shortened Instructions | ✅ All 14 conditions shortened 60-70% |
| F | Log Header with Stats | ✅ write_log_header() |
| G | Log-Only Formatting Verified | ✅ Documented |
| H | Output Examples Section | ✅ Separate file |
| I | Section Ordering Updated | ✅ Summary before examples |
| J | Shorter __PROTECTED__ Placeholder | ✅ Already using __PROTECTED__ |
| K | Content Warning System | ✅ check_content_warning() |

**Tests Passing:**
- 605 pytest tests (all conditional prompt tests updated)
- 84 conditional_prompts.py tests specifically
- All instructions work with shorter text

**Files Modified:**
- functions/api_client.py: Log header, token tracking, content warning
- functions/prompt_builder.py: Section ordering, empty section skip, examples
- functions/conditional_prompts.py: 9 pattern-triggered prompts (reworked from 15)
- functions/mainhelper.py: Call write_log_header()
- Base instructions: embedded in _DEFAULT_PROMPT_TEMPLATE (Session 25: config/base_instructions.txt removed)
- Output examples: embedded in _DEFAULT_OUTPUT_EXAMPLES (Session 25: config/output_examples.txt removed)
- CherryAI.ini: Added content_warning_enabled setting

**Conditional Prompt Token Reduction:**
| Condition | Before | After | Reduction |
|-----------|--------|-------|-----------|
| PROT_TOKEN | 5 lines | 1 line | 80% |
| DEDUP_TOKEN | 3 lines | 1 line | 67% |
| TEMPREPL | 2 lines | 1 line | 50% |
| BRACKETS | 5 lines | 1 line | 80% |
| JP_BRACKETS | 4 lines | 1 line | 75% |
| COLOR_CODES | 3 lines | 1 line | 67% |
| VARIABLES | 3 lines | 1 line | 67% |
| MEDIA | 4 lines | 1 line | 75% |
| FORMATTING | 3 lines | 1 line | 67% |
| RUBY | 4 lines | 1 line | 75% |
| ELLIPSIS | 3 lines | 1 line | 67% |
| SPEAKER | 4 lines | 1 line | 75% |
| SPEAKER_FORMAT | 15 lines | 1 line | 93% |
| BR_TAGS | 3 lines | 1 line | 67% |

**API Log Improvements:**
- Cost displayed per 1M tokens (industry standard)
- FREE noted for Gemini free tier
- Structured output mode (JSON) displayed
- Skipped lines tracking (DEDUP, symbols, no source lang)
- Missing sections listed (Glossary, Rolling Context)
- Log footer with final statistics
- Removed duplicate examples from prompt.txt (loaded from output_examples.txt)

**New API Log Format:**
```
API Log - 2025-01-30 08:00:00
File: message.txt
================================================================================

[TRANSLATION STATISTICS]
  Total Lines: 200
  Total Chunks: 4
  Model: gemini-2.0-flash-lite
  Structured Output: JSON mode enabled
  Cost: $0.00/1M input, $0.00/1M output (FREE TIER)

[SKIPPED LINES]
  DEDUP markers: 0
  Symbols only: 5
  No source lang: 10

================================================================================
CHUNK #1 - 2025-11-30 08:00:49 | Tokens: 2259 in / 459 out | Running Total: 2718
================================================================================
...
================================================================================
TRANSLATION COMPLETE - 2025-01-30 08:01:23
================================================================================

[FINAL STATISTICS]
  Chunks Processed: 4/4
  Total Prompt Tokens: 9,000
  Total Completion Tokens: 1,800
  Total Tokens: 10,800
  Estimated Cost: FREE (Gemini free tier)
```

---

## Quick Reference

### Run All Script Tests
```bash
pytest dev/test_manifest_v2.py dev/test_modi_v2.py dev/test_functions_v2.py dev/test_replication.py dev/test_config.py dev/test_dedup.py dev/test_options.py dev/test_validation.py dev/test_conditional_prompts.py dev/test_api_error_classification.py dev/test_first_request_gate.py dev/test_request_sorting.py dev/test_concurrent_execution.py dev/test_context_type_prompts.py -v
```

### Run API Test (Full)
```bash
python CherryAI.py test
```

### Run API Test (No LLM)
```bash
python CherryAI.py test --skip-api
```

### Run Specific Test Class
```bash
pytest dev/test_manifest_v2.py::TestLineEntryCreation -v
```

### Run Tests Matching Pattern
```bash
pytest dev/ -k "roundtrip" -v
```

---

## New Test Files (2025)

### dev/test_config.py (23 tests)

Configuration management tests validating load, save, and merge operations.

#### TestLoadConfig (5 tests)

| Test | Purpose |
|------|---------|
| `test_load_missing_file_returns_empty` | Missing config returns {} |
| `test_load_valid_json` | Parses valid JSON correctly |
| `test_load_invalid_json_returns_empty` | Malformed JSON returns {} |
| `test_load_empty_file` | Empty file returns {} |
| `test_load_with_comments` | JSON with comments handled |

#### TestSaveConfig (4 tests)

| Test | Purpose |
|------|---------|
| `test_save_creates_file` | New config file created |
| `test_save_overwrites_existing` | Existing file updated |
| `test_save_preserves_unicode` | UTF-8 encoding works |
| `test_save_creates_directories` | Missing dirs created |

#### TestMergeWithDefaults (3 tests)

| Test | Purpose |
|------|---------|
| `test_merge_empty_uses_defaults` | Empty user config gets defaults |
| `test_merge_user_overrides_defaults` | User values take priority |
| `test_merge_nested_dicts` | Deep merge works correctly |

#### TestUIState (3 tests)

| Test | Purpose |
|------|---------|
| `test_ui_state_initialization` | UI state created properly |
| `test_ui_state_persistence` | State survives save/load |
| `test_ui_state_validation` | Invalid states rejected |

#### TestAPIConfig (3 tests)

| Test | Purpose |
|------|---------|
| `test_api_config_defaults` | API defaults are correct |
| `test_api_config_validation` | Invalid API configs rejected |
| `test_api_config_sensitive_data` | Keys not logged |

#### TestEnsureConfigInitialized (3 tests)

| Test | Purpose |
|------|---------|
| `test_creates_config_if_missing` | Missing config initialized |
| `test_preserves_existing_config` | Existing config not overwritten |
| `test_adds_missing_keys` | Missing keys added to existing |

#### TestResetConfig (2 tests)

| Test | Purpose |
|------|---------|
| `test_reset_restores_defaults` | Reset clears user customizations |
| `test_reset_preserves_api_key` | API key not lost on reset |

---

### dev/test_ini_manager.py (48 tests) - TASK 21.1

INI configuration manager tests validating path resolution, typed access, and manifest defaults.

#### TestINIPathResolution (4 tests)

| Test | Purpose |
|------|---------|
| `test_ini_path_relative_to_module` | INI path resolved relative to main module |
| `test_ini_path_is_absolute` | Path is always absolute |
| `test_ini_path_cached` | Path caching works correctly |
| `test_app_dir_returns_parent_of_ini` | App dir is INI parent |

#### TestManifestDirectory (3 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_dir_default_location` | Manifest dir at {app_dir}/manifests |
| `test_manifest_dir_is_absolute` | Path is absolute |
| `test_manifest_dir_created_if_not_exists` | Directory created when missing |

#### TestGetDefault (9 tests)

| Test | Purpose |
|------|---------|
| `test_get_default_with_fallback` | Returns fallback for missing keys |
| `test_get_default_existing_key` | Returns actual value for existing keys |
| `test_get_default_missing_section` | Returns fallback for missing sections |
| `test_get_default_type_conversion_int` | Converts to int type |
| `test_get_default_type_conversion_float` | Converts to float type |
| `test_get_default_type_conversion_bool_true` | Converts 'true' to True |
| `test_get_default_type_conversion_bool_yes` | Converts 'yes' to True |
| `test_get_default_type_conversion_bool_false` | Converts 'false' to False |

#### TestTypedGetters (6 tests)

| Test | Purpose |
|------|---------|
| `test_get_str` | Returns string value |
| `test_get_int` | Returns integer value |
| `test_get_float` | Returns float value |
| `test_get_bool` | Returns boolean value |
| `test_get_list_empty` | Returns empty list for missing |
| `test_get_list_fallback` | Returns fallback for missing |

#### TestSetDefault (6 tests)

| Test | Purpose |
|------|---------|
| `test_set_default_creates_section` | Creates section if missing |
| `test_set_default_string_value` | Saves string values |
| `test_set_default_bool_true` | Saves True as 'true' |
| `test_set_default_bool_false` | Saves False as 'false' |
| `test_set_default_int_value` | Saves integer values |
| `test_set_default_none_value` | Saves None as empty string |

#### TestSectionOperations (6 tests)

| Test | Purpose |
|------|---------|
| `test_get_section_existing` | Returns all key-value pairs |
| `test_get_section_missing` | Returns empty dict for missing |
| `test_has_section_true` | Returns True for existing sections |
| `test_has_section_false` | Returns False for missing sections |
| `test_has_option_true` | Returns True for existing options |
| `test_has_option_false` | Returns False for missing options |

#### TestManifestDefaults (7 tests)

| Test | Purpose |
|------|---------|
| `test_get_manifest_default_string` | Returns string manifest default |
| `test_get_manifest_default_bool` | Infers bool type from fallback |
| `test_get_manifest_default_int` | Infers int type from fallback |
| `test_get_manifest_default_float` | Infers float type from fallback |
| `test_get_all_manifest_defaults` | Returns typed dict of all defaults |
| `test_builtin_manifest_defaults` | Builtin defaults are complete |
| `test_get_all_manifest_defaults_missing_ini` | Returns builtins if INI missing |

#### TestCaching (2 tests)

| Test | Purpose |
|------|---------|
| `test_reload_ini_clears_cache` | Reload refreshes data from file |
| `test_clear_cache` | Cache clearing works |

#### TestErrorHandling (3 tests)

| Test | Purpose |
|------|---------|
| `test_get_default_invalid_int` | Returns fallback for invalid int |
| `test_get_default_invalid_float` | Returns fallback for invalid float |
| `test_missing_ini_file` | Graceful handling of missing INI |

#### TestIntegration (3 tests)

| Test | Purpose |
|------|---------|
| `test_real_ini_exists` | CherryAI.ini exists |
| `test_real_ini_has_manifest_defaults` | Has [manifest_defaults] section |
| `test_real_manifest_defaults_types` | Manifest defaults have correct types |

---

### dev/test_manifest_defaults.py (44 tests) - TASK 21.2

Manifest initialization and defaults tests validating v3.0 field population from INI.

#### TestCreateManifestPopulatesAllDefaults (11 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_has_version` | New manifest has correct v3.0 version |
| `test_manifest_has_project_info` | project_info has all required fields |
| `test_manifest_has_preprocessing_fields` | All preprocessing options present |
| `test_manifest_has_estimation_fields` | Estimation fields initialized |
| `test_manifest_has_validation_rules` | ValidationRules nested object complete |
| `test_manifest_has_qa_options` | QAOptions nested object complete |
| `test_manifest_has_request_options` | RequestOptions with all API settings |
| `test_manifest_has_postprocessing` | PostProcessing options complete |
| `test_manifest_has_wordwrap_settings` | WordwrapSettings complete |
| `test_manifest_has_output_format` | OutputFormat options complete |
| `test_manifest_has_glossary_config` | Glossary configuration present |

#### TestLoadedManifestHasAllFields (5 tests)

| Test | Purpose |
|------|---------|
| `test_v2_manifest_gets_preprocessing_fields` | V2.1 manifest upgraded with preprocessing |
| `test_v2_manifest_gets_validation_rules` | V2.1 manifest gets ValidationRules |
| `test_v2_manifest_gets_request_options` | V2.1 manifest gets RequestOptions |
| `test_partial_nested_object_gets_filled` | Partial nested objects completed |
| `test_existing_values_not_overwritten` | Custom values preserved on load |

#### TestDefaultValuesMatchINI (6 tests)

| Test | Purpose |
|------|---------|
| `test_deduplication_default_from_ini` | Deduplication matches INI setting |
| `test_temperature_default_from_ini` | Temperature matches INI setting |
| `test_lines_per_chunk_default_from_ini` | LinesPerChunk matches INI |
| `test_wordwrap_width_default_from_ini` | WordwrapWidth matches INI |
| `test_source_language_default_from_ini` | SourceLanguage from INI |
| `test_target_language_default_from_ini` | TargetLanguage from INI |

#### TestBuiltinDefaults (2 tests)

| Test | Purpose |
|------|---------|
| `test_get_builtin_defaults_returns_dict` | Builtin defaults available |
| `test_builtin_defaults_have_correct_types` | Builtin types are correct |

#### TestBackwardCompatibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_lines_array_preserved` | Lines data preserved on load |
| `test_step_state_preserved` | Step state preserved on load |
| `test_metadata_preserved` | Metadata fields preserved |
| `test_save_load_roundtrip` | Save/load preserves all data |

#### TestListFieldParsing (3 tests)

| Test | Purpose |
|------|---------|
| `test_code_spacing_rules_is_bool` | CodeSpacingRules is boolean |
| `test_custom_placeholders_is_list` | CustomPlaceholders parsed as list |
| `test_ignore_patterns_is_list` | IgnorePatterns parsed as list |

#### TestHelperMethods (5 tests)

| Test | Purpose |
|------|---------|
| `test_parse_list_default_empty_string` | Empty string becomes [] |
| `test_parse_list_default_single_item` | Single item becomes [item] |
| `test_parse_list_default_multiple_items` | Multiple items parsed |
| `test_parse_list_default_strips_whitespace` | Whitespace stripped |
| `test_get_manifest_defaults_returns_dict` | Returns defaults dict |

#### TestFieldCountVerification (6 tests)

| Test | Purpose |
|------|---------|
| `test_total_top_level_fields` | All v3.0 top-level fields present |
| `test_validation_rules_field_count` | ValidationRules has 6 fields |
| `test_request_options_field_count` | RequestOptions has 9 fields |
| `test_postprocessing_field_count` | PostProcessing has 9 fields |
| `test_wordwrap_settings_field_count` | WordwrapSettings has 9 fields |
| `test_output_format_field_count` | OutputFormat has 12 fields |

---

### dev/test_dependencies.py (17 tests) - NEW (TASK 15.1)

Dependency checking module tests validating hash computation, caching, and install logic.

#### TestComputeFileHash (4 tests)

| Test | Purpose |
|------|---------|
| `test_hash_consistency` | Same file produces same hash |
| `test_different_content_different_hash` | Different content = different hash |
| `test_nonexistent_file_returns_empty` | Missing file returns "" |
| `test_empty_file_has_hash` | Empty file produces valid hash |

#### TestLoadCachedHash (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_existing_hash` | Loads cached hash correctly |
| `test_load_nonexistent_returns_none` | Missing file returns None |
| `test_load_empty_file_returns_none` | Empty file returns None |
| `test_load_whitespace_only_returns_none` | Whitespace-only returns None |

#### TestSaveCachedHash (3 tests)

| Test | Purpose |
|------|---------|
| `test_save_hash` | Saves hash to file |
| `test_save_creates_parent_dirs` | Creates parent directories |
| `test_save_overwrites_existing` | Overwrites existing hash |

#### TestCheckAndInstallDependencies (3 tests)

| Test | Purpose |
|------|---------|
| `test_missing_requirements_file_returns_true` | Missing file doesn't block |
| `test_matching_hash_skips_install` | Matching hash skips pip install |
| `test_force_reinstall_ignores_hash` | Force flag ignores cache |

#### TestConstants (3 tests)

| Test | Purpose |
|------|---------|
| `test_default_requirements_filename` | Correct default filename |
| `test_default_version_file_starts_with_dot` | Version file is hidden |
| `test_default_version_file_has_hash_extension` | Correct extension |

---

### dev/test_dedup.py (34 tests)

Deduplication module tests validating placeholder tokens, normalization, roundtrips,
per-line tag storage, and top-N group limiting.

#### TestPlaceholderTokens (4 tests)

| Test | Purpose |
|------|---------|
| `test_placeholder_tokens_returns_set` | placeholder_tokens() returns set |
| `test_is_dedup_placeholder_exact_match` | Exact placeholder detection |
| `test_is_dedup_placeholder_rejects_non_placeholder` | Non-placeholders rejected |
| `test_is_dedup_placeholder_tolerant_format` | Format variations handled |

#### TestAggressiveNormalization (4 tests)

| Test | Purpose |
|------|---------|
| `test_normalize_removes_numbers` | Numbers stripped for matching |
| `test_normalize_strips_whitespace` | Whitespace normalized |
| `test_normalize_consistent_for_identical_text` | Same text = same result |
| `test_normalize_different_numbers_same_result` | Number-only differences match |

#### TestAggressiveMasking (3 tests)

| Test | Purpose |
|------|---------|
| `test_mask_line_replaces_numbers` | Numbers → tokens |
| `test_mask_line_preserves_non_numbers` | Text preserved |
| `test_mask_multiple_numbers` | Multiple numbers handled |

#### TestAggressiveRestore (3 tests)

| Test | Purpose |
|------|---------|
| `test_restore_line_replaces_tokens` | Tokens → numbers |
| `test_restore_multiple_numbers_in_order` | Order preserved |
| `test_restore_empty_numbers_list` | Empty list handled |

#### TestDeduplicatePre (4 tests)

| Test | Purpose |
|------|---------|
| `test_collapse_duplicate_lines` | Duplicates collapsed |
| `test_collapse_multiple_duplicates` | Multiple duplicates work |
| `test_collapse_records_mapping` | source_idx populated |
| `test_collapse_preserves_empty_lines` | Empty lines handled |

#### TestDeduplicatePost (2 tests)

| Test | Purpose |
|------|---------|
| `test_restore_from_source_idx` | Restoration from source_idx |
| `test_restore_from_recorded_text` | Fallback restoration |

#### TestDedupRoundtrip (1 test)

| Test | Purpose |
|------|---------|
| `test_simple_roundtrip` | Pre→Post roundtrip preserves data |

#### TestGetDedupEntries (3 tests)

| Test | Purpose |
|------|---------|
| `test_empty_manifest_returns_empty` | No dedup = empty dict |
| `test_parses_per_doc_entries` | Per-document entries parsed |
| `test_parses_legacy_int_entries` | Legacy format supported |

#### TestMigrateLegacyDedup (2 tests)

| Test | Purpose |
|------|---------|
| `test_migrate_int_entries_to_dict` | int → dict migration |
| `test_migrate_already_dict_no_change` | Already-migrated unchanged |

#### TestDedupTagging (6 tests)

| Test | Purpose |
|------|---------|
| `test_tags_set_on_duplicate_lines` | Duplicate lines get dedup,D{idx} tags |
| `test_no_tags_on_unique_lines` | Unique lines get no dedup tags |
| `test_tag_based_roundtrip` | Pre→Post via tags roundtrip |
| `test_multiple_groups_tagged` | Multiple dedup groups each get own D{idx} |
| `test_read_dedup_tags_helper` | _read_dedup_tags parses correctly |
| `test_legacy_post_still_works` | Legacy dict-based post still restores |

#### TestTopNGroupLimit (2 tests)

| Test | Purpose |
|------|---------|
| `test_top_10_limit` | Only top MAX_DEDUP_GROUPS groups kept |
| `test_all_groups_when_under_limit` | All groups kept when under limit |

---

### dev/test_dedup_pipeline.py (37 tests)

GUI dedup pipeline tests validating apply_dedup_batch, apply_aggressive_dedup_batch, preprocessing integration, postprocessing _best_text resolution, and dedup restoration end-to-end.

#### TestApplyDedupBatch (6 tests)

| Test | Purpose |
|------|---------|  
| `test_no_duplicates` | No duplicates returns unchanged |
| `test_simple_duplicates` | Duplicates replaced with __DEDUP__ |
| `test_empty_lines_ignored` | Empty lines not treated as duplicates |
| `test_threshold_zero_disables` | Threshold 0 disables dedup |
| `test_many_duplicates` | Multiple groups handled |
| `test_returns_copy` | Input list not mutated |

#### TestApplyAggressiveDedupBatch (4 tests)

| Test | Purpose |
|------|---------|  
| `test_no_number_variations` | No variations returns unchanged |
| `test_number_normalised_dedup` | Number variants collapsed |
| `test_skips_dedup_placeholder` | __DEDUP__ lines skipped |
| `test_empty_lines_skipped` | Empty lines not matched |

#### TestAggressiveHelpers (3 tests)

| Test | Purpose |
|------|---------|  
| `test_normalize_replaces_digits` | Digits replaced for matching |
| `test_mask_captures_numbers` | Numbers captured during masking |
| `test_restore_puts_numbers_back` | Numbers restored from list |

Indexed aggressive placeholder regressions now also verify that multi-number lines emit `<NUM1>`, `<NUM2>`, ... instead of repeated generic `<NUM>` tokens and that reordered translations restore by explicit slot rather than left-to-right position.

#### TestApplyPreprocessingDedup (10 tests)

| Test | Purpose |
|------|---------|  
| `test_dedup_applied_first` | Dedup runs at P10 |
| `test_dedup_tags_generated` | D{idx} tags created |
| `test_aggressive_dedup_applied_last` | Aggressive dedup runs at P90 |
| `test_aggressive_tags_generated` | AD{idx} tags created |
| `test_aggr_numbers_stored` | aggr_numbers dict populated |
| `test_dedup_disabled` | Config off skips dedup |
| `test_combined_standard_and_aggressive` | Both dedup types in one pass |
| `test_progress_callback` | progress_cb called with float values |
| `test_dedup_map_string_keys_for_json` | Map keys are strings for JSON |
| `test_standard_dedup_can_resolve_aggressive_source_chain` | Standard dedup rows resolve through aggressive dedup sources during postprocess restoration |

#### TestBestText (7 tests)

| Test | Purpose |
|------|---------|  
| `test_prefers_postprocessed` | Postprocessed text preferred |
| `test_falls_back_to_translated` | Falls back to translated |
| `test_skips_dedup_sentinel` | __DEDUP__ sentinel skipped |
| `test_all_empty_returns_empty` | All empty returns empty string |
| `test_falls_back_to_preprocessed` | Falls back to preprocessed when tl empty |
| `test_preprocessed_skips_dedup_sentinel` | __DEDUP__ in preprocessed skipped |
| `test_priority_order_postpro_tl_prepro_orig` | Full priority chain verified |

#### TestDedupRestoration (4 tests)

| Test | Purpose |
|------|---------|  
| `test_standard_dedup_restored_from_postprocessed` | Source postpro copied to dup |
| `test_standard_dedup_falls_back_to_translated` | Falls back to tl when no postpro |
| `test_standard_dedup_falls_back_to_preprocessed` | Falls back to prepro when no tl |
| `test_aggressive_dedup_with_number_restoration` | Numbers restored from aggr_numbers |

Focused regression additions:
- `dev/test_dedup.py::TestAggressiveMasking::test_mask_multiple_numbers`
- `dev/test_dedup.py::TestAggressiveRestore::test_restore_indexed_numbers_by_explicit_slot`
- `dev/test_postprocess_phase45.py::TestAggressiveDedupIndexedRestore::test_reverse_aggr_numbers_restores_reordered_indexed_tokens`

Verified command:

```bash
python -m pytest CherryAI/dev/test_dedup.py -q --timeout=10 -k "aggressive or dedup"
python -m pytest CherryAI/dev/test_postprocess_phase45.py -q --timeout=10 -k "AggressiveDedupIndexedRestore"
```

---

### dev/test_recovery_anchor.py (79 tests)

Comprehensive tests for anchor-relative bracket and quote recovery. Validates ANCHOR_EQUIVS equivalence-aware comparison, balanced-original gating for bracket recovery, anchor-relative insertion (line start/end, punctuation anchors), NEEDS_RETRY flagging when no anchor found, helper functions, integration with recover_line(), lenticular `【】` versus square `[]` equivalence, extra unmatched-bracket removal, and the intentional triple-`}` exception.

#### TestBracketEquivalence (9 tests)

| Test | Purpose |
|------|---------|
| `test_fullwidth_parens_to_halfwidth` | （）→() no spurious insertion |
| `test_fullwidth_square_to_halfwidth` | ［］→[] no spurious insertion |
| `test_fullwidth_curly_to_halfwidth` | ｛｝→{} no spurious insertion |
| `test_fullwidth_angle_to_halfwidth` | ＜＞→<> no spurious insertion |
| `test_japanese_corner_brackets_unchanged` | 「」 survives translation |
| `test_multiple_fullwidth_pairs` | Multiple （）→() pairs balanced |
| `test_mixed_bracket_types_all_equivalent` | Different types all converted |
| `test_halfwidth_to_halfwidth_same` | Identical brackets unchanged |
| `test_corner_brackets_as_quote_equivalents` | 「」 treated as own type |

#### TestBracketAnchorInsertion (7 tests)

| Test | Purpose |
|------|---------|
| `test_missing_opening_bracket_at_line_start` | ( at line start → insert at start |
| `test_missing_closing_bracket_at_line_end` | ) at line end → insert at end |
| `test_missing_opening_square_bracket_start` | [ at start → insert at start |
| `test_missing_closing_square_bracket_end` | ] at end → insert at end |
| `test_missing_bracket_with_punctuation_anchor` | Anchor-relative via 。→. equiv |
| `test_both_brackets_missing_with_anchors` | Both brackets recovered |
| `test_insert_uses_canonical_halfwidth` | Canonical halfwidth used |

#### TestBracketNeedsRetry (2 tests)

| Test | Purpose |
|------|---------|
| `test_missing_bracket_in_middle_no_anchor` | No punctuation → graceful handling |
| `test_no_absolute_position_algorithm` | Regression: no rel_pos formula |

#### TestBracketRecoveryGate (6 tests)

| Test | Purpose |
|------|---------|
| `test_unbalanced_original_skips_recovery` | Unbalanced source lines do not trigger repair |
| `test_unbalanced_original_skips_retry_flagging` | Unbalanced source also suppresses retry flagging |
| `test_balanced_latest_with_different_brackets_is_ignored` | Balanced output is ignored despite bracket-style drift |
| `test_lenticular_brackets_match_square_brackets_and_extra_brace_is_removed` | `【】` and `[]` are equivalent while stray `}` is removed |
| `test_recover_line_keeps_lenticular_equivalence_without_reinserting_fullwidth` | recover_line keeps `[]` and removes only the extra brace |
| `test_intentionally_unbalanced_triple_closing_brace_is_kept` | Rare source-side triple `}` lines are left unchanged |

#### TestQuoteEquivalence (6 tests)

| Test | Purpose |
|------|---------|
| `test_fullwidth_double_quote_to_halfwidth` | ＂→" no spurious insertion |
| `test_curly_double_quotes_to_straight` | ""→"" no spurious insertion |
| `test_jp_corner_brackets_to_en_quotes` | 「」→"" via ANCHOR_EQUIVS equiv |
| `test_mixed_quote_styles_balanced` | Curly vs straight balanced |
| `test_identical_quotes_no_change` | Same quotes unchanged |
| `test_single_quotes_equivalent` | ''→'' no crash |

#### TestQuoteAnchorInsertion (4 tests)

| Test | Purpose |
|------|---------|
| `test_missing_closing_quote_at_line_end` | Closing " appended at end |
| `test_missing_opening_quote_at_line_start` | Same-char balanced after insert |
| `test_closing_curly_quote_recovered` | Missing \u201d recovered |
| `test_missing_quote_fullwidth_original` | ＂→" recovered at end |

#### TestQuoteNeedsRetry (2 tests)

| Test | Purpose |
|------|---------|
| `test_interior_opening_quote_no_anchor` | Interior quote handled gracefully |
| `test_no_absolute_position_for_quotes` | Regression: no rel_pos formula |

#### TestFindAnchorNear (10 tests)

| Test | Purpose |
|------|---------|
| `test_find_punctuation_left` | Finds . to the left |
| `test_find_punctuation_right` | Finds . to the right |
| `test_no_anchor_left` | No punctuation → None |
| `test_no_anchor_right` | No punctuation → None |
| `test_skip_chars_parameter` | Skip chars respected |
| `test_anchor_at_boundary` | Anchor at text end found |
| `test_skip_whitespace_to_anchor` | Spaces skipped to find anchor |
| `test_left_from_start` | Pos 0 left → None |
| `test_right_from_end` | Last pos right → None |
| `test_japanese_punctuation_found` | 。 found as anchor |

#### TestTryAnchorBracketInsert (6 tests)

| Test | Purpose |
|------|---------|
| `test_opening_at_line_start` | Opening at orig start → result start |
| `test_closing_at_line_end` | Closing at orig end → result end |
| `test_anchor_based_insertion` | Punctuation anchor-relative insert |
| `test_no_anchor_returns_none` | No anchor → None |
| `test_opening_at_near_start` | Whitespace before → line start |
| `test_closing_at_near_end` | Whitespace after → line end |

#### TestNormalizeBracket (4 tests)

| Test | Purpose |
|------|---------|
| `test_fullwidth_to_halfwidth` | （→(, ）→), etc. |
| `test_halfwidth_passthrough` | (→(, )→) unchanged |
| `test_non_bracket_passthrough` | a→a unchanged |
| `test_jp_corner_bracket_canonical` | 「→", 」→" |

#### TestRecoverLineIntegration (6 tests)

| Test | Purpose |
|------|---------|
| `test_fullwidth_brackets_no_spurious_insertion` | recover_line: （）→() clean |
| `test_fullwidth_quotes_no_spurious_insertion` | recover_line: ＂→" clean |
| `test_missing_bracket_recovered_via_anchor` | recover_line: ( inserted |
| `test_missing_quote_recovered_at_end` | recover_line: " at end |
| `test_jp_to_en_complete_conversion` | 「」（）→""() no corruption |
| `test_no_issues_when_balanced` | Balanced text has zero issues |

#### TestModuleConstants (5 tests)

| Test | Purpose |
|------|---------|
| `test_canon_map_has_all_equivs` | _CANON_MAP covers ANCHOR_EQUIVS |
| `test_closing_to_opening_complete` | _CLOSING_TO_OPENING complete |
| `test_recovery_anchor_chars_include_punctuation` | Punctuation in set |
| `test_bracket_equiv_subset_of_canon_map` | BRACKET_EQUIV ⊂ _CANON_MAP |
| `test_quote_equiv_subset_of_canon_map` | QUOTE_EQUIV ⊂ _CANON_MAP |

#### TestEdgeCases (12 tests)

| Test | Purpose |
|------|---------|
| `test_empty_texts` | Empty orig+trans no crash |
| `test_empty_translated` | Empty trans with bracket orig |
| `test_empty_original` | Empty orig with bracket trans |
| `test_only_brackets` | Text is only brackets |
| `test_nested_brackets_balanced` | Nested (()) balanced |
| `test_multiple_bracket_types_mixed` | Multiple types in one line |
| `test_empty_texts_quote_recovery` | Empty texts for quotes |
| `test_quote_inside_brackets` | Quotes inside brackets |
| `test_very_long_line` | 1000+ char line no crash |
| `test_unicode_content_between_brackets` | Unicode content in brackets |
| `test_single_bracket_in_original` | Unmatched bracket graceful |
| `test_extra_brackets_in_translated` | Extra brackets not removed |

---

### dev/test_prompt_builder_shared.py (20 tests)

Shared prompt builder tests validating §5.2 slot assembly, POV integration, glossary filtering, and that Costs and Translation both use the shared builder.

#### TestBuildFullSystemPrompt (17 tests)

| Test | Purpose |
|------|---------|  
| `test_all_sections_present` | All §5.2 sections in output |
| `test_injection_order` | Sections appear in correct order |
| `test_pov_high_confidence_included` | POV included when high confidence |
| `test_pov_low_confidence_excluded` | POV excluded when low confidence |
| `test_pov_none_excluded` | POV excluded when None |
| `test_empty_metadata` | Empty dict handled gracefully |
| `test_none_metadata` | None metadata handled gracefully |
| `test_glossary_active_filter` | Only active entries included |
| `test_glossary_with_notes` | Notes column appended |
| `test_characters_section` | Characters section formatted |
| `test_rolling_context_appended` | Rolling context at end |
| `test_breakdown_counts_words` | Token breakdown has word counts |
| `test_language_section_format` | Language direction formatted |
| `test_partial_language_excluded` | Missing language skips section |
| `test_pov_1st_person` | 1st person mapped correctly |
| `test_pov_3rd_person` | 3rd person mapped correctly |

#### TestCostsPromptOverhead (2 tests)

| Test | Purpose |
|------|---------|  
| `test_costs_imports_shared_builder` | Costs module imports builder |
| `test_shared_builder_returns_nonzero_tokens` | Builder returns >0 tokens |

#### TestTranslateUsesSharedBuilder (2 tests)

| Test | Purpose |
|------|---------|  
| `test_translate_imports_shared_builder` | Translate module imports builder |
| `test_prompt_includes_pov_when_set` | POV present in translate prompt |

---

### dev/test_prompt_toggles.py (28 tests)

Section toggle tests validating that `*_enabled` metadata flags correctly gate
which prompt sections are included or excluded by `build_full_system_prompt()`.

#### TestGenreToggle (2 tests)

| Test | Purpose |
|------|---------|
| `test_genre_included_when_enabled` | Genre section present when `genre_enabled=True` |
| `test_genre_excluded_when_disabled` | Genre section absent when `genre_enabled=False` |

#### TestSummaryToggle (2 tests)

| Test | Purpose |
|------|---------|
| `test_summary_included_when_enabled` | Summary section present when `summary_enabled=True` |
| `test_summary_excluded_when_disabled` | Summary section absent when `summary_enabled=False` |

#### TestStyleToggle (2 tests)

| Test | Purpose |
|------|---------|
| `test_style_included_when_enabled` | Style section present when `style_enabled=True` |
| `test_style_excluded_when_disabled` | Style section absent when `style_enabled=False` |

#### TestToneToggle (2 tests)

| Test | Purpose |
|------|---------|
| `test_tone_included_when_enabled` | Tone section present when `tone_enabled=True` |
| `test_tone_excluded_when_disabled` | Tone section absent when `tone_enabled=False` |

#### TestSystemInstructionsToggle (2 tests)

| Test | Purpose |
|------|---------|
| `test_si_included_when_enabled` | System Instructions present when `system_instructions_enabled=True` |
| `test_si_excluded_when_disabled` | System Instructions absent when `system_instructions_enabled=False` |

#### TestGlossaryToggle (2 tests)

| Test | Purpose |
|------|---------|
| `test_glossary_included_when_enabled` | Glossary + Characters present when `glossary_enabled=True` |
| `test_glossary_excluded_when_disabled` | Glossary + Characters absent when `glossary_enabled=False` |

#### TestDefaultToggleValues (6 tests)

| Test | Purpose |
|------|---------|
| `test_missing_genre_defaults_to_disabled` | Missing key defaults to disabled (backward compat) |
| `test_missing_summary_defaults_to_disabled` | Missing key defaults to disabled |
| `test_missing_style_defaults_to_disabled` | Missing key defaults to disabled |
| `test_missing_tone_defaults_to_disabled` | Missing key defaults to disabled |
| `test_missing_si_defaults_to_enabled` | Missing key defaults to enabled |
| `test_missing_glossary_defaults_to_enabled` | Missing key defaults to enabled |

#### TestCombinedToggles (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_disabled_produces_minimal_prompt` | Only Language section with all toggles off |
| `test_all_enabled_includes_everything` | All sections present with all toggles on |
| `test_token_count_changes_with_toggles` | Word count decreases when sections disabled |
| `test_idempotent_across_calls` | Same inputs produce identical outputs |

#### TestEdgeCases (6 tests)

| Test | Purpose |
|------|---------|
| `test_empty_metadata` | Empty dict returns empty prompt |
| `test_none_metadata` | None metadata returns empty prompt |
| `test_style_falls_back_to_custom_style` | Falls back to `custom_style` when `style` empty |
| `test_tone_falls_back_to_custom_tone` | Falls back to `custom_tone` when `tone` empty |
| `test_enabled_but_empty_field_produces_no_section` | Toggle on + empty text = no section |
| `test_chunk_filtering_with_glossary_toggle` | Per-chunk filtering respects glossary toggle |

---

### dev/test_section_toggles.py (76 tests)

End-to-end section toggle tests validating toggle persistence across tab changes,
preview request gating, estimation integration, Save button removal, disabled
textbox visual styling, button alignment, and table sorting behaviour.

#### TestPromptToggleGating (15 tests)

| Test | Purpose |
|------|---------|
| `test_genre_enabled_includes_section` | Genre section present when `genre_enabled=True` |
| `test_genre_disabled_excludes_section` | Genre section absent when `genre_enabled=False` |
| `test_summary_enabled_includes_section` | Summary section present when enabled |
| `test_summary_disabled_excludes_section` | Summary section absent when disabled |
| `test_style_enabled_includes_section` | Style section present when enabled |
| `test_style_disabled_excludes_section` | Style section absent when disabled |
| `test_tone_enabled_includes_section` | Tone section present when enabled |
| `test_tone_disabled_excludes_section` | Tone section absent when disabled |
| `test_si_enabled_includes_section` | System Instructions present when enabled |
| `test_si_disabled_excludes_section` | System Instructions absent when disabled |
| `test_glossary_enabled_includes_section` | Glossary section present when enabled |
| `test_glossary_disabled_excludes_section` | Glossary section absent when disabled |
| `test_all_disabled_minimal_prompt` | Only Language section when all toggles off |
| `test_all_enabled_full_prompt` | All sections present when all toggles on |
| `test_missing_flags_use_defaults` | Missing keys use backward-compatible defaults |

#### TestProjectMetadataBoundary (1 test)

| Test | Purpose |
|------|---------|
| `test_to_dict_excludes_enabled_flags` | `ProjectMetadata.to_dict()` does NOT include `*_enabled` flags |

#### TestOnLeaveTogglePreservation (2 tests)

| Test | Purpose |
|------|---------|
| `test_on_leave_preserves_toggle_states` | `on_leave()` merges BooleanVar values into metadata dict |
| `test_on_leave_toggles_survive_to_dict` | Toggle flags survive `ProjectMetadata.to_dict()` replacement |

#### TestPromptTokenCount (2 tests)

| Test | Purpose |
|------|---------|
| `test_tokens_decrease_when_sections_disabled` | Word count drops when sections disabled |
| `test_tokens_stable_across_repeated_calls` | Identical inputs produce same word count |

#### TestManifestMetadataField (5 tests)

| Test | Purpose |
|------|---------|
| `test_set_and_get_metadata_field` | Round-trip via `set_info_metadata_field`/`get_info_metadata_field` |
| `test_get_missing_field_returns_default` | Missing key returns provided default |
| `test_overwrite_existing_field` | Second set overwrites first |
| `test_get_info_metadata_returns_reference` | `get_info_metadata()` returns dict reference |
| `test_set_field_creates_metadata_if_missing` | `set_info_metadata_field()` creates metadata dict if absent |

#### TestSaveButtonRemoved (1 test)

| Test | Purpose |
|------|---------|
| `test_no_save_button_in_header` | Save button source code removed from `_build_header()` |

#### TestPreviewSectionGating (6 tests)

| Test | Purpose |
|------|---------|
| `test_preview_si_disabled_excluded` | Disabled sys_instructions excluded from preview |
| `test_preview_style_disabled_excluded` | Disabled style excluded from preview |
| `test_preview_tone_disabled_excluded` | Disabled tone excluded from preview |
| `test_preview_summary_disabled_excluded` | Disabled summary excluded from preview |
| `test_preview_genre_disabled_excluded` | Disabled genre excluded from preview |
| `test_preview_glossary_disabled_excluded` | Disabled glossary/characters excluded from preview |

#### TestTabChangeSaveLoad (3 tests)

| Test | Purpose |
|------|---------|
| `test_toggle_flag_roundtrip_via_manifest` | Flags survive set → get roundtrip |
| `test_enabled_flags_in_step_data` | Flags present in `get_step_data()` metadata |
| `test_load_toggles_reads_from_manifest` | `_load_section_toggles()` reads stored flags |

#### TestDisabledTextboxGreyOut (11 tests)

| Test | Purpose |
|------|---------|
| `test_apply_widget_enabled_state_method_exists` | Static method exists on InformationStep |
| `test_apply_widget_enabled_state_is_static` | Method is a staticmethod |
| `test_toggle_section_calls_apply_widget_enabled_state` | `_toggle_section_enabled` delegates to helper |
| `test_load_section_toggles_calls_apply_widget_enabled_state` | `_load_section_toggles` delegates to helper |
| `test_apply_widget_sets_text_bg_fg_disabled` | Disabled tk.Text widgets get THEME.bg_disabled / text_disabled |
| `test_apply_widget_restores_text_bg_fg_enabled` | Enabled tk.Text widgets get white / black |
| `test_apply_widget_non_text_widget_no_bg_change` | Non-Text widgets skip bg/fg changes |
| `test_summary_toggle_widgets_include_summary_text` | Summary section includes ScrolledText in toggle widget list |
| `test_style_toggle_widgets_include_style_text` | Style section includes ScrolledText in toggle widget list |
| `test_tone_toggle_widgets_include_tone_text` | Tone section includes ScrolledText in toggle widget list |
| `test_si_toggle_widgets_include_notes_text` | SI section includes ScrolledText in toggle widget list |

#### TestButtonAlignment (11 tests)

| Test | Purpose |
|------|---------|
| `test_style_save_button_right_aligned` | Style Save button uses `side="right"` |
| `test_style_delete_button_right_aligned` | Style Delete button uses `side="right"` |
| `test_style_toggle_button_right_aligned` | Style Toggle button uses `side="right"` |
| `test_tone_save_button_right_aligned` | Tone Save button uses `side="right"` |
| `test_tone_delete_button_right_aligned` | Tone Delete button uses `side="right"` |
| `test_tone_toggle_button_right_aligned` | Tone Toggle button uses `side="right"` |
| `test_si_save_button_right_aligned` | SI Save button uses `side="right"` |
| `test_si_delete_button_right_aligned` | SI Delete button uses `side="right"` |
| `test_si_toggle_button_right_aligned` | SI Toggle button uses `side="right"` |
| `test_summary_toggle_right_aligned` | Summary toggle uses `side="right"` (reference) |
| `test_no_left_pack_for_style_buttons` | Style section has no `side="left"` for buttons |

#### TestTableSorting (19 tests)

| Test | Purpose |
|------|---------|
| `test_char_refresh_sorts_by_count_desc` | Default character sort: count descending |
| `test_char_refresh_adds_tags` | Each character row gets `char_{idx}` tag |
| `test_get_char_idx_extracts_tag` | `_get_char_idx` parses tag correctly |
| `test_get_char_idx_returns_negative_for_missing_tag` | Missing tag returns -1 |
| `test_char_heading_click_first_sets_ascending` | First click sets ascending |
| `test_char_heading_click_second_sets_descending` | Second click switches to descending |
| `test_char_heading_click_third_resets_to_count` | Third click resets to count sort |
| `test_char_heading_click_different_col_resets` | New column resets to ascending |
| `test_char_heading_arrows_show_on_sorted_col` | Active column shows ▲ |
| `test_char_heading_arrows_descending` | Descending shows ▼ |
| `test_char_heading_arrows_cleared_on_reset` | Reset removes all arrows |
| `test_code_heading_click_cycle` | Code tree heading click cycles correctly |
| `test_code_refresh_default_sorts_by_count_desc` | Default code sort: instances first, count desc |
| `test_char_save_manifest_sorted_by_count` | Characters saved in count-desc order |
| `test_code_save_manifest_sorted_by_count` | Code patterns saved in count-desc order |
| `test_char_headings_have_command` | Character headings have click commands |
| `test_code_headings_have_command` | Code headings have click commands |
| `test_char_column_sort_ascending` | A-Z sort for character names |
| `test_char_column_sort_descending` | Z-A sort for character names |

```bash
# Run section toggle tests
python -m pytest CherryAI/dev/test_section_toggles.py -v --timeout=10
```

---

| `test_provider_has_required_keys` | name, base_url, models present |
| `test_openai_has_empty_base_url` | OpenAI uses SDK default |
| `test_gemini_has_openai_compat_url` | Gemini uses compat endpoint |
| `test_each_provider_has_models` | Every provider has ≥1 model |

#### TestSupportedLanguages (3 tests)

| Test | Purpose |
|------|---------|
| `test_japanese_english_present` | Primary languages exist |
| `test_minimum_language_count` | ≥10 languages supported |
| `test_no_duplicates` | No duplicate entries |

#### TestDefaultConfig (6 tests)

| Test | Purpose |
|------|---------|
| `test_api_section_exists` | API section in defaults |
| `test_api_has_required_keys` | All 11 API keys present |
| `test_default_provider_is_openai` | Default = openai |
| `test_default_temperature_in_range` | 0.0 ≤ temp ≤ 2.0 |
| `test_default_timeout_reasonable` | 10 ≤ timeout ≤ 600 |
| `test_default_chunk_size_reasonable` | 10 ≤ chunk ≤ 200 |

#### TestConfigPersistence (2 tests)

| Test | Purpose |
|------|---------|
| `test_save_and_load_api_config` | Full roundtrip works |
| `test_load_merges_with_defaults` | Missing keys filled |

#### TestAPISettingsSummary (3 tests)

| Test | Purpose |
|------|---------|
| `test_summary_format` | Format: provider/model (Key: status) |
| `test_summary_shows_key_not_set` | Shows "NOT SET" when empty |
| `test_summary_shows_key_configured` | Shows "configured" when set |

#### TestValidationLogic (5 tests)

| Test | Purpose |
|------|---------|
| `test_temperature_validation` | Range: 0.0 - 2.0 |
| `test_timeout_validation` | Range: 10 - 600 |
| `test_chunk_size_validation` | Range: 10 - 200 |
| `test_retries_validation` | Range: 0 - 10 |
| `test_rate_limit_validation` | Range: 1 - 1000 |

#### TestProviderModelMapping (3 tests)

| Test | Purpose |
|------|---------|
| `test_openai_models` | OpenAI has gpt-4o variants |
| `test_gemini_models` | Gemini has gemini-* models |
| `test_local_has_custom_model` | Local has "custom" model |

#### TestConfigIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_full_config_roundtrip` | All values preserved |
| `test_partial_update_preserves_other_keys` | Partial save doesn't clobber |

---

### dev/test_validation.py (56 tests)

API validation tests for pre-translation filtering, post-translation validation,
and symbol normalization.

#### TestHasJapanese (6 tests)

| Test | Purpose |
|------|---------|
| `test_hiragana` | Detect hiragana characters |
| `test_katakana` | Detect katakana characters |
| `test_kanji` | Detect kanji characters |
| `test_mixed` | Detect Japanese in mixed content |
| `test_no_japanese` | Reject non-Japanese text |
| `test_fullwidth_ascii` | Fullwidth ASCII is not Japanese |

#### TestCountJapanese (3 tests)

| Test | Purpose |
|------|---------|
| `test_count_hiragana` | Count hiragana chars correctly |
| `test_count_mixed` | Count in mixed content |
| `test_count_none` | Return 0 for non-Japanese |

#### TestIsSymbolOnly (7 tests)

| Test | Purpose |
|------|---------|
| `test_punctuation_only` | Pure punctuation is symbol-only |
| `test_fullwidth_punctuation` | Fullwidth punct is symbol-only |
| `test_mixed_symbols` | Mixed symbols with whitespace |
| `test_with_japanese` | Not symbol-only with Japanese |
| `test_with_alpha` | Not symbol-only with alphabetic |
| `test_empty` | Empty is not symbol-only |
| `test_numbers_only` | Numbers are symbol-only |

#### TestNormalizeSymbols (7 tests)

| Test | Purpose |
|------|---------|
| `test_ellipsis` | …→... normalization |
| `test_fullwidth_punctuation` | 。→., 、→, etc. |
| `test_fullwidth_brackets` | （）→(), ［］→[] |
| `test_japanese_quotes` | 「」→"" normalization |
| `test_fullwidth_space` | 　→ space |
| `test_mixed_content` | Mixed content normalizes |
| `test_preserve_normal` | Already-normal unchanged |

#### TestValidateLinePre (13 tests)

| Test | Purpose |
|------|---------|
| `test_empty_line` | Skip empty lines |
| `test_comment_line` | Skip __COMMENT__-prefixed lines |
| `test_hash_lines_not_comments` | # lines treated as normal text |
| `test_equals_line` | = lines treated as normal text |
| `test_dedup_only` | Skip __DEDUP__ only lines |
| `test_prot_only` | Skip __PROTECTED__ only lines |
| `test_already_translated` | Skip lines with translation |
| `test_no_japanese` | Skip lines without Japanese |
| `test_symbol_only_auto_translate` | Auto-translate symbols |
| `test_valid_japanese_line` | Valid lines pass through |
| `test_skip_comments_disabled` | Comments pass when disabled |
| `test_skip_equals_disabled` | Equals pass when disabled |

#### TestValidateBatchPre (3 tests)

| Test | Purpose |
|------|---------|
| `test_mixed_batch` | Categorize various line types |
| `test_with_existing_translations` | Respect existing translations |
| `test_empty_batch` | Handle empty batch |

#### TestExtractAnchors (4 tests)

| Test | Purpose |
|------|---------|
| `test_basic_anchors` | Extract [, ], " etc. |
| `test_fullwidth_equivalents` | ［］ maps to canonical |
| `test_japanese_quotes` | 「」 maps to " |
| `test_no_anchors` | Empty set for no anchors |

#### TestCountAnchorOccurrences (3 tests)

| Test | Purpose |
|------|---------|
| `test_count_brackets` | Count [ occurrences |
| `test_count_with_equivalents` | Include fullwidth variants |
| `test_count_quotes` | Count all quote variants |

#### TestValidateLinePost (7 tests)

| Test | Purpose |
|------|---------|
| `test_clean_translation` | Valid translation passes |
| `test_too_many_japanese` | Reject >4 JP chars |
| `test_few_japanese_warning` | Warn about 1-4 JP chars |
| `test_max_japanese_custom` | Custom max works |
| `test_anchor_preservation` | Preserved anchors pass |
| `test_anchor_missing_warning` | Warn on missing anchors |
| `test_anchor_check_disabled` | No warn when disabled |

#### TestValidateBatchPost (1 test)

| Test | Purpose |
|------|---------|
| `test_batch_validation` | Validate batch of translations |

#### TestReassembleTranslations (3 tests)

| Test | Purpose |
|------|---------|
| `test_basic_reassembly` | Reassemble in correct order |
| `test_preserve_comments` | Preserve __COMMENT__ and context marker lines |
| `test_no_preserve` | Don't preserve when disabled |

#### TestValidationIntegration (1 test)

| Test | Purpose |
|------|---------|
| `test_full_pipeline` | Complete validation pipeline |

---

### dev/test_conditional_prompts.py (86 tests)

Conditional prompt system tests for the reworked 11-prompt set: pattern detection, dynamic instruction generation, merged-request instructions, user customization, and integration.

#### TestConditionalPrompt (8 tests)

| Test | Purpose |
|------|---------|
| `test_create_basic` | Create conditional prompt with defaults |
| `test_matches_simple_pattern` | Match single pattern in text |
| `test_matches_multiple_patterns` | Match multiple patterns in text |
| `test_no_match` | No patterns matched returns false |
| `test_invalid_regex_skipped` | Invalid regex patterns silently skipped |
| `test_serialization_roundtrip` | to_dict and from_dict preserve data including pattern_examples |
| `test_get_dynamic_instruction_no_examples` | Dynamic instruction returns base when no examples |
| `test_get_dynamic_instruction_with_examples` | Dynamic instruction includes relevant examples |

#### TestBuiltinConditions (5 tests)

| Test | Purpose |
|------|---------|
| `test_exactly_nine_builtins` | Exactly 11 built-in conditions after rework |
| `test_all_expected_names_present` | All 11 expected condition names present (including code_context, span_content) |
| `test_removed_conditions_absent` | 6 removed conditions no longer present |
| `test_all_have_required_fields` | All builtins have required fields |
| `test_unique_names` | Condition names are unique |

#### TestPatternMatching (30 tests)

| Test | Purpose |
|------|---------|
| `test_temprepl_matches_temprepl_token` | __TEMPREPL_0_0__ detection |
| `test_temprepl_matches_cust_token` | __CUST__ Custom Placeholder detection |
| `test_temprepl_no_match_plain` | No match on plain text |
| `test_delim_matches_square` | [square] delimiter detection |
| `test_delim_matches_curly` | {curly} delimiter detection |
| `test_delim_matches_angle` | <angle> delimiter detection |
| `test_delim_matches_double_underscore` | __dunder__ delimiter detection |
| `test_delim_no_match_plain` | No match on plain text |
| `test_linebreaks_matches_br` | <br> tag detection |
| `test_linebreaks_matches_br_uppercase` | <BR /> uppercase detection |
| `test_linebreaks_matches_escaped_n` | \\n escape detection |
| `test_linebreaks_matches_literal_newline` | Literal newline detection |
| `test_linebreaks_no_match_plain` | No match on plain text |
| `test_color_matches_numeric` | \\c[4] detection |
| `test_color_matches_hex` | \\c[#FF0000] detection |
| `test_color_no_match_plain` | No match on plain text |
| `test_media_matches_se` | \\se[sound] detection |
| `test_media_matches_SE` | \\SE[beep] uppercase detection |
| `test_media_matches_pic` | \\pic[image] detection |
| `test_media_matches_wait` | \\wait[60] detection |
| `test_media_matches_fadein` | \\fadein[30] detection |
| `test_media_no_match_plain` | No match on plain text |
| `test_formatting_matches_fb` | \\fb detection |
| `test_formatting_matches_fr` | \\fr detection |
| `test_formatting_matches_italic` | \\i[2] detection |
| `test_formatting_matches_bold` | \\b detection |
| `test_formatting_no_match_plain` | No match on plain text |
| `test_formatting_does_not_match_newline` | \\n NOT in formatting patterns |
| `test_ruby_matches` | \\rb[漢字,かんじ] detection |
| `test_ruby_no_match_plain` | No match on plain text |
| `test_ellipsis_matches_dots` | ... detection |
| `test_ellipsis_matches_unicode` | …… detection |
| `test_ellipsis_no_match_plain` | No match on plain text |
| `test_speaker_matches_colon_dialogue` | Name: dialogue detection |
| `test_speaker_matches_fullwidth_colon` | 太郎：dialogue detection |
| `test_speaker_no_match_plain` | No match on plain text |
| `test_speaker_no_match_long_name` | Names >30 chars don't match |

#### TestDynamicInstructions (7 tests)

| Test | Purpose |
|------|---------|
| `test_delimiter_only_square` | Lists only [square] when only that matches |
| `test_delimiter_square_and_curly` | Lists both types when both match |
| `test_delimiter_double_underscore` | Lists __double_underscore__ when matched |
| `test_linebreak_only_br` | Lists only <br> tags when only those match |
| `test_linebreak_only_escaped_n` | Lists only \\n when only that matches |
| `test_linebreak_multiple_kinds` | Lists all detected linebreak kinds |
| `test_color_dynamic_with_examples` | Color codes shows matched examples |

#### TestConditionalPromptManager (12 tests)

| Test | Purpose |
|------|---------|
| `test_init_loads_builtins` | Manager loads all 9 builtins on init |
| `test_evaluate_batch_empty` | Empty batch returns empty list |
| `test_evaluate_batch_detects_color` | Batch with color codes triggers condition |
| `test_evaluate_batch_detects_delimiter` | Batch with delimiters triggers condition |
| `test_evaluate_batch_sorted_by_priority` | Results sorted by priority (high first) |
| `test_build_instructions_empty` | No conditions = empty string |
| `test_build_instructions_with_patterns` | Conditions build instruction block |
| `test_set_condition_enabled` | Enable/disable conditions |
| `test_get_condition` | Retrieve condition by name |
| `test_add_custom_condition` | Add user-defined conditions |
| `test_remove_custom_condition` | Remove custom conditions |
| `test_cannot_remove_builtin` | Builtin conditions cannot be removed |
| `test_list_conditions` | List conditions with filters |
| `test_disabled_condition_not_evaluated` | Disabled conditions skipped |

#### TestUserCustomization (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_user_overrides` | User config overrides builtins |
| `test_load_custom_conditions` | User-defined conditions loaded |
| `test_save_user_conditions` | Save conditions to JSON file |
| `test_create_default_config` | Generate default config template |

#### TestMergedRequestInstruction (5 tests)

| Test | Purpose |
|------|---------|
| `test_empty_returns_empty` | Empty boundaries → empty string |
| `test_single_block_returns_empty` | Single block → empty string |
| `test_all_single_lines` | All single-line blocks → unrelated text |
| `test_mixed_blocks` | Mixed sizes describe boundaries |
| `test_three_mixed_blocks` | Three blocks describe all boundaries |

#### TestIntegration (4 tests)

| Test | Purpose |
|------|---------|
| `test_full_workflow` | Complete evaluation workflow |
| `test_disabled_conditions_not_included` | Disabled conditions skipped |
| `test_category_ordering` | Category-based priority ordering |
| `test_all_nine_conditions_can_trigger` | All 9 conditions trigger with correct input |

---

### dev/test_standard_mode.py (37 tests)

Standard mode tests for symbol conversion, ellipsis compression, PROTECTED handling, and integration.

#### TestNormalizeLang (4 tests)

| Test | Purpose |
|------|---------|
| `test_japanese_aliases` | ja, jp, jpn, japanese all map to jpn |
| `test_english_aliases` | en, eng, english all map to eng |
| `test_case_insensitive` | Language codes are case-insensitive |
| `test_unknown_lang` | Unknown codes pass through unchanged |

#### TestBuildSymbolReplacements (4 tests)

| Test | Purpose |
|------|---------|
| `test_jpn_to_eng` | Japanese → English replacement table |
| `test_same_language_no_replacements` | Same lang → empty table |
| `test_empty_language_no_replacements` | Empty/null lang → empty table |
| `test_eng_to_jpn` | English → Japanese replacement table |

#### TestApplySymbolConversion (6 tests)

| Test | Purpose |
|------|---------|
| `test_convert_japanese_quotes` | 「」 → "" conversion |
| `test_convert_fullwidth_digits` | ０-９ → 0-9 conversion |
| `test_convert_mixed_content` | Mixed content with speaker format |
| `test_preserve_br_tags` | <br> tags not affected |
| `test_empty_lines_ignored` | Empty lines skipped |
| `test_stats_tracking` | Conversion count statistics |

#### TestSymbolConversionOnSampleData (3 tests)

| Test | Purpose |
|------|---------|
| `test_speaker_dialogue_format` | Speaker: 「Dialogue」 format |
| `test_dialogue_with_br_and_fullwidth_space` | <br>　 sequences preserved |
| `test_narration_lines` | Narration (no speaker) handling |

#### TestEllipsisCompression (7 tests)

| Test | Purpose |
|------|---------|
| `test_compress_simple_ellipsis` | ... → compressed |
| `test_compress_long_ellipsis` | ...... → compressed |
| `test_compress_multiple_ellipses` | Multiple ellipses in line |
| `test_no_ellipsis` | No ellipsis → no change |
| `test_decompress_ellipsis` | Restore compressed ellipsis |
| `test_decompress_multiple` | Restore multiple ellipses |
| `test_roundtrip` | Compress → decompress roundtrip |

#### TestProtCompression (6 tests)

| Test | Purpose |
|------|---------|
| `test_compress_single_prot` | Single PROTECTED (non-adjacent) |
| `test_compress_adjacent_prots` | Adjacent PROTs cluster |
| `test_compress_multiple_clusters` | Multiple PROTECTED clusters |
| `test_no_prot` | No PROTECTED → no change |
| `test_decompress_single` | Restore single cluster |
| `test_roundtrip` | Compress → decompress roundtrip |

#### TestGetStandardConfig (2 tests)

| Test | Purpose |
|------|---------|
| `test_default_config_values` | Defaults: symbol_conversion=True, etc. |
| `test_config_preserves_existing_values` | Existing config not overwritten |

#### TestStandardModeIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_apply_pre_symbol_conversion_enabled` | apply_pre triggers conversion |
| `test_apply_pre_with_sample_data` | Full sample data processing |

#### TestMissingFullwidthCharacters (3 tests)

| Test | Purpose |
|------|---------|
| `test_fullwidth_equals_sign` | ＝ → = conversion |
| `test_fullwidth_letters_converted` | Ａ-Ｚ, ａ-ｚ → A-Z, a-z |
| `test_fullwidth_brackets` | 【】→[], 《》→<> |

---

### dev/test_cli_languages.py (23 tests)

CLI language selection and normalization tests.

#### TestNormalizeLanguageCode (10 tests)

| Test | Purpose |
|------|---------|
| `test_japanese_aliases` | ja, jp, jpn, japanese → "ja" |
| `test_english_aliases` | en, eng, english → "en" |
| `test_german_aliases` | de, deu, ger, german, deutsch → "de" |
| `test_french_aliases` | fr, fra, fre, french → "fr" |
| `test_spanish_aliases` | es, spa, spanish → "es" |
| `test_chinese_aliases` | zh-cn, chinese, simplified → "zh-CN" |
| `test_korean_aliases` | ko, kor, korean → "ko" |
| `test_case_insensitive` | JA, ENGLISH, German → normalized |
| `test_whitespace_handling` | Strips leading/trailing whitespace |
| `test_unknown_language_returns_none` | Unknown codes return None |

#### TestGetLanguageName (3 tests)

| Test | Purpose |
|------|---------|
| `test_known_languages` | ja → "Japanese", de → "German" |
| `test_aliases_return_names` | jpn → "Japanese", ger → "German" |
| `test_unknown_returns_as_is` | Unknown codes returned unchanged |

#### TestLanguageAliasCoverage (3 tests)

| Test | Purpose |
|------|---------|
| `test_iso_639_1_codes_covered` | ja, en, de, fr, es, ko supported |
| `test_iso_639_2_codes_covered` | jpn, eng, deu, fra, spa, kor supported |
| `test_full_names_covered` | japanese, english, german, etc. supported |

#### TestCLILanguageIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_update_config_languages` | Config updated with language names |
| `test_get_current_config` | Current language config retrieved |

#### TestTranslationDirections (5 tests)

| Test | Purpose |
|------|---------|
| `test_ja_to_en` | Japanese → English (most common) |
| `test_ja_to_de` | Japanese → German |
| `test_ja_to_fr` | Japanese → French |
| `test_ja_to_es` | Japanese → Spanish |
| `test_en_to_de` | English → German |

---

### dev/test_languages.py (87 tests) - TASK 16.1

Language module consolidation tests. Created as part of TASK 16.1 to verify
`functions/languages.py` provides a single source of truth for both
`options.py` (GUI) and `CLI.py` language handling.

#### TestLanguageClass (7 tests)

| Test | Purpose |
|------|---------|
| `test_language_creation` | Can create Language instance |
| `test_language_immutable` | Language instances are frozen |
| `test_language_matches_code` | matches() works for code |
| `test_language_matches_name` | matches() works for name |
| `test_language_matches_native` | matches() works for native name |
| `test_language_matches_alias` | matches() works for aliases |
| `test_language_no_match` | matches() returns False for non-matches |

#### TestLanguagesRegistry (17 tests)

| Test | Purpose |
|------|---------|
| `test_languages_not_empty` | Registry has entries |
| `test_languages_has_14_languages` | Exactly 14 languages defined |
| `test_*_defined` (14 tests) | Each language defined correctly |
| `test_all_have_required_fields` | All fields present |
| `test_all_have_descriptions` | Descriptions provided |

#### TestGetLanguageNames (6 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | Returns List[str] |
| `test_returns_14_names` | 14 names returned |
| `test_sorted_alphabetically` | Names sorted |
| `test_contains_japanese` | Japanese in list |
| `test_contains_english` | English in list |
| `test_contains_all_expected` | All expected names present |

#### TestGetLanguageCodes (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | Returns List[str] |
| `test_returns_14_codes` | 14 codes returned |
| `test_sorted_alphabetically` | Codes sorted |
| `test_contains_expected_codes` | All codes present |

#### TestGetLanguageByCode (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_language` | Returns Language for valid code |
| `test_returns_none_for_unknown` | None for invalid code |
| `test_case_sensitive` | Direct lookup is case-sensitive |
| `test_chinese_codes` | zh-CN and zh-TW handled |

#### TestGetLanguageByName (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_language` | Returns Language for valid name |
| `test_case_insensitive` | Case-insensitive lookup |
| `test_returns_none_for_unknown` | None for invalid name |
| `test_strips_whitespace` | Whitespace stripped |

#### TestGetLanguageByAlias (7 tests)

| Test | Purpose |
|------|---------|
| `test_finds_by_code` | Finds by canonical code |
| `test_finds_by_name` | Finds by English name |
| `test_finds_by_native` | Finds by native name |
| `test_finds_by_alias` | Finds by alias |
| `test_case_insensitive` | Case-insensitive |
| `test_returns_none_for_unknown` | None for invalid |
| `test_chinese_aliases` | Chinese variant aliases |

#### TestNormalizeLanguageCode (6 tests)

| Test | Purpose |
|------|---------|
| `test_returns_code_for_code` | ja → ja |
| `test_returns_code_for_name` | Japanese → ja |
| `test_returns_code_for_alias` | jp → ja |
| `test_case_insensitive` | JP → ja |
| `test_returns_none_for_unknown` | None for invalid |
| `test_chinese_normalization` | Chinese variants |

#### TestGetLanguageNameFromCode (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_name_for_code` | ja → Japanese |
| `test_returns_name_for_alias` | jp → Japanese |
| `test_returns_input_for_unknown` | unknown → unknown |

#### TestGetLanguageDict (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns Dict |
| `test_has_14_entries` | 14 entries |
| `test_structure_correct` | name, native, description |
| `test_japanese_entry` | Japanese entry correct |

#### TestBuildLanguageAliases (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns Dict |
| `test_contains_codes` | Contains canonical codes |
| `test_contains_aliases` | Contains all aliases |
| `test_all_lowercase_keys` | All keys lowercase |

#### TestIsValidLanguage (4 tests)

| Test | Purpose |
|------|---------|
| `test_valid_code` | True for valid codes |
| `test_valid_name` | True for valid names |
| `test_valid_alias` | True for valid aliases |
| `test_invalid` | False for invalid |

#### TestCompatibilityWithOptionsModule (1 test)

| Test | Purpose |
|------|---------|
| `test_names_match_old_list` | Names match old options.py list |

#### TestCompatibilityWithCLIModule (3 tests)

| Test | Purpose |
|------|---------|
| `test_dict_structure_compatible` | Dict structure CLI-compatible |
| `test_all_cli_languages_present` | All old CLI languages present |
| `test_aliases_match_cli` | Aliases match CLI behavior |

#### TestConsolidationVerification (8 tests) - Critical

| Test | Purpose |
|------|---------|
| `test_options_imports_from_languages` | options.py uses languages.py |
| `test_cli_imports_from_languages` | CLI.py uses languages.py |
| `test_cli_aliases_from_languages` | CLI aliases from languages.py |
| `test_cli_normalize_uses_languages` | CLI normalize uses languages.py |
| `test_cli_get_language_name_uses_languages` | CLI get_name uses languages.py |
| `test_options_and_cli_have_same_languages` | Options & CLI match |
| `test_no_hardcoded_languages_in_options` | No hardcoded list in options.py |
| `test_no_hardcoded_languages_in_cli` | No hardcoded dict in CLI.py |

#### TestEdgeCases (4 tests)

| Test | Purpose |
|------|---------|
| `test_empty_string` | Handles "" |
| `test_whitespace_only` | Handles "   " |
| `test_special_characters` | Handles @#$ |
| `test_numeric_input` | Handles 123 |

---

### dev/test_api_providers.py (60 tests) - TASK 16.2

Tests for consolidated API provider definitions. Verifies single source of truth
in `functions/options.py` with imports from global_options.py and CLI.py.

#### TestAPIProvidersStructure (7 tests)

| Test | Purpose |
|------|---------|
| `test_api_providers_not_empty` | API_PROVIDERS is not empty |
| `test_api_providers_has_expected_count` | Has 6 providers |
| `test_api_providers_has_required_keys` | Contains all expected keys |
| `test_each_provider_has_required_fields` | Each has name, base_url, models |
| `test_each_provider_name_is_string` | Names are non-empty strings |
| `test_each_provider_base_url_is_string` | URLs are strings |
| `test_each_provider_models_is_list` | Models are non-empty lists |

#### TestOpenAIProvider (4 tests)

| Test | Purpose |
|------|---------|
| `test_openai_exists` | OpenAI provider exists |
| `test_openai_name` | Has "OpenAI" display name |
| `test_openai_url` | Has correct base URL |
| `test_openai_models` | Has expected models |

#### TestGeminiProvider (4 tests)

| Test | Purpose |
|------|---------|
| `test_gemini_exists` | Gemini provider exists |
| `test_gemini_name` | Has "Google Gemini" name |
| `test_gemini_url` | Has googleapis.com URL |
| `test_gemini_models` | Has expected models |

#### TestAnthropicProvider (4 tests)

| Test | Purpose |
|------|---------|
| `test_anthropic_exists` | Anthropic provider exists |
| `test_anthropic_name` | Has "Anthropic Claude" name |
| `test_anthropic_url` | Has api.anthropic.com URL |
| `test_anthropic_models` | Has Claude models |

#### TestLocalProvider (3 tests)

| Test | Purpose |
|------|---------|
| `test_local_exists` | Local provider exists |
| `test_local_name` | Has "Local/Custom" name |
| `test_local_url` | Has localhost URL |

#### TestOllamaProvider (3 tests)

| Test | Purpose |
|------|---------|
| `test_ollama_exists` | Ollama provider exists |
| `test_ollama_name` | Has "Ollama" name |
| `test_ollama_url` | Has localhost:11434 URL |

#### TestLMStudioProvider (3 tests)

| Test | Purpose |
|------|---------|
| `test_lmstudio_exists` | LM Studio provider exists |
| `test_lmstudio_name` | Has "LM Studio" name |
| `test_lmstudio_url` | Has localhost:1234 URL |

#### TestGetApiUrls (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary |
| `test_has_all_providers` | Contains all providers |
| `test_values_are_strings` | All values are strings |
| `test_cli_compatibility` | Matches CLI KNOWN_API_URLS |

#### TestGetProviderModels (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list_for_valid_provider` | Returns list for valid |
| `test_returns_empty_for_invalid_provider` | Empty for invalid |
| `test_returns_correct_models` | Returns correct models |

#### TestGetAllProviderModels (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary |
| `test_has_all_providers` | Contains all providers |
| `test_values_are_lists` | All values are lists |
| `test_cli_compatibility` | Matches CLI KNOWN_MODELS |

#### TestGetProviderNames (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | Returns list |
| `test_has_all_providers` | Contains all providers |
| `test_count_is_correct` | Has 6 providers |

#### TestGetProviderDisplayName (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_string` | Returns string |
| `test_returns_correct_name` | Returns correct names |
| `test_returns_key_for_invalid_provider` | Returns key for unknown |

#### TestAPIProvidesConsolidation (3 tests) - Critical

| Test | Purpose |
|------|---------|
| `test_options_and_global_options_same_object` | Identity check (same object) |
| `test_cli_providers_accessible` | CLI uses options.py functions for provider data |
| `test_no_duplicate_definitions` | No duplicate definitions |

#### TestAPIUrlFormats (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_urls_are_valid_format` | All URLs start with http |
| `test_remote_providers_have_https` | Remote uses HTTPS |
| `test_local_providers_use_localhost` | Local uses localhost |
| `test_urls_end_with_version_path` | URLs contain /v1 |

#### TestModelLists (3 tests)

| Test | Purpose |
|------|---------|
| `test_all_model_names_are_strings` | All models are strings |
| `test_all_model_names_non_empty` | No empty model names |
| `test_no_duplicate_models_per_provider` | No duplicates per provider |

---

### dev/test_model_encodings.py (52 tests) - TASK 16.3

Tests for consolidated model encoding definitions. Verifies single source of truth
in `functions/config.py` with imports from chunker.py and logit_bias.py.

#### TestModelEncodingsStructure (8 tests)

| Test | Purpose |
|------|---------|
| `test_model_encodings_not_empty` | MODEL_ENCODINGS is not empty |
| `test_model_encodings_has_expected_count` | Has 9 models |
| `test_model_encodings_has_required_keys` | Contains all expected models |
| `test_each_encoding_is_string` | All encodings are strings |
| `test_each_encoding_is_valid` | All encodings are valid tiktoken encodings |
| `test_default_encoding_exists` | DEFAULT_ENCODING is defined |
| `test_default_encoding_is_string` | DEFAULT_ENCODING is a string |
| `test_default_encoding_is_valid` | DEFAULT_ENCODING is valid tiktoken encoding |

#### TestGPT4Models (5 tests)

| Test | Purpose |
|------|---------|
| `test_gpt4_exists` | gpt-4 model exists |
| `test_gpt4_turbo_exists` | gpt-4-turbo model exists |
| `test_gpt4_turbo_preview_exists` | gpt-4-turbo-preview model exists |
| `test_gpt4_uses_cl100k` | gpt-4 uses cl100k_base |
| `test_gpt4_turbo_uses_cl100k` | gpt-4-turbo uses cl100k_base |

#### TestGPT4oModels (4 tests)

| Test | Purpose |
|------|---------|
| `test_gpt4o_exists` | gpt-4o model exists |
| `test_gpt4o_mini_exists` | gpt-4o-mini model exists |
| `test_gpt4o_uses_o200k` | gpt-4o uses o200k_base |
| `test_gpt4o_mini_uses_o200k` | gpt-4o-mini uses o200k_base |

#### TestGPT35Models (4 tests)

| Test | Purpose |
|------|---------|
| `test_gpt35_turbo_exists` | gpt-3.5-turbo model exists |
| `test_gpt35_turbo_16k_exists` | gpt-3.5-turbo-16k model exists |
| `test_gpt35_uses_cl100k` | gpt-3.5-turbo uses cl100k_base |
| `test_gpt35_16k_uses_cl100k` | gpt-3.5-turbo-16k uses cl100k_base |

#### TestLegacyModels (4 tests)

| Test | Purpose |
|------|---------|
| `test_davinci003_exists` | text-davinci-003 model exists |
| `test_davinci002_exists` | text-davinci-002 model exists |
| `test_davinci003_uses_p50k` | text-davinci-003 uses p50k_base |
| `test_davinci002_uses_p50k` | text-davinci-002 uses p50k_base |

#### TestGetEncodingForModel (6 tests)

| Test | Purpose |
|------|---------|
| `test_returns_encoding_for_known_model` | Returns encoding for known model |
| `test_returns_default_for_unknown_model` | Returns default for unknown model |
| `test_handles_gpt4` | Handles gpt-4 correctly |
| `test_handles_gpt4o` | Handles gpt-4o correctly |
| `test_handles_legacy` | Handles legacy models correctly |
| `test_returns_string` | Always returns a string |

#### TestGetSupportedEncodings (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | Returns list |
| `test_has_all_encodings` | Contains all encodings |
| `test_no_duplicates` | No duplicate encodings |
| `test_includes_expected` | Includes cl100k, o200k, p50k |

#### TestGetModelsForEncoding (5 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | Returns list |
| `test_cl100k_has_models` | cl100k_base returns models |
| `test_o200k_has_models` | o200k_base returns gpt-4o models |
| `test_p50k_has_models` | p50k_base returns legacy models |
| `test_unknown_encoding_returns_empty` | Unknown encoding returns empty |

#### TestModelEncodingsConsolidation (4 tests) - Critical

| Test | Purpose |
|------|---------|
| `test_chunker_imports_from_config` | chunker.py imports from config.py |
| `test_logit_bias_imports_from_config` | logit_bias.py imports from config.py |
| `test_chunker_and_config_same_object` | Identity check (same object) |
| `test_logit_bias_and_config_same_object` | Identity check (same object) |

#### TestChunkerBackwardCompatibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_chunker_model_encodings_exists` | MODEL_ENCODINGS still accessible |
| `test_chunker_default_encoding_exists` | DEFAULT_ENCODING still accessible |
| `test_chunker_get_encoding_exists` | get_encoding_for_model still works |
| `test_chunker_has_all_models` | Has all 9 models |

#### TestLogitBiasBackwardCompatibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_logit_bias_model_encodings_exists` | MODEL_ENCODINGS still accessible |
| `test_logit_bias_default_encoding_exists` | DEFAULT_ENCODING still accessible |
| `test_logit_bias_get_encoding_exists` | get_encoding_for_model still works |
| `test_logit_bias_has_all_models` | Has all 9 models |

---

### dev/test_model_pricing.py (52 tests) - TASK 16.4

Tests for consolidated model pricing definitions. Verifies single source of truth
in `functions/config.py` with imports from estimate.py and analysis.py.

#### TestModelPricingStructure (7 tests)

| Test | Purpose |
|------|---------|
| `test_model_pricing_not_empty` | MODEL_PRICING is not empty |
| `test_model_pricing_has_expected_count` | Has 11+ models |
| `test_model_pricing_has_required_keys` | Contains all expected models |
| `test_each_model_has_required_fields` | Each has name/input/output |
| `test_each_model_name_is_string` | Names are non-empty strings |
| `test_each_model_input_price_is_number` | Input prices are numeric |
| `test_each_model_output_price_is_number` | Output prices are numeric |

#### TestOpenAIModels (5 tests)

| Test | Purpose |
|------|---------|
| `test_gpt41_exists` | GPT-4.1 model exists |
| `test_gpt4o_exists` | GPT-4o model exists |
| `test_gpt4o_mini_exists` | GPT-4o Mini model exists |
| `test_gpt4_turbo_exists` | GPT-4 Turbo model exists |
| `test_gpt4o_mini_is_cheapest_openai` | Mini is cheapest OpenAI |

#### TestClaudeModels (4 tests)

| Test | Purpose |
|------|---------|
| `test_claude35_sonnet_exists` | Claude 3.5 Sonnet exists |
| `test_claude3_opus_exists` | Claude 3 Opus exists |
| `test_claude3_haiku_exists` | Claude 3 Haiku exists |
| `test_claude_haiku_is_cheapest_claude` | Haiku is cheapest Claude |

#### TestGeminiModels (5 tests)

| Test | Purpose |
|------|---------|
| `test_gemini15_pro_exists` | Gemini 1.5 Pro exists |
| `test_gemini15_flash_exists` | Gemini 1.5 Flash exists |
| `test_gemini20_flash_exists` | Gemini 2.0 Flash exists |
| `test_gemini20_flash_lite_exists` | Gemini 2.0 Flash Lite exists |
| `test_gemini_flash_lite_is_free` | Flash Lite is free tier |

#### TestGetModelPricing (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict_for_valid_model` | Returns pricing dict for valid |
| `test_returns_default_for_unknown_model` | Returns default for unknown |
| `test_returns_correct_values` | Returns correct pricing values |

#### TestGetModelNames (3 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | Returns list |
| `test_has_all_models` | Contains all models |
| `test_contains_expected_models` | Contains expected model IDs |

#### TestGetModelDisplayName (2 tests)

| Test | Purpose |
|------|---------|
| `test_returns_display_name` | Returns human-readable name |
| `test_returns_model_id_for_unknown` | Falls back for unknown |

#### TestEstimateCost (6 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dict with cost values |
| `test_zero_tokens_zero_cost` | Zero tokens = zero cost |
| `test_uses_default_model_when_none` | Uses default when model=None |
| `test_uses_specified_model` | Uses specified model pricing |
| `test_rounds_up_to_cents` | Rounds up to nearest cent |
| `test_free_model_zero_cost` | Free tier returns zero cost |

#### TestGetAllModelPricing (2 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns complete pricing dict |
| `test_same_as_model_pricing` | Same object as MODEL_PRICING |

#### TestModelPricingConsolidation (4 tests) - Critical

| Test | Purpose |
|------|---------|
| `test_estimate_and_config_same_object` | estimate.py uses config.py |
| `test_analysis_imports_estimate_cost` | analysis.py uses config.py |
| `test_analysis_backward_compat_constants` | PRICE constants preserved |
| `test_no_duplicate_definitions` | No duplicate definitions |

#### TestEstimateBackwardCompatibility (3 tests)

| Test | Purpose |
|------|---------|
| `test_model_pricing_exists` | MODEL_PRICING accessible |
| `test_default_model_exists` | DEFAULT_MODEL accessible |
| `test_output_multiplier_exists` | OUTPUT_MULTIPLIER accessible |

#### TestAnalysisBackwardCompatibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_price_constants_exist` | PRICE_GPT41_* exist |
| `test_price_constants_correct` | Values are correct |
| `test_jp_output_multiplier_exists` | JP multiplier exists |
| `test_estimate_cost_callable` | estimate_cost is callable |

#### TestDefaultConstants (4 tests)

| Test | Purpose |
|------|---------|
| `test_default_pricing_model_exists` | DEFAULT_PRICING_MODEL exists |
| `test_default_pricing_model_is_valid` | Is valid model ID |
| `test_output_token_multiplier_exists` | OUTPUT_TOKEN_MULTIPLIER exists |
| `test_output_token_multiplier_value` | Has expected value (1.2) |

---

### dev/test_gui_modi_integration.py (45 tests) - TASK 16.5

Tests for GUI-Modi integration. Verifies that GUI Step 4 (Preprocessing) uses
modi/ modules via mode_adapter instead of hardcoded patterns.

| Class | Tests | Purpose |
|-------|-------|---------|
| TestModeAdapterImports | 8 | Module exports all functions |
| TestEllipsisCompression | 4 | Ellipsis compression via modi |
| TestSymbolConversion | 6 | Symbol conversion via modi |
| TestProtCompression | 4 | PROTECTED compression via modi |
| TestProtectCode | 4 | Protect code patterns |
| TestCustomPlaceholder | 4 | Custom placeholders |
| TestPreprocessingPipeline | 3 | Unified pipeline |
| TestCommonPatterns | 3 | Common pattern helpers |
| TestSessionStateIntegration | 3 | SessionState config |
| TestPreprocessingStepIntegration | 3 | PreprocessingStep imports |
| TestModeAdapterModiConsistency | 2 | Modi consistency check |
| TestGuiModiIntegrationCount | 1 | Test count verification |

**New Files Created:**
- `gui/helpers/__init__.py` - Helper package exports
- `gui/helpers/mode_adapter.py` - Adapter layer (400+ lines)
- `dev/test_gui_modi_integration.py` - 45 tests

---

### dev/test_gui_analysis_integration.py (45 tests) - TASK 16.6 + 18.1

Integration tests for GUI Step 2 (Analysis) using analysis_adapter.

| Test Class | Count | Description |
|------------|-------|-------------|
| TestAnalysisAdapterImports | 8 | Module imports |
| TestLanguageDetection | 6 | Language detection |
| TestCodePatternDetection | 6 | Code pattern detection |
| TestSpeakerDetection | 4 | Speaker detection |
| TestLineStatistics | 4 | Line statistics |
| TestTokenCounting | 4 | Token counting |
| TestAnalysisPipeline | 4 | Full analysis pipeline |
| TestGUIStepIntegration | 4 | GUI step integration |
| TestCoreConsistency | 2 | Core function consistency |
| TestAnalysisStepUIConstruction | 2 | UI construction (no duplicates) - TASK 18.1 |
| TestGuiAnalysisIntegrationCount | 1 | Test count verification |

**New Files Created:**
- `gui/helpers/analysis_adapter.py` - Adapter layer (528 lines)
- `dev/test_gui_analysis_integration.py` - 45 tests (43 original + 2 for TASK 18.1)

---

### dev/test_speaker_detection.py (97 tests) - Speaker Detection Rules

Unit tests for enhanced speaker detection validation rules in `name_glossary_functions.py`.

| Test Class | Count | Description |
|------------|-------|-------------|
| TestBasicSpeakerDetection | 8 | Basic NAME: pattern extraction |
| TestBalancedBrackets | 15 | Bracket balance validation (ASCII + CJK) |
| TestNoNewlineBeforeColon | 4 | Multiline rejection rules |
| TestLengthLimit | 9 | Script-aware length limits (30 Latin / 20 CJK) |
| TestHasBalancedBrackets | 11 | `_has_balanced_brackets()` helper |
| TestIsCjkChar | 6 | `_is_cjk_char()` helper |
| TestSpeakerLengthOk | 6 | `_speaker_length_ok()` helper |
| TestFalsePositivePrevention | 8 | Real-world false positive patterns (skill descs, templates, NPC descriptions) |
| TestUtilitySettingsSpeakerThreshold | 6 | UtilitySettings speaker_threshold field (default, to_dict, from_dict, roundtrip) |
| TestSpeakerThresholdCollapse | 10 | Threshold-based speaker split logic (above/below/edge cases) |
| TestTermTranslationThresholdFilter | 6 | Below-threshold speakers excluded from term translation |
| TestGlossaryImportThresholdFilter | 4 | Below-threshold speakers excluded from glossary import |
| TestCUDataIntegration | 5 | Integration tests against CU.CherryAI.json real-world data |

---

### dev/test_gui_glossary_integration.py (76 tests) - TASK 16.7

Integration tests for GUI Step 3 (Information) using glossary_adapter.
Bridges gui/steps/information.py with functions/glossary.py, 
functions/project_config.py, and functions/style_presets.py.

| Test Class | Count | Description |
|------------|-------|-------------|
| TestGlossaryEntryView | 8 | GlossaryEntryView data class |
| TestStylePresetView | 3 | StylePresetView data class |
| TestGlossaryConstants | 5 | Type and gender constants |
| TestLoadGlossary | 2 | Glossary loading |
| TestSaveGlossary | 2 | Glossary saving |
| TestAddGlossaryEntry | 3 | Adding entries |
| TestGetGlossaryEntriesByType | 2 | Type filtering |
| TestGetGlossaryNames | 2 | Name retrieval |
| TestGetGlossaryStats | 3 | Statistics |
| TestSearchGlossary | 3 | Search functionality |
| TestGetStylePresets | 4 | Style preset listing |
| TestGetStylePresetNames | 3 | Preset name listing |
| TestGetStylePresetByName | 2 | Preset lookup |
| TestGetStylePresetPrompt | 3 | Prompt text generation |
| TestGetPresetsByCategory | 2 | Category organization |
| TestCreateProjectConfig | 5 | Config creation |
| TestLoadProjectConfig | 3 | Config loading |
| TestGetProjectApiOverrides | 2 | API override extraction |
| TestGetCharactersFromGlossary | 2 | Character extraction |
| TestSyncCharactersToGlossary | 3 | Character sync |
| TestGlossaryEntryViewRoundtrip | 2 | Dict roundtrip |
| TestStylePresetViewRoundtrip | 1 | Dict roundtrip |
| TestIntegration | 3 | End-to-end workflows |
| TestModuleImports | 4 | Module exports |
| TestErrorHandling | 4 | Error handling |

**New Files Created:**
- `gui/helpers/glossary_adapter.py` - Adapter layer (774 lines)
- `dev/test_gui_glossary_integration.py` - 76 tests

**Key Adapter Functions:**
- Glossary: load_glossary, save_glossary, add_glossary_entry, search_glossary
- Style: get_style_presets, get_style_preset_names, get_style_preset_prompt
- Config: create_project_config, load_project_config, get_project_api_overrides
- Characters: get_characters_from_glossary, sync_characters_to_glossary

---

### dev/test_gui_chunker_integration.py (87 tests) - TASK 16.8

Integration tests for GUI Step 5 (Estimation) using chunker_adapter.
Bridges gui/steps/estimate.py with functions/chunker.py, 
functions/chunk_optimizer.py, and functions/rate_limiter.py.

| Test Class | Count | Description |
|------------|-------|-------------|
| TestConstants | 8 | Exported constants |
| TestCountTokens | 6 | Token counting |
| TestCountTokensBatch | 4 | Batch token counting |
| TestIsTiktokenAvailable | 1 | Tiktoken availability check |
| TestChunkModeView | 5 | ChunkModeView enum |
| TestGetChunkModes | 1 | Mode listing |
| TestChunkConfigView | 4 | ChunkConfigView data class |
| TestCreateChunkConfig | 2 | Config factory |
| TestChunkLines | 6 | Line chunking |
| TestEstimateChunks | 3 | Chunk estimation |
| TestRateLimitView | 3 | RateLimitView data class |
| TestGetModelRateLimits | 4 | Model rate limits |
| TestGetAllModelLimits | 2 | All model limits |
| TestTimeEstimateView | 2 | TimeEstimateView data class |
| TestEstimateRateLimitTime | 7 | Time estimation |
| TestEstimateTimeForModel | 2 | Model-specific time |
| TestOptimizerStatsView | 4 | OptimizerStatsView data class |
| TestCreateOptimizerStats | 2 | Stats creation |
| TestGetAdaptiveChunkSize | 3 | Adaptive sizing |
| TestGetOptimizerRecommendation | 2 | Optimizer recommendations |
| TestEstimateTranslationJob | 5 | Combined estimation |
| TestEstimatePyIntegration | 2 | estimate.py integration |
| TestEdgeCases | 6 | Edge cases |
| TestChunkResultView | 3 | ChunkResultView data class |

**New Files Created:**
- `gui/helpers/chunker_adapter.py` - Adapter layer (810 lines)
- `dev/test_gui_chunker_integration.py` - 87 tests

**Key Adapter Functions:**
- Token: count_tokens, count_tokens_batch, is_tiktoken_available
- Chunking: chunk_lines, estimate_chunks, create_chunk_config
- Rate Limits: get_model_rate_limits, get_all_model_limits
- Time: estimate_rate_limit_time, estimate_time_for_model
- Optimizer: get_adaptive_chunk_size, get_optimizer_recommendation
- Combined: estimate_translation_job

---

### CLI Configuration Tests (Manual)

CLI configuration commands can be tested manually:

```bash
# Test config listing
python CherryAI.py config

# Test option details
python CherryAI.py config api_url
python CherryAI.py config model

# Test value setting (numbers and direct values)
python CherryAI.py config api_url 2
python CherryAI.py config model gemini-2.0-flash

# Test validation
python CherryAI.py config temperature 0.5
python CherryAI.py config chunk_size 100

# Test glossary commands
python CherryAI.py glossary
python CherryAI.py glossary list names
python CherryAI.py glossary search test

# Test help commands
python CherryAI.py help
python CherryAI.py help config
python CherryAI.py help glossary
```

---

### IO Configuration Tests (Manual)

IO format configuration commands can be tested manually:

```bash
# Test IO settings display
python CherryAI.py io

# Test formats listing
python CherryAI.py io formats

# Test setting extract format
python CherryAI.py io extract txt
python CherryAI.py io extract csv
python CherryAI.py io extract json

# Test setting inject format
python CherryAI.py io inject txt
python CherryAI.py io inject json
python CherryAI.py io inject xlsx

# Test standard command (set both at once)
python CherryAI.py io standard txt json
python CherryAI.py io standard csv txt

# Test preserve_original toggle
python CherryAI.py io preserve_original true
python CherryAI.py io preserve_original false

# Test invalid format handling
python CherryAI.py io extract invalid_format

# Test help
python CherryAI.py help io
```

---

### File Format Handler Tests (Implemented - 57 tests)

Tests for formats/ module in dev/test_formats.py:

```python
# Implemented test classes:
# TestTxtHandler - txt file read/write
# TestCsvHandler - csv with pair support
# TestTsvHandler - tsv with pair support
# TestJsonHandler - json structures (strings, pairs, objects, dictionary format)
# TestXlsxHandler - xlsx with openpyxl
# TestHtmlHandler - HTML parsing with BS4
# TestFormatRegistry - handler registration and lookup
# TestIOConfig - configuration serialization
# TestDocumentPlaceholders - PDF/EPUB placeholders
# TestRpgMakerPlaceholders - RPG Maker placeholders
# TestFormatIntegration - cross-format workflows
```

---

### dev/test_br_protection.py (26 tests)

Tests for `<br>` tag protection and recovery in CherryAI.

**Test Classes:**

#### TestBrTagConditionalPrompt (8 tests)
Tests CONDITION_LINEBREAKS pattern matching.

| Test | Purpose |
|------|---------|
| `test_br_tag_pattern_matches_simple_br` | Match `<br>` |
| `test_br_tag_pattern_matches_br_with_slash` | Match `<br/>` |
| `test_br_tag_pattern_matches_br_with_space_slash` | Match `<br />` |
| `test_br_tag_pattern_no_match_without_br` | No false positives |
| `test_br_tag_pattern_no_match_partial` | No match for `<br` without `>` |
| `test_br_tag_in_builtin_conditions` | Verify in BUILTIN_CONDITIONS |
| `test_br_tag_has_code_category` | Category is "code" |
| `test_br_tag_has_high_priority` | Priority >= 85 |

#### TestBrCountValidation (4 tests)
Tests `<br>` tag counting logic.

| Test | Purpose |
|------|---------|
| `test_count_br_simple` | Count basic `<br>` tags |
| `test_count_br_variants` | Count mixed `<br>`, `<br/>`, `<br />` |
| `test_count_br_case_insensitive` | `<BR>`, `<Br>` counted same |
| `test_count_br_with_fullwidth_space` | `<br>　` (with fullwidth space) |

#### TestBrRecovery (2 tests)
Tests postanalysis recovery of missing `<br>` tags.

| Test | Purpose |
|------|---------|
| `test_compare_identifies_br_mismatch` | Detect missing `<br>` in final |
| `test_compare_no_mismatch_when_counts_match` | No false mismatch when equal |

#### TestBrConditionalPromptManager (2 tests)
Tests ConditionalPromptManager detection of `<br>`.

| Test | Purpose |
|------|---------|
| `test_manager_detects_br_in_batch` | Manager finds `<br>` in Japanese text |
| `test_manager_no_br_detection_without_tags` | No detection when absent |

#### TestBrWithJapaneseText (4 tests)
Tests `<br>` with actual Japanese text patterns.

| Test | Purpose |
|------|---------|
| `test_sample_line_pattern` | Match `Speaker: 「Text<br>　More」` |
| `test_br_with_fullwidth_space_after` | Fullwidth space indentation |
| `test_multiple_br_in_single_line` | Count 3+ `<br>` in one line |
| `test_br_preserves_surrounding_japanese` | Works with 「」 quotes |

#### TestBrEdgeCases (6 tests)
Tests edge cases for `<br>` handling.

| Test | Purpose |
|------|---------|
| `test_empty_string` | No crash on empty input |
| `test_only_br_tag` | Match string that is just `<br>` |
| `test_br_at_start` | Match `<br>Hello` |
| `test_br_at_end` | Match `Hello<br>` |
| `test_consecutive_br_tags` | Count `<br><br>` as 2 |
| `test_similar_but_not_br_tag` | `<break>` not matched |

---

### dev/test_gender_inference.py (21 tests)

Tests for enhanced gender inference with explicit detection and weighted signals.

**Test Classes:**

#### TestExplicitGenderDetection (5 tests)
Tests `detect_explicit_gender()` for status cards and narrative markers.

| Test | Purpose |
|------|---------|
| `test_status_card_female` | Detect "名前：リリィ、性別：女性" as Female |
| `test_status_card_male` | Detect "名前：タロウ、性別：男性" as Male |
| `test_no_explicit_gender` | Return None when no explicit marker |
| `test_transformation_female` | Detect "リリィは女性になった" |
| `test_wrong_name_no_match` | Don't match status cards for different names |

#### TestHonorificGenderFromOthers (3 tests)
Tests `detect_honorific_gender_from_others()` for weighted signals.

| Test | Purpose |
|------|---------|
| `test_chan_indicates_female` | ちゃん from others suggests Female |
| `test_kun_indicates_male` | くん from others suggests Male |
| `test_no_honorific_no_result` | Return None when no honorifics used |

#### TestComprehensiveGenderInference (4 tests)
Tests `infer_gender_comprehensive()` multi-signal priority.

| Test | Purpose |
|------|---------|
| `test_explicit_overrides_pronouns` | Explicit marker overrides conflicting pronouns |
| `test_others_honorific_overrides_pronouns` | Others' honorifics override self-pronouns |
| `test_falls_back_to_pronouns` | Falls back when no explicit signals |
| `test_unknown_when_no_signals` | Returns Unknown with no signals |

#### TestBasicGenderInference (5 tests)
Tests original `infer_gender_from_context()` function.

| Test | Purpose |
|------|---------|
| `test_male_pronouns` | 俺/僕 pronouns infer Male |
| `test_female_pronouns` | あたし pronouns infer Female |
| `test_conflicting_signals` | Majority wins when above threshold |
| `test_conflicting_signals_below_threshold` | Below threshold returns Unknown |
| `test_empty_data_unknown` | Empty data returns Unknown |

#### TestConstants (2 tests)
Tests gender inference constants.

| Test | Purpose |
|------|---------|
| `test_explicit_gender_values_complete` | All gender mappings present |
| `test_strong_honorifics_present` | ちゃん/くん honorifics defined |

#### TestLilyCharacterCase (2 tests)
Integration tests for リリィ (Lily) character edge case.

| Test | Purpose |
|------|---------|
| `test_lily_with_all_signals` | Explicit marker overrides 俺様 pronoun |
| `test_lily_without_explicit_fallback_to_others` | Falls back to ちゃん from others |

---

### dev/test_gender_batch.py (31 tests)

Tests for batch gender inference via `infer_genders_batch()`, optimized for large manifests.

**Test Classes:**

#### TestBatchBasic (9 tests)
Tests basic batch inference functionality.

| Test | Purpose |
|------|---------|
| `test_empty_names` | Empty names list returns empty dict |
| `test_empty_lines` | Empty lines returns Unknown for all |
| `test_single_speaker_no_signals` | Single speaker with no evidence → Unknown |
| `test_explicit_gender_female` | Status card "性別：女性" detected as Female |
| `test_explicit_gender_male` | Status card "性別：男性" detected as Male |
| `test_honorific_chan_female` | ちゃん from others → Female |
| `test_honorific_kun_male` | くん from others → Male |
| `test_self_pronoun_ore_male` | 俺 in own dialogue → Male |
| `test_self_pronoun_atashi_female` | あたし in own dialogue → Female |

#### TestBatchPriority (2 tests)
Tests multi-signal priority ordering.

| Test | Purpose |
|------|---------|
| `test_explicit_overrides_honorific` | Explicit gender wins over conflicting honorifics |
| `test_honorific_overrides_pronoun` | Others' honorifics win over self-pronouns |

#### TestBatchLimits (5 tests)
Tests `max_lines_per_speaker` and `min_evidence` settings.

| Test | Purpose |
|------|---------|
| `test_max_lines_limits_scanning` | Only scans up to max_lines dialogue lines |
| `test_min_evidence_threshold` | Requires min evidence points for decision |
| `test_do_all_false_early_exit` | Stops scanning early when consensus reached |
| `test_do_all_true_full_scan` | Forces full scan even with early consensus |
| `test_ignore_unknown_excludes` | No-evidence lines excluded from max count |

#### TestBatchCancel (2 tests)
Tests cancellation support.

| Test | Purpose |
|------|---------|
| `test_cancel_returns_partial` | Cancel callback stops processing, returns partial results |
| `test_cancel_check_called` | Cancel callback is polled during processing |

#### TestBatchProgress (1 test)
Tests progress reporting.

| Test | Purpose |
|------|---------|
| `test_progress_callback_called` | Progress callback receives (current, total, name) updates |

#### TestBatchMultiSpeaker (2 tests)
Tests with multiple simultaneous speakers.

| Test | Purpose |
|------|---------|
| `test_multiple_speakers_batch` | Correctly infers gender for many speakers at once |
| `test_speakers_not_in_lines` | Speakers with no dialogue lines → Unknown |

#### TestBatchPerformance (2 tests)
Tests performance characteristics.

| Test | Purpose |
|------|---------|
| `test_large_input_completes` | 200 speakers + 10K lines completes in <2s |
| `test_batch_faster_than_individual` | Batch is faster than per-speaker calls |

#### TestBatchEdgeCases (7 tests)
Tests edge cases and boundary conditions.

| Test | Purpose |
|------|---------|
| `test_speaker_talks_to_self` | Self-referencing honorifics not counted as others |
| `test_mixed_gender_honorifics` | Conflicting honorifics resolved by majority weight |
| `test_unicode_names` | Full Unicode name handling (kanji, kana) |
| `test_empty_dialogue_lines` | Lines with empty dialogue portion handled |
| `test_colon_variants` | Both half-width and full-width colons detected |
| `test_no_speaker_lines` | Lines without speaker format skipped cleanly |
| `test_duplicate_names` | Duplicate names in input handled without error |

#### TestBatchGUIIntegration (1 test)
Tests GUI-facing integration.

| Test | Purpose |
|------|---------|
| `test_return_format_matches_gui` | Return tuple format matches GUI expectations |

---

### dev/test_game_pipeline.py (133 tests)

Test suite for the test_game folder pipeline. Creates manifests from test_game files and validates
the __COMMENT__ / context marker system end-to-end, then exercises the preprocessing pipeline
(deduplication, protect code, standard helpers) with direct mode calls, tests request
building (build_line_infos, build_requests, PromptBuilder), mock translation with flaw injection,
postprocessing recovery, wordwrap, game update detection, and import translations.

#### TestTask1_ManifestCreation (1 test)

| Test | Purpose |
|------|---------|
| `test_create_manifest_1_1` | Create manifest from test_game files, verify contents |

#### TestTask1_ValidationChanges (15 tests)

| Test | Purpose |
|------|---------|
| `test_comment_marker_skipped` | __COMMENT__ lines skipped |
| `test_comment_marker_with_leading_space` | Indented __COMMENT__ skipped |
| `test_hash_lines_are_normal_text` | # lines are valid text (not comments) |
| `test_hash_only_no_japanese` | # without Japanese → NO_JAPANESE |
| `test_equals_lines_are_normal_text` | = lines are valid text |
| `test_context_marker_dialogue` | __DIALOGUE__ → TAG |
| `test_context_marker_menu` | __MENU__ → TAG |
| `test_context_marker_choice` | __CHOICE__ → TAG |
| `test_context_marker_file` | __FILE__ → TAG |
| `test_context_marker_case_insensitive` | Case-insensitive matching |
| `test_context_marker_with_whitespace` | Whitespace around markers |
| `test_context_marker_in_text_not_matched` | Embedded markers not caught |
| `test_dedup_still_skipped` | __DEDUP__ unchanged |
| `test_prot_still_skipped` | __PROTECTED__ unchanged |
| `test_empty_still_skipped` | Empty lines unchanged |
| `test_batch_validation_new_markers` | Batch categorizes new types |

#### TestTask1_LineEntry (5 tests)

| Test | Purpose |
|------|---------|
| `test_context_marker_field` | LineEntry tag field |
| `test_file_end_marker` | __FILE__ → file_end |
| `test_no_marker` | Regular lines have no marker |
| `test_marker_serialization` | to_dict/from_dict roundtrip |
| `test_no_marker_not_in_dict` | Sparse serialization |

#### TestTask1_FileFormat (2 tests)

| Test | Purpose |
|------|---------|
| `test_txt_handler_reads_all` | TxtHandler reads __COMMENT__ and markers |
| `test_txt_handler_no_hash_filtering` | TxtHandler does not filter # |

#### TestTask2_Deduplication (3 tests)

| Test | Purpose |
|------|---------|
| `test_dedup_pre_basic` | Exact duplicates collapsed to __DEDUP__ |
| `test_dedup_pre_comment_lines_not_deduped` | __COMMENT__ lines not deduped against each other |
| `test_dedup_from_test_file` | Dedup on actual test_deduplication.txt content |

#### TestTask2_ProtectCode (3 tests)

| Test | Purpose |
|------|---------|
| `test_protect_code_rpg_maker` | RPG Maker codes replaced with __PROTECTED__ |
| `test_protect_code_records_prepro_ops` | Captured values recorded in prepro_ops |
| `test_protect_code_from_test_file` | Code protection on test_code_patterns.txt |

#### TestTask2_StandardHelpers (2 tests)

| Test | Purpose |
|------|---------|
| `test_ellipsis_compression` | Ellipsis processing via standard_mode.apply_pre |
| `test_symbol_conversion` | Fullwidth symbol processing via standard_mode.apply_pre |

#### TestTask2_FullPipeline (3 tests)

| Test | Purpose |
|------|---------|
| `test_pipeline_dedup_then_protect` | Dedup runs first, then protect code |
| `test_pipeline_preserves_comment_lines` | __COMMENT__ and markers survive preprocessing |
| `test_pipeline_on_full_test_game` | Full pipeline on all test_game files |

#### TestTask5_BuildLineInfos (9 tests)

| Test | Purpose |
|------|---------|
| `test_basic_conversion` | Normal lines become valid LineInfo |
| `test_comment_lines_not_filtered` | __COMMENT__ not filtered by build_line_infos |
| `test_context_markers_invalid` | Tag lines marked is_invalid=True |
| `test_context_type_propagation` | Context type propagates to subsequent lines |
| `test_placeholder_lines_invalid` | __PROTECTED__ and __DEDUP__ lines marked invalid |
| `test_empty_lines_invalid` | Empty/whitespace lines marked invalid |
| `test_prepro_preferred_over_orig` | prepro field takes priority over orig |
| `test_file_end_does_not_propagate` | file_end resets context to unknown |
| `test_from_test_game_files` | LineInfos from actual test_game content |

#### TestTask5_BuildRequests (5 tests)

| Test | Purpose |
|------|---------|
| `test_basic_request_formation` | Valid lines form translation requests |
| `test_menu_choice_split` | Menu/choice blocks get separate requests |
| `test_file_boundary_split` | File boundaries split into sections |
| `test_invalid_lines_excluded` | __PROTECTED__, __DEDUP__, empty excluded |
| `test_from_test_game_files` | Requests from actual test_game content |

#### TestTask5_PromptAssembly (3 tests)

| Test | Purpose |
|------|---------|
| `test_prompt_builder_init` | PromptBuilder initializes from config dir |
| `test_construct_system_prompt` | System prompt contains base template |
| `test_context_type_prompt_injection` | Context types add specific instructions |

#### TestTask6_MockTranslatorBasic (5 tests)

| Test | Purpose |
|------|---------|
| `test_basic_translation` | MockTranslator replaces Japanese with NATO-phonetic words |
| `test_preserves_prot_tokens` | __PROTECTED__ tokens preserved through translation |
| `test_empty_and_whitespace` | Empty/whitespace lines pass through unchanged |
| `test_deterministic_output` | Same input produces same output each time |
| `test_batch_translate` | translate_batch processes list of lines |

#### TestTask6_FlawInjection (5 tests)

| Test | Purpose |
|------|---------|
| `test_placeholder_malformation` | FlawConfig injects placeholder corruption |
| `test_anchor_manipulation` | FlawConfig injects anchor tag errors |
| `test_code_intrusion` | FlawConfig injects random code into output |
| `test_character_surgery` | FlawConfig injects character-level corruption |
| `test_flaw_report_tracking` | FlawReport tracks all injected flaws |

#### TestTask7_RecoveryBasic (4 tests)

| Test | Purpose |
|------|---------|
| `test_recover_strips_leading_trailing` | recover_line strips whitespace |
| `test_recover_fixes_quotes` | recover_line normalizes quote issues |
| `test_recover_empty_passthrough` | Empty lines pass through recovery |
| `test_recover_preserves_content` | Clean lines pass through unchanged |

#### TestTask7_PostProcessManager (4 tests)

| Test | Purpose |
|------|---------|
| `test_manager_init` | PostProcessManager initializes with ops and manifest |
| `test_manager_process_line` | Manager processes line through recovery pipeline |
| `test_manager_stats_tracking` | RecoveryStats tracks applied operations |
| `test_manager_batch_processing` | Manager processes multiple lines |

#### TestTask7_ProtectCodeRestore (2 tests)

| Test | Purpose |
|------|---------|
| `test_prot_token_restore` | __PROTECTED__ tokens restored to original values |
| `test_prot_restore_multiple` | Multiple __PROTECTED__ tokens restored correctly |

#### TestTask7_DedupRestore (1 test)

| Test | Purpose |
|------|---------|
| `test_dedup_pre_post_roundtrip` | Deduped lines restored from first-occurrence translation |

#### TestTask8_SmartWrap (9 tests)

| Test | Purpose |
|------|---------|
| `test_short_line_unchanged` | Lines shorter than width pass through unchanged |
| `test_wrap_at_word_boundary` | Long line breaks at word boundary |
| `test_hard_break_unbreakable_word` | Single word exceeding width is hard-broken |
| `test_existing_newlines_preserved` | Existing newlines treated as segment boundaries |
| `test_max_lines_truncation` | Output truncated to max_lines |
| `test_zero_width_returns_unchanged` | Width <= 0 returns text unchanged |
| `test_empty_input` | Empty string returns empty string |
| `test_custom_break_char` | Break character can be customized |
| `test_ignore_patterns_zero_width` | Ignore patterns contribute zero width |

#### TestTask8_ManualWrapLine (2 tests)

| Test | Purpose |
|------|---------|
| `test_basic_wrap` | Manual wrap delegates to smart_wrap via speaker pipeline |
| `test_short_line_unchanged` | Short line passes through unchanged |

#### TestTask8_PrettyWrap (4 tests)

| Test | Purpose |
|------|---------|
| `test_punctuation_preferred_break` | Pretty wrap prefers breaking after punctuation |
| `test_anti_orphan` | Anti-orphan moves word to prevent tiny last line |
| `test_no_orphan_prevention_when_disabled` | Orphan prevention can be disabled |
| `test_hanging_indent` | Continuation lines prefixed with hanging indent spaces |

#### TestTask8_ApplyWordwrap (8 tests)

| Test | Purpose |
|------|---------|
| `test_manual_mode_basic` | Manual mode wraps each line to specified width |
| `test_dict_config` | Config can be passed as a plain dict |
| `test_none_config_noop` | None config returns input unchanged |
| `test_zero_width_noop` | Width <= 0 returns input unchanged |
| `test_unknown_mode_noop` | Unknown mode returns input unchanged |
| `test_max_lines_via_config` | Max lines limits output line count |
| `test_ignore_codes_angle` | Ignore codes make HTML-like tags zero-width |
| `test_rpgmaker_mode` | RPGMaker mode uses pretty_wrap |

#### TestTask8_NormalizeBreakChar (5 tests)

| Test | Purpose |
|------|---------|
| `test_backslash_n_string` | '\\n' normalizes to actual newline |
| `test_newline_word` | 'newline' normalizes to actual newline |
| `test_linebreak_word` | 'linebreak' normalizes to actual newline |
| `test_none_defaults_newline` | None input defaults to newline |
| `test_custom_char_preserved` | Custom separator passed through unchanged |

#### TestTask8_TestGameWordwrap (4 tests)

| Test | Purpose |
|------|---------|
| `test_short_lines_unchanged` | Short fixture lines pass through unchanged |
| `test_long_lines_wrapped` | Long fixture lines get wrapped |
| `test_unbreakable_word_hard_broken` | Unbreakable words hard-broken |
| `test_batch_apply_on_fixture` | apply_wordwrap processes all fixture lines |

#### TestTask8_GetWordwrapModes (1 test)

| Test | Purpose |
|------|---------|
| `test_modes_structure` | Modes dict contains manual and rpgmaker with required keys |

#### TestTask9_UpdateFolderExists (3 tests)

| Test | Purpose |
|------|---------|
| `test_updates_folder_exists` | test_game_updates directory exists |
| `test_updated_dialogue_exists` | Updated dialogue file exists |
| `test_updated_menu_choice_exists` | Updated menu_choice file exists |

#### TestTask9_ChangeDetection (5 tests)

| Test | Purpose |
|------|---------|
| `test_dialogue_modified_lines_detected` | Identical text shows no changes |
| `test_dialogue_changes_detected` | Changes between original and updated detected |
| `test_change_types_present` | Modified change type present in comparison |
| `test_menu_choice_changes_detected` | Menu update changes detected |
| `test_unchanged_lines_counted` | Unchanged lines properly counted |

#### TestTask9_ComparisonResult (2 tests)

| Test | Purpose |
|------|---------|
| `test_to_dict_structure` | ComparisonResult.to_dict() has expected structure |
| `test_has_translation_flag` | Modified lines have has_translation=True |

#### TestTask9_UpdateManifestGeneration (3 tests)

| Test | Purpose |
|------|---------|
| `test_generate_update_manifest` | Update manifest generated from comparison |
| `test_update_manifest_has_changed_lines` | Update manifest contains changed lines |
| `test_update_text_generation` | Update text output generated |

#### TestTask10_MergeUpdateIntoManifest (6 tests)

| Test | Purpose |
|------|---------|
| `test_merge_preserves_original` | Merge does not modify original manifest |
| `test_merge_unchanged_lines_preserved` | Unchanged lines preserved in merge |
| `test_merge_new_line_appended` | New lines appended to merged manifest |
| `test_merge_deleted_flag` | Deleted flag propagated through merge |
| `test_merge_metadata_last_update` | Metadata records last_update |
| `test_merge_sorted_by_idx` | Merged lines sorted by idx |

#### TestTask10_ContentBasedImport (6 tests)

| Test | Purpose |
|------|---------|
| `test_exact_match_import` | Lines with identical orig get translations |
| `test_partial_match` | Only matching lines get imports |
| `test_no_match` | No matching lines yields zero imports |
| `test_numbered_fields_imported` | edit/tlc fields imported correctly |
| `test_first_match_wins` | Duplicate origs: first occurrence used |
| `test_multi_field_copy` | All copyable fields transferred |

#### TestTask10_FullWorkflow (2 tests)

| Test | Purpose |
|------|---------|
| `test_roundtrip_update_workflow` | Full workflow: compare, generate, merge |
| `test_unchanged_translations_preserved_through_workflow` | Unchanged lines keep translations after merge |

---

### dev/test_game_summary.py (22 tests)

Tests for game summary loading, project configuration, and API profile management.

**Test Classes:**

#### TestGameSummaryLoading (6 tests)
Tests `load_game_summary()` file loading and processing.

| Test | Purpose |
|------|---------|
| `test_load_empty_file` | Empty file returns empty string |
| `test_load_with_content` | Content loaded correctly |
| `test_comments_stripped` | Lines starting with "# " removed, "## " preserved |
| `test_placeholder_lines_removed` | Template placeholders like "[Title goes here]" removed |
| `test_truncation_at_max_chars` | Long summaries truncated at 2000 chars |
| `test_missing_file_returns_empty` | Non-existent file returns empty string |

#### TestSummaryFormatting (5 tests)
Tests `format_summary_for_prompt()` output formatting.

| Test | Purpose |
|------|---------|
| `test_empty_summary_returns_empty` | Empty input returns empty string |
| `test_basic_formatting` | Summary wrapped in "# Game Context" header |
| `test_includes_project_name` | Project name added when available |
| `test_includes_genre_and_tone` | Genre and tone added when available |
| `test_includes_style_notes` | Style notes appended when available |

#### TestProjectConfig (3 tests)
Tests `ProjectConfig` dataclass and persistence.

| Test | Purpose |
|------|---------|
| `test_default_values` | Default ProjectConfig has sensible values |
| `test_to_dict_roundtrip` | to_dict/from_dict preserves all fields |
| `test_ini_save_load_roundtrip` | INI save/load preserves config |

#### TestAPIProfile (2 tests)
Tests `APIProfile` dataclass.

| Test | Purpose |
|------|---------|
| `test_default_values` | Default APIProfile has sensible values |
| `test_to_dict_roundtrip` | to_dict/from_dict preserves all fields |

#### TestAPIProfileStorage (3 tests)
Tests API profile INI storage.

| Test | Purpose |
|------|---------|
| `test_save_and_load_profile` | Profile saved and loaded correctly |
| `test_multiple_profiles` | Multiple profiles can be stored |
| `test_delete_profile` | Profile can be deleted |

#### TestPromptBuilderIntegration (3 tests)
Integration tests for PromptBuilder with game summary.

| Test | Purpose |
|------|---------|
| `test_prompt_includes_summary` | System prompt includes game summary |
| `test_prompt_without_summary` | Prompt works without summary |
| `test_set_project_config_reloads_summary` | Config change reloads summary |

---

### dev/test_partial_translation.py (18 tests)

Tests for partial translation mode (TASK 9) - translating only first N lines.

**Test Classes:**

#### TestApplyPartialTranslation (7 tests)
Tests `_apply_partial_translation()` helper function in CLI.py.

| Test | Purpose |
|------|---------|
| `test_all_lines_translated` | When all lines translated, no skipping occurs |
| `test_partial_translation_with_limit` | Limit < total: remaining lines get skip marker |
| `test_empty_lines_no_marker` | Empty/whitespace lines don't get skip marker |
| `test_custom_skip_marker` | Custom marker like "[PENDING]" applied correctly |
| `test_no_skip_marker` | Empty marker leaves original unchanged |
| `test_empty_input` | Empty input returns empty result |
| `test_translated_exceeds_original` | Extra translated lines ignored |

#### TestPartialTranslationConfig (4 tests)
Tests configuration for partial translation in config.py.

| Test | Purpose |
|------|---------|
| `test_default_config_has_partial_translation` | DEFAULT_CONFIG has section |
| `test_default_max_lines_is_100` | Default limit is 100 lines |
| `test_get_partial_translation_config_structure` | Config returns expected keys |
| `test_get_partial_translation_config_defaults` | Sensible defaults returned |

#### TestPartialTranslationIntegration (3 tests)
Integration tests combining limit logic with content handling.

| Test | Purpose |
|------|---------|
| `test_limit_of_one` | Single line translation works |
| `test_limit_larger_than_content` | Limit > content translates all |
| `test_multiline_content_preservation` | Special characters preserved |

#### TestPartialTranslationEdgeCases (4 tests)
Edge cases for partial translation.

| Test | Purpose |
|------|---------|
| `test_single_line_file` | Single line file with limit works |
| `test_whitespace_only_lines` | Whitespace preserved, no marker |
| `test_zero_limit` | Zero limit means nothing translated |
| `test_negative_limit_treated_as_zero` | Negative limit skips all |

---

## Workflow Integration (analysis.py)

The comprehensive gender inference is fully integrated into the analysis workflow.

**Integration Points:**

1. **update_glossaries_from_analysis()** in `analysis.py`:
   - Reads input file content for comprehensive inference
   - Passes `full_text` and `lines` to `update_speakers_in_glossary()`
   - Enables all three detection tiers during normal analysis

2. **update_speakers_in_glossary()** in `name_glossary_functions.py`:
   - Extended signature with `full_text` and `lines` parameters
   - Now uses `infer_gender_comprehensive()` instead of `infer_gender_from_context()`
   - Multi-signal priority: explicit > others' honorifics > self-pronouns

3. **_infer_character_genders()** in `gui/steps/information.py`:
   - Uses `infer_genders_batch()` for batch inference across all speakers
   - Both script and LLM passes run in background threads with Cancel support
   - Settings (`gender_script_maximum`, `gender_script_minimum`, `ignore_unknown`, `do_all`) passed through as `max_lines_per_speaker`, `min_evidence`, etc.

**Verification:**
- All 21 gender inference tests pass
- All 31 batch gender inference tests pass
- All 144 core tests pass (options, normalization, config, validation, functions_v2)
- No regressions in existing functionality

---

## API2Glossary Manual Verification

The API2Glossary module requires a live API key to test. Manual verification:

**Test Command:**
```bash
python -c "from functions.API2Glossary import test_api_connection; print(test_api_connection())"
```

**Expected Result (Success):**
```
(True, {'status': 'success', 'message': "'太郎' correctly inferred as 'Male'", 
        'result': {'gender': 'Male'}, ...})
```

**Verification Status:** ✅ PASSED (2025-11-29)
- API key loaded from CherryAI.ini [api] section
- Model: gemini-2.0-flash-lite
- Test speaker: 太郎 → correctly inferred as Male
- Gender values are case-insensitive normalized (e.g. "female" → "Female")
- Any non-"Unknown" gender accepted as valid connection test result

---

## Tests Yet To Be Implemented

The following modules have been identified as needing test coverage:

### HIGH PRIORITY

| Module | Lines | Current State | Recommended Tests |
|--------|-------|---------------|-------------------|
| `glossary.py` | 936 | No pytest | Term matching, normalization, CSV parsing |
| `api_client.py` | 255 | No pytest | Request building, response parsing, error handling |

### MEDIUM PRIORITY

| Module | Lines | Current State | Recommended Tests |
|--------|-------|---------------|-------------------|
| `analysis.py` | 1971 | No tests | Line analysis, Japanese detection, code handling |
| `prompt_builder.py` | 201 | No tests | Prompt formatting, context injection |
| `wordwrap.py` | 853 | No tests | Line wrapping, character width calculation |

### LOW PRIORITY

| Module | Lines | Current State | Recommended Tests |
|--------|-------|---------------|-------------------|
| `modehelper.py` | 391 | No tests | Mode detection, file type handling |
| `mainhelper.py` | 305 | No tests | Main loop helpers, state management |
| `postanalysis.py` | 375 | Partial (test_br_protection.py) | Speaker fix, code recovery (already tested in br_protection) |


### Test Implementation Guidelines

When implementing new tests:

1. Create file `dev/test_<module>.py`
2. Follow existing patterns (pytest, fixtures, no LLM calls)
3. Test edge cases and error handling
4. Add documentation to this file
5. Update test count summary

---

## Tests for Planned Features

The following tests will be needed for upcoming features:

### API Response Verification (test_api_validator.py)

| Test Class | Test | Purpose |
|------------|------|---------|
| TestStructuralValidation | `test_valid_json_passes` | Well-formed JSON accepted |
| | `test_invalid_json_fails` | Malformed JSON rejected |
| | `test_line_count_match_passes` | Input/output count match accepted |
| | `test_line_count_mismatch_fails` | Count mismatch rejected |
| | `test_empty_response_fails` | Empty API response rejected |
| | `test_encoding_validation` | UTF-8 encoding verified |
| TestPlaceholderValidation | `test_prot_count_match` | __PROTECTED__ count verified |
| | `test_prot_count_mismatch` | Missing __PROTECTED__ detected |
| | `test_prot_format_corruption` | __PR OT__ (with space) detected |
| | `test_dedup_unchanged` | __DEDUP__ lines must be unchanged |
| | `test_temprepl_preserved` | __TEMPREPL_X_Y__ exact match |
| | `test_position_drift_within_tolerance` | Small position changes allowed |
| | `test_position_drift_exceeds_tolerance` | Large position drift flagged |
| TestContentValidation | `test_refusal_detection` | "I cannot translate" detected |
| | `test_refusal_patterns_comprehensive` | All refusal patterns detected |
| | `test_untranslated_detection` | Output == input flagged |
| | `test_over_translation_detection` | Output >3x length flagged |
| | `test_under_translation_detection` | Output <0.3x length flagged |
| | `test_language_verification` | Output in target language |
| TestRecoveryStrategies | `test_retry_with_emphasis` | Emphasis strategy triggered |
| | `test_retry_with_split` | Split strategy for large batches |
| | `test_retry_line_by_line` | Individual line retry |
| | `test_fallback_to_original` | Original preserved on failure |
| | `test_recovery_success` | Successful recovery after retry |
| TestValidationMetrics | `test_metrics_tracking` | Validation stats recorded |
| | `test_error_frequency_tracking` | Common errors counted |

**Estimated: 27 tests**

### Prompt Builder Enhancements (test_prompt_builder.py)

| Test Class | Test | Purpose |
|------------|------|---------|
| TestBatchBuilding | `test_build_batches_respects_size` | Max batch size enforced |
| | `test_build_batches_respects_markers` | Context markers split batches |
| | `test_rolling_context_included` | Previous lines in context |
| | `test_batch_indices_correct` | Original indices preserved |
| TestGlossaryInjection | `test_selective_glossary` | Only present terms injected |
| | `test_empty_glossary_handled` | No glossary = no injection |
| | `test_character_list_appended` | Character info in prompt |
| TestTokenEstimation | `test_estimate_tokens_accuracy` | Token count reasonable |
| | `test_estimate_with_cjk` | CJK characters counted correctly |

**Estimated: 9 tests**

### API Client Enhancements (test_api_client.py)

| Test Class | Test | Purpose |
|------------|------|---------|
| TestAPIConfig | `test_config_from_dict` | Config loads from dict |
| | `test_config_defaults` | Missing keys use defaults |
| | `test_config_type_conversion` | String→int/float conversion |
| TestRateLimiting | `test_rate_limit_enforcement` | Rate limit wait triggered |
| | `test_rate_limit_cleanup` | Old timestamps removed |
| TestChunking | `test_chunk_splitting` | Large batches split correctly |
| | `test_chunk_size_respected` | Chunk size limit enforced |
| TestRetryLogic | `test_exponential_backoff` | Backoff delays increase |
| | `test_max_retries_respected` | Stops after max retries |
| | `test_retry_on_rate_limit` | Rate limit triggers retry |
| TestTranslation | `test_translate_batch_success` | Successful translation |
| | `test_translate_with_validation` | Validation integrated |
| | `test_translate_recovery` | Recovery on validation failure |

**Estimated: 13 tests**

### Extended Line Tags (test_line_tags.py)

| Test Class | Test | Purpose |
|------------|------|---------|
| TestTagSeverity | `test_severity_enum_values` | INFO/WARNING/ERROR/CRITICAL enum |
| | `test_severity_comparison` | INFO < WARNING < ERROR < CRITICAL |
| | `test_severity_color_mapping` | Severity maps to correct color |
| TestLineTag | `test_tag_creation` | Tag with name, severity, color |
| | `test_tag_with_timestamp` | Tag records creation time |
| | `test_tag_serialization` | Tag to/from JSON |
| TestLineEntryTags | `test_add_tag_to_line` | Tags list populated |
| | `test_add_duplicate_tag` | Same tag not added twice |
| | `test_remove_tag` | Tag removed from list |
| | `test_has_tag` | Tag presence check |
| | `test_get_highest_severity` | Returns max severity from all tags |
| | `test_empty_tags_info_severity` | No tags = INFO default |
| | `test_get_display_color` | Color from highest severity |
| TestAutoTagger | `test_auto_tag_after_translation` | api_translated added |
| | `test_auto_tag_manual_edit` | manual_edit added on change |
| | `test_auto_tag_placeholder_error` | placeholder_error on restore fail |
| | `test_auto_tag_code_mismatch` | code_mismatch when counts differ |
| | `test_auto_tag_empty_translation` | empty_translation on blank result |
| | `test_auto_tag_has_speaker` | has_speaker when detected |
| | `test_auto_tag_has_code` | has_code when protected |
| | `test_auto_tag_long_line` | long_line exceeds threshold |
| | `test_auto_tag_short_line` | short_line below threshold |
| TestTagFiltering | `test_filter_by_tag` | Filter lines with specific tag |
| | `test_filter_by_severity` | Filter lines >= severity |
| | `test_filter_multiple_tags` | Filter by tag combination |
| | `test_filter_empty_result` | No matches returns empty |

**Estimated: 27 tests**

### GUI Table View (test_table_controller.py)

| Test Class | Test | Purpose |
|------------|------|---------|
| TestTableColumn | `test_column_creation` | Column with name, width, sortable |
| | `test_column_editable` | Editable column flag |
| | `test_column_width_validation` | Width within bounds |
| TestTableSelection | `test_empty_selection` | Initial selection empty |
| | `test_single_row_select` | Select one row |
| | `test_multi_row_select` | Select multiple rows |
| | `test_range_select` | Shift+click range selection |
| | `test_toggle_select` | Ctrl+click toggle row |
| | `test_clear_selection` | Clear all selections |
| | `test_select_all` | Select all rows |
| TestTableSort | `test_sort_ascending` | Column sorted A-Z |
| | `test_sort_descending` | Column sorted Z-A |
| | `test_sort_toggle` | Click toggles direction |
| | `test_sort_preserves_data` | Data unchanged after sort |
| | `test_sort_stable` | Stable sort on equal values |
| TestTableFilter | `test_filter_by_column_value` | Show matching rows only |
| | `test_filter_by_tag` | Show rows with tag |
| | `test_filter_by_severity` | Show rows >= severity |
| | `test_filter_clear` | Remove filter shows all |
| | `test_filter_combined` | Multiple filters AND |
| TestTableSearch | `test_search_single_column` | Find in specific column |
| | `test_search_all_columns` | Find in any column |
| | `test_search_case_insensitive` | Case-insensitive by default |
| | `test_search_regex` | Regex pattern search |
| | `test_search_no_match` | No match returns empty |
| TestTableReplace | `test_replace_in_column` | Replace text in column |
| | `test_replace_in_selection` | Replace only in selected rows |
| | `test_replace_all` | Replace all occurrences |
| | `test_replace_count` | Returns replacement count |
| | `test_replace_regex` | Regex replacement |
| TestTableEdit | `test_edit_cell` | In-place cell edit |
| | `test_edit_triggers_manual_tag` | Edit adds manual_edit tag |
| | `test_edit_readonly_column` | Read-only column blocks edit |
| | `test_edit_validation` | Invalid value rejected |
| TestTableBulkOps | `test_add_tag_to_selected` | Bulk tag addition |
| | `test_remove_tag_from_selected` | Bulk tag removal |
| | `test_clear_field_selected` | Reset field to prior stage |
| | `test_delete_selected` | Mark selected as deleted |
| | `test_translate_selected` | API call for selected only |
| TestUndoRedo | `test_undo_single_edit` | Undo last edit |
| | `test_redo_after_undo` | Redo restores edit |
| | `test_undo_bulk_operation` | Undo bulk op (one step) |
| | `test_undo_limit` | Stack size limited |
| | `test_undo_clears_redo` | New edit clears redo stack |
| | `test_can_undo` | Check undo available |
| | `test_can_redo` | Check redo available |
| | `test_undo_description` | Get action description |
| TestTableExport | `test_export_visible_rows` | Export filtered view |
| | `test_export_selected_rows` | Export selection only |
| | `test_export_by_tag` | Export rows with tag |
| | `test_copy_to_clipboard` | Copy selection to clipboard |

**Estimated: 52 tests**

---

### dev/test_speaker_format.py (45 tests)

Speaker format preservation validation (TASK 10). Validates "Speaker: Dialogue" format 
detection and two-tier validation (retry + flag).

| Test Class | Test | Purpose |
|------------|------|---------|
| TestDetectSpeakerDialogueFormat | `test_standard_english_format` | Detect Speaker: "text" format |
| | `test_japanese_format_kakko` | Detect 太郎：「テキスト」format |
| | `test_single_quote_format` | Detect Speaker: 'text' format |
| | `test_parentheses_for_aside` | Detect Speaker: (aside) format |
| | `test_space_after_colon` | Handle space: "text" correctly |
| | `test_simple_command_between_colon_and_quote` | Allow \b between : and quote |
| | `test_no_colon_no_format` | Plain text not detected |
| | `test_colon_without_quote_no_format` | Colon: without quotes not detected |
| | `test_empty_line` | Empty line returns default info |
| | `test_whitespace_only` | Whitespace-only returns default info |
| | `test_quote_not_at_end` | Quote in middle not detected |
| | `test_unbalanced_quotes` | Mismatched quotes detected as unbalanced |
| | `test_fullwidth_parentheses` | 話者：（テキスト）detected |
| | `test_curly_quotes` | Curly/smart quotes detected |
| | `test_double_bracket_format` | 『double』brackets detected |
| TestValidateSpeakerFormatPreserved | `test_format_preserved_correctly` | Valid when format matches |
| | `test_format_lost_in_translation` | Invalid when format lost |
| | `test_original_has_no_format` | Valid when original has no format |
| | `test_balance_lost` | Detect when balance broken |
| | `test_different_quote_types_allowed` | Quote type can change |
| | `test_strict_mode_warns_on_quote_change` | Strict mode warns on type change |
| TestShouldRetryForSpeakerFormat | `test_no_retry_when_no_original_format` | No retry for non-speaker lines |
| | `test_retry_when_format_lost` | Retry when format lost |
| | `test_retry_when_balance_lost` | Retry when quotes unbalanced |
| | `test_no_retry_when_format_preserved` | No retry when preserved |
| TestQuoteCharacterSets | `test_opening_quotes_include_standard` | Opening set complete |
| | `test_closing_quotes_include_standard` | Closing set complete |
| | `test_parentheses_included` | () and （）included |
| | `test_quote_pairs_defined` | Pair mapping complete |
| | `test_colon_chars_include_both` | : and ： included |
| TestSpeakerFormatInfo | `test_default_values` | Dataclass defaults correct |
| | `test_to_dict_serialization` | Serialization works |
| TestConditionalPromptSpeakerFormat | `test_condition_in_builtin_list` | Condition registered |
| | `test_condition_matches_standard_format` | Pattern matches Speaker: "text" |
| | `test_condition_matches_japanese_format` | Pattern matches 話者：「テキスト」 |
| | `test_condition_no_match_plain_text` | Plain text not matched |
| | `test_condition_has_instruction` | Instruction text set |
| | `test_condition_priority` | Priority = 32 |
| TestSpeakerFormatEdgeCases | `test_colon_inside_quotes` | Colon inside quotes handled |
| | `test_multiple_colons_uses_first` | First colon is separator |
| | `test_trailing_whitespace` | Trailing space handled |
| | `test_complex_escape_command_not_simple` | Complex commands block detection |
| | `test_empty_speaker_name` | Empty speaker returns no format |
| | `test_unicode_speaker_name` | Unicode speakers work |
| | `test_mixed_quote_types_same_line` | Mixed types on one line |

---

### dev/test_cli_overrides.py (38 tests)

CLI API override parameter tests (TASK 3). Validates --model, --temperature, --timeout,
--chunk-size, and --preset command-line arguments.

| Test Class | Test | Purpose |
|------------|------|---------|
| TestValidateApiOverrides | `test_all_none_is_valid` | No overrides is valid |
| | `test_valid_temperature` | 0.0-2.0 passes |
| | `test_invalid_temperature_too_low` | <0.0 fails |
| | `test_invalid_temperature_too_high` | >2.0 fails |
| | `test_valid_timeout` | 10-600 passes |
| | `test_invalid_timeout_too_low` | <10 fails |
| | `test_invalid_timeout_too_high` | >600 fails |
| | `test_valid_chunk_size` | 10-200 passes |
| | `test_invalid_chunk_size_too_low` | <10 fails |
| | `test_invalid_chunk_size_too_high` | >200 fails |
| | `test_valid_preset` | Known presets pass |
| | `test_invalid_preset` | Unknown preset fails |
| | `test_model_always_valid` | Any model string valid |
| | `test_multiple_errors` | Multiple errors returned |
| TestApplyApiOverrides | `test_empty_overrides` | Empty dict no-op |
| | `test_none_overrides` | None values ignored |
| | `test_apply_model_override` | Model applied |
| | `test_apply_temperature_override` | Temperature applied |
| | `test_apply_timeout_override` | Timeout applied |
| | `test_apply_chunk_size_override` | Chunk size applied |
| | `test_invalid_temperature_ignored` | Out of range ignored |
| | `test_invalid_timeout_ignored` | Out of range ignored |
| | `test_invalid_chunk_size_ignored` | Out of range ignored |
| TestPresetApplication | `test_preset_names_available` | Default presets exist |
| | `test_get_preset_config` | Preset configs retrievable |
| | `test_apply_preset_changes_model` | Preset changes model |
| | `test_preset_then_override` | Override follows preset |
| TestCliArgsIntegration | `test_translate_accepts_model_arg` | --model parsed |
| | `test_translate_accepts_temperature_arg` | --temperature parsed |
| | `test_translate_accepts_timeout_arg` | --timeout parsed |
| | `test_translate_accepts_chunk_size_arg` | --chunk-size parsed |
| | `test_translate_accepts_preset_arg` | --preset parsed |
| | `test_multiple_override_args` | Combined args work |
| TestDefaultConfig | `test_default_api_section_exists` | api section exists |
| | `test_default_presets_section_exists` | presets section exists |
| | `test_default_temperature_valid` | Default temp valid |
| | `test_default_timeout_valid` | Default timeout valid |
| | `test_default_chunk_size_valid` | Default chunk valid |

---

### dev/test_api_validation.py (52 tests)

API response validation and retry recommendation tests (TASK 4). Validates placeholder
preservation, comprehensive translation validation, and per-line retry logic.

| Test Class | Test | Purpose |
|------------|------|---------|
| TestExtractPlaceholders | `test_single_prot` | Extract __PROTECTED__ |
| | `test_prot_with_index` | Extract __PROTECTED_1__ style |
| | `test_custom_placeholders` | Extract __NAME__ style |
| | `test_mixed_placeholders` | Mixed placeholder types |
| | `test_no_placeholders` | Empty for no placeholders |
| | `test_case_insensitive` | Normalize to uppercase |
| | `test_whitespace_variations` | Handle whitespace |
| | `test_empty_string` | Empty returns empty |
| TestCountPlaceholder | `test_count_single` | Count one occurrence |
| | `test_count_multiple` | Count multiple occurrences |
| | `test_count_indexed` | Count indexed separately |
| | `test_count_zero` | Zero when not present |
| | `test_case_insensitive_count` | Case-insensitive count |
| TestValidatePlaceholderPreserved | `test_all_placeholders_preserved` | Valid when preserved |
| | `test_placeholder_missing` | Invalid when missing |
| | `test_multiple_placeholders_some_missing` | Detect partial missing |
| | `test_placeholder_count_mismatch` | Detect count mismatch |
| | `test_extra_placeholder_warning` | Warn on extra placeholders |
| | `test_no_placeholders_in_original` | Valid when no placeholders |
| | `test_custom_placeholder_preserved` | Custom placeholders validated |
| | `test_custom_placeholder_missing` | Detect missing custom |
| TestValidateTranslationComprehensive | `test_valid_translation` | Valid passes all checks |
| | `test_empty_translation_triggers_retry` | Empty triggers retry |
| | `test_whitespace_only_translation` | Whitespace as empty |
| | `test_placeholder_missing_triggers_retry` | Missing placeholder retry |
| | `test_speaker_format_lost_triggers_retry` | Format loss triggers retry |
| | `test_speaker_format_preserved` | Preserved no retry |
| | `test_too_many_japanese_triggers_retry` | JP chars trigger retry |
| | `test_japanese_chars_warning_no_retry` | Few JP only warning |
| | `test_multiple_issues_multiple_retry_reasons` | Multiple reasons |
| | `test_line_index_preserved` | Line index in result |
| | `test_placeholder_result_included` | Placeholder result included |
| TestValidateBatchComprehensive | `test_all_valid` | All valid batch |
| | `test_some_need_retry` | Partial retry needed |
| | `test_line_count_mismatch` | Mismatch triggers full retry |
| | `test_empty_batch` | Empty batch valid |
| | `test_success_rate_calculation` | Success rate calc |
| | `test_per_line_results` | Per-line access |
| TestRetryReasons | `test_empty_translation_reason` | EMPTY_TRANSLATION used |
| | `test_placeholder_missing_reason` | PLACEHOLDER_MISSING used |
| | `test_speaker_format_lost_reason` | SPEAKER_FORMAT_LOST used |
| | `test_too_many_japanese_reason` | TOO_MANY_JAPANESE used |
| TestEdgeCases | `test_placeholder_with_special_chars_around` | Special chars around |
| | `test_multiple_identical_placeholders` | Same placeholder multiple |
| | `test_placeholder_only_line` | Placeholder-only line |
| | `test_unicode_with_placeholders` | Unicode + placeholders |
| | `test_nested_looking_placeholders` | Nested-looking handled |
| | `test_disable_placeholder_check` | Can disable check |
| | `test_disable_speaker_format_check` | Can disable format |
| TestValidationIntegration | `test_typical_translation_batch` | Typical mixed batch |
| | `test_batch_with_mangled_line` | One mangled line |
| | `test_per_line_error_isolation` | Errors isolated |

---

### dev/test_logit_bias.py (38 tests)

Token banning / logit bias tests. Validates LogitBiasConfig, LogitBiasManager,
preset application, CLI argument parsing, and tiktoken integration.

| Test Class | Test | Purpose |
|------------|------|---------|
| TestLogitBiasConfig | `test_default_config` | Default config values |
| | `test_custom_config` | Custom config values |
| TestLogitBiasManagerDisabled | `test_disabled_returns_empty_bias` | Disabled returns {} |
| | `test_disabled_summary` | Summary shows disabled |
| TestLogitBiasManagerEnabled | `test_banned_chars_get_bias_negative_100` | Banned → -100 bias |
| | `test_discouraged_chars_get_custom_bias` | Discouraged → custom bias |
| | `test_banned_overrides_discouraged` | Banned takes priority |
| | `test_multiple_chars_combined` | Multiple chars combined |
| | `test_is_available_with_tiktoken` | Availability check |
| | `test_summary_shows_banned` | Summary shows banned chars |
| TestLogitBiasTokenCache | `test_tokens_cached` | Token IDs cached |
| | `test_empty_char_returns_tokens` | Empty char returns tokens |
| TestPresets | `test_list_presets_returns_names` | List preset names |
| | `test_get_preset_description` | Get preset description |
| | `test_get_preset_description_unknown` | Unknown → empty |
| | `test_apply_preset_adds_chars` | Preset adds chars |
| | `test_apply_preset_unknown_returns_false` | Unknown → False |
| | `test_preset_in_config_auto_applied` | Config preset auto-applied |
| | `test_preset_merges_with_existing` | Preset merges chars |
| TestPresetContents | `test_no_fancy_punctuation_preset` | Preset content correct |
| | `test_no_em_dash_preset` | EM dash preset correct |
| | `test_no_smart_quotes_preset` | Smart quotes preset |
| TestCreateLogitBiasManager | `test_create_disabled` | Factory disabled |
| | `test_create_enabled_with_chars` | Factory with chars |
| | `test_create_with_preset` | Factory with preset |
| TestParseBanTokensArg | `test_empty_string` | Empty → empty set |
| | `test_single_char` | Single char parsed |
| | `test_named_alias_em_dash` | em_dash alias works |
| | `test_named_alias_en_dash` | en_dash alias works |
| | `test_mixed_aliases_and_chars` | Mixed parsing |
| | `test_smart_quote_aliases` | Smart quote aliases |
| TestTiktokenAvailability | `test_is_tiktoken_available_returns_bool` | Returns boolean |
| TestModelEncodings | `test_gpt4_uses_cl100k` | GPT-4 encoding |
| | `test_gpt4o_uses_o200k` | GPT-4o encoding |
| | `test_unknown_model_uses_default` | Unknown → default |
| TestEdgeCases | `test_disabled_no_encoder_init` | No encoder when disabled |
| | `test_unicode_chars_handled` | Unicode chars work |
| | `test_empty_banned_chars` | Empty chars handled |

---

### dev/test_retry_handler.py (47 tests)

Retry strategy tests. Validates BATCH, CONTEXTUAL, ISOLATED, and SKIP strategies
for handling failed translation lines.

| Test Class | Test | Purpose |
|------------|------|---------|
| TestRetryStrategy | `test_batch_value` | BATCH enum value |
| | `test_contextual_value` | CONTEXTUAL enum value |
| | `test_isolated_value` | ISOLATED enum value |
| | `test_skip_value` | SKIP enum value |
| TestRetryConfig | `test_default_config` | Default config values |
| | `test_custom_config` | Custom config values |
| TestRetryResult | `test_successful_result` | Success result attrs |
| | `test_failed_result` | Failed result with error |
| TestBatchRetryResult | `test_empty_result` | Empty result defaults |
| | `test_success_rate_calculation` | Success rate calc |
| TestRetryHandlerInit | `test_default_init` | Default initialization |
| | `test_custom_config` | Custom config accepted |
| TestRetryHandlerRetryCountTracking | `test_initial_count_is_zero` | Initial count = 0 |
| | `test_increment_retry_count` | Count increments |
| | `test_reset_retry_counts` | Reset clears counts |
| | `test_should_continue_retrying` | Continue check |
| | `test_get_exhausted_lines` | Exhausted detection |
| TestRetryHandlerBatch | `test_batch_retry_success` | Batch success |
| | `test_batch_retry_adds_emphasis_prompt` | Emphasis added |
| | `test_batch_retry_empty_result_marks_failed` | Empty = failed |
| TestRetryHandlerContextual | `test_contextual_includes_surrounding_context` | Context included |
| | `test_contextual_handles_edge_lines` | Edge lines work |
| TestRetryHandlerIsolated | `test_isolated_uses_minimal_prompt` | Minimal prompt |
| | `test_isolated_translates_one_at_a_time` | One line per call |
| TestRetryHandlerSkip | `test_skip_does_not_call_translate` | No translate call |
| | `test_skip_preserves_original_text` | Original preserved |
| TestCreateRetryHandler | `test_create_batch` | Factory batch |
| | `test_create_contextual` | Factory contextual |
| | `test_create_isolated` | Factory isolated |
| | `test_create_skip` | Factory skip |
| | `test_create_with_max_retries` | Custom max retries |
| | `test_create_unknown_defaults_to_batch` | Unknown → batch |
| TestParseRetryStrategyArg | `test_parse_batch` | Parse "batch" |
| | `test_parse_contextual` | Parse "contextual" |
| | `test_parse_context_alias` | "context" alias |
| | `test_parse_isolated` | Parse "isolated" |
| | `test_parse_single_alias` | "single" alias |
| | `test_parse_skip` | Parse "skip" |
| | `test_parse_none_alias` | "none" alias |
| | `test_parse_case_insensitive` | Case insensitive |
| | `test_parse_unknown_raises` | Unknown raises error |
| TestHelperFunctions | `test_list_retry_strategies` | List strategies |
| | `test_get_strategy_description` | Get description |
| | `test_get_strategy_description_all` | All have descriptions |
| TestEdgeCases | `test_empty_failed_indices` | Empty indices handled |
| | `test_translate_function_exception` | Exception handling |
| | `test_chunk_list_helper` | Chunk helper works |

---

### dev/test_request_cache.py (48 tests)

Request caching tests. Validates cache storage, retrieval, expiration,
LRU eviction, and different cache matching modes.

| Test Class | Test | Purpose |
|------------|------|---------|
| TestCacheMode | `test_strict_value` | STRICT enum value |
| | `test_model_only_value` | MODEL_ONLY enum value |
| | `test_any_value` | ANY enum value |
| TestCacheConfig | `test_default_config` | Default config values |
| | `test_custom_config` | Custom config values |
| | `test_mode_enum_type` | Mode is correct type |
| TestCacheEntry | `test_default_entry` | Default entry values |
| | `test_touch_updates_access` | Touch increments count |
| | `test_touch_updates_timestamp` | Touch updates time |
| | `test_is_expired_false_for_new` | New entries not expired |
| | `test_is_expired_true_for_old` | Old entries expired |
| | `test_to_dict_and_from_dict` | Serialization roundtrip |
| TestCacheStats | `test_default_stats` | Default stats zero |
| | `test_hit_rate_zero_when_empty` | Empty hit rate = 0 |
| | `test_hit_rate_calculation` | Hit rate calculated |
| | `test_to_dict` | Stats serialization |
| TestRequestCacheBasic | `test_store_and_get` | Store/retrieve works |
| | `test_get_miss_returns_none` | Miss returns None |
| | `test_disabled_cache_returns_none` | Disabled always None |
| | `test_stats_updated_on_hit` | Stats track hits |
| | `test_stats_updated_on_miss` | Stats track misses |
| TestRequestCacheModes | `test_model_only_mode_same_model_hits` | MODEL_ONLY same model |
| | `test_model_only_mode_different_model_misses` | MODEL_ONLY diff model |
| | `test_strict_mode_different_temp_misses` | STRICT temp mismatch |
| | `test_strict_mode_same_settings_hits` | STRICT all match |
| | `test_any_mode_ignores_model` | ANY ignores all |
| TestRequestCacheExpiration | `test_expired_entry_not_returned` | Expired not returned |
| | `test_cleanup_expired_removes_old` | Cleanup removes old |
| TestRequestCacheEviction | `test_eviction_when_over_limit` | LRU eviction works |
| | `test_lru_evicts_oldest` | Oldest evicted first |
| | `test_touch_updates_lru_order` | Touch updates LRU |
| TestRequestCachePersistence | `test_save_and_load` | Save/load roundtrip |
| | `test_load_missing_file` | Missing file handled |
| | `test_invalid_json_recovery` | Invalid JSON recovered |
| TestCreateRequestCache | `test_create_enabled` | Factory enabled |
| | `test_create_disabled_returns_none` | Factory disabled |
| | `test_create_custom_mode` | Factory custom mode |
| TestParseCacheModeArg | `test_parse_strict` | Parse "strict" |
| | `test_parse_model_only` | Parse "model_only" |
| | `test_parse_model_alias` | "model" alias |
| | `test_parse_any` | Parse "any" |
| | `test_parse_case_insensitive` | Case insensitive |
| | `test_parse_unknown_raises` | Unknown raises error |
| TestHelperFunctions | `test_list_cache_modes` | List modes |
| | `test_get_cache_mode_description` | Get description |
| | `test_get_cache_mode_description_all` | All have descriptions |
| TestEdgeCases | `test_store_line_count_mismatch` | Mismatch rejected |
| | `test_empty_lines` | Empty lines handled |
| | `test_clear_cache` | Clear removes all |
| | `test_hash_consistency` | Same input = same hash |
| | `test_different_content_different_hash` | Diff input = diff hash |

---

## Test Priority Summary

| Category | Tests | Priority | Status |
|----------|-------|----------|--------|
| Existing Modules (Manifest, Modi, Functions, Replication, Config, Dedup, Options) | 198 | HIGH | ✅ IMPLEMENTED |
| Validation | 56 | HIGH | ✅ IMPLEMENTED |
| Conditional Prompts | 34 | MEDIUM | ✅ IMPLEMENTED |
| Logit Bias / Token Banning | 38 | MEDIUM | ✅ IMPLEMENTED |
| Retry Strategies | 47 | MEDIUM | ✅ IMPLEMENTED |
| Request Caching | 48 | MEDIUM | ✅ IMPLEMENTED |
| **Total Implemented** | **421+** | | ✅ |

### Planned Tests

**Note:** Some tests previously marked "Planned" have been implemented:
- Rate Limiter: **70 tests** (dev/test_rate_limiter.py - 752 lines)
- Header-Based Rate Limiter: **36 tests** (dev/test_header_rate_limiter.py - 360 lines)
- Chunk Optimizer: **31 tests** (dev/test_chunk_optimizer.py - 447 lines)  
- Line-by-Line Mode: **15 tests** (dev/test_line_by_line.py - 378 lines)

| Category | Tests | Priority | Depends On | Status |
|----------|-------|----------|------------|--------|
| Rate Limiter | 70 | HIGH | None | ✅ Implemented |
| Header-Based Rate Limiter | 36 | HIGH | None | ✅ Implemented |
| Chunk Optimizer | 31 | MEDIUM | Validation | ✅ Implemented |
| Line-by-Line Mode | 15 | LOW | None | ✅ Implemented |
| API Validator | 27 | HIGH | API Client | Planned |
| Prompt Builder | 9 | MEDIUM | None | Planned |
| API Client | 13 | HIGH | None | Planned |
| Extended Line Tags | 27 | HIGH | Manifest v2.0 | Planned |
| GUI Table View | 52 | MEDIUM | Line Tags, Manifest | Partial |
| Progress Tracker | 12 | LOW | None | Planned |
| Auto Recovery | 18 | HIGH | Validation | Planned |
| Style Presets | 28 | LOW | None | Planned |
| Quote Stripper | 14 | LOW | Validation | Planned |
| Token Chunker | 16 | MEDIUM | None | Planned |
| **Total (New Tests)** | **116** | | | ✅ Implemented |
| **Still Planned** | **216** | | | |

Combined with existing 4208 tests: Comprehensive coverage achieved.

### Implemented Test Details (Previously Planned)


#### dev/test_rate_limiter.py (Implemented - 70 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestRPMLimits | `test_under_limit_allowed` | Under RPM allowed |
| | `test_at_limit_blocked` | At RPM blocked |
| | `test_limit_resets_after_minute` | Resets after 60s |
| | `test_wait_for_slot` | Blocks until slot |
| TestDailyLimits | `test_under_daily_allowed` | Under daily allowed |
| | `test_at_daily_blocked` | At daily blocked |
| | `test_daily_resets_at_midnight` | Resets at midnight |
| | `test_remaining_today` | Remaining count correct |
| TestConcurrency | `test_concurrent_within_limit` | Parallel OK within RPM |
| | `test_concurrent_exceeds_limit` | Blocks excess parallel |
| | `test_slot_release` | Slots released after completion |
| TestModelConfigs | `test_gemini_free_limits` | Gemini free limits correct |
| | `test_gpt4_limits` | GPT-4 limits correct |
| | `test_local_unlimited` | Local has high limits |
| | `test_custom_model_defaults` | Unknown model defaults |
| TestPersistence | `test_usage_persists` | Usage survives restart |
| | `test_load_today_usage` | Today's usage loaded |
| | `test_stale_usage_cleared` | Old day's usage cleared |
| TestEstimation | `test_estimate_completion` | ETA calculated |
| | `test_estimate_with_daily_limit` | Daily limit in ETA |
| | `test_multi_day_split` | Split over days detected |
| TestThrottling | `test_429_backoff` | 429 triggers backoff |

#### dev/test_chunk_optimizer.py (Implemented - 31 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestErrorTracking | `test_track_empty_response` | Empty counted |
| | `test_track_batch_retry` | Retry counted |
| | `test_track_timeout` | Timeout counted |
| | `test_error_rate_calculation` | Rate calculated |
| TestChunkAdjustment | `test_under_threshold_no_change` | Low error no change |
| | `test_threshold_triggers_reduction` | 20% triggers reduce |
| | `test_min_requests_required` | Need 7 before adjust |
| | `test_reduction_factor_applied` | 25% reduction |
| | `test_minimum_chunk_floor` | Floor at 10 lines |
| TestRecovery | `test_success_streak_resets` | 10 successes reset |
| | `test_partial_streak_no_reset` | Partial streak keeps |
| TestPerModel | `test_optimal_per_model` | Per-model tracking |
| | `test_persist_optimal` | Optimal persists |
| TestIntegration | `test_full_adjustment_cycle` | Full reduce/recover |
| | `test_multiple_adjustments` | Can reduce multiple times |

*Note: Actual implementation has 31 tests (447 lines). Additional tests cover OptimizerConfig, OptimizerStats, BatchResult, and factory functions.*

#### dev/test_progress_tracker.py (Planned - 12 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestProgressState | `test_initial_state` | Initial values correct |
| | `test_update_lines` | Line count updates |
| | `test_percentage_calculation` | Percentage correct |
| | `test_eta_calculation` | ETA from rate |
| TestCLIDisplay | `test_format_progress_bar` | Bar format correct |
| | `test_format_file_counter` | File counter format |
| | `test_format_batch_info` | Batch info format |
| | `test_non_tty_fallback` | Simple for non-TTY |
| TestTokenTracking | `test_running_total` | Token total tracked |
| | `test_cost_estimation` | Cost calculated |
| TestCompletion | `test_complete_state` | Completion detected |
| | `test_summary_output` | Summary format correct |

#### dev/test_auto_recovery.py (Planned - 18 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestSpeakerRecovery | `test_speaker_colon_missing` | Add colon after speaker |
| | `test_speaker_bracket_mismatch` | Fix 【 】 brackets |
| | `test_speaker_from_context` | Extract from merge |
| | `test_speaker_unknown_fallback` | Keep original if unclear |
| TestCodeRecovery | `test_code_untranslated` | Restore untranslated \<code> |
| | `test_code_partial_damage` | Fix partial damage |
| | `test_code_escaped` | Handle escaped codes |
| | `test_code_from_source` | Match to source line |
| TestBrRecovery | `test_br_missing` | Restore missing \<br> |
| | `test_br_extra` | Remove extra \<br> |
| | `test_br_escaped` | Handle \&lt;br\&gt; |
| | `test_br_combined` | Multiple fixes together |
| TestCountMismatch | `test_empty_line_fill` | Fill from context |
| | `test_extra_line_merge` | Merge split lines |
| | `test_split_detection` | Detect split point |
| TestRecoveryResult | `test_result_success` | Success result correct |
| | `test_result_partial` | Partial recovery marked |
| | `test_result_failed` | Failed result correct |
| | `test_requires_retry` | Flags retry needed |

#### dev/test_retry_strategies.py (Planned - 22 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestRetryMode | `test_mode_enum_values` | Enum values correct |
| | `test_default_mode` | Default is emphasis |
| | `test_mode_from_string` | Parse CLI arg |
| TestEmphasisMode | `test_emphasis_prompt` | Prompt enhanced |
| | `test_emphasis_full_batch` | Retries full batch |
| | `test_emphasis_formatting_note` | Format note added |
| | `test_emphasis_speaker_note` | Speaker note added |
| | `test_emphasis_max_attempts` | Respects max retries |
| TestInContextMode | `test_context_selection` | Selects neighbor lines |
| | `test_context_window_size` | Window configurable |
| | `test_context_already_translated` | Uses existing TL |
| | `test_context_maintains_anchors` | Anchors preserved |
| | `test_context_quality_prompt` | Quality prompt used |
| TestConsolidateMode | `test_reduce_batch_size` | Batch halved |
| | `test_consolidate_prompt` | Care prompt added |
| | `test_consolidate_min_batch` | Min batch 1 line |
| | `test_consolidate_progressive` | Further reduces on fail |
| TestRetryResult | `test_result_success` | Success result |
| | `test_result_partial` | Partial success |
| | `test_result_exhausted` | All attempts failed |
| TestModeSelection | `test_error_type_suggests_mode` | Error → mode mapping |
| | `test_cli_override` | CLI forces mode |
| | `test_fallback_chain` | Fallback to next mode |

#### dev/test_line_by_line.py (Implemented - 15 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestLineByLineMode | `test_flag_enables` | --single-line works |
| | `test_batch_size_one` | Batch size forced to 1 |
| | `test_prompt_simple` | Uses simple prompt |
| | `test_no_context_sent` | No neighbor context |
| TestSimplePrompt | `test_prompt_minimal` | Minimal instructions |
| | `test_prompt_target_lang` | Target lang included |
| | `test_prompt_source_lang` | Source lang if known |
| | `test_prompt_glossary` | Glossary still applies |
| TestErrorIsolation | `test_error_affects_one` | Error isolated to line |
| | `test_retry_single` | Retries one line |
| | `test_continue_on_fail` | Others continue |
| TestPerformance | `test_parallel_requests` | Can parallelize |
| | `test_rate_limit_respected` | RPM honored |
| TestProgressTracking | `test_progress_per_line` | Progress updates per line |
| | `test_eta_accurate` | ETA based on line rate |

*Note: Actual implementation has 15 tests (378 lines) covering line-by-line translation mode.*

### Still Planned Test Details

#### dev/test_style_presets.py (78 tests)

Translation style preset system tests for built-in presets, custom loading, and combining.

| Class | Test | Purpose |
|-------|------|---------|
| TestStyleCategory | `test_time_period_value` | TIME_PERIOD enum value |
| | `test_cultural_value` | CULTURAL enum value |
| | `test_genre_value` | GENRE enum value |
| | `test_character_value` | CHARACTER enum value |
| | `test_dialect_value` | DIALECT enum value |
| TestFormality | `test_very_formal_value` | VERY_FORMAL enum value |
| | `test_formal_value` | FORMAL enum value |
| | `test_neutral_value` | NEUTRAL enum value |
| | `test_casual_value` | CASUAL enum value |
| | `test_very_casual_value` | VERY_CASUAL enum value |
| TestHonorificHandling | `test_keep_value` | KEEP enum value |
| | `test_localize_value` | LOCALIZE enum value |
| | `test_remove_value` | REMOVE enum value |
| TestStylePreset | `test_minimal_preset` | Required fields only |
| | `test_full_preset` | All fields populated |
| | `test_to_prompt_text_basic` | Basic prompt text generation |
| | `test_to_prompt_text_with_instructions` | Includes style instructions |
| | `test_to_prompt_text_with_vocabulary` | Includes vocabulary notes |
| | `test_to_prompt_text_with_avoid_list` | Includes avoid list |
| | `test_to_prompt_text_with_examples` | Includes example phrases |
| | `test_to_prompt_text_honorific_keep_note` | Note for keep honorifics |
| | `test_to_prompt_text_honorific_remove_note` | Note for remove honorifics |
| | `test_to_dict` | Dict serialization |
| | `test_from_dict` | Dict deserialization |
| TestBuiltinPresets | `test_archaic_english_exists` | archaic_english preset |
| | `test_victorian_exists` | victorian preset |
| | `test_modern_casual_exists` | modern_casual preset |
| | `test_british_english_exists` | british_english preset |
| | `test_american_english_exists` | american_english preset |
| | `test_formal_japanese_exists` | formal_japanese preset |
| | `test_formal_japanese_keeps_honorifics` | formal_japanese keeps honorifics |
| | `test_casual_japanese_removes_honorifics` | casual_japanese removes honorifics |
| | `test_fantasy_medieval_exists` | fantasy_medieval preset |
| | `test_fantasy_eastern_exists` | fantasy_eastern preset |
| | `test_noir_detective_exists` | noir_detective preset |
| | `test_romance_flowery_exists` | romance_flowery preset |
| | `test_horror_gothic_exists` | horror_gothic preset |
| | `test_noble_aristocrat_exists` | noble_aristocrat preset |
| | `test_pirate_nautical_exists` | pirate_nautical preset |
| | `test_robot_mechanical_exists` | robot_mechanical preset |
| | `test_all_presets_have_descriptions` | All have descriptions |
| | `test_all_presets_have_categories` | All have categories |
| | `test_minimum_preset_count` | Minimum 27 presets |
| TestStylePresetManager | `test_init_without_custom_dir` | Manager initialization |
| | `test_get_builtin_preset` | Get builtin preset |
| | `test_get_preset_case_insensitive` | Case insensitive lookup |
| | `test_get_preset_unknown_returns_none` | Unknown returns None |
| | `test_list_presets_all` | List all presets |
| | `test_list_presets_by_category` | List by category |
| | `test_list_preset_names` | List preset names |
| | `test_combine_single_preset` | Combine single preset |
| | `test_combine_multiple_presets` | Combine multiple presets |
| | `test_combine_presets_merges_vocabulary` | Vocabulary merging |
| | `test_combine_presets_empty_list_returns_none` | Empty list returns None |
| | `test_combine_presets_invalid_names_returns_none` | Invalid names returns None |
| TestStylePresetManagerCustomPresets | `test_load_custom_preset` | Load custom preset |
| | `test_custom_preset_takes_priority` | Custom overrides builtin |
| | `test_nonexistent_custom_dir` | Nonexistent dir OK |
| TestGetStylePreset | `test_get_existing_preset` | Get existing preset |
| | `test_get_preset_case_insensitive` | Case insensitive |
| | `test_get_nonexistent_preset` | Nonexistent returns None |
| TestListStylePresets | `test_returns_sorted_list` | Sorted list |
| | `test_contains_known_presets` | Contains known presets |
| TestListPresetsByCategory | `test_returns_dict` | Returns dict |
| | `test_categories_present` | Categories present |
| | `test_presets_in_correct_category` | Correct categorization |
| TestParseStylePresetArg | `test_parse_single_preset` | Parse single preset |
| | `test_parse_multiple_presets` | Parse comma-separated |
| | `test_parse_with_spaces` | Handles spaces |
| | `test_parse_empty_string` | Empty string |
| | `test_parse_converts_to_lowercase` | Lowercase conversion |
| TestGetPresetDescription | `test_get_existing_description` | Get description |
| | `test_get_nonexistent_description` | Nonexistent returns empty |
| TestCreateStyleManager | `test_create_without_custom_dir` | Create without dir |
| | `test_create_with_custom_dir` | Create with custom dir |
| TestEdgeCases | `test_preset_with_empty_fields` | Empty fields OK |
| | `test_preset_roundtrip` | Dict roundtrip |
| | `test_combine_deduplicates_vocabulary` | Dedupe vocabulary |

#### dev/test_rate_limiter.py (70 tests)

Rate limiting system tests for API request management and usage tracking.

| Class | Test | Purpose |
|-------|------|---------|
| TestRateLimitEnums | `test_rate_limit_type_values` | RateLimitType enum values |
| | `test_rate_limit_action_values` | RateLimitAction enum values |
| TestModelRateLimits | `test_default_values` | Default rate limits |
| | `test_custom_values` | Custom rate limits |
| | `test_to_dict` | Dict serialization |
| | `test_from_dict` | Dict deserialization |
| | `test_from_dict_with_extra_keys` | Handles extra keys |
| TestUsageRecord | `test_default_values` | Default usage values |
| | `test_custom_values` | Custom usage values |
| | `test_reset` | Reset usage to zero |
| TestRateLimitStats | `test_default_values` | Default stats values |
| | `test_custom_values` | Custom stats values |
| | `test_percent_used_calculations` | Percentage calculations |
| TestRateLimitCheckResult | `test_allow_result` | Allow action result |
| | `test_wait_result` | Wait action result |
| | `test_deny_result` | Deny action result |
| TestRateLimiterConfig | `test_default_config` | Default configuration |
| | `test_custom_persistence_path` | Custom file path |
| | `test_persistence_disabled` | Disable persistence |
| TestDefaultModelLimits | `test_gemini_flash_limits` | Gemini Flash limits |
| | `test_gemini_pro_limits` | Gemini Pro limits |
| | `test_gpt4o_limits` | GPT-4o limits |
| | `test_claude_limits` | Claude limits |
| | `test_local_models_unlimited` | Local models unlimited |
| TestRateLimiterInit | `test_basic_init` | Basic initialization |
| | `test_init_with_custom_config` | Custom config init |
| | `test_init_creates_default_limits` | Default limits created |
| TestGetModelLimits | `test_get_known_model` | Get known model limits |
| | `test_get_unknown_model_prefix_match` | Prefix matching |
| | `test_get_unknown_model_default` | Unknown uses default |
| | `test_empty_model_name` | Empty name handling |
| TestSetModelLimits | `test_set_new_limits` | Set new limits |
| | `test_override_existing_limits` | Override existing |
| TestCheckRateLimit | `test_allow_under_limit` | Allow under limit |
| | `test_deny_rpm_exceeded` | Deny RPM exceeded |
| | `test_deny_tpm_exceeded` | Deny TPM exceeded |
| | `test_wait_when_close_to_limit` | Wait near limit |
| | `test_allow_with_estimated_tokens` | Allow with estimation |
| | `test_deny_daily_limit` | Deny daily limit |
| TestRecordRequest | `test_record_updates_rpm` | Updates RPM count |
| | `test_record_updates_tokens` | Updates token count |
| | `test_daily_usage_tracked` | Daily usage tracked |
| | `test_record_multiple_models` | Multiple models tracked |
| TestGetStats | `test_stats_reflect_usage` | Stats reflect usage |
| | `test_stats_no_usage` | Stats when no usage |
| TestResetDailyUsage | `test_reset_clears_daily` | Reset clears daily |
| | `test_reset_specific_model` | Reset specific model |
| | `test_reset_all_models` | Reset all models |
| TestEstimateCapacity | `test_basic_estimate` | Basic estimation |
| | `test_estimate_with_rate_limits` | Estimate with limits |
| | `test_estimate_respects_daily_limit` | Respects daily limit |
| TestConcurrentRequests | `test_acquire_slot_succeeds` | Acquire slot success |
| | `test_acquire_at_max_returns_false` | Max concurrent fails |
| | `test_release_slot` | Release slot |
| | `test_concurrent_limit_enforced` | Concurrent enforced |
| TestSlidingWindow | `test_window_clears_old_requests` | Old requests cleared |
| | `test_window_respects_minute_boundary` | Minute boundary |
| TestPersistence | `test_save_creates_file` | Save creates file |
| | `test_load_restores_usage` | Load restores usage |
| | `test_load_nonexistent_file` | Nonexistent file OK |
| | `test_persistence_disabled` | Disabled persistence |
| TestFactoryFunctions | `test_create_rate_limiter` | Create rate limiter |
| | `test_create_with_custom_path` | Create with path |
| | `test_get_model_limits_helper` | Get limits helper |
| | `test_list_known_models` | List known models |
| TestEdgeCases | `test_very_high_token_estimate` | High token estimate |
| | `test_zero_rpm_limit` | Zero RPM limit |
| | `test_rapid_requests` | Rapid requests |
| | `test_model_family_inference` | Model family inference |

#### dev/test_header_rate_limiter.py (36 tests)

Header-based rate limiter tests covering duration parsing, per-model counters,
thread safety, monotonic timer usage, and custom provider configuration.

| Class | Test | Purpose |
|-------|------|---------|
| TestParseResetDuration | `test_plain_seconds` | Plain numeric seconds |
| | `test_seconds_suffix` | "1s", "30s" format |
| | `test_minutes_and_seconds` | "6m0s", "1m30s" format |
| | `test_hours_minutes_seconds` | "1h2m3s" format |
| | `test_milliseconds` | "200ms" format |
| | `test_combined_with_millis` | "1s200ms" format |
| | `test_empty_string` | Empty/whitespace input |
| | `test_invalid_string` | Non-parseable input |
| | `test_whitespace_stripped` | Leading/trailing whitespace |
| TestModelWindowState | `test_defaults` | Default dataclass values |
| TestProviderRateLimitConfig | `test_openai_defaults` | OpenAI config values |
| | `test_custom_provider` | Custom header names |
| TestHeaderBasedRateLimiter | `test_set_and_get_limits` | Set/get RPM/TPM |
| | `test_unknown_model_returns_zero_limits` | Unknown model handled |
| | `test_pre_request_increments_counters` | Counter increment |
| | `test_pre_request_multiple` | Multiple increments |
| | `test_unlimited_model_never_blocks` | Unlimited pass-through |
| | `test_request_limit_blocks` | RPM wait enforcement |
| | `test_token_limit_blocks` | TPM wait enforcement |
| | `test_update_limits_from_headers` | Header-driven limit update |
| | `test_update_reset_timing` | Reset timing from headers |
| | `test_empty_headers_ignored` | Empty/None headers safe |
| | `test_case_insensitive_headers` | Case-insensitive keys |
| | `test_counters_reset_after_window` | Auto-reset after window |
| | `test_reset_model` | Manual counter reset |
| | `test_per_model_isolation` | Independent model tracking |
| | `test_max_wait_exceeded_proceeds` | Safety valve timeout |
| | `test_get_stats_unknown_model` | Stats for unknown model |
| TestThreadSafety | `test_concurrent_pre_request` | 10 threads × 100 requests |
| | `test_concurrent_update_from_headers` | 5 threads × 50 updates |
| TestCustomProviderConfig | `test_custom_header_names` | Custom header integration |
| TestMonotonicTimer | `test_reset_uses_monotonic` | Monotonic timer verification |
| TestParseDurationEdgeCases | `test_minutes_only` | "5m" format |
| | `test_hours_only` | "2h" format |
| | `test_fractional_seconds` | "1.5s" format |
| | `test_zero` | "0s" and "0" |

#### dev/test_local_llm.py (63 tests)

Local LLM integration tests for server detection, health checking, and error handling.

| Class | Test | Purpose |
|-------|------|---------|
| TestLocalLLMProvider | `test_lmstudio_value` | LM Studio enum value |
| | `test_ollama_value` | Ollama enum value |
| | `test_text_gen_webui_value` | text-gen-webui enum value |
| | `test_generic_value` | Generic enum value |
| TestLocalServerInfo | `test_default_values` | Default dataclass values |
| | `test_custom_values` | Custom values set correctly |
| TestModelInfo | `test_default_values` | ModelInfo defaults |
| | `test_from_openai_model` | Parse OpenAI format |
| | `test_from_openai_model_minimal` | Parse minimal data |
| | `test_from_openai_model_empty` | Handle empty data |
| TestDefaultPorts | `test_lmstudio_port` | LM Studio port 1234 |
| | `test_ollama_port` | Ollama port 11434 |
| | `test_text_gen_webui_ports` | text-gen-webui ports |
| | `test_generic_includes_common_ports` | Generic has all ports |
| TestCheckPortOpen | `test_closed_port` | Closed port returns False |
| | `test_invalid_host` | Invalid host returns False |
| | `test_open_port_mocked` | Open port returns True |
| | `test_socket_error` | Socket error handled |
| TestInferProvider | `test_infer_ollama_by_port` | Infer Ollama from port |
| | `test_infer_lmstudio_by_port` | Infer LM Studio from port |
| | `test_infer_text_gen_by_port` | Infer text-gen from port |
| | `test_infer_ollama_by_model_format` | Infer from model:tag |
| | `test_infer_lmstudio_by_gguf` | Infer from GGUF model |
| | `test_infer_generic_fallback` | Fallback to generic |
| TestCheckServerHealth | `test_healthy_server_openai_format` | OpenAI format response |
| | `test_healthy_server_ollama_format` | Ollama format response |
| | `test_connection_refused` | Handle connection refused |
| | `test_timeout` | Handle timeout |
| | `test_404_with_fallback` | 404 with fallback check |
| | `test_invalid_json` | Invalid JSON handled |
| | `test_url_normalization` | URL normalized correctly |
| TestDiscoverModels | `test_healthy_server_returns_models` | Returns models list |
| | `test_unhealthy_server_returns_empty` | Empty for unhealthy |
| TestGetLocalErrorHelp | `test_connection_refused_message` | Helpful refused message |
| | `test_timeout_message` | Helpful timeout message |
| | `test_ssl_error_message` | SSL error guidance |
| | `test_404_message` | 404 troubleshooting |
| | `test_401_message` | Auth error guidance |
| | `test_generic_error_message` | Generic error help |
| TestGetProviderSetupInstructions | `test_lmstudio_instructions` | LM Studio setup |
| | `test_ollama_instructions` | Ollama setup |
| | `test_text_gen_webui_instructions` | text-gen-webui setup |
| | `test_generic_instructions` | Generic server setup |
| TestFormatServerStatus | `test_no_servers` | No servers message |
| | `test_healthy_server` | Healthy server display |
| | `test_unhealthy_server` | Unhealthy server error |
| | `test_many_models_truncated` | Model list truncated |
| TestIsLocalUrl | `test_localhost` | localhost is local |
| | `test_127_0_0_1` | 127.0.0.1 is local |
| | `test_192_168_x_x` | Private IP is local |
| | `test_10_x_x_x` | 10.x.x.x is local |
| | `test_openai_not_local` | Public URLs not local |
| | `test_empty_url` | Empty URL not local |
| TestCreateLocalHealthChecker | `test_no_servers` | No servers found |
| | `test_healthy_server` | Healthy server found |
| | `test_unhealthy_server` | Only unhealthy found |
| TestDetectLocalServers | `test_finds_open_ports` | Finds open ports |
| | `test_no_open_ports` | No ports open |
| | `test_deduplicates_ports` | Ports not duplicated |
| TestEdgeCases | `test_server_info_immutable_models` | Models list mutable |
| | `test_model_info_defaults` | Sensible defaults |
| | `test_health_check_measures_time` | Response time measured |
| | `test_local_url_case_insensitive` | URL check case-insensitive |

#### dev/test_lmstudio_live.py (Live Integration Test)

Live integration test for LM Studio server at `http://127.0.0.1:1234`.
Requires LM Studio running with a model loaded. Tests actual API connectivity.

| Test | Purpose |
|------|---------|
| `test_server_health` | Verify LM Studio server responds on port 1234 |
| `test_model_discovery` | List models via `/v1/models` endpoint |
| `test_chat_completion` | Send a basic chat request, measure tok/s |
| `test_json_schema_mode` | Verify `json_schema` response format works |
| `test_openai_sdk_compat` | Verify OpenAI SDK compatibility |

#### dev/_test_backend_lmstudio.py (Backend Integration Test)

End-to-end backend test using `APIClient` with `provider="lmstudio"`.
Validates the full translation pipeline against a live LM Studio server.

| Test | Purpose |
|------|---------|
| `test_api_client_init` | Initialize APIClient with lmstudio provider |
| `test_is_local_provider` | `is_local_provider()` returns True |
| `test_translate_chunk_json_schema` | `_translate_chunk()` with `json_schema` format |
| `test_code_marker_preservation` | VN code markers preserved in translation |
| `test_model_translation` | `test_model_translation()` passes 6/6 checks |

#### dev/_test_gui_flow.py (GUI Flow Validation Test)

Non-GUI test that validates all components needed for the GUI LM Studio flow.

| Test | Purpose |
|------|---------|
| `test_key_save_load` | Save/load lmstudio key in API.ini |
| `test_api_connection` | `test_api_connection()` succeeds |
| `test_api_providers_registry` | lmstudio in `API_PROVIDERS` |
| `test_model_discovery` | `discover_models()` returns server models |
| `test_provider_detection` | `is_local_provider()` for all local types |
| `test_provider_presets` | LM Studio preset in `PROVIDER_PRESETS` |

#### dev/test_postprocess.py (79 tests)

Post-process recovery suite tests for fixing translation structural issues.

| Class | Test | Purpose |
|-------|------|---------|
| TestRecoveryType | `test_all_recovery_types_exist` | All enum values present |
| | `test_recovery_type_values` | Values match strings |
| TestRecoveryAction | `test_all_actions_exist` | All actions present |
| | `test_action_values` | Values match strings |
| TestRecoveryIssue | `test_default_values` | Defaults correct |
| | `test_full_initialization` | All fields set |
| TestRecoveryResult | `test_default_values` | Empty result valid |
| | `test_had_issues_property` | Property correct |
| | `test_recovery_count_property` | Count correct |
| TestBatchRecoveryResult | `test_default_values` | Empty batch valid |
| | `test_add_result` | Results accumulate |
| | `test_add_result_with_retry` | Retry tracked |
| TestRecoveryStats | `test_default_values` | Empty stats valid |
| | `test_record_issue` | Issue recorded |
| | `test_record_issue_not_recovered` | Unrecovered tracked |
| | `test_get_recovery_rate` | Rate calculated |
| TestNormalizePlaceholder | `test_basic_normalization` | Basic case fixed |
| | `test_with_index` | Index preserved |
| | `test_extra_spaces` | Spaces removed |
| | `test_missing_underscores` | Underscores added |
| | `test_preserve_case` | Case optionally kept |
| TestExtractPlaceholdersOrdered | `test_no_placeholders` | Empty returns empty |
| | `test_single_placeholder` | Single found |
| | `test_multiple_placeholders` | Multiple ordered |
| | `test_placeholder_with_index` | Index parsed |
| | `test_case_insensitive` | Case ignored |
| TestRecoverPlaceholderCase | `test_no_change_needed` | Correct unchanged |
| | `test_lowercase_recovery` | Lowercase fixed |
| | `test_mixed_case_recovery` | Mixed case fixed |
| | `test_multiple_placeholders` | Multiple fixed |
| | `test_no_match_in_originals` | Unknown ignored |
| TestRecoverMangledPlaceholders | `test_extra_spaces` | Spaces fixed |
| | `test_translated_placeholder` | Translated handled |
| TestRecoverMissingPlaceholders | `test_no_missing` | None missing OK |
| | `test_missing_placeholder` | Missing inserted |
| | `test_multiple_missing` | Multiple inserted |
| TestNormalizePlaceholderWhitespace | `test_no_change_needed` | Clean unchanged |
| | `test_internal_whitespace` | Internal fixed |
| TestCheckBracketBalance | `test_balanced_brackets` | Balanced detected |
| | `test_unbalanced_opening` | Opening detected |
| | `test_unbalanced_closing` | Closing detected |
| | `test_nested_brackets` | Nested handled |
| | `test_japanese_brackets` | Japanese handled |
| TestRecoverBracketBalance | `test_no_recovery_needed` | Balanced OK |
| | `test_missing_closing_bracket` | Closing inserted |
| TestCheckQuoteBalance | `test_balanced_quotes` | Balanced OK |
| | `test_unbalanced_opening_quote` | Opening detected |
| | `test_curly_quotes` | Curly pairs work |
| TestRecoverQuoteBalance | `test_no_recovery_needed` | Balanced OK |
| TestRecoverLine | `test_no_recovery_needed` | Clean unchanged |
| | `test_placeholder_case_recovery` | Case fixed |
| | `test_missing_placeholder_recovery` | Missing inserted |
| | `test_disable_placeholder_recovery` | Disabled works |
| | `test_disable_bracket_recovery` | Disabled works |
| TestRecoverBatch | `test_empty_batch` | Empty handled |
| | `test_single_line_batch` | Single line works |
| | `test_multiple_lines` | Batch works |
| | `test_mismatched_lengths` | Length mismatch OK |
| TestPostProcessManager | `test_initialization` | Default config |
| | `test_custom_initialization` | Custom config |
| | `test_process_line` | Line processed |
| | `test_process_batch` | Batch processed |
| | `test_get_stats` | Stats returned |
| | `test_reset_stats` | Stats reset |
| | `test_get_recovery_summary` | Summary complete |
| TestFactoryFunctions | `test_create_postprocess_manager` | Factory works |
| | `test_create_postprocess_manager_with_options` | Options passed |
| | `test_get_recovery_type_description` | Descriptions work |
| | `test_list_recovery_types` | All listed |
| TestEdgeCases | `test_empty_strings` | Empty handled |
| | `test_whitespace_only` | Whitespace OK |
| | `test_unicode_text` | Unicode works |
| | `test_multiple_same_placeholders` | Duplicates fixed |
| | `test_nested_brackets` | Nested handled |
| | `test_mixed_bracket_types` | Mixed types work |
| | `test_long_text` | Long text works |
| TestIntegration | `test_combined_recovery` | Multiple types |
| | `test_placeholder_only_recovery` | Only placeholders |
| | `test_full_workflow` | Manager workflow |

#### dev/test_quote_stripper.py (Planned - 14 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestQuoteDetection | `test_detect_double_quotes` | Detects "..." format |
| | `test_detect_single_quotes` | Detects '...' format |
| | `test_detect_curly_quotes` | Detects "..." format |
| | `test_detect_jp_brackets` | Detects 「...」format |
| | `test_no_quotes` | Returns None for no quotes |
| TestQuoteStripping | `test_strip_double_quotes` | Strips "..." correctly |
| | `test_strip_speaker_format` | Strips Speaker: "..." |
| | `test_preserve_inner_quotes` | Keeps quotes inside |
| | `test_preserve_escaped` | Keeps escaped quotes |
| | `test_non_speaker_unchanged` | Non-speaker lines unchanged |
| TestQuoteRestoration | `test_restore_double_quotes` | Restores "..." correctly |
| | `test_restore_matches_original` | Same quote style restored |
| | `test_restore_different_style` | Handles style change |
| TestTokenSavings | `test_count_savings` | Token savings calculated |

#### dev/test_token_chunker.py (Planned - 16 tests)

| Class | Test | Purpose |
|-------|------|---------|
| TestTokenCounting | `test_count_single_line` | Single line counted |
| | `test_count_multiple_lines` | Multiple lines summed |
| | `test_cache_hit` | Cached values reused |
| | `test_empty_line` | Empty line = 0 tokens |
| TestLineChunking | `test_chunk_by_lines` | Lines mode works |
| | `test_chunk_exact_fit` | Exact line count fits |
| | `test_chunk_overflow` | Extra lines new chunk |
| TestTokenChunking | `test_chunk_by_tokens` | Token mode works |
| | `test_token_limit_split` | Splits at token limit |
| | `test_single_long_line` | Long line own chunk |
| TestHybridChunking | `test_hybrid_lines_first` | Lines limit triggers |
| | `test_hybrid_tokens_first` | Tokens limit triggers |
| | `test_hybrid_balanced` | Both limits balanced |
| TestChunkConfig | `test_available_tokens` | Available calculated |
| | `test_system_prompt_reserve` | Reserves prompt tokens |
| TestEstimation | `test_estimate_chunks` | Chunk count estimated |

---

### dev/test_html.py (64 tests)

HTML file format handler tests for formats/html.py module.

#### TestConstants (8 tests)

| Test | Purpose |
|------|---------|
| `test_skip_tags_contains_script` | SKIP_TAGS includes script |
| `test_skip_tags_contains_style` | SKIP_TAGS includes style |
| `test_inline_tags_contains_b` | INLINE_TAGS includes b (bold) |
| `test_inline_tags_contains_i` | INLINE_TAGS includes i (italic) |
| `test_inline_tags_contains_span` | INLINE_TAGS includes span |
| `test_inline_tags_contains_a` | INLINE_TAGS includes a (anchor) |
| `test_block_tags_contains_div` | BLOCK_TAGS includes div |
| `test_block_tags_contains_p` | BLOCK_TAGS includes p (paragraph) |

#### TestInlineTag (3 tests)

| Test | Purpose |
|------|---------|
| `test_create_inline_tag` | Create InlineTag with basic attributes |
| `test_inline_tag_with_attrs` | InlineTag with HTML attributes |
| `test_closing_inline_tag` | Create closing InlineTag |

#### TestTextBlock (2 tests)

| Test | Purpose |
|------|---------|
| `test_create_text_block` | Create TextBlock with basic attributes |
| `test_text_block_with_inline_tags` | TextBlock with inline tags list |

#### TestHtmlHandlerInit (7 tests)

| Test | Purpose |
|------|---------|
| `test_handler_format_id` | Handler has format_id "html" |
| `test_handler_extensions` | Supports .html, .htm, .xhtml |
| `test_handler_description` | Has description with "HTML" |
| `test_handler_supports_pairs` | Does not support pairs |
| `test_handler_skip_pre_default` | skip_pre defaults to True |
| `test_handler_preserve_whitespace_default` | preserve_whitespace defaults to False |
| `test_handler_custom_init` | Custom init options work |

#### TestBasicExtraction (4 tests)

| Test | Purpose |
|------|---------|
| `test_extract_simple_text` | Extract text from simple HTML |
| `test_extract_paragraph_text` | Extract paragraph text |
| `test_extract_returns_list` | extract() returns list |
| `test_extract_preserves_text_content` | Preserves Unicode content |

#### TestInlineTagHandling (5 tests)

| Test | Purpose |
|------|---------|
| `test_extract_with_bold` | Extract text with bold tags |
| `test_extract_with_italic` | Extract text with italic tags |
| `test_extract_with_anchor` | Extract text with anchor tags |
| `test_placeholder_generation` | Placeholders are unique |
| `test_placeholder_format` | Placeholders follow __TAG_N__ format |

#### TestSkipTags (3 tests)

| Test | Purpose |
|------|---------|
| `test_skip_script_content` | Script content not extracted |
| `test_skip_style_content` | Style content not extracted |
| `test_extract_visible_content` | Visible content still extracted |

#### TestNestedStructures (2 tests)

| Test | Purpose |
|------|---------|
| `test_extract_nested_paragraphs` | Extract from nested paragraphs |
| `test_extract_list_items` | Extract from list items |

#### TestWhitespaceHandling (2 tests)

| Test | Purpose |
|------|---------|
| `test_normalize_whitespace` | Multiple spaces normalized |
| `test_preserve_whitespace_option` | preserve_whitespace keeps all whitespace |

#### TestInjection (3 tests)

| Test | Purpose |
|------|---------|
| `test_basic_inject` | Basic injection of translated text |
| `test_inject_creates_file` | inject() creates output file |
| `test_inject_line_count_mismatch` | Raises error on line count mismatch |

#### TestMetadata (4 tests)

| Test | Purpose |
|------|---------|
| `test_get_title` | Metadata includes page title |
| `test_get_charset` | Metadata includes charset |
| `test_get_language` | Metadata includes language |
| `test_get_tag_count` | Metadata includes tag count |

#### TestAdvancedHandler (3 tests)

| Test | Purpose |
|------|---------|
| `test_advanced_format_id` | Advanced handler has format_id "html_advanced" |
| `test_advanced_extract` | Advanced handler extracts text |
| `test_advanced_stores_soup` | Stores soup after extraction |

#### TestGetHandlers (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_list` | get_handlers() returns list |
| `test_returns_handlers` | Returns handler instances |
| `test_includes_basic_handler` | Includes HtmlHandler |
| `test_includes_advanced_handler` | Includes HtmlHandlerAdvanced |

#### TestEdgeCases (7 tests)

| Test | Purpose |
|------|---------|
| `test_empty_html` | Handle empty HTML file |
| `test_html_only_whitespace` | Handle whitespace-only HTML |
| `test_malformed_html` | Handle malformed HTML gracefully |
| `test_unicode_content` | Handle Unicode content |
| `test_html_entities` | Handle HTML entities |
| `test_self_closing_tags` | Handle self-closing tags |
| `test_file_not_found` | Handle non-existent file |

#### TestComplexDocuments (3 tests)

| Test | Purpose |
|------|---------|
| `test_rpgmaker_style_html` | RPG Maker-style HTML patterns |
| `test_table_content` | Extracting text from tables |
| `test_deeply_nested_inline` | Deeply nested inline tags |

#### TestIntegration (2 tests)

| Test | Purpose |
|------|---------|
| `test_extract_inject_roundtrip` | Extract -> translate -> inject workflow |
| `test_format_registry_integration` | Integrates with format registry |

#### TestEncoding (2 tests)

| Test | Purpose |
|------|---------|
| `test_utf8_encoding` | UTF-8 encoded file |
| `test_inject_with_encoding` | Inject with specified encoding |

---

### dev/test_auto_tagger.py (122 tests)

Tests for the auto-tagging system (Manifest v2.1). Covers content classification,
status tracking, severity levels, quality scoring, and pattern-based rule matching.

**Test Classes:**

#### TestContentTag (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_tags_exist` | All expected ContentTag values exist |
| `test_unique_values` | Each tag has unique value |
| `test_default_is_unknown` | UNKNOWN is first/default tag |
| `test_all_tags_have_descriptions` | All tags have descriptions |

#### TestStatusTag (3 tests)

| Test | Purpose |
|------|---------|
| `test_all_statuses_exist` | All expected StatusTag values exist |
| `test_unique_values` | Each status has unique value |
| `test_all_statuses_have_descriptions` | All statuses have descriptions |

#### TestSeverityLevel (3 tests)

| Test | Purpose |
|------|---------|
| `test_all_levels_exist` | All expected severity levels exist |
| `test_ordered_values` | Levels ordered 0-4 (TRIVIAL to CRITICAL) |
| `test_all_levels_have_descriptions` | All levels have descriptions |

#### TestLineTag (8 tests)

| Test | Purpose |
|------|---------|
| `test_create_basic` | Basic tag creation with defaults |
| `test_create_with_all_fields` | Tag with all fields specified |
| `test_to_dict_basic` | Basic serialization |
| `test_to_dict_with_value` | Serialization with value |
| `test_to_dict_with_low_confidence` | Serialization with confidence |
| `test_from_dict_basic` | Basic deserialization |
| `test_from_dict_full` | Deserialization with all fields |
| `test_roundtrip` | Serialize and deserialize cycle |

#### TestLineTags (20 tests)

| Test | Purpose |
|------|---------|
| `test_default_values` | Default values are sensible |
| `test_add_tag` | Adding custom tags |
| `test_add_tag_with_params` | Adding tags with all parameters |
| `test_add_flag` | Adding flags |
| `test_add_duplicate_flag` | Duplicate flags deduplicated |
| `test_has_flag` | Checking flag existence |
| `test_get_tag` | Getting custom tags by name |
| `test_remove_tag` | Removing custom tags |
| `test_to_dict_default` | Empty tags serializes to empty dict |
| `test_to_dict_with_content_type` | Serialize non-default content_type |
| `test_to_dict_with_status` | Serialize non-default status |
| `test_to_dict_with_severity` | Serialize non-default severity |
| `test_to_dict_with_quality_score` | Serialize quality_score |
| `test_to_dict_with_custom_tags` | Serialize custom_tags list |
| `test_to_dict_with_flags` | Serialize flags set |
| `test_from_dict_empty` | Deserialize empty dict |
| `test_from_dict_with_content_type` | Deserialize content_type |
| `test_from_dict_invalid_content_type` | Invalid content_type defaults to UNKNOWN |
| `test_from_dict_with_status` | Deserialize status |
| `test_from_dict_invalid_status` | Invalid status defaults to PENDING |
| `test_from_dict_with_severity` | Deserialize severity |
| `test_from_dict_with_flags` | Deserialize flags |
| `test_roundtrip_full` | Full roundtrip with all fields |

#### TestQualityMetrics (13 tests)

| Test | Purpose |
|------|---------|
| `test_default_perfect_score` | Default gives 100 score |
| `test_placeholder_not_preserved` | Missing placeholder -30 points |
| `test_has_untranslated` | Untranslated content -20 points |
| `test_has_repetition` | Repetitive content -15 points |
| `test_bracket_unbalanced` | Unbalanced brackets -10 points |
| `test_extreme_length_ratio_short` | Very short translation -15 |
| `test_extreme_length_ratio_long` | Very long translation -15 |
| `test_moderate_length_ratio` | Moderate difference -10 |
| `test_slight_length_ratio` | Slight difference -5 |
| `test_issues_deduct` | Per-issue -2 points |
| `test_multiple_problems` | Problems stack |
| `test_minimum_score_zero` | Score never below 0 |
| `test_maximum_score_hundred` | Score never above 100 |

#### TestTagRule (6 tests)

| Test | Purpose |
|------|---------|
| `test_basic_rule` | Basic rule creation |
| `test_rule_with_all_fields` | Rule with all fields |
| `test_matches_simple` | Simple pattern matching |
| `test_matches_case_insensitive` | Case-insensitive matching |
| `test_matches_regex` | Complex regex patterns |
| `test_invalid_pattern` | Invalid regex doesn't crash |

#### TestAutoTagger (30 tests)

| Test | Purpose |
|------|---------|
| `test_create_default` | Create with default rules |
| `test_create_with_custom_rules` | Create with custom rules |
| `test_create_without_quality` | Create with quality disabled |
| `test_rules_sorted_by_priority` | Rules sorted by priority |
| `test_analyze_line_unknown` | Unmatched line is UNKNOWN |
| `test_analyze_dialogue_speaker` | Dialogue speaker detection |
| `test_analyze_quoted_text` | Quoted text detection |
| `test_analyze_system_message_jp` | Japanese system message |
| `test_analyze_menu_item_en` | English menu item |
| `test_analyze_placeholder` | Placeholder detection |
| `test_analyze_with_translation` | Quality calculated with translation |
| `test_analyze_quality_disabled` | Quality not calculated when disabled |
| `test_analyze_preserves_existing_tags` | Existing tags preserved |
| `test_detect_patterns_speaker` | Speaker pattern detection |
| `test_detect_patterns_placeholder` | Placeholder pattern detection |
| `test_detect_patterns_markup` | Markup pattern detection |
| `test_detect_patterns_symbols` | Symbol pattern detection |
| `test_detect_patterns_numbers` | Number pattern detection |
| `test_detect_patterns_japanese` | Japanese pattern detection |
| `test_detect_patterns_linebreak` | Linebreak pattern detection |
| `test_quality_placeholder_mismatch` | Quality deduction for placeholder mismatch |
| `test_quality_untranslated` | Quality deduction for untranslated |
| `test_quality_repetition` | Quality deduction for repetition |
| `test_quality_unbalanced_brackets` | Quality deduction for unbalanced brackets |
| `test_quality_low_triggers_review` | Low quality triggers NEEDS_REVIEW |
| `test_analyze_batch` | Batch analysis |
| `test_add_rule` | Adding rules dynamically |
| `test_remove_rule` | Removing rules |
| `test_get_rule` | Getting rules by name |

#### TestFactoryFunctions (9 tests)

| Test | Purpose |
|------|---------|
| `test_create_auto_tagger_default` | Factory with defaults |
| `test_create_auto_tagger_custom` | Factory with custom options |
| `test_get_content_tag_description` | Get content tag description |
| `test_get_content_tag_description_unknown` | Unknown tag fallback |
| `test_get_status_tag_description` | Get status tag description |
| `test_get_severity_description` | Get severity description |
| `test_list_content_tags` | List all content tags |
| `test_list_status_tags` | List all status tags |
| `test_list_severity_levels` | List all severity levels |

#### TestDefaultRules (7 tests)

| Test | Purpose |
|------|---------|
| `test_rules_not_empty` | Default rules exist |
| `test_all_rules_have_names` | All rules have names |
| `test_all_rules_have_patterns` | All rules have patterns |
| `test_all_rules_compile` | All patterns compile |
| `test_unique_rule_names` | All names unique |
| `test_speaker_dialogue_rule` | Speaker dialogue rule works |
| `test_menu_item_rule` | Menu item rule works |
| `test_placeholder_rule` | Placeholder rule works |

#### TestLineEntryIntegration (6 tests)

| Test | Purpose |
|------|---------|
| `test_lineentry_has_tags_field` | LineEntry has tags field |
| `test_lineentry_with_tags` | LineEntry can store LineTags |
| `test_lineentry_to_dict_with_tags` | to_dict serializes tags |
| `test_lineentry_to_dict_empty_tags` | Empty tags not included |
| `test_lineentry_from_dict_with_tags` | from_dict deserializes tags |
| `test_lineentry_roundtrip_with_tags` | Full roundtrip with tags |

#### TestEdgeCases (10 tests)

| Test | Purpose |
|------|---------|
| `test_empty_string_analysis` | Empty string doesn't crash |
| `test_very_long_text` | Very long text handled |
| `test_unicode_text` | Unicode text handled |
| `test_mixed_scripts` | Mixed scripts detected |
| `test_special_characters` | Special characters handled |
| `test_newlines_in_text` | Newlines handled |
| `test_quality_with_empty_original` | Empty original handled |
| `test_quality_with_empty_translation` | Empty translation handled |
| `test_batch_with_empty_list` | Empty batch handled |
| `test_linetags_multiple_flags` | Multiple flags preserved |

---

### dev/test_session_persistence.py (40 tests)

Session persistence tests validating auto-save on close and auto-load on startup.
Added for Release Stabilization task "Ensure Sessions Are Properly Saved & Loaded".
Extended in January 2025 with file restoration and auto-numbered save tests.
**Session 26:** Updated assertions for new tab order (Information=2, Preprocessing=3, Costs=4).

#### TestSessionPersistence (6 tests)

| Test | Purpose |
|------|---------|
| `test_session_save_to_file` | Session state saves to file |
| `test_session_load_from_file` | Session state loads from file |
| `test_session_autosave_path_exists` | Autosave constants defined |
| `test_load_session_from_autosave_missing` | Missing autosave returns None |
| `test_session_dirty_flag` | Dirty flag tracking |
| `test_session_step_data_persists` | Step data survives save/load |

#### TestStepStateSerialization (4 tests)

| Test | Purpose |
|------|---------|
| `test_step_state_basic_serialization` | Basic fields serialize |
| `test_step_state_data_serialization` | Nested data serializes |
| `test_step_state_skipped_flag` | Skipped flag persists |
| `test_step_state_reset` | Reset clears all data |

#### TestAllStepsPersistence (10 tests)

| Test | Purpose |
|------|---------|
| `test_input_step_data_persistence` | Step 0: Input data persists |
| `test_analysis_step_data_persistence` | Step 1: Analysis data persists |
| `test_estimation_step_data_persistence` | Step 2: Estimation data persists |
| `test_information_step_data_persistence` | Step 3: Information data persists |
| `test_preprocessing_step_data_persistence` | Step 4: Preprocessing data persists |
| `test_translation_step_data_persistence` | Step 5: Translation data persists |
| `test_postprocessing_step_data_persistence` | Step 6: Postprocessing data persists |
| `test_wordwrap_step_data_persistence` | Step 8: Wordwrap data persists |
| `test_qa_step_data_persistence` | Step 7: QA data persists |
| `test_output_step_data_persistence` | Step 9: Output data persists |

#### TestManifestAssociation (2 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_path_persistence` | Manifest path persists |
| `test_manifest_path_none` | None manifest handled |

#### TestPresetsPersistence (2 tests)

| Test | Purpose |
|------|---------|
| `test_active_preset_persistence` | Active preset persists |
| `test_preset_definitions_step_order` | Presets use correct step indices |

#### TestStepOrderAfterReorganization (3 tests)

| Test | Purpose |
|------|---------|
| `test_step_definitions_order` | Step order correct after reorg |
| `test_estimation_follows_analysis` | Estimation after Analysis |
| `test_session_state_initializes_with_correct_order` | Session uses correct order |

#### TestCorruptedSessionHandling (3 tests)

| Test | Purpose |
|------|---------|
| `test_load_corrupted_json_fails_gracefully` | Corrupted JSON raises error |
| `test_load_missing_fields_uses_defaults` | Missing fields use defaults |
| `test_autosave_corrupted_returns_none` | Corrupted autosave returns None |

#### TestUndoStackPersistence (2 tests)

| Test | Purpose |
|------|---------|
| `test_undo_stack_limited_serialization` | Only last 10 undo actions saved |
| `test_undo_stack_restored` | Undo stack restored from file |

#### TestInputStepFileRestoration (4 tests)

| Test | Purpose |
|------|---------|
| `test_session_files_metadata_structure` | Files metadata has expected structure |
| `test_session_step_metadata_persistence` | Input step metadata persists through save/load (TASK 71) |
| `test_session_input_metadata_roundtrip` | Input step metadata roundtrip (no all_lines/files) |
| `test_empty_session_input_handled` | Empty Input step data handled gracefully |

#### TestAutoNumberedSessionSaves (4 tests)

| Test | Purpose |
|------|---------|
| `test_session_save_directory_structure` | Sessions use user/sessions/ directory |
| `test_session_filename_pattern` | Filename follows session_state_NNNN.cherrysession pattern |
| `test_next_session_number_calculation` | Next session number calculated correctly |
| `test_session_number_starts_at_one_for_empty_dir` | Numbering starts at 1 for empty directory |

---

### dev/test_gui_v2.py (491 tests)

GUI v2 framework tests validating the new 10-step workflow interface.
All 15 phases complete: Phase 0 (Skeleton), Phase 1 (Input/Extraction), Phase 2 (Table),
Phase 3 (Analysis), Phase 4 (Progress/State), Phase 5 (Preprocessing), Phase 6 (Estimation),
Phase 7 (Translation), Phase 8 (QA), Phase 9 (Postprocessing), Phase 10 (Wordwrap),
Phase 11 (Output), Phase 12 (Information), Phase 13 (Global Options), Phase 14 (Polish).

#### TestThemeColors (5 tests)

| Test | Purpose |
|------|---------|
| `test_color_palette_exists` | ColorPalette dataclass exists |
| `test_theme_is_frozen` | THEME instance is immutable |
| `test_theme_has_required_colors` | All required color fields present |
| `test_no_yellow_or_red_colors` | Design ethos: no yellow/red colors |
| `test_ttk_style_map_structure` | get_ttk_style() returns valid dict |

#### TestHighContrastTheme (Phase 14, 5 tests)

| Test | Purpose |
|------|---------|
| `test_high_contrast_theme_exists` | HIGH_CONTRAST_THEME exists |
| `test_high_contrast_is_frozen` | Immutable high-contrast theme |
| `test_high_contrast_colors_differ_from_pastel` | Different from default |
| `test_high_contrast_has_dark_background` | Dark navy background |
| `test_high_contrast_has_bright_text` | Pure white text |

#### TestThemeMode (Phase 14, 2 tests)

| Test | Purpose |
|------|---------|
| `test_theme_mode_enum_exists` | ThemeMode enum exists |
| `test_theme_mode_values` | Correct enum values |

#### TestThemeSwitching (Phase 14, 4 tests)

| Test | Purpose |
|------|---------|
| `test_get_theme_returns_current` | get_theme() works |
| `test_get_theme_mode_returns_current` | get_theme_mode() works |
| `test_set_theme_to_high_contrast` | Switch to high-contrast |
| `test_set_theme_to_pastel_blue` | Switch back to pastel |

#### TestIconsModule (Phase 14, 5 tests)

| Test | Purpose |
|------|---------|
| `test_icons_dataclass_exists` | Icons dataclass exists |
| `test_icons_is_frozen` | Immutable icons |
| `test_status_icons_exist` | Status icons defined |
| `test_step_icons_exist` | Step icons defined |
| `test_action_icons_exist` | Action icons defined |

#### TestStepIcons (Phase 14, 4 tests)

| Test | Purpose |
|------|---------|
| `test_step_icons_mapping_exists` | STEP_ICONS mapping exists |
| `test_step_icons_has_all_steps` | Icons for all 10 steps |
| `test_get_step_icon_function` | get_step_icon() works |
| `test_get_step_icon_invalid_returns_empty` | Invalid returns empty |

#### TestPresetWorkflows (Phase 14, 5 tests)

| Test | Purpose |
|------|---------|
| `test_preset_definitions_exist` | Presets defined |
| `test_sample_preset` | Sample preset configured |
| `test_dirty_cheap_preset` | Dirty & Cheap preset |
| `test_automatic_luxury_preset` | All steps auto |
| `test_everything_custom_preset` | No auto steps |

#### TestEndToEndWorkflowStructure (Phase 14, 4 tests)

| Test | Purpose |
|------|---------|
| `test_all_step_definitions_exist` | 10 steps defined |
| `test_step_names_are_unique` | Unique step names |
| `test_step_tab_classes_exist` | All tab classes import |
| `test_global_options_dialog_exists` | Dialog imports |

#### TestSampleFileCompatibility (Phase 14, 4 tests)

| Test | Purpose |
|------|---------|
| `test_sample_file_path` | sample.txt exists |
| `test_sample_file_readable` | File is readable |
| `test_sample_file_has_japanese` | Contains Japanese |
| `test_sample_file_has_multiple_lines` | Has 10+ lines |

#### TestSessionState (14 tests)

| Test | Purpose |
|------|---------|
| `test_step_definitions_count` | Exactly 10 workflow steps defined |
| `test_step_definitions_structure` | Each step has (id, name, desc) tuple |
| `test_step_definitions_names` | Step names match spec order |
| `test_step_state_creation` | StepState dataclass works |
| `test_step_state_serialization` | StepState to_dict/from_dict |
| `test_session_state_initialization` | SessionState starts at step 0 |
| `test_session_state_get_step` | get_step_state() returns correct state |
| `test_session_state_mark_done` | mark_done() updates step status |
| `test_session_state_advance_step` | advance_step() increments current_step |
| `test_session_state_advance_at_end` | advance_step() no-op at last step |
| `test_session_state_go_to_step` | go_to_step() navigates directly |
| `test_session_state_serialization` | SessionState to_dict/from_dict |
| `test_get_session_singleton` | get_session() returns same instance |
| `test_reset_session` | reset_session() creates new instance |

#### TestBaseStep (3 tests)

| Test | Purpose |
|------|---------|
| `test_base_step_is_abstract` | BaseStep cannot be instantiated |
| `test_placeholder_step_creation` | PlaceholderStep works correctly |
| `test_placeholder_step_phase_mapping` | PlaceholderStep maps to correct phase |

#### TestAppStructure (4 tests)

| Test | Purpose |
|------|---------|
| `test_app_constants` | App has required constants |
| `test_app_class_exists` | App class is importable |
| `test_progress_tracker_class_exists` | ProgressTracker class exists |
| `test_main_function_exists` | main() entry point exists |

#### TestGuiPackageStructure (5 tests)

| Test | Purpose |
|------|---------|
| `test_gui_init_exports_app` | gui/__init__.py exports App |
| `test_gui_theme_init_exports` | gui/theme exports correctly |
| `test_gui_state_init_exports` | gui/state exports correctly |
| `test_gui_steps_init_exports` | gui/steps exports correctly |
| `test_gui_components_init_exists` | gui/components package exists |

#### TestLegacyGuiPreservation (2 tests)

| Test | Purpose |
|------|---------|
| `test_legacy_gui_file_exists` | functions/gui_legacy.py exists |
| `test_legacy_gui_importable` | Legacy GUI still importable |

#### TestCherryAIPyIntegration (1 test)

| Test | Purpose |
|------|---------|
| `test_main_imports_new_gui` | CherryAI.py uses gui.app |

#### TestLoadedFile (4 tests) - Phase 1

| Test | Purpose |
|------|---------|
| `test_loaded_file_creation` | LoadedFile with required attributes |
| `test_loaded_file_with_manifest` | LoadedFile with manifest path |
| `test_loaded_file_to_dict` | LoadedFile serialization |
| `test_loaded_file_empty_lines` | LoadedFile handles empty lines |

#### TestFormatDetection (2 tests) - Phase 1

| Test | Purpose |
|------|---------|
| `test_format_map_contents` | FORMAT_MAP has expected extensions |
| `test_supported_extensions` | SUPPORTED_EXTENSIONS contains all formats |

#### TestInputExtractionStepClass (5 tests) - Phase 1

| Test | Purpose |
|------|---------|
| `test_input_extraction_step_exists` | InputExtractionStep is importable |
| `test_input_extraction_step_inherits_base` | Inherits from BaseStep |
| `test_input_extraction_step_id` | Has step_id 0 |
| `test_input_extraction_step_name` | Has correct step name |
| `test_steps_package_exports_input_extraction` | Package exports correctly |

#### TestFileExtraction (5 tests) - Phase 1

| Test | Purpose |
|------|---------|
| `test_extract_txt_file` | Extract lines from TXT file |
| `test_extract_csv_file` | Extract lines from CSV file |
| `test_extract_tsv_file` | Extract lines from TSV file |
| `test_extract_json_file` | Extract lines from JSON file |
| `test_extract_with_encoding` | Extract with specific encoding |

#### TestManifestDetection (3 tests) - Phase 1

| Test | Purpose |
|------|---------|
| `test_find_manifest_in_same_dir` | Find manifest in same directory |
| `test_find_manifest_in_manifests_subdir` | Find in manifests/ subdirectory |
| `test_find_manifest_not_found` | Return None when not found |

#### TestInputExtractionIntegration (3 tests) - Phase 1

| Test | Purpose |
|------|---------|
| `test_app_uses_input_extraction_for_step_0` | App uses InputExtractionStep |
| `test_get_loaded_files_empty` | get_loaded_files returns empty initially |
| `test_get_all_lines_empty` | get_all_lines returns empty initially |

#### TestGUILaunch (3 tests) - Phase 1 Bug Prevention

| Test | Purpose |
|------|---------|
| `test_input_extraction_step_builds_ui` | InputExtractionStep builds UI without errors (skip if no Tk) |
| `test_app_initializes_without_error` | App initializes without errors (skip if no Tk) |
| `test_theme_attributes_match_usage` | All THEME attributes used in code exist |

#### TestTableRow (3 tests) - Phase 2

| Test | Purpose |
|------|---------|
| `test_table_row_creation` | TableRow dataclass with basic fields |
| `test_table_row_with_tags` | TableRow with optional tags field |
| `test_table_row_to_dict` | TableRow to_dict() serialization |

#### TestColumnDef (2 tests) - Phase 2

| Test | Purpose |
|------|---------|
| `test_column_def_creation` | ColumnDef with key, title, width |
| `test_column_def_defaults` | ColumnDef default sortable and resizable |

#### TestSharedTable (4 tests) - Phase 2

| Test | Purpose |
|------|---------|
| `test_shared_table_import` | SharedTable importable from gui.components |
| `test_shared_table_set_data` | SharedTable accepts TableRow list |
| `test_shared_table_filter_basic` | SharedTable filter method exists |
| `test_shared_table_clear_data` | SharedTable clear method exists |

#### TestAnalysisStep (4 tests) - Phase 3

| Test | Purpose |
|------|---------|
| `test_analysis_step_exists` | AnalysisStep importable from gui.steps |
| `test_analysis_step_inherits_base` | AnalysisStep extends BaseStep |
| `test_analysis_step_id` | AnalysisStep.step_id == 1 |
| `test_analysis_step_name` | AnalysisStep.step_name correct |

#### TestAnalysisFunctions (4 tests) - Phase 3

| Test | Purpose |
|------|---------|
| `test_run_analysis_on_lines` | Analysis runs on line list |
| `test_language_detection` | Language detection returns dict |
| `test_duplicate_detection` | Duplicate detection works |
| `test_code_pattern_detection` | Code pattern detection works |

#### TestAnalysisIntegration (2 tests) - Phase 3

| Test | Purpose |
|------|---------|
| `test_app_uses_analysis_step_for_step_1` | App uses AnalysisStep for tab 1 |
| `test_analysis_with_sample_file` | Full analysis on sample.txt (skipped if missing) |

#### TestUndoRedo (7 tests) - Phase 4

| Test | Purpose |
|------|---------|
| `test_undo_stack_initially_empty` | Undo stack starts empty |
| `test_redo_stack_initially_empty` | Redo stack starts empty |
| `test_mark_done_creates_undo_action` | Actions push to undo stack |
| `test_undo_reverts_step_status` | Undo restores previous state |
| `test_redo_reapplies_step_status` | Redo reapplies undone action |
| `test_undo_clears_after_new_action` | New action clears redo stack |
| `test_undo_stack_has_max_limit` | Undo stack capped at MAX_UNDO_STACK_SIZE |

#### TestPresets (7 tests) - Phase 4

| Test | Purpose |
|------|---------|
| `test_preset_names_available` | get_preset_names() returns list |
| `test_preset_definitions_exist` | All 4 presets defined |
| `test_preset_has_description` | Each preset has description |
| `test_preset_has_enabled_steps` | Each preset has auto_steps/skip_steps |
| `test_apply_preset_sample` | Sample preset skips correct steps |
| `test_apply_preset_creates_undo` | Preset application is undoable |
| `test_default_preset_is_everything_custom` | Default preset is Everything Custom |

#### TestSkipAndRollback (4 tests) - Phase 4

| Test | Purpose |
|------|---------|
| `test_mark_skipped` | mark_skipped() sets skipped flag |
| `test_skip_creates_undo` | Skip action is undoable |
| `test_rollback_step` | rollback_step() resets to not-started |
| `test_rollback_clears_skipped` | Rollback clears skipped flag |

#### TestAutosave (4 tests) - Phase 4

Note: `test_start_autosave_creates_thread` and `test_stop_autosave_clears_thread` now expect no-op behavior since SessionState autosave was disabled in favor of ManifestManager autosave.

| Test | Purpose |
|------|---------|
| `test_dirty_flag_initially_false` | dirty flag starts False |
| `test_action_sets_dirty_flag` | Actions set dirty flag |
| `test_start_autosave_creates_thread` | Autosave starts background thread |
| `test_stop_autosave_clears_thread` | Autosave thread stops cleanly |

#### TestSessionSaveLoad (3 tests) - Phase 4

| Test | Purpose |
|------|---------|
| `test_save_creates_file` | save_to_file() creates JSON file |
| `test_load_restores_state` | load_from_file() restores session |
| `test_load_clears_dirty_flag` | Loading clears dirty flag |

#### TestProgressTrackerModule (5 tests) - Phase 4

| Test | Purpose |
|------|---------|
| `test_progress_module_exists` | gui/progress.py importable |
| `test_progress_tracker_class_exists` | ProgressTracker class exists |
| `test_step_row_class_exists` | StepRow class exists |
| `test_progress_panel_class_exists` | ProgressPanel class exists |
| `test_progress_tracker_in_app` | App imports ProgressTracker |

#### TestCompletionPercentage (4 tests) - Phase 4

| Test | Purpose |
|------|---------|
| `test_initial_completion_zero` | Initial completion is 0% |
| `test_completion_after_one_step` | Completion increases after step |
| `test_skipped_steps_count_as_complete` | Skipped steps count as done |
| `test_preset_sample_fifty_percent` | Sample preset shows ~50% |

#### TestTableRowSerialization (3 tests) - Data Flow Fixes

| Test | Purpose |
|------|---------|
| `test_table_row_to_dict` | TableRow.to_dict() serializes correctly |
| `test_table_row_from_dict` | TableRow.from_dict() deserializes correctly |
| `test_table_row_roundtrip` | TableRow round-trips through dict |

#### TestStepStateSerialization (2 tests) - Data Flow Fixes

| Test | Purpose |
|------|---------|
| `test_step_state_serializes_table_rows` | StepState handles nested TableRow objects |
| `test_step_state_serializes_paths` | StepState handles Path objects in data |

#### TestSessionDataFlow (2 tests) - Data Flow Fixes

| Test | Purpose |
|------|---------|
| `test_input_step_data_no_longer_stores_all_lines` | Input step data no longer stores all_lines (TASK 71) |
| `test_session_save_load_preserves_step_metadata` | Session save/load preserves Input step metadata |

#### TestManifestMigrationStripsRedundant (7 tests) - TASK 71

| Test | Purpose |
|------|---------|
| `test_strips_all_lines_from_input` | all_lines removed from Input step_data during migration |
| `test_strips_files_from_input` | files removed from Input step_data during migration |
| `test_strips_processed_lines_from_preprocessing` | processed_lines removed from Preprocessing step_data |
| `test_strips_postprocessed_lines_from_postprocessing` | postprocessed_lines removed from Postprocessing step_data |
| `test_no_error_if_keys_absent` | Migration doesn't fail when redundant keys already absent |
| `test_get_all_orig_lines_returns_orig_values` | ManifestManager.get_all_orig_lines() returns lines[].orig |
| `test_get_all_orig_lines_empty_manifest` | get_all_orig_lines returns empty list when no lines |

#### TestLoadedFileSerialization (1 test) - Data Flow Fixes

| Test | Purpose |
|------|---------|
| `test_loaded_file_to_dict` | LoadedFile.to_dict() works correctly |

#### TestPreprocessingStepModule (5 tests) - Phase 5

| Test | Purpose |
|------|---------|
| `test_preprocessing_module_exists` | PreprocessingStep module importable |
| `test_preprocessing_step_class_exists` | PreprocessingStep class exists |
| `test_preprocessing_step_inherits_base` | PreprocessingStep extends BaseStep |
| `test_preprocessing_step_id` | PreprocessingStep.step_id == 3 |
| `test_preprocessing_step_name` | PreprocessingStep.step_name correct |

#### TestPreprocessingConfig (6 tests) - Phase 5

| Test | Purpose |
|------|---------|
| `test_default_config_exists` | DEFAULT_PREPROCESS_CONFIG defined |
| `test_default_config_has_dedup` | Config includes deduplication settings |
| `test_default_config_has_ellipsis` | Config includes ellipsis setting |
| `test_default_config_has_symbol_conversion` | Config includes symbol conversion |
| `test_default_config_has_placeholder_rules` | Config includes placeholder rules list |
| `test_default_config_has_protect_patterns` | Config includes protect patterns list |

#### TestPreprocessingRuleTooltips (4 tests) - Phase 5

| Test | Purpose |
|------|---------|
| `test_rule_tooltips_exists` | RULE_TOOLTIPS dictionary exists |
| `test_dedup_tooltip_exists` | Deduplication tooltip defined |
| `test_ellipsis_tooltip_exists` | Ellipsis tooltip defined |
| `test_symbol_conversion_tooltip_exists` | Symbol conversion tooltip defined |

#### TestPreprocessingFunctions (4 tests) - Phase 5

| Test | Purpose |
|------|---------|
| `test_ellipsis_compression_western` | Western ellipsis compression works |
| `test_ellipsis_compression_japanese` | Japanese ellipsis compression works |
| `test_symbol_conversion_basic` | Basic JP punctuation conversion |
| `test_symbol_conversion_quotes` | Japanese quote conversion |

#### TestPreprocessingIntegration (2 tests) - Phase 5

| Test | Purpose |
|------|---------|
| `test_app_uses_preprocessing_step_for_step_3` | App uses PreprocessingStep for tab 3 |
| `test_preprocessing_in_steps_init` | PreprocessingStep exported from gui.steps |

#### TestEstimationStepModule (5 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_estimation_module_exists` | EstimationStep module importable |
| `test_estimation_step_class_exists` | EstimationStep class exists |
| `test_estimation_step_inherits_base` | EstimationStep extends BaseStep |
| `test_estimation_step_id` | EstimationStep.step_id == 4 |
| `test_estimation_step_name` | EstimationStep.step_name correct |

#### TestModelPricing (5 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_model_pricing_exists` | MODEL_PRICING dictionary exists |
| `test_model_pricing_has_gpt4o_mini` | GPT-4o Mini pricing defined |
| `test_model_pricing_has_claude` | Claude models pricing defined |
| `test_model_pricing_has_gemini` | Gemini models pricing defined |
| `test_model_pricing_structure` | All models have name/input/output fields |

#### TestEstimationDataclasses (2 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_estimation_result_exists` | EstimationResult dataclass works |
| `test_comparison_result_exists` | ComparisonResult dataclass works |

#### TestTokenCounting (4 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_count_tokens_empty` | Empty string returns 0 tokens |
| `test_count_tokens_english` | English text token counting |
| `test_count_tokens_japanese` | Japanese text token counting |
| `test_count_tokens_returns_tuple` | Returns (count, method) tuple |

#### TestCostEstimation (4 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_estimate_cost_basic` | Cost estimation structure correct |
| `test_estimate_cost_gpt4o_mini` | GPT-4o Mini pricing accurate |
| `test_estimate_cost_small_tokens` | Small token counts handled |
| `test_estimate_cost_default_model` | Unknown model uses default |

#### TestTimeEstimation (5 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_estimate_rate_limit_time_basic` | Time estimation structure correct |
| `test_estimate_rate_limit_time_60_requests` | 60 RPM calculation accurate |
| `test_format_time_seconds` | Short durations formatted as seconds |
| `test_format_time_minutes` | Medium durations formatted as minutes |
| `test_format_time_hours` | Long durations formatted as hours |

#### TestEstimationIntegration (3 tests) - Phase 6

| Test | Purpose |
|------|---------|
| `test_app_uses_estimation_step_for_step_4` | App uses EstimationStep for tab 4 |
| `test_estimation_in_steps_init` | EstimationStep exported from gui.steps |
| `test_output_multiplier_defined` | OUTPUT_MULTIPLIER constant defined |

#### TestTranslationEnums (2 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_line_status_enum_values` | LineStatus enum has expected values |
| `test_translation_state_enum_values` | TranslationState enum has expected values |

#### TestTranslationProgress (4 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_translation_progress_defaults` | TranslationProgress has sensible defaults |
| `test_translation_progress_remaining` | remaining_lines property calculates correctly |
| `test_translation_progress_percent` | progress_percent property calculates correctly |
| `test_translation_progress_percent_empty` | progress_percent returns 0 for empty progress |

#### TestTranslationOptions (2 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_translation_options_defaults` | TranslationOptions has sensible defaults |
| `test_translation_options_custom_values` | TranslationOptions accepts custom values |

#### TestTranslatableLine (3 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_translatable_line_creation` | TranslatableLine can be created with required fields |
| `test_translatable_line_status_change` | TranslatableLine status can be changed |
| `test_translatable_line_with_error` | TranslatableLine can store error message |

#### TestTranslationStepClass (5 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_translation_step_exists` | TranslationStep class exists and is importable |
| `test_translation_step_id` | TranslationStep has correct step_id (5) |
| `test_translation_step_name` | TranslationStep has correct step_name |
| `test_translation_step_model_options` | TranslationStep has MODEL_OPTIONS list |
| `test_translation_step_retry_strategies` | TranslationStep has RETRY_STRATEGIES list |

#### TestTranslationProgressWindow (2 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_progress_window_exists` | TranslationProgressWindow class exists |
| `test_progress_window_format_time` | TranslationProgressWindow._format_time works correctly |

#### TestTranslationStepIntegration (5 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_translation_step_in_steps_init` | TranslationStep is exported from gui.steps |
| `test_app_imports_translation_step` | App module imports TranslationStep |
| `test_translation_step_inherits_base` | TranslationStep inherits from BaseStep |
| `test_translation_step_has_required_methods` | TranslationStep has required abstract methods |
| `test_translation_step_has_helper_methods` | TranslationStep has expected helper methods |

#### TestTranslationLineStatus (2 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_all_line_statuses` | All LineStatus values are handled (5 statuses) |
| `test_line_status_display_mapping` | Line status has display text mapping |

#### TestTranslationStateTransitions (2 tests) - Phase 7

| Test | Purpose |
|------|---------|
| `test_valid_state_transitions` | TranslationState transitions are valid |
| `test_terminal_states` | Terminal states are correctly identified |

#### TestQAEnums (3 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_issue_type_enum_values` | IssueType enum has expected values (9 types) |
| `test_issue_severity_enum_values` | IssueSeverity enum has expected values |
| `test_qa_status_enum_values` | QAStatus enum has expected values |

#### TestQAIssue (2 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_issue_creation` | QAIssue can be created with required fields |
| `test_qa_issue_with_suggestion` | QAIssue can have suggestion and auto_fixable flag |

#### TestQALine (4 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_line_creation` | QALine can be created with required fields |
| `test_qa_line_has_issues` | QALine.has_issues property works correctly |
| `test_qa_line_has_errors` | QALine.has_errors property works correctly |
| `test_qa_line_issue_count` | QALine.issue_count property works correctly |

#### TestValidationRule (2 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_validation_rule_defaults` | ValidationRule has sensible defaults |
| `test_validation_rule_custom` | ValidationRule accepts custom values |

#### TestQAOptions (2 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_options_defaults` | QAOptions has sensible defaults |
| `test_qa_options_custom` | QAOptions accepts custom values |

#### TestQAStepClass (4 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_step_exists` | QAStep class exists and is importable |
| `test_qa_step_id` | QAStep has correct step_id (8) |
| `test_qa_step_name` | QAStep has correct step_name |
| `test_qa_step_default_rules` | QAStep has DEFAULT_RULES list (6 rules) |

#### TestQAStepIntegration (5 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_step_in_steps_init` | QAStep is exported from gui.steps |
| `test_app_imports_qa_step` | App module imports QAStep |
| `test_qa_step_inherits_base` | QAStep inherits from BaseStep |
| `test_qa_step_has_required_methods` | QAStep has required abstract methods |
| `test_qa_step_has_helper_methods` | QAStep has expected helper methods |

#### TestQAIssueTypes (2 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_all_issue_types_exist` | All IssueType values are defined (9+ types) |
| `test_issue_severity_levels` | All severity levels are properly ordered |

#### TestQAReportGeneration (2 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_line_properties` | QALine properties work with multiple issues |
| `test_qa_line_fixed_issues` | Fixed issues are properly excluded from counts |

#### TestQAAcceptReject (3 tests) - Phase 8

| Test | Purpose |
|------|---------|
| `test_qa_line_accept_state` | QALine can be accepted |
| `test_qa_line_reject_state` | QALine can be rejected |
| `test_qa_line_mutual_exclusion` | Accepted and rejected are mutually exclusive |

---

## Phase 18 Tests (89 tests)

Tests added for the Phase 18 Polish & Fixes tasks.

### dev/test_gui_dialogs.py (21 tests) - TASK 18.7

Tests for GlobalOptionsDialog freeze fix and lifecycle management.
**Session 24+:** TestDialogDataHandling and TestDialogCleanup updated to reflect renamed Settings
dataclass fields (autosave, interval, load_last, banned, encoding, lines, preservebom, backup).

#### TestGlobalOptionsDataclass (5 tests)

| Test | Purpose |
|------|---------|
| `test_global_options_creation` | GlobalOptions dataclass creates with defaults |
| `test_global_options_to_dict` | GlobalOptions serializes correctly |
| `test_global_options_from_dict` | GlobalOptions deserializes correctly |
| `test_theme_enum_values` | ThemeMode enum has expected values |
| `test_autosave_interval_validation` | Autosave interval accepts valid values |

#### TestGlobalSettingsDefaults (4 tests)

| Test | Purpose |
|------|---------|
| `test_global_settings_singleton` | GlobalSettings singleton pattern |
| `test_default_theme_mode` | Default theme is 'system' |
| `test_default_autosave_enabled` | Autosave enabled by default |
| `test_default_api_timeout` | Default API timeout is 60 seconds |

#### TestGlobalOptionsDialogLifecycle (4 tests)

| Test | Purpose |
|------|---------|
| `test_dialog_exists` | GlobalOptionsDialog class exists |
| `test_dialog_has_wm_delete_protocol` | Dialog has WM_DELETE_WINDOW handler |
| `test_dialog_has_on_close_method` | Dialog has _on_close method |
| `test_dialog_destroy_releases_grab` | destroy() calls grab_release() |

#### TestDialogReuse (5 tests)

| Test | Purpose |
|------|---------|
| `test_api_log_open_or_focus_reuses_existing_dialog` | Existing API Log window is focused instead of duplicated |
| `test_api_log_open_or_focus_creates_and_registers_dialog` | New API Log window is registered on the root window |
| `test_global_options_add_save_listener_deduplicates_bound_methods` | Save listener registration avoids duplicates |
| `test_global_options_open_or_focus_reuses_existing_dialog` | Existing Global Options dialog is focused and retargeted to the requested section |
| `test_global_options_destroy_clears_root_reference` | Destroy clears the root-window dialog registry |

### dev/test_cli_estimation.py (13 tests) - TASK 18.6

Tests for CLI estimation command and cost calculation.

#### TestEstimationDataStructures (5 tests)

| Test | Purpose |
|------|---------|
| `test_estimation_result_exists` | EstimationResult dataclass exists |
| `test_estimation_result_fields` | Has required fields (tokens, cost, chunks) |
| `test_estimation_result_defaults` | Default values are sensible |
| `test_estimation_result_to_dict` | Serialization works |
| `test_estimation_result_calculated_fields` | Calculated fields compute correctly |

#### TestCLIEstimationLogic (4 tests)

| Test | Purpose |
|------|---------|
| `test_calculate_cost_function_exists` | calculate_cost function exists |
| `test_cost_calculation_basic` | Basic cost calculation works |
| `test_cost_zero_tokens` | Zero tokens returns zero cost |
| `test_cost_per_provider` | Different providers have different rates |

#### TestEstimationDisplay (4 tests)

| Test | Purpose |
|------|---------|
| `test_display_estimate_method_exists` | _display_estimate method exists in CLI |
| `test_estimation_format_currency` | Currency formatting works |
| `test_estimation_format_tokens` | Token count formatting works |
| `test_estimation_command_exists` | estimate command is registered |

### dev/test_manifest_automation.py (12 tests) - TASK 18.8

Tests for automatic manifest creation and persistence.

#### TestManifestStructure (4 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_has_required_fields` | Required fields present |
| `test_manifest_version` | Version is "2.0" |
| `test_manifest_serialization` | JSON serialization works |
| `test_manifest_deserialization` | JSON deserialization works |

#### TestManifestCreation (4 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_has_required_fields` | Required manifest fields present |
| `test_manifest_filename_pattern` | Uses .manifest.json extension |
| `test_manifest_includes_source_path` | Source path is recorded |
| `test_manifest_includes_timestamp` | Creation timestamp is recorded |

**Note**: Unified manifest creation is now handled by `ManifestManager.create_new()` called from `App.create_new_project()`. Individual per-file manifests are no longer created.

#### TestManifestPersistence (4 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_file_roundtrip` | Write and read manifest |
| `test_manifest_unicode_paths` | Unicode paths work |
| `test_manifest_file_count` | File count is accurate |
| `test_manifest_update_timestamp` | Timestamp updates on change |

### dev/test_glossary_integration.py (12 tests) - TASK 18.4

Tests for Analysis → Information character/glossary integration.

#### TestCharacterDataStructures (4 tests)

| Test | Purpose |
|------|---------|
| `test_character_info_dataclass_exists` | CharacterInfo exists |
| `test_character_info_has_required_fields` | Required fields present (original_name, translation, notes) |
| `test_character_info_optional_fields` | Optional fields have defaults |
| `test_project_metadata_has_characters` | ProjectMetadata includes characters |

#### TestSpeakerDetectionFormat (4 tests)

| Test | Purpose |
|------|---------|
| `test_speakers_dict_format` | Speakers stored as dict[str, int] |
| `test_speakers_can_be_sorted_by_count` | Sorting by count works |
| `test_empty_speakers_handled` | Empty speakers dict works |
| `test_unicode_speaker_names` | Unicode names work |

#### TestIntegrationDataFlow (4 tests)

| Test | Purpose |
|------|---------|
| `test_analysis_results_structure` | Analysis results format |
| `test_analysis_step_data_structure` | Session data structure |
| `test_character_import_from_speakers` | Character creation from speakers |
| `test_total_test_count` | Test count verification |

### dev/test_gui_layout.py (12 tests) - TASK 18.2

Tests for 2-column layout in Information tab.

#### TestColumnStructure (4 tests)

| Test | Purpose |
|------|---------|
| `test_information_step_exists` | InformationStep importable |
| `test_information_step_has_left_column_attribute` | _left_column in code |
| `test_information_step_has_right_column_attribute` | _right_column in code |
| `test_columns_use_grid_layout` | Grid geometry used |

#### TestWidgetPlacement (4 tests)

| Test | Purpose |
|------|---------|
| `test_project_section_in_left_column` | Project in left |
| `test_language_section_in_left_column` | Languages in left |
| `test_notes_section_in_right_column` | Notes in right |
| `test_inference_section_in_right_column` | Inference in right |

#### TestLayoutResponsiveness (4 tests)

| Test | Purpose |
|------|---------|
| `test_columns_have_weight_configured` | Weight=1 for responsive |
| `test_columns_have_minimum_size` | Minsize for readability |
| `test_sticky_nsew_for_expansion` | Sticky for expansion |
| `test_total_test_count` | Test count verification |

### dev/test_subtask_tracking.py (14 tests) - TASK 18.3

Tests for subtask tracking in ProgressTracker.

#### TestSubtaskDataClasses (5 tests)

| Test | Purpose |
|------|---------|
| `test_subtask_creation` | Subtask defaults |
| `test_subtask_to_dict` | Subtask serialization |
| `test_subtask_from_dict` | Subtask deserialization |
| `test_subtaskgroup_creation` | SubtaskGroup defaults |
| `test_subtaskgroup_add_subtask` | Adding subtasks |

#### TestSubtaskGroupManagement (4 tests)

| Test | Purpose |
|------|---------|
| `test_update_subtask` | Update by name |
| `test_update_subtask_not_found` | Returns False if not found |
| `test_get_overall_progress` | Average progress calculation |
| `test_clear_subtasks` | Clear all subtasks |

#### TestProgressAPI (5 tests)

| Test | Purpose |
|------|---------|
| `test_register_subtasks_method_exists` | API method exists |
| `test_update_subtask_method_exists` | API method exists |
| `test_complete_subtask_method_exists` | API method exists |
| `test_clear_subtasks_method_exists` | API method exists |
| `test_total_test_count` | Test count verification |

### dev/test_code_glossary_display.py (27 tests) - TASK 18.5

Tests for Code Glossary widget in Information tab, CodePattern dataclass, instance counts.

#### TestCodePatternDataClass (11 tests)

| Test | Purpose |
|------|---------|
| `test_code_pattern_creation` | CodePattern defaults |
| `test_code_pattern_to_dict` | Serialization |
| `test_code_pattern_from_dict` | Deserialization |
| `test_code_pattern_default_action` | Default is 'preserve' |
| `test_code_pattern_count_field` | Count field present |
| `test_code_pattern_raw_type_field` | raw_type field present |
| `test_code_pattern_instances_field` | instances field present |
| `test_code_pattern_to_dict_with_new_fields` | New fields serialized |
| `test_code_pattern_to_dict_omits_empty_instances` | Empty instances omitted |
| `test_code_pattern_from_dict_with_new_fields` | New fields deserialized |
| `test_code_pattern_from_dict_legacy` | Legacy format compat |

#### TestProjectMetadataIntegration (4 tests)

| Test | Purpose |
|------|---------|
| `test_project_metadata_has_code_patterns` | code_patterns field exists |
| `test_project_metadata_to_dict_includes_patterns` | Serializes patterns |
| `test_project_metadata_from_dict_loads_patterns` | Deserializes patterns |
| `test_total_test_count` | Test count verification |

#### TestCodePatternDialogStructure (4 tests)

| Test | Purpose |
|------|---------|
| `test_code_pattern_dialog_exists` | Dialog class exists |
| `test_code_pattern_dialog_has_actions` | ACTIONS constant |
| `test_code_pattern_dialog_has_categories` | CATEGORIES constant |
| `test_information_step_has_code_methods` | Management methods exist |

#### TestCodePatternInstanceCounts (8 tests)

| Test | Purpose |
|------|---------|
| `test_instance_counts_default_empty` | instance_counts defaults to [] |
| `test_instance_counts_creation` | instance_counts created with values |
| `test_to_dict_count_as_list_when_instance_counts` | count serialized as [total, inst1, ...] |
| `test_to_dict_count_as_int_when_no_instance_counts` | count stays int without instances |
| `test_from_dict_list_count` | List count split into count + instance_counts |
| `test_from_dict_int_count_no_instance_counts` | Int count gives empty instance_counts |
| `test_roundtrip_with_instance_counts` | Full roundtrip with instance_counts |
| `test_from_dict_empty_list_count` | Edge case: [5] with no sub-counts |

---

### dev/test_code_pattern_actions.py (46 tests) - Code Pattern Action Overhaul

Tests for the code pattern action system overhaul: normalization fixes (CJK tags, space-separated numbers, closing tags), new action set, sync with preprocessing sections, validation, and prompt building.

#### TestAngleBracketNormalization (10 tests)

| Test | Purpose |
|------|---------|
| `test_simple_ascii_tag` | `<abc>` → `<TAG>` |
| `test_cjk_tag_name` | `<文字色 …>` → `<文字色 <NUM>>` |
| `test_multiple_space_separated_numbers` | `<tag 1 2 3>` → `<tag <NUM>>` |
| `test_closing_tag` | `</>` → `</>` (literal) |
| `test_tag_no_extra_content` | `<文字色>` → `<TAG>` |
| `test_tag_with_hex_content` | `<TAG FF>` → `<TAG <NUM>>` |
| `test_empty_brackets` | `<>` → `<>` |
| `test_self_closing_html` | `<br/>` → `<TAG>` |
| `test_non_numeric_content` | `<tag abc def>` → `<TAG>` |
| `test_mixed_alpha_num_content` | `<tag abc 123>` stays generic |

#### TestAngleBracketRegex (3 tests)

| Test | Purpose |
|------|---------|
| `test_cjk_regex_matches_variants` | Regex matches space-separated numbers |
| `test_closing_tag_regex_literal` | `</>` regex is literal match |
| `test_ascii_tag_regex_matches` | `<TAG>` regex matches |

#### TestCodePatternActions (4 tests)

| Test | Purpose |
|------|---------|
| `test_valid_actions` | ACTIONS list contains all 6 new actions |
| `test_from_dict_preserves_action` | from_dict preserves valid action |
| `test_from_dict_migrate_translate` | "translate" → "provides_context" |
| `test_from_dict_migrate_remove` | "remove" → "preserve" |

#### TestProvidesContextPrompt (2 tests)

| Test | Purpose |
|------|---------|
| `test_provides_context_in_prompt` | "Translate as" hint for provides_context |
| `test_default_action_in_prompt` | "Do not translate" for other actions |

#### TestPartOfSpanPrompt (1 test)

| Test | Purpose |
|------|---------|
| `test_part_of_span_default` | part_of_span gets "Do not translate" |

#### TestSyncCodePatternActions (5 tests)

| Test | Purpose |
|------|---------|
| `test_protect_syncs_to_protect_code_patterns` | protect → ProtectCodePatterns |
| `test_custom_placeholder_syncs` | custom_placeholder → CustomPlaceholders |
| `test_strip_with_anchor_syncs` | strip_with_anchor → AnchorRemoval |
| `test_stale_entries_removed` | Old auto entries cleaned on re-sync |
| `test_manual_entries_preserved` | Non-auto entries kept |

#### TestCodePatternValidation (5 tests)

| Test | Purpose |
|------|---------|
| `test_missing_pattern_detected` | Missing preserve pattern flagged |
| `test_present_pattern_ok` | Present pattern passes |
| `test_non_preserve_ignored` | Non-preserve actions skipped |
| `test_pattern_not_in_original` | Original missing pattern skipped |
| `test_validate_line_post_integration` | Integration with validate_line_post |

#### TestAnchorEquivalents (2 tests)

| Test | Purpose |
|------|---------|
| `test_strip_with_anchor_equivalent` | strip_with_anchor syncs like anchor |
| `test_anchor_icon_in_action` | Action recognized |

#### TestPromptBuilderActions (5 tests)

| Test | Purpose |
|------|---------|
| `test_provides_context_hint` | provides_context generates hint |
| `test_default_hint` | Other actions get "Do not translate" |
| `test_preserve_do_not_translate` | preserve → "Do not translate" |
| `test_protect_default_path` | protect → default path |
| `test_old_remove_not_skipped` | remove action no longer skips |

#### TestConsistencyActions (2 tests)

| Test | Purpose |
|------|---------|
| `test_provides_context_excludes` | provides_context excluded from consistency |
| `test_preserve_includes` | preserve included in consistency |

#### TestFromDictMigration (3 tests)

| Test | Purpose |
|------|---------|
| `test_replace_migrates_to_protect` | "replace" → "protect" |
| `test_unknown_action_passthrough` | Unknown action kept as-is |
| `test_missing_action_defaults_preserve` | Missing action defaults preserve |

#### TestNormalizationEdgeCases (4 tests)

| Test | Purpose |
|------|---------|
| `test_unicode_tag_with_numbers` | Unicode tag + space-separated numbers |
| `test_plain_number_in_brackets` | `<123>` → `<NUM>` |
| `test_nested_looking_brackets` | Nested angle brackets handled |
| `test_very_long_tag_content` | Long content stays generic |

```
python -m pytest CherryAI/dev/test_code_pattern_actions.py -v --timeout=10
```

---

### dev/test_code_pattern_recovery.py (33 tests) - Code Pattern Recovery

Tests for preserve-action code pattern recovery, validation, and the full pipeline fix for the idx 8 bug ({アンカー} translated as {anchor}). Also covers doubled-delimiter preserve tokens such as `{{...}}` so restores replace the whole token instead of leaving a trailing brace.

#### TestDetectDelimiters (8 tests)

| Test | Purpose |
|------|---------|
| `test_curly_braces` | `{アンカー}` → `{`, `}` |
| `test_square_brackets` | `[font_COLOR]` → `[`, `]` |
| `test_angle_brackets` | `<br>` → `<`, `>` |
| `test_parentheses` | `(hello)` → `(`, `)` |
| `test_empty_string` | Empty → None |
| `test_no_delimiters` | `plain_text` → None |
| `test_fullwidth_curly` | `｛test｝` → `｛`, `｝` |
| `test_cjk_angle` | `《test》` → `《`, `》` |

#### TestRecoverCodePatterns (10 tests)

| Test | Purpose |
|------|---------|
| `test_anchor_translated_to_english` | Core bug: `{anchor}` → `{アンカー}` recovered |
| `test_pattern_already_preserved` | No-op when pattern survives translation |
| `test_non_preserve_action_skipped` | translate-action patterns not checked |
| `test_square_bracket_recovery` | `[name]` → `[名前]` recovered |
| `test_unrecoverable_pattern_flagged` | NEEDS_RETRY when no candidate found |
| `test_multiple_patterns_recovered` | Two patterns both recovered |
| `test_empty_code_patterns` | No-op with empty list |
| `test_pattern_not_in_original` | Skip when pattern absent from original |
| `test_candidate_matches_different_known_pattern` | Don't clobber valid patterns |
| `test_nested_single_curly_inside_double_curly_is_ignored` | Inner `{...}` is ignored when only outer `{{...}}` should recover |

#### TestValidateCodePatternsPreserved (5 tests)

| Test | Purpose |
|------|---------|
| `test_missing_pattern_detected` | Warning for missing `{アンカー}` |
| `test_preserved_pattern_no_warning` | No warning when preserved |
| `test_translate_action_not_checked` | translate-action skipped |
| `test_multiple_occurrences_partial` | Partial preservation flagged |
| `test_nested_single_curly_inside_double_curly_is_not_flagged` | Avoid double-flagging `{...}` inside `{{...}}` |

#### TestValidateTranslationComprehensiveCodePatterns (3 tests)

| Test | Purpose |
|------|---------|
| `test_code_pattern_error_and_retry` | Check #7 fires, CODE_PATTERN_TRANSLATED retry reason |
| `test_no_error_when_preserved` | No error when pattern survives |
| `test_no_code_patterns_param` | Without code_patterns, check #7 is no-op |

#### TestRecoverLineCodePatterns (3 tests)

| Test | Purpose |
|------|---------|
| `test_code_pattern_recovered_in_pipeline` | recover_line passes code_patterns through |
| `test_no_code_patterns_param_skipped` | Without code_patterns, recovery skipped |
| `test_double_curly_preserve_does_not_leave_extra_closing_brace` | `{{Guild Name}}` → `{{ギルド呼び名}}` without trailing `}` |

#### TestIdx8BugScenario (2 tests)

| Test | Purpose |
|------|---------|
| `test_full_recovery_pipeline` | End-to-end: validate → comprehensive → recover → re-validate |
| `test_unrecoverable_flags_qa` | Unrecoverable patterns set needs_retry=True |

```
python -m pytest CherryAI/dev/test_code_pattern_recovery.py -v --timeout=10
```

### dev/test_custom_placeholder_recovery.py (2 tests)

Focused regression tests for line-agnostic custom placeholder restoration.

**Files Tested:** `functions/modehelper.py`

| Test | Purpose |
|------|---------|
| `test_restores_named_placeholder_on_different_line` | Restores a named token such as `Jane` even when the LLM moved it to a different line |
| `test_prefers_local_restore_before_global_fallback` | Ensures per-line restoration still wins before the batch-wide fallback runs |

```
python -m pytest CherryAI/dev/test_custom_placeholder_recovery.py -v --timeout=10
```

---

### dev/test_request_slicing_settings.py (30 tests) - Per-Model Settings Priority

Tests for the per-model API.ini settings priority fix ensuring Estimation and Preview Requests respect per-model chunk_size, rolling_context, chunk_max_tokens, and temperature from API.ini `[model_settings]` instead of unconditionally using Global Options defaults.

#### TestEfficientAlwaysFewerRequests (7 tests)

| Test | Purpose |
|------|---------|
| `test_chunk_size_10` | Efficient ≤ conservative with chunk_size=10 |
| `test_chunk_size_50` | Efficient ≤ conservative with chunk_size=50 |
| `test_chunk_size_200` | Efficient ≤ conservative with chunk_size=200 |
| `test_single_file` | Single-file input (no cross-file merge) |
| `test_multi_file` | Multi-file input triggers cross-file merge |
| `test_high_chunk_size` | Large chunk covers all lines in one request |
| `test_all_same_file` | All lines in same file, no merge opportunity |

#### TestMinLinesCalculation (2 tests)

| Test | Purpose |
|------|---------|
| `test_conservative_min_lines` | `min_lines = max(2, chunk_size // 5)` |
| `test_efficient_min_lines` | `min_lines = max(5, chunk_size // 2)` |

#### TestStep5EfficientMerge (5 tests)

| Test | Purpose |
|------|---------|
| `test_cross_file_merge` | Step 5 merges small cross-file requests |
| `test_no_merge_same_file` | No merge when all lines from same file |
| `test_preserves_boundaries` | Merge preserves original request boundaries |
| `test_skips_when_disabled` | No merge when efficient_merge=False |
| `test_merge_reduces_count` | Merged result has fewer requests |

#### TestConfigPropagation (2 tests)

| Test | Purpose |
|------|---------|
| `test_efficient_merge_true` | RequestFormationConfig.efficient_merge=True propagates |
| `test_efficient_merge_false` | RequestFormationConfig.efficient_merge=False propagates |

#### TestCostsEstimationNoOverride (2 tests)

| Test | Purpose |
|------|---------|
| `test_no_go_request_override` | costs.py source has no go.request.chunk_size override |
| `test_chunk_var_read` | _do_estimation reads chunk_size from _chunk_var |

#### TestTranslateLoadModelSettings (2 tests)

| Test | Purpose |
|------|---------|
| `test_method_exists` | translate.py defines _load_model_settings |
| `test_has_get_model_settings_call` | _load_model_settings calls get_model_settings |

#### TestPreviewUpdatesOptions (1 test)

| Test | Purpose |
|------|---------|
| `test_translation_options_assigned` | _build_preview_requests assigns _translation_options |

#### TestBuildChunksPerModelSettings (4 tests)

| Test | Purpose |
|------|---------|
| `test_get_model_settings_call` | _build_chunks calls get_model_settings |
| `test_rc_between_from_model` | rolling_context_between read from per-model settings |
| `test_rc_after_from_model` | rolling_context_after read from per-model settings |
| `test_chunk_max_tokens_from_model` | chunk_max_tokens read from per-model settings |

#### TestPreviewRollingContextPerModel (1 test)

| Test | Purpose |
|------|---------|
| `test_rolling_context_before_per_model` | Preview reads rolling_context_before from per-model API.ini |

#### TestFormationPipelineRealWorld (3 tests)

| Test | Purpose |
|------|---------|
| `test_100_lines` | Formation pipeline with 100 real-world lines |
| `test_500_lines` | Formation pipeline with 500 lines |
| `test_1000_lines` | Formation pipeline with 1000 lines |

#### TestFormationStepsConsistency (1 test)

| Test | Purpose |
|------|---------|
| `test_conservative_ge_efficient` | Conservative always produces ≥ efficient request count |

```
python -m pytest CherryAI/dev/test_request_slicing_settings.py -v --timeout=10
```

---

### dev/test_session_loading.py (28 tests) - TASKS 18.1-18.8

Tests for session loading and state restoration fixes.
**Session 26:** Updated `TestSessionStepNameMapping` assertions for new tab order (Information=2, Preprocessing=3).

#### TestAnalysisSessionLoading (4 tests) - TASK 18.1

| Test | Purpose |
|------|---------|
| `test_analysis_results_stored_in_session` | Results can be stored in session |
| `test_analysis_results_structure` | Results have expected structure |
| `test_analysis_languages_dict` | Languages dict structure |
| `test_analysis_speakers_dict` | Speakers dict structure |

#### TestAnalysisFindingsDeserialization (5 tests) - TASK 18.5

| Test | Purpose |
|------|---------|
| `test_tablerow_from_dict` | TableRow deserialization from dict |
| `test_tablerow_roundtrip` | TableRow serialization roundtrip |
| `test_findings_list_deserialization` | List of findings deserialization |
| `test_findings_values_is_dict_not_method` | Validates fix for dict.values vs TableRow.values |
| `test_mixed_findings_deserialization` | Handles mixed TableRow/dict lists |

#### TestInformationSessionLoading (4 tests) - TASK 18.2

| Test | Purpose |
|------|---------|
| `test_metadata_stored_in_session` | Metadata can be stored in session |
| `test_metadata_characters_stored` | Characters properly stored |
| `test_metadata_code_patterns_stored` | Code patterns properly stored |
| `test_metadata_all_fields_present` | All expected fields present |

#### TestCodePatternDialog (4 tests) - TASK 18.3

| Test | Purpose |
|------|---------|
| `test_code_pattern_dataclass_creation` | CodePattern creation |
| `test_code_pattern_to_dict` | Serialization |
| `test_code_pattern_from_dict` | Deserialization |
| `test_code_pattern_actions` | Valid actions list (6 new actions: preserve, provides_context, custom_placeholder, protect, strip_with_anchor, part_of_span) |

#### TestPreprocessingSessionLoading (4 tests) - TASK 18.4/18.8

| Test | Purpose |
|------|---------|
| `test_input_step_data_no_redundant_all_lines` | Input step data no longer stores all_lines (TASK 71) |
| `test_preprocessing_config_storage` | Config storage and retrieval |
| `test_preprocessing_placeholder_rules_storage` | Placeholder rules storage |
| `test_preprocessing_protect_patterns_storage` | Protect patterns storage |

#### TestSessionStateRoundtrip (3 tests)

| Test | Purpose |
|------|---------|
| `test_step_state_to_dict` | StepState serialization |
| `test_step_state_from_dict` | StepState deserialization |
| `test_metadata_roundtrip` | ProjectMetadata roundtrip |

#### TestEdgeCases (4 tests)

| Test | Purpose |
|------|---------|
| `test_empty_session_step_data` | Empty step data handling |
| `test_missing_metadata_fields` | Missing optional fields |

---

### dev/test_folder_loading.py (23 tests) - Folder Loading Feature

Tests for folder loading functionality in InputExtractionStep. Covers recursive file 
collection, relative path display, and cleanup verification.

#### TestCollectFilesFromFolder (4 tests)

| Test | Purpose |
|------|---------|
| `test_collects_all_supported_files` | Recursively finds all supported file types |
| `test_collects_txt_files_only` | Single extension filtering |
| `test_handles_empty_folder` | Empty folder returns empty list |
| `test_handles_permission_error` | Permission errors handled gracefully |

#### TestGetDisplayName (5 tests)

| Test | Purpose |
|------|---------|
| `test_returns_relative_path_when_folder_root_set` | Relative path display |
| `test_returns_deeply_nested_relative_path` | Deeply nested path display |
| `test_returns_filename_when_not_relative` | Fallback to filename |
| `test_returns_filename_when_folder_root_none` | No folder root behavior |
| `test_root_file_shows_just_filename` | Root-level file display |

#### TestFileCreationAndCleanup (2 tests)

| Test | Purpose |
|------|---------|
| `test_temp_folder_is_created` | Temp fixture works |
| `test_populated_folder_has_expected_structure` | Populated fixture structure |

#### TestCleanupVerification (2 tests)

| Test | Purpose |
|------|---------|
| `test_cleanup_removes_temp_folder` | Cleanup mechanism works |
| `test_no_leftover_test_folders` | No test folders left behind |

#### TestInputExtractionStepFolderLoading (4 tests)

| Test | Purpose |
|------|---------|
| `test_folder_root_initially_none` | Initial state is None |
| `test_folder_root_set_after_folder_load` | Folder root set correctly |
| `test_file_loading_respects_format_filter` | Only supported formats loaded |
| `test_sorted_file_order` | Files sorted by path |

#### TestEdgeCases (5 tests)

| Test | Purpose |
|------|---------|
| `test_folder_with_only_unsupported_files` | Empty result for unsupported |
| `test_folder_with_mixed_case_extensions` | Case-insensitive matching |
| `test_folder_with_spaces_in_path` | Spaces in paths handled |
| `test_folder_with_unicode_names` | Unicode filenames handled |
| `test_relative_path_with_unicode` | Unicode in relative paths |

#### TestFinalCleanup (1 test)

| Test | Purpose |
|------|---------|
| `test_zz_no_test_files_left_behind` | Ensures no test files persist |

---

### dev/test_input_step_phase39.py (40 tests) - Phase 39 Input Step Improvements

Comprehensive tests for Phase 39 Input step UI/UX improvements including unified
file selector, Treeview hierarchy, format filtering, encoding auto-detect, and
progress dialog.

#### TestUnifiedSelector (2 tests)

| Test | Purpose |
|------|---------|
| `test_select_button_exists` | Unified "Select File(s)" button exists |
| `test_show_select_menu_method` | `_show_select_menu` method exists |

#### TestRemovedButtons (2 tests)

| Test | Purpose |
|------|---------|
| `test_load_manifest_button_removed` | Load Manifest button removed from toolbar |
| `test_clear_all_button_removed` | Clear All button removed from toolbar |

#### TestEncodingDropdown (6 tests)

| Test | Purpose |
|------|---------|
| `test_auto_encoding_detect_utf8` | UTF-8 auto detection |
| `test_auto_encoding_detect_utf8_sig` | UTF-8 BOM auto detection |
| `test_auto_encoding_detect_utf16` | UTF-16 BOM auto detection |
| `test_auto_encoding_fallback_utf8` | Empty-file fallback |
| `test_load_file_uses_selected_parser_for_auto_encoding` | Explicit parser selection still uses parser `detect_encoding()` when Encoding stays `auto` |
| `test_sync_output_defaults_to_manifest_uses_loaded_file_metadata` | Input step seeds manifest Output defaults from loaded file metadata |

#### TestFormatDropdown (3 tests)

| Test | Purpose |
|------|---------|
| `test_rpgmaker_format_option` | "rpgmaker" is in format values |
| `test_image_format_option` | "image" is in format values |
| `test_format_values_count` | Correct number of format options |

#### TestFormatFiltering (4 tests)

| Test | Purpose |
|------|---------|
| `test_format_extensions_dict` | FORMAT_EXTENSIONS dict exists |
| `test_file_matches_format_method` | `_file_matches_format` method exists |
| `test_txt_format_extensions` | TXT format has correct extensions |
| `test_csv_format_extensions` | CSV format has correct extensions |

#### TestFileTree (6 tests)

| Test | Purpose |
|------|---------|
| `test_file_tree_is_treeview` | File list is a ttk.Treeview |
| `test_tree_item_to_index_dict` | `_tree_item_to_index` mapping exists |
| `test_treeview_columns` | Treeview has correct columns |
| `test_treeview_multiselect` | Treeview supports extended selection |
| `test_backward_compat_alias` | `_file_listbox` aliases `_file_tree` |
| `test_select_all_in_folder_method` | `_on_select_all_in_folder` method exists |

#### TestMultiLinePreview (4 tests)

| Test | Purpose |
|------|---------|
| `test_update_preview_method` | `_update_preview` method exists |
| `test_newline_marker_in_preview` | Newlines replaced with ↵ markers |
| `test_crlf_replaced` | CRLF sequences replaced |
| `test_cr_replaced` | CR-only sequences replaced |

#### TestManifestLabelRemoved (2 tests)

| Test | Purpose |
|------|---------|
| `test_no_manifest_frame` | `_manifest_frame` removed |
| `test_no_manifest_label` | `_manifest_label` removed |

#### TestLoadingProgressDialog (4 tests)

| Test | Purpose |
|------|---------|
| `test_import` | LoadingProgressDialog importable |
| `test_init_signature` | Constructor accepts parent and total_files |
| `test_update_method` | Has `update()` method |
| `test_close_method` | Has `close()` method |

#### TestSupportedExtensions (2 tests)

| Test | Purpose |
|------|---------|
| `test_image_in_supported` | Image extensions in SUPPORTED_EXTENSIONS |
| `test_rpgmaker_in_format_map` | RPG Maker in FORMAT_MAP |

#### TestPhase39Integration (4 tests)

| Test | Purpose |
|------|---------|
| `test_all_phase39_methods` | All Phase 39 methods exist on class |
| `test_all_phase39_attributes` | All Phase 39 attributes exist |
| `test_loading_progress_module` | Loading progress module accessible |
| `test_input_step_importable` | InputExtractionStep still importable |

#### TestPhase39Cleanup (1 test)

| Test | Purpose |
|------|---------|
| `test_no_deprecated_widgets` | Deprecated widgets removed |

---

### dev/test_input_step_improvements.py (60 tests) - Phase 60 Input Step Improvements

Tests for Phase 60 Input step UI/UX improvements: type column refresh fix,
clickable column header sort, file list filter, cross-file preview search.

#### TestModuleImports (2 tests)

| Test | Purpose |
|------|---------|
| `test_input_extraction_step_importable` | InputExtractionStep class is importable |
| `test_classify_file_type_importable` | classify_file_type function is importable |

#### TestTypeColumnRefresh (4 tests)

| Test | Purpose |
|------|---------|
| `test_update_file_list_method_exists` | _update_file_list method exists |
| `test_load_selected_paths_method_exists` | _load_selected_paths method exists |
| `test_on_load_files_method_exists` | _on_load_files method exists |
| `test_on_load_folder_method_exists` | _on_load_folder method exists |

#### TestClickableColumnHeaders (13 tests)

| Test | Purpose |
|------|---------|
| `test_sort_column_attribute_exists` | _sort_column attribute exists |
| `test_sort_ascending_attribute_exists` | _sort_ascending attribute exists |
| `test_sort_column_default_empty` | _sort_column defaults to "" |
| `test_sort_ascending_default_true` | _sort_ascending defaults to True |
| `test_on_column_sort_method_exists` | _on_column_sort method exists |
| `test_refresh_sort_headings_method_exists` | _refresh_sort_headings method exists |
| `test_no_sort_combobox` | _sort_var attribute removed |
| `test_column_sort_toggles_ascending` | First sort sets ascending, second toggles |
| `test_column_sort_changes_column` | Sorting different column resets to ascending |
| `test_column_sort_name` | Sorting by "name" works |
| `test_column_sort_type` | Sorting by "type" works |
| `test_column_sort_lines` | Sorting by "lines" works |
| `test_refresh_sort_headings_callable` | _refresh_sort_headings is callable |

#### TestFileListFilter (9 tests)

| Test | Purpose |
|------|---------|
| `test_file_filter_var_exists` | _file_filter_var attribute exists |
| `test_file_filter_entry_exists` | _file_filter_entry attribute exists |
| `test_file_filter_clear_btn_exists` | _file_filter_clear_btn attribute exists |
| `test_filter_var_is_string_var` | _file_filter_var is a StringVar |
| `test_filter_default_empty` | Filter defaults to empty string |
| `test_filter_match_name` | Filter matches against filename |
| `test_filter_match_type` | Filter matches against file type |
| `test_filter_match_line_count` | Filter matches against line count |
| `test_filter_case_insensitive` | Filter matching is case-insensitive |

#### TestCrossFilePreviewSearch (14 tests)

| Test | Purpose |
|------|---------|
| `test_update_preview_method_exists` | _update_preview method exists |
| `test_update_preview_single_file_method` | _update_preview_single_file method exists |
| `test_update_preview_cross_file_method` | _update_preview_cross_file method exists |
| `test_on_preview_select_method` | _on_preview_select method exists |
| `test_select_file_in_tree_method` | _select_file_in_tree method exists |
| `test_on_preview_search_clear_method` | _on_preview_search_clear method exists |
| `test_preview_search_clear_btn_exists` | _preview_search_clear_btn attribute exists |
| `test_preview_tree_has_idx_column` | Preview treeview has idx column |
| `test_preview_tree_columns_complete` | Preview tree has all expected columns (idx, line, content, tags) |
| `test_current_file_index_attribute` | _current_file_index attribute exists |
| `test_preview_search_var_exists` | _preview_search_var attribute exists |
| `test_loaded_files_attribute` | _loaded_files attribute exists |
| `test_preview_tree_has_selectmode` | Preview tree supports selection |
| `test_file_tree_has_selectmode` | File tree supports selection |

#### TestLoadedFileBasics (2 tests)

| Test | Purpose |
|------|---------|
| `test_loaded_files_is_list` | _loaded_files is a list |
| `test_current_file_index_is_int` | _current_file_index is an integer |

#### TestSortLogicUnit (4 tests)

| Test | Purpose |
|------|---------|
| `test_sort_by_name_ascending` | Sort files by name ascending |
| `test_sort_by_name_descending` | Sort files by name descending |
| `test_sort_by_lines_ascending` | Sort files by line count ascending |
| `test_sort_by_lines_descending` | Sort files by line count descending |

#### TestFilterLogicUnit (8 tests)

| Test | Purpose |
|------|---------|
| `test_filter_empty_shows_all` | Empty filter shows all files |
| `test_filter_by_partial_name` | Partial name match filters correctly |
| `test_filter_no_match` | Non-matching filter returns empty |
| `test_filter_by_type_dialogue` | Filter by "dialogue" type |
| `test_filter_by_line_count_string` | Filter by line count number |
| `test_filter_case_insensitive_logic` | Case-insensitive matching |
| `test_filter_multiple_matches` | Multiple files match single filter |
| `test_filter_whitespace_stripped` | Leading/trailing whitespace stripped |

#### TestCrossFileSearchLogicUnit (4 tests)

| Test | Purpose |
|------|---------|
| `test_search_finds_across_files` | Search finds matches across multiple files |
| `test_search_returns_global_idx` | Results include global idx |
| `test_search_empty_returns_none` | Empty search returns no cross-file results |
| `test_search_case_insensitive` | Search matching is case-insensitive |

---

### dev/test_costs_step_phase40.py (52 tests) - Phase 40 Costs Step Improvements

Tests for all Phase 40 tasks: renaming, hybrid chunking, prompt overhead,
dual estimation, dual ticks, model comparison, concurrent time, prepro lines.

#### TestCostsRename (10 tests) - TASK 40.1

| Test | Purpose |
|------|---------|
| `test_costs_step_class_exists` | CostsStep importable from costs module |
| `test_costs_step_name` | step_name is "Costs" |
| `test_costs_step_id` | step_id is 2 |
| `test_backward_compat_alias` | EstimationStep alias → CostsStep |
| `test_backward_compat_estimate_module` | estimate.py re-exports both |
| `test_init_exports` | Steps __init__ exports CostsStep |
| `test_step_definitions_name` | STEP_DEFINITIONS uses "Costs" |
| `test_estimate_re_exports_dataclasses` | estimate.py re-exports dataclasses |
| `test_estimate_re_exports_functions` | estimate.py re-exports functions |
| `test_estimate_re_exports_constants` | estimate.py re-exports pricing constants |

#### TestTokensRequestLimit (4 tests) - TASK 40.2

| Test | Purpose |
|------|---------|
| `test_estimate_chunks_hybrid_mode` | Hybrid mode works with both limits |
| `test_hybrid_respects_lines_limit` | Lines limit respected in hybrid |
| `test_hybrid_respects_tokens_limit` | Tokens limit respected in hybrid |
| `test_estimate_chunks_modes` | All three modes (lines/tokens/hybrid) work |

#### TestPromptOverhead (3 tests) - TASK 40.3

| Test | Purpose |
|------|---------|
| `test_build_prompt_preview_exists` | build_prompt_preview importable |
| `test_build_prompt_preview_returns_text` | Returns PromptPreviewView with content |
| `test_count_tokens_function` | count_tokens returns positive value |

#### TestDualEstimation (5 tests) - TASK 40.4

| Test | Purpose |
|------|---------|
| `test_estimation_state_structure` | _estimation_state has correct keys |
| `test_estimation_result_dataclass` | EstimationResult fields correct |
| `test_comparison_result_dataclass` | ComparisonResult fields correct |
| `test_reset_estimation_method_exists` | reset_estimation method exists |
| `test_reset_estimation_signature` | Accepts reset_preprocessed_only param |

#### TestDualTicks (7 tests) - TASK 40.5

| Test | Purpose |
|------|---------|
| `test_step_row_accepts_dual_ticks` | StepRow accepts dual_ticks param |
| `test_progress_panel_has_dual_tick_api` | ProgressPanel has set/clear/get methods |
| `test_dual_tick_icons_unchecked` | ☐☐ when both False |
| `test_dual_tick_icons_first_checked` | ☑☐ when first True |
| `test_dual_tick_icons_both_checked` | ☑☑ when both True |
| `test_single_tick_unchanged` | Standard ✓ when dual_ticks is None |
| `test_skipped_icon_with_no_dual` | ⊘ icon when skipped, no dual ticks |

#### TestModelComparisonColumns (4 tests) - TASK 40.6

| Test | Purpose |
|------|---------|
| `test_model_pricing_has_all_models` | Expected models present in MODEL_PRICING |
| `test_model_pricing_structure` | Each model has name, input, output |
| `test_estimate_cost_function` | Returns dict with cost breakdown |
| `test_estimate_cost_different_models` | Expensive models cost more |

#### TestTimeConcurrent (10 tests) - TASK 40.7

| Test | Purpose |
|------|---------|
| `test_model_pricing_has_concurrent` | concurrent field in all models |
| `test_model_pricing_has_token_speed` | token_speed field in all models |
| `test_estimate_rate_limit_time_signature` | Accepts concurrent/token params |
| `test_time_decrease_with_concurrency` | Higher concurrency → shorter time |
| `test_time_rate_limit_dominates` | Rate limit dominates when RPM low |
| `test_time_token_speed_dominates` | Token speed dominates for large output |
| `test_time_concurrent_dominates` | Concurrent throughput dominates |
| `test_time_zero_requests` | Zero requests → 0 seconds |
| `test_time_no_rate_limit` | RPM=0 → "No rate limit" |
| `test_time_with_buffer` | Buffer increases time |
| `test_time_formatted_string` | Non-empty formatted string |

#### TestPreprocessedLines (3 tests) - TASK 40.9

| Test | Purpose |
|------|---------|
| `test_costs_step_has_get_lines` | _get_lines method exists |
| `test_get_lines_returns_tuple` | Return annotation present |
| `test_manifest_prepro_fallback_in_source` | Checks manifest prepro[] entries |

#### TestCostsModuleIntegrity (5 tests) - Integration

| Test | Purpose |
|------|---------|
| `test_all_imports_resolve` | costs.py imports resolve |
| `test_all_imports_estimate_resolve` | estimate.py imports resolve |
| `test_costs_step_inherits_base` | CostsStep inherits BaseStep |
| `test_count_tokens_returns_tuple` | Returns (int, str) tuple |
| `test_update_dual_ticks_method_exists` | _update_dual_ticks method exists |

---

### dev/test_costs_api_rework.py (35 tests) - API Requests & Costs Rework

Tests for all 7 Costs/Translation rework tasks: cache calculation, mode buttons,
instant mode recalculation, model lock, settings decoupling, button rename,
and translation request mode selector.

#### TestCachedCostCalculation (8 tests)

| Test | Purpose |
|------|---------|
| `test_cache_hit_rate_constant_exists` | CACHE_HIT_RATE constant exists in costs module |
| `test_cache_hit_rate_value` | CACHE_HIT_RATE is 0.80 |
| `test_cache_hit_rate_range` | CACHE_HIT_RATE between 0 and 1 |
| `test_get_static_prompt_tokens_method` | _get_static_prompt_tokens method exists |
| `test_build_full_system_prompt_static_sections` | Static prompt sections are cacheable |
| `test_build_full_system_prompt_dynamic_sections` | Dynamic prompt sections identified |
| `test_cached_tokens_less_than_total` | Cached cost < total cost in estimation |
| `test_no_caching_below_threshold` | No caching when static prefix < 1024 tokens |

#### TestModeButtonLabels (3 tests)

| Test | Purpose |
|------|---------|
| `test_request_modes_defined` | REQUEST_MODES has 4 entries |
| `test_mode_button_labels_include_availability` | Labels include (Available)/(Unavailable) |
| `test_normal_mode_no_suffix` | Normal mode has no availability suffix |

#### TestModeCostRecalculation (3 tests)

| Test | Purpose |
|------|---------|
| `test_recalculate_method_exists` | _recalculate_costs_for_mode method exists |
| `test_select_mode_no_estimation` | Mode change does not trigger re-estimation |
| `test_mode_cost_updates_fields` | Mode change updates cost display fields |

#### TestModelLockDuringEstimation (2 tests)

| Test | Purpose |
|------|---------|
| `test_model_locked_during_estimation` | Model combo disabled during estimation |
| `test_model_unlocked_after_estimation` | Model combo re-enabled after estimation |

#### TestSettingsDecoupling (4 tests)

| Test | Purpose |
|------|---------|
| `test_no_load_on_model_change` | _on_model_changed does not call _load_model_settings |
| `test_settings_loaded_once_flag` | _settings_loaded_once attribute exists |
| `test_settings_loaded_on_enter` | on_enter loads settings from API.ini |
| `test_settings_reset_on_new_project` | on_new_project resets _settings_loaded_once flag |

#### TestSaveButtonRename (3 tests)

| Test | Purpose |
|------|---------|
| `test_button_text_apply` | Button text is "📤 Apply Settings to Model" |
| `test_one_way_docstring` | _save_settings mentions one-way write |
| `test_confirmation_text` | Confirmation shows "Applied" |

#### TestTranslationRequestMode (8 tests)

| Test | Purpose |
|------|---------|
| `test_translation_options_has_request_mode` | TranslationOptions has request_mode field |
| `test_request_mode_combo_built` | Request mode combobox exists in translate module |
| `test_request_mode_values` | Combobox has Normal/Batch/Flex/Priority values |
| `test_request_mode_change_handler` | _on_request_mode_changed method exists |
| `test_request_mode_refresh_method` | _refresh_request_mode_options method exists |
| `test_api_config_has_request_mode` | APIConfig dataclass has request_mode field |
| `test_api_client_mode_set_during_translation` | _do_translation sets request_mode on APIConfig |
| `test_get_model_pricing_imported` | get_model_pricing imported in translate module |

#### TestCostEstimationMath (4 tests)

| Test | Purpose |
|------|---------|
| `test_estimate_cost_returns_dict` | estimate_cost returns a dictionary |
| `test_estimation_result_fields` | EstimationResult has required fields |
| `test_mode_price_keys_normal` | Normal mode uses standard price keys |
| `test_model_setting_keys_include_request_mode` | _MODEL_SETTING_KEYS includes request_mode |

---

### dev/test_costs_additive_display.py (30 tests) - Additive Cost Display Rework

Tests for the purely additive cost display rework: ceil-to-cents rounding, content-only
input_cost, non-cached prompt token display, label layout, and additive total verification.

#### TestCeilToCents (5 tests)

| Test | Purpose |
|------|---------|
| `test_small_fraction_rounds_up` | $0.001 → $0.01 (rounds up to next cent) |
| `test_exact_cent_stays` | $0.05 stays $0.05 |
| `test_zero_stays_zero` | $0.00 stays $0.00 |
| `test_negative_stays_zero_or_negative` | Negative input does not produce positive |
| `test_large_value` | $12.344 → $12.35 |

#### TestFmtCost (3 tests)

| Test | Purpose |
|------|---------|
| `test_fmt_cost_dollar_prefix` | Result starts with "$" |
| `test_fmt_cost_two_decimals` | Result has exactly 2 decimal places |
| `test_fmt_cost_ceil` | Uses ceil-to-cents (not round) |

#### TestEstimationResultSemantics (2 tests)

| Test | Purpose |
|------|---------|
| `test_input_cost_is_content_only` | input_cost + prompt_cost + cached_input_cost + output_cost ≈ total_cost |
| `test_prompt_tokens_minus_cached_display` | prompt_tokens − cached_tokens ≥ 0 |

#### TestAdditiveCostCalculation (3 tests)

| Test | Purpose |
|------|---------|
| `test_four_components_sum_to_total` | content + prompt + cached + output = total |
| `test_total_matches_old_approach` | New split produces same total as old bundled approach |
| `test_no_caching_prompt_equals_full` | When cached_tokens=0, prompt_cost covers full prompt |

#### TestRecalculateStructure (4 tests)

| Test | Purpose |
|------|---------|
| `test_recalculate_uses_content_tokens` | Source code references content_tokens for input_cost |
| `test_recalculate_uses_fmt_cost` | Source code uses _fmt_cost for display |
| `test_reprice_uses_content_tokens` | _reprice_for_model uses content_tokens |
| `test_reprice_uses_fmt_cost` | _reprice_for_model uses _fmt_cost |

#### TestPromptTokenDisplay (3 tests)

| Test | Purpose |
|------|---------|
| `test_update_ui_subtracts_cached_from_prompt` | _update_ui shows prompt − cached |
| `test_prompt_saved_uses_non_cached` | Saved column uses non-cached delta |
| `test_non_cached_ge_zero` | Non-cached prompt tokens ≥ 0 |

#### TestCostLabelLayout (3 tests)

| Test | Purpose |
|------|---------|
| `test_prompt_cost_no_indent` | "Prompt Cost:" label has no leading spaces |
| `test_cached_cost_no_indent` | "Cached Cost:" label has no leading spaces |
| `test_cached_label_renamed` | Label is "Cached Cost:" not "Cached Input Cost:" |

#### TestCostDisplayAlwaysShown (3 tests)

| Test | Purpose |
|------|---------|
| `test_recalculate_always_shows_prompt` | _recalculate always configures prompt cost label |
| `test_recalculate_always_shows_cached` | _recalculate always configures cached cost label |
| `test_no_conditional_dash_hide` | No `configure(text="-")` pattern for cost rows |

#### TestDoEstimationCalculation (3 tests)

| Test | Purpose |
|------|---------|
| `test_do_estimation_no_estimate_cost_call` | _do_estimation does not call estimate_cost() for cache path |
| `test_do_estimation_has_content_cost` | _do_estimation computes orig_content_cost |
| `test_do_estimation_four_components` | _do_estimation sums 4 components to total |

#### TestCostsAdditiveDisplayTestCount (1 test)

| Test | Purpose |
|------|---------|
| `test_total_test_count` | Verifies exactly 30 tests in the file |

---

### dev/test_estimate_manifest.py (33 tests)

Estimation and Analysis step manifest integration for Phase 25.

#### TestInputLinesField (3 tests) - TASK 25.1

| Test | Purpose |
|------|---------|
| `test_save_input_lines_to_manifest` | Saves InputLines to manifest |
| `test_load_input_lines_from_manifest` | Loads InputLines from manifest |
| `test_input_lines_default_value` | Default value is 0 |

#### TestInputTokensField (3 tests) - TASK 25.1

| Test | Purpose |
|------|---------|
| `test_save_input_tokens_to_manifest` | Saves InputTokens to manifest |
| `test_load_input_tokens_from_manifest` | Loads InputTokens from manifest |
| `test_input_tokens_default_value` | Default value is 0 |

#### TestOutputTokensField (3 tests) - TASK 25.1

| Test | Purpose |
|------|---------|
| `test_save_output_tokens_to_manifest` | Saves OutputTokens to manifest |
| `test_load_output_tokens_from_manifest` | Loads OutputTokens from manifest |
| `test_output_tokens_default_value` | Default value is 0 |

#### TestAnalysisResultsRoundtrip (2 tests) - TASK 25.1

| Test | Purpose |
|------|---------|
| `test_all_fields_roundtrip` | Save/load all analysis fields |
| `test_large_token_values` | Handles large token values |

#### TestTask251Integration (3 tests) - TASK 25.1

| Test | Purpose |
|------|---------|
| `test_estimation_step_has_manifest_fields` | EstimationStep has save methods |
| `test_analysis_step_has_manifest_fields` | AnalysisStep has save methods |
| `test_manifest_data_structure` | Verifies manifest structure |

#### TestValidationRulesPlaceholderPreservation (3 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_save_placeholder_preservation` | Saves to ValidationRules |
| `test_load_placeholder_preservation` | Loads from ValidationRules |
| `test_placeholder_preservation_default_true` | Default is true |

#### TestValidationRulesAnchorPreservation (2 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_save_anchor_preservation` | Saves to ValidationRules |
| `test_anchor_preservation_default_true` | Default is true |

#### TestValidationRulesJapaneseCharDetection (2 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_save_japanese_char_detection` | Saves to ValidationRules |
| `test_japanese_char_detection_default_true` | Default is true |

#### TestValidationRulesSpeakerFormat (2 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_save_speaker_format` | Saves to ValidationRules |
| `test_speaker_format_default_true` | Default is true |

#### TestValidationRulesQuoteBalance (2 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_save_quote_balance` | Saves to ValidationRules |
| `test_quote_balance_default_true` | Default is true |

#### TestValidationRulesEmptyTranslation (2 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_save_empty_translation` | Saves to ValidationRules |
| `test_empty_translation_default_true` | Default is true |

#### TestValidationRulesAllDefaults (2 tests) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_all_validation_rules_default_true` | All rules default to true |
| `test_validation_rules_persist` | Rules persist after save/load |

#### TestTask252Integration (1 test) - TASK 25.2

| Test | Purpose |
|------|---------|
| `test_validation_rules_nested_structure` | ValidationRules nested structure |

#### TestEdgeCases (3 tests) - TASK 25.1

| Test | Purpose |
|------|---------|
| `test_zero_lines` | Handles zero lines |
| `test_negative_values_clamped` | Negative values clamped to 0 |
| `test_string_conversion` | String values converted to int |

---

### dev/test_qa_manifest.py (19 tests)

QA step manifest integration for Phase 26 Task 26.1.

#### TestQAOptionsRerunPolicy (5 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_save_rerun_policy_failed_only` | Saves FailedOnly policy |
| `test_save_rerun_policy_all` | Saves All policy |
| `test_save_rerun_policy_none` | Saves None policy |
| `test_load_rerun_policy` | Loads RerunPolicy |
| `test_rerun_policy_default_failed_only` | Default is FailedOnly |

#### TestQAOptionsMaxSourceLanguageChars (4 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_save_max_source_language_chars` | Saves to manifest |
| `test_load_max_source_language_chars` | Loads from manifest |
| `test_max_source_language_chars_default_4` | Default is 4 |
| `test_max_source_language_chars_clamped` | Values clamped to min 0 |

#### TestQAOptionsMaxLineLength (4 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_save_max_line_length` | Saves to manifest |
| `test_load_max_line_length` | Loads from manifest |
| `test_max_line_length_default_0` | Default is 0 (disabled) |
| `test_max_line_length_zero_disables` | Zero disables check |

#### TestQAOptionsAllFields (2 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_all_qa_options_roundtrip` | All fields save/load |
| `test_qa_options_nested_structure` | QAOptions nested under manifest |

#### TestTask261Integration (2 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_qa_step_has_imports` | QAStep has binding imports |
| `test_qa_options_coexist_with_validation_rules` | Both sections coexist |

#### TestQAStageInputResolution (2 tests)

| Test | Purpose |
|------|---------|
| `test_qa_uses_wordwrap_chain_for_original_column` | QA original column uses postpro → tl → prepro → orig |
| `test_qa_overwrite_falls_back_to_wordwrap_chain_when_empty` | Overwrite column loads only qa_overwrite and stays empty when none is stored |

---

### dev/test_translate_manifest.py (47 tests)

Translation step manifest integration for Phase 26 Task 26.2.

#### TestRequestOptionsModel (3 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_model_field_save_to_manifest` | Saves Model to manifest |
| `test_model_field_load_from_manifest` | Loads Model from manifest |
| `test_model_field_default_when_missing` | Default is empty string |

#### TestRequestOptionsTemperature (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_temperature_field_save_to_manifest` | Saves Temperature (float) |
| `test_temperature_field_load_from_manifest` | Loads Temperature |
| `test_temperature_field_default_when_missing` | Default is 0.2 |
| `test_temperature_field_zero_value` | Handles zero value |

#### TestRequestOptionsLinesPerChunk (3 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_lines_per_chunk_save_to_manifest` | Saves LinesPerChunk |
| `test_lines_per_chunk_load_from_manifest` | Loads LinesPerChunk |
| `test_lines_per_chunk_default_when_missing` | Default is 30 |

#### TestRequestOptionsRetryStrategy (3 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_retry_strategy_save_to_manifest` | Saves RetryStrategy |
| `test_retry_strategy_load_batch` | Loads Batch strategy |
| `test_retry_strategy_load_line` | Loads Line strategy |

#### TestRequestOptionsMaxRetries (3 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_max_retries_save_to_manifest` | Saves MaxRetries |
| `test_max_retries_load_from_manifest` | Loads MaxRetries |
| `test_max_retries_default_when_missing` | Default is 3 |

#### TestRequestOptionsEnableRequestCaching (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_caching_enabled_save_to_manifest` | Saves true value |
| `test_caching_disabled_save_to_manifest` | Saves false value |
| `test_caching_load_from_manifest` | Loads value |
| `test_caching_default_when_missing` | Default is true |

#### TestRequestOptionsLineByLineMode (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_line_by_line_enabled_save_to_manifest` | Saves true value |
| `test_line_by_line_disabled_save_to_manifest` | Saves false value |
| `test_line_by_line_load_from_manifest` | Loads value |
| `test_line_by_line_default_when_missing` | Default is false |

#### TestRequestOptionsContextLines (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_context_lines_save_to_manifest` | Saves ContextLines |
| `test_context_lines_load_from_manifest` | Loads ContextLines |
| `test_context_lines_default_when_missing` | Default is 2 |
| `test_context_lines_zero_value` | Handles zero value |

#### TestRequestOptionsThinking (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_thinking_enabled_save_to_manifest` | Saves true value |
| `test_thinking_disabled_save_to_manifest` | Saves false value |
| `test_thinking_load_from_manifest` | Loads value |
| `test_thinking_default_when_missing` | Default is false |

#### TestRequestOptionsThinkingBudget (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_thinking_budget_save_to_manifest` | Saves ThinkingBudget |
| `test_thinking_budget_load_from_manifest` | Loads ThinkingBudget |
| `test_thinking_budget_default_when_missing` | Default is 10000 |
| `test_thinking_budget_minimum_value` | Handles minimum value (1000) |

#### TestRequestOptionsAllFields (2 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_all_fields_roundtrip` | All 10 fields save/load |
| `test_all_fields_defaults` | All defaults correct |

#### TestTask262Integration (4 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_translate_step_has_manifest_bindings_list` | TranslationStep has _manifest_bindings |
| `test_translate_step_has_load_request_options_method` | Has _load_request_options_from_manifest |
| `test_translate_step_has_save_temperature_method` | Has _save_temperature_to_manifest |
| `test_translate_step_on_enter_calls_load_request_options` | on_enter calls load method |

#### TestRequestOptionsEdgeCases (5 tests) - TASK 26.2

| Test | Purpose |
|------|---------|
| `test_temperature_high_value` | Max temperature 2.0 |
| `test_lines_per_chunk_minimum_value` | Min chunk size 5 |
| `test_lines_per_chunk_maximum_value` | Max chunk size 100 |
| `test_max_retries_maximum_value` | Max retries 10 |
| `test_thinking_budget_maximum_value` | Max budget 100000 |
| `test_code_pattern_with_missing_fields` | CodePattern defaults |
| `test_character_with_missing_fields` | CharacterInfo defaults |

---

### dev/test_postprocess_manifest.py (35 tests)

Postprocessing step manifest integration tests. Verifies all 9 PostProcessing
fields (8 boolean toggles + 1 failure handling enum) are properly bound.

**Files Tested:** `gui/steps/postprocess.py`

#### TestPostProcessingPlaceholderRecovery (3 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_placeholder_recovery_save_to_manifest` | Saves PlaceholderRecovery |
| `test_placeholder_recovery_load_from_manifest` | Loads PlaceholderRecovery |
| `test_placeholder_recovery_default_true` | Default is True |

#### TestPostProcessingBracketBalanceRecovery (2 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_bracket_balance_save_to_manifest` | Saves BracketBalanceRecovery |
| `test_bracket_balance_load_from_manifest` | Loads BracketBalanceRecovery |

#### TestPostProcessingQuoteBalanceRecovery (2 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_quote_balance_save_to_manifest` | Saves QuoteBalanceRecovery |
| `test_quote_balance_load_from_manifest` | Loads QuoteBalanceRecovery |

#### TestPostProcessingWhitespaceNormalization (2 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_whitespace_save_to_manifest` | Saves WhitespaceNormalization |
| `test_whitespace_load_from_manifest` | Loads WhitespaceNormalization |

#### TestPostProcessingRestoreCodeCharacters (2 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_restore_code_save_to_manifest` | Saves RestoreCodeCharacters |
| `test_restore_code_load_from_manifest` | Loads RestoreCodeCharacters |

#### TestPostProcessingRestoreLinebreaks (2 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_restore_linebreaks_save_to_manifest` | Saves RestoreLinebreaks |
| `test_restore_linebreaks_load_from_manifest` | Loads RestoreLinebreaks |

#### TestPostProcessingEnableSymbolConversion (3 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_symbol_conversion_save_to_manifest` | Saves EnableSymbolConversion |
| `test_symbol_conversion_load_from_manifest` | Loads EnableSymbolConversion |
| `test_symbol_conversion_default_true` | Default is True |

#### TestPostProcessingFullwidthToHalfwidth (3 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_fullwidth_save_to_manifest` | Saves FullwidthToHalfwidth |
| `test_fullwidth_load_from_manifest` | Loads FullwidthToHalfwidth |
| `test_fullwidth_default_true` | Default is True |

#### TestPostProcessingFailureHandling (5 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_failure_handling_save_skip` | Saves FailureHandling=skip |
| `test_failure_handling_save_flag` | Saves FailureHandling=flag |
| `test_failure_handling_save_retry` | Saves FailureHandling=retry |
| `test_failure_handling_load_from_manifest` | Loads FailureHandling |
| `test_failure_handling_default_skip` | Default is "skip" |

#### TestPostProcessingAllFields (2 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_all_fields_save_and_load` | All 9 fields roundtrip |
| `test_postprocessing_field_count` | Verifies 9 fields stored |

#### TestTask271Integration (4 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_postprocessing_step_has_manifest_bindings_list` | PostprocessingStep has _manifest_bindings |
| `test_postprocessing_step_has_load_method` | Has _load_postprocessing_options_from_manifest |
| `test_postprocessing_step_has_save_failure_policy_method` | Has _save_failure_policy_to_manifest |
| `test_postprocessing_step_imports_binding_functions` | Imports binding functions |

#### TestPostProcessingEdgeCases (5 tests) - TASK 27.1

| Test | Purpose |
|------|---------|
| `test_toggle_state_roundtrip` | Toggle states survive roundtrip |
| `test_failure_policy_roundtrip` | All 3 policies roundtrip |
| `test_mixed_boolean_states` | Mixed True/False states |
| `test_none_manifest_manager_no_error` | None manager handled |
| `test_empty_section_creates_structure` | Creates nested structure |

---

### dev/test_wordwrap_manifest.py

Wordwrap step manifest integration tests. Verifies current WordwrapSettings
fields, including PrettyWrap and per-format FormatConfigs, are properly bound for session persistence.

**Files Tested:** `gui/steps/wordwrap_overwrite.py`

#### TestWordwrapSettingsMode (5 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_mode_save_manual` | Saves Mode=manual |
| `test_mode_save_rpgmaker` | Saves Mode=rpgmaker |
| `test_mode_save_disabled` | Saves Mode=disabled |
| `test_mode_load_from_manifest` | Loads Mode |
| `test_mode_default_manual` | Default is "manual" |

#### TestWordwrapSettingsWidth (4 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_width_save_default` | Saves Width=48 |
| `test_width_save_custom` | Saves custom width |
| `test_width_load_from_manifest` | Loads Width |
| `test_width_default_48` | Default is 48 |

#### TestWordwrapSettingsBreakChar (3 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_break_char_save_newline` | Saves BreakChar=\\n |
| `test_break_char_save_br` | Saves BreakChar=<br> |
| `test_break_char_load_from_manifest` | Loads BreakChar |

#### TestWordwrapSettingsMaxLines (3 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_max_lines_save_default` | Saves MaxLines=4 |
| `test_max_lines_save_unlimited` | Saves MaxLines=0 |
| `test_max_lines_load_from_manifest` | Loads MaxLines |

#### TestWordwrapSettingsPrettyWrap - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_pretty_wrap_save_true` | Saves PrettyWrap=True |
| `test_pretty_wrap_save_false` | Saves PrettyWrap=False |
| `test_pretty_wrap_load_from_manifest` | Loads PrettyWrap |
| `test_pretty_wrap_default_true` | Default is True |

#### TestWordwrapSettingsFormatConfigs - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_format_configs_save_and_load` | Saves and loads FormatConfigs |
| `test_format_configs_default_empty` | Default list is empty |

#### TestWordwrapSettingsSpeakerHandling (3 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_speaker_handling_save_sameline` | Saves SpeakerHandling=sameline |
| `test_speaker_handling_save_newline` | Saves SpeakerHandling=newline |
| `test_speaker_handling_load_from_manifest` | Loads SpeakerHandling |

#### TestWordwrapSettingsTypography (3 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_typography_save_western` | Saves Typography=western |
| `test_typography_save_japanese` | Saves Typography=japanese |
| `test_typography_load_from_manifest` | Loads Typography |

#### TestWordwrapSettingsAllFields (2 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_all_fields_roundtrip` | Current Wordwrap settings save/load together |
| `test_wordwrap_settings_field_count` | Verifies current field set stored |

#### TestTask281Integration (5 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_wordwrap_step_has_manifest_bindings_list` | Has _manifest_bindings |
| `test_wordwrap_step_has_load_method` | Has load method |
| `test_wordwrap_step_has_save_mode_method` | Has save mode method |
| `test_wordwrap_step_has_save_speaker_method` | Has save speaker method |
| `test_wordwrap_step_imports_binding_functions` | Imports binding functions |

#### TestWordwrapSettingsEdgeCases (5 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_width_min_boundary` | Width minimum 20 |
| `test_width_max_boundary` | Width maximum 200 |
| `test_max_lines_zero_unlimited` | MaxLines=0 unlimited |
| `test_settings_roundtrip` | Settings survive roundtrip |
| `test_empty_section_creates_structure` | Creates nested structure |

---

### dev/test_tag_wordwrap.py

Per-tag wordwrap settings, parser pretty_wrap hook, manifest TagConfigs/FormatConfigs, and tag resolution tests.

**Files Tested:** `gui/steps/wordwrap_overwrite.py`, `functions/manifest_manager.py`, `formats/parser_base.py`, `formats/LightVN.py`

#### TestBuildSourcePaths (4 tests)

| Test | Purpose |
|------|---------|
| `test_suffix_match` | Suffix-based path resolution (subdir/file.txt) |
| `test_subdir_resolution` | Subdirectory paths resolve correctly |
| `test_cross_contamination` | Same-name files in different subdirs don't collide |
| `test_ambiguity` | Ambiguous filename-only match uses unambiguous fallback |

#### TestTagConfigsManifest

| Test | Purpose |
|------|---------|
| `test_empty_default` | New manifest has `TagConfigs: []` |
| `test_set_get_roundtrip` | set/get_wordwrap_tag_configs roundtrip |
| `test_dirty_flag` | Setting tag configs marks manifest dirty |
| `test_tag_configs_key` | TagConfigs key exists in WordwrapSettings |
| `test_pretty_wrap_flag_roundtrip` | PrettyWrap persists in tag configs |
| `test_format_configs_roundtrip` | FormatConfigs persist in WordwrapSettings |

#### TestPrettyWrapHook (12 tests)

| Test | Purpose |
|------|---------|
| `test_base_returns_none` | ParserScript.pretty_wrap returns None |
| `test_null_parser_info` | NullParser has_custom_pretty_wrap=False |
| `test_stub_parser_info` | StubParser has_custom_pretty_wrap=True |
| `test_lightvn_pretty_wrap` | LightVN pretty_wrap returns wrapped string |
| `test_lightvn_width_respect` | Width parameter respected |
| `test_lightvn_max_lines` | max_lines truncation works |
| `test_lightvn_break_char` | Custom break_char used |
| `test_lightvn_short_text` | Short text returned unchanged |
| `test_lightvn_empty` | Empty text returns empty |
| `test_lightvn_zero_width` | Width=0 returns text unchanged |
| `test_lightvn_info` | LightVN info() has_custom_pretty_wrap=True |
| `test_lightvn_info_has_wordwrap` | LightVN info() has_custom_wordwrap=True |

#### TestTagWrapConfig (5 tests)

| Test | Purpose |
|------|---------|
| `test_defaults` | Default values (width=48, max_lines=4, speaker=count) |
| `test_to_dict` | Serialization to dict with all new fields |
| `test_new_fields` | speaker_handling, prevent_orphans, prefer_punct_breaks, new_textbox in dict |
| `test_roundtrip` | to_dict→from_dict roundtrip |
| `test_missing_keys` | from_dict handles missing keys gracefully |

#### TestDefaultTagConfigs (3 tests)

| Test | Purpose |
|------|---------|
| `test_has_dialogue_and_menu` | DEFAULT_TAG_CONFIGS has dialogue + menu |
| `test_dialogue_defaults` | Dialogue: width=48, max_lines=4 |
| `test_menu_defaults` | Menu: width=48, max_lines=0 |

#### TestTagResolution (3 tests)

| Test | Purpose |
|------|---------|
| `test_line_tag_overrules_filedir` | Line tag takes priority over filedir type |
| `test_filedir_used` | Filedir type used when no line tag |
| `test_dialogue_fallback` | Falls back to "dialogue" when neither present |

#### TestParserCapabilityDetection (3 tests)

| Test | Purpose |
|------|---------|
| `test_lightvn_both` | LightVN has both O6 and O9 |
| `test_stub_pretty_only` | StubParser has O9 only |
| `test_null_neither` | NullParser has neither |

#### TestPrettyWrapIntegration (5 tests)

| Test | Purpose |
|------|---------|
| `test_stub_wraps` | StubParser pretty_wrap produces wrapped output |
| `test_max_lines` | pretty_wrap max_lines truncation |
| `test_lightvn_for_tag_dialogue` | LightVN wordwrap_for_tag("dialogue") returns config |
| `test_lightvn_for_tag_menu` | LightVN wordwrap_for_tag("menu") returns no-wrap config |
| `test_wordwrap_for_tag_items_no_wrap` | LightVN wordwrap_for_tag("items") returns no-wrap config |

#### TestImportTranslationCompat (3 tests)

| Test | Purpose |
|------|---------|
| `test_old_manifest` | Old manifest without TagConfigs returns [] |
| `test_copy_preserves` | Full copy preserves TagConfigs |
| `test_backward_compat` | Graceful degradation for old manifests |

#### TestCollectAvailableTags (3 tests)

| Test | Purpose |
|------|---------|
| `test_always_dialogue_menu` | Always includes dialogue + menu |
| `test_filedir_types` | Filedir types appear in available tags |
| `test_line_tags` | Line tags appear in available tags |

#### TestEdgeCases (7 tests)

| Test | Purpose |
|------|---------|
| `test_width_zero` | Width=0 means no wrap |
| `test_single_word` | Single word longer than width |
| `test_variable_tag` | Variable tag behaviour |
| `test_parser_defaults_editable` | Parser-provided defaults are still editable |
| `test_new_textbox_injection` | NewTextboxInjection serializes correctly |
| `test_no_max_lines` | max_lines=0 means unlimited |
| `test_empty_dict` | from_dict with empty dict uses defaults |

```bash
# Run tag wordwrap tests
python -m pytest dev/test_tag_wordwrap.py -v --timeout=60
```

---

### test_output_manifest.py (48 tests) - TASK 28.2

Output step manifest integration tests. Verifies that OutputInjectStep binds all output format settings to ManifestManager for unified state persistence.

**Bindings Tested:**
- OutputFormat.Destination (entry, default "Same as Source")
- OutputFormat.PreserveFolderStructure (checkbox, default true)
- OutputFormat.Format (combobox, default "txt")
- OutputFormat.PairMode (combobox, default "custom")
- OutputFormat.Encoding (combobox, default "utf-8")
- OutputFormat.FileNaming (radio buttons via trace)
- OutputFormat.TextOption (entry, default "translated")
- OutputFormat.OverwriteExistingFiles (checkbox, default true)
- OutputFormat.Backup (combobox, default "timestamp")
- OutputFormat.BackupExtension (entry, default ".bk")
- OutputFormat.ExportManifestFile (checkbox, default false)
- OutputFormat.ExportProcessingLogs (checkbox, default false)
- OutputFormat.ExportGlossaryEntries (checkbox, default false)

#### TestOutputManifestBindings (27 tests) - TASK 28.2

---

### dev/test_new_project_flush.py (45 tests)

Validates that File → New Project fully flushes all cached state from every step tab,
preventing old project data from leaking into a new session.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestManifestManagerClose | 7 | ManifestManager.close() resets path, dirty, step, lines, filedir, characters, code_patterns |
| TestResetManifestManager | 3 | reset_manifest_manager() returns new instance with empty state |
| TestBaseStepOnNewProject | 1 | BaseStep.on_new_project() invalidates cache hash |
| TestInputStepNewProject | 7 | InputExtractionStep clears _loaded_files, _current_file_index, _folder_root, _tree_item_to_index, _pending_project_name; calls UI stubs; invalidates cache |
| TestAnalysisStepNewProject | 5 | AnalysisStep clears _analysis_results, _is_analyzing, _instance_rows, _expanded_parents, _findings_rows |
| TestCostsStepNewProject | 5 | CostsStep clears _estimation_result, _is_estimating, _lines_original, _lines_preprocessed, resets _estimation_state |
| TestTranslationStepNewProject | 5 | TranslationStep clears _lines, _cancel_requested, _pause_requested, _api_client, _manifest_bindings |
| TestPostprocessStepNewProject | 3 | PostprocessStep clears _lines, _selected_line_idx, _validation_result |
| TestWordwrapStepNewProject | 2 | WordwrapStep clears _lines, _selected_line_idx |
| TestQAStepNewProject | 2 | QAStep clears _lines, _selected_line_idx |
| TestOutputStepNewProject | 3 | OutputStep clears _files, _cancel_requested, _selected_file_idx |
| TestNewProjectFlushIntegration | 2 | All steps have on_new_project(); ManifestManager empty after reset |

```bash
# Run New Project flush tests
python -m pytest CherryAI/dev/test_new_project_flush.py -v --timeout=10
```

---

### dev/test_input_dialog_ui.py (5 tests)

Source-level inspection tests that validate UI fixes in UnifiedInputDialog without
requiring a Tkinter display (no GUI instantiation needed).

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestUpButtonText | 2 | Up button uses plain Unicode arrow ↑ (U+2191), not emoji ⬆️; text is compact with single space |
| TestAutoPipelineHidden | 3 | Pipeline widgets not packed (hidden); _pipeline_var created; pipeline_cb combobox created |

---

### dev/test_io_examples.py (63 tests)

Comprehensive tests for I/O example generation, language resolution, prompt builder
integration, metadata persistence, manifest default seeding, cache configuration,
static prompt consistency, and fill mode calculation. No GUI or API required.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestGenerateIoExamples | 13 | Returns (str, int) tuple; zero/negative target yields empty; 1500/2500 token budgets within ±100; 2500 > 1500; output contains Input/Output JSON blocks; sequential LineN keys; Input/Output line number pairing; globally unique line numbers across blocks; code pattern boosting; no patterns fallback; small budget yields at least one block |
| TestLanguageResolution | 11 | JP→EN default (jp, en); EN→JP reversed (en, jp); unknown source + EN target → jp fallback; JP source + unknown target → en fallback; both unknown, no English → en+jp tiebreak; EN source + unknown target → jp; case-insensitive; keys always distinct across all combinations; EN→JP generation produces swapped roles; JP→EN uses English in output |
| TestCalculateFillTarget | 3 | Small static returns positive fill target; large static returns 0; at-threshold returns small positive |
| TestOptimalCacheSize | 3 | OpenAI default 1536; unknown provider fallback; optimal_cache_size in _MODEL_SETTING_KEYS |
| TestPromptBuilderIoExamples | 7 | Disabled mode preserves all SI content; 1500 mode generates io_examples section; SI unchanged when generating (never stripped); IO placed between SI and Style; fill mode; 2500 mode; io_examples in _STATIC_PROMPT_SECTIONS |
| TestProjectMetadataPersistence | 7 | si_preset survives to_dict/from_dict roundtrip; si_preset defaults to "Default"; io_examples survives to_dict/from_dict roundtrip; io_examples defaults to "disabled"; full roundtrip preserves both fields |
| TestManifestDefaultSeeding | 4 | _get_info_defaults() includes system_instructions, si_preset="Default", io_examples="disabled", source/target languages |
| TestEstimateTokens | 4 | Empty string yields 0; English text yields positive count; Japanese text yields positive count; Japanese tokens > English tokens for same character length |
| TestStaticPromptConsistency | 8 | Static prefix identical across different chunks; all enabled sections present in breakdown; IO examples deterministic (same params → same output); LineN keys consistent across calls; fill mode uses full static tokens (fewer IO tokens when other sections present); fill respects optimal cache size boundary; no dynamic content without chunks; breakdown non-dynamic keys match _STATIC_PROMPT_SECTIONS |
| TestFillModeCalculation | 4 | Empty prompt fills most of optimal cache; at-optimal static returns 0; fill target never negative; more static content (style+tone) → less IO fill |

```bash
# Run I/O examples tests
python -m pytest CherryAI/dev/test_io_examples.py -v --timeout=10
```

```bash
# Run Input Dialog UI tests
python -m pytest CherryAI/dev/test_input_dialog_ui.py -v --timeout=10
```

| Test | Purpose |
|------|---------|
| `test_output_step_has_manifest_bindings_list` | Has _manifest_bindings |
| `test_preserve_folder_structure_default_true` | Default true |
| `test_preserve_folder_structure_binding_saves_to_manifest` | Saves to manifest |
| `test_format_default_txt` | Default "txt" |
| `test_format_binding_saves_to_manifest` | Saves to manifest |
| `test_pair_mode_default_translated_only` | Default "translated_only" |
| `test_pair_mode_binding_saves_to_manifest` | Saves to manifest |
| `test_encoding_default_utf8` | Default "utf-8" |
| `test_encoding_binding_saves_to_manifest` | Saves to manifest |
| `test_file_naming_default_suffix` | Default "suffix" |
| `test_file_naming_binding_saves_to_manifest` | Saves to manifest |
| `test_file_naming_subfolder_saves_to_manifest` | Subfolder saves |
| `test_text_option_default_translated` | Default "_translated" |
| `test_text_option_binding_saves_to_manifest` | Saves to manifest |
| `test_overwrite_existing_files_default_false` | Default false |
| `test_overwrite_existing_files_binding_saves_to_manifest` | Saves to manifest |
| `test_backup_default_timestamp` | Default "timestamp" |
| `test_backup_binding_saves_to_manifest` | Saves to manifest |
| `test_backup_extension_default_bak` | Default ".bak" |
| `test_backup_extension_binding_saves_to_manifest` | Saves to manifest |
| `test_export_manifest_file_default_false` | Default false |
| `test_export_manifest_file_binding_saves_to_manifest` | Saves to manifest |
| `test_export_processing_logs_default_false` | Default false |
| `test_export_processing_logs_binding_saves_to_manifest` | Saves to manifest |
| `test_export_glossary_entries_default_false` | Default false |
| `test_export_glossary_entries_binding_saves_to_manifest` | Saves to manifest |
| `test_export_options_all_default_false` | All export options default false |

#### TestOutputManifestLoad (14 tests) - TASK 28.2

| Test | Purpose |
|------|---------|
| `test_load_preserve_folder_structure_from_manifest` | Loads PreserveFolderStructure |
| `test_load_format_from_manifest` | Loads Format |
| `test_load_pair_mode_from_manifest` | Loads PairMode |
| `test_load_encoding_from_manifest` | Loads Encoding |
| `test_load_file_naming_from_manifest` | Loads FileNaming |
| `test_load_text_option_from_manifest` | Loads TextOption |
| `test_load_overwrite_from_manifest` | Loads OverwriteExistingFiles |
| `test_load_backup_from_manifest` | Loads Backup |
| `test_load_backup_extension_from_manifest` | Loads BackupExtension |
| `test_load_export_manifest_from_manifest` | Loads ExportManifestFile |
| `test_load_export_logs_from_manifest` | Loads ExportProcessingLogs |
| `test_load_export_glossary_from_manifest` | Loads ExportGlossaryEntries |
| `test_load_all_settings_from_manifest` | Loads all settings |
| `test_load_default_when_field_missing` | Uses defaults for missing |

#### TestOutputManifestRoundtrip (1 test) - TASK 28.2

| Test | Purpose |
|------|---------|
| `test_roundtrip_all_settings` | Settings survive save/load roundtrip |

#### TestOutputManifestNoManager (3 tests) - TASK 28.2

| Test | Purpose |
|------|---------|
| `test_step_works_without_manifest_manager` | No crash without manager |
| `test_load_from_manifest_no_manager_does_not_raise` | Load method safe without manager |
| `test_file_naming_trace_without_manager` | Trace safe without manager |

#### TestOutputManifestBindingCount (1 test) - TASK 28.2

| Test | Purpose |
|------|---------|
| `test_correct_number_of_bindings` | Has 10 bindings (excludes radio trace) |

---

### test_autosave.py (24 tests) - TASK 29.1

ManifestManager autosave system tests. Verifies that autosave:
- Reads settings from INI file correctly
- Runs in background thread at specified interval
- Only saves when dirty flag is set
- Can be disabled via configuration
- Does not affect mainhelper manifest operations

#### TestAutosaveSettings (6 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_autosave_enabled_default_true` | Default enabled |
| `test_autosave_interval_default_15` | Default 15 seconds |
| `test_save_on_close_default_true` | Default save on close |
| `test_autosave_enabled_from_ini` | Reads from INI |
| `test_autosave_interval_clamped_min` | Min 5 seconds |
| `test_autosave_interval_clamped_max` | Max 300 seconds |

#### TestAutosaveThread (5 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_start_autosave_creates_thread` | Creates background thread |
| `test_stop_autosave_stops_thread` | Stops thread |
| `test_start_autosave_idempotent` | No duplicate threads |
| `test_stop_autosave_idempotent` | Safe multiple stops |
| `test_autosave_disabled_no_thread` | No thread when disabled |

#### TestAutosaveSaveOnDirty (2 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_autosave_saves_when_dirty` | Saves when dirty |
| `test_autosave_does_not_save_when_clean` | No save when clean |

#### TestAutosaveDisabled (2 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_disable_autosave_via_property` | Disable stops thread |
| `test_enable_autosave_via_property` | Enable starts thread |

#### TestAutosaveSaveOnClose (2 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_close_saves_when_dirty_and_enabled` | Saves on close |
| `test_close_does_not_save_when_disabled` | No save when disabled |

#### TestAutosaveProjectLifecycle (3 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_create_new_starts_autosave` | Start on create_new |
| `test_load_starts_autosave` | Start on load |
| `test_close_stops_autosave` | Stop on close |

#### TestAutosaveMainhelperIndependence (2 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_mainhelper_manifest_unaffected` | mainhelper.Manifest unchanged |
| `test_manifest_manager_autosave_isolated` | Isolated from mainhelper |

#### TestAutosaveThreadSafety (2 tests) - TASK 29.1

| Test | Purpose |
|------|---------|
| `test_concurrent_mark_dirty` | Thread-safe mark_dirty |
| `test_autosave_daemon_thread` | Thread is daemon |

### test_save_triggers.py (17 tests) - TASK 29.2

Save trigger functionality tests. Verifies that ManifestManager.save() is called
at critical points in the application lifecycle.

#### TestSaveOnClose (2 tests) - TASK 29.2

| Test | Purpose |
|------|---------|
| `test_app_on_close_saves_manifest` | Close saves manifest |
| `test_close_stops_autosave_thread` | Close stops thread |

#### TestSaveAfterFileLoad (3 tests) - TASK 29.2

| Test | Purpose |
|------|---------|
| `test_input_extract_step_has_save_method` | Method exists |
| `test_save_method_calls_manifest_save` | Correct signature |
| `test_on_load_files_calls_save_method` | Called in _on_load_files |

#### TestSaveBeforeTranslation (3 tests) - TASK 29.2

| Test | Purpose |
|------|---------|
| `test_translate_step_has_save_method` | Method exists |
| `test_save_method_calls_manifest_save` | Correct signature |
| `test_start_translation_calls_save_method` | Called in _start_translation |

#### TestSaveTriggerIntegration (3 tests) - TASK 29.2

| Test | Purpose |
|------|---------|
| `test_save_triggers_docstrings` | Docstrings mention TASK 29.2 |
| `test_save_methods_check_manifest_loaded` | Checks is_loaded |
| `test_save_methods_handle_exceptions` | Has try/except blocks |

#### TestSaveTriggerOrder (2 tests) - TASK 29.2

| Test | Purpose |
|------|---------|
| `test_file_load_save_after_project_creation` | Save after ensure_project_created |
| `test_translation_save_before_thread_start` | Save before Thread() |

#### TestSaveTriggerLogging (4 tests) - TASK 29.2

| Test | Purpose |
|------|---------|
| `test_file_load_save_logs_success` | Logs debug on success |
| `test_translation_save_logs_success` | Logs debug on success |
| `test_file_load_save_logs_failure` | Logs warning on failure |
| `test_translation_save_logs_failure` | Logs warning on failure |

### test_preset_manager.py (42 tests) - TASK 30.1

Preset manager tests. Verifies that presets can be saved, loaded, deleted,
and handles edge cases like quotes, unicode, and corrupted files.

#### TestPreset (4 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_preset_creation` | Create preset dataclass |
| `test_preset_to_dict` | Convert to dictionary |
| `test_preset_from_dict` | Create from dictionary |
| `test_preset_from_dict_missing_fields` | Handle missing fields |

#### TestPresetFile (10 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_preset_file_creation` | Create empty preset file |
| `test_preset_file_add_preset_new` | Add new preset |
| `test_preset_file_add_preset_update` | Update existing preset |
| `test_preset_file_get_preset` | Get preset by name |
| `test_preset_file_get_preset_not_found` | Get missing preset |
| `test_preset_file_delete_preset` | Delete preset |
| `test_preset_file_delete_preset_not_found` | Delete missing preset |
| `test_preset_file_get_names` | Get all names |
| `test_preset_file_to_dict` | Convert to dictionary |
| `test_preset_file_from_dict` | Create from dictionary |

#### TestPresetManagerBasics (3 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_singleton_instance` | Singleton pattern |
| `test_preset_types` | Supported types |
| `test_invalid_preset_type_raises` | Invalid type error |

#### TestSaveNewPreset (4 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_save_new_preset` | Save new preset |
| `test_save_multiple_presets` | Save multiple |
| `test_save_preset_empty_name_fails` | Empty name fails |
| `test_save_preset_whitespace_name_fails` | Whitespace name fails |

#### TestUpdateExistingPreset (2 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_update_existing_preset` | Update content |
| `test_update_preserves_other_presets` | Preserve others |

#### TestLoadPreset (3 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_load_preset_populates_field` | Load returns content |
| `test_load_preset_not_found` | Load missing returns None |
| `test_load_preset_from_fresh_manager` | File persistence |

#### TestDeletePreset (3 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_delete_preset` | Delete preset |
| `test_delete_preset_not_found` | Delete missing |
| `test_delete_preserves_other_presets` | Preserve others |

#### TestEscapeQuotes (4 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_escape_quotes_in_content` | Handle quotes |
| `test_content_with_newlines` | Handle newlines |
| `test_content_with_special_characters` | Handle special chars |
| `test_content_with_unicode` | Handle unicode |

#### TestDefaultPresets (3 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_style_has_default_presets` | Style defaults |
| `test_tone_has_default_presets` | Tone defaults |
| `test_prompt_has_default_presets` | Prompt defaults |

#### TestPresetExists (2 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_preset_exists_true` | Exists returns True |
| `test_preset_exists_false` | Missing returns False |

#### TestGetPresets (2 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_get_presets_returns_list` | Returns Preset list |
| `test_get_presets_includes_custom` | Includes custom |

#### TestFilePersistence (2 tests) - TASK 30.1

| Test | Purpose |
|------|---------|
| `test_presets_persist_across_manager_instances` | Persist across sessions |
| `test_corrupted_file_handled_gracefully` | Recover from corruption |

### test_preset_gui.py (21 tests) - TASK 30.2

GUI preset integration tests. Verifies that PresetManager is accessible
from GUI components and provides correct data for UI elements.

#### TestPresetUIExists (4 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_information_step_has_preset_manager` | Manager accessible |
| `test_preset_manager_has_style_type` | Style type supported |
| `test_preset_manager_has_tone_type` | Tone type supported |
| `test_preset_manager_has_prompt_type` | Prompt type supported |

#### TestPresetDropdown (3 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_preset_dropdown_shows_all_presets` | Style presets shown |
| `test_tone_dropdown_shows_all_presets` | Tone presets shown |
| `test_prompt_dropdown_shows_all_presets` | Prompt presets shown |

#### TestSaveButtonCreatesPreset (3 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_save_button_creates_preset` | Save creates preset |
| `test_save_preset_with_content` | Content saved correctly |
| `test_save_preset_updates_dropdown` | Dropdown updated |

#### TestDeletePresetUI (3 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_delete_removes_from_dropdown` | Delete removes |
| `test_delete_default_preset_not_recommended` | Defaults deletable |
| `test_delete_preserves_other_presets` | Others preserved |

#### TestPresetIntegration (2 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_preset_workflow_save_load_delete` | Full workflow |
| `test_preset_persistence` | Persistence across resets |

#### TestPresetHelperMethods (3 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_get_preset_names_returns_strings` | Returns strings |
| `test_preset_exists_for_validation` | Validation works |
| `test_get_presets_returns_preset_objects` | Returns Preset |

#### TestPresetNamingDialog (3 tests) - TASK 30.2

| Test | Purpose |
|------|---------|
| `test_empty_name_rejected` | Empty rejected |
| `test_whitespace_name_rejected` | Whitespace rejected |
| `test_duplicate_name_updates` | Duplicate updates |

---

### test_defaults.py (45 tests) - TASK 31.2

Tests for user defaults configuration system.

#### TestInitialDefaults (7 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_get_initial_default_string` | String initial default |
| `test_get_initial_default_bool` | Boolean initial default |
| `test_get_initial_default_int` | Integer initial default |
| `test_get_initial_default_float` | Float initial default |
| `test_get_initial_default_missing_key` | Missing key fallback |
| `test_get_initial_default_missing_section` | Missing section fallback |
| `test_get_all_initial_defaults` | Get all for section |

#### TestUserDefaults (6 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_set_user_default` | Setting user default |
| `test_get_user_default_not_set` | Fallback when not set |
| `test_has_user_default_true` | Check exists (true) |
| `test_has_user_default_false` | Check exists (false) |
| `test_save_as_user_defaults_multiple` | Save multiple at once |
| `test_get_all_user_defaults` | Get all for section |

#### TestEffectiveDefaults (4 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_effective_uses_user_default_when_set` | User overrides initial |
| `test_effective_uses_initial_when_no_user_default` | Initial when no user |
| `test_effective_uses_fallback_when_no_defaults` | Fallback when no defaults |
| `test_user_defaults_override_initial` | Complete override test |

#### TestClearRestoreDefaults (4 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_clear_user_defaults_specific_section` | Clear specific section |
| `test_clear_user_defaults_all` | Clear all sections |
| `test_restore_initial_defaults` | Restore all to initial |
| `test_restore_initial_defaults_section` | Restore specific section |

#### TestDefaultsPath (2 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_get_defaults_path` | Path resolution |
| `test_defaults_path_exists` | File existence check |

#### TestDefaultsCache (2 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_reload_defaults_cache` | Cache reload |
| `test_clear_cache_clears_defaults` | Clear clears defaults |

#### TestMissingDefaultsFile (1 test) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_missing_defaults_file_returns_fallback` | Graceful fallback |

#### TestBooleanConversion (15 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_boolean_conversion_variations[true-True]` | "true" → True |
| `test_boolean_conversion_variations[True-True]` | "True" → True |
| `test_boolean_conversion_variations[TRUE-True]` | "TRUE" → True |
| `test_boolean_conversion_variations[yes-True]` | "yes" → True |
| `test_boolean_conversion_variations[Yes-True]` | "Yes" → True |
| `test_boolean_conversion_variations[1-True]` | "1" → True |
| `test_boolean_conversion_variations[on-True]` | "on" → True |
| `test_boolean_conversion_variations[On-True]` | "On" → True |
| `test_boolean_conversion_variations[false-False]` | "false" → False |
| `test_boolean_conversion_variations[False-False]` | "False" → False |
| `test_boolean_conversion_variations[no-False]` | "no" → False |
| `test_boolean_conversion_variations[0-False]` | "0" → False |
| `test_boolean_conversion_variations[off-False]` | "off" → False |
| `test_boolean_conversion_variations[-False]` | "" → False |
| `test_boolean_conversion_variations[anything_else-False]` | Unknown → False |

#### TestTypeConversionErrors (2 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_invalid_int_returns_fallback` | Invalid int handling |
| `test_invalid_float_returns_fallback` | Invalid float handling |

#### TestDefaultsIntegration (2 tests) - TASK 31.2

| Test | Purpose |
|------|---------|
| `test_full_workflow_save_and_restore` | Complete workflow |
| `test_mixed_sections_user_defaults` | Cross-section defaults |
---

### test_paths.py (18 tests) - TASK 32.1

Tests for path handling and absolute path storage.

#### TestManifestAbsolutePaths (3 tests) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_source_files_stored_as_absolute_on_create` | Create stores absolute |
| `test_source_files_resolved_on_set` | set_source_files resolves |
| `test_paths_remain_absolute_after_save_load` | Persist through save/load |

#### TestINIAbsolutePaths (2 tests) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_last_manifest_stored_as_absolute` | last_manifest absolute |
| `test_recent_manifests_stored_as_absolute` | Recent list absolute |

#### TestSourceFileStatus (3 tests) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_found_status_for_existing_file` | Existing = found |
| `test_recoverable_status_for_missing_with_lines` | Missing with lines = recoverable |
| `test_missing_status_for_complex_format` | Complex missing = missing |

#### TestPathDisplay (2 tests) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_absolute_path_can_be_displayed_relative` | Relative display |
| `test_filename_extraction_from_absolute` | Extract filename |

#### TestPathResolution (3 tests) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_resolve_handles_relative_path` | Resolve relative |
| `test_resolve_preserves_absolute_path` | Preserve absolute |
| `test_resolve_normalizes_path` | Normalize .. paths |

#### TestManifestPathStorage (1 test) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_manifest_json_contains_absolute_paths` | JSON has absolute |

#### TestPathEdgeCases (4 tests) - TASK 32.1

| Test | Purpose |
|------|---------|
| `test_empty_source_files_handled` | Empty list handled |
| `test_paths_with_spaces_handled` | Spaces in paths |
| `test_paths_with_unicode_handled` | Unicode in paths |
| `test_nonexistent_source_file_path_preserved` | Nonexistent path saved |

---

### test_edit_before_translate.py (36 tests) - TASK 33.1

Edit Before Translation feature tests.

#### TestLineEntryEditedPrepro (4 tests)

| Test | Purpose |
|------|---------|
| `test_line_entry_has_edited_prepro_field` | Field exists on LineEntry |
| `test_line_entry_edited_prepro_default_none` | Default is None |
| `test_line_entry_edited_prepro_settable` | Can set value at construction |
| `test_line_entry_edited_prepro_mutable` | Can modify after construction |

#### TestInputForTranslationResolution (5 tests)

| Test | Purpose |
|------|---------|
| `test_returns_orig_when_no_prepro_no_edited` | Fallback to original |
| `test_returns_prepro_when_available_no_edited` | Use prepro when available |
| `test_returns_edited_prepro_when_available` | Prefer edited_prepro |
| `test_edited_prepro_takes_precedence_over_prepro` | edited > prepro |
| `test_edited_prepro_takes_precedence_over_orig` | edited > orig |

#### TestLineEntrySerialization (5 tests)

| Test | Purpose |
|------|---------|
| `test_to_dict_includes_edited_prepro_when_set` | Serialize when set |
| `test_to_dict_excludes_edited_prepro_when_none` | Skip when None |
| `test_from_dict_restores_edited_prepro` | Deserialize properly |
| `test_from_dict_handles_missing_edited_prepro` | Handle missing field |
| `test_round_trip_preserves_edited_prepro` | Full roundtrip |

#### TestTranslationOptionsEditFlag (3 tests)

| Test | Purpose |
|------|---------|
| `test_translation_options_has_edit_flag` | Flag exists |
| `test_edit_before_translation_defaults_false` | Defaults to False |
| `test_edit_before_translation_settable` | Can be set |

#### TestTranslatableLineEditedPrepro (3 tests)

| Test | Purpose |
|------|---------|
| `test_translatable_line_has_edited_prepro` | Field exists |
| `test_edited_prepro_defaults_empty_string` | Defaults to empty |
| `test_edited_prepro_settable` | Can be set |

#### TestEditPreviewDialogStructure (2 tests)

| Test | Purpose |
|------|---------|
| `test_edit_preview_dialog_class_exists` | Class exists |
| `test_has_result_constants` | Has RESULT_APPLY and RESULT_CANCEL |

#### TestEditPreviewDialogUI (3 tests)

| Test | Purpose |
|------|---------|
| `test_dialog_creation` | Dialog can be created |
| `test_dialog_result_property` | Result property works |
| `test_dialog_edited_data_property` | edited_data property works |

#### TestManifestEditedPreproStorage (3 tests)

| Test | Purpose |
|------|---------|
| `test_manifest_manager_set_line_field` | Can set edited_prepro |
| `test_manifest_manager_get_line_edited_prepro` | Can retrieve edited_prepro |
| `test_manifest_save_load_preserves_edited_prepro` | Persistence works |

#### TestFieldProgressionOrder (2 tests)

| Test | Purpose |
|------|---------|
| `test_progression_order_documented` | Docstring has progression |
| `test_field_order_in_dataclass` | Fields in correct order |

#### TestTranslationFlowIntegration (1 test)

| Test | Purpose |
|------|---------|
| `test_translate_chunk_uses_edited_prepro` | Translation uses edited text |

#### TestEditedPreproEdgeCases (5 tests)

| Test | Purpose |
|------|---------|
| `test_empty_string_edited_prepro` | Empty string handling |
| `test_whitespace_only_edited_prepro` | Whitespace preserved |
| `test_multiline_edited_prepro` | Multiline preserved |
| `test_unicode_edited_prepro` | Unicode preserved |
| `test_special_characters_edited_prepro` | Special chars preserved |

#### TestBackwardCompatibility (2 tests)

| Test | Purpose |
|------|---------|
| `test_old_manifest_without_edited_prepro` | Old manifests work |
| `test_migration_adds_edited_prepro` | Migration adds field |

---

### test_prompts_config.py (40 tests) - TASK 33.2

Configurable Edit/TLC Prompts feature tests.
**Session 24+:** TestPromptsINIConfiguration tests updated to read `defaults.ini` with
`encoding='utf-8'` (file is UTF-8 due to em/en-dash characters in [limit] section).

#### TestPromptsSettingsDataclass (7 tests)

| Test | Purpose |
|------|---------|
| `test_default_values` | PromptsSettings has correct defaults |
| `test_custom_values` | Custom values work |
| `test_to_dict` | Serialization works |
| `test_from_dict_with_all_fields` | Deserialization with all fields |
| `test_from_dict_with_missing_fields` | Defaults for missing fields |
| `test_from_dict_with_partial_fields` | Partial field handling |
| `test_roundtrip_serialization` | to_dict -> from_dict preserves |

#### TestDefaultPromptConstants (4 tests)

| Test | Purpose |
|------|---------|
| `test_default_edit_prompt_not_empty` | Edit prompt is meaningful |
| `test_default_tlc_prompt_not_empty` | TLC prompt is meaningful |
| `test_default_tlc_prompt_has_placeholder` | TLC has {target_lang} |
| `test_default_prompts_are_distinct` | Edit != TLC |

#### TestGlobalOptionsWithPrompts (6 tests)

| Test | Purpose |
|------|---------|
| `test_global_options_has_prompts_field` | Field exists |
| `test_global_options_prompts_defaults` | Correct defaults |
| `test_global_options_to_dict_includes_prompts` | Serialization includes prompts |
| `test_global_options_from_dict_with_prompts` | Deserialization restores prompts |
| `test_global_options_from_dict_without_prompts` | Missing prompts use defaults |

#### TestOptionSectionEnum (4 tests)

| Test | Purpose |
|------|---------|
| `test_option_section_count` | OptionSection has 10 members |
| `test_option_section_iteration` | Can iterate; yields 10 sections |
| `test_prompts_section_exists` | PROMPTS enum exists |
| `test_prompts_section_in_descriptions` | Has description |
| `test_prompts_section_in_names` | Has display name |
| `test_prompts_section_in_category_order` | In navigation |

#### TestPromptsINIConfiguration (4 tests)

| Test | Purpose |
|------|---------|
| `test_defaults_ini_has_prompts_section` | [prompts] in defaults.ini |
| `test_defaults_ini_has_edit_prompt` | edit_prompt key exists |
| `test_defaults_ini_has_tlc_prompt` | tlc_prompt key exists |
| `test_defaults_ini_tlc_prompt_has_placeholder` | {target_lang} in TLC |

#### TestPromptPlaceholders (4 tests)

| Test | Purpose |
|------|---------|
| `test_substitute_target_lang` | {target_lang} substitution |
| `test_substitute_source_lang` | {source_lang} substitution |
| `test_substitute_multiple_placeholders` | Both placeholders |
| `test_default_tlc_prompt_substitutes_correctly` | Default TLC substitutes |

#### TestPromptsEdgeCases (6 tests)

| Test | Purpose |
|------|---------|
| `test_empty_edit_prompt` | Empty prompt handling |
| `test_empty_tlc_prompt` | Empty TLC handling |
| `test_multiline_edit_prompt` | Multiline preserved |
| `test_special_characters_in_prompt` | Special chars preserved |
| `test_unicode_in_prompt` | Unicode preserved |
| `test_very_long_prompt` | Very long prompts work |

#### TestPromptsSettingsTypeCoercion (2 tests)

| Test | Purpose |
|------|---------|
| `test_from_dict_coerces_non_string` | Type coercion works |
| `test_from_dict_handles_list_value` | List converted to string |

#### TestPromptsBackwardsCompatibility (2 tests)

| Test | Purpose |
|------|---------|
| `test_old_global_options_dict_without_prompts` | Old data uses defaults |
| `test_migration_preserves_other_settings` | Other settings preserved |

#### TestPromptsDialogWidgetsMocked (2 tests)

| Test | Purpose |
|------|---------|
| `test_dialog_creates_prompts_panel` | Panel configured properly |
| `test_prompts_section_description_meaningful` | Description is useful |

| `test_migration_adds_edited_prepro` | Migration adds field |

---

### dev/test_phase34_comprehensive.py (34 tests) - PHASE 34

Comprehensive testing infrastructure for Phase 34: Extended and More Robust Automatic Testing.

This test file implements:
1. Internal timeout mechanism to prevent infinite loops
2. mypy static type checking validation
3. GUI button execution tests
4. CherryAI launch tests

#### TestTimeoutFramework (5 tests)

Tests for the internal timeout mechanism.

| Test | Purpose |
|------|---------|
| `test_timer_tracks_elapsed_time` | Timer correctly measures elapsed time |
| `test_timer_detects_fast_completion` | Timer recognizes fast completion |
| `test_run_with_timeout_returns_result` | run_with_timeout returns function result |
| `test_run_with_timeout_propagates_exception` | Exceptions propagate correctly |
| `test_timer_handles_multiple_sequential_tests` | Multiple tests work correctly |

#### TestMypyValidation (7 tests)

Tests that run mypy static type checking.

| Test | Purpose |
|------|---------|
| `test_mypy_is_available` | mypy is installed |
| `test_functions_package_passes_mypy` | functions/ passes type checking |
| `test_modi_package_passes_mypy` | modi/ passes type checking |
| `test_formats_package_passes_mypy` | formats/ passes type checking |
| `test_all_packages_importable` | All packages import cleanly |
| `test_no_circular_imports` | No circular import issues |
| `test_critical_modules_type_annotated` | Critical modules have annotations |

#### TestGUIButtonExecution (12 tests)

Tests for GUI button callbacks and lifecycle methods.

| Test | Purpose |
|------|---------|
| `test_translation_step_has_start_button` | TranslationStep has Start button |
| `test_translation_step_has_stop_button` | TranslationStep has stop/cancel functionality |
| `test_input_step_has_load_button` | InputExtractionStep has Load button |
| `test_analysis_step_has_analyze_button` | AnalysisStep has Analyze button |
| `test_preprocessing_step_has_process_button` | PreprocessingStep has Process button |
| `test_output_step_has_export_button` | OutputInjectStep has Export button |
| `test_estimation_step_has_estimate_button` | EstimationStep has Estimate button |
| `test_wordwrap_step_has_apply_button` | WordwrapOverwriteStep has Apply button |
| `test_app_has_file_menu` | App has File menu |
| `test_all_steps_have_on_enter_method` | All steps have on_enter() |
| `test_all_steps_have_on_leave_method` | All steps have on_leave() |
| `test_button_callbacks_are_bound` | Button command= bindings exist |

#### TestCherryAILaunch (6 tests)

Tests for CherryAI application launch.

| Test | Purpose |
|------|---------|
| `test_cherryai_module_exists` | CherryAI.py exists |
| `test_cherryai_has_main_entry` | Has main entry point |
| `test_cli_help_works` | CLI responds to --help |
| `test_cli_test_command_exists` | CLI has test command |
| `test_config_files_exist` | Required config files exist |
| `test_app_class_importable` | App class can be imported |

#### TestTestSuiteItself (4 tests)

Meta-tests verifying test infrastructure.

| Test | Purpose |
|------|---------|
| `test_timeout_tests_exist` | Timeout framework tests present |
| `test_mypy_tests_exist` | mypy validation tests present |
| `test_gui_button_tests_exist` | GUI button tests present |
| `test_launch_tests_exist` | Launch tests present |

---

## Phase 34 Testing Policy

Phase 34 establishes these testing requirements:

1. **All non-API tests must pass before and after every phase**
2. **A phase can only be considered done if all tests succeed**
3. **If tests fail before starting a phase, fix them first**

### Timeout Protection

All tests should complete within reasonable time limits:
- Individual test: 10 seconds default
- Full test suite: 5 minutes maximum
- Use `--timeout=10` flag with pytest

If a test takes too long:
- If purpose justifies duration: extend timeout
- If not: investigate and fix the root cause

---

### dev/test_mock_translation.py (70 tests) - PHASE 56

Mock Translation Flaw Testing — validates the deliberate flaw injection engine
in `functions/mock_translator.py` and its integration with the postprocessing
recovery pipeline, plus cancellation and speed. Uses `dev/example/example.txt` as test fixture.

#### TestExampleFile (3 tests)

| Test | Purpose |
|------|---------|
| `test_example_file_exists` | Test fixture file present |
| `test_example_has_content` | File contains expected lines |
| `test_example_has_speaker_lines` | Speaker:dialogue format present |

#### TestMockTranslatorBasic (6 tests)

| Test | Purpose |
|------|---------|
| `test_translate_single_line` | Single line mock translation works |
| `test_batch_preserves_line_count` | Output count matches input |
| `test_placeholder_preserved` | `__PROTECTED__` tokens kept intact |
| `test_deterministic_with_seed` | Same seed produces same output |
| `test_empty_line_preserved` | Empty lines pass through unchanged |
| `test_whitespace_only_preserved` | Whitespace-only lines pass through |

#### TestTokenPreservation (7 tests)

| Test | Purpose |
|------|---------|
| `test_prot_token_preserved` | `__PROTECTED_0__` survives translation |
| `test_dedup_token_preserved` | `__DEDUP_1__` survives translation |
| `test_custom_token_preserved` | `__CUSTOM_2__` survives translation |
| `test_multiple_tokens_preserved` | Multiple tokens in one line |
| `test_token_at_start_preserved` | Token at line start |
| `test_token_at_end_preserved` | Token at line end |
| `test_adjacent_tokens_preserved` | Back-to-back tokens |

#### TestSpeakerPreservation (2 tests)

| Test | Purpose |
|------|---------|
| `test_speaker_name_kept` | Speaker name before colon preserved |
| `test_dialogue_translated` | Dialogue part after colon translated |

#### TestFlawConfig (7 tests)

| Test | Purpose |
|------|---------|
| `test_default_config_disabled` | Flaws disabled by default |
| `test_enabled_config` | FlawConfig enables all flaw types |
| `test_intensity_mild` | Mild intensity = 10% corruption |
| `test_intensity_moderate` | Moderate intensity = 30% corruption |
| `test_intensity_severe` | Severe intensity = 60% corruption |
| `test_selective_flaw_types` | Individual flaw types toggled |
| `test_from_string_intensity` | String intensity creates valid enum |

#### TestPlaceholderMalformation (4 tests)

| Test | Purpose |
|------|---------|
| `test_malformation_changes_placeholder` | Placeholder text is corrupted |
| `test_malformation_is_documented` | FlawReport records malformations |
| `test_no_malformation_when_disabled` | Disabled flag prevents flaws |
| `test_malformation_severe_affects_more` | Severe intensity corrupts more |

#### TestAnchorManipulation (4 tests)

| Test | Purpose |
|------|---------|
| `test_anchor_removal` | Anchors are removed from lines |
| `test_anchor_removal_documented` | FlawReport records removals |
| `test_anchor_insertion` | Random anchors inserted |
| `test_no_anchor_flaw_when_disabled` | Disabled flag prevents flaws |

#### TestCodeIntrusion (3 tests)

| Test | Purpose |
|------|---------|
| `test_code_gets_intruded` | Code patterns receive replacement |
| `test_code_intrusion_documented` | FlawReport records intrusions |
| `test_no_intrusion_when_disabled` | Disabled flag prevents flaws |

#### TestCharacterSurgery (3 tests)

| Test | Purpose |
|------|---------|
| `test_character_surgery_changes_text` | Text is modified at character level |
| `test_surgery_documented` | FlawReport records surgeries |
| `test_no_surgery_when_disabled` | Disabled flag prevents flaws |

#### TestFlawReport (4 tests)

| Test | Purpose |
|------|---------|
| `test_report_tracks_totals` | Report counters increment correctly |
| `test_report_details_populated` | Detail records have all fields |
| `test_report_reset` | reset_report() clears counters |
| `test_report_multiple_batches` | Report accumulates across batches |

#### TestRecoveryValidation (7 tests)

| Test | Purpose |
|------|---------|
| `test_malformed_placeholders_recoverable` | Postprocess recovers placeholders |
| `test_anchor_removal_errors_flagged` | Removed anchors detected |
| `test_code_intrusion_detected_in_validation` | Code intrusion flagged |
| `test_character_surgery_detectable` | Character surgery detected |
| `test_end_to_end_with_example_file` | Full pipeline with example.txt |
| `test_end_to_end_produces_functional_output` | Output is usable text |
| `test_postprocess_manager_stats` | PostProcessManager tracks stats |

#### TestAPIClientMockRouting (2 tests)

| Test | Purpose |
|------|---------|
| `test_mock_model_in_api_config` | APIConfig accepts model="mock" |
| `test_api_config_from_dict_mock` | Dict-based config with mock model |

#### TestEdgeCases (7 tests)

| Test | Purpose |
|------|---------|
| `test_line_with_only_placeholders` | Line of only placeholders passes |
| `test_very_long_line` | Very long line handled correctly |
| `test_unicode_preservation` | Unicode characters preserved |
| `test_mixed_japanese_english` | Mixed scripts handled properly |
| `test_flaw_on_empty_line_no_crash` | Flaws on empty lines don't crash |
| `test_flaw_severity_increases_corruption` | Severe creates more flaws |
| `test_delay_per_chunk` | Delay parameter works correctly |

#### TestCancellation (8 tests)

| Test | Purpose |
|------|---------|
| `test_cancel_event_accepted` | MockTranslator accepts cancel_event parameter |
| `test_cancel_stops_batch` | Pre-set cancel event stops batch immediately |
| `test_cancel_returns_correct_length` | Cancelled batch returns same length as input |
| `test_cancel_preserves_completed_lines` | Lines before cancel are kept |
| `test_no_cancel_event_works_normally` | Without cancel_event, works as before |
| `test_unset_cancel_event_no_effect` | Unset event does not interrupt |
| `test_factory_cancel_event` | create_mock_translator accepts cancel_event |
| `test_cancel_from_thread` | Cancel from different thread stops processing |

#### TestSpeed (3 tests)

| Test | Purpose |
|------|---------|
| `test_no_artificial_delay` | Default MockTranslator has no delay |
| `test_thousand_lines_under_100ms` | 1000 lines translate in < 100 ms |
| `test_factory_default_no_delay` | Factory defaults to delay=0.0 |

### Running Phase 56 Tests

```bash
# Run mock translation tests specifically
python -m pytest CherryAI/dev/test_mock_translation.py -v --timeout=10

# Run all tests with timeout protection
python -m pytest CherryAI/dev/ -v --timeout=10
```

### dev/test_information_step_phase41.py (57 tests) - Phase 41 Information Step UI Enhancements

Comprehensive tests for Phase 41 Information step UI enhancements including widget
renames, genre dialog ADD behavior, language custom input, style/tone presets,
glossary inline editing, import from analysis, code database actions, global
glossary widget, selective glossary feature, collapsible right-column widgets,
taller tables, and style/tone text display fixes.

#### TestWidgetRenames (5 tests) - TASK 41.1

| Test | Purpose |
|------|---------|
| `test_summary_label_in_source` | "Summary / Description" replaced with "Summary" |
| `test_system_instructions_label_in_source` | "System Instructions" label present |
| `test_code_database_label_in_source` | "Code Database" label present |
| `test_old_prompt_label_removed` | Old "Prompt" LabelFrame removed |
| `test_old_code_glossary_label_removed` | Old "Code Glossary" LabelFrame removed |

#### TestGenreDialogAdd (3 tests) - TASK 41.2

| Test | Purpose |
|------|---------|
| `test_open_genre_dialog_method_exists` | _open_genre_dialog method exists |
| `test_genre_dialog_merge_logic_in_source` | Merge logic (non_common) in source |
| `test_common_genres_constant_exists` | COMMON_GENRES available |

#### TestOtherLanguageCustom (4 tests) - TASK 41.3

| Test | Purpose |
|------|---------|
| `test_on_language_change_method_exists` | _on_language_change method exists |
| `test_simpledialog_imported` | simpledialog imported |
| `test_prev_lang_attributes_in_source` | _prev_source_lang/_prev_target_lang tracked |
| `test_combobox_selected_binding_in_source` | <<ComboboxSelected>> binding present |

#### TestStyleTonePresets (4 tests) - Phase 60 (replaces TestStyleToneGraying)

| Test | Purpose |
|------|---------|
| `test_toggle_preset_state_method_exists` | _toggle_preset_state method exists |
| `test_style_save_delete_methods_exist` | Save/Delete preset methods exist |
| `test_preset_helpers_in_style_section` | Preset helper widgets in style section |
| `test_on_style_changed_populates_text` | Style change populates ScrolledText |

#### TestGlossaryTableInlineEdit (7 tests) - TASK 41.5

| Test | Purpose |
|------|---------|
| `test_add_glossary_entry_method` | _add_glossary_entry method exists |
| `test_remove_glossary_entry_method` | _remove_glossary_entry method exists |
| `test_on_glossary_double_click_method` | _on_glossary_double_click method exists |
| `test_start_glossary_inline_edit_method` | _start_glossary_inline_edit method exists |
| `test_sync_glossary_tree_to_manifest_method` | _sync_glossary_tree_to_manifest method exists |
| `test_refresh_glossary_entries_method` | _refresh_glossary_entries method exists |
| `test_glossary_treeview_columns_in_source` | Treeview columns defined |

#### TestImportCodePatterns (3 tests) - TASK 41.6

| Test | Purpose |
|------|---------|
| `test_import_code_patterns_method_exists` | _on_import_code_patterns method exists |
| `test_detected_category_in_source` | category="Detected" in import |
| `test_import_merges_no_duplicates_logic` | Dedup logic present |

#### TestImportGlossaryFromAnalysis (4 tests) - TASK 41.7

| Test | Purpose |
|------|---------|
| `test_import_glossary_from_analysis_method` | _on_import_glossary_from_analysis method exists |
| `test_speaker_import_logic` | Speaker detection data used |
| `test_import_glossary_dedup_logic` | Deduplication against existing entries |
| `test_import_glossary_refresh_call` | Calls _refresh_glossary_entries after import |

#### TestCodeDatabaseActions (6 tests) - TASK 41.8

| Test | Purpose |
|------|---------|
| `test_preserve_action_format` | Preserve → "Do not translate" |
| `test_translate_action_format` | Translate → "Translate [pattern] as" |
| `test_remove_action_excluded` | Remove action filtered from prompt |
| `test_preserve_with_example` | Example shown as "(e.g., ...)" |
| `test_translate_with_notes` | Notes used as translation target |
| `test_code_patterns_header` | "# Code Patterns" header in prompt |

#### TestGlobalGlossaryWidget (7 tests) - TASK 41.9

| Test | Purpose |
|------|---------|
| `test_build_global_database_section_method` | _build_global_database_section method exists |
| `test_global_db_path_method` | _global_db_path method exists |
| `test_load_global_db_missing_file` | Returns empty list when file missing |
| `test_save_and_load_global_db` | Save/load roundtrip works |
| `test_refresh_global_database_method` | _refresh_global_database method exists |
| `test_import_export_methods_exist` | Import/export methods exist |
| `test_global_db_mode_switch_logic` | Mode switch (Glossary/Code Database) in source |

#### TestSelectiveGlossary (8 tests) - TASK 41.10

| Test | Purpose |
|------|---------|
| `test_active_column_in_glossary_tree` | Active column defined in Treeview |
| `test_on_glossary_click_method` | _on_glossary_click toggle method exists |
| `test_active_toggle_symbols` | ✓ and ✗ symbols used for toggle |
| `test_save_glossary_entries_includes_active` | active field saved to manifest |
| `test_load_glossary_entries_includes_active` | active field loaded from manifest |
| `test_active_defaults_true` | Missing active field defaults to True |
| `test_sync_glossary_includes_active` | Sync reads active from tree values |
| `test_manifest_active_field_roundtrip` | Full roundtrip with active field |

#### TestPhase41Integrity (7 tests) - Integration

Includes verification that collapsible widget methods (`_toggle_collapsible`,
`_reconfigure_right_column_weights`, `_ensure_style_tone_text`) exist, Glossary
uses right column (`_right_column` in `_build_character_section`), and tables
use height=8 with grid layout.

| Test | Purpose |
|------|---------|
| `test_all_phase41_methods_exist` | All Phase 41 methods present on class |
| `test_information_step_importable` | InformationStep importable |
| `test_prompt_builder_importable` | PromptBuilder importable |
| `test_manifest_fields_importable` | manifest_fields importable |
| `test_no_syntax_errors_in_information` | information.py has no syntax errors |
| `test_no_syntax_errors_in_prompt_builder` | prompt_builder.py has no syntax errors |

### Running Phase 41 Tests

```bash
# Run Phase 41 Information Step tests
python -m pytest CherryAI/dev/test_information_step_phase41.py -v --timeout=10

# Run all tests with timeout protection
python -m pytest CherryAI/dev/ -v --timeout=10
```

### Phase 41+ Additional Coverage (Information Step Enhancements)

The following features added post-Phase 60 are validated through existing test
infrastructure and source-level assertions:

| Feature | Validated By | Notes |
|---------|-------------|-------|
| Summary height=2 | `test_information_step_phase41.py` source checks | ScrolledText height parameter |
| Summary restore default button | `_restore_summary_default` method existence | Resets to `DEFAULT_SUMMARY_TEXT` |
| Default texts population | `_ensure_default_texts` in `on_enter()` | Populates Summary and SI when empty |
| SI preset system | `_load_si_presets`, `_on_si_preset_changed`, `_save_si_preset`, `_delete_si_preset` | Mirrors Style/Tone preset pattern |
| SI preset manifest binding | `SIPreset` combobox binding | String-based, saved/loaded with manifest |
| Hint labels removed | Source inspection | No description labels in Summary/SI sections |
| Project Name from manifest | `_apply_suggested_project_name` | Prefers manifest `ProjectName` over folder |
| Style/Tone in translation | `_build_system_prompt_from_manifest` in translate.py | Reads `CustomStyle`/`CustomTone` from manifest |
| Analysis→Glossary entries | `_show_nameable_dialog._apply()` in analysis.py | Creates glossary entry with gender/role/notes |

### Running Phase 34 Tests

```bash
# Run Phase 34 tests specifically
python -m pytest CherryAI/dev/test_phase34_comprehensive.py -v --timeout=30

# Run all tests with timeout protection
python -m pytest CherryAI/dev/ -v --timeout=10

# Run mypy validation manually
python -m mypy CherryAI/functions CherryAI/modi CherryAI/formats
```

### Phase 42: Preprocessing & Postprocessing Tests (80 tests)

**File:** `dev/test_preprocess_phase42.py`
**TASK 72 Updates:** `TestPreviewFiltering` updated for tag-based filtering (required_tag, line_tags); filter options expanded to 12 entries

| Test Class | Tests | Coverage |
|-----------|-------|----------|
| TestAnchoringWidget | 6 | Anchoring section, _AnchorDialog, tree methods, manifest format |
| TestCustomPlaceholdersRegex | 5 | _RuleDialog show_regex, regex_result, placeholder tree |
| TestProtectCodeDefaults | 4 | Protect tree, regex default, config format, save/load |
| TestAggressiveDedup | 15 | Normalize, mask, restore, set_aggressive_dedup, UI/config |
| TestEllipsisCompression | 7 | Compress 3/6/9 dots, decompress, multiple, passthrough |
| TestPROTCompression | 7 | Adjacent, non-adjacent, three-way, decompress, mixed |
| TestCodeSpacingIntegration | 3 | save_code_glossary visible/spacing, manifest reads |
| TestPreviewFiltering | 4 | Filter var, options (12 TASK 72), update_preview tag-based, count label |
| TestRoundtrip | 4 | Ellipsis, PROT, aggressive dedup, empty line roundtrips |
| TestValidationRecovery | 11 | Position shift, extra tokens, recover_line, save_to_manifest |
| TestProcessOrder | 7 | Module import, pre/post ordering, get_pre/post_order |
| TestEdgeCases | 7 | Empty input, special chars, long lines, unicode, mixed PROTECTED |

```bash
# Run Phase 42 tests
python -m pytest CherryAI/dev/test_preprocess_phase42.py -v --timeout=10
```

### Phase 43: Translation Tab Overhaul Tests (48 tests)

**File:** `dev/test_translation_phase43.py`

| Test Class | Tests | Coverage |
|-----------|-------|----------|
| TestManifestAttribute | 1 | No raw self.manifest in translate.py (Task 43.1) |
| TestMergedColumn | 5 | "To be Translated" column, resolution priority (Task 43.3) |
| TestNewlineRendering | 3 | ↵ symbol replacement, multiple newlines (Task 43.4) |
| TestMockTranslation | 4 | MODEL_OPTIONS, MockTranslator, PROTECTED preservation (Task 43.5) |
| TestAPIProviderManagement | 6 | APIProviderEntry roundtrip, providers, presets (Task 43.6) |
| TestCachingGlobalOptions | 2 | cache_mode default and roundtrip (Task 43.7) |
| TestThinkingGlobalOptions | 2 | thinking_enabled/budget defaults and roundtrip (Task 43.8) |
| TestRollingContextGlobalOptions | 2 | rolling_context_lines default and roundtrip (Task 43.9) |
| TestRetryRefinement | 2 | RETRY_STRATEGIES (2), ALL_RETRY_STRATEGIES (4) (Task 43.10) |
| TestPromptEditorRedesign | 2 | _BAN_PRESETS existence and content (Task 43.11) |
| TestChunkSync | 2 | Read/write LinesPerChunk manifest sync (Task 43.12) |
| TestSkipNonSourceLanguage | 10 | detect_line_script(), _LANG_SCRIPT_MAP (Task 43.13) |
| TestTabCaching | 4 | Hash computation, validity, update, invalidate (Task 43.14) |
| TestTablePerformance | 2 | Batch threshold (100 vs 600 rows) (Task 43.2) |
| TestGlobalOptionsIntegration | 1 | Full GlobalOptions roundtrip with all Phase 43 fields |

```bash
# Run Phase 43 tests
python -m pytest CherryAI/dev/test_translation_phase43.py -v --timeout=10
```

### Phase 44: Shared Validation & QA Placeholder Tests (24 tests)

**File:** `dev/test_validation_shared.py`

| Test Class | Tests | Coverage |
|-----------|-------|----------|
| TestValidationModuleAvailability | 7 | Core validation functions importable |
| TestPostprocessingUsesValidation | 4 | Postprocess imports recover_line, validation |
| TestTranslationUsesRetryRecovery | 3 | Translation imports prompt_adapter retry |
| TestValidationConsistency | 7 | Placeholder validation, extract, pre/post, recovery types |
| TestQAPlaceholder | 3 | QA step full UI always shown (placeholder mode removed), dataclasses preserved |

```bash
# Run Phase 44 tests
python -m pytest CherryAI/dev/test_validation_shared.py -v --timeout=10
```

### Phase 45: Postprocessing Tab Overhaul Tests (49 tests)

**File:** `dev/test_postprocess_phase45.py`

| Test Class | Tests | Coverage |
|-----------|-------|----------|
| TestTask451MouseWheel | 1 | bind_all not used (scoped binding check) |
| TestTask452RenameLabel | 1 | "Processed Lines" label present |
| TestTask453RemoveButtons | 3 | No Refresh/Revert All buttons in header |
| TestTask454AutoRecovery | 5 | Auto recovery always on, no checkboxes, hardcoded True |
| TestTask455BidirectionalSymbol | 8 | HALFWIDTH_TO_FULLWIDTH map, mutual exclusion, bidirectional conversion |
| TestTask456FailureHandling | 6 | FailurePolicy.WRITE/FLAG enum, default WRITE, manifest values |
| TestTask457DiffViewEditing | 5 | Edit text widget, mark-as-fixed flow, _mark_line_as_fixed method |
| TestTask458SummaryUpdates | 6 | Progress bar, Written/Flagged labels, completion popup |
| TestTask459FilterOptions | 8 | All/Changed/Written/Flagged filters, PostprocessLine.written/flagged fields |
| TestTask4510OverwriteWarning | 4 | Overwrite dialog on re-run, skip on first run |
| TestFailurePolicyPropagation | 2 | FailurePolicy WRITE/FLAG propagation in _do_postprocessing |
| TestStageInputResolution | 2 | Postprocessing translated input stays on tl → prepro → orig while postpro remains separate |

```bash
# Run Phase 45 tests
python -m pytest CherryAI/dev/test_postprocess_phase45.py -v --timeout=10
```

### Phase 46: Wordwrap Tab Overhaul Tests (47 tests)

Test file: `dev/test_wordwrap_phase46.py`

| Test Class | Count | Coverage |
|------------|-------|----------|
| TestTask461ModeDropdown | 3 | WrapMode.MANUAL only, count==1, combobox values |
| TestTask462RemoveOrphanPunct | 2 | No _orphan_var/_punct_var, get_wrap_options hardcodes True |
| TestTask463SpeakerHandling | 6 | SpeakerMode IGNORE/COUNT, count==2, descriptions match |
| TestTask464IgnorePatterns | 3 | No IgnorePattern enum, _get_ignore_codes reads CodeDatabase |
| TestTask465RemoveTypography | 2 | No TypographyStyle/TypographyOptions, no get_typography_options |
| TestTask466RemoveOverwriteStrategy | 3 | No OverwriteStrategy/MergeMethod/OverwriteOptions, no get_overwrite_options |
| TestTask467WidthDropdown | 4 | _on_width_mode_changed, char/pixel frames toggle, pixel has font_size |
| TestTask468TargetStrategy | 7 | WrapTarget values, no Step 8 overwrite field/column, tags-only/file-first resolution, preserve untyped rows |
| TestTask469TableFilters | 5 | Filter values All/Changed/Exceeding/New Textbox, _refresh_table filter logic |
| TestTask4610MaxLinesFlag | 4 | _simple_wrap exceeds_limit detection, WrapLine exceeds_limit field |
| TestRemainingEnumsDataclasses | 6 | WrapStatus intact, FormatConfig intact, WrapStats intact |
| TestStageInputResolution | 3 | Input column uses qa → postpro → tl → prepro → orig while restoring existing wordwr separately; Simple mode does not auto-refresh on mode switch |

```bash
# Run Phase 46 tests
python -m pytest CherryAI/dev/test_wordwrap_phase46.py -v --timeout=10
```

### Phase 47: Output + Pipeline Completeness + Import Tests (52 tests)

Test file: `dev/test_output_phase47.py`

| Test Class | Count | Coverage |
|------------|-------|----------|
| TestGetFinalOutput | 14 | 9-level priority chain, edit{N}/tlc{N} highest round, gaps, empty |
| TestResolveAllLines | 2 | Batch resolution, empty input |
| TestGetSourceBreakdown | 2 | Source field counting across lines |
| TestPriorityChainConstant | 1 | PRIORITY_CHAIN list order and completeness |
| TestDirtyFlags | 6 | get_dirty_flags, set_dirty_flag, defaults, isolation |
| TestNonDestructiveDefaults | 5 | NamingOptions default SUBFOLDER, output defaults including overwrite-on and Same-as-Source destination |
| TestFailureLogging | 4 | ExportStats.failure_log, append entries, empty default |
| TestImportTranslations | 4 | _on_import_translations method, field copy, matching |
| TestSkipAlreadyTranslated | 4 | TranslationOptions.skip_already_translated, skip logic |
| TestOutputSummaryPanel | 5 | Dirty flag labels, _update_dirty_flags method |
| TestExistingAPIStability | 5 | OutputFormat, NamingStrategy, BackupStrategy, ExportStatus enums intact |

```bash
# Run Phase 47 tests
python -m pytest CherryAI/dev/test_output_phase47.py -v --timeout=10
```

### Phase 48: Pipeline Logging System Tests (test_pipeline_logging.py)

**File:** `dev/test_pipeline_logging.py`
**Test Count:** 52
**Coverage:** Log rotation, status vocabulary, step log I/O, API client step log, GUI step integration, manifest metrics, log export, naming conventions, error resilience, UTF-8 encoding, API stability

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestRotateLog | 3 | No existing log, archive existing, multiple archives |
| TestGetStepLogPath | 2 | Canonical path format, all step names |
| TestWriteStepLogHeader | 2 | Header content with separators, parent dir creation |
| TestWriteStepLogFooter | 2 | Footer appended to existing, non-existent file safe |
| TestAppendStepLogEntry | 1 | Free-form text append |
| TestLogStatus | 5 | PASS constant, recovered/partial_retrial/partial_failure/failure formats |
| TestFailureType | 2 | All 11 constants defined, uppercase verification |
| TestFormatLogStatus | 2 | Without detail, with detail |
| TestDeriveStepStatus | 6 | Empty, all PASS, recovered, partial, failure, partial retrial |
| TestAPIClientStepLog | 4 | _step_log_path attribute, write_log_header/footer/call integration |
| TestPostprocessStepLogIntegration | 2 | Log code presence, step name |
| TestWordwrapStepLogIntegration | 2 | Log code presence, step name |
| TestOutputStepLogIntegration | 3 | Log code presence, step name, export glob |
| TestManifestStepMetrics | 6 | Set/get roundtrip, merge update, empty, copy isolation, multi-step, spec fields |
| TestLogFileNamingConvention | 2 | Active log naming, archive naming pattern |
| TestLogWriteNeverBlocks | 3 | Header/footer/append invalid path safe |
| TestLogUTF8Encoding | 2 | Header UTF-8, entry UTF-8 |
| TestExistingAPIStability | 3 | setup_logger signature, write_failure_report, now_iso |

```bash
# Run Phase 48 tests
python -m pytest CherryAI/dev/test_pipeline_logging.py -v --timeout=10
```

### Phase 49: Request Formation Tests (test_request_formation.py)

**File:** `dev/test_request_formation.py`
**Test Count:** 50
**Coverage:** LineInfo, RequestFormationConfig, TranslationRequest, build_requests 4-step process, menu/choice splitting, file boundaries, size balancing, short request merging, existing API stability

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestLineInfo | 2 | Defaults, with marker |
| TestRequestFormationConfig | 2 | Defaults, custom values |
| TestTranslationRequest | 2 | Defaults, line_count property |
| TestExtractValidLines | 3 | All valid, mixed, empty |
| TestStep1MenuChoiceSplitting | 6 | No markers, menu block, choice block, multiple blocks, no rolling context, dialogue stays |
| TestStep2FileBoundarySplitting | 6 | No markers, single, multiple, empty, start boundary, consecutive |
| TestStep3SplitAndBalance | 7 | Small group, oversized, balanced, is_split flag, multiple groups, empty, exact max |
| TestStep4MergeShortRequests | 6 | No short, merge same-type, different types, exceeds max, menu never merged, empty |
| TestBuildRequestsIntegration | 10 | Simple chunking, invalid excluded, menu/choice separated, file boundaries, order preserved, empty/all-invalid, single line, estimation=translation, context types, default config |
| TestExistingPromptBuilderStability | 5 | RequestBatch, RollingContextConfig, PromptBuilder, strip_speaker_quotes, format_rolling_context |

```bash
# Run Phase 49 tests
python -m pytest CherryAI/dev/test_request_formation.py -v --timeout=10
```

---

### Phase 50: Context Markers Full Implementation (70 tests)

**File:** `dev/test_context_markers.py`
**Baseline:** 5010 passed, 70 skipped

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestLineEntryContextMarker | 5 | Default None, set marker, all valid types, get_marker_type, VALID_TAGS |
| TestLineEntryContextMarkerSerialization | 6 | to_dict without/with marker, from_dict with/without marker, roundtrip both |
| TestIsChoiceItem | 7 | Numbered, bullet, CJK bullet, circled number, long reject, empty, plain |
| TestIsMenuItem | 5 | Short items, speaker reject, long reject, multi-sentence reject, empty |
| TestIsDialogueLine | 3 | Speaker colon, Japanese speaker, no speaker |
| TestDetectContextMarkers | 8 | Empty, all dialogue, below threshold, menu, choice, mixed, no file_end, empty lines |
| TestGetActiveContextType | 4 | No markers, inherits earlier, overridden by later, at marker position |
| TestBuildLineInfos | 11 | Basic, marker invalid, placeholder invalid, empty invalid, propagation, file_end no propagate, detected fallback, entry override, prepro, index |
| TestBuildLineInfosIntegrationWithBuildRequests | 3 | Dialogue end-to-end, menu end-to-end, file boundary splitting |
| TestContextPromptTemplates | 7 | All types have templates, dialogue/menu/choice/unknown content, invalid type, map matches |
| TestConstructSystemPromptContextType | 5 | No context, dialogue, menu, choice, unknown |
| TestContextMarkerEdgeCases | 7 | Backward compat, empty inputs, no markers unknown, single line, marker excluded, populated fields, builder stability |

```bash
# Run Phase 50 tests
python -m pytest CherryAI/dev/test_context_markers.py -v --timeout=10
```

---

### Phase 51: Speaker Duplicate Removal (47 tests)

**File:** `dev/test_speaker_dedup.py`
**Baseline:** 5100 passed, 27 skipped

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestDetectConsecutiveSpeakers | 12 | No speakers, no duplicates, simple, multiple consecutive, non-consecutive, fullwidth, mixed colon, empty lines, single, empty input, case-sensitive, spaces in name |
| TestSpeakerDedupOp | 4 | to_dict, from_dict, roundtrip, defaults |
| TestRemoveDuplicateSpeakers | 7 | Basic removal, no duplicates, custom indices, fullwidth, original unchanged, out-of-range, multiple groups |
| TestRestoreDuplicateSpeakers | 6 | Basic restore, with indices, fullwidth, non-dedup ops ignored, more ops than lines, original unchanged |
| TestRoundTrip | 5 | Simple, multi-group, fullwidth, no duplicates, translated |
| TestRequestSettingsToggle | 6 | Default false, enable, to_dict, from_dict, default false, serialization roundtrip |
| TestEdgeCases | 7 | Colon-only speaker, colon in dialogue, whitespace, long name, negative index, many consecutive, empty ops |

```bash
# Run Phase 51 tests
python -m pytest CherryAI/dev/test_speaker_dedup.py -v --timeout=10
```

---

### Phase 52: Selective Glossary Per Chunk (28 tests)

**File:** `dev/test_glossary_selective.py`
**Baseline:** 5130 passed, 25 skipped

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestFilterAll | 3 | Returns all entries, empty glossary, empty chunk |
| TestFilterOriginalOnly | 4 | Matching originals, no matches, translation not matched, empty translation included |
| TestFilterBoth | 5 | Original match, translation match, both no duplicates, empty translation, partial match |
| TestConstants | 2 | Modes frozenset, mode string values |
| TestPromptBuilderIntegration | 2 | Original-only filters prompt, all mode includes everything |
| TestRequestSettingsGlossaryFilter | 6 | Default all, set original_only, to_dict, from_dict, default, roundtrip |
| TestEdgeCases | 6 | Empty glossary, empty chunk, empty original key, multiline, identical orig/tl, case-sensitive |

```bash
# Run Phase 52 tests
python -m pytest CherryAI/dev/test_glossary_selective.py -v --timeout=10
```

---

### Phase 53: Parser Scripts System (54 tests)

**File:** `dev/test_parser_scripts.py`
**Baseline:** 5184 passed, 25 skipped

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestWordwrapConfig | 4 | Defaults, custom values, roundtrip serialisation, from_dict defaults |
| TestForbiddenChars | 4 | Defaults, custom values, roundtrip serialisation, from_dict defaults |
| TestTagRules | 4 | Defaults, compiled empty patterns, compiled valid regex, roundtrip |
| TestParserScriptABC | 3 | Cannot instantiate base, minimal implementation, info summary |
| TestRpgMakerMVParser | 7 | Name, wordwrap config, forbidden chars, context markers, can_handle www/data, non-json rejected, info capabilities |
| TestRpgMakerMZParser | 4 | Name, wider wordwrap than MV, same forbidden chars as MV, non-json rejected |
| TestParserRegistry | 4 | Register/get case-insensitive, get missing, list parsers, detect no match |
| TestGlobalRegistry | 3 | Returns instance, has RPG Maker parsers, detect non-json |
| TestMergeParserForbiddenChars | 4 | Merge adds chars, no duplicates, empty parser chars, preserves discouraged |
| TestReplaceForbiddenChars | 6 | Replace action, flag action, no chars, empty text, custom replacement, no match |
| TestWordwrapParserIntegration | 2 | MV format config values, MZ wider width |
| TestCanHandleRealFiles | 3 | Detects RPG Maker array, rejects plain JSON, rejects array without null |
| TestEdgeCases | 6 | Negative width, both output actions, invalid regex, registry overwrite, nonexistent file, type coercion |

```bash
# Run Phase 53 tests
python -m pytest CherryAI/dev/test_parser_scripts.py -v --timeout=10
```

### Parser Surgical Injection — inject_to (16 tests)

**File:** `dev/test_parser_injection.py`

Tests for parser-based surgical injection in the Output step. Verifies that `inject_to()` reads from source, surgically replaces translatable text, and writes to output — preserving all non-translatable script structure. Covers the Output step's filedir-based parser routing and per-file line slicing.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestLightVNInjectTo | 8 | Non-empty output, preserves structure, replaces translated text, doesn't modify source, creates parent dirs, output line count matches, inject delegates to inject_to, empty translations still produce full script |
| TestBaseInjectToDefault | 1 | Base ParserScript.inject_to still supports the adjacent `_translated` fallback when a non-tagged parser cannot map any extracted key back onto raw source text |
| TestWriteFileParserRouting | 3 | Parser format IDs route directly to `parser.inject_to`, standard formats skip parser routing, and per-file line slicing uses `first_idx/last_idx` |
| TestEndToEndLightVNInjection | 3 | Full script surgical injection, output is not empty (regression), non-translatable lines preserved |
| TestParserFormatExtension | 1 | lightvn format preserves .txt extension |

```bash
# Run Parser Surgical Injection tests
python -m pytest CherryAI/dev/test_parser_injection.py -v --timeout=60
```

### Parser Handshake & LightVN Parser (focused LightVN regressions documented below)

**File:** `dev/test_lightvn_parser.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestHandshakeValidation | 6 | LightVN satisfies handshake, RPGMaker satisfies handshake, missing extract raises, missing inject raises, missing format_id raises, optional components absent ok |
| TestSpeakerInfo | 1 | Creation with name and line_idx |
| TestExtractedLine | 4 | Defaults, to_dict minimal, to_dict full, roundtrip |
| TestParserError | 1 | Attributes (parser_name, component, message) |
| TestLightVNExtraction | 7 | Name, extract dialogue, narration, menu, variable, empty file, no translatable |
| TestLightVNTaggedExtraction | 5 | All types returned, dialogue has speaker, narration no speaker, menu no speaker, variable no speaker |
| TestConditionalDialogue | 2 | Conditional extracted, conditional prefix stripped |
| TestMultilineDialogue | 1 | Multiline joined |
| TestSpeakerDetection | 2 | Detect speakers, detect no speakers |
| TestWordwrap | 7 | Short no wrap, long wraps, bracket ignored, config, tag dialogue, tag menu no wrap, textbox splitting |
| TestCodeHandling | 5 | Code segments, code recovery, angle bracket safety, angle brackets preserved, code only detection |
| TestConditionalPrefix | 5 | Strip simple, strip nested, no prefix, has conditional, extract prefix |
| TestInjection | 4 | Inject dialogue, menu, variable, preserves structure |
| TestEncoding | 2 | UTF-8, UTF-8 BOM |
| TestCanHandle | 3 | Recognizes LightVN script, rejects non-txt, rejects plain txt |
| TestOptionalComponents | 3 | Forbidden chars, context markers, info capabilities (including O9 pretty_wrap) |
| TestFullCorpus | 4 | Extraction count (55604/50212), tagged count matches, all tags valid, speaker detection on corpus |
| TestAllParsersHandshake | 1 | All registered parsers valid |
| **TestDuplicateDialogue** | **4** | **Duplicate dialogue count, text content, tags, speakers — verifies extraction returns all occurrences** |
| **TestDuplicateMenu** | **3** | **Duplicate menu count, いいえ count, all menu tagged** |
| **TestDuplicateVariable** | **3** | **Duplicate variable count, text content, all variable tagged** |
| **TestItemVariables** | **2** | **Item-like variable assignments extract with the `items` tag and inject back through both direct and conditional assignment lines** |
| **TestProjectScopedVariableClassification** | **4** | **Display-only quoted project variables extract and inject, while mixed display-plus-asset variables (`胎児`) and control-flow variables (`付与対象`) stay out of translation** |
| **TestTargetedVariableExtraction** | **7** | **Exact-name LightVN variable whitelist extracts assignment and `==` / `!=` comparison literals, skips file-like values, excludes prefixed names such as `ti_主人公`, applies `items` tags for targeted loot/material names, keeps parity with padded placeholder assignments, injects those literals back surgically, and stays out of the generic assignment helper** |
| **TestTargetedVariableOriginalCoverage** | **5** | **Real-Uni16 verification that every whitelisted exact variable is extracted by the new helper, injectable back through the same helper, covers every targeted assignment the broad helper would have returned, and leaves both targeted and broad generic assignment scans empty on the staged originals** |
| **TestMixedDuplicates** | **5** | **Mixed total count, dialogue dupes, menu dupes, variable dupes, document order preserved** |
| **TestNoDuplicates** | **2** | **Unique-only scripts still extract correctly (regression)** |
| **TestExtractAgreement** | **2** | **extract() and extract_tagged() return same count/content** |
| **TestInjectionWithDuplicates** | **2** | **_extract_all_keys includes duplicates, injection dict from duplicates** |
| **TestRealFileExtraction** | **2** | **skilltext.txt has duplicates (>300 total), small file extraction** |
| **TestBookmarkHandling** | **2** | **`~栞` bookmarks skip `ここにテキストを入力` placeholders and clear carried speaker state before later dialogue extraction** |
| **TestSpeakerDetection (new)** | **2** | **Speakers from dialogue, single speaker** |
| **TestSpeakerAllowlistFiltering** | **6** | **analyze_lines always detects, include_false skips, allowlist keeps valid, removes false positives, empty allowlist filters all, batch counts** |

Latest verified focused LightVN result: `dev/test_lightvn_fixes.py`, `dev/test_lightvn_parser.py`, `dev/test_output_injection.py` — 132 passed.
Latest verified combined LightVN + parser-routing result: `dev/test_lightvn_fixes.py`, `dev/test_lightvn_parser.py`, `dev/test_output_injection.py`, `dev/test_parser_injection.py` — 148 passed.

```bash
# Run Parser Handshake & LightVN tests
python -m pytest CherryAI/dev/test_lightvn_parser.py -v --timeout=300

# Focused project-scoped variable safety + injection regression
python -m pytest CherryAI/dev/test_output_injection.py CherryAI/dev/test_lightvn_parser.py CherryAI/dev/test_lightvn_fixes.py -q --timeout=10

# Verified targeted-variable + menu-parentheses LightVN regression
python -m pytest CherryAI/dev/test_lightvn_fixes.py CherryAI/dev/test_lightvn_parser.py CherryAI/dev/test_output_injection.py -q --timeout=20
```

### Parser Input Routing & P2 Validation (32 tests)

**File:** `dev/test_parser_input_routing.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestListParserNames | 4 | Returns list of strings, contains LightVN, contains RPGMaker, no duplicates |
| TestParserRegistryLookup | 3 | LightVN lookup, case-insensitive, unknown returns None |
| TestParserAwareExtraction | 2 | LightVN extract via registry, extract_lines routes to parser |
| TestAutoDetection | 2 | Detect LightVN script, non-LightVN not detected |
| TestFileMatchesFormat | 3 | LightVN script matches, plain text doesn't match, extension format still works |
| TestFullCorpusViaRouting | 1 | Corpus via registry matches direct parser call |
| TestInputDialogFormatValues | 2 | Format values include lightvn, rpgmaker not duplicated |
| TestHandshakeValidation | 5 | Valid parser no errors, missing extract, missing inject, missing identity, all registered parsers pass |
| TestTokenValidation | 4 | Estimate short text, estimate empty, estimate long text, normal lines pass |
| TestEncodingFallback | 6 | UTF-8 BOM, UTF-16 BOM, plain UTF-8, Shift-JIS, Latin-1 fallback, parser encoding preferred |

```bash
# Run Parser Input Routing & P2 Validation tests
python -m pytest CherryAI/dev/test_parser_input_routing.py -v --timeout=60
```

### Parser Optional Wiring — P3 (28 tests)

**File:** `dev/test_parser_optional_wiring.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestO4SpeakerDetection | 4 | LightVN returns list, name+idx valid, no-override returns None, override check |
| TestO6CustomWordwrap | 4 | LightVN has override, short line passthrough, long line wraps, no-override returns None |
| TestO7ForbiddenChars | 4 | LightVN exists, has characters, to_dict/from_dict round-trip, RPG Maker check |
| TestO8ContextMarkers | 7 | Default heuristics, parser rules override, empty lines None, LightVN rules exist, rules compile, dialogue match, no-rules + no-lines |
| TestWireParserOptionals | 7 | ParserName stored, speaker flag, wordwrap flag, forbidden chars dict, context markers flag, all LightVN optionals, info flags match |
| TestAnalysisSpeakerSkip | 2 | Without speakers, with speakers (allowlist filtering) |

```bash
# Run Parser Optional Wiring P3 tests
python -m pytest CherryAI/dev/test_parser_optional_wiring.py -v --timeout=60
```

### Parser Handler Retrofit — P4 (28 tests)

**File:** `dev/test_parser_handler_retrofit.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestFormatHandlerCompliance | 9 | All extract, all inject, all identity, txt/csv/tsv/json/xlsx individual, validate_parser on all registered |
| TestParserScriptCompliance | 4 | All parsers pass, LightVN valid, RPGMakerMV valid, RPGMakerMZ valid |
| TestRpgMakerStubs | 9 | MV extract/inject raise, MZ extract/inject raise, plugin extract/inject raise, MV/MZ parser delegate raises, error metadata |
| TestRpgMakerParserOptionals | 6 | MV/MZ wordwrap config, MV forbidden chars, MV context markers, MV/MZ can_handle override |

```bash
# Run Parser Handler Retrofit P4 tests
python -m pytest CherryAI/dev/test_parser_handler_retrofit.py -v --timeout=60
```

### Phase 54: Point of View Inference (36 tests)

**File:** `dev/test_pov_inference.py`
**Baseline:** 5218 passed, 27 skipped

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestPronounPatterns | 9 | Pattern existence for 4 languages, English case-insensitive, Japanese patterns match, fallback to Japanese for unknown |
| TestDetectPOVJapanese | 4 | 1st person dominant, 2nd person dominant, empty lines, non-dialogue only |
| TestDetectPOVEnglish | 3 | 1st person "I/my/mine", 2nd person "you/your", mixed case handling |
| TestPOVConfidence | 4 | High confidence >60%, low confidence, mixed when secondary ≥20%, unknown on empty |
| TestPOVWithContextMarkers | 3 | Menu lines excluded, choice lines excluded, dialogue lines excluded |
| TestPOVResult | 3 | to_dict roundtrip, from_dict, default values |
| TestPromptPOVIntegration | 5 | High confidence adds section, low confidence excluded, 1st/2nd/3rd person labels, None pov_result safe |
| TestEdgeCases | 5 | All dialogue lines, protagonist name 3rd person, single line, mixed languages, no protagonist name |

```bash
# Run Phase 54 tests
python -m pytest CherryAI/dev/test_pov_inference.py -v --timeout=10
```

### Task 75: Protagonist Detection + Japanese Romanization (40 tests)

**File:** `dev/test_protagonist_romanization.py`
**Baseline:** 6222+ passed

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestProtagonistDetection | 6 | Single/multiple/no protagonists, empty list, case-insensitive, missing notes |
| TestProtagonistsFromCodeDB | 2 | Code pattern protagonist, no code protagonist |
| TestRunPovWithProtagonists | 4 | 3rd person from protagonist name, 1st person without protagonist, empty lines, no protagonist set |
| TestFormatProtagonistPrompt | 6 | Single protagonist with POV, multiple protagonists, no protagonist, low POV fallback, code patterns, no translation |
| TestRomanize | 14 | Hiragana vowels, katakana, konnichiha, digraphs (sha/kya/cho), small tsu (katta/kitte/zutto), long vowel, mixed text, katakana/hiragana names, extended digraphs (fa/ti/wi), n-before-vowel, all dakuten, all handakuten |
| TestContainsKana | 5 | Hiragana, katakana, Latin, empty, mixed |
| TestRomanizeIfJapanese | 3 | Kana romanized, non-kana unchanged, empty string |

```bash
# Run Task 75 tests
python -m pytest CherryAI/dev/test_protagonist_romanization.py -v --timeout=10
```

### Glossary ↔ Term Translation Link (19 tests)

**File:** `dev/test_glossary_term_link.py`

Tests for the dual-storage desync fix between Term Translation (Analysis step)
and the Glossary widget (Information step). Verifies that `on_enter()` loads
characters from the authoritative top-level manifest key AFTER `_load_metadata()`
replaces `self._metadata` from step_state. Verifies `on_leave()` syncs to
top-level. Verifies `_import_analysis_speakers()` persists immediately.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestCharacterRoundTrip | 2 | CharacterInfo to_dict/from_dict preserves translation, from_dict handles missing translation |
| TestOnEnterLoadOrder | 3 | AST verification: _load_metadata called before _load_characters_from_manifest and _load_code_patterns_from_manifest in on_enter |
| TestOnLeaveSyncToManifest | 2 | AST verification: on_leave calls _save_characters_to_manifest and _save_code_patterns_to_manifest |
| TestImportAnalysisSpeakersPersistence | 1 | AST verification: _import_analysis_speakers calls _save_characters_to_manifest |
| TestDualStorageSync | 4 | Top-level overrides stale step_state, translations survive tab round-trip, empty top-level doesn't wipe step_state, concurrent writes don't lose data |
| TestCharacterInfoPreservation | 3 | All fields preserved in round-trip, empty/missing fields default cleanly, count field preserved as int |
| TestProjectMetadataPreservation | 2 | ProjectMetadata.characters round-trip, metadata to_dict/from_dict preserves character translations |
| TestLoadGuardBehavior | 2 | Non-empty top-level overrides, empty top-level leaves existing characters untouched |

```bash
# Run glossary term link tests
python -m pytest CherryAI/dev/test_glossary_term_link.py -v --timeout=10
```

### Term Translation & Global Options Extensions (100 tests)

**File:** `dev/test_term_translation.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestCapitalizeName | 9 | Simple name, multi-word (first-letter-only), hyphenated segments, empty string, single char, all-caps preserved, already capitalized, whitespace, mixed delimiters |
| TestContainsKanji | 6 | Pure kanji, mixed kanji+kana, pure hiragana, pure katakana, Latin text, empty string |
| TestRomanizeIfJapaneseKanjiSkip | 5 | Pure kana romanized, mixed kanji+kana unchanged, single kanji unchanged, Latin unchanged, translate_term kanji passthrough |
| TestTermTranslationSimple | 7 | Kana translation, non-kana passthrough, empty term, katakana name, mode override, mixed text, MTL not in MODES |
| TestUtilitySettings | 6 | Default mode (Romaji), roundtrip, from_dict defaults, to_dict, LLM mode, MTL migration to Romaji |
| TestGlobalOptionsUtility | 4 | GlobalOptions has utility field, default utility settings, roundtrip serialization, utility in to_dict |
| TestOptionSectionEnums | 3 | UTILITY enum exists, utility in SECTION_NAMES, utility in CATEGORY_ORDER |
| TestCodePatternTranslation | 6 | Default empty translation, to_dict includes translation, from_dict reads translation, roundtrip, legacy from_dict without translation, translation in display |
| TestManifestCodeGlossaryTranslation | 4 | save_code_glossary includes translation, load_code_glossary returns translation, missing translation defaults empty, roundtrip preserves translation |
| TestSectionDescriptions | 2 | SECTION_DESCRIPTIONS completeness, all OptionSection values have descriptions |
| TestTranslateTermsBatch | 4 | Batch splitting exact, batch splitting remainder, large batch single call, Romaji mode no batching |
| TestSkipEmptyTranslation | 5 | Empty LLM result in batch, caller skip-empty logic, caller skip-whitespace, caller skip-same-as-original, empty result not written |
| TestExtractCodeSegments | 10 | No brackets, empty string, single square bracket, multiple segments, nested brackets, angle brackets, fullwidth brackets, unbalanced skipped, mixed bracket types, adjacent segments |
| TestValidateTranslationCode | 8 | No code always valid, code preserved, code missing, partial loss, all preserved, nested preserved, nested lost, empty original valid |
| TestErrorPathPartialSave | 5 | Partial char save, partial code save, error mid-batch keeps prior results, save_character_notes roundtrip, save_code_glossary roundtrip |
| TestTermTranslationManifestOnly | 6 | Code pattern read from manifest, write to manifest only, partial save roundtrip, no global TSV write import, no read_all_rows_extended import, characters saved to manifest only |
| TestManifestSaveAfterChunk | 3 | _process_single_chunk calls save(), _handle_chunk_retry calls save(), save() guarded by None check |
| TestCodePatternsInPrompt | 7 | Translate action in prompt, preserve action excluded, translation arrow format, selective chunk filtering, notes in parentheses, translate step passes code_patterns, costs step passes code_patterns |

```bash
# Run term translation tests
python -m pytest CherryAI/dev/test_term_translation.py -v --timeout=10
```

### Utility Settings Unit Tests (63 tests)

**File:** `dev/test_utility_settings.py`

Tests for the expanded UtilitySettings dataclass (17 fields), term translation
batch splitting, mode detection, API key resolution, gender inference confidence
logic, error abort behaviour, prompt-type routing, configurable prompts,
`_normalize_gender` case-insensitive normalization, JSON-schema validation
(single `details` field, no enum), and model dropdown auto-population.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestUtilitySettings | 6 | Defaults (all 17 fields), to_dict/from_dict roundtrip, empty dict defaults, legacy mode migration (Simple/MTL → Romaji), invalid gender mode fallback, to_dict key completeness |
| TestTermTranslationMode | 7 | LLM mode, Romaji mode, legacy Simple → Romaji, legacy MTL → Romaji, batch size reading, batch size default, batch size clamp to 1 |
| TestTranslateTerm | 4 | Empty term passthrough, empty list passthrough, Romaji dispatch, LLM batch splitting (batch size = 2) |
| TestLLMBatchErrorAbort | 2 | Missing API key raises RuntimeError, API timeout raises RuntimeError |
| TestGenderInferenceConsensus | 5 | Empty results, not enough votes, consensus reached, consensus with mixed votes, no consensus when evenly split |
| TestInferGenderLLM | 3 | Male consensus (mocked, returns {"gender": "Male"}), missing key raises RuntimeError, insufficient lines |
| TestPromptsSettingsUtilityFields | 5 | Defaults match constants, to_dict includes utility keys, from_dict roundtrip, missing keys use defaults, default prompts contain lang placeholders |
| TestPromptTypeRouting | 3 | translate_term passes prompt_type to LLM, translate_terms passes prompt_type, default prompt_type is glossary |
| TestGetPromptTemplate | 4 | Returns ini value for glossary, returns ini value for code, fallback to default glossary, fallback to default code |
| TestNormalizeGender | 8 | Female passthrough, Male passthrough, Non-Binary passthrough, Unsure → Unknown, Unknown → Unknown, Neutral → Non-Binary, arbitrary value title-cased, empty → Unknown |
| TestGenderInferenceSchema | 3 | Schema has `details` string field (no enum), schema is strict, schema has no name/romaji fields |
| TestTermTranslationSchema | 3 | Schema is strict, schema has translations array, schema disallows additionalProperties |
| TestUtilityModelDropdown | 4 | Term model list populated from get_provider_models, gender model list populated, empty provider no crash, unknown provider fallback |

```bash
# Run utility settings tests
python -m pytest CherryAI/dev/test_utility_settings.py -v --timeout=10
```

### Utility Integration Tests — GPT 4.1 Nano (7 tests)

**File:** `dev/test_utility_integration.py`

Live API integration tests using the real OpenAI key from `user/API.ini` and
the `gpt-4.1-nano` model. Tests are skipped when no API key is available.
Uses synthesised Japanese dialogue with known-answer speakers (太郎 = Male,
花子 = Female).

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestTermTranslationLLM | 4 | Single term (太郎 → Taro), batch of 2, batch size = 2 splitting across 5 terms, RuntimeError on bad key |
| TestGenderInferenceLLM | 3 | Male speaker (太郎 → Male >50%), Female speaker (花子 → Female >50%), RuntimeError on bad key |

```bash
# Run integration tests (requires API key + network)
python -m pytest CherryAI/dev/test_utility_integration.py -v -s --timeout=60
```

### Phase 55: Consistency System (60 tests)

**File:** `dev/test_consistency.py`
**Baseline:** 5235 passed, 70 skipped

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestConsistencyTerm | 7 | Defaults, resolved/unresolved, invalid type, all valid types, roundtrip, from_dict defaults |
| TestConsistencyStore | 11 | Empty store, add/get, case-insensitive, update canonical (found/missing), remove, resolved/unresolved filters, by_type, roundtrip, invalid entries, overwrite |
| TestDetectCodeTerms | 4 | Provides_context action detected, preserve/other actions ignored, empty pattern skipped, case-insensitive action |
| TestDetectGlossaryTerms | 4 | Empty translation, empty notes, complete entry skipped, empty source skipped |
| TestDetectSpanTerms | 5 | RPG Maker color span, HTML bold, no spans, dedup, source_line_idx |
| TestBuildConsistencyStore | 3 | Combined detection, empty inputs, no duplicate between types |
| TestPreliminaryMode | 5 | Single pass, multi-pass agreement, disagreement majority, API failure, all resolved skips |
| TestDuringMode | 4 | First occurrence captured, resolved skipped, replace in requests, unresolved not replaced |
| TestCheckMode | 4 | Consistent no flags, inconsistent flagged, no originals skips, flag to_dict |
| TestGlobalOption | 4 | Modes constant, RequestSettings default, roundtrip, GlobalOptions roundtrip |
| TestDisabledMode | 3 | Empty store preliminary, during, check |
| TestEdgeCases | 6 | Special regex chars, mismatched line counts, empty chunks, multiline spans, empty dict, term types constant |

```bash
# Run Phase 55 tests
python -m pytest CherryAI/dev/test_consistency.py -v --timeout=10
```

### Phase 17: New Infrastructure (339 tests)

Phase 17 adds 9 new test files covering batch API support, multi-key management,
named API profiles, additional file formats, usage analytics, agent-assisted modes,
estimation engine, and i18n/tooltips.

**Baseline after Phase 17:** 5619 passed, 25 skipped

#### test_batch_api.py (41 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestBatchRequest | 3 | Defaults, to_dict roundtrip, custom_id format |
| TestBuildBatchJSONL | 5 | Single/multiple chunks, model/temperature forwarded, custom system prompt, empty list |
| TestParseBatchResults | 5 | Single/multiple results, missing choices, error entry, empty input |
| TestBatchJob | 6 | Defaults, elapsed, is_terminal states, to_dict/from_dict roundtrip, status updates |
| TestBatchJobPersistence | 5 | Save/load roundtrip, multiple jobs, remove, empty file, corrupt file |
| TestSubmitBatch | 4 | Success, file upload, API error, invalid client |
| TestPollBatchStatus | 4 | Completed, failed, in_progress, cancelled |
| TestRetrieveBatchResults | 5 | Success, no output file, API error, download, parse integration |
| TestCancelBatch | 2 | Success, API error |
| TestAPIClientBatchMethods | 2 | batch_mode config field, submit_batch_translation delegates |

```bash
python -m pytest CherryAI/dev/test_batch_api.py -v --timeout=10
```

#### test_key_manager.py (34 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestAPIKey | 4 | Defaults, status transitions, rate_limited_until, mask |
| TestKeyPoolBasic | 6 | Empty pool, add/remove, get by id, duplicate rejection, active_keys filter, reset_daily |
| TestPoolModeSequential | 4 | First key, skip exhausted, skip rate_limited, all exhausted returns None |
| TestPoolModeEven | 4 | Fewest requests, tie-break by key_id, increment on pick, all exhausted |
| TestPoolModePriority | 4 | Lowest priority first, skip inactive, equal priority sequential, single key |
| TestPersistence | 6 | Save/load roundtrip, empty pool, corrupt file, pool mode preserved, key status preserved, missing file |
| TestMarkMethods | 4 | mark_exhausted, mark_rate_limited with until, mark back to active, unknown key_id |
| TestEdgeCases | 2 | Thread safety (sequential calls), large pool performance |

```bash
python -m pytest CherryAI/dev/test_key_manager.py -v --timeout=10
```

#### test_named_api_profiles.py (45 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestAPIProfileEnhancements | 8 | display_name default, label with/without display_name, system_prompt_tweak, to_dict/from_dict, roundtrip |
| TestListProfileNames | 5 | Default profile, multiple profiles, empty ini, profile order, special chars |
| TestRenameProfile | 6 | Basic rename, nonexistent source, target exists, preserve fields, same name noop, special chars |
| TestDuplicateProfile | 6 | Basic duplicate, nonexistent source, target exists, all fields copied, display_name/tweak copied |
| TestGetProfileDisplayMap | 5 | Empty, single, multiple, display_name used, mixed |
| TestProfileIntegration | 8 | Create+list, rename+verify, duplicate+modify, display_map after rename, delete+list, profile switching |
| TestEdgeCases | 7 | Unicode names, empty display_name, long tweak, special ini chars, concurrent operations, case sensitivity |

```bash
python -m pytest CherryAI/dev/test_named_api_profiles.py -v --timeout=10
```

#### test_file_formats_17_4.py (62 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestMarkdownExtract | 10 | Plain text, headings, code blocks preserved, lists, frontmatter skipped, empty, inline code, links, images, mixed |
| TestMarkdownInject | 8 | Basic inject, heading count match, code blocks untouched, frontmatter preserved, roundtrip, partial, empty, line count match |
| TestMarkdownMetadata | 4 | Basic, with frontmatter, code block count, empty |
| TestJsonLenientExtract | 10 | Simple pairs, nested, arrays, sanitise pipeline, BOM removal, trailing commas, single quotes, comments, empty, corrupt |
| TestJsonLenientInject | 8 | Basic, preserve structure, nested, array, roundtrip, partial, key order, empty |
| TestJsonLenientMetadata | 4 | Basic, nested depth, key count, empty |
| TestTranslatorPlusExtract | 6 | Basic table, multiple columns, empty cells, no table, missing file, encoding |
| TestTranslatorPlusInject | 6 | Basic, roundtrip, partial, column selection, empty, new rows |
| TestTranslatorPlusMetadata | 4 | Row/column count, table names, empty db, missing file |
| TestFormatRegistration | 2 | All three handlers registered, handler lookup by extension |

```bash
python -m pytest CherryAI/dev/test_file_formats_17_4.py -v --timeout=10
```

#### test_usage_tracker.py (27 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestRecordUsage | 5 | Basic insert, all task types, optional fields, auto-timestamp, invalid task_type |
| TestQueryUsage | 5 | By date range, by task_type, by model, combined filters, empty result |
| TestUsageSummary | 4 | By model, by task_type, date range, empty |
| TestTotalCostTokens | 3 | total_cost, total_tokens (input+output), filtered |
| TestExportCSV | 3 | Basic export, filtered, empty |
| TestPurgeBefore | 3 | Purge old records, purge all, purge none |
| TestEdgeCases | 4 | Concurrent writes, record_count, db creation, special chars in notes |

```bash
python -m pytest CherryAI/dev/test_usage_tracker.py -v --timeout=10
```

#### test_agent_modes.py (42 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestAgentMode | 5 | Defaults, all fields, read/write scopes, to_dict/from_dict, roundtrip |
| TestRegistry | 8 | Built-in modes present, register custom, unregister, get by name, list sorted, duplicate error, unregister unknown, re-register |
| TestAgentRequestResponse | 5 | Request defaults, response roundtrip, empty context, conversation history, metadata |
| TestGatherContext | 4 | Basic context, scope filtering, empty request, mode system_prompt |
| TestAgentCall | 6 | Success, API error, empty response, streaming disabled, mode not found, conversation history forwarded |
| TestSandbox | 4 | Write creates file, nested path, overwrite, directory in sandbox |
| TestAuditLog | 6 | Log entry, load entries, limit, empty log, multiple entries, corrupt line skipped |
| TestEdgeCases | 4 | Unicode content, large context, special chars in mode name, concurrent calls |

```bash
python -m pytest CherryAI/dev/test_agent_modes.py -v --timeout=10
```

#### test_estimation.py (45 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestInferenceOptions | 5 | Defaults, custom values, to_dict/from_dict, roundtrip, validation |
| TestEstimateTokens | 5 | Basic estimation, empty lines, long lines, chars_per_token ratio, single line |
| TestEstimateChunks | 4 | Basic, single chunk, exact fit, zero tokens |
| TestComputeCost | 8 | Basic, batch discount 50%, zero tokens, asymmetric pricing, line items check, notes, free model, large volume |
| TestBuildEstimate | 8 | Basic, with batch, custom options, empty lines, model lookup, unknown model, output ratio, chunk count |
| TestCompareModels | 5 | Two models, three models, sorted by total, with/without batch, empty lines |
| TestPersistence | 6 | Save/load roundtrip, missing file defaults, corrupt file defaults, all fields preserved, path creation, overwrite |
| TestEdgeCases | 4 | Very large file, unicode lines, mixed empty lines, zero cost model |

```bash
python -m pytest CherryAI/dev/test_estimation.py -v --timeout=10
```

#### test_i18n.py (30 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestInit | 4 | Default English, custom lang dir, missing lang falls back, re-init switches |
| TestTranslation | 6 | Basic key, nested key, format substitution, missing key returns key, empty key, special chars |
| TestLanguageSwitch | 4 | set_language, get_language, available_languages, switch and verify |
| TestHasKey | 3 | Existing key, missing key, nested key |
| TestMissingKeys | 3 | No missing, some missing, reference same as active |
| TestFlattenDict | 3 | Flat dict, nested dict, deeply nested |
| TestTooltipAttach | 3 | Attach returns id, detach, get_tooltip_text |
| TestTooltipEnable | 2 | Enable/disable toggle, are_tooltips_enabled |
| TestTooltipDelay | 2 | set_tooltip_delay, default delay |

```bash
python -m pytest CherryAI/dev/test_i18n.py -v --timeout=10
```

#### Session Persistence (test_session_persistence.py, 7 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestSessionPersistence | 7 | Save/restore step index, clamp out-of-range, default on missing, INI integration, close handler saves, app init restores, negative index clamped |

```bash
python -m pytest CherryAI/dev/test_session_persistence.py -v --timeout=10
```

#### Table Batch Insertion (test_table_batch_insert.py, 16 tests)

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestBatchInsertVersionTracking | 5 | Version initialization, refresh increments version, stale batch skipped, current version proceeds, multiple refresh cancels previous |
| TestBatchInsertSignature | 1 | Version parameter in method signature |
| TestTableRowDeduplication | 2 | Row IDs unique, Tcl/Tk duplicate detection |
| TestRowConstructionPerformance | 3 | TASK 71: 10k/50k/100k row build under threshold |
| TestDisplayCapAndBatching | 3 | TASK 72: pagination (5000 rows/page), 2000-row batches, bulk *children delete |
| TestFilterPerformance | 2 | TASK 71: 10k filter < 200ms, 50k filter < 1s |

```bash
python -m pytest CherryAI/dev/test_table_batch_insert.py -v --timeout=10
```

---

### Phase 58-59 Test Files

#### test_auto_pipeline.py (35 tests) - Phase 58

Tests for automatic pipeline orchestration.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestPipelineLevel | 2 | Level values, level comparison |
| TestPipelineResult | 2 | Default values, error result |
| TestPipelineContext | 2 | Context creation, context with options |
| TestAutoPipeline | 6 | Manual level, analyze level, step sequence, level cutoff, error handling, skip existing |
| TestPipelineError | 2 | Error properties, error formatting |
| TestConvenienceFunctions | 3 | Run auto pipeline, level descriptions, unknown level |
| TestInferencePopulation | 2 | Infer speakers, no duplicates |
| TestMockTranslationLevel | 4 | Level value, runs all steps, copies source, preserves existing |
| TestQAValidation | 2 | Empty translations, identical source/target |
| TestPipelineSummary | 3 | Summary includes level, counts lines, result has summary field |
| TestManifestPipelineRecording | 7 | Execution time field, time recorded, manifest recording, level, steps, success, error |

```bash
python -m pytest CherryAI/dev/test_auto_pipeline.py -v --timeout=10
```

#### test_analysis_language.py (37 tests) - Phase 59.1, 59.2, 59.7

Tests for project language detection, aggressive dedup projection, and ignored patterns.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestHiraganaKatakanaDetection | 4 | Hiragana detected, katakana detected, kanji not kana, latin not kana |
| TestCJKCharacterDetection | 3 | Kanji is CJK, kana not CJK, hangul not CJK |
| TestHangulDetection | 3 | Hangul detected, kanji not hangul, kana not hangul |
| TestClassifyCJKLine | 6 | Japanese has kana, Chinese-only no kana, Korean classified, Korean excluded from threshold, latin returns none, empty returns none |
| TestProjectLanguageDetection | 8 | Below threshold is Japanese, above threshold is Chinese, threshold flag, pure Japanese, mixed project, Korean excluded, English unknown, Korean dominant |
| TestProjectLanguageResultFields | 1 | Result has all fields |
| TestAggressiveDedupProjection | 6 | Empty lines zeros, all unique, all duplicates, numeric normalization, display text format, mixed content |
| TestIgnoredPatterns | 6 | Set ignored patterns, add pattern, remove pattern, filter removes matches, filter with no ignored, empty patterns list |

```bash
python -m pytest CherryAI/dev/test_analysis_language.py -v --timeout=10
```

#### test_analysis_context_menu.py (15 tests) - Phase 59.3

Tests for category-aware context menu on Findings Table.
Categories use plural forms: "Speakers", "Code Patterns".

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestContextMenuCategoryDetection | 4 | Speakers category, Code Patterns category, mixed categories, single category not mixed |
| TestContextMenuOptions | 3 | Speaker menu glossary option, code pattern preserve option, generic menu basic options |
| TestSpeakerRoles | 2 | All roles available, role storage format |
| TestGenderOptions | 2 | Gender options available, gender storage format |
| TestPatternActions | 2 | Pattern actions available, pattern types available |
| TestMixedSelectionBehavior | 2 | Mixed selection shows generic, single overview shows generic |
| TestSpeakerNoTruncation | 3 | All speakers shown, small list unchanged, ordering by count |

```bash
python -m pytest CherryAI/dev/test_analysis_context_menu.py -v --timeout=10
```

#### test_analysis_actions.py (16 tests) - Phase 59.4, 59.5

Tests for speaker and code pattern context menu actions.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestAddSpeakerToGlossary | 2 | Add single speaker to character glossary, add multiple speakers |
| TestSetSpeakerRole | 3 | Role stored in character entry, role with existing entry, role replaces old role |
| TestSetSpeakerGender | 2 | Gender male value, gender female value |
| TestSetSpeakerTranslation | 1 | Translation stored in character entry |
| TestSpeakerMultiSelect | 2 | Bulk role assignment, bulk gender assignment |
| TestAddToCodeGlossary | 1 | Speaker protected in code database |
| TestPatternActions | 3 | Preserve action default, action options, type options |
| TestPatternMultiSelect | 2 | Bulk action assignment, bulk type assignment |

```bash
python -m pytest CherryAI/dev/test_analysis_actions.py -v --timeout=10
```

#### test_analysis_findings.py (54 tests) - Findings Enhancements

Tests for individual code detection, count filtering, code pattern action persistence,
protagonist variable handling, no-truncation, details population, category consistency,
instance tracking, and collapsible instance expansion.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestDetectIndividualCodesBatch | 6 | Returns dict, empty lines, br tag, count accumulation, no examples, no sample |
| TestCountFilterParsing | 10 | Empty, bare number gte/lte, equals explicit, >X, <X, >=X, <=X, =X, invalid, whitespace, zero |
| TestCodePatternActionPersistence | 5 | New entry, update existing, valid actions, type in notes, replacement in notes |
| TestProtagonistNames | 6 | Male name, female name, single-token first, single-token surname, glossary format, code pattern entry |
| TestNoSpeakerTruncation | 3 | 50 speakers, 100 speakers, ordering preserved |
| TestDetailsPopulation | 3 | Speaker details from character glossary, code type, code type only |
| TestCategoryStringConsistency | 4 | Plural speaker, plural code pattern, matches builder, matches handler |
| TestFriendlyCodeType | 3 | Known types mapped, unknown passthrough, variable number |
| TestCodePatternMenuOptions | 3 | Has protagonist option, action options exclusive, type options exclusive |
| TestInstanceTracking | 4 | instances dict present, tracks raw codes, empty when no normalization, fallback path |
| TestFindingsInstanceExpansion | 5 | Expandable [+] prefix, non-expandable no prefix, instance children stored, instances-sort-first, expandable meta set |

```bash
python -m pytest CherryAI/dev/test_analysis_findings.py -v --timeout=10
```

---

## Phase 62 Test Files — File System and API Unification

### test_phase62_glossary.py (32 tests) — Task 62.1: Glossary TSV

Tests for `functions/glossary.py` TSV unification: path resolution, migration chain, 3-column format, GlossaryEntry serialisation, and Notes metadata encoding.

| Test Group | Count | Coverage |
|-----------|-------|----------|
| Path and Header | 4 | `_unified_glossary_path()` returns TSV, UNIFIED_HEADER = 3 cols, env var override, path under user/ |
| GlossaryEntry TSV | 6 | to_tsv_row() basic, from_tsv_row() roundtrip, metadata encoding in Notes, gender encoding, empty fields, source encoding |
| read/write roundtrip | 5 | write then read returns identical dict, empty glossary, unicode keys, multiple entries, overwrite |
| Migration | 7 | CSV->TSV, GlobalGlossary.csv->TSV, JSON merge->TSV, .migrated rename, no source = empty read, partial migration |
| filter_glossary_for_chunk | 5 | original match, translation match, no match filtered, empty glossary, case sensitivity |
| global glossary read | 5 | absent returns {}, header-only returns {}, malformed rows skipped, notes parsed, characters section |

```bash
python -m pytest dev/test_phase62_glossary.py -v --timeout=15
```

### test_phase62_codedb.py (27 tests) — Task 62.2: Code Database TSV

Tests for `functions/glossaries/code_glossary_db.py` TSV unification: path resolution, HEADER constant, migration from SQLite/CSV/JSON, 4-column compat API, and full 9-column extended API.

| Test Group | Count | Coverage |
|-----------|-------|----------|
| Path and Header | 3 | get_db_path() under user/, HEADER = 9 cols, env var override |
| init_db | 4 | creates TSV with header, idempotent, creates parent dirs, header row correct |
| Migration | 6 | SQLite migration preserves data, CSV migration, JSON merge, .migrated rename, combined chain, empty source |
| read_all_rows (4-col compat) | 5 | absent returns [], header-only returns [], data rows, extra cols ignored, malformed rows skipped |
| read_all_rows_extended (9-col) | 4 | all 9 cols returned, absent returns [], bool cols parsed, default empty string for missing |
| write_all_rows / upsert / delete | 5 | write roundtrip, upsert new, upsert update existing, delete existing row, delete nonexistent no-op |

```bash
python -m pytest dev/test_phase62_codedb.py -v --timeout=15
```

### test_phase62_api.py (25 tests) — Task 62.3: API Profiles Consolidation

Tests for `functions/api_config.py` profile settings and `functions/project_config.py` API profile CRUD using `user/API.ini`.

| Test Group | Count | Coverage |
|-----------|-------|----------|
| _ensure_sections | 2 | [translation] section created, [glossary] section created |
| get/set_profile_setting | 5 | read missing key returns fallback, write and read back, unknown profile creates section, empty value stored, unicode value |
| get_all_profile_settings | 3 | empty section returns {}, populated section returns dict, unknown profile returns {} |
| migrate_profiles_ini | 5 | non-secret fields migrated, api_key excluded, source renamed to .migrated, empty source no error, count returned |
| project_config CRUD | 10 | load_api_profiles() reads from API.ini, load triggers migration, save writes to API.ini, get reads fields, delete removes section, save excludes api_key, reload after save, delete nonexistent no error, profile isolation, all profiles loaded |

```bash
python -m pytest dev/test_phase62_api.py -v --timeout=15
```

### test_phase62_prompt.py (28 tests) — Task 62.4: Prompt Order Alignment

Tests for `functions/prompt_builder.py` `_construct_system_prompt()` 7-slot order, language direction header, separate Tone slot, merged Conditional block, and removal of output examples.

| Test Group | Count | Coverage |
|-----------|-------|----------|
| Language Direction (slot 1) | 4 | Header present, correct format, source/target from project_config, absent when langs missing |
| System Instructions (slot 2) | 3 | Base prompt present, position after direction, placeholder text excluded |
| Style (slot 3) | 3 | Style injected, position after instructions, empty style skipped |
| Tone (slot 4) | 3 | Tone injected as separate slot, position after style, empty tone skipped |
| Summary (slot 5) | 3 | Summary injected, placeholder skipped, ordering relative to tone |
| Conditional block (slot 6) | 5 | Context-type merged, POV merged, pattern-triggered merged, single slot ordering, empty conditional skipped |
| Glossary (slot 7) | 4 | Glossary last, characters inline no separate block, only terms in chunk, absent entries skip |
| Output examples removed | 3 | No output examples in system prompt, examples not in result, slot 3 is Style not examples |

```bash
python -m pytest dev/test_phase62_prompt.py -v --timeout=15
```

### test_phase62_dirs.py (17 tests) — Directory Initialisation and File Auto-Creation

Tests for `functions/ini_manager.py` `ensure_app_dirs()` and auto-creation of all critical files on first access.

| Test Function | Coverage |
|--------------|----------|
| test_ensure_app_dirs_creates_projects | Projects/ created by ensure_app_dirs() |
| test_ensure_app_dirs_creates_logs | logs/ created by ensure_app_dirs() |
| test_ensure_app_dirs_creates_cache | cache/ created by ensure_app_dirs() |
| test_ensure_app_dirs_creates_user | user/ created by ensure_app_dirs() |
| test_ensure_app_dirs_idempotent | Calling 3x does not raise |
| test_ensure_app_dirs_all_four_dirs | All 4 dirs created in single call |
| test_load_ini_triggers_dir_creation | _load_ini() creates Projects/, logs/, cache/ |
| test_cherryai_ini_created_when_absent | CherryAI.ini written on first _load_ini() |
| test_cherryai_ini_has_required_sections | All required sections present after creation |
| test_cherryai_ini_reinits_after_deletion | CherryAI.ini recreated with sections after delete |
| test_api_ini_created_when_absent | API.ini created on first write access |
| test_api_ini_reinits_after_deletion | API.ini recreated after deletion |
| test_globalglossary_tsv_created_when_absent | read_unified_glossary() returns {} when absent |
| test_globalglossary_tsv_reinits_after_deletion | read_unified_glossary() safe after deletion |
| test_codedatabase_tsv_created_on_init | init_db() creates codedatabase.tsv with correct header |
| test_codedatabase_tsv_reinits_after_deletion | init_db() recreates TSV after deletion |
| test_codedatabase_tsv_read_all_rows_absent | read_all_rows() returns [] when TSV absent |

```bash
python -m pytest dev/test_phase62_dirs.py -v --timeout=15
```


=============================================================================

## dev/test_model_registry.py — 140 tests

Tests for the dynamic model registry system, API config, and Costs tab features. Run with:
```bash
python -m pytest dev/test_model_registry.py -v --timeout=30
```

| Class | Tests | Description |
|-------|-------|-------------|
| `TestModelInfoDataclass` | 5 | Serialization, round-trip, unknown keys, pricing entry keys |
| `TestFallbackData` | 10 | All providers present, prices valid, capabilities, known models |
| `TestIniPersistence` | 9 | Save/load, sections, timestamps, multi-provider coexistence |
| `TestRefreshModels` | 5 | No-key/fallback, writes all 3 providers, subset refresh |
| `TestGetAllModels` | 8 | All providers, flat list, get_model_info (found/not/fallback) |
| `TestGetPricingDict` | 7 | Backward-compat keys, all 3 providers, float prices, no INI fallback |
| `TestStaleCache` | 6 | Timestamp logic, is_data_fresh before/after save/old-timestamp |
| `TestRegistrySummary` | 4 | All providers, required keys, count matches, freshness |
| `TestConfigModelPricingFunctions` | 4 | get_all_model_pricing returns dict, openai/google/mistral models present |
| `TestOptionsAPIProvidersProxy` | 10 | All providers present, get_provider_models for 3 cloud providers, reload |
| `TestEndToEndFlow` | 3 | Fresh INI → populate → read; pricing dict from INI; shared data |
| `TestStructuredOutputFilter` | 10 | Only structured_output=True models saved to registry |
| `TestRateLimitProbing` | 5 | Rate limit probe function, header parsing, RPM/TPM extraction |
| `TestDerivedConcurrent` | 6 | Concurrent slot derivation from RPM, defaults, boundary cases |
| `TestCurrentSelection` | 4 | current_selection write/read, provider.model format |
| `TestPerModelSettings` | 7 | Per-model settings CRUD, key validation, isolation |
| `TestCostsTabSaveSettings` | 8 | Save/load UI settings per model, round-trip, fallback handling |
| `TestRequestModeSettings` | 6 | Request mode round-trip, per-model mode, pricing keys, defaults |
| `TestTokenBreakdown` | 6 | content/prompt/cached tokens in EstimationResult, UI grid rows |
| `TestManifestEstimationPersistence` | 6 | Save/load full estimation to manifest, field coverage |
| `TestEstimateButtonRename` | 3 | Initial "▶ Estimate" → "↻ Update Counts" after first run |
| `TestLiveFetch` | 4 | **SKIPPED** unless `CHERRYAI_TEST_LIVE=1` — live OpenAI/Google/Mistral fetch |

**Key individual tests:**
- `test_from_dict_round_trip` — `ModelInfo.from_dict(m.to_dict())` preserves all 25+ fields
- `test_save_load_round_trip` — `save_to_ini()` → `load_from_ini()` preserves all models and pricing
- `test_refresh_with_no_keys_uses_fallback` — no-key path writes all 3 providers to INI
- `test_pricing_dict_has_expected_keys` — ensures `name`/`input`/`output`/`concurrent`/`token_speed` keys
- `test_end_to_end_analysis_translation_same_data` — Analysis and Translation steps use same model data

**Live test prerequisites** (for `TestLiveFetch`):
```bash
set CHERRYAI_TEST_LIVE=1
set OPENAI_API_KEY=sk-...
set GOOGLE_API_KEY=...
set MISTRAL_API_KEY=...
python -m pytest dev/test_model_registry.py::TestLiveFetch -v
```
=============================================================================

## dev/test_api_keys.py — 50 tests

Tests for the API key management, connection testing, encrypted storage pipeline, plaintext key storage, and password disable/reset. Run with:
```bash
python -m pytest dev/test_api_keys.py -v --timeout=30
```

| Class | Tests | Description |
|-------|-------|-------------|
| `TestPasswordManagement` | 7 | Set/verify/change password, wrong password, empty password |
| `TestApiKeyStorage` | 10 | Set/get with default and custom names, multi-provider, overwrite, special chars |
| `TestIniFormat` | 3 | `provider, name` INI key format, Fernet encryption verification, security section fields |
| `TestListDeleteKeys` | 6 | List all keys, delete existing/nonexistent, preserve unrelated keys |
| `TestConnectionTest` | 8 | Empty key, unknown provider, mock success/auth/timeout/connection errors, custom URL; all return `(bool, str, list)` 3-tuple with model ID list |
| `TestConnectionTestLive` | 3 | **Live** tests with Google Gemini API (valid/invalid key, explicit URL); assert models list populated |
| `TestProviderBaseUrls` | 4 | Known providers have URLs, specific URL validation |
| `TestApiKeyOptionHelper` | 3 | `_api_key_option()` format, whitespace stripping, case preservation |
| `TestPasswordStrength` | 5 | Tier assessment: Instantly, Weak, Safe, meter_text |
| `TestFullPipeline` | 2 | End-to-end lifecycle (set pw → save → list → load → delete), change_password re-encrypts all |

**Key individual tests:**
- `test_multiple_keys_per_provider` — Two keys for same provider stored and retrieved independently
- `test_ini_key_format_provider_comma_name` — Verifies `[api_keys]` uses `provider, name` as INI option
- `test_ini_value_is_encrypted` — Stored value starts with `gAAAAA` (Fernet token), not plaintext
- `test_google_gemini_valid_key` — Live test validates connection to Gemini API (43+ models), asserts models is a list
- `test_google_gemini_invalid_key` — Live test confirms invalid key properly rejected, models list empty
- `test_auth_error_returns_invalid_key` — Mock 401 → "Authentication failed" message, 3-tuple return
- `test_full_lifecycle` — Complete CRUD cycle: password → 3 keys → list → retrieve → delete → verify

**Return type change (all callers updated):**
- `test_api_connection()` returns `(bool, str, list)` — third element is list of model IDs
- All `TestConnectionTest` and `TestConnectionTestLive` tests unpack 3-tuple: `ok, msg, models = ...`
- Success tests assert `isinstance(models, list)` and `len(models) > 0`
- Failure tests assert `models == []`

=============================================================================

## dev/test_request_preview.py — 44 tests

Tests for the Preview Requests feature: `PreviewRequest` dataclass, `FILTER_PARTS` constant, `RequestPreviewDialog` class, and `_build_preview_requests()` integration. Run with:
```bash
python -m pytest dev/test_request_preview.py -v --timeout=15
```

| Class | Tests | Description |
|-------|-------|-------------|
| `TestPreviewRequestDataclass` | 8 | `get_part()`, `build_full_request_text()` with/without filters, empty parts skipped, `build_pure_json()` valid JSON, temperature extraction, `request_params` passthrough, `line_count` |
| `TestFilterParts` | 3 | 13 entries in `FILTER_PARTS`, unique keys, keys match dataclass field names |
| `TestViewModes` | 4 | Pure returns valid JSON, Formatted has section headers (═══), Plain preserves curly braces but strips brackets/quotes, Plain wraps long lines |
| `TestRequestPreviewDialogCreation` | 5 | Dialog opens/closes, shows request count, Jump To navigates, clamp high, clamp low |
| `TestRequestPreviewDialogSearch` | 4 | Search finds matches with highlighting, no-match shows "0 of 0", next wraps around, prev wraps around |
| `TestRequestPreviewDialogFilter` | 3 | Deselect hides section from display, Select All restores, Deselect All clears |
| `TestRequestPreviewDialogViewModes` | 3 | Switch to Pure validates JSON, switch to Plain strips markers, switch to Formatted shows headers |
| `TestBuildPreviewRequests` | 6 | Correct chunk count (3 lines / chunk_size 2 → 2 requests), all parts populated, prompt cache key appears in Meta + Pure JSON, input_lines valid JSON, POV excluded on low confidence, glossary entries present with selective per-chunk filtering |
| `TestEdgeCases` | 7 | Empty request list, all empty parts, Unicode in Pure JSON, case-insensitive search, info label updates, cross-request search counts across all requests, cross-request navigation switches requests |

**Key implementation details tested:**
- `PreviewRequest.build_pure_json()` — Produces valid JSON with `messages` array (system + user), `model`, `temperature`, and any effective request metadata such as `prompt_cache_key`
- `RequestPreviewDialog` — Headless Tk tests (2 may skip on CI where Tk is unavailable)
- `_build_preview_requests()` — Integration test using mocked `TranslationStep` with `_build_chunks` side effect, patched `build_conditional_instructions` and `load_glossary_entries`
- Cross-request search — `_do_search()` scans all requests, `_search_next()`/`_search_prev()` navigate across request boundaries with global match index
- Section headers — `=== Label (description) ===` format with `SECTION_DESCRIPTIONS` dict
- Selective glossary — Only glossary entries whose source term appears in chunk lines are included
- Formation-aware chunking — `_build_chunks()` integrates `build_requests()` from `prompt_builder.py`

**Session 30 updates:** Added 2 cross-request search tests (`test_cross_request_search_counts`,
`test_cross_request_search_navigates`). Updated `FILTER_PARTS` count 9→12 for new sections
(language, genre, rolling_context). Updated header assertions for `=== Label (desc) ===` format.
Updated `_make_request` helper with language/genre/rolling_context fields.
Updated glossary test for selective per-chunk filtering (source terms in input lines).

**Session 31 updates:** Added prompt-cache metadata coverage for Preview Requests:
`build_pure_json()` now tests `request_params` passthrough, `_build_preview_requests()`
verifies `prompt_cache_key` visibility in both Meta and Pure JSON, and fixtures now include
the current `io_examples` field plus the metadata enable flags used by the live request builder.

---

### dev/test_knowledge_base.py (56 tests)

**Purpose**: Comprehensive tests for the Knowledge Base widget (TASK 76), covering Active column support in TSV files, collapsible widget redesign, Knowledge Base widget structure, prompt adapter integration, and button text standardization.

**Test Classes**:

#### TestGlossaryEntryActive (10 tests)
- `test_default_active_true` — GlossaryEntry defaults active=True
- `test_active_false` — GlossaryEntry(active=False) stores False
- `test_to_tsv_row_active_true` — to_tsv_row() includes "True" as 4th element
- `test_to_tsv_row_active_false` — to_tsv_row() includes "False" as 4th element
- `test_from_tsv_row_active_true` — from_tsv_row(["a","b","c","True"]) sets active=True
- `test_from_tsv_row_active_false` — from_tsv_row(["a","b","c","False"]) sets active=False
- `test_from_tsv_row_missing_active` — 3-element row defaults active=True (backward compat)
- `test_roundtrip_active_true` — to_tsv_row → from_tsv_row preserves active=True
- `test_roundtrip_active_false` — to_tsv_row → from_tsv_row preserves active=False
- `test_active_in_repr` — repr(GlossaryEntry) includes active field

#### TestUnifiedGlossaryActiveIO (3 tests)
- `test_write_includes_active_column` — Written TSV header has 4 columns including Active
- `test_read_preserves_active_false` — Read-back of written file preserves active=False
- `test_legacy_3col_defaults_active` — Old 3-column TSV rows default active=True

#### TestCodeDatabaseActive (5 tests)
- `test_header_has_active` — HEADER list includes "Active" as last column
- `test_num_cols_is_10` — _NUM_COLS == 10
- `test_pad_row_9col_gets_active` — 9-element legacy row padded to 10 columns
- `test_pad_row_10col_unchanged` — 10-element row passes through unchanged
- `test_write_read_roundtrip_active` — Full write → read roundtrip preserves Active column

#### TestUnifiedHeader (2 tests)
- `test_unified_header_has_4_columns` — UNIFIED_HEADER has exactly 4 elements
- `test_unified_header_contains_active` — "Active" is in UNIFIED_HEADER

#### TestCollapsibleDesign (4 tests)
- `test_no_labelframe_in_collapsible_builder` — Source code does not use ttk.LabelFrame
- `test_separator_in_collapsible_builder` — Source uses ttk.Separator in header
- `test_extra_header_widgets_param` — Method signature accepts extra_header_widgets
- `test_collapsible_returns_body` — Method returns a Frame (the body)

#### TestKnowledgeBaseStructure (8 tests)
- `test_build_method_exists` — `_build_knowledge_base_section` exists on InformationStep
- `test_kb_mode_switch_exists` — `_kb_mode_var` attribute created
- `test_kb_tree_exists` — `_kb_tree` Treeview attribute created
- `test_kb_search_exists` — `_kb_search_var` attribute created
- `test_kb_enabled_var_exists` — `_kb_enabled_var` BooleanVar attribute created
- `test_kb_count_var_exists` — `_kb_count_var` StringVar attribute created
- `test_kb_activate_btn_exists` — `_kb_activate_btn` button exists
- `test_kb_copy_btn_exists` — `_kb_copy_btn` button exists

#### TestKnowledgeBaseHelpers (12 tests)
- `test_toggle_kb_enabled_method` — `_toggle_kb_enabled` method exists
- `test_refresh_kb_method` — `_refresh_kb` method exists
- `test_configure_kb_columns_method` — `_configure_kb_columns` method exists
- `test_load_kb_entries_method` — `_load_kb_entries` method exists
- `test_save_kb_entries_method` — `_save_kb_entries` method exists
- `test_add_kb_entry_method` — `_add_kb_entry` method exists
- `test_remove_kb_entry_method` — `_remove_kb_entry` method exists
- `test_on_kb_click_method` — `_on_kb_click` method exists
- `test_on_kb_double_click_method` — `_on_kb_double_click` method exists
- `test_start_kb_inline_edit_method` — `_start_kb_inline_edit` method exists
- `test_update_kb_activate_btn_method` — `_update_kb_activate_btn` method exists
- `test_toggle_kb_active_method` — `_toggle_kb_active` method exists

#### TestMixedActivateFailsafe (2 tests)
- `test_show_mixed_activate_popup_method` — `_show_mixed_activate_popup` method exists
- `test_copy_project_to_global_method` — `_copy_project_to_global` method exists

#### TestButtonText (4 tests)
- `test_add_button_text_compact` — "+Add" appears in source (not "+Add Character" etc.)
- `test_remove_button_text_compact` — "Remove" appears (not "Remove Selected")
- `test_edit_button_text` — "Edit" button text used
- `test_no_remove_selected_text` — "Remove Selected" does NOT appear in _build_knowledge_base_section

#### TestEnabledDisabledPrompt (3 tests)
- `test_prompt_adapter_filters_inactive` — build_full_system_prompt() excludes inactive glossary entries
- `test_prompt_adapter_includes_active` — Active entries are included in prompt
- `test_prompt_adapter_default_active` — Entries without explicit active field default to included

#### TestCollapsibleState (2 tests)
- `test_collapsible_state_three_keys` — _collapsible_state has exactly 3 keys
- `test_collapsible_state_key_names` — Keys are "glossary", "code_database", "knowledge_base"

#### TestKnowledgeBaseTestCount (1 test)
- `test_knowledge_base_tests_count` — Self-validation: at least 56 tests in file

### dev/test_estimation_skip.py (41 tests) — Phase 78 Estimation Skip Logic

Tests for `_get_skip_indices()` in the costs step: skip non-source language lines,
overwrite-off skips existing translations, symbol-only dialogue, generic placeholders
(`__PLACEHOLDER__`, `__DEDUP__`).

### dev/test_rolling_context_phase78.py (10 tests) — Phase 78 Rolling Context

#### TestFormationReceivesContext (4 tests)
- First request of file section gets `receives_context=False`
- Subsequent requests get `receives_context=True`
- Multiple file sections each reset `receives_context`
- Single-file formation keeps first request without context

#### TestTranslationBufferReset (2 tests)
- Buffer cleared at file boundaries
- Buffer preserved within same file section

#### TestPreviewRollingContext (3 tests)
- Preview shows actual original lines from manifest
- File-first-idx respected in preview

#### TestRollingContextPhase78Count (1 test)
- Self-validation: at least 10 tests in file

### dev/test_rolling_context_merge.py (37 tests) — Task 78 Rolling Context Extensions & Efficient Merge

#### TestRollingContextConfigFields (2 tests)
- Default values for `lines_between` and `lines_after`
- Custom values round-trip through constructor

#### TestFormatRollingContextType (4 tests)
- Default context_type produces "before" label
- `context_type="between"` / `"after"` produce distinct labels
- Empty input returns empty string

#### TestRequestFormationConfigExtended (2 tests)
- `efficient_merge` defaults to False
- `rolling_context_between` / `rolling_context_after` defaults to 0

#### TestTranslationRequestMerge (3 tests)
- Not merged by default (empty `_merge_boundaries`)
- `is_merged` True when boundaries have >1 entry
- Single boundary → not merged

#### TestStep5EfficientMerge (11 tests)
- Disabled when `efficient_merge=False`
- Merges singleton file sections across boundaries
- Respects `max_lines` limit
- Skips menu/choice requests
- Skips requests with `receives_context=True`
- Blocks when next request has `receives_context=True`
- Gap blocked when `rolling_context_between > 0`
- Contiguous merges even with between-context configured
- Three-way merge tracks all boundaries
- `_merge_boundaries` records original block sizes
- Empty input returns empty

#### TestBuildRequestsEfficientMerge (3 tests)
- Integration: singleton files merge in efficient mode
- Multi-request files keep internal context chain
- Conservative mode skips Step 5

#### TestBuildMergedRequestInstruction (6 tests)
- Empty / single boundary returns empty
- All single-line blocks → "All lines are unrelated to each other."
- Two blocks → describes first/last block boundaries
- Three mixed blocks → describes all boundaries
- Two single lines → all-unrelated message

#### TestRequestSettingsSerialization (2 tests)
- Round-trip for `rolling_context_between`, `rolling_context_after`, `use_translated_context`
- Default values

#### TestRequestBatchContext (4 tests)
- Empty context fields, `has_rolling_context` False
- `has_rolling_context` True for before/between/after

### dev/test_slicing_phase78.py (11 tests) — Phase 78 Slicing Efficient Mode

#### TestSlicingMinLines (3 tests)
- Efficient mode: `min_lines = max(5, chunk_size // 2)`
- Conservative mode: `min_lines = max(2, chunk_size // 5)`
- Both modes respect chunk_size upper bound

#### TestSlicingMergeEffect (3 tests)
- Efficient merges aggressively within file sections
- Conservative preserves more separate requests
- File boundaries prevent cross-file merges

#### TestSlicingInCosts / TestSlicingInTranslation (4 tests)
- Costs step and translation step respect slicing mode independently

#### TestSlicingPhase78Count (1 test)
- Self-validation: at least 11 tests in file

### dev/test_char_filter_phase78.py (32 tests) — Phase 78 Blacklist/Whitelist Validation

#### TestParseFilterEntries (11 tests)
- Empty/whitespace → empty list
- Single token, multiple tokens, whitespace trimmed
- `\,` literal comma, `re=` regex entries, invalid regex skipped
- Plain token matching, mixed entries

#### TestCheckFilterViolations (7 tests)
- No filters → no violations
- Blacklist match / no match / regex
- Whitelist violation, whitespace allowed, both filters combined

#### TestTranslationSettingsCharValidation (3 tests)
- Default values, custom values, roundtrip via to_dict/from_dict

#### TestApplyCharFiltersExchange (3 tests)
- Exchange replaces blacklisted chars via autofix map
- No autofix match leaves text, flags instead
- Exchange disabled skips replacement

#### TestApplyCharFiltersRetry (2 tests)
- Retry empties text and resets line to PENDING
- No retry for clean lines

#### TestApplyCharFiltersFlag (2 tests)
- Flag sets NEEDS_REVIEW status on violation
- Flag disabled preserves original status

#### TestApplyCharFiltersRegex (2 tests)
- Regex blacklist triggers flagging
- Literal comma in entry matches correctly

#### TestApplyCharFiltersNoFilter (1 test)
- Empty filters pass through unchanged

#### TestCharFilterPhase78Count (1 test)
- Self-validation: at least 25 tests in file
---

### 	est_gui_cleanup_phase40.py (Phase 40 GUI Cleanup & Refactor)

**Overview:** Confirms that application UI routing, window titling dynamically adapts to manifest context, and checks the architectural logic decoupling from legacy constraints.
**Test Classes:**
- TestGUIPhase40 (3 tests)
  - _Test Update Window Title_: Confirms App window extracts project name correctly or falls back gracefully without project.
  - _Test Input Dialog Tuple Structure_: Ensures UnifiedInputDialog returns a well-formed 5-element tuple (paths, fmt, enc, proj, pipeline) for input configurations.
  - _Test On Remove Selected File_: Confirms that deleting a file dynamically targets the underlying ManifestManager.remove_file(rel_path) bypassing frontend trees.

---

### `test_manifest_remove.py` (Phase 40 Manifest Deletion Routing)

**Overview:** Validates that manipulating project datasets through coordinate intersections shifts arrays correctly natively inside JSON representations before file writes.
**Test Classes:**
- TestManifestRemove (4 tests)
  - _Remove Not Found_: Gracefully ignores missed path strings.
  - _Remove Middle File_: Confirms lines are deleted accurately and subsequent indices loop and subtract correctly down to lower indices, shifting ranges and idx.
  - _Remove First File_: Validates front-load shifting. 
  - _Remove Last File_: Validates end truncation behavior without throwing key out-of-bounds errors on empty trails.

---

### Task 41: Max Input Tokens (test_max_input_tokens.py)

**File:** `dev/test_max_input_tokens.py`
**Test Count:** 34
**Coverage:** RequestSettings.max_input_tokens field, GlobalOptions integration, RequestFormationConfig.max_tokens plumbing, build_requests token enforcement, costs estimation, edge cases, INI persistence

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestRequestSettingsMaxInputTokens | 7 | Default value, custom value, to_dict, from_dict, missing key default, roundtrip |
| TestGlobalOptionsMaxInputTokens | 4 | GlobalOptions default, to_dict, from_dict, roundtrip |
| TestRequestFormationConfigMaxTokens | 3 | Default zero, custom, coexistence with max_lines |
| TestBuildRequestsMaxTokens | 7 | No limit single request, token limit splitting, token tighter than lines, lines tighter than tokens, zero means no limit, all lines preserved, file boundaries |
| TestStep3TokenSplitting | 3 | Split by tokens, no split below limit, balanced splitting |
| TestCostsStepMaxInputTokens | 2 | Hybrid estimation with tokens, EstimationResult dataclass |
| TestMaxInputTokensEdgeCases | 6 | Zero no limit, single line exceeds limit, all short single request, empty lines skipped, negative treated as no limit, negative defaults to zero |
| TestINIPersistence | 2 | Persist key name, field roundtrip |

```bash
# Run Task 41 tests
python -m pytest CherryAI/dev/test_max_input_tokens.py -v --timeout=10
```

---

### dev/test_api_error_classification.py (56 tests) - TASK 78.1

API error classification system tests. Validates the `APIErrorCategory` enum,
`ClassifiedAPIError` dataclass, `classify_api_error()` function, and
`TranslationAbortError` exception class.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestAPIErrorInfoCompleteness | 2 | All categories have entries, no stale keys |
| TestBuildClassified | 2 | Default fields, custom is_fatal/is_retryable |
| TestClassifyByExceptionType | 10 | Auth, permission, not-found, rate-limit (429/quota), bad-request variants, timeout, server error, connection |
| TestClassifyByMessage | 14 | HTTP status codes (400-504), keyword matching (rate limit, timeout, overloaded, invalid JSON, content filter, billing, etc.) |
| TestTranslationAbortError | 5 | Properties, display (fatal/unknown), user_message passthrough |
| TestClassifiedAPIErrorDefaults | 2 | Default retryable/fatal, custom override |
| TestEdgeCases | 5 | Empty message, None attributes, generic Exception, nested messages, very long messages |

```bash
python -m pytest dev/test_api_error_classification.py -v --timeout=10
```

---

### dev/test_first_request_gate.py (14 tests) - TASK 78.2

First-request validation gate and instant-stop behaviour tests. Validates
that `_translate_chunk_with_retry()` in `api_client.py` classifies errors
and raises `TranslationAbortError` for fatal errors without retrying.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestRetryFatalErrors | 5 | Auth (text + SDK type), model-not-found, non-structured output, quota exceeded |
| TestRetryRetryableErrors | 4 | Rate-limit (real SDK), timeout recovery, TranslationError timeout retries, server error (real SDK) |
| TestTranslateChunkError | 3 | Invalid JSON, non-list translation, API error propagation |
| TestAbortErrorDisplay | 2 | Fatal display shows steps, unknown shows raw message |

```bash
python -m pytest dev/test_first_request_gate.py -v --timeout=10
```

---

### dev/test_request_sorting.py (22 tests) - TASK 78.4

Request string sorting by type priority tests. Validates `sort_requests_by_type()`
and `RequestString` dataclass from `prompt_builder.py`.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestBasicSorting | 4 | Empty, single, type ordering (dialogue > choice > menu), full priority chain |
| TestRollingContextChains | 5 | Chain detection, section boundaries, receives_false breaks chain, RC chains before standalone, chain order preserved |
| TestSizeSort | 2 | Longer strings first, type priority overrides size |
| TestRequestStringDataclass | 3 | Priority property, line_count, has_rolling_context |
| TestContextTypePriority | 3 | Dialogue highest, menu lowest, choice between |
| TestEdgeCases | 5 | Mixed types in section, document order in chain, dominant type detection, priority consistency, chain dominant multi-type |

```bash
python -m pytest dev/test_request_sorting.py -v --timeout=10
```

---

### dev/test_concurrent_execution.py (23 tests) - TASK 78.5

Concurrent request execution engine tests. Validates `_process_single_chunk()`,
`_execute_string_sequential()`, `_group_chunks_into_strings()`, and
ThreadPoolExecutor-based parallel string execution.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestGroupChunksIntoStrings | 5 | Empty, single, two independent, RC chain stays together, mixed chains + standalone |
| TestProcessSingleChunk | 6 | Successful translation, cancel before processing, abort on fatal, rolling context extends, rolling context clears, thread-safe progress |
| TestExecuteStringSequential | 4 | Sequential order, cancel stops, abort raises TranslationAbortError, rolling context flows |
| TestConcurrentExecution | 3 | Independent strings run in parallel, abort in one stops others, sequential fallback with max_concurrent=1 |
| TestEdgeCases | 5 | Empty string group, single-line chunk, already-set abort skips, provides_context=False, source text context |

```bash
python -m pytest dev/test_concurrent_execution.py -v --timeout=10
```

---

### dev/test_context_type_prompts.py (18 tests) - TASK 78.6

Context-type conditional prompt injection tests. Validates that `context_type`
flows from `_formation_ctx` through `_translate_chunk` →
`_build_system_prompt_from_manifest` → `build_full_system_prompt` →
`get_context_prompt`, ensuring §5.2 item 7b is correctly injected.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestGetContextPrompt | 6 | Dialogue, menu, choice, unknown, unrecognised, empty |
| TestBuildFullSystemPromptContextType | 5 | Dialogue injected, menu injected, choice injected, no type = no injection, unknown type |
| TestMergeInstruction | 2 | Merge instruction injected, empty not injected |
| TestBuildMergedRequestInstruction | 3 | Basic merge, single boundary, empty boundaries |
| TestTranslateChunkContextTypeFlow | 2 | context_type reaches prompt, merge_boundaries generate instruction |

```bash
python -m pytest dev/test_context_type_prompts.py -v --timeout=10
```

---

### dev/test_input_import_fixes.py (23 tests) — Input & Import Fixes

Tests for Input step fixes and Import Translation improvements.

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestSafeOutputFormat | 8 | Empty, whitespace, valid formats, uppercase, invalid, numeric |
| TestAddFiles | 8 | Single add, preserved lines, sorted order, contiguous idx, duplicate raises, multiple, empty, type preserved |
| TestImportLineFields | 3 | Translated only, skip already translated, QA fields |
| TestImportSettingsSections | 4 | Preprocessing, postprocessing, nothing selected, wordwrap settings |

```bash
python -m pytest dev/test_input_import_fixes.py -v --timeout=10
```

---

### dev/test_lightvn_fixes.py (37 tests) — LightVN Detection, Tags & Input Fixes

Tests for LightVN parser detection expansion, ~文字 menu parsing, tag propagation, staged `Original/` re-extraction during Input sync, and explicit rel-path original staging before filedir rebuild.
to manifest tag, messagebox import shadowing fix, and source file copy
rel_path matching.

**Files Tested:** `formats/LightVN.py`, `gui/steps/input_extract.py`, `functions/manifest_manager.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestCanHandleExpanded | 14 | Speaker tag, ~文字, ~絵, ~ボタン, ~効果音, ~選択, 栞 prefix, `~栞` prefix, `~スクリプト`, bare script/variable-only files, plain text reject, non-txt reject, chara_make pattern, bookmark without tilde |
| TestMojiMenuParsing | 7 | Basic ~文字, fullwidth parens, ASCII parens inside quoted text, multiple lines, full context, ~文字窓 variant, no quoted text |
| TestTagPropagation | 4 | LoadedFile stores tags, default None, sync sets tag, tag assignment |
| TestMessageboxFix | 2 | No local messagebox import in _load_selected_paths (AST), module-level import exists |
| TestCopyOriginalsRelPathMatching | 3 | No filename-only matching (AST), uses _find_common_base, matches entry rel_path |
| TestFullFileIntegration | 5 | chara_make-style file, dialogue tags, mixed tags, _DETECT_PATTERNS set, _DETECT_LINE_PREFIXES tuple |

```bash
python -m pytest dev/test_lightvn_fixes.py -v --timeout=10
```

---

### dev/test_postpro_pipeline.py (48 tests) — Preprocessing/Postprocessing Round-Trip

Tests for the full preprocessing → postprocessing reversal pipeline. Validates that
every preprocessing transformation is correctly reversed during postprocessing,
including protect code, custom placeholders, ellipsis compression, anchoring,
deduplication, and PROTECTED token compression/decompression.

**Files Tested:** `gui/helpers/mode_adapter.py`, `gui/steps/postprocess.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestPreprocessingOrder | 3 | Protect code before symbol conversion, custom placeholder before symbol, symbol conversion after protection |
| TestProtCompression | 4 | Compress 2, compress 3, no compress single, decompress roundtrip |
| TestProtectCodeRestore | 5 | Capture single, capture multiple, restore single, restore multiple order, restore no data noop |
| TestCustomPlaceholderRestore | 3 | Capture literal, restore literal, restore no data noop |
| TestEllipsisRoundtrip | 4 | Batch captures counts, compress and decompress, reverse ellipsis method, JP ellipsis roundtrip |
| TestAnchoring | 5 | Remove anchors with adjacent anchors, remove no adjacent anchor (stays), anchor records capture values, restore anchors new format (anchor-relative), anchor batch captures |
| TestDedupRestoration | 3 | Standard dedup map, aggressive dedup numbers, aggressive restore line |
| TestFullPipelineRoundtrip | 16 | Per-index preprocessing checks (idx 0–8), postprocess prot decompression, protect restore, full idx6/idx7/idx5/idx8 roundtrips, stats completeness |
| TestEdgeCases | 5 | Empty line, no changes no stats, prot decompression no tokens, restore more tokens than values, anchor no entries |

```bash
python -m pytest dev/test_postpro_pipeline.py -v --timeout=10
```


---

## `dev/test_output_injection.py` — 39 tests

Tests for the Output Injection Standardization (Phase 79): standardized inject_to
handshake with Speaker:Dialogue awareness, INJECTION OutputFormat, fresh line reads,
Same as Source directory fix, the _write_injection 4-step parser handshake,
`_split_speaker_dialogue` helper, and Speaker:Dialogue-aware injection scenarios.

**Files Tested:** `formats/parser_base.py`, `formats/LightVN.py`, `gui/steps/output_inject.py`

| Test Class | Count | Coverage |
|-----------|-------|----------|
| TestStandardInjectTo | 8 | Simple replacement, duplicate handling, failure on missing, no-change same text, fallback without orig_lines, parent dir creation, long JSON sequential, returns list type |
| TestLightVNInjectSignature | 2 | Accepts orig_lines kwarg, returns list |
| TestFreshLineReads | 2 | _get_fresh_lines_for_file reads from manifest not stale cache, fallback to session |
| TestSameAsSourceDir | 3 | Parent of Original, translated next to Original, fallback to cwd |
| TestInjectionFormat | 4 | Enum member exists, in descriptions, in extensions (empty), _safe_output_format parses it |
| TestWriteInjection | 2 | Full handshake simple case, mismatch preserves original |
| TestBuildFileListInjection | 1 | Injection format preserves extension |
| TestInjectToEdgeCases | 3 | Empty lines, source not found, partial replacement |
| TestSplitSpeakerDialogue | 4 | Half-width colon split, fullwidth colon split, no colon returns empty speaker, multiple colons splits on first |
| TestSpeakerDialogueInjection | 10 | Speaker+dialogue replaced separately, consecutive same-speaker skip, narration plain replace, same-speaker preserved, dialogue not found failure, spaces preserved, mixed speaker/plain lines, alternating speakers, no-change tracking, fallback without extract_tagged |

```bash
python -m pytest dev/test_output_injection.py -v --timeout=10
```


