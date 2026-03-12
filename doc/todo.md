CHERRYAI - OUTSTANDING WORK & ROADMAP

Features, Improvements, and Known Tasks

=============================================================================

AI AGENT INSTRUCTIONS
---------------------

CRITICAL ARCHITECTURE PRINCIPLE:
The GUI must NOT contain processing logic. All processing functions belong 
in shared modules (functions/, modi/, formats/) that both CLI and GUI use.

WHEN IMPLEMENTING NEW FEATURES:
- ALL text manipulation → functions/ modules
- ALL pre/post-processing → modi/ plugins  
- ALL file I/O → formats/ handlers
- GUI code → display and user interaction ONLY

DOCUMENTATION CROSS-REFERENCE:
- User features: doc/features.md
- Technical API: doc/technical.md
- Test coverage: doc/tests.md

=============================================================================

TESTING REFERENCE

For comprehensive test documentation, see `doc/tests.md`

**Current Status:** 6315 tests passing (verified Q2 2026 via pytest)

Two test types:
- **Script Test**: pytest unit tests (fast, no LLM)
- **API Test**: 7-stage One_Click_Test (full pipeline with LLM)

Run Script Tests: `python -m pytest CherryAI/dev/ -v --timeout=10`
Run API Test: `python CherryAI.py test`

**Note:** Always use `--timeout` to prevent infinite loops. See `doc/tests.md`.

=============================================================================

MODULE COUNTS (Verified January 2026)

- functions/: 39 modules (+ glossaries/ subfolder with 5 files, + romanization.py, + term_translation.py)
- modi/: 12 processing modes
- formats/: 5 format handlers
- gui/steps/: 10 workflow tabs
- gui/helpers/: 6 adapter modules (mode, analysis, glossary, chunker, prompt, manifest_binding)
- gui/dialogs/: 6 dialog modules (global_options, project_dialog, input_dialog, loading_progress, password_dialog, table_view)

=============================================================================

=============================================================================
[Archived: Sessions 43–24 + Phase 62 → see doc/archived.md]

### BUG FIX: Input Step Non-Destructive Addition, Import Dialog, OutputFormat Crash
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Fix Input button to non-destructively add files to existing manifests, add Import Translation selection dialog, fix OutputFormat ValueError crash, rename preview columns to Project/File with 1-based indexing.

**Changes:**
1. **OutputFormat ValueError** — Added `_safe_output_format()` in `output_inject.py` to prevent crash on empty/invalid format string (defaults to TXT).
2. **Non-Destructive File Addition** — `ManifestManager.add_files()` merges new files into sorted filedir, rewritting all idx values contiguously while preserving existing line data (tl, prepro, tags, etc.). `_load_selected_paths()` now detects add-to-existing mode, validates source root, skips already-loaded files, and calls `_add_files_to_existing_manifest()` for new files only.
3. **Preview Column Rename** — "Idx" → "Project" (1-based global idx), "#" → "File" (1-based per-file line number).
4. **Import Translation Dialog** — `_ImportTranslationDialog` Toplevel with Line Fields group (Preprocessed, Tags, Translated, Postprocessed, Wordwrap, QA, skip option) and Settings Sections group (Analysis, Information, Preprocessing, Costs, Translation, Postprocessing, Wordwrap, QA/Validation, File Settings). Per-section import logic via `_import_line_fields()` and `_import_settings_sections()`.

**Files Modified:**
- `gui/steps/output_inject.py` — `_safe_output_format()`, 7 call sites updated
- `gui/steps/input_extract.py` — `_ImportTranslationDialog` class, `_add_files_to_existing_manifest()`, `_import_line_fields()`, `_import_settings_sections()`, modified `_load_selected_paths()` and `_on_import_translations()`, preview headings
- `functions/manifest_manager.py` — `add_files()` method

**Tests:** `dev/test_input_import_fixes.py` — 23 tests (8 OutputFormat, 8 add_files, 3 import lines, 4 import sections)

---

### BUG FIX: si_preset Lost on Tab Change
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: si_preset value disappears from manifest when switching tabs because `ProjectMetadata.to_dict()` and `from_dict()` did not include `si_preset`.

**Solution:** Added `si_preset` field to `ProjectMetadata` dataclass, `to_dict()`, `from_dict()`, `_collect_metadata()`, and `_populate_form()` in `gui/steps/information.py`.

**Files Modified:** `gui/steps/information.py`
**Tests:** `dev/test_io_examples.py::TestProjectMetadataPersistence` — 7 tests

---

### BUG FIX: System Instructions Reset on Re-enter
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Default system instructions text overwrote user edits every time the Information tab was entered because `_ensure_default_texts()` ran unconditionally and empty manifests had no seeded defaults.

**Solution:** Two-pronged fix:
1. `manifest_manager.py::_create_empty_manifest()` now seeds `info_metadata` defaults (system_instructions, si_preset, io_examples, languages, toggles) via new `_get_info_defaults()` method
2. `_ensure_default_texts()` rewritten as fallback-only — only fills truly empty fields in manifests that somehow have no defaults

**Files Modified:** `functions/manifest_manager.py`, `gui/steps/information.py`
**Tests:** `dev/test_io_examples.py::TestManifestDefaultSeeding` — 4 tests

---

### FEATURE: I/O Examples Generation
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 6 hours

Goal: Generate I/O (input/output) example blocks in the system prompt to improve translation quality. Mode selectable per-project: disabled, fill (cache-aligned), 1500, or 2500 tokens.

**Implementation:**
- New module `functions/io_examples.py` — `_Example` dataclass with language-keyed fields (`jp`, `en`), `_resolve_example_keys()` for language resolution, example bank (~35 pairs), priority scoring, code pattern boosting, sequential LineN renumbering, tiktoken token counting with heuristic fallback
- UI dropdown in Information Step (System Instructions section) with 4 modes
- `build_full_system_prompt()` in `prompt_adapter.py` injects examples at slot 2b (between SI and Style)
- Never modifies System Instructions — examples are a separate prompt slot
- Language key resolution: maps lang names to `jp`/`en` keys; unknown languages fall back to `en` unless English is source or target (then `jp`)
- "fill" mode uses `calculate_fill_target()` + `get_optimal_cache_size()` to fill optimal cache boundary
- `api_config.py` extended with `optimal_cache_size` model setting key, `_CACHE_DEFAULTS`, `get_optimal_cache_size()`
- `api_client.py` extended with `io_examples` in `_STATIC_PROMPT_SECTIONS`
- Manifest seeding: `io_examples` default "disabled" seeded at manifest creation

**Files Modified:**
- `functions/io_examples.py` (NEW)
- `gui/steps/information.py` — ProjectMetadata, UI dropdown, _on_io_examples_changed()
- `gui/helpers/prompt_adapter.py` — slot 2b injection
- `functions/api_config.py` — optimal_cache_size key, get_optimal_cache_size()
- `functions/api_client.py` — _STATIC_PROMPT_SECTIONS
- `functions/manifest_manager.py` — _create_empty_manifest, _get_info_defaults

**Tests:** `dev/test_io_examples.py` — 63 tests across 10 classes (all passing)

---

### IMPROVEMENT: Fill Mode Cache Calculation & Preview Request IO Examples
**Priority:** HIGH | **Status:** ✅ COMPLETE

Goal: Ensure fill mode calculates correctly by subtracting ALL static prompt sections from optimal cache size (not just slots 1-2). Add IO Examples to Preview Requests. Verify static prompt consistency with tests.

**Implementation:**
1. **Fill mode fix** — `build_full_system_prompt()` at slot 2b now pre-computes tokens for ALL later static sections (style, tone, summary, genre, protagonist, POV, context-type prompt) using `estimate_tokens()` before calculating fill target. Replaces the old incomplete calculation that only had access to slots 1-2 in `breakdown`.
2. **Preview Request IO Examples** — Added `io_examples` to `FILTER_PARTS` (after system_instructions, before style), `SECTION_DESCRIPTIONS`, `PreviewRequest` dataclass, and `_build_preview_requests()` generation logic with fill mode support.
3. **Static prompt consistency tests** — `TestStaticPromptConsistency` (8 tests): verifies static prefix identical across chunks, all sections present, IO determinism, LineN key consistency, fill uses full static tokens, fill respects cache boundary, no dynamic content without chunks, breakdown matches _STATIC_PROMPT_SECTIONS. `TestFillModeCalculation` (4 tests): empty prompt fill, at-optimal returns 0, never negative, more static → less IO fill.

**Files Modified:**
- `gui/helpers/prompt_adapter.py` — pre-compute all static section tokens at slot 2b
- `gui/steps/translate.py` — FILTER_PARTS, SECTION_DESCRIPTIONS, PreviewRequest, _build_preview_requests
- `dev/test_io_examples.py` — 12 new tests (TestStaticPromptConsistency, TestFillModeCalculation)

**Tests:** `dev/test_io_examples.py` — 63 tests across 10 classes (all passing)

---


PENDING TASKS - Full Table View

### FEATURE: Full Table View Dialog
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Spreadsheet-like view of all manifest line entries accessible via menu bar.

**Implementation:**
- Added `gui/dialogs/table_view.py` — FullTableViewDialog (Toplevel)
- Menu bar restructured: File (dropdown), Full Table View (direct), Options (direct), Help (dropdown)
- Edit menu removed; Tools menu replaced by direct Options entry
- Toolbar removed from app.py (all access via menu bar)
- 11 columns with display names: Line # (idx), Tags (context_marker), Original (orig), Preprocessed (prepro), Translated (tl), Postprocessed (postpro), Wrapped (wordwr), Overwrite, Quality Assurance (qa_overwrite), Log, Tags (Internal) (tags)
- Removed deprecated columns: edited_prepro, edit1-3, tlc1-3
- Column filter: slim tk.Menu dropdown with Show All / Show Visible / Show Latest presets + individual toggles
- All columns hideable including Line #; Tags hidden by default (DEFAULT_HIDDEN)
- Column selection bar: "Select / Selected" labels per column for search/replace scoping
- Sort indicators: ▲/▼ in column headers; tracks sort column and direction
- Two-row toolbar layout: search row (top), replace row (bottom)
- Results Only mode (inverted Show Misses) with ◀ / ▶ navigation
- Non-editable: Line # and Original (orig allows read-only copy via double-click)
- Tags and Line # now searchable (removed from METADATA_FIELDS)
- Search/replace scoped to visible or selected columns
- File filter dropdown with larger font (size 11)
- Hierarchical file filter dropdown with folder navigation
- Cell editing (double-click), deletion (Del), multi-select, column clearing
- Pagination: Show All / Show X (default 100), configurable page size
- Save/Reset/Diff operations against manifest with change tracking
- Close prompt for unsaved changes

**Files Modified:**
- `gui/dialogs/table_view.py` — FullTableViewDialog, _FileFilterDropdown (removed _ColumnFilterDropdown)
- `gui/app.py` — Menu bar restructured (removed Edit, Tools, toolbar)

**Tests:** `dev/test_table_view.py` — 124 tests (all passing)

---

PENDING TASKS - Costs TAB

### BUG FIX: Section Toggle Persistence
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Section Enabled/Disabled toggle states must survive tab changes and be respected by Preview Request and Estimation.

**Root Cause:** `on_leave()` called `ProjectMetadata.to_dict()` which does NOT include
`*_enabled` flags, then replaced the entire metadata dict via `set_step_data()`. This
erased toggle states written by `_toggle_section_enabled()` via `set_info_metadata_field()`.

**Solution:** Modified `on_leave()` and `_save_metadata()` to read current BooleanVar values
for all seven toggle flags and merge them into the metadata dict after `to_dict()` but before
`set_step_data()`. This preserves flags across tab changes.

**Files Modified:**
- `gui/steps/information.py` - Fixed on_leave() and _save_metadata() to merge toggle states

**Tests:** `dev/test_section_toggles.py` — 35 tests (all passing)

---

### BUG FIX: Preview Request Ignores Section Toggles
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Preview Request must respect Enabled/Disabled toggles — disabled sections must not
appear in the request preview.

**Root Cause:** `_build_preview_requests()` in translate.py built labeled sections for all
fields regardless of `*_enabled` flags. `build_full_system_prompt()` already gated sections
correctly, but the preview builder did not.

**Solution:** Added enabled flag reads from metadata in `_build_preview_requests()`. Each
labeled section (sys_instructions, style, tone, summary, genre, glossary, characters) is
now gated by its corresponding `*_enabled` flag, matching `build_full_system_prompt()`.

**Files Modified:**
- `gui/steps/translate.py` - Gated preview sections by enabled flags in _build_preview_requests()

**Tests:** `dev/test_section_toggles.py::TestPreviewSectionGating` — 6 tests (all passing)

---

### BUG FIX: Redundant Save Button Removal
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 10 minutes

Goal: Remove redundant Save button from Information step header.

**Root Cause:** The Save button duplicated auto-save behavior (manifest saves on every tab
change via on_leave → set_step_data) and showed a misleading "Saved" messagebox.

**Solution:** Removed Save button from header UI. Retained `_save_metadata()` as internal
helper without messagebox for programmatic use.

**Files Modified:**
- `gui/steps/information.py` - Removed Save button, removed messagebox from _save_metadata()

**Tests:** `dev/test_section_toggles.py::TestSaveButtonRemoved` — 1 test (all passing)

---

### BUG FIX: New Project Manifest Flush
**Priority:** CRITICAL | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: File → New Project must fully flush all cached state from every step tab.

**Root Cause:** `_on_new_session()` reset ManifestManager and SessionState but did NOT
clear instance-level cached state in step tabs (e.g., `_loaded_files`, `_lines`,
`_analysis_results`). Old project data leaked into new sessions.

**Solution:** Added `on_new_project()` lifecycle method to `BaseStep` (invalidates cache)
with overrides in all 10 step tabs clearing their specific cached attributes. Called from
`_on_new_session()` in `gui/app.py` before `on_enter()`.

**Files Modified:**
- `gui/steps/base.py` - Added `on_new_project()` method
- `gui/steps/input_extract.py` through `gui/steps/output_inject.py` - Added overrides
- `gui/app.py` - Updated `_on_new_session()` to call `tab.on_new_project()`

**Tests:** `dev/test_new_project_flush.py` — 45 tests (all passing)

---

### BUG FIX: Up Button Emoji Spacing
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 10 minutes

Goal: Fix excessive spacing between arrow symbol and "Up" text in UnifiedInputDialog.

**Root Cause:** The Up button used emoji `⬆️` (U+2B06 + U+FE0F variation selector) which
renders wider than expected on Windows due to emoji presentation.

**Solution:** Replaced with plain Unicode arrow `↑` (U+2191) in `gui/dialogs/input_dialog.py`.

**Tests:** `dev/test_input_dialog_ui.py::TestUpButtonText` — 2 tests (all passing)

---

### BUG FIX: Hide Auto-Pipeline Option
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 10 minutes

Goal: Auto-Pipeline dropdown must be hidden (not removed) in UnifiedInputDialog pending rework.

**Solution:** In `gui/dialogs/input_dialog.py` `_build_options_panel()`, the pipeline Label
and Combobox are still created (for future rework) but their `.pack()` calls are commented out.
The `_pipeline_var` remains functional so existing code referencing it won't break.

**Tests:** `dev/test_input_dialog_ui.py::TestAutoPipelineHidden` — 3 tests (all passing)

---

### BUG FIX: Debug Print Statements in Global Options
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 15 minutes

Goal: Remove all DEBUG print statements from GlobalOptionsDialog and app.py that polluted
console output every time the Options dialog was opened.

**Root Cause:** 23 debug `print("DEBUG:...")` statements were left in `global_options.py`
and 5 in `app.py` from development/troubleshooting and were never removed.

**Solution:** Removed all `print("DEBUG:...")` statements. Retained existing `logger.debug()`
calls which respect the logging configuration.

**Files Modified:** `gui/dialogs/global_options.py`, `gui/app.py`

---

### BUG FIX: API Log View Crash on entry.status.value
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Fix AttributeError crash in API Log View that caused log entries to show only a
checkmark icon with no other content.

**Root Cause:** `_render_entry()` used `entry.status.value.upper()` but `LogEntry.status`
is typed as `str` (not `LogStatus` enum). The `.value` accessor only works on enum instances
but after deserialization status is a plain string. Same issue in `_entry_to_searchable()`.

**Solution:** Changed `entry.status.value.upper()` → `entry.status.upper()` in
`_render_entry()` and `entry.status.value` → `entry.status` in `_entry_to_searchable()`.
Dict lookups using `LogStatus` enum keys still work because `LogStatus(str, Enum)` compares
equal to its string value.

**Files Modified:** `gui/dialogs/api_log_view.py`
**Tests:** `dev/test_api_log.py::TestStatusStringCompatibility` — 5 tests (all passing)

---

### BUG FIX: GlobalOptions Mousewheel Error After Destroy
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Fix "invalid command name" TclError spam when scrolling after closing Global Options.

**Root Cause:** `_build_utility_section()` used `canvas.bind_all("<MouseWheel>", ...)` which
registers a global binding. When the dialog was destroyed, the binding persisted but the canvas
widget no longer existed, causing "invalid command name" errors on every mouse wheel event.

**Solution:** Two-part fix:
1. Changed `_build_utility_section()` to use `<Enter>`/`<Leave>` binding pattern (matching
   the existing `_build_security_section()` approach): binds mousewheel on canvas enter,
   unbinds on canvas leave.
2. Added `self.unbind_all("<MouseWheel>")` to `destroy()` as safety net to clean up any
   lingering global mousewheel bindings before widget destruction.

**Files Modified:** `gui/dialogs/global_options.py`

---

### BUG FIX: Manifest Save File Locking (WinError 32/5)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Fix concurrent manifest save crashes caused by autosave thread and main thread racing
on `os.replace()`.

**Root Cause:** `save()` did not acquire `_autosave_lock`, so the autosave background thread
and the main thread could both write to the `.tmp` file and call `os.replace()` simultaneously.
On Windows this caused WinError 32 ("file being used by another process") and WinError 5
("Access denied").

**Solution:** Wrapped `save()`'s critical section with `self._autosave_lock`. Added retry
logic (3 attempts with back-off) for `os.replace()` to handle transient Windows file locks
from antivirus scanning or other processes.

**Files Modified:** `functions/manifest_manager.py`
**Tests:** `dev/test_api_log.py::TestManifestSaveThreadSafety` — 2 tests (all passing)

---

### BUG FIX: Gender Inference Freezes Window
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Fix UI freeze during LLM-based gender inference which blocked the main thread for
the duration of all API calls.

**Root Cause:** `_infer_character_genders()` ran LLM API calls (`infer_gender_llm()`)
synchronously on the Tkinter main thread. Each API call (3-30 seconds) blocked the event
loop, making the window completely unresponsive. The progress dialog with
`update_idletasks()` only helped between calls, not during them.

**Solution:** Refactored the LLM pass to use a background thread with queue-based
communication:
1. Script pass (fast, CPU-bound) remains synchronous with `update_idletasks()`
2. LLM pass runs in a `threading.Thread` with a `queue.Queue` for messages
3. Main thread polls the queue via `after(100, _poll_llm)` to update progress
4. Added Cancel button to abort the LLM pass via `threading.Event`
5. Completion callback `_finish_inference()` handles dialog close, refresh, and
   notification on the main thread

**Files Modified:** `gui/steps/information.py`

---

### FEATURE: Prompt Caching (OpenAI)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement OpenAI prompt caching support for gpt-4o+ models to reduce input token
costs by up to 50% and latency by up to 80%.

**Description:** OpenAI automatically caches identical prompt prefixes (≥1024 tokens)
across API requests. The system prompt assembly order (§5.2) already places static
sections (slots 1-7) before dynamic sections (slots 8-10), which is optimal for
prefix-based caching. Implementation adds model detection, extended 24h retention
support for gpt-4.1/gpt-5 models, cached token tracking in logs/stats, and
configurable APIConfig fields.

**Solution:**
- Confirmed prompt ordering is already cache-optimal (static before dynamic)
- Added `prompt_cache_enabled`, `prompt_cache_retention`, and `prompt_cache_key` to APIConfig
- `supports_prompt_caching()` restricted to `provider == "openai"` (Gemini excluded)
- Added `supports_extended_cache_retention()`, `get_prompt_cache_params()` (returns key + retention)
- Injected cache parameters into `_translate_chunk()` API call
- Tracked cached tokens from `usage.prompt_tokens_details.cached_tokens`
- Tracked reasoning tokens from `usage.completion_tokens_details` (reasoning, accepted/rejected prediction)
- Added cache hit rate, savings, and cached token counts to all log outputs
- `generate_prompt_cache_key(project_name, created_at)` — format `"{alpha5}-{seconds}"`
- `check_static_prompt_cache_status(token_breakdown)` — ok/suggest/warn classification
- Update button now calls `refresh_models()` + `reload_model_pricing()` to save to API.ini
- Available Models: added Cached Input filter, inverted Thinking filter, Save button, Cached $/1M column
- Costs step: `estimate_cost()` supports `cached_tokens` param, Prompt/Cached Input Cost rows, Cached $/1M in comparison table

**Files Modified:**
- `functions/api_client.py` — APIConfig fields, model lists, helper methods, param injection, token tracking, log updates, generate_prompt_cache_key, check_static_prompt_cache_status
- `functions/config.py` — `estimate_cost()` cached_tokens support
- `gui/dialogs/global_options.py` — Filters, Save button, Update button fix, Cached $/1M column
- `gui/steps/costs.py` — EstimationResult extended, Cached $/1M column, Prompt/Cached Input Cost rows
- `dev/test_prompt_caching.py` — Comprehensive test file (103 tests)

**Tests:** `dev/test_prompt_caching.py` — 103 tests (all passing)

---

### TASK 25.1: Analysis Results Storage
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Store analysis results (line counts, token estimates) in manifest.

**Field Mappings:**
- Input Lines → `InputLines` (int)
- Input Tokens → `InputTokens` (int)
- Output Tokens → `OutputTokens` (int)

**Files to Modify:**
- `gui/steps/estimate.py` - Save analysis results to manifest
- `gui/steps/analysis.py` - Write results to manifest after analysis

**Tests to Add:**
- `dev/test_estimate_manifest.py`:
  - `test_analysis_results_saved`
  - `test_token_counts_loaded`

---

### TASK 40.8: Refresh Button Model Data Fetch
**Priority:** LOW | **Status:** ✅ SUPERSEDED | **Effort:** 3 hours

Superseded by model_registry.py implementation (functions/model_registry.py).
Model data is now fetched from provider APIs and persisted to API.ini.

---

### BUG FIX: Model Registry Save Criteria (structured_output filter)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Only save models with structured_output=True to the model registry INI.
Previously, all API-returned models were saved, including skeleton models that
default to structured_output=False, cluttering the registry with unusable entries.

**Root Cause:** fetch_openai_models(), fetch_google_models(), and fetch_mistral_models()
created skeleton ModelInfo for API models not in FALLBACK_MODELS with all defaults
(structured_output=False). These were saved alongside real models.

**Solution:** Added `result = [m for m in result if m.structured_output]` filter after
building the result list in all three fetch functions. Skeleton models without
structured output are now excluded. All FALLBACK_MODELS have structured_output=True
so they are preserved.

**Files Modified:**
- `functions/model_registry.py` — Added structured_output filter to fetch_openai_models(),
  fetch_google_models(), fetch_mistral_models()

**Tests:** `dev/test_model_registry.py::TestStructuredOutputFilter` — 10 tests (all passing)
  `dev/test_model_registry.py::TestFallbackData::test_all_fallback_models_have_structured_output`

---

### FEATURE: Rate Limit Probing via API Response Headers
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fetch actual RPM and TPM for each model from OpenAI's rate limit response
headers instead of relying on hardcoded values. Remove hardcoded max_concurrent=5.

**Root Cause:** max_concurrent defaulted to 5 for all models. OpenAI does not
impose a concurrent request limit — only RPM and TPM. The hardcoded 5 was
artificially limiting throughput.

**Solution:**
- Added `_http_post_json()` helper returning (body, headers)
- Added `probe_openai_rate_limits(api_key, model_id)` that makes a minimal
  chat completion request (1 token) and reads `x-ratelimit-limit-requests` (RPM)
  and `x-ratelimit-limit-tokens` (TPM) from response headers
- `fetch_openai_models()` accepts `probe_limits=True` to probe after filtering
- `refresh_models()` passes `probe_limits` through to fetch_openai_models
- `global_options.py` `_update_models()` now calls with `probe_limits=True`
- `max_concurrent` changed from `int = 5` to `Optional[int] = None`
- Added `_derived_concurrent()` method to calculate concurrent from RPM when unset
- `to_pricing_entry()["concurrent"]` uses explicit value or derived value

**Files Modified:**
- `functions/model_registry.py` — Added probing, changed max_concurrent type,
  added _derived_concurrent
- `gui/dialogs/global_options.py` — Pass probe_limits=True in _update_models

**Tests:** `dev/test_model_registry.py::TestRateLimitProbing` — 5 tests (all passing)
  `dev/test_model_registry.py::TestDerivedConcurrent` — 6 tests (all passing)

---

### FEATURE: Current Selection + Per-Model Settings in API.ini
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Track the active model selection across providers and store per-model
settings (temperature, timeout, chunk_size, etc.) in API.ini so that each
model retains its own configuration.

**Root Cause:** Previously, all model settings were global in CherryAI.ini.
Switching models lost per-model tuning. No cross-provider selection tracking.

**Solution:**
- `set_default_model()` now also writes `current_selection = {provider}.{model_id}`
  to API.ini via `set_api_setting()`
- Added `get_current_selection()` to read back `current_selection`
- Added `_MODEL_SETTING_KEYS` tuple (11 allowed keys: temperature, timeout,
  chunk_size, chunk_max_tokens, retries, rate_limit_requests, thinking_enabled,
  thinking_budget, logit_bias_enabled, max_concurrent, request_mode)
- Added `get_model_settings(model_id)` — reads `[model_settings]` section,
  returns dict of `{key: value}` for matching `{model_id}.{key}` entries
- Added `set_model_settings(model_id, settings)` — validates keys against
  `_MODEL_SETTING_KEYS`, writes to `[model_settings]` section
- Added `delete_model_settings(model_id)` — removes all keys for a model

**Files Modified:**
- `functions/api_config.py` — Added current_selection writing, get_current_selection,
  per-model settings CRUD functions

**Tests:** `dev/test_model_registry.py::TestCurrentSelection` — 4 tests (all passing)
  `dev/test_model_registry.py::TestPerModelSettings` — 7 tests (all passing)

---

### FEATURE: Save Settings + Translation Options in Costs Tab (Task 4)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Replace Refresh button with Save Settings, add workflow defaults
(Thinking, Translated Context checkboxes) and Rolling Context spinboxes
(Before, Between, After) to the Costs tab header.  Settings are saved
per-model to API.ini via `set_model_settings()` only when Save Settings
is pressed.  Model change loads saved settings without auto-saving.

**Solution:**
- Removed `↻ Refresh` button from Costs header
- Added `💾 Save Settings` button that persists UI settings per-model
- Added second header row with:
  - Thinking checkbox (`thinking_enabled`)
  - Translated Context checkbox (`use_translated_context`)
  - Rolling Context Before/Between/After spinboxes (0–20)
- `_save_settings()` collects all UI values and calls `set_model_settings()`
- `_load_model_settings()` reads per-model settings from API.ini, falling
  back to Global Options defaults
- `_on_model_changed()` calls `_load_model_settings()` before re-estimating
- `on_enter()` loads model settings on tab activation
- Rolling context values passed to `RequestFormationConfig` for accurate
  request formation during estimation
- Extended `_MODEL_SETTING_KEYS` with `rolling_context_before`,
  `rolling_context_between`, `rolling_context_after`, `use_translated_context`
- Fixed test fixture isolation: patched `_load.__globals__` in addition to
  module attribute to handle conftest module duplication

**Files Modified:**
- `gui/steps/costs.py` — New header layout, Save/Load settings, rolling context
- `functions/api_config.py` — Extended `_MODEL_SETTING_KEYS` (4 new keys)
- `dev/test_model_registry.py` — Fixed 3 fixtures, added TestCostsTabSaveSettings

**Tests:** `dev/test_model_registry.py::TestCostsTabSaveSettings` — 8 tests (all passing)
  All 119 + 4 skipped in test_model_registry.py
  All 56 in test_costs_step_phase40.py

---

### FEATURE: Request Mode Widget in Costs Tab (Task 5)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Add a 2×2 Request Mode grid (Normal / Batch / Flex / Priority) to
the Costs tab summary panel.  Mode selection drives pricing in the
comparison table and persists per-model via API.ini.

**Description:** OpenAI offers alternative processing tiers:
- **Normal** — standard synchronous, full price
- **Batch** — asynchronous (24 h turnaround), 50 % discount
- **Flex** — synchronous but slower, batch-rate pricing
- **Priority** — guaranteed processing, may cost more

Button states:
- **Selected** (#4a90d9 / white / sunken) — currently active mode
- **Available** (#c8e6c9 / green text / groove) — model has pricing data
- **Unavailable** (#ffcdd2 / gray text / flat) — no mode pricing in registry

**Solution:**
- Added `_REQUEST_MODES` class tuple mapping mode → (key, label, input_key,
  output_key) for all four tiers
- `_build_request_mode_grid()` creates 2×2 tk.Button grid in summary panel
- `_select_request_mode(mode)` validates availability, sets `_mode_var`,
  calls `_refresh_mode_buttons()` and re-estimates
- `_refresh_mode_buttons()` colors buttons per state; guards for
  uninitialized widgets
- `_get_mode_price_keys()` returns `(input_key, output_key)` for the
  active mode, defaulting to `("input", "output")`
- `_update_comparison_table()` now uses mode-specific pricing keys
- `_save_settings()` includes `request_mode` in per-model settings
- `_load_model_settings()` restores `request_mode` from API.ini
- Added "(No Model)" sentinel to Primary Model dropdown

**Files Modified:**
- `gui/steps/costs.py` — Request Mode grid, mode-aware pricing, save/load
- `dev/test_model_registry.py` — Added TestRequestModeSettings (6 tests)

**Tests:** `dev/test_model_registry.py::TestRequestModeSettings` — 6 tests (all passing)
  All 125 + 4 skipped in test_model_registry.py
  All 56 in test_costs_step_phase40.py

---

### FEATURE: Revised Token/Cost Breakdown in Costs Tab (Task 6)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Separate the Token Counts display into distinct rows for
content tokens (line text only), prompt tokens (overhead), cached
tokens (prompt portion from request 2+), and total input (billed).
Previously, Input Tokens showed the combined content+prompt total.

**Solution:**
- Added `content_tokens`, `prompt_tokens`, `cached_tokens` fields to
  `EstimationResult` dataclass (default 0 for backward compatibility)
- Token Counts UI grid now shows 6 rows:
  1. **Lines** — translatable line count
  2. **Input Tokens** — content tokens only (line JSON payloads)
  3. **Prompt Tokens** — total prompt overhead across all requests
  4. **Cached Tokens** — prompt tokens cached after first request
  5. **Total Input** (bold) — content + prompt (what gets billed)
  6. **Output Tokens (est)** — estimated output
- `_do_estimation()` populates new fields: `content_tokens` = line-only,
  `prompt_tokens` = per-request overhead sum, `cached_tokens` = prompt ×
  (num_requests − 1) when prompt ≥ 1024 tokens and model has cached_input pricing
- `_update_ui()` displays all breakdown rows with Original/Preprocessed/Saved
  columns for each
- Updated existing `TestPromptOverheadFormat` tests to verify new grid
  structure instead of old single-label format

**Files Modified:**
- `gui/steps/costs.py` — EstimationResult fields, UI grid layout, estimation logic
- `dev/test_costs_step_phase40.py` — Updated TestPromptOverheadFormat tests
- `dev/test_model_registry.py` — Added TestTokenBreakdown (6 tests)

**Tests:** `dev/test_model_registry.py::TestTokenBreakdown` — 6 tests (all passing)
  `dev/test_costs_step_phase40.py::TestPromptOverheadFormat` — 5 tests (all passing)
  All 131 + 4 skipped in test_model_registry.py
  All 57 in test_costs_step_phase40.py

---

### FEATURE: Manifest Estimation Persistence (Task 7)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 min

Goal: Persist full estimation results to the manifest so re-opening the
Costs tab restores previous values without re-estimating.  Previously
only InputLines, InputTokens, OutputTokens were saved (TASK 25.1).

**Solution:**
- Replaced `_save_analysis_results_to_manifest()` /
  `_load_analysis_results_from_manifest()` with expanded
  `_save_estimation_to_manifest()` / `_load_estimation_from_manifest()`
- Saved fields: InputLines, InputTokens, OutputTokens, ContentTokens,
  PromptTokens, CachedTokens, NumRequests, InputCost, OutputCost, TotalCost
- `on_enter()` restores all token breakdown rows (Input, Prompt,
  Cached, Total, Output), request count, and total cost from manifest
- `_load_estimation_from_manifest()` returns `None` when no saved data
- Added `save_float_field` / `load_float_field` imports for cost fields

**Files Modified:**
- `gui/steps/costs.py` — Expanded save/load, on_enter restoration
- `dev/test_model_registry.py` — Added TestManifestEstimationPersistence (6 tests)

**Tests:** `dev/test_model_registry.py::TestManifestEstimationPersistence` — 6 tests (all passing)
  All 137 + 4 skipped in test_model_registry.py
  All 57 in test_costs_step_phase40.py

---

### FEATURE: Estimate/Update Counts Button Rename (Task 8)
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 15 min

Goal: After the first estimation, rename the Estimate button to
"↻ Update Counts" so users know clicking again refreshes (not creates)
the estimation.  Also sets "↻ Update Counts" when restoring saved
estimation from manifest on tab enter.

**Solution:**
- `_estimation_complete()` now checks `self._estimation_result`:
  if present → "↻ Update Counts", else → "▶ Estimate"
- `on_enter()` sets "↻ Update Counts" when manifest data is restored
- Initial text remains "▶ Estimate" in `_build_header()`
- "Estimating..." shown during computation (unchanged)

**Files Modified:**
- `gui/steps/costs.py` — Button text logic in _estimation_complete, on_enter
- `dev/test_model_registry.py` — Added TestEstimateButtonRename (3 tests)

**Tests:** `dev/test_model_registry.py::TestEstimateButtonRename` — 3 tests (all passing)
  All 140 + 4 skipped in test_model_registry.py
  All 57 in test_costs_step_phase40.py

---

### DOCS: Costs Tab Overhaul Documentation (Task 9)
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 15 min

Goal: Update all documentation to reflect changes made in Tasks 1-8.

**Changes:**
- `doc/features.md` — Costs Tab section updated: dynamic registry, per-model
  settings, Translation Options row, Request Mode widget, revised token
  breakdown (6 rows), manifest persistence (10 fields), Estimate/Update
  button rename
- `doc/technical.md` — costs.py entry updated with all new features
- `doc/tests.md` — test_model_registry.py section updated from 83 to 140
  tests with 21 class entries; added to summary table; total updated
  from 3901 to 4041
- `doc/todo.md` — Tasks 1-9 all documented with COMPLETE status

=============================================================================

PENDING TASKS - UI

TASK: Progress Sidebar Rework

   Goal: Rework the Progress Sidebar for automatic completion detection, detailed tasks, and proper collapsing without being blank.
   Files: `gui/app.py`, `gui/tracker.py`
   Priority: HIGH
   Effort: 3-5 hours

   Details:
   - Ensure the Sidebar automatically updates and tracks step completion.
   - Show detailed tasks inside the steps.
   - Properly collapse/hide when not in use, without leaving a blank area.

---

TASK: Single/Double Click Editing for Model Comparison

   Goal: Enable click interactions for model selection and comparison in
   the Estimation step.
   Files: `gui/steps/estimate.py`
   Priority: MEDIUM
   Effort: 2-3 hours

   Details:
   - Single click: Select model for comparison.
   - Double click: Set primary model or select API key if multiple found.
   - Visual feedback for selected/active model.

=============================================================================

PENDING TASKS - ARCHITECTURE

TASK: Refactor Processing, IO, Models, Reporting

   Goal: Processing in each mode, shared reporting in modehelper
   Files: modi/*.py, mainhelper.py
   Priority: MEDIUM
   Effort: 4-8 hours

---

TASK: Establish Proper Pipeline

   Goal: Strict separation: CherryAI → mainhelper → modi
   Priority: MEDIUM
   Effort: 2-4 hours
   Depends On: Refactor Processing

=============================================================================

PENDING TASKS - MAJOR FEATURES

TASK: GUI Table View with Full Editing Capabilities

   Goal: Spreadsheet-like table view with search/replace, undo/redo
   Files: gui_table.py (NEW), gui_dialogs.py (NEW), gui_filters.py (NEW)
   Priority: HIGH
   Effort: 20-25 hours

---

TASK: Advanced API Request System

   Goal: Rolling context, multi-step workflows (TLC, Edit, Rewrite)
   Files: api_request.py (NEW), api_client.py (EXTEND)
   Priority: MEDIUM
   Effort: 26-32 hours

---

TASK: LLM Provider Modules

   Goal: Modular provider system with online capability/pricing updates
   Files: providers/ (NEW folder)
   Priority: MEDIUM
   Effort: 12-16 hours
   
   Requirements:
   - Abstract provider interface (OpenAI-compatible as baseline)
   - Provider-specific modules for: OpenAI, Anthropic, Google, Mistral, local
   - Online fetch of model capabilities (context window, features, etc.)
   - Periodic price updates from official pricing pages or APIs
   - Cache model info locally with TTL (e.g., refresh weekly)
   - Fallback to bundled defaults if fetch fails

---

TASK: Translation Progress Window (Live)

   Goal: Dedicated modal/window during Translation step
   Priority: MEDIUM
   Effort: 8-12 hours
   
   Display:
   - Overall progress % (lines translated / total)
   - Time remaining (ETA) based on moving average throughput
   - Token speed (input + output tokens/sec)
   - Lines translated, remaining, failed
   - Current model/provider and rate-limit status
   
   Controls:
   - Start/Resume, Pause, Cancel
   
   Logging:
   - Inline log pane with collapsible details
   - Export session log to logs/

=============================================================================

UPCOMING FEATURES

See the image translation workflow: [Image Translation Workflow](image_translation_workflow.md)

[Archived: Tasks 17.1–17.10 (Completed Features) → see doc/archived.md]

COMPLETED: API Log Window (2026)
   ✅ Core data module: functions/api_log.py (LogCategory, LogStatus, LogEntrySent, LogEntryReceived, LogEntry, APILogStore)
   ✅ Hook logging into all API call sites: api_client.py, term_translation.py, API2Glossary.py, api_config.py
   ✅ Per-project persistence: .api_log.jsonl alongside manifest, atomic saves, "log" manifest key
   ✅ GUI: gui/dialogs/api_log_view.py (non-blocking Toplevel, search, category filter, view mode, color-coded entries, live updates)
   ✅ Menu bar: "API Log" direct entry between Full Table View and Options
   ✅ Tests: dev/test_api_log.py (37 tests — serialization, CRUD, filtering, subscription, persistence, singleton, enums)

PENDING TASKS - QUALITY

TASK: Performance Optimization

   Goal: Support 1M+ line files efficiently
   Priority: LOW
   Effort: 6-8 hours

=============================================================================

KNOWN ISSUES / BUGS

ISSUE: SharedTable "Item N already exists" TclError ✅ FIXED
   Status: FIXED (Phase 17)
   Description: Batch insertion callbacks continued after _refresh_display() was called again,
                causing duplicate item IDs when loading large files and rapidly switching tabs.
   Solution: Added _batch_insert_version counter. Batch callbacks check if version matches
             current before inserting. If stale, batch is silently cancelled.
   Files: gui/components/table.py, dev/test_table_batch_insert.py (8 tests)

---

ISSUE: Placeholders resolved in wrong order (Pre/Post mismatch)
   Status: OPEN (HIGH PRIORITY)
   Impact: Can corrupt restored text with overlapping placeholders
   Workaround: Reduce overlapping patterns, run Dry Run to inspect

---

ISSUE: Anchors / Remove-Restore reinserts content twice on Post-TL
   Status: OPEN (HIGH PRIORITY)
   Impact: Duplicate insertions corrupt output
   Workaround: Inspect manifest mappings for duplicates before Post-TL

---

ISSUE: GUI v2 Autosave JSON Parse Error
   Status: OPEN
   Description: "Failed to load autosave: Expecting value: line 41 column 13"
   Impact: Session not restored on launch
   Workaround: Delete temp/gui_session_autosave.json

---

ISSUE: GUI v2 Manifest Not Created Automatically
   Status: OPEN
   Description: Loading files does not automatically create a manifest
   Impact: User must manually create manifest for workflow

---

ISSUE: Japanese Ellipsis Restoration (Edge Case)
   Status: LOW PRIORITY
   Description: Japanese ellipsis (……) vs Western (...) mismatch warnings
   Impact: Cosmetic only, translations complete successfully

=============================================================================

ORPHANED MODULES (Exist but Not Fully Integrated)

| Module | Reason | Recommendation |
|--------|--------|----------------|
| formats/document.py | Placeholder (PDF/EPUB) | Keep for future |
| formats/html.py | Under development | Keep for HTML support |
| formats/rpgmaker.py | Placeholder | Keep for RPG Maker support |
| functions/local_llm.py | ✅ Integrated with GUI | LM Studio/Ollama support in Translation Step, Global Options |
| functions/replication.py | CLI only | Consider GUI integration |

=============================================================================

POTENTIAL ENHANCEMENTS

Future considerations (not prioritized):
- Undo/redo history in UI
- Real-time glossary suggestions while typing
- Export statistics to Excel
- Comparison mode (side-by-side before/after)
- Diff view for translations
- Integration with version control (git)
- REST API for headless operation

=============================================================================

EFFORT ESTIMATES

Phase 17 (COMPLETED):
- ✅ Batch API Support: 8-12 hours
- ✅ Multi-Key Management & Auto-Rotation: 10-14 hours
- ✅ Named API Profiles: 4-6 hours
- ✅ Additional File Formats (.trans, .md, lenient JSON): 8-10 hours
- ✅ Advanced Usage Analytics & Rate Limiting: 12-16 hours
- ✅ Automatic API Key Provisioning (Invest.): 4-6 hours (NOT FEASIBLE)
- ✅ Session Persistence & Auto-Load: 4-6 hours
- ✅ Agent-Assisted Modes: 6-8 hours
- ✅ Estimation Step Upgrade: 6-10 hours
- ✅ Tooltips & Multi-Language UI: 6-12 hours

Major Projects (12+ hours):
- LLM Provider Modules: 12-16 hours
- Advanced API Request System: 26-32 hours
- GUI Table View: 20-25 hours
- Translation Progress Window: 8-12 hours

Medium Tasks (2-8 hours):
- Refactor Processing: 4-8 hours
- Establish Proper Pipeline: 2-4 hours
- Performance Optimization: 6-8 hours
- Model Data Fetch (Task 40.8): 3 hours
- Analysis Results Storage (Task 25.1): 2 hours
- Model Comparison Click Editing: 2-3 hours

Total Remaining Effort: ~155-215 hours

=============================================================================

FUTURE IDEAS (No Phase Commitment)
**Priority:** LOW | **Status:** 🔲 PARKED | **Effort:** N/A

### Costs Step Future Enhancements
- **Final Cost Recording**: Track actual tokens and cost after translation completes
- **Cost Comparison**: Display estimated vs actual difference post-translation
- **Additional Cost Types**: Track costs for Editing, TLC, Summary generation, Glossary inference, Tone/Style inference
- **Cost History**: Track and display costs across multiple translation sessions
- **Budget Warnings**: Alert when estimated cost exceeds configured budget threshold
- **Request Merging**: Combine small trailing chunks into previous request when no rolling context needed
- **Token Speed Tracking**: Calculate actual tokens/sec from previous translations for accurate time estimates
- **Batch Mode Pricing**: Show batch API pricing (with discount %) for supported models
- **Image Cost Estimation**: Include image processing costs when image files loaded
- **Expanded Deduplication (also part of Pre- and Post-Processing Steps)**: Current Deduplication may just take the original string before any processing. More aggressive Deduplication can apply its own rules after all preprocessing and before all postprocessing. It can use one {CODE} for all code and X for all numbers.

### Analysis Step Future Enhancements
- **Auto-populate Glossary**: Use detected speakers and code patterns to pre-fill glossary entries
- **Pattern Suggestions**: Recommend protection rules based on detected code patterns
- **Export Formats**: Support additional export formats (JSON, XLSX) for findings
- **Visual Charts**: Charts/graphs for language distribution and pattern frequency
- **Diff Analysis**: Compare against previous analysis when files change
- **Code Patterns Consolidation**: The findings table currently writes to a dedicated code patterns table. Rework so findings write directly to the Code Database and Glossary in the Information step, eliminating the intermediate table. This reduces duplication and keeps a single source of truth for all patterns.

### Information Step Future Enhancements
- **Summary Generation via API**: Button to auto-generate summary using LLM analysis of loaded content
- ~~**Save/Load System Instructions**: Buttons to save current System Instructions to file and load from templates~~ ✅ DONE (preset system with Default/Custom/user presets)
- **Expanded Genre List**: Add more genre options, potentially with subcategories
- **Glossary Inference via API**: Use LLM to suggest glossary entries based on content analysis
- **Style/Tone Inference**: Auto-detect appropriate style/tone from sample text
- **Character Database**: Extended character info with relationships, traits, speaking patterns
- **Glossary Categories**: Group glossary entries by category (names, places, terms, etc.)
- **Glossary Import from File**: Direct import from external glossary files (CSV, JSON, TMX)
- **Code Pattern Templates**: Pre-built code pattern sets for common game engines (RPG Maker, Unity, etc.)
- **Project Templates**: Save/load entire Information step configurations as reusable templates
- ~~**Redesign Glossary Settings Widget**: Fold "Glossary Settings" into the "Global Glossary and Database" widget. Requiring a rework to remove, move and streamline to only ever export from the manifest to the global files.~~ ✅ DONE (TASK 76 — replaced both widgets with unified "Knowledge Base" widget)

### Preprocessing/Postprocessing Future Enhancements
- [x] **Line Field Persistence (Task 3)**: Fixed critical bug where preprocessing, postprocessing, and wordwrap steps stored per-line results only in step_state but never wrote to manifest `lines[].prepro` / `lines[].postpro` / `lines[].wordwr` via `set_line_field()`. Also fixed `_mark_line_as_fixed()` calling nonexistent `update_line_field()` → `set_line_field()`. 39 tests in `dev/test_line_saving.py`.
- **Speaker Name Replacement Rework**: Handle edge cases (speakers with colons in name, multiple dialogue formats, speaker extraction from non-standard patterns)
- **Code Spacing Rules Expansion**: Deeper integration with Code Database, expanded rule definitions, per-pattern spacing tags (visible/invisible, variable handling)
- **Advanced Deduplication Rules**: Pattern-based deduplication using Increase/Decrease equivalence, RPG stat names (Strength/Willpower/Dexterity) as equivalent, database of auto-translations for common patterns
- **Pattern Replacement Mode**: Replace patterns permanently before translation (not restored after)
- **Pattern Removal Mode**: Remove patterns permanently before translation (not restored after)
- **Variable Replacement via Preprocessing**: Replace variable codes (\\v[N], \\n[N]) during preprocessing and restore with postprocessing. Needs improved parser to handle replacements and restore positions correctly. Currently handled only via conditional prompt instruction.
- **Functions Not Visible in GUI**: Restore additional processing functions that exist in code but lack GUI exposure
- **Context-Aware Deduplication**: Use semantic similarity rather than exact match for deduplication
- **Deduplication Variants Database**: Create database of pattern variants that should be treated as duplicates
- **Deduplication Tag-Based Rework**: Replace the current dedup_map file with inline tags (e.g. ``dedup,D3516``) embedded in each line. This removes the need for a separate mapping file, simplifies the restore step, and makes dedup state visible during translation and QA. Requires changes to the dedup pipeline, restore logic, and manifest line schema.
- **Queue for Retry (Postprocessing)**: When a postprocessing recovery fails, queue the line for re-translation with stricter one-line instructions. Requires retry pipeline integration with Translation Step (Step 5) and a prompt template designed for recovery-focused re-translation. Currently hidden from Failure Handling widget.

### Translation Step Future Enhancements
- **Edit Before Translation**: Button opens a dialog where the LLM is prompted to fix specific mistakes in the original text (not translate). Requires separate prompt design and dedicated LLM pass. Currently hidden from UI.
- **Line-by-Line Translation Mode**: Translate each line individually with configurable rolling context window. Slower but more precise for difficult content. Currently hidden from UI.
- **NMT Mock Translation**: Replace nonsense Mock Translation output with Neural Machine Translation (NMT) engine for basic but meaningful offline translation. Potential engines: MarianMT, CTranslate2, or local model integration.
- **Isolated Retry Strategy**: Retry each failed line individually with strict one-line instructions. Needs further refinement before UI exposure.
- **Skip Retry Strategy**: Mark failed lines as Skipped immediately without retrying. Needs UX design for manual review flow.
- **Advanced Cache Modes**: Implement strict (exact prompt match), model_only (same model), and any (any translation) cache modes beyond the default Line cache.
- **Daily Limit Check**: Alert before exceeding configured daily API budget/token limits.
- **Batch API Pricing**: Show batch API pricing with discount percentages for supported models.
- **Translation / Edit / TLC Mode Toggle**: A three-way toggle switching the Translation step between Translation (default), Edit, and TLC modes. Edit mode prompts the LLM to fix grammar, naturalness, and formatting in existing translations. TLC mode sends original + translation for accuracy verification. Key design challenge: line-matching strategy (line numbers, full lines, or empty lines) since not every line will be edited/TLC'd and unnecessary output tokens are the most expensive component. Each mode writes to its own manifest fields (`lines[].edit{N}`, `lines[].tlc{N}`). Requires dedicated prompt design, matching script development, and cost-optimization testing before UI exposure.

### Wordwrap Step Future Enhancements
- ~~**Per-Tag Wordwrap Settings**: Tag-based wordwrap configuration with per-tag Width/BreakChar/MaxLines. TagWrapConfig dataclass, tag resolution (line tag → filedir type → "dialogue" fallback), parser-managed tag detection, manifest persistence via TagConfigs.~~ ✅ IMPLEMENTED
- **Parser-Driven Wrap Options**: Parsers auto-populate wordwrap settings (width, break char, max lines) based on the game engine format. Requires each format parser to expose a `get_wrap_config()` method returning engine-appropriate defaults.
- **RPG Maker as Own Parser**: Move RPG Maker-specific wordwrap logic (pixel-accurate width, `analyze_rpgmaker_project()`, `measure_font_avg_char_px()`) into a dedicated RPG Maker format parser. RPG Maker is no longer a wordwrap mode — it becomes a parser that drives the wordwrap settings automatically.
- **New Textboxes Structure**: When wrapping overflow exceeds Max Lines, split into a new text box entry instead of flagging. Requires parser support for text box boundaries and understanding of how the engine structures multi-box dialogue sequences.
- **Font Commands**: Parser-level support for font size commands (`size_up`, `size_down`, `size_increments`, `set_size`, `get_size`) that affect rendered width mid-line. Width calculation must account for font size changes within a single line of text.
- **Invisible Code and Variable Code**: Distinguish between code that is invisible (zero rendered width, e.g., color codes) and code that represents a variable (rendered width depends on the variable's runtime value). Variable code should use a max-length estimate for width calculation.
- **Line Break Auto-Detection from Parser**: Parsers identify the engine's native line break character and auto-populate the Break Character field. Currently break char is user-configured with common presets.
- **Pixel-Accurate Width Calculation**: Full pixel-based width using font metrics from `measure_font_avg_char_px()`. Requires Pillow for font measurement and project analysis via `analyze_rpgmaker_project()`. Show pixel ruler in preview.
- **Break Character Removal Before Translation**: Remove line breaks before sending to LLM to save tokens (fewer continuation lines = lower cost). Display warning that post-editing may be needed since LLM won't see original line structure. Re-wrapping after translation restores breaks.

### QA Step Future Enhancements
- **Full QA Implementation**: Activate the complete QA interface with validation rules panel, issue details, batch accept/reject, auto-fix, and export report. Currently behind a placeholder toggle.
- **Edit/TLC Filtering**: Once Edit and TLC modes exist in the Translation step, add "Edited" and "TLC'd" filter options to QA. These allow inspecting how much each inference pass changed and measuring the value of additional passes.
- **Re-run Policy**: Implement configurable re-run policies (FailedOnly, All, None) for selective re-validation after manual fixes.
- **Issue Severity Customization**: Allow users to override default severity levels per rule (e.g., downgrade Japanese Remaining from WARNING to INFO for mixed-language projects).
- **QA Report Templates**: Multiple export formats (JSON, XLSX, HTML) with configurable detail levels.
- **QA History**: Track QA results across translation rounds to show improvement/regression trends.

### Other Future Ideas
- Benchmark Mode (requires synthesized text with multiple passes and comparison)
- ToS/EULA for legal protection
- Agent AI
- Context Menu
- System Tray
- Image to Text Translation through OCR-capable model screenshot capture

---

### Application Rename
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Easily rename application when a name is finally found.

**Implementation:**
- Keep all internal references to CherryAI
- Update window title, about dialog, documentation once decided on
- Keep file naming

**Files to Modify:**
- All files with CherryAI references
- Documentation files

---

### Tooltips and Translation Support
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Add tooltips with translation support for all GUI fields.

**Implementation:**
- Create tooltip system with concise explanations
- Add toggle to disable tooltips in Options
- Translation files in `user/lang/` for i18n

**Files to Create:**
- `gui/helpers/tooltip.py` - Tooltip system
- `user/lang/en.json` - English tooltip strings

=============================================================================

CRITICAL ARCHITECTURE NOTE: UNIFIED MANIFEST SYSTEM

CherryAI uses ONE manifest file per project that contains ALL data:

**SINGLE MANIFEST FILE (.CherryAI.json) contains:**
1. **Processing Data** (v2.1 fields) - `lines`, `operations`, `mappings`, `summary`, `metadata`
2. **Project Settings** (v3.0 additions) - all GUI field defaults and user choices
3. **Step State** - workflow progress and per-step configuration

**TWO CLASSES access the SAME data:**

**1. `ManifestManager` - FILE AUTHORITY**
   - Location: `functions/manifest_manager.py`
   - Purpose: Single authority for manifest file I/O
   - Manages: `_manifest_data` dict containing ALL fields
   - Used by: GUI App, all gui/steps/, project dialogs
   - Role: Creates, loads, saves, validates manifest files
   - Tests: `test_manifest_state.py` - MUST NOT BREAK

**2. `mainhelper.Manifest` - RUNTIME PROCESSING VIEW**
   - Location: `functions/mainhelper.py`
   - Purpose: Dataclass optimized for Processor operations
   - Contains: `LineEntry` objects, `Operation` list, `mappings` dict
   - Used by: `Processor` class, all modi/ modules, CLI operations
   - Role: Runtime view of processing data (not file I/O)
   - Tests: `test_manifest_v2.py` - MUST NOT BREAK

**DATA FLOW:**
```
Manifest File (.CherryAI.json)
       |
       v
ManifestManager._manifest_data  <-- Single source of truth
       |
       |---> GUI reads/writes project settings directly
       |
       +---> export_to_mainhelper_manifest() --> Processor
                                                    |
       import_from_mainhelper_manifest() <----------+
       (syncs processing results back)
```

**MANIFEST 3.0 IS AN EXTENSION, NOT A REPLACEMENT:**
- v2.1 fields (`lines`, `operations`, `mappings`) remain unchanged
- v3.0 ADDS project settings fields alongside existing ones
- All fields coexist in ONE JSON file
- Processor still works with same LineEntry/Operation structures
- GUI simply has more fields to read/write

**Initialization Order:**
1. ManifestManager creates manifest with ALL defaults from .ini
2. GUI loads and can modify any field
3. Before processing: `export_to_mainhelper_manifest()` creates runtime view
4. Processor runs using mainhelper.Manifest dataclass
5. After processing: `import_from_mainhelper_manifest()` syncs results back
6. ManifestManager saves everything to ONE file

**Core Principles:**
1. ONE manifest file per project containing ALL data
2. ManifestManager is the ONLY class that reads/writes files
3. mainhelper.Manifest is a runtime convenience, not a separate system
4. v3.0 extends v2.1 format - all existing tests continue to pass
5. All defaults initialized BEFORE GUI can access fields
6. Most project settings get passed to functions/API requests

**KEY FILES AND THEIR ROLES:**
```
functions/mainhelper.py       - LineEntry, Manifest dataclass, Processor
                                (runtime processing - DO NOT change format)
functions/manifest_manager.py - ManifestManager (file I/O, v3.0 fields)
functions/ini_manager.py      - INI defaults loading
functions/manifest_fields.py  - Field type helpers for GUI binding + shared priority resolution (PIPELINE_FIELDS, resolve_line_field, get_all_lines_resolved)
functions/options.py          - API providers (global settings, not per-project)
functions/project_config.py   - Project overrides (will merge into ManifestManager)
gui/app.py                    - Uses ManifestManager for all state
gui/steps/*.py                - Read/write via ManifestManager
```

=============================================================================

CRITICAL TEST VERIFICATION REQUIREMENTS

Before ANY phase is marked complete, the following tests MUST pass:

**Existing Tests (MUST NOT BREAK):**
- `dev/test_manifest_v2.py` - 50+ tests for mainhelper.Manifest and LineEntry
- `dev/test_manifest_state.py` - 40+ tests for ManifestManager
- `dev/test_manifest_automation.py` - Automated manifest creation tests
- All other existing tests

**Test Commands:**
```bash
# Run all manifest tests
pytest dev/test_manifest_v2.py dev/test_manifest_state.py -v

# Run full test suite (should be done before each merge)
pytest dev/ -v --tb=short
```

**Regression Prevention:**
1. mainhelper.Manifest.to_dict() output format MUST NOT CHANGE
2. mainhelper.Manifest.from_dict() MUST accept existing v2.1 format
3. LineEntry field names and behavior MUST NOT CHANGE
4. ManifestManager bridge methods MUST preserve all line/operation data
5. Processing pipeline (Processor, modes) MUST continue working unchanged

=============================================================================

MANIFEST 3.0 COMPLETE FIELD REFERENCE

All fields stored in the UNIFIED manifest file (ManifestManager._manifest_data).
v2.1 processing fields (`lines`, `operations`, `mappings`) coexist with v3.0 settings.

**Field Categories:**
- **v2.1 Processing** - Unchanged, used by Processor via export_to_mainhelper_manifest()
- **v3.0 Settings** - Passed to functions during processing

### v2.1 Processing Fields (existing - DO NOT CHANGE FORMAT)

| Manifest Key | Type | Description | Managed By |
|--------------|------|-------------|------------|
| `lines` | array | LineEntry.to_dict() results | Processor → import_from_mainhelper_manifest() |
| `operations` | array | Operation.__dict__ results | Processor → import_from_mainhelper_manifest() |
| `mappings` | object | Mode state mappings | Processor → import_from_mainhelper_manifest() |
| `summary` | text | Processing summary | Processor |
| `metadata` | object | Processing metadata | Processor |

These fields are populated by the processing pipeline. GUI should NOT directly modify them.
Instead, use the bridge methods to sync processing results into ManifestManager.

### v3.0 Settings Fields

| GUI Field | Manifest Key | Type | Default | Passed To |
|-----------|--------------|------|---------|-----------|
| Project Name | `step_state.Information.data.metadata.project_name` | text | "Project1" | - |
| Title | `step_state.Information.data.metadata.game_title` | text | "Title1" | prompt |
| Genre | `step_state.Information.data.metadata.genre` | text | "fictional, nonfictional" | prompt |
| Source Language | `step_state.Information.data.metadata.source_language` | text | "Japanese" | api_client |
| Target Language | `step_state.Information.data.metadata.target_language` | text | "English" | api_client |
| Summary | `step_state.Information.data.metadata.summary` | text | "[DEFAULT_SUMMARY_TEXT]" | prompt |
| Style Preset | `step_state.Information.data.metadata.style_preset` | text | "Natural" | prompt |
| Tone Preset | `step_state.Information.data.metadata.tone_preset` | text | "Neutral" | prompt |
| Glossary (Characters) | `CharacterNotes` | special | [] | prompt |
| Code Database | `CodeGlossary` | special | [] | prompt |
| Prompt | `step_state.Information.data.metadata.custom_notes` | text | "[DEFAULT_SYSTEM_INSTRUCTIONS]" | prompt |
| SI Preset | `step_state.Information.data.metadata.si_preset` | text | "Default" | - |
| Genre Enabled | `step_state.Information.data.metadata.genre_enabled` | boolean | false | prompt toggle |
| Summary Enabled | `step_state.Information.data.metadata.summary_enabled` | boolean | false | prompt toggle |
| Style Enabled | `step_state.Information.data.metadata.style_enabled` | boolean | false | prompt toggle |
| Tone Enabled | `step_state.Information.data.metadata.tone_enabled` | boolean | false | prompt toggle |
| SI Enabled | `step_state.Information.data.metadata.system_instructions_enabled` | boolean | true | prompt toggle |
| Glossary Enabled | `step_state.Information.data.metadata.glossary_enabled` | boolean | true | prompt toggle |
| Code DB Enabled | `step_state.Information.data.metadata.code_database_enabled` | boolean | true | prompt toggle |
| Deduplication | `Deduplication` | boolean | true | dedup mode |
| Dedup Threshold | `DeduplicationThreshold` | int | 1 | dedup mode |
| Ellipsis Compression | `EllipsisCompression` | boolean | true | ellipsis mode |
| Symbol Conversion | `SymbolConversion` | boolean | true | symbol mode |
| Speaker Name Replacement | `SpeakerNameReplacement` | boolean | false | speaker mode |
| Code Spacing Rules | `CodeSpacingRules` | boolean | true | code mode |
| Protect Code Patterns | `ProtectCodePatterns` | special | [] | protect_code mode |
| Custom Placeholders | `CustomPlaceholders` | special | [] | placeholder mode |
| Anchor Removal | `AnchorRemoval` | special | [] | anchor mode |
| Input Lines | `InputLines` | int | 0 | estimation |
| Input Tokens | `InputTokens` | int | 0 | estimation |
| Output Tokens | `OutputTokens` | int | 0 | estimation |
| Placeholder Preservation | `ValidationRules.PlaceholderPreservation` | boolean | true | validation |
| Anchor Preservation | `ValidationRules.AnchorPreservation` | boolean | true | validation |
| Japanese Char Detection | `ValidationRules.JapaneseCharacterDetection` | boolean | true | validation |
| Speaker Format | `ValidationRules.SpeakerFormat` | boolean | true | validation |
| Quote Balance | `ValidationRules.QuoteBalance` | boolean | true | validation |
| Empty Translation | `ValidationRules.EmptyTranslation` | boolean | true | validation |
| Re-run Policy | `QAOptions.RerunPolicy` | enum | "FailedOnly" | qa |
| Max Japanese Chars | `QAOptions.MaxJapaneseChars` | int | 4 | qa |
| Max Line Length | `QAOptions.MaxLineLength` | int | 0 | qa |
| Model | `RequestOptions.Model` | text | "" | api_client |
| Temperature | `RequestOptions.Temperature` | float | 0.2 | api_client |
| Lines per Chunk | `RequestOptions.LinesPerChunk` | int | 30 | chunker |
| Retry Strategy | `RequestOptions.RetryStrategy` | enum | "Batch" | api_client |
| Max Retries | `RequestOptions.MaxRetries` | int | 3 | api_client |
| Enable Caching | `RequestOptions.EnableRequestCaching` | boolean | true | api_client |
| Line by Line | `RequestOptions.LineByLineMode` | boolean | false | chunker |
| Thinking | `RequestOptions.Thinking` | boolean | false | api_client |
| Thinking Budget | `RequestOptions.ThinkingBudget` | int | 1000 | api_client |
| Placeholder Recovery | `PostProcessing.PlaceholderRecovery` | boolean | true | postprocess |
| Bracket Balance | `PostProcessing.BracketBalanceRecovery` | boolean | true | postprocess |
| Quote Balance | `PostProcessing.QuoteBalanceRecovery` | boolean | true | postprocess |
| Whitespace Norm | `PostProcessing.WhitespaceNormalization` | boolean | true | postprocess |
| Restore Code Chars | `PostProcessing.RestoreCodeCharacters` | boolean | true | postprocess |
| Restore Linebreaks | `PostProcessing.RestoreLinebreaks` | boolean | true | postprocess |
| Symbol Conversion | `PostProcessing.EnableSymbolConversion` | boolean | true | postprocess |
| Fullwidth→Halfwidth | `PostProcessing.FullwidthToHalfwidth` | boolean | true | postprocess |
| Failure Handling | `PostProcessing.FailureHandling` | enum | "FlagForReview" | postprocess |
| Wordwrap Mode | `WordwrapSettings.Mode` | enum | "Manual" | wordwrap |
| Width | `WordwrapSettings.Width` | int | 48 | wordwrap |
| Break Char | `WordwrapSettings.BreakChar` | text | "" | wordwrap |
| Max Lines | `WordwrapSettings.MaxLines` | int | 4 | wordwrap |
| Prevent Orphans | `WordwrapSettings.PreventOrphans` | boolean | true | wordwrap |
| Prefer Punctuation | `WordwrapSettings.PreferPunctuationBreaks` | boolean | true | wordwrap |
| Speaker Handling | `WordwrapSettings.SpeakerHandling` | enum | "Sameline" | wordwrap |
| Ignore Patterns | `WordwrapSettings.IgnorePatterns` | list | ["Angle","Square","Curly","En"] | wordwrap |
| Typography | `WordwrapSettings.Typography` | text | "Western" | wordwrap |
| Tag Configs | `WordwrapSettings.TagConfigs` | list | [] | wordwrap (per-tag) |
| Preserve Folders | `OutputFormat.PreserveFolderStructure` | boolean | true | output |
| Format | `OutputFormat.Format` | text | "" | output |
| Pair Mode | `OutputFormat.PairMode` | text | "translated_only" | output |
| Encoding | `OutputFormat.Encoding` | text | "" | output |
| File Naming | `OutputFormat.FileNaming` | enum | "PutInSubfolder" | output |
| Text Option | `OutputFormat.TextOption` | text | "translated" | output |
| Overwrite Files | `OutputFormat.OverwriteExistingFiles` | boolean | false | output |
| Backup | `OutputFormat.Backup` | text | "Timestamp" | output |
| Backup Extension | `OutputFormat.BackupExtension` | text | ".bk" | output |
| Export Manifest | `OutputFormat.ExportManifestFile` | boolean | false | output |
| Export Logs | `OutputFormat.ExportProcessingLogs` | boolean | false | output |
| Export Glossary | `OutputFormat.ExportGlossaryEntries` | boolean | false | output |

=============================================================================

PHASE 58: INPUT AUTOMATION (Step 0 Enhancement)
-----------------------------------------------

**Status:** 🔲 PLANNED | **Effort:** 16-24 hours | **Priority:** HIGH

Goal: Implement automatic pipeline execution when files are loaded, providing
users with a "load and see results" workflow. When files are loaded into a 
new project, the pipeline automatically runs up to a configurable endpoint.

**Reference:** See `doc/specs.md` Section 2.2 → Step 0: Input for full spec.

### TASK 58.1: Input Button Unified Window
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Replace separate Load Files/Load Folder buttons with a unified Input
button that opens a combined file/folder selection window.

**Requirements:**
- Single button opens a modal window with dual-pane interface
- Left pane: Folder tree browser for directory selection
- Right pane: File list for individual file selection
- Both support multi-select (Ctrl+Click, Shift+Click)
- "Add Selection" button queues items without closing
- "Load" button finalizes and begins pipeline

**Files to Modify:**
- `gui/steps/input.py` - Replace buttons with unified Input button
- `gui/dialogs/` - Create new `input_dialog.py` for combined selection

**Tests to Add:**
- `dev/test_input_dialog.py`:
  - `test_file_selection`
  - `test_folder_selection`
  - `test_mixed_selection`
  - `test_add_selection_queue`

---

### TASK 58.2: Auto-Pipeline Dropdown
**Priority:** HIGH | **Status:** ✅ COMPLETE (hidden pending rework) | **Effort:** 2 hours

Goal: Add dropdown to Options Panel for selecting automation level (0-4).

**Levels:**
- 0: Manual (load only)
- 1: Analyze
- 2: Estimate Original
- 3: Preprocess (Default)
- 4: Mock Translate

**Files to Modify:**
- `gui/steps/input.py` - Add Auto-Pipeline Dropdown to Options Panel
- `config/defaults.ini` - Add `auto_pipeline_level = 3`

**Tests to Add:**
- `dev/test_auto_pipeline.py`:
  - `test_pipeline_level_0_load_only`
  - `test_pipeline_level_3_default`
  - `test_pipeline_level_persistence`

[Archived: Phase 58: Input Automation → see doc/archived.md]


---

### TASK 59.2: Aggressive Deduplication Projection
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Show projected line count after aggressive deduplication in Statistics.

**Display:**
Format: "Aggressive Dedup: X lines → Y unique (Z% reduction)"

**Files to Modify:**
- `functions/analysis.py` - Calculate aggressive dedup projection
- `gui/steps/analysis.py` - Display projection in Statistics Panel

**Tests to Add:**
- `dev/test_analysis.py`:
  - `test_aggressive_dedup_projection`

---

### TASK 59.3: Category-Aware Findings Table Context Menu
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

---

=============================================================================

## PHASE: Parser Handshake — Unified I/O Parser Interface 

**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 12-16 hours

### Goal

Define a formal "handshake" contract that every file-format parser must satisfy.
The contract has **mandatory** components (must be present and return valid data or
raise an error) and **optional** components (provide additional capabilities when
the format supports them). The handshake standardises how parsers communicate with
the pipeline so that adding a new format is purely additive — implement the ABC,
register, done.

All parsers remain in the `formats/` folder. No new top-level package is created.

### Design Principle

Parsers write their results to well-known manifest fields. The rest of the pipeline
never reads parser internals — it reads the manifest. If a mandatory handshake
function is missing or returns an error/unknwn value, an error popup is shown
immediately (on parser selection for missing functions, or after Input is attempted
for validation failures). Warnings (e.g., lines > 1024 tokens) are displayed but
do not block.

---

### Current Implementation Snapshot

Two parallel hierarchies already exist in `formats/`:

1. **`FormatHandler`** (ABC in `formats/__init__.py`)
   - `format_id: str`, `extensions: list[str]`
   - `extract(path, encoding) → list[str]`
   - `inject(path, lines, encoding)`
   - `supports_original() → bool`, `get_metadata(path) → dict`
   - Registered via `FormatRegistry` with extension-based lookup.
   - Concrete handlers: `TxtHandler`, `CsvHandler`, `TsvHandler`, `JsonHandler`,
     `XlsxHandler`, `HtmlHandler`, `MarkdownHandler`, `JsonLenientHandler`,
     `TranslatorPlusHandler` (all in `formats/`). Stub handlers: `RpgMakerMVHandler`,
     `RpgMakerMZHandler`, `PdfHandler`, `EpubHandler`.

2. **`ParserScript`** (ABC in `formats/parser_base.py`)
   - Wraps a FormatHandler and adds game-engine-specific features.
   - `name: str`, `extract()`, `inject()`, optional `wordwrap_config`,
     `forbidden_chars`, `context_marker_rules`, `can_handle()`.
   - Dataclasses: `WordwrapConfig`, `ForbiddenChars`, `ContextMarkerRules`.
   - Registered via `ParserRegistry` with `can_handle()` auto-detection.
   - Concrete parsers: `RpgMakerMVParser`, `RpgMakerMZParser`
     (in `formats/parser_rpgmaker.py`).

**Registration flow:**
- `get_registry()` → `_load_handlers()` (simple, html, markdown, json_lenient,
  translator_plus)
- `get_parser_registry()` → `_load_parsers()` (RPG Maker MV, RPG Maker MZ)

**Step 0 (Input)** currently calls `FormatRegistry.get_for_path()` or
`ParserRegistry.detect()` to find the right handler. Lines are stored in
`manifest.lines[].orig`.

**Step 9 (Output)** calls the handler's `inject()` to write translated lines into
copies of the original files.

---

### Handshake Contract

#### A. MANDATORY Components

Every parser (whether a simple `FormatHandler` or an engine-specific `ParserScript`)
**must** implement the following. Failure to provide one raises an error popup when
the parser is selected.

| # | Component | Signature / Type | Description | Validation |
|---|-----------|-----------------|-------------|------------|
| M1 | **Extract** | `extract(path, encoding=None) → list[str]` | Extract translatable lines from the source file, one element per line. Must not return `None`. | Empty list is valid (file has no translatable text). Raises `ParserError` on read failure. |
| M2 | **Inject** | `inject(path, lines, encoding=None)` | Inject translated lines back into a **copy** of the source. Never modifies the original. | `len(lines)` must match the count produced by `extract()` for the same file. Raises `ParserError` on write failure. |
| M3 | **Format ID / Extensions** | `format_id: str` + `extensions: list[str]` **or** `can_handle(path) → bool` | Determines which file types this parser claims. For `FormatHandler` subclasses this is `format_id` and `extensions`. For `ParserScript` subclasses this is `can_handle()` (probes file structure). At least one mechanism is required. | `format_id` must be non-empty. `extensions` must have ≥1 entry or `can_handle()` must be defined. |

**Validation rules for mandatory outputs:**
- No single extracted line may exceed **2048 tokens** (raises `ParserError` immediately).
- Lines exceeding **1024 tokens** emit a warning popup: "Line {idx} is {N} tokens
  ({N-1024} over recommended limit). Consider splitting."
- Token counting uses `tiktoken` when available, else the `len(text) * 0.3` heuristic
  already in `functions/chunker.py`.

#### B. OPTIONAL Components

Optional components follow an `opt-in` pattern: the parser either provides the
attribute/method or does not. The pipeline checks `hasattr()` / `getattr(..., None)`
before using them. Missing optionals never raise errors.

| # | Component | Signature / Type | Description | Manifest Field(s) |
|---|-----------|-----------------|-------------|-------------------|
| O1 | **Decryption** | `decrypt(path) → path` | Decrypt source file before extraction. **Discouraged** without explicit copyright permission. Situated in pipeline *before* `extract()`. | — (transparent to manifest) |
| O2 | **Encryption** | `encrypt(path) → path` | Re-encrypt output file after injection. Situated *after* `inject()`. Must mirror the original encryption. | — (transparent to manifest) |
| O3 | **Encoding** | `detect_encoding(path) → str` **or** `encoding: str` | Calculate or declare the file encoding. When absent the pipeline uses its own heuristic (`chardet` → UTF-8 fallback from `formats/__init__.py`). | `Options.Encoding` |
| O4 | **Speaker Detection** | `detect_speakers(lines) → list[SpeakerInfo]` | Parse `Speaker: Dialogue` or format-specific speaker notation. Returns list of `SpeakerInfo(name, line_idx)`. When provided: auto-writes speakers to Analysis findings, disables the generic regex-based speaker detector in `functions/analysis.py` for this project. | `Analysis.speakers`, `characters[]` |
| O5 | **Wordwrap Config** | `wordwrap_config: WordwrapConfig` | Engine-specific wrapping settings (`max_line_length`, `max_line_number`, `wordwrap_command`, `new_textbox_injection`). Written to manifest in Wordwrap step (Step 7) and loaded by it. | `Options.Wordwrap.*` |
| O6 | **Wordwrap Function** | `wordwrap(line, config) → list[str]` | Custom wrapping logic that **replaces** the built-in `pretty_wrap`. When present, Step 7 calls this instead of `functions/wordwrap.py`. The return value is the wrapped lines list. | `lines[].wordwr` |
| O9 | **Pretty Wrap Hook** | `pretty_wrap(text, width, break_char, max_lines) → Optional[str]` | Lighter core-wrap replacement. Replaces built-in `pretty_wrap` while keeping speaker handling and pipeline logic intact. Used for user-managed tags or as fallback when O6 is absent. | `lines[].wordwr` |
| O7 | **Forbidden/Allowed Chars** | `forbidden_chars: ForbiddenChars` | Characters the engine cannot render. Added to logit bias during Translation (Step 5) and to the Blacklist/Whitelist during Postprocessing (Step 6). | `Options.ForbiddenChars`, `Options.LogitBias` |
| O8 | **Context Markers** | `context_marker_rules: ContextMarkerRules` | Regex patterns for scene, dialogue, menu, and choice boundaries. Injected during Input to tag lines. | `lines[].tag` |

#### C. Dataclass Reference (existing + extensions)

```python
# --- Already defined in formats/parser_base.py ---
@dataclass
class WordwrapConfig:
    max_line_length: int = 0        # 0 = no limit
    max_line_number: int = 0        # 0 = no limit
    wordwrap_command: str = "\n"    # engine linebreak
    new_textbox_injection: str = "" # overflow handler

@dataclass
class ForbiddenChars:
    characters: list[str]           # chars that must not appear
    logit_bias: dict[str, int]      # token→bias mapping
    output_action: str = "replace"  # "replace" | "flag"

@dataclass
class ContextMarkerRules:
    scene_pattern: str = ""         # regex
    dialogue_pattern: str = ""
    menu_pattern: str = ""
    choice_pattern: str = ""

# --- NEW for Parser Handshake ---
@dataclass
class SpeakerInfo:
    name: str          # speaker name as detected
    line_idx: int      # index into extracted lines where speaker appears
```

---

### Validation Pipeline

Validation is split into **selection-time** and **load-time** checks:

**Selection-time** (when user picks a format/parser in Step 0 dropdown):
- Verify `extract()` exists and is callable → error popup if missing.
- Verify `inject()` exists and is callable → error popup if missing.
- Verify `format_id` is non-empty or `can_handle()` is defined → error popup if
  neither.

**Load-time** (after user clicks Input to load files):
- Run `extract()` → on `ParserError`, show error popup with message.
- For each line: token-count check (>2048 → error, >1024 → warning).
- Encoding heuristic: if `detect_encoding` provided, use it and verify it can
  decode the first 8 KB of the file without errors. If heuristic, fall back
  through `chardet` → UTF-8 → Latin-1 with a warning on each fallback.

This validation must be **fast** — encoding heuristic reads the first 8 KB
only, token counting uses the fast `len(text) * 0.3` estimate for the warning
threshold and only calls `tiktoken` if the estimate exceeds 900 tokens.

---

### Manifest Integration Points

Parsers write to the manifest through the existing `ManifestManager` API.
The handshake standardises which keys are targeted:

| Parser Output | Manifest Key | Written When |
|---------------|-------------|--------------|
| Extracted lines | `lines[].orig` | Step 0 Input load |
| File directory | `file_dir[]` (with `type` field) | Step 0 Input load |
| Encoding | `Options.Encoding` | Step 0 Input load |
| Speaker list | `Analysis.speakers`, `characters[]` | Step 0 via O4 or Step 1 Analysis |
| Speaker-detect disable | `Options.ParserHandlesSpeakers` | Step 0 via O4 |
| Wordwrap config | `Options.Wordwrap.*` | Step 0 load; Step 7 reads |
| Wordwrap function flag | `Options.ParserHandlesWordwrap` | Step 0 load; Step 7 checks |
| Forbidden chars | `Options.ForbiddenChars` | Step 0 load; Step 5 logit bias |
| Context markers | `lines[].tag` | Step 0 via O8 or Step 1 Analysis |
| Decryption/Encryption | (transparent) | Step 0 before extract / Step 9 after inject |

---

### Implementation Plan

#### TASK P1: Define `ParserHandshake` Protocol
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `formats/handshake.py` with a `ParserHandshake` Protocol class
  documenting all mandatory and optional components.
- Add `SpeakerInfo` dataclass.
- Add `ParserError` exception class for mandatory-component failures.
- Add `validate_parser(parser) → list[str]` that returns error messages for
  missing mandatory components (empty list = valid).

**Files to Create:**
- `formats/handshake.py`

**Files to Modify:**
- `formats/__init__.py` — export `ParserHandshake`, `ParserError`,
  `validate_parser`, `SpeakerInfo`

**Tests to Add:**
- `dev/test_parser_handshake.py`:
  - `test_txt_handler_satisfies_handshake`
  - `test_csv_handler_satisfies_handshake`
  - `test_json_handler_satisfies_handshake`
  - `test_rpgmaker_parser_satisfies_handshake`
  - `test_missing_extract_raises`
  - `test_missing_inject_raises`
  - `test_missing_format_id_raises`
  - `test_optional_components_absent_ok`

---

#### TASK P2: Integrate Validation into Step 0 (Input)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

- On parser/format selection in Step 0, run `validate_parser()`.
  Missing mandatory → error popup, block load.
- After `extract()`, run per-line token validation (>2048 error, >1024 warning).
- Add encoding heuristic (8 KB probe, BOM → parser → utf-8 → shift_jis → cp932 → latin-1 fallback chain).
- Show error popups via `tkinter.messagebox.showerror`.

**Files Modified:**
- `gui/steps/input_extract.py` — `_validate_parser_selection()`, `_validate_extracted_lines()`,
  `_estimate_tokens()` (static method, tiktoken with `len*0.3` fallback),
  `_detect_encoding()` (8 KB probe, BOM → parser `detect_encoding()` → utf-8 → shift_jis → cp932 → latin-1)
- Wired into `_load_file()` (parser validation + token validation before loading)
- Wired into `_load_selected_paths()` (batch parser validation before file loop)

**Tests:** `dev/test_parser_input_routing.py` — 32 tests (all passing):
- TestHandshakeValidation (5): valid parser, missing extract, missing inject, missing identity, all registered parsers pass
- TestTokenValidation (4): short text, empty, long text, normal lines pass
- TestEncodingFallback (6): utf-8 BOM, utf-16 BOM, plain utf-8, shift_jis, latin-1 fallback, parser encoding preferred

---

#### TASK P3: Wire Optional Components into Pipeline
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Wired each optional component to its consuming pipeline step:

- **O3 Encoding**: Parser `detect_encoding()` preferred in 8 KB probe chain (P2).
- **O4 Speaker Detection**: `_wire_parser_optionals()` calls `detect_speakers()`,
  writes `SpeakerInfo` list to `characters[]`, sets `Options.ParserHandlesSpeakers`.
  Analysis step reads flag and skips generic speaker detection.
- **O5 Wordwrap Config**: `_apply_parser_wordwrap_defaults()` auto-populates
  wordwrap fields from `wordwrap_config` on tab entry (already done pre-P3).
- **O6 Wordwrap Function**: `_wire_parser_optionals()` sets
  `Options.ParserHandlesWordwrap`. Step 7 `_process_wrap` delegates to
  `parser.wordwrap()` instead of built-in `apply_wordwrap`.
- **O9 Pretty Wrap Hook**: `parser.pretty_wrap(text, width, break_char, max_lines)`
  replaces built-in core wrapping while keeping speaker handling and pipeline logic.
  Lighter than O6; used for user-managed tags or as fallback when O6 is absent.
  Detected via `type(parser).pretty_wrap is not ParserScript.pretty_wrap`.
- **O7 Forbidden Chars**: `_wire_parser_optionals()` serialises
  `forbidden_chars.to_dict()` to `Options.ParserForbiddenChars`. Translation
  step calls `api_client.apply_parser_forbidden_chars()` to merge into logit bias.
- **O8 Context Markers**: `_wire_parser_optionals()` compiles
  `context_marker_rules` and applies regex to extracted lines, writing
  `context_marker` tags. `detect_context_markers()` in `functions/analysis.py`
  accepts optional `parser_rules` parameter to override built-in heuristics.
- **O1/O2 Decrypt/Encrypt**: Deferred — requires permission UX design.

**Files Modified:**
- `gui/steps/input_extract.py` — `_wire_parser_optionals()` (~100 lines) called
  between `_ensure_project_created` and `_save_manifest_after_file_load`
- `gui/steps/analysis.py` — reads `ParserHandlesSpeakers`, skips generic speakers
- `gui/steps/wordwrap_overwrite.py` — reads `ParserHandlesWordwrap`, delegates
  to `parser.wordwrap()` per line
- `gui/steps/output_inject.py` — reads `ParserName`, routes through `parser.inject()`
- `gui/steps/translate.py` — reads `ParserName`, calls `apply_parser_forbidden_chars()`
- `functions/analysis.py` — `detect_context_markers()` accepts `parser_rules` kwarg

**Tests:** `dev/test_parser_optional_wiring.py` — 28 tests (all passing):
- TestO4SpeakerDetection (4): returns list, name+idx, no-override returns None, override check
- TestO6CustomWordwrap (4): has override, short line, long line, no-override returns None
- TestO7ForbiddenChars (4): exists, has characters, serialisable round-trip, RPG Maker check
- TestO8ContextMarkers (7): default heuristics, parser rules override, empty lines, LightVN rules exist, compile, dialogue match, no-rules+no-lines
- TestWireParserOptionals (7): parser name stored, speaker flag, wordwrap flag, forbidden chars dict, context markers flag, all LightVN optionals, info flags match checks
- TestAnalysisSpeakerSkip (2): without speakers, with speakers

---

#### TASK P4: Retrofit Existing Handlers to Handshake
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Verified and annotated all existing handlers:

- `TxtHandler` — M1 ✓, M2 ✓, M3 ✓ (extensions: `.txt`). No optionals.
- `CsvHandler` / `TsvHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `JsonHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `XlsxHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `HtmlHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `MarkdownHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `JsonLenientHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `TranslatorPlusHandler` — M1 ✓, M2 ✓, M3 ✓. O3 (encoding — SQLite). No others.
- `RpgMakerMVParser` — M3 ✓ (via `can_handle`). O5 ✓, O7 ✓, O8 ✓. M1/M2 stubs raise `ParserError`.
- `RpgMakerMZParser` — same as MV with different constants. M1/M2 stubs raise `ParserError`.

RPG Maker handler stubs (`formats/rpgmaker.py`) now raise `ParserError` with
`parser_name` and `component` metadata instead of silently returning empty
results. All registered FormatHandlers pass `validate_parser()`.

**Files Modified:**
- `formats/rpgmaker.py` — extract/inject raise `ParserError` on all three stubs

**Tests:** `dev/test_parser_handler_retrofit.py` — 28 tests (all passing):
- TestFormatHandlerCompliance (9): all extract, all inject, all identity, txt/csv/tsv/json/xlsx individual, validate_parser on all
- TestParserScriptCompliance (4): all parsers pass, LightVN valid, RPGMakerMV valid, RPGMakerMZ valid
- TestRpgMakerStubs (9): MV extract/inject raise, MZ extract/inject raise, plugin extract/inject raise, MV parser delegates raise, MZ parser delegates raise, error metadata
- TestRpgMakerParserOptionals (6): MV wordwrap, MZ wordwrap, MV forbidden chars, MV context markers, MV can_handle, MZ can_handle

**Tests:**
- Expand `dev/test_parser_handshake.py` with one test per handler.

---

#### TASK P5: New Parser Template & Documentation
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 1 hour

LightVN parser (`formats/LightVN.py`) serves as the reference implementation.
All features documented in `features.md`, `technical.md`, and `tests.md`.

---

=============================================================================

## PHASE: Provider Handshake — Unified LLM Provider Interface

**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 16-20 hours

### Goal

Define a formal "handshake" contract for LLM providers so that each provider
is a self-contained module in a new `providers/` top-level folder. The contract
has **mandatory** provider-level components, **mandatory** model-level components,
and **optional** components for advanced features. The OpenAI provider serves as
the **default reference implementation** — other providers that speak the
OpenAI-compatible format can simply delegate to OpenAI's functions instead of
reimplementing them.

Failure to satisfy a mandatory component or having it return an error/unknown
value raises an error popup immediately (on provider selection for missing
functions, or on first API call attempt for runtime failures).

---

### Current Implementation Snapshot

All provider logic currently lives in scattered locations:

1. **`functions/options.py`** — Provider definitions
   - `_STATIC_PROVIDERS`: anthropic, local, ollama, lmstudio (with URLs)
   - `_CLOUD_PROVIDER_META`: openai, gemini, mistral (with registry IDs + URLs)
   - `_build_api_providers()` merges static + dynamic model lists from registry
   - `API_PROVIDERS` is a lazy proxy dict rebuilt on every access
   - Helper functions: `get_api_urls()`, `get_provider_models()`,
     `get_provider_display_name()`, etc.

2. **`functions/api_client.py`** (~2170 lines) — Monolithic API client
   - `APIConfig` dataclass (50+ fields) — all config for all providers
   - `APIClient` class — a single class handling ALL providers:
     - `_init_client()` — creates `OpenAI(...)` SDK client for ALL providers
       (including Claude and Gemini, which use OpenAI-compatible endpoints)
     - Local providers get placeholder API key `"lm-studio"`
     - Provider-specific branching scattered throughout:
       - `is_local_provider()` — checks `LOCAL_PROVIDERS` tuple
       - `is_openai_reasoning_model()` — checks for "o1", "o3" in model name
       - `is_claude_thinking_model()` — checks for "claude" + versioned names
       - `supports_prompt_caching()` — OpenAI-only (Gemini excluded)
       - `supports_extended_cache_retention()` — gpt-4.1/gpt-5 only
     - `_translate_chunk()` has the biggest provider branch:
       - Local → `response_format = json_schema` (strict schema)
       - Cloud → `response_format = json_object`
       - Claude → `extra_body = thinking params`, inflated `max_tokens`
     - Token usage parsing assumes OpenAI response format
       (`usage.prompt_tokens_details.cached_tokens`, etc.)

3. **`functions/model_registry.py`** (~1730 lines) — Model data
   - `ModelInfo` dataclass with 30+ fields (pricing, rate limits, capabilities)
   - `FALLBACK_MODELS`: curated built-in data per provider (OpenAI 12, Google 7,
     Mistral 8 models) <- MUST BE REMOVED
   - Provider-specific fetchers: `fetch_openai_models()`, `fetch_google_models()`,
     `fetch_mistral_models()` — each fetches from provider API + parses pricing pages
   - `probe_openai_rate_limits()` — reads `x-ratelimit-*` headers
   - INI persistence: saves/loads model data to `user/API.ini`

4. **`functions/common_errors.py`** — Error classification
   - `classify_api_error()` inspects error type + message for provider-specific patterns
   - Categories: AUTH_INVALID, MODEL_NOT_FOUND, RATE_LIMITED, QUOTA_EXCEEDED,
     CONTENT_FILTERED, THINKING_NOT_AVAILABLE, TEMPERATURE_NOT_AVAILABLE, etc.

5. **`functions/config.py`** — loads API config from `user/API.ini`

6. **Supporting modules:**
   - `functions/local_llm.py` — `is_local_url()` helper
   - `functions/logit_bias.py` — `LogitBiasManager`
   - `functions/rate_limiter.py` — `RateLimiter`
   - `functions/batch_tracker.py` — `BatchJob` (batch API support)
   - `functions/request_cache.py` — `RequestCache`
   - `functions/retry_handler.py` — retry logic

**Key architectural problem:** Everything is routed through a single `OpenAI()`
SDK client. Provider differences are handled by scattered `if`/`elif` branches
inside `APIClient`. Adding a new provider means touching `api_client.py`,
`options.py`, `model_registry.py`, and `common_errors.py` simultaneously.

---

### Handshake Contract

#### A. MANDATORY Provider-Level Components

Every provider module **must** implement the following. Failure raises an error
popup when the provider is selected.

| # | Component | Signature / Type | Description | Validation |
|---|-----------|-----------------|-------------|------------|
| MP1 | **API Key Requirement** | `requires_api_key: bool` | `True` for cloud providers, `False` for local. Determines whether the pipeline validates and requires an API key before proceeding. When `False`, a placeholder key is used automatically. | Must be `bool`. |
| MP2 | **Input Price** | `get_input_price(model_id) → float` | Returns price in USD per 1M input tokens. For local providers returns `0.0` (FREE). Cloud providers must fetch or look up from static data. | Must be ≥ 0.0. Return `0.0` for free/local. |
| MP3 | **Output Price** | `get_output_price(model_id) → float` | Returns price in USD per 1M output tokens. Same rules as Input Price. | Must be ≥ 0.0. Return `0.0` for free/local. |
| MP4 | **Base URL** | `base_url: str` | Provider API endpoint. For OpenAI: `https://api.openai.com/v1`. For local: `http://localhost:{port}/v1`. | Must be non-empty, valid URL format. |
| MP5 | **Send Request** | `send_request(messages, model, temperature, response_format, **kwargs) → ProviderResponse` | Send a chat completion request. Returns a `ProviderResponse` with `content`, `usage`, `finish_reason`. This is the core translation call. Providers that use the OpenAI-compatible format can delegate to the default OpenAI implementation. | Must return `ProviderResponse`. Raises `ProviderError` on failure. | `temperature` may be disabled for some models and relegated to optional model.
| MP6 | **Parse Response** | `parse_response(raw_response) → ProviderResponse` | Extract translated content, token usage metadata, and finish reason from the raw API response. Must handle the provider's specific response format and normalise to `ProviderResponse`. | `ProviderResponse.content` must be non-empty on success. `ProviderResponse.usage` must populate `prompt_tokens` and `completion_tokens` at minimum. |

**`ProviderResponse` dataclass:**
```python
@dataclass
class ProviderResponse:
    content: str                           # The response text (JSON string)
    usage: TokenUsage                      # Token counts
    finish_reason: str = "stop"            # "stop", "length", "content_filter"
    raw: Any = None                        # Original response object for debugging

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Optional extended fields — populated when provider supports them
    cached_tokens: int = 0                 # OpenAI prompt caching
    reasoning_tokens: int = 0              # o1/o3/Claude thinking
    accepted_prediction_tokens: int = 0
    rejected_prediction_tokens: int = 0
```

**`ProviderError` exception hierarchy:**
```python
class ProviderError(Exception):
    """Base error for all provider failures."""
    def __init__(self, message, is_fatal=False, error_code="UNKNOWN"):
        ...

class AuthenticationError(ProviderError):    # is_fatal=True
class ModelNotFoundError(ProviderError):     # is_fatal=True
class RateLimitedError(ProviderError):       # is_fatal=False (retryable)
class QuotaExceededError(ProviderError):     # is_fatal=True
class ContentFilteredError(ProviderError):   # is_fatal=True
class ProviderConnectionError(ProviderError): # is_fatal=False (retryable)
class ProviderTimeoutError(ProviderError):   # is_fatal=False (retryable)
```

#### B. MANDATORY Model-Level Components

Each provider must be able to report these per-model facts. These determine
whether a model is valid for use in CherryAI.

| # | Component | Signature / Type | Description | Validation |
|---|-----------|-----------------|-------------|------------|
| MM1 | **Structured Output** | `supports_structured_output(model_id) → bool` | Whether the model can return structured JSON. CherryAI requires this for line-by-line translation matching. Models without structured output are **rejected** (not shown in model dropdown). | Must be `bool`. `True` → model included, else discarded. |
| MM2 | **Model Name** | `get_model_name(model_id) → str` | Human-readable display name for the model. | Must be non-empty. |
| MM3 | **Thinking / Reasoning** | `get_thinking_config(model_id) → ThinkingConfig` | Determines if and how thinking/reasoning is implemented for the model. Returns config with `available`, `mode` ("builtin" for o1/o3, "explicit" for Claude), and `param_builder` callable. | `ThinkingConfig.available` must be `bool`. When `True`, `mode` must be "builtin" or "explicit". "builtin" are by default rejected when filtering for No / Optional Thinking which is the default. |

**`ThinkingConfig` dataclass:**
```python
@dataclass
class ThinkingConfig:
    available: bool = False
    mode: str = ""                  # "builtin" | "explicit" | ""
    budget_default: int = 10000     # default thinking token budget
    budget_min: int = 1000
    budget_max: int = 100000

    def build_params(self, budget: int) -> dict:
        """Build provider-specific API params for thinking mode."""
        if not self.available:
            return {}
        if self.mode == "builtin":
            return {}  # OpenAI o1/o3: built-in, no extra params
        if self.mode == "explicit":
            return {    # Claude: explicit thinking param
                "thinking": {"type": "enabled", "budget_tokens": budget}
            }
        return {}
```

#### C. OPTIONAL Provider-Level Components

| # | Component | Signature / Type | Description |
|---|-----------|-----------------|-------------|
| OP1 | **Cached Input** | `get_cached_input_config(model_id) → CachedInputConfig \| None` | Check whether model supports prompt caching, minimum static prompt size to trigger it, and how cached tokens are reported. Currently OpenAI-only: prefix-based, auto-triggered at ≥1024 tokens, reported via `prompt_tokens_details.cached_tokens`. | Claude is know to be vastly different.
| OP2 | **Batch / Flex / Priority Mode** | `get_batch_config(model_id) → BatchConfig \| None` | Check availability of discount batch modes: Batch (50% off, 24h), Flex (variable discount), Priority (faster, premium). Returns differing input/output prices per mode. Currently only OpenAI has Batch. | Must be looked up for other providers.
| OP3 | **Model List Fetcher** | `fetch_models(api_key) → list[ModelInfo]` | Fetch available models from the provider API. Currently implemented for OpenAI, Google, Mistral. Each has its own endpoint and response format. |
| OP4 | **Rate Limit Probing** | `probe_rate_limits(api_key, model_id) → RateLimitInfo \| None` | Send a minimal request to read rate limit headers. Currently OpenAI-only (`x-ratelimit-*` headers). |
| OP5 | **Error Classifier** | `classify_error(error) → ClassifiedError` | Provider-specific error classification. When absent, falls back to the default classifier in `common_errors.py`. |

**`CachedInputConfig` dataclass:**
```python
@dataclass
class CachedInputConfig:
    supported: bool = False
    min_prefix_tokens: int = 1024   # minimum for cache to trigger
    retention: str = ""             # "" | "in_memory" | "24h"
    cached_price_ratio: float = 0.5 # cached tokens cost this fraction of normal
    param_builder: Callable = None  # builds provider-specific params

    @staticmethod
    def openai_default() -> 'CachedInputConfig':
        return CachedInputConfig(
            supported=True,
            min_prefix_tokens=1024,
            retention="in_memory",
            cached_price_ratio=0.5,
        )
```

**`BatchConfig` dataclass:**
```python
@dataclass
class BatchConfig:
    batch_available: bool = False
    batch_input_price_ratio: float = 0.5   # vs normal price
    batch_output_price_ratio: float = 0.5
    flex_available: bool = False
    flex_input_price_ratio: float = 0.0
    flex_output_price_ratio: float = 0.0
    priority_available: bool = False
    priority_input_price_ratio: float = 1.0
    priority_output_price_ratio: float = 1.0
```

#### D. OPTIONAL Model-Level Components

| # | Component | Signature / Type | Description |
|---|-----------|-----------------|-------------|
| OM1 | **Temperature** | `get_temperature_config(model_id) → TemperatureConfig \| None` | Whether the model supports temperature, and its valid range. Some models (o1) do not support temperature at all. Others have restricted ranges. |
| OM2 | **Context Window** | `get_context_window(model_id) → int` | Maximum context window in tokens. Used for chunk size validation. |

**`TemperatureConfig` dataclass:**
```python
@dataclass
class TemperatureConfig:
    supported: bool = True
    min_value: float = 0.0
    max_value: float = 2.0
    default: float = 0.3
```

---

### Provider Module Structure

New `providers/` top-level folder alongside `functions/`, `modi/`, `formats/`:

```
providers/
├── __init__.py          # ProviderBase ABC, ProviderRegistry, ProviderResponse,
│                        #   TokenUsage, ProviderError hierarchy, dataclasses
├── openai_provider.py   # OpenAI reference implementation — delegates to existing
│                        #   functions in api_client.py. Other OpenAI-format providers
│                        #   inherit or call these functions.
├── anthropic_provider.py  # Claude via OpenAI-compat + thinking mode specifics
├── google_provider.py     # Gemini via OpenAI-compat (generativelanguage endpoint)
├── mistral_provider.py    # Mistral via OpenAI-compat
├── local_provider.py      # LM Studio / Ollama / generic local (json_schema format)
└── custom_provider.py     # Template for user-created providers (future)
```

**`ProviderBase` ABC** (in `providers/__init__.py`):
```python
class ProviderBase(ABC):
    """Base class for all LLM providers."""
    name: str                          # e.g., "openai", "anthropic"
    display_name: str                  # e.g., "OpenAI", "Anthropic (Claude)"
    requires_api_key: bool = True      # MP1
    base_url: str = ""                 # MP4

    # --- Mandatory ---
    @abstractmethod
    def send_request(self, messages, model, temperature, response_format, **kw):
        """MP5: Send a chat completion request."""
        ...

    @abstractmethod
    def parse_response(self, raw_response) -> ProviderResponse:
        """MP6: Parse raw response to ProviderResponse."""
        ...

    @abstractmethod
    def get_input_price(self, model_id: str) -> float:
        """MP2: USD per 1M input tokens."""
        ...

    @abstractmethod
    def get_output_price(self, model_id: str) -> float:
        """MP3: USD per 1M output tokens."""
        ...

    @abstractmethod
    def supports_structured_output(self, model_id: str) -> bool:
        """MM1: Can this model return structured JSON?"""
        ...

    @abstractmethod
    def get_model_name(self, model_id: str) -> str:
        """MM2: Human-readable model name."""
        ...

    @abstractmethod
    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        """MM3: Thinking/reasoning support."""
        ...

    # --- Optional (default no-ops) ---
    def get_cached_input_config(self, model_id: str):
        return None  # OP1

    def get_batch_config(self, model_id: str):
        return None  # OP2

    def fetch_models(self, api_key: str) -> list:
        return []  # OP3

    def probe_rate_limits(self, api_key: str, model_id: str):
        return None  # OP4

    def classify_error(self, error: Exception):
        return None  # OP5 — falls back to common_errors.classify_api_error()

    def get_temperature_config(self, model_id: str):
        return TemperatureConfig()  # OM1

    def get_context_window(self, model_id: str) -> int:
        return 128000  # OM2 default
```

---

### OpenAI as Default Reference

`providers/openai_provider.py` is the reference implementation. It delegates to
the existing proven functions in `functions/api_client.py` rather than rewriting
them. Other providers that speak the OpenAI-compatible format (Gemini, Mistral,
generic locals via `/v1/chat/completions`) can inherit from
`OpenAICompatProvider` and override only what differs.

```python
class OpenAIProvider(ProviderBase):
    """Reference implementation. All existing api_client.py functions stay."""
    name = "openai"
    display_name = "OpenAI"
    requires_api_key = True
    base_url = "https://api.openai.com/v1"
    # Implements all methods by calling the existing api_client.py code

class OpenAICompatProvider(OpenAIProvider):
    """Base for providers using OpenAI-compatible endpoints."""
    # Override: name, display_name, base_url, pricing, model lists
    # Keep: send_request, parse_response (identical format)

class GoogleProvider(OpenAICompatProvider):
    """Gemini via OpenAI-compat endpoint."""
    name = "gemini"
    display_name = "Google (Gemini)"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # Override: pricing, model list fetcher, prompt caching (not supported)

class MistralProvider(OpenAICompatProvider):
    name = "mistral"
    display_name = "Mistral AI"
    base_url = "https://api.mistral.ai/v1"

class AnthropicProvider(OpenAICompatProvider):
    """Claude via OpenAI-compat proxy + thinking mode."""
    name = "anthropic"
    display_name = "Anthropic (Claude)"
    base_url = "https://api.anthropic.com/v1"
    # Override: thinking config (explicit mode), send_request (extra_body)

class LocalProvider(ProviderBase):
    """LM Studio / Ollama / generic local."""
    name = "local"
    display_name = "Local LLM"
    requires_api_key = False
    base_url = "http://localhost:11434/v1"
    # Override: send_request (json_schema format), pricing (FREE)
```

---

### Migration Path

The Provider Handshake is a **refactor**, not a rewrite. All existing features
must be preserved. The migration moves scattered provider logic from
`api_client.py` into discrete provider modules while keeping `APIClient` as
the orchestrator that delegates to the active provider.

**What moves to providers/:**
- Provider-specific request formatting (response_format branching)
- Provider-specific thinking mode params
- Provider-specific prompt caching params
- Provider-specific error classification
- Provider-specific pricing lookups
- Provider model list fetchers (from model_registry.py)
- Provider-specific rate limit probing

**What stays in api_client.py:**
- `APIClient` class as orchestrator (chunking, retry, caching, logging)
- `APIConfig` dataclass (config remains centralised)
- Translation batch orchestration (`translate_batch`, `_translate_chunk_with_retry`)
- Request caching and rate limiting (shared infrastructure)
- Step-log integration

**What stays in model_registry.py:**
- `ModelInfo` dataclass, `FALLBACK_MODELS` (curated static data)
- INI persistence (save/load to `user/API.ini`)
- Provider-specific fetch functions become thin wrappers calling provider modules

---

### Implementation Plan

#### TASK V1: Define Provider ABC and Shared Types
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `providers/__init__.py` with `ProviderBase` ABC, `ProviderResponse`,
  `TokenUsage`, `ProviderError` hierarchy, `ThinkingConfig`, `CachedInputConfig`,
  `BatchConfig`, `TemperatureConfig`, `ProviderRegistry`.
- `ProviderRegistry.register(provider)`, `get(name)`, `list_providers()`.
- `validate_provider(provider) → list[str]` — checks mandatory components.

**Files to Create:**
- `providers/__init__.py`

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_provider_base_is_abstract`
  - `test_mandatory_methods_enforced`
  - `test_optional_methods_have_defaults`
  - `test_provider_response_dataclass`
  - `test_token_usage_dataclass`
  - `test_provider_error_hierarchy`
  - `test_thinking_config_build_params`
  - `test_cached_input_config_openai_default`

---

#### TASK V2: OpenAI Reference Provider
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

- Create `providers/openai_provider.py` implementing `ProviderBase`.
- `send_request()` uses `OpenAI` SDK `client.chat.completions.create()`.
- `parse_response()` extracts `content`, `usage` (including
  `prompt_tokens_details.cached_tokens`, `completion_tokens_details.*`).
- `get_input_price()` / `get_output_price()` delegate to `model_registry`.
- `supports_structured_output()` checks `ModelInfo.structured_output`.
- `get_thinking_config()` returns builtin config for o1/o3 models.
- `get_cached_input_config()` returns OpenAI config for gpt-4o+ models.
- `fetch_models()` wraps existing `fetch_openai_models()`.
- `probe_rate_limits()` wraps existing `probe_openai_rate_limits()`.
- `classify_error()` wraps error patterns from `common_errors.py`.

**Files to Create:**
- `providers/openai_provider.py`

**Files to Modify:**
- `providers/__init__.py` — register OpenAI provider

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_openai_satisfies_handshake`
  - `test_openai_send_request_format`
  - `test_openai_parse_response_usage`
  - `test_openai_thinking_config_o1`
  - `test_openai_cached_input_gpt4o`
  - `test_openai_pricing_lookup`
  - `test_openai_structured_output_cloud_format`

---

#### TASK V3: OpenAI-Compatible Base + Google/Mistral Providers
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

- Create `OpenAICompatProvider` class inheriting from `OpenAIProvider`.
  It reuses `send_request()` and `parse_response()` but overrides URL,
  pricing, and model fetching.
- Create `providers/google_provider.py` (`GoogleProvider`):
  - `base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"`
  - `get_cached_input_config()` returns `None` (Gemini caching not supported)
  - `fetch_models()` wraps existing `fetch_google_models()`
- Create `providers/mistral_provider.py` (`MistralProvider`):
  - `base_url = "https://api.mistral.ai/v1"`
  - `fetch_models()` wraps existing `fetch_mistral_models()`

**Files to Create:**
- `providers/google_provider.py`
- `providers/mistral_provider.py`

**Files to Modify:**
- `providers/openai_provider.py` — add `OpenAICompatProvider` base
- `providers/__init__.py` — register Google and Mistral

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_google_satisfies_handshake`
  - `test_google_no_prompt_caching`
  - `test_google_pricing_free_tier`
  - `test_mistral_satisfies_handshake`
  - `test_mistral_pricing_lookup`
  - `test_openai_compat_inherits_send_request`

---

#### TASK V4: Anthropic (Claude) Provider
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `providers/anthropic_provider.py` (`AnthropicProvider`):
  - Inherits `OpenAICompatProvider` (uses OpenAI-compat endpoint)
  - Overrides `send_request()` to inject `extra_body` with thinking params
    and inflate `max_tokens` when thinking is enabled
  - `get_thinking_config()` returns explicit mode for Claude sonnet-4/opus-4/
    haiku-4 models
  - Pricing from model registry FallbackModels or hardcoded
  - Currently no models in `FALLBACK_MODELS` — add Claude models

**Files to Create:**
- `providers/anthropic_provider.py`

**Files to Modify:**
- `providers/__init__.py` — register Anthropic
- `functions/model_registry.py` — add Claude `FALLBACK_MODELS` entries

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_anthropic_satisfies_handshake`
  - `test_anthropic_thinking_config_claude`
  - `test_anthropic_send_request_extra_body`
  - `test_anthropic_max_tokens_inflation`

---

#### TASK V5: Local Provider (LM Studio / Ollama)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `providers/local_provider.py` (`LocalProvider`):
  - `requires_api_key = False`
  - `send_request()` overrides `response_format` to use full `json_schema`
    with strict schema (the biggest provider-specific branch currently in
    `_translate_chunk()`)
  - All pricing returns `0.0` (FREE)
  - `supports_structured_output()` returns `True` (LM Studio and Ollama
    support JSON schema)
  - `get_thinking_config()` returns default (not available)
  - `fetch_models()` queries `/v1/models` endpoint on localhost
  - Subclasses `LMStudioProvider` (port 1234) and `OllamaProvider` (port 11434)
    can override `base_url`

**Files to Create:**
- `providers/local_provider.py`

**Files to Modify:**
- `providers/__init__.py` — register Local, LMStudio, Ollama

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_local_satisfies_handshake`
  - `test_local_no_api_key_required`
  - `test_local_json_schema_format`
  - `test_local_pricing_free`
  - `test_lmstudio_port_1234`
  - `test_ollama_port_11434`

---

#### TASK V6: Integrate ProviderRegistry into APIClient
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Refactor `APIClient` to delegate to the active provider instead of using
inline `if`/`elif` branches:

- `__init__` resolves `self.provider = ProviderRegistry.get(config.provider)`
- `_translate_chunk()` replaces all provider branches with:
  - `response_format = self.provider.get_response_format(model)`
  - `thinking_params = self.provider.get_thinking_config(model).build_params(budget)`
  - `cache_params = self.provider.get_cached_input_config(model).build_params()`
  - `raw = self.provider.send_request(messages, model, temp, response_format, **extra)`
  - `result = self.provider.parse_response(raw)`
- Error handling delegates to `self.provider.classify_error(e)` with fallback
  to `common_errors.classify_api_error()`.
- `_init_client()` uses `self.provider.requires_api_key` instead of hardcoded
  `LOCAL_PROVIDERS` check.

**Critical**: This is a refactor — all existing tests must continue passing.
The observable behaviour of `APIClient` must not change.

**Files to Modify:**
- `functions/api_client.py` — refactor to use provider delegation

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_api_client_uses_provider_registry`
  - `test_api_client_local_json_schema`
  - `test_api_client_claude_thinking_delegation`
  - `test_api_client_openai_cache_delegation`
  - `test_api_client_error_classification_delegation`

---

#### TASK V7: Migrate options.py Provider Definitions
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Replace `_STATIC_PROVIDERS`, `_CLOUD_PROVIDER_META`, and `_build_api_providers()`
in `options.py` with lookups against `ProviderRegistry`:

- `API_PROVIDERS` becomes: `{p.name: {"url": p.base_url, "models": p.fetch_models_cached()} for p in ProviderRegistry.all()}`
- Helper functions (`get_api_urls`, `get_provider_models`, etc.) delegate to
  `ProviderRegistry`.
- `model_registry.py` fetch functions become thin redirects:
  `fetch_openai_models()` → `ProviderRegistry.get("openai").fetch_models()`.

**Files to Modify:**
- `functions/options.py` — replace provider dicts with registry lookups
- `functions/model_registry.py` — redirect fetch functions to providers

**Tests:**
- Existing tests in `dev/test_api_providers.py` must continue passing.
- `dev/test_provider_handshake.py`:
  - `test_options_api_providers_from_registry`
  - `test_model_registry_delegates_to_provider`

---

#### TASK V8: Provider Validation in Global Options UI
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

When user selects a provider in Global Options:
- Run `validate_provider()` — error popup for missing mandatory methods.
- Add model selection to Model Settings so every model gets its own settings. Ensure that each writers and loads its own config. Use default values for initial. 
- When user selects a model: check `supports_structured_output()` — warn if False.
- Check if Thinking is available, `get_thinking_config().available` — hide entry if False. When user enables thinking: check `get_thinking_config().available` — warn if False. Warn users that thinking and reasoning are only known to waste money and may even negatively affect translation. Ensure that the request do not contain thinking if not supported.
- When loading temperature: check `get_temperature_config().supported` — hide entry if
  not supported, adjust slider to show valid range if available. Ensure that the request do not contain temperature if not supported.

**Files to Modify:**
- `gui/dialogs/global_options.py` — add provider validation callbacks

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_provider_selection_validation`
  - `test_model_structured_output_warning`

---

#### TASK V9: New Provider Template & Documentation
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Create a documented template showing how to add a new provider:

- Copy template, fill in `send_request()`, `parse_response()`, pricing, model list.
- For OpenAI-compatible APIs: inherit `OpenAICompatProvider`, override URL and pricing.
- For truly custom APIs: implement `ProviderBase` directly.
- Register in `providers/__init__.py`'s `_load_providers()`.
- `validate_provider()` confirms compliance.

**Files to Create:**
- `providers/provider_template.py` — documented skeleton
- `doc/adding_a_provider.md` — step-by-step guide

---

### Summary of Provider-Specific Behaviour (Reference for Migration)

This table captures every known provider-specific branch from the current
codebase that must be preserved during migration:

| Concern | OpenAI | Claude (Anthropic) | Gemini (Google) | Mistral | Local (LM Studio/Ollama) |
|---------|--------|-------------------|-----------------|---------|--------------------------|
| **SDK init** | `OpenAI(api_key, base_url)` | Same (compat proxy) | Same (compat endpoint) | Same (compat endpoint) | Same + placeholder key `"lm-studio"` |
| **response_format** | `{"type": "json_object"}` | `{"type": "json_object"}` | `{"type": "json_object"}` | `{"type": "json_object"}` | Full `json_schema` with strict schema |
| **Thinking mode** | Built-in for o1/o3 (no extra params) | `extra_body.thinking` + inflated `max_tokens` | Not supported | Not supported | Not supported |
| **Prompt caching** | Auto for gpt-4o+; 24h retention for gpt-4.1/gpt-5 | No | No | No | No |
| **Batch mode** | Yes (JSONL, 50% off) | No | No | No | No |
| **Pricing** | Per-model (model_registry) | Default $1/$2 per M (no registry models yet) | FREE tier (some paid) | Per-model (model_registry) | FREE ($0.0) |
| **Token usage** | Full details (cached, reasoning, prediction) | Basic (prompt + completion) | Basic (prompt + completion) | Basic (prompt + completion) | Basic (prompt + completion) |
| **Error patterns** | All categories from `classify_api_error()` | Same (via compat) + thinking-specific | Same (via compat) + content filter likelihood | Same (via compat) | Connection errors more common |
| **Rate limit headers** | `x-ratelimit-*` (probeable) | Not available | Not available | Not available | Not applicable |
| **Model fetcher** | `fetch_openai_models()` — `/v1/models` + pricing page HTML | None (hardcoded) | `fetch_google_models()` — `/v1beta/models` + pricing page | `fetch_mistral_models()` — `/v1/models` | `/v1/models` on localhost |
| **Logit bias** | Supports `logit_bias` param | Not supported (ignored) | Limited support | Not supported | Varies by backend |
| **Temperature** | 0.0-2.0 (some models no temperature: o1) | 0.0-1.0 | 0.0-2.0 | 0.0-1.0 | Varies |

---

=============================================================================

Goal: Add category-aware right-click menu to the existing Findings Table. The
menu dynamically shows options based on the Category of selected row(s).

**Approach:**
- Keep existing Findings Table (do NOT split into separate tables)
- Add right-click context menu that inspects the Category column
- Show Speaker-specific options when Category = "Speakers"
- Show Code Pattern-specific options when Category = "Code Patterns"
- Show only generic options (Copy, Select All) when mixed categories selected

**Speaker Options:**
- Add to Glossary (writes to character glossary in manifest `characters` key)
- Set Role → (Protagonist | Love Interest | Major | Minor)
- Set Gender → (Male | Female | Other → Non-Binary | Transwoman | Transman)
- Set Translation → Custom Input dialog
- Add to Code Database (writes to manifest code database)
- Copy Name
- Select All with Speaker (sets filter)

**Code Pattern Options:**
- Preserve / Provides Context / Custom Placeholder / Protect (Generic Placeholder) / Strip with Anchor / Part of a Span (persisted to Code Database)
- Action sync: Protect → ProtectCodePatterns, Custom Placeholder → CustomPlaceholders, Strip with Anchor → AnchorRemoval (auto-synced via sync_code_pattern_actions in manifest_fields.py)
- Legacy migration: translate→provides_context, remove→preserve, replace→protect
- Is a Name / Is Text / Is a Number / Is Invisible (type classification)
- Nameable... (expanded dialog with Character/Company/Location modes,
  Custom Replacement, Role, Gender, Notes, OK/Cancel/Apply)
- Copy Pattern
- Show Lines with Pattern (sets filter)

**Enhancements Implemented:**
- All speakers shown (no truncation), ordered by count descending
- Individual code patterns shown instead of type summaries
- Details column auto-populated: sample lines for speakers, type + examples for codes
- Count Filter field: supports `<X`, `>X`, `<=X`, `>=X`, `=X` syntax
- Count Filter toggle button: switches between ≥ (default) and ≤ for bare numbers
- All code pattern actions persist to manifest via `save_code_glossary()`
- "Is a Name" adds to glossary with temp replacement
- "Nameable..." opens expanded dialog for character/company/location assignment
- Speaker actions write to character glossary (manifest `characters` key) via `_upsert_character_entry()`
- Gender support expanded: Male, Female, Non-Binary, Transwoman, Transman
- Import from Analysis dialogs offer choice of how many to import (non-destructive)
- Enhanced speaker detection: balanced bracket validation, no-newline rule, script-aware length limits (≤30 Latin / ≤20 CJK)
- Speaker Threshold (Global Options → Utility → Misc, default 10): below-threshold speakers collapsed into "[+] N Speakers" row; excluded from Glossary import and Term Translation

**Files Modified:**
- `gui/steps/analysis.py` - Right-click binding, dynamic menu, pattern actions, Nameable dialog
- `gui/helpers/analysis_adapter.py` - `detect_individual_codes_batch()`, speaker samples
- `gui/components/table.py` - Count filter entry with ≥/≤ toggle, `_parse_count_filter()`, updated `_apply_filter()`
- `functions/glossary.py` - Added GENDER_NONBINARY, GENDER_TRANSWOMAN, GENDER_TRANSMAN
- `gui/helpers/glossary_adapter.py` - New gender constant exports
- `functions/manifest_fields.py` - Added gender field to glossary entry schema

**Tests:**
- `dev/test_analysis_context_menu.py` - Category detection, menu options, no-truncation
- `dev/test_analysis_actions.py` - Glossary integration, role/gender persistence
- `dev/test_analysis_findings.py` - Individual codes, count filter, protagonist, details population

---

### TASK 59.4: Speaker Context Menu Actions
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement the Speaker-specific actions for the Findings Table context menu.
When user right-clicks on rows with Category = "Speaker", these options appear.

**Menu Actions to Implement:**
- Add to Glossary: Creates character glossary entry, original_name = speaker name, Translation empty
- Set Role → Protagonist | Love Interest | Major | Minor
  - Stored in character glossary entry's role field
- Set Gender → Male | Female | Other → (Non-Binary | Transwoman | Transman)
  - Stored in character glossary entry's gender field
- Set Translation → Dialog prompt
  - User enters custom translation
  - Fills character glossary entry's name (translation) field
- Add to Code Database: Creates manifest Code Database entry to protect speaker name
- Copy Name: Copies speaker name to clipboard
- Select All with Speaker: Filters preview panel to show lines from this speaker

**Multi-Select:**
- Support bulk operations: "Add X speakers to Glossary"
- Role/Gender apply to all selected

**Files to Modify:**
- `gui/steps/analysis.py` - Menu handler for speaker actions, character glossary helpers (`_upsert_character_entry`, `_load_characters`, `_save_characters`)
- `functions/manifest_fields.py` - `save_character_notes()`, `load_character_notes()` for character glossary

**Tests to Add:**
- `dev/test_analysis_actions.py`:
  - `test_add_speaker_to_glossary`
  - `test_set_speaker_role`
  - `test_set_speaker_gender`
  - `test_set_speaker_translation`
  - `test_speaker_multi_select_bulk`
  - `test_character_notes_populated`

---

### TASK 59.5: Code Pattern Context Menu Actions
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement the Code Pattern-specific actions for the Findings Table context 
menu. When user right-clicks on rows with Category = "Code Patterns", these options
appear.

**Action Options (persisted to Code Database via `save_code_glossary()`):**
- Preserve: Keep pattern unchanged in translation (default)
- Remove: Remove pattern from output
- Translate: Translate pattern as regular text
- Replace → Generic (placeholder) | Custom Input (dialog)

**Type Options (stored in notes field):**
- Is a Name: Pattern represents a character name — also adds to glossary with temp replacement
- Is Text: Pattern represents visible text content
- Is a Number: Pattern represents numeric values
- Is Invisible: Pattern is control code (default)

**Protagonist Variable Support → Nameable Dialog:**
- Nameable...: Opens expanded dialog for assigning replacement to code pattern
- Three modes: Character, Company, Location — each pre-fills suitable defaults
- Fields: Custom Replacement, Role dropdown, Gender dropdown, Custom Notes
- OK / Cancel / Apply buttons for persistence control
- Warns if entry already exists (overwrite confirmation)
- Replacement name stored in character glossary (manifest `characters` key) and code pattern stored in Custom Placeholders (manifest `CustomPlaceholders` key, restore_after=True)

**Utility Options:**
- Copy Pattern: Copy to clipboard
- Show Lines with Pattern: Sets findings table filter to show pattern

**Code Database Integration:**
- All actions persisted via `_upsert_code_pattern()` → `save_code_glossary()`
- Stored as `code_patterns[]` in manifest data
- Populates Code Database in Information Step (Step 3)
- Populates Preprocessing options (Step 4)
- LLM prompt includes action/type info for special handling

**Multi-Select:**
- Support bulk operations: "Set X patterns to Preserve"
- Action and Type apply to all selected

**Files Modified:**
- `gui/steps/analysis.py` - Pattern action handlers with persistence, protagonist feature
- `functions/manifest_fields.py` - `save_code_glossary()`, `load_code_glossary()`

**Tests:**
- `dev/test_analysis_actions.py` - Pattern action options, multi-select, code glossary

---

[Archived: Session 33: Manifest Rework → see doc/archived.md]

[Archived: Phase 60: UX Polish & Preset Rework → see doc/archived.md]

[Archived: Information Step UI Improvements → see doc/archived.md]


[Archived: Information Step Functional Enhancements → see doc/archived.md]

[Archived: 2026 User-Folder & Security Overhaul + Sessions 29–30 → see doc/archived.md]

[Archived: Session 30 TASK 74 + Phase 78 + Dynamic Registry + API Keys → see doc/archived.md]

---

### TASK 75+: Utility Section Expansion — Term Translation & Gender Inference
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Expand Global Options → Utility section with per-feature API key/model
selection, batch size control, configurable gender inference modes, and error
abort on API failure.

**Term Translation:**
- Mode dropdown: Romaji / LLM (legacy Simple/MTL migrate to Romaji)
- API key provider + key name dropdowns populated from API.ini [api_keys]
- Model **Combobox** auto-populated via `_update_term_model_list()` → `get_provider_models(provider)` when API key changes
- Batch size spinbox (1–100, default 10); `_worker` calls `translate_terms()` which splits internally
- API.ini [term_translation] profile stores provider/key_name/model
- Code validation: `extract_code_segments()` + `validate_translation_code()` — skip terms with missing code segments
- Skip empty/whitespace-only/identical results silently
- Partial save on error: `_save_results()` persists all successful translations before showing error messagebox
- RuntimeError on missing key or API failure, caught in analysis.py

**Gender Inference:**
- Mode dropdown: Script only / Script + LLM
- "Script only" runs heuristic pass with configurable confidence (min/max)
- "Script + LLM" runs script first, then LLM on remaining unknowns
- Separate API key/model controls (stored in API.ini [gender_inference])
- Model **Combobox** auto-populated via `_update_gender_model_list()` → `get_provider_models(provider)` when API key changes
- LLM confidence spinboxes (min/max, default 3/5)
- ignore_unknown / do_all checkboxes for both script and LLM
- RuntimeError on LLM failure shown via messagebox

**UtilitySettings dataclass:** Expanded from 1 to 17 fields with full
to_dict/from_dict roundtrip and legacy mode migration.

**Files Modified:**
- `gui/dialogs/global_options.py` — UtilitySettings, _build_utility_section (Combobox model fields, _update_term_model_list, _update_gender_model_list), _on_apply, save defaults
- `functions/term_translation.py` — Rewritten: batch splitting, API.ini profile, RuntimeError, extract_code_segments(), validate_translation_code()
- `functions/API2Glossary.py` — infer_gender_llm(), _has_consensus(), _call_api_for_excerpt_custom()
- `gui/steps/analysis.py` — _worker() batch processing via translate_terms(), code validation, skip-empty, _save_results()/_finish_with_error() partial save on error
- `gui/steps/information.py` — Rewritten _infer_character_genders() with two modes

**Tests:**
- `dev/test_utility_settings.py` — 57 unit tests (dataclass, batching, consensus, error abort, model dropdown)
- `dev/test_utility_integration.py` — 7 live API tests with gpt-4.1-nano
- `dev/test_term_translation.py` — 100 tests (batch, skip-empty, code validation, partial save, manifest-only persistence, chunk save, code patterns in prompt)

---

### TASK 75++: Structured Output, Configurable Prompts & Token Efficiency
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Minimise output-token waste (previously 2k input → 33k output in 15
requests) by enforcing strict JSON-schema structured output, adding `max_tokens`
caps and `store=False`. Make prompts for Term Translation and Gender Inference
configurable in Global Options → Prompts. Hide Edit/TLC prompt sections.

**Structured Output (json_schema):**
- `term_translation.py` — `_TERM_TRANSLATION_SCHEMA` with strict `{"translations": [...]}` schema
- `API2Glossary.py` — `RESPONSE_SCHEMA` with gender enum `[Female, Male, Non-Binary, Unsure]`
- Both use `store=False` (prevents storing requests for model training)
- `term_translation.py` — `max_tokens=max(100, len(terms) * 20)`
- `API2Glossary.py` — `max_tokens=150`

**Configurable Prompts (Global Options → Prompts):**
- Three new PromptsSettings fields: `term_glossary`, `term_code`, `gender_inference`
- Three new DEFAULT constants with `{source_lang}`, `{target_lang}`, `{count}` (term) and `{name}`, `{excerpt}` (gender) placeholders
- `_get_prompt_template(prompt_type)` in term_translation.py reads from CherryAI.ini `[prompts]`
- `_get_gender_prompt(name, excerpt)` in API2Glossary.py reads from CherryAI.ini `[prompts]`
- Fallback to compiled-in defaults when ini has no value

**Prompt Type Routing:**
- `translate_term()` and `translate_terms()` accept `prompt_type="glossary"|"code"` kwarg
- `analysis.py _translate_terms()` passes `prompt_type="glossary"` for characters, `"code"` for code patterns

**Gender Normalization:**
- `_normalize_gender()` maps API output: Unsure→Unknown, Neutral→Non-Binary
- All API result handlers use `_normalize_gender()` for consistent downstream values

**UI Changes (Global Options → Prompts):**
- Three utility prompt LabelFrames at top: Glossary, Code, Gender Inference
- Each has a Text widget + scrollbar + "Reset to Default" button
- Edit Step Prompt and TLC Step Prompt sections hidden (widgets exist for data round-trip)

**Files Modified:**
- `gui/dialogs/global_options.py` — PromptsSettings + 3 new defaults + UI sections + hide Edit/TLC
- `functions/term_translation.py` — json_schema, store=False, max_tokens, prompt_type, configurable prompt
- `functions/API2Glossary.py` — json_schema gender enum, store=False, max_tokens=150, _normalize_gender, configurable prompt
- `gui/steps/analysis.py` — prompt_type="glossary" / "code" pass-through

**Tests:**
- `dev/test_utility_settings.py` — Expanded to 53 tests (+26 new: PromptsSettings fields, prompt_type routing, _get_prompt_template, _normalize_gender, schema validation)

---

### Phase 78.2: API Error Classification, Concurrent Execution & Validation
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Classify all API errors with user-facing messages and remediation steps,
add first-request validation gate, implement concurrent string execution, sort
requests by content type, and fix context-type conditional prompt injection.

**Completed Sub-tasks:**
1. ✅ API Error Classification System (`functions/common_errors.py`)
   - 20-category APIErrorCategory enum, ClassifiedAPIError dataclass
   - classify_api_error() maps exceptions to categories
   - TranslationAbortError with format_for_display()
2. ✅ First-Request Validation Gate (`gui/steps/translate.py`)
   - First chunk sent alone; fatal errors abort immediately
3. ✅ Instant-Stop on Non-Structured Output (`functions/api_client.py`)
   - _translate_chunk_with_retry() classifies errors; fatal = no retry
   - _translate_chunk() reclassifies before re-raising
4. ✅ Request String Sorting by Type (`functions/prompt_builder.py`)
   - sort_requests_by_type(): Dialogue > Choice > Mixed/Unknown > Menu
   - RequestString dataclass with priority, RC chain detection
5. ✅ Concurrent Request Execution (`gui/steps/translate.py`)
   - ThreadPoolExecutor parallel strings, sequential within string
   - _group_chunks_into_strings(), _process_single_chunk(), _execute_string_sequential()
   - Thread-safe progress via threading.Lock
6. ✅ Context-Type Conditional Prompt Fix (`gui/steps/translate.py`)
   - _translate_chunk() now passes context_type to _build_system_prompt_from_manifest()
   - Enables §5.2 item 7b injection (was silently missing)

**Files Modified:**
- `functions/common_errors.py` — APIErrorCategory, ClassifiedAPIError, classify_api_error, TranslationAbortError
- `functions/api_client.py` — _translate_chunk_with_retry rewrite, _translate_chunk error classification
- `functions/prompt_builder.py` — _CONTEXT_TYPE_PRIORITY, RequestString, sort_requests_by_type, _build_string
- `gui/steps/translate.py` — Concurrent engine, validation gate, _process_single_chunk, context_type fix

**Tests (133 total):**
- `dev/test_api_error_classification.py` — 56 tests
- `dev/test_first_request_gate.py` — 14 tests
- `dev/test_request_sorting.py` — 22 tests
- `dev/test_concurrent_execution.py` — 23 tests
- `dev/test_context_type_prompts.py` — 18 tests

---

### Phase 60: Input Step Improvements
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Fix Type column display bug, replace Sort Combobox with clickable column headers,
add file list filter, and implement cross-file preview search with automatic file switching.

**Completed Sub-tasks:**
1. ✅ Type Column Refresh Fix (`gui/steps/input_extract.py`)
   - Added `_update_file_list()` call after `_ensure_project_created()` + `_save_manifest_after_file_load()` in all 3 loading methods
   - Root cause: `_update_file_list()` was called before `_sync_lines_to_manifest()` set file types via `classify_file_type()`
2. ✅ Clickable Column Headers (`gui/steps/input_extract.py`)
   - Replaced Sort Combobox with clickable Name/Type/Lines column headings
   - ▲/▼ indicators for ascending/descending sort direction
   - Same column click toggles direction; different column resets to ascending
   - New attributes: `_sort_column`, `_sort_ascending`
   - New methods: `_on_column_sort()`, `_refresh_sort_headings()`
3. ✅ File List Filter (`gui/steps/input_extract.py`)
   - Filter Entry replaces Sort Combobox frame area
   - Matches against display name, file type, or line count (case-insensitive)
   - ✕ clear button resets filter; filter resets on New Project
   - New widgets: `_file_filter_var`, `_file_filter_entry`, `_file_filter_clear_btn`
4. ✅ Cross-File Preview Search (`gui/steps/input_extract.py`)
   - Added `idx` column to preview Treeview
   - Search text triggers cross-file search across ALL loaded files
   - Selecting a result auto-switches to the containing file in the file tree
   - ✕ clear button restores single-file preview mode
   - New methods: `_update_preview_single_file()`, `_update_preview_cross_file()`, `_on_preview_select()`, `_select_file_in_tree()`, `_on_preview_search_clear()`

**Files Modified:**
- `gui/steps/input_extract.py` — All 4 improvements

**Tests (60 total):**
- `dev/test_input_step_improvements.py` — 60 tests (all passing)

=============================================================================
TASK: INFORMATION STEP UI REFINEMENTS
=============================================================================
Status: ✅ COMPLETE

Goal: Three visual and UX refinements to the Information Step (Step 2).

1. ✅ Disabled Textbox Greying (`gui/steps/information.py`)
   - `_apply_widget_enabled_state()` static method: sets bg/fg for ScrolledText
   - THEME.bg_disabled / THEME.text_disabled when disabled; white/black when enabled
   - Applied to Summary, Style, Tone, System Instructions fields
   - Called by `_toggle_section_enabled()` and `_load_section_toggles()`

2. ✅ Button Right-Alignment (`gui/steps/information.py`)
   - Save, Delete, Toggle buttons for Style, Tone, SI now use `side="right"` pack
   - Reversed pack order (toggle → delete → save) for correct visual left-to-right
   - Matches existing Summary section button layout

3. ✅ Table Sorting by Count + Clickable Headers (`gui/steps/information.py`)
   - Glossary (Characters) defaults to count descending, Code Database already did
   - All column headings clickable: ascending → descending → reset to count
   - ▲/▼ arrows in active sort column heading
   - Glossary uses `char_{idx}` tags via `_get_char_idx()` for index mapping
   - Manifest saves in count-descending order for both tables
   - New attributes: `_char_sort_col`, `_char_sort_reverse`, `_char_sort_clicks`
   - New attributes: `_code_sort_col`, `_code_sort_reverse`, `_code_sort_clicks`
   - New methods: `_on_char_heading_click()`, `_update_char_heading_arrows()`
   - New methods: `_on_code_heading_click()`, `_update_code_heading_arrows()`
   - New method: `_get_char_idx()`

**Files Modified:**
- `gui/steps/information.py` — All 3 refinements

**Tests (76 total in test_section_toggles.py):**
- TestDisabledTextboxGreyOut — 11 tests
- TestButtonAlignment — 11 tests
- TestTableSorting — 19 tests

END OF ROADMAP
=============================================================================