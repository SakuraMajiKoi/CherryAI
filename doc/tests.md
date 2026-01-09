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

## Script Test (pytest)

**Location:** `dev/test_*.py`  
**Runner:** `pytest`  
**Count:** 3177 tests collected, 3177 passed, 26 skipped (integration tests)
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
- If you see `ModuleNotFoundError`, ensure you are running from `c:\Users\patri\TLUtility\utility`.
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
| `test_get_input_for_postprocessing_with_edits` | Post uses latest edit/tlc |
| `test_get_input_for_postprocessing_with_tlc_only` | Post uses latest tlc if no edits |
| `test_get_input_for_postprocessing_fallback` | Post falls back through tl → prepro → orig |
| `test_get_input_for_wordwrap_with_postpro` | Wordwrap uses postpro if available |
| `test_get_input_for_wordwrap_fallback` | Wordwrap falls back to postprocessing resolution |

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
| `test_attributes` | Protect Code has NAME, PHASE, PRIORITY=20 |
| `test_apply_pre_replaces_with_prot` | Replaces with __PROT__ |
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

### dev/test_formats.py (52 tests) - NEW (TASK 15.7)

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

#### TestJsonHandler (7 tests)

| Test | Purpose |
|------|---------|
| `test_json_handler_format_id` | JsonHandler has format_id, supports_pairs |
| `test_json_extract_string_array` | Handles array of strings |
| `test_json_extract_pairs_array` | Handles [original, translated] pairs |
| `test_json_extract_object_array` | Handles objects with original/translated |
| `test_json_inject_simple` | Writes array of strings |
| `test_json_inject_with_pairs` | Writes objects when original provided |
| `test_json_get_metadata` | get_metadata() returns structure info |

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
| test_conditional_prompts.py | 45 | Conditional prompts with dynamic examples (TASK 5) |
| test_config.py | 23 | Config management |
| test_dedup.py | 26 | Deduplication |
| test_dependencies.py | 17 | Dependency checking (TASK 15.1) |
| test_formats.py | 52 | Formats module handlers (TASK 15.7) |
| test_functions_v2.py | 15 | Functions integration |
| test_game_summary.py | 22 | Game summary & project config |
| test_gender_inference.py | 21 | Gender inference |
| test_glossary.py | 30 | Glossary management |
| test_gui_analysis_integration.py | 45 | GUI-Analysis integration (TASK 16.6 + 18.1) |
| test_gui_chunker_integration.py | 87 | GUI-Chunker integration (TASK 16.8) |
| test_gui_glossary_integration.py | 76 | GUI-Glossary integration (TASK 16.7) |
| test_gui_modi_integration.py | 45 | GUI-Modi integration (TASK 16.5) |
| test_gui_progress.py | 24 | GUI progress indicators (TASK 15.12) |
| test_gui_v2.py | 595 | GUI v2 framework (TASK 15.8-15.14: core + theme/CLI/deprecated) |
| test_session_persistence.py | 40 | Session auto-save/load, step persistence, file restoration (Release Stabilization) |
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
| test_model_selection.py | 23 | Model presets (TASK 8) |
| test_modi_all.py | 44 | Modi comprehensive (TASK 15.6) |
| test_modi_v2.py | 14 | Modi integration |
| test_options.py | 29 | Options dialog & API config |
| test_partial_translation.py | 18 | Partial translation mode (TASK 9) |
| test_postprocess.py | 79 | Post-process recovery suite |
| test_project_config.py | 19 | Project configuration |
| test_quote_stripping.py | 33 | Quote stripping modes |
| test_rate_limiter.py | 70 | Rate limiting system |
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
| test_gui_dialogs.py | 14 | GlobalOptions dialog tests (TASK 18.7) |
| test_cli_estimation.py | 13 | CLI estimation verification (TASK 18.6) |
| test_manifest_automation.py | 12 | Manifest auto-creation (TASK 18.8) |
| test_glossary_integration.py | 12 | Analysis→Information integration (TASK 18.4) |
| test_gui_layout.py | 12 | 2-column layout tests (TASK 18.2) |
| test_subtask_tracking.py | 14 | Subtask progress tracking (TASK 18.3) |
| test_code_glossary_display.py | 12 | Code glossary widget (TASK 18.5) |
| smoke_test/*.py | 5+ | Smoke tests |
| **Total Script Tests** | **2803** | (+89 from Phase 18) |
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
| J | Shorter __PROT__ Placeholder | ✅ Already using __PROT__ |
| K | Content Warning System | ✅ check_content_warning() |

**Tests Passing:**
- 566 pytest tests (all conditional prompt tests updated)
- 34 conditional_prompts.py tests specifically
- All instructions work with shorter text

**Files Modified:**
- functions/api_client.py: Log header, token tracking, content warning
- functions/prompt_builder.py: Section ordering, empty section skip, examples
- functions/conditional_prompts.py: All 14 instructions shortened
- functions/mainhelper.py: Call write_log_header()
- config/base_instructions.txt: NEW - generic instructions
- config/output_examples.txt: NEW - JSON format examples
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
pytest dev/test_manifest_v2.py dev/test_modi_v2.py dev/test_functions_v2.py dev/test_replication.py dev/test_config.py dev/test_dedup.py dev/test_options.py dev/test_validation.py dev/test_conditional_prompts.py -v
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

### dev/test_dedup.py (26 tests)

Deduplication module tests validating placeholder tokens, normalization, and roundtrips.

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

---

### dev/test_options.py (29 tests)

Options dialog and API configuration tests validating providers, languages, and settings.

#### TestAPIProviders (5 tests)

| Test | Purpose |
|------|---------|
| `test_providers_exist` | All expected providers defined |
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

#### TestValidateLinePre (12 tests)

| Test | Purpose |
|------|---------|
| `test_empty_line` | Skip empty lines |
| `test_comment_line` | Skip # prefixed lines |
| `test_equals_line` | Skip = prefixed lines |
| `test_dedup_only` | Skip __DEDUP__ only lines |
| `test_prot_only` | Skip __PROT__ only lines |
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
| `test_preserve_comments` | Preserve comment lines |
| `test_no_preserve` | Don't preserve when disabled |

#### TestValidationIntegration (1 test)

| Test | Purpose |
|------|---------|
| `test_full_pipeline` | Complete validation pipeline |

---

### dev/test_conditional_prompts.py (45 tests)

Conditional prompt system tests for pattern-triggered LLM instruction injection with dynamic examples.

#### TestConditionalPrompt (8 tests)

| Test | Purpose |
|------|---------|
| `test_create_basic` | Create conditional prompt with defaults |
| `test_matches_simple_pattern` | Match single pattern in text |
| `test_matches_multiple_patterns` | Match multiple patterns in text |
| `test_no_match` | No patterns matched returns false |
| `test_serialization_roundtrip` | to_dict and from_dict preserve data including pattern_examples |
| `test_get_dynamic_instruction_no_examples` | Dynamic instruction returns base when no examples |
| `test_get_dynamic_instruction_with_examples` | Dynamic instruction includes relevant examples |
| `test_get_dynamic_instruction_multiple_examples` | Multiple matched patterns show multiple examples |

#### TestBuiltinConditions (9 tests)

| Test | Purpose |
|------|---------|
| `test_builtin_conditions_exist` | All 15 builtin conditions present |
| `test_prot_token_matches` | __PROT__, __PROT_1__, __COLOR__, __FONT__ detection |
| `test_prot_token_no_match` | No match without valid placeholders |
| `test_dedup_token_matches` | __DEDUP__ pattern detection |
| `test_brackets_matches` | [], {}, <tag> bracket detection |
| `test_color_codes_matches` | \\c[N] and \\c[#RRGGBB] detection |
| `test_variables_matches` | \\v[N], \\n[N] variable detection |
| `test_ellipsis_matches` | ... and … detection |
| `test_builtin_all_have_required_fields` | All builtins have required fields |

#### TestConditionalPromptManager (12 tests)

| Test | Purpose |
|------|---------|
| `test_init_loads_builtins` | Manager loads all builtins on init |
| `test_evaluate_batch_empty` | Empty batch returns empty list |
| `test_evaluate_batch_with_prot` | Batch with PROT triggers condition |
| `test_evaluate_batch_multiple_conditions` | Multiple conditions in batch |
| `test_evaluate_batch_sorted_by_priority` | Results sorted by priority (high first) |
| `test_build_conditional_instructions_empty` | No conditions = empty string |
| `test_build_conditional_instructions_with_patterns` | Conditions build instruction block with dynamic examples |
| `test_set_condition_enabled` | Enable/disable conditions |
| `test_get_condition` | Retrieve condition by name |
| `test_add_custom_condition` | Add user-defined conditions |
| `test_remove_custom_condition` | Remove custom conditions |
| `test_cannot_remove_builtin` | Builtin conditions cannot be removed |
| `test_list_conditions` | List all conditions with status |

#### TestUserCustomization (4 tests)

| Test | Purpose |
|------|---------|
| `test_load_user_overrides` | User config overrides builtins |
| `test_load_custom_conditions` | User-defined conditions loaded |
| `test_save_user_conditions` | Save conditions to JSON file |
| `test_create_default_config` | Generate default config template |

#### TestConditionalPromptIntegration (3 tests)

| Test | Purpose |
|------|---------|
| `test_full_workflow` | Complete evaluation workflow |
| `test_disabled_conditions_not_included` | Disabled conditions skipped |
| `test_category_ordering` | Category-based priority ordering |

#### TestDynamicInstructions (9 tests) - NEW (TASK 5)

| Test | Purpose |
|------|---------|
| `test_prot_only_shows_matched_types` | __PROT__ shows only matched placeholder types |
| `test_brackets_only_shows_used_types` | Brackets shows only detected bracket types |
| `test_brackets_shows_multiple_types` | Multiple bracket types show all examples |
| `test_br_vs_newline_distinction` | <br> and \\n have separate conditions |
| `test_newline_escape_detection` | \\n newline escapes detected separately |
| `test_color_font_prot_differentiated` | __COLOR__, __FONT__, __PROT__ show correct examples |
| `test_indexed_placeholders_shown` | __PROT_1__, __PROT_2__ show indexed examples |
| `test_jp_brackets_conversion_examples` | Japanese brackets show conversion examples |

---

### dev/test_standard_mode.py (37 tests)

Standard mode tests for symbol conversion, ellipsis compression, PROT handling, and integration.

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
| `test_compress_single_prot` | Single PROT (non-adjacent) |
| `test_compress_adjacent_prots` | Adjacent PROTs cluster |
| `test_compress_multiple_clusters` | Multiple PROT clusters |
| `test_no_prot` | No PROT → no change |
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

### dev/test_cli_languages.py (32 tests)

CLI language selection and normalization tests.

#### TestSupportedLanguages (9 tests)

| Test | Purpose |
|------|---------|
| `test_japanese_defined` | Japanese (ja) in SUPPORTED_LANGUAGES |
| `test_english_defined` | English (en) in SUPPORTED_LANGUAGES |
| `test_chinese_simplified_defined` | Chinese Simplified (zh-CN) defined |
| `test_chinese_traditional_defined` | Chinese Traditional (zh-TW) defined |
| `test_korean_defined` | Korean (ko) in SUPPORTED_LANGUAGES |
| `test_german_defined` | German (de) in SUPPORTED_LANGUAGES |
| `test_french_defined` | French (fr) in SUPPORTED_LANGUAGES |
| `test_spanish_defined` | Spanish (es) in SUPPORTED_LANGUAGES |
| `test_all_languages_have_required_fields` | name, native, description present |

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

#### TestAPIProvidesConsolidation (4 tests) - Critical

| Test | Purpose |
|------|---------|
| `test_options_and_global_options_same_object` | Identity check (same object) |
| `test_cli_known_urls_matches_options` | CLI URLs from options.py |
| `test_cli_known_models_matches_options` | CLI models from options.py |
| `test_no_duplicate_definitions` | No duplicate definitions |

#### TestCLIBackwardCompatibility (4 tests)

| Test | Purpose |
|------|---------|
| `test_known_api_urls_exists` | KNOWN_API_URLS still exists |
| `test_known_models_exists` | KNOWN_MODELS still exists |
| `test_known_api_urls_has_expected_providers` | Has all 6 providers |
| `test_known_models_has_expected_providers` | Has all 6 providers |

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
| TestProtCompression | 4 | PROT compression via modi |
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

### File Format Handler Tests (Planned)

Future tests for formats/ module:

```python
# Planned test classes:
# TestTxtHandler - txt file read/write
# TestCsvHandler - csv with pair support
# TestTsvHandler - tsv with pair support
# TestJsonHandler - json structures (strings, pairs, objects)
# TestXlsxHandler - xlsx with openpyxl
# TestFormatRegistry - handler registration and lookup
# TestIOConfig - configuration serialization
```

---

### dev/test_br_protection.py (26 tests)

Tests for `<br>` tag protection and recovery in CherryAI.

**Test Classes:**

#### TestBrTagConditionalPrompt (8 tests)
Tests CONDITION_BR_TAGS pattern matching.

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

**Verification:**
- All 21 gender inference tests pass
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
        'result': {'romaji': 'Tarou', 'gender': 'Male', 'note': '...'}, ...})
```

**Verification Status:** ✅ PASSED (2025-11-29)
- API key loaded from CherryAI.ini [api] section
- Model: gemini-2.0-flash-lite
- Test speaker: 太郎 → correctly inferred as Male
- Romanization: Tarou (correct)

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
| TestPlaceholderValidation | `test_prot_count_match` | __PROT__ count verified |
| | `test_prot_count_mismatch` | Missing __PROT__ detected |
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
| | `test_condition_priority` | Priority = 82 |
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
| TestExtractPlaceholders | `test_single_prot` | Extract __PROT__ |
| | `test_prot_with_index` | Extract __PROT_1__ style |
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

| Category | Tests | Priority | Depends On |
|----------|-------|----------|------------|
| API Validator | 27 | HIGH | API Client |
| Prompt Builder | 9 | MEDIUM | None |
| API Client | 13 | HIGH | None |
| Extended Line Tags | 27 | HIGH | Manifest v2.0 |
| GUI Table View | 52 | MEDIUM | Line Tags, Manifest |
| Rate Limiter | 22 | HIGH | None |
| Chunk Optimizer | 15 | MEDIUM | Validation |
| Progress Tracker | 12 | LOW | None |
| Auto Recovery | 18 | HIGH | Validation |
| Line-by-Line Mode | 15 | LOW | None |
| Style Presets | 28 | LOW | None |
| Quote Stripper | 14 | LOW | Validation |
| Token Chunker | 16 | MEDIUM | None |
| **Total Planned** | **268** | | |

Combined with existing 1021 tests: **~1289 tests** after all features implemented.

### Planned Test Details


#### dev/test_rate_limiter.py (Planned - 22 tests)

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

#### dev/test_chunk_optimizer.py (Planned - 15 tests)

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

#### dev/test_line_by_line.py (Planned - 15 tests)

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
| `test_qa_step_data_persistence` | Step 6: QA data persists |
| `test_postprocessing_step_data_persistence` | Step 7: Postprocessing data persists |
| `test_wordwrap_step_data_persistence` | Step 8: Wordwrap data persists |
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
| `test_session_all_lines_persistence` | all_lines data persists through save/load |
| `test_session_files_with_lines_complete_roundtrip` | Complete file metadata and lines roundtrip |
| `test_empty_session_files_handled` | Empty files list handled gracefully |

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
| `test_input_step_stores_all_lines` | Input step stores all_lines in step data |
| `test_session_save_load_preserves_all_lines` | Session save/load preserves all_lines |

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
| `test_qa_step_id` | QAStep has correct step_id (6) |
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

### dev/test_gui_dialogs.py (14 tests) - TASK 18.7

Tests for GlobalOptionsDialog freeze fix and lifecycle management.

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
| `test_create_manifest_function_exists` | _create_manifest method exists |
| `test_manifest_filename_pattern` | Uses .manifest.json extension |
| `test_manifest_includes_source_path` | Source path is recorded |
| `test_manifest_includes_timestamp` | Creation timestamp is recorded |

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
| `test_character_info_has_required_fields` | Required fields present |
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

### dev/test_code_glossary_display.py (12 tests) - TASK 18.5

Tests for Code Glossary widget in Information tab.

#### TestCodePatternDataClass (4 tests)

| Test | Purpose |
|------|---------|
| `test_code_pattern_creation` | CodePattern defaults |
| `test_code_pattern_to_dict` | Serialization |
| `test_code_pattern_from_dict` | Deserialization |
| `test_code_pattern_default_action` | Default is 'preserve' |

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

---

### dev/test_session_loading.py (28 tests) - TASKS 18.1-18.8

Tests for session loading and state restoration fixes.

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
| `test_code_pattern_actions` | Valid actions list |

#### TestPreprocessingSessionLoading (4 tests) - TASK 18.4/18.8

| Test | Purpose |
|------|---------|
| `test_input_step_data_has_all_lines` | all_lines storage |
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
| `test_code_pattern_with_missing_fields` | CodePattern defaults |
| `test_character_with_missing_fields` | CharacterInfo defaults |
