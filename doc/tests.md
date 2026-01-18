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
**Count:** 4130 tests collected, 4130 passed, 26 skipped (integration tests)
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
| `test_ensure_all_fields_present` | _ensure_all_fields_present works |
| `test_ensure_nested_fields` | _ensure_nested_fields works |
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
| `test_contains_japanese_detection` | JapaneseCharacterDetection key |
| `test_contains_speaker_format` | SpeakerFormat key |
| `test_contains_quote_balance` | QuoteBalance key |
| `test_contains_empty_translation` | EmptyTranslation key |
| `test_returns_deep_copy` | Returns deep copy |

#### TestGetQAOptions (4 tests)

| Test | Purpose |
|------|---------|
| `test_returns_dict` | Returns dictionary type |
| `test_contains_rerun_policy` | RerunPolicy key present |
| `test_contains_max_japanese_chars` | MaxJapaneseChars (int) |
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
| `test_contains_prevent_orphans` | PreventOrphans (bool) |
| `test_contains_punctuation_breaks` | PreferPunctuationBreaks key |
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
| `test_default_is_true` | Default restore_on_launch is True when set in INI |
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

---

### dev/test_manifest_fields.py (181 tests)

Manifest field type helpers for Task 22.1 and 22.2. Reusable save/load operations for different field types and complex data structures.

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

#### TestCodeGlossaryRoundtrip (1 test)

| Test | Purpose |
|------|---------|
| `test_roundtrip_preserves_data` | Roundtrip preserves all data |

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
| `test_binding_count_after_task_232` | 10 bindings after Tasks 23.1+23.2 |

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

### dev/test_preprocess_manifest.py (49 tests)

Phase 24 tests for PreprocessingStep manifest integration. Tests all preprocessing options bound to manifest.

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
| `test_prot_binding_created` | PROT binding exists |
| `test_prot_saves_to_manifest` | PROT saves when changed |

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
| test_estimate_manifest.py | 33 | Estimation/Analysis manifest integration (TASK 25.1, 25.2) |
| test_qa_manifest.py | 17 | QA step manifest integration (TASK 26.1) |
| test_translate_manifest.py | 47 | Translation step manifest integration (TASK 26.2) |
| test_postprocess_manifest.py | 35 | Postprocessing step manifest integration (TASK 27.1) |
| test_wordwrap_manifest.py | 40 | Wordwrap step manifest integration (TASK 28.1) |
| test_output_manifest.py | 45 | Output step manifest integration (TASK 28.2) |
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
| **Total Script Tests** | **2900** | (+97 manifest integration from Phase 25-26) |
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

#### TestHelperMethods (7 tests)

| Test | Purpose |
|------|---------|
| `test_parse_list_default_empty_string` | Empty string becomes [] |
| `test_parse_list_default_single_item` | Single item becomes [item] |
| `test_parse_list_default_multiple_items` | Multiple items parsed |
| `test_parse_list_default_strips_whitespace` | Whitespace stripped |
| `test_ensure_nested_fields_creates_missing_parent` | Creates parent dict |
| `test_ensure_nested_fields_fills_missing_children` | Fills missing children |
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

### dev/test_qa_manifest.py (17 tests)

QA step manifest integration for Phase 26 Task 26.1.

#### TestQAOptionsRerunPolicy (5 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_save_rerun_policy_failed_only` | Saves FailedOnly policy |
| `test_save_rerun_policy_all` | Saves All policy |
| `test_save_rerun_policy_none` | Saves None policy |
| `test_load_rerun_policy` | Loads RerunPolicy |
| `test_rerun_policy_default_failed_only` | Default is FailedOnly |

#### TestQAOptionsMaxJapaneseChars (4 tests) - TASK 26.1

| Test | Purpose |
|------|---------|
| `test_save_max_japanese_chars` | Saves to manifest |
| `test_load_max_japanese_chars` | Loads from manifest |
| `test_max_japanese_chars_default_4` | Default is 4 |
| `test_max_japanese_chars_clamped` | Values clamped to min 0 |

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

### dev/test_wordwrap_manifest.py (40 tests)

Wordwrap step manifest integration tests. Verifies all 8 WordwrapSettings
fields are properly bound for session persistence.

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

#### TestWordwrapSettingsPreventOrphans (4 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_prevent_orphans_save_true` | Saves PreventOrphans=True |
| `test_prevent_orphans_save_false` | Saves PreventOrphans=False |
| `test_prevent_orphans_load_from_manifest` | Loads PreventOrphans |
| `test_prevent_orphans_default_true` | Default is True |

#### TestWordwrapSettingsPreferPunctuationBreaks (3 tests) - TASK 28.1

| Test | Purpose |
|------|---------|
| `test_punct_breaks_save_true` | Saves PreferPunctuationBreaks=True |
| `test_punct_breaks_save_false` | Saves PreferPunctuationBreaks=False |
| `test_punct_breaks_default_true` | Default is True |

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
| `test_all_fields_roundtrip` | All 8 fields save/load |
| `test_wordwrap_settings_field_count` | Verifies 8 fields stored |

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

### test_output_manifest.py (45 tests) - TASK 28.2

Output step manifest integration tests. Verifies that OutputInjectStep binds all output format settings to ManifestManager for unified state persistence.

**Bindings Tested:**
- OutputFormat.PreserveFolderStructure (checkbox, default true)
- OutputFormat.Format (combobox, default "txt")
- OutputFormat.PairMode (combobox, default "translated_only")
- OutputFormat.Encoding (combobox, default "utf-8")
- OutputFormat.FileNaming (radio buttons via trace)
- OutputFormat.TextOption (entry, default "_translated")
- OutputFormat.OverwriteExistingFiles (checkbox, default false)
- OutputFormat.Backup (combobox, default "timestamp")
- OutputFormat.BackupExtension (entry, default ".bak")
- OutputFormat.ExportManifestFile (checkbox, default false)
- OutputFormat.ExportProcessingLogs (checkbox, default false)
- OutputFormat.ExportGlossaryEntries (checkbox, default false)

#### TestOutputManifestBindings (27 tests) - TASK 28.2

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