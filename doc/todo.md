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

**Current Status:** 4428 tests (verified June 2025 via pytest --collect-only)

Two test types:
- **Script Test**: pytest unit tests (fast, no LLM)
- **API Test**: 7-stage One_Click_Test (full pipeline with LLM)

Run Script Tests: `python -m pytest CherryAI/dev/ -v --timeout=10`
Run API Test: `python CherryAI.py test`

**Note:** Always use `--timeout` to prevent infinite loops. See `doc/tests.md`.

=============================================================================

MODULE COUNTS (Verified January 2026)

- functions/: 37 modules (+ glossaries/ subfolder with 5 files)
- modi/: 12 processing modes
- formats/: 5 format handlers
- gui/steps/: 10 workflow tabs
- gui/helpers/: 6 adapter modules (mode, analysis, glossary, chunker, prompt, manifest_binding)
- gui/dialogs/: 3 dialog modules (global_options, project_dialog, loading_progress)

=============================================================================

=============================================================================

COMPLETED - SESSION 25 (Remove config/ Folder)

### SESSION 25: Remove config/ Folder — All Config Embedded in INI/Constants ✅ DONE

**Changes implemented:**
- `config/` folder — DELETED entirely (defaults.ini, config.txt, prompt.txt,
  output_examples.txt, base_instructions.txt, game_summary.txt,
  translation_style.txt, conditional_prompts.json all removed)
- `functions/ini_manager.py` — `_FACTORY_DEFAULTS_INI_TEXT` constant embeds all
  factory defaults; `get_defaults_path()` returns None (compat stub);
  `_load_defaults_ini()` uses `read_string()` on embedded constant;
  added `[caching].aggressive_dedup = false` to embedded constant
- `functions/prompt_builder.py` — `_DEFAULT_PROMPT_TEMPLATE` embeds full eroge
  translator prompt; `_DEFAULT_OUTPUT_EXAMPLES` embeds JSON format examples;
  `config_dir` default changed to `Path(".")`;
  `style_file`/`summary_file` default to empty string (no external file)
- `functions/project_config.py` — `summary_file` default changed from
  `config/game_summary.txt` to `""` throughout; `load_game_summary()` returns
  early on empty path
- `functions/API2Glossary.py` — API key now read from `user/API.ini [api2glossary]
  key` (was `config/config.txt`)
- `functions/dedup.py` — `_is_aggressive_enabled()` reads from
  `user/CherryAI.ini [caching].aggressive_dedup` (was `config/config.txt`)
- `functions/config.py` — DEFAULTS `summary_file`/`style_file` both → `""`
- `functions/agent_modes.py` — Removed `config/base_instructions.txt` and
  `config/prompt.txt` from `DOC_READ_PATHS`
- `functions/auto_pipeline.py` — `_step_apply_defaults()` uses
  `get_all_initial_defaults()` and new `_apply_defaults_from_dict()` method
- `functions/conditional_prompts.py` — `DEFAULT_CONDITIONS_FILE` →
  `user/conditional_prompts.json`; `config_dir` default → `Path("user")`
- `CherryAI.ini` — `summary_file =` and `style_file =` now empty (no external file)
- `user/API.ini` — Added `[api2glossary]` section with `key =` placeholder
- `gui/helpers/prompt_adapter.py` — All `config/...` defaults removed; uses `""`
- `gui/helpers/glossary_adapter.py` — `summary_file` default → `""`
- `dev/example/sample.txt` + `dev/example/sample_translated.txt` — Created
  (moved from `config/`)

**Tests fixed:**
- `test_defaults.py` — Rewrote 5 test methods to work with embedded constant
- `test_prompts_config.py` — Rewrote `TestPromptsINIConfiguration` (4 tests)
- `test_game_summary.py` — `test_default_values` expects `""` not path
- `test_phase34_comprehensive.py` — `test_config_files_exist` uses
  `get_initial_default()` instead of checking `config/defaults.ini` file

=============================================================================

COMPLETED - SESSION 24 (INI System + Conditional Prompts)

### SESSION 24: INI Population, Conditional Prompts in Global Options, Mock Context ✅ DONE

**Changes implemented:**
- `config/defaults.ini` — Renamed all sections/keys to match `CherryAI.ini` naming
  (logging→log, safety→limit, file_io→fileio; updated key names throughout);
  added `[conditional_prompts]` section with dialogue/menu/choice/unknown prompts
- `functions/ini_manager.py` — `_populate_from_defaults()` auto-seeds empty CherryAI.ini
  sections from defaults.ini on first load; `get_conditional_prompt()` /
  `set_conditional_prompt()` helpers for typed access to context-type prompts
- `functions/prompt_builder.py` — `get_context_prompt()` reads from INI first via
  `get_conditional_prompt()`; falls back to hardcoded constants
- `gui/dialogs/global_options.py` — `PromptsSettings` gains 4 new fields
  (dialogue, menu, choice, unknown); Global Options Prompts section shows a
  4-row conditional prompts table (Text widget + scrollbar + Reset per row);
  save/load/defaults all wired up for the new fields
- `functions/mock_translator.py` — `MockTranslator.__init__` gains `context_type`
  param; `translate_batch()` accepts optional per-call `context_type`; factory
  `create_mock_translator()` forwards `context_type`
- `functions/api_client.py` — `translate_batch()` passes `system_prompt` to
  `_mock_translate()`; `_mock_translate()` extracts context_type from prompt header
  and forwards to `create_mock_translator()`
- `dev/test_gui_dialogs.py` — Updated to use new Settings dataclass field names
- `dev/test_prompts_config.py` — Updated defaults.ini reads to use `encoding='utf-8'`

=============================================================================

COMPLETED TASKS - PHASE 62: FILE SYSTEM AND API UNIFICATION
✅ DONE — Session 28

### Phase 62 Overview

**Priority:** HIGH | **Status:** ✅ COMPLETE (Session 28) | **Effort:** 8-12 hours

**Goal:** Unify all diverged parallel systems into the canonical file design:
- `user/CherryAI.ini` — all non-meta config (prompts, sytsem instructions, style, tone, caching, limits, UI)
- `user/API.ini` — all API meta information (keys, model, temperature, URL, provider profiles)
- `user/globalglossary.tsv` — global translation glossary (3 columns: Original, Translation, Notes)
- `user/codedatabase.tsv` — global code pattern database (Pattern, Type, RegEx, Notes, Visibility, extended props)
- `Projects/` — Per-project manifests — all project-specific information, including glossary and code entries as well as current entries and options from the four above
- `logs/` - Created and Accessed during Translation and QA
- `cache/` - Created and Accessed during Translation to optionally skip lines or requests (filling translation via script)

---

### TASK 62.1: Glossary File Unification (CSV → TSV, 3-column design)

**Status:** ✅ DONE (Session 28) | **Effort:** 3 hours
**Tests:** `dev/test_phase62_glossary.py` — 32 tests, all passing

**CONFLICTING FUNCTIONS (same purpose, different implementation):**

| Function/File | Location | Purpose | Return/Format |
|--------------|----------|---------|---------------|
| `_unified_glossary_path()` | `functions/glossary.py:191` | Path to global glossary | `user/GlobalGlossary.csv` (CSV, 8 columns) |
| `_global_db_path("Glossary")` | `gui/steps/information.py:3264` | Path to global glossary for widget | `user/global_glossary.json` (JSON, unknown schema) |

**SIMILAR BUT NOT THE SAME:**

| System | Where Used | What It Does | Difference |
|--------|-----------|--------------|------------|
| `glossary.py` CSV reader | `functions/glossary.py`, `functions/prompt_builder.py`, `functions/API2Glossary.py` | Reads/writes GlobalGlossary.csv for translation prompt inclusion | Structured CSV with 8 columns; used in translation pipeline |
| Information step JSON | `gui/steps/information.py::_load_global_db()` | Loads global_glossary.json for the Global Glossary widget display | JSON format; GUI-only; not connected to translation pipeline |

**Root Cause:** The Global Glossary widget was built independently of functions/glossary.py. It uses
a JSON file while the translation pipeline uses CSV. Neither knows about the other.

**Target Design:**
- Single file: `user/globalglossary.tsv` with 3 columns: `Original`, `Translation`, `Notes`
- `Notes` column carries all contextual data: type, gender, role, source (plain text in Notes field)
- `functions/glossary.py` reads/writes `globalglossary.tsv`
- `gui/steps/information.py` Global Glossary widget reads/writes same `globalglossary.tsv`
- Migration: `GlobalGlossary.csv` → `globalglossary.tsv` on first access (auto-migration in `_unified_glossary_path()`)
- Legacy `global_glossary.json` merged into `globalglossary.tsv` on first widget load then deleted

**Files to Modify:**
- `functions/glossary.py` — `_unified_glossary_path()` returns `globalglossary.tsv`; reader/writer uses TSV 3-column format; auto-migration chain: `glossary.csv` → `GlobalGlossary.csv` → `globalglossary.tsv`
- `gui/steps/information.py` — `_global_db_path()`, `_load_global_db()`, `_save_global_db()` all route to `globalglossary.tsv` via `functions/glossary.py`
- `dev/test_information_step_phase41.py` — Update `TestGlobalGlossaryWidget` tests to expect `globalglossary.tsv`
- `dev/test_glossary_*.py` — Update path assertions

**Tests to Add:**
- `test_glossary_migration` — Legacy CSV migrates to TSV on first access
- `test_glossary_3col_format` — TSV has exactly 3 columns: Original, Translation, Notes
- `test_global_glossary_widget_uses_tsv` — Widget reads/writes same file as pipeline

---

### TASK 62.2: Code Database Unification (SQLite → TSV)

**Status:** ✅ DONE (Session 28) | **Effort:** 3 hours
**Tests:** `dev/test_phase62_codedb.py` — 27 tests, all passing

**CONFLICTING FUNCTIONS (same purpose, different implementation):**

| Function/File | Location | Purpose | Format |
|--------------|----------|---------|--------|
| `_code_glossary_path()` | `functions/glossary.py:204` | Path to global code DB | `user/codeglossary.db` (SQLite) |
| `code_glossary_db.init_db()` | `functions/glossaries/code_glossary_db.py` | Initialize SQLite DB | SQLite WAL, schema: codes(code, type, regex, notes) |
| `_global_db_path("Code Database")` | `gui/steps/information.py:3264` | Path for Code DB widget | `user/global_codes.json` (JSON) |

**SIMILAR BUT NOT THE SAME:**

| System | Where Used | What It Does | Difference |
|--------|-----------|--------------|------------|
| `code_glossary_db.py` SQLite | `functions/glossary.py`, `functions/glossaries/code_glossary_functions.py` | Read/write code patterns from SQLite for analysis and translation | Structured SQLite, 4-column schema |
| Information step JSON | `gui/steps/information.py::_load_global_db()` | Loads global_codes.json for Code Database widget display | JSON format; GUI-only; not connected to pipeline |
| Per-project Code Database | Manifest `CodeGlossary[]` | Project-specific code patterns with extended props (Action, IsInvisible, etc.) | JSON in manifest; used by preprocessing/postprocessing |

**Root Cause:** Three separate implementations for code data. The global DB (SQLite) and widget (JSON)
are disconnected. Project manifest code entries have more fields (Action, Visibility) than the global DB.

**Target Design:**
- Single file: `user/codedatabase.tsv` with columns: `Pattern`, `Type`, `RegEx`, `Notes`, `Visible`, `IsInvisible`, `IsCouple`, `IsNumber`, `IsWord`
- `functions/glossaries/code_glossary_db.py` rewritten to use TSV I/O instead of SQLite
- `gui/steps/information.py` Code Database widget routes to same `codedatabase.tsv`
- `_code_glossary_path()` updated to return `codedatabase.tsv`
- Migration: `codeglossary.db` → `codedatabase.tsv` on first access; `global_codes.json` merged then deleted

**Files to Modify:**
- `functions/glossaries/code_glossary_db.py` — Replace SQLite with TSV I/O; preserve API surface (`read_all_rows()`, `write_all_rows()`, `upsert_rows()`, `delete_row()`)
- `functions/glossary.py` — `_code_glossary_path()` returns `codedatabase.tsv`
- `gui/steps/information.py` — `_global_db_path("Code Database")`, `_load_global_db()`, `_save_global_db()` route to `codedatabase.tsv`
- `dev/test_information_step_phase41.py` — Update `TestCodeDatabaseActions` tests
- `dev/test_code_glossary.py` — Update path assertions

**Tests to Add:**
- `test_code_db_migration` — codeglossary.db migrates to codedatabase.tsv on first access
- `test_code_db_9col_format` — TSV has correct columns including Visibility + extended props
- `test_code_db_widget_uses_tsv` — Widget reads/writes same file as pipeline

---

### TASK 62.3: api_profiles.ini Consolidation into API.ini

**Status:** ✅ DONE (Session 28) | **Effort:** 2 hours
**Tests:** `dev/test_phase62_api.py` — 25 tests, all passing

**CONFLICTING FUNCTIONS (same purpose, different implementation):**

| System | File | Purpose | What It Has |
|--------|------|---------|-------------|
| `api_profiles.ini` | Project root | API provider profiles | `[translation]` and `[glossary]` sections with provider, api_key, base_url, model, temperature, timeout, retries, rate_limit, chunk_size |
| `api_config.py` + `user/API.ini` | `functions/api_config.py` + `user/API.ini` | Encrypted API configuration | Currently only has encrypted keys and security hash |

**Root Cause:** `api_profiles.ini` was an early design. `api_config.py`/`API.ini` was built as the
secure replacement but only covers key encryption, not the full profile data still in `api_profiles.ini`.

**Target Design:**
- `api_profiles.ini` deleted; all data migrated into `user/API.ini` `[translation]` and `[glossary]` sections
- `api_config.py` extended to read/write provider profile settings (model, temperature, URL, etc.)
- Keys remain encrypted (Fernet AES-256); non-secret settings stored in plaintext in respective sections
- `api2glossary` section (already in `user/API.ini`) retained for API2Glossary key

**Files to Modify:**
- `functions/api_config.py` — Add `get_profile_setting()`, `set_profile_setting()` for non-secret API settings
- `api_profiles.ini` — Delete (after migration)
- `functions/config.py` — Remove any reads from `api_profiles.ini`; route to `api_config.py`
- `functions/project_config.py` — Update any `api_profiles.ini` reads to use `api_config.py`
- `dev/test_api_providers.py` — Update to use new API.ini structure

**Tests to Add:**
- `test_api_profile_migration` — api_profiles.ini data migrated to API.ini on first load
- `test_api_ini_has_translation_section` — API.ini contains `[translation]` with model/temperature/URL
- `test_api_ini_has_glossary_section` — API.ini contains `[glossary]` with separate profile

---

### TASK 62.4: API Request Prompt Order Alignment

**Status:** ✅ DONE (Session 28) | **Effort:** 2 hours
**Tests:** `dev/test_phase62_prompt.py` — 28 tests, all passing

**Current implementation** (`functions/prompt_builder.py::_construct_system_prompt()`):
```
1. Base prompt template (eroge translator instructions)
2. Context-type instructions (dialogue/menu/choice/unknown)
3. Game summary
4. Output examples
5. Filtered glossary entries + character list
6. Translation style (combined Style+Tone)
7. Narrative perspective (POV)
8. Conditional instructions (pattern-triggered)
```

**Target order** (per canonical design — IMPLEMENTED):
```
1. Language direction header: "# Language\nTranslate from {Source} to {Target}."
2. System Instructions (custom_notes from metadata)
3. Style (# Translation Style Guidelines)
4. Tone (# Translation Tone; separate from Style)
5. Summary (# Game Context)
6. Genre (# Genre)
7. Conditional Prompts (selective: context-type + pattern-triggered + POV)
8. Glossary (selective: content-based + Characters from metadata)
9. Rolling Context (# Rolling Context; preceding translated lines)
10. Input Lines
```

**Implementation Notes:**
- `_build_system_prompt_from_manifest()` now reads ALL data from `step_state.Information.data.metadata` via `mgr.get_step_data_value(3, "metadata", {})`
- `api_client._translate_chunk()` uses the caller's system prompt directly and appends `# Output Format` with JSON instructions
- `ManifestManager.consolidate_project_info()` migrates top-level keys into metadata on load
- `FILTER_PARTS` expanded from 9 to 12 entries (added Language, Genre, Rolling Context)
- Characters from metadata are included as a `# Characters` section after the glossary

**Files to Modify:**
- `functions/prompt_builder.py` — Rewrite `_construct_system_prompt()` to follow exact slot order
- `functions/prompt_builder.py` — Add language direction header (slot 1); separate Style/Tone fields
- `functions/prompt_builder.py` — Move context-type prompt to slot 6 (merged with conditional prompts)
- `functions/prompt_builder.py` — Remove output examples from prompt injection
- `gui/steps/translate.py` — `_build_system_prompt_from_manifest()` must pass separate Style/Tone
- `dev/test_prompt_builder.py` — Update slot order assertions

**Tests to Add:**
- `test_prompt_slot_1_language_direction` — First section is "Translate X into Y"
- `test_prompt_slot_3_style_separate` — Style injected separately from Tone
- `test_prompt_slot_6_conditional_merged` — Context-type and pattern prompts in same slot
- `test_prompt_slot_7_glossary_after_conditional` — Glossary comes after conditionals
- `test_prompt_output_examples_not_in_prompt` — Output examples not in system prompt

---

### Phase 62 — Cross-Reference: After Each Task is Tested

✅ **Session 28 complete.** All 5 doc files updated. Summary of changes:
- **Task 62.1**: `functions/glossary.py` + `gui/steps/information.py` → `globalglossary.tsv` (3-col TSV, migration chain)
- **Task 62.2**: `functions/glossaries/code_glossary_db.py` → `codedatabase.tsv` (9-col TSV, migration from SQLite/CSV/JSON)
- **Task 62.3**: `functions/api_config.py` + `functions/project_config.py` → all API profiles in `user/API.ini` `[translation]`/`[glossary]`; auto-migration from `api_profiles.ini`
- **Task 62.4**: `functions/prompt_builder.py` `_construct_system_prompt()` → 7-slot order: language direction → instructions → style → tone → summary → conditional → glossary; UPDATED: `gui/steps/translate.py` `_build_system_prompt_from_manifest()` → 10-slot order reading from `step_state.Information.data.metadata`: language → instructions → style → tone → summary → genre → conditional → glossary+characters → rolling context → (output format appended by api_client); `FILTER_PARTS` expanded to 12 entries; `api_client._translate_chunk()` uses caller prompt directly; `consolidate_project_info()` added to ManifestManager
- **Dir Init**: `functions/ini_manager.py` `ensure_app_dirs()` called from `_load_ini()` → creates `user/`, `Projects/`, `logs/`, `cache/` on first access
- **Tests**: `test_phase62_glossary.py` (32), `test_phase62_codedb.py` (27), `test_phase62_api.py` (25), `test_phase62_prompt.py` (28), `test_phase62_dirs.py` (17) = **129 new tests**

After each task passes tests, update:
- `doc/features.md` — File format, glossary widget, API settings
- `doc/technical.md` — Module descriptions, DATA FORMATS section, PROJECT STRUCTURE
- `doc/tests.md` — New/updated test file entries
- `doc/specs.md` — 3.1/3.2 file tables (already updated in Session 26 to reflect targets)
- `doc/todo.md` — Mark task complete with session number

=============================================================================

PENDING TASKS - Costs TAB

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
**Priority:** LOW | **Status:** 🔲 DEFERRED | **Effort:** 3 hours

Goal: Implement Refresh button to fetch latest model data from providers.

**Current Issue:**
- Refresh button does nothing
- Model data is static from config.py

**Changes Required:**
- Create `functions/model_data.py` module
- Implement API calls to fetch model info:
  - OpenAI: `/v1/models` endpoint
  - Gemini: Models API
  - Claude: Models API
  - Mistral: Models API
  - Grok: Models API
  - DeepSeek: Models API
- Store fetched data in `models.db` (SQLite)
- Load from database on startup, fallback to config.py
- Refresh button triggers async fetch
- Update Model Comparison table with new data

**Files to Create:**
- `functions/model_data.py` - Model data fetching and storage

**Files to Modify:**
- `gui/steps/costs.py` - Wire Refresh button to fetch
- `functions/config.py` - Add database fallback

**Tests to Add:**
- `dev/test_model_data.py`:
  - Test API fetch (mocked)
  - Test database storage
  - Test fallback to static config

=============================================================================

PENDING TASKS - UI

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

### TASK 17.1: Batch API Support ✅ DONE
**Priority:** HIGH | **Effort:** 8-12 hours | **Status:** COMPLETE

Goal: Support provider batch APIs (often 50% cheaper than real-time)

**Features:**
- Batch mode toggle in Translation step
- Queue requests for batch processing (async, up to 24h turnaround)
- Track batch job status and retrieve results
- Automatic fallback to real-time if batch unavailable

**Limitations:**
- Rolling context in source language only (no translated context mid-batch)
- Results may arrive hours later
- Not all providers support batch mode

**Implementation:**
- Add `batch_mode` option to api_client.py
- Create batch job tracker in functions/batch_tracker.py
- Store pending batch IDs in manifest for retrieval
- GUI: Add "Batch Mode" checkbox with cost savings indicator

---

### TASK 17.2: Multi-Key Management & Auto-Rotation ✅ DONE
**Priority:** HIGH | **Effort:** 10-14 hours | **Status:** COMPLETE

Goal: Manage multiple API keys with automatic rotation on rate limits

**Features:**
- Store multiple API keys per provider (encrypted in config)
- Name/label keys for identification (e.g., "Personal", "Work", "Free Tier")
- Mark keys as active/inactive
- Auto-rotate to next key when:
  - Daily/monthly limit approaching (predictive)
  - Rate limit error received (reactive)
  - Key marked as exhausted for the day

**Key Pool Modes:**
- **Sequential**: Use keys in order until exhausted
- **Even Distribution**: Spread requests across all active keys
- **Priority-Based**: Prefer certain keys, fallback to others
- **Mixed**: Priority with even distribution among same-priority keys

**Implementation:**
- Create `functions/key_manager.py` for key storage and rotation
- Extend `api_client.py` with key pool support
- Add usage tracking per key (requests, tokens, estimated cost)
- GUI: Key Management dialog in Global Options
- Store keys in `user/api_keys.json` (encrypted or OS keyring)

**GUI Components:**
- Key list with name, provider, status (active/inactive/exhausted)
- Add/Edit/Remove key buttons
- Pool mode selector per provider
- Usage stats display (today/month)
- Manual "Mark as Exhausted" / "Reset" buttons

---

### TASK 17.3: Named API Profiles & Configuration ✅ DONE
**Priority:** MEDIUM | **Effort:** 4-6 hours | **Status:** COMPLETE

Goal: Allow naming and organizing API configurations

**Features:**
- Name API profiles (e.g., "Fast Translation", "Quality Check", "Cheap Bulk")
- Associate profiles with specific key pools
- Quick-switch between profiles
- Profile-specific settings (model, temperature, system prompt tweaks)

**Implementation:**
- Extend existing preset system in config.py
- Add profile management UI in Global Options
- Profile selector in Translation step

---

### TASK 17.4: Additional File Format Support ✅ DONE
**Priority:** MEDIUM | **Effort:** 8-10 hours | **Status:** COMPLETE

Goal: Support additional translation file formats

**New Formats:**

1. **.trans files (Translator++)**
   - SQLite database with translation pairs
   - Extract: Read from database tables
   - Inject: Write translations back to database
   - Preserve Translator++ metadata and context

2. **Markdown (.md)**
   - Preserve code blocks (```) as protected
   - Handle inline code (`code`) 
   - Preserve frontmatter (YAML header)
   - Translate text content only
   - Maintain heading structure

3. **Lenient JSON ("bad" JSON)**
   - Parse JSON with trailing commas
   - Handle single quotes instead of double
   - Support unquoted keys
   - Comments in JSON (// and /* */)
   - Use `json5` or custom parser

**Implementation:**
- Add `formats/translator_plus.py` for .trans files
- Add `formats/markdown.py` for .md files  
- Add `formats/json_lenient.py` for bad JSON
- Register handlers in formats/__init__.py
- Add format detection for auto-selection

---

### TASK 17.5: Advanced Usage Analytics & Dynamic Rate Limiting ✅ DONE
**Priority:** HIGH | **Effort:** 12-16 hours | **Status:** COMPLETE

Goal: Comprehensive tracking of API usage and automated rate limit enforcement.

**Features:**
- **Dynamic Provider Metadata:** Fetch prices, context windows, and rate limits from minimal online sources (e.g., provider metadata APIs) rather than hardcoding.
- **Smart Rate Limiting:**
  - Track Requests Per Minute (RPM) and Requests Per Day (RPD).
  - Handle timezone-specific reset times (e.g., OpenAI resets at specific UTC times).
  - Automatically pause/throttle to avoid 429 errors.
- **Granular Usage Database:**
  - Record every request with: Timestamp, Model, Key ID, User Profile, Task Type, Tokens (In/Out), Cost.
  - **Task Types:** API Tests, Glossary Generation, Game Summary, Translation, TLC, Editing.
- **Analytics Dashboard:**
  - View usage by Model, Key, Profile, or Task.
  - Filterable views.
  - Export data to CSV.

**Implementation:**
- Create `functions/usage_tracker.py` (SQLite based).
- Integrate tracking into `api_client.py` and `One_Click_Test.py`.
- Implement `functions/rate_limiter.py` with timezone awareness.

---

### TASK 17.6: Automatic API Key Provisioning (Investigation) ✅ DONE
**Priority:** LOW | **Effort:** 4-6 hours | **Status:** COMPLETE (NOT FEASIBLE)

Goal: Investigate feasibility of automated API key acquisition to lower entry barrier.

**Scope:**
- Research provider APIs for programmatic account/key creation.
- Evaluate "convenience vs. ToS" compliance (avoiding unauthorized automation).
- Explore legitimate "Get Started" flows that can be streamlined within the tool.
- **Constraint:** Must strictly adhere to provider Terms of Service.

**STATUS: INVESTIGATION COMPLETE — NOT FEASIBLE FOR AUTO-PROVISIONING**

**Findings:**

1. **OpenAI** — Has an Admin API (`POST /organization/admin_api_keys`) for creating
   and managing API keys. However, this requires an **existing Admin API key** with
   organization-level privileges. There is no public API for account creation or
   signup. Service accounts can be created per-project, but again require existing
   admin credentials. **Chicken-and-egg problem: you need a key to create a key.**

2. **Anthropic (Claude)** — No Admin API for programmatic key management. Keys are
   managed exclusively through the console UI at `console.anthropic.com`. No
   documented endpoints for key creation, listing, or deletion.

3. **Google (Gemini via Vertex AI / AI Studio)** — Google Cloud offers a full REST
   API for API key management (`apikeys.googleapis.com`): create, list, restrict,
   rotate, delete. However, this requires an existing GCP project and OAuth2 or
   service-account authentication. No way to create GCP accounts programmatically
   without human signup and billing setup.

4. **Other providers (OpenRouter, DeepSeek, Mistral, local models):**
   - OpenRouter: OAuth-based, no programmatic key creation.
   - DeepSeek / Mistral: Manual signup only, no admin APIs.
   - Local models (Ollama, LM Studio): No API keys needed at all.

5. **ToS Compliance** — All major providers explicitly prohibit automated account
   creation. Even where Admin APIs exist (OpenAI, Google), they are designed for
   managing keys within **already-authenticated organizations**, not for onboarding
   new users.

**Recommendation:** Instead of auto-provisioning, implement a "Get Started" helper
in the GUI that:
- Opens the provider's signup page in the default browser.
- Provides step-by-step guidance for key creation.
- Offers a paste-and-validate field for the new key.
- This approach is ToS-compliant and user-friendly.

**Conclusion:** Automated API key provisioning is **not feasible** without violating
provider Terms of Service. The recommended alternative is a guided onboarding
flow within the application.

---

### TASK 17.7: Session Persistence & Auto-Load ✅ DONE
**Priority:** HIGH | **Effort:** 4-6 hours | **Status:** COMPLETE

Goal: Seamless workflow continuation.

**Features:**
- **Auto-Load:** Automatically load the last used manifest and progress state on application launch.
- **Opt-Out:** Configuration option to disable auto-load (start fresh).
- **State Recovery:** Robustly restore GUI state (tabs, selections) from `temp/gui_session_autosave.json`.

**Implementation:**
- Fix `ISSUE: GUI v2 Session Not Loading Automatically`.
- Update `gui/app.py` initialization logic.
- Add "Load Last Session" toggle in Global Options.

---

### TASK 17.8: Agent-Assisted Modes (Ask/Agent LLM Modes) ✅ DONE
**Priority:** LOW | **Effort:** 6-8 hours | **Status:** COMPLETE

Goal: Add an optional "Ask/Agent" feature that exposes multiple specialized agent modes backed by LLM API access. Each mode has its own system instruction, and configurable read/write scopes (toggleable) to control whether the agent may read project documentation, manifests, or write new artifacts (scripts, templates, or manifests).

Features:
- **Mode: Interactive Help** — An assistant configured to act as an interactive help system for CherryAI. It is provided with loaded documentation snippets (`doc/` files, help text) and can answer contextual questions, point to configuration locations, and provide step-by-step guidance for using the tool. Read access to `doc/` and `config/` is toggleable.
- **Mode: Language Assistant** — A language-focused agent that can analyze and suggest language improvements, provide localized guidance, and operate on selected table/cell context. The agent can accept selected table cell content (from the GUI table selection) as context for more precise language suggestions and can optionally write back changed cell suggestions as draft edits (write toggle).
- **Mode: Script Author** — An agent tuned to author new CherryAI scripts (primarily extraction/injection handlers or format plugins). It will be provided developer-facing documentation (function signatures, `formats/` and `functions/` guidelines) and can propose or generate new Python modules/templates. Write access is gated — by default it only returns code suggestions, with an explicit opt-in to write new files into a `dev/sandbox/` area.
- **Mode: Targeted Translation / TLC / Check** — An agent specialized in targeted translation tasks: making translation suggestions, running edit passes, and performing validation/checking. It accepts manifest or selected-line-context and can produce suggested edits or validation reports. Read/write toggles control whether it may alter a manifest or only emit suggestions.

Implementation Notes:
- Add a new `functions/agent_modes.py` module implementing a small mode registry, mode metadata (name, system prompt template, default read/write capabilities), and a safe execution wrapper for API calls. This module should be optional (soft import) so the rest of the app runs without API credentials.
- Extend `functions/api_client.py` with a lightweight `agent_call()` helper that accepts: `mode`, `system_instruction`, `context`, `allowed_reads`, `allow_write` and returns a structured response (content, commands, suggested_files).
- GUI: Add an "Ask/Agent" panel in `gui/steps/` or a new `gui/dialogs/agent_console.py` dialog. The panel should:
   - Let users pick a mode and toggle read/write scopes.
   - Show current context (selected lines, selected table cells, or loaded docs snippets) and allow editing before sending.
   - Display agent responses and, when write is allowed, present a safe preview and an "Apply to Sandbox" button that writes to `dev/sandbox/` only.
- Security: All write operations must be sandboxed by default in `dev/sandbox/` and require explicit user confirmation before writing to production locations (e.g., `formats/`, `functions/`). Keep a clear audit trail in `logs/agent/` with request, mode, context hash, and time.
- Configuration: Add an `agent_modes` section to `CherryAI.ini` with per-mode toggles and a `agent.sandbox_path` option. Provide small presets for `interactive_help`, `language`, `script_author`, `translation_check`.
- The costs for API usage will also be estimated and recorded.

Testing & QA:
- Add `dev/test_agent_modes.py` (script tests) that:
   - Mocks `functions.api_client.agent_call` to verify mode metadata, system prompt templating, and read/write gating.
   - Verifies GUI dialog behavior in headless mode by testing the model selection, toggles default states, and sandbox write preview creation.
- Add integration example: `dev/example_agent_session.md` documenting a safe workflow for using Script Author mode to generate a small `formats/markdown.py` starter in `dev/sandbox/`.

Notes & Constraints:
- This feature is optional and should degrade gracefully when no API credentials exist: the GUI should disable agent modes and present a helpful message.
- Keep system instructions versioned in `doc/agent_prompts/` for auditability and test fixtures.
- Effort estimates assume an incremental, opt-in rollout (UI + functions + small tests). More advanced capabilities (direct code execution, auto-apply to repo) are intentionally out of scope for the low-priority initial implementation.

---

### TASK 17.9: Estimation Step Upgrade (Move & Enhancements) ✅ DONE
**Priority:** MEDIUM | **Effort:** 6-10 hours | **Status:** COMPLETE

Goal: Improve the Estimation step so it runs earlier in the workflow (after Extraction and before Analysis) and provides a configurable LLM inference options panel with a real-time estimated price using the currently selected model and preset.

Motivation:
- Presenting cost and inference options earlier helps users choose models/options before heavy analysis and pre-processing, preventing wasted compute and allowing better control of pipeline cost.

Features:
- Move the Estimation step UI from its current position to appear immediately after `InputExtractionStep` and before `AnalysisStep` in the GUI workflow ordering.
- Provide a panel to toggle inference settings prior to translation/further analysis (analysis will still already run. scripted Analysis will run automatically upon loading a file), including:
   - Batch/chunk options (max tokens | max lines)
   - Rolling context usage toggle
   - Cost-saving toggles (Use local model | batch API)
   - Use API for Summary (Summary Size | Request Size)
   - Use API for Glossary (Only for Uncertain | Full)
   - Use API for Editing and TLC (Set # of: Editing | TLC)
   - Move Deduplication from pre-processing to Estimation
   - Strip and Re-add Quotes from Speaker: "Dialogue" with Script 
   - Everything can be opted out, even Translation
- The Panel will also be the itemized bill with an estimated final, the changed value and final update when the respective option changes.
- The Panel will also have a small API selection  
- Show live estimated price and token counts for the current batch using the selected model/preset and options. Use provider price metadata (from provider modules or cached presets) to compute an estimated cost per request and per-batch total.
- Persist chosen estimation options to session config and include them in `manifests/` so repeated runs use same settings.

Implementation Notes:
- Add `functions/estimation.py` to compute token estimates and cost predictions. Use `functions/api_client` provider metadata (context window, price/1000 tokens) when available, and fall back to `api_presets` defaults.
- Update workflow ordering in `gui/steps/__init__.py` or the place where steps are registered so Estimation appears between Extraction and Analysis. Ensure unit tests referencing step indices are updated or made resilient to insertion.
- Extend `gui/steps/estimate.py` to include an advanced options panel and live price preview. The panel should accept selected presets and update estimates on change.
- CLI: Add `estimate` subcommand or flag to `CherryAI.py` that outputs the same price/token estimate in headless mode.

Testing & QA:
- Add `dev/test_estimation.py` to validate estimation math, fallback defaults, and persistence to manifest.
- Mock provider pricing in tests to assert correct computation of per-line / per-batch costs.
- Ensure GUI tests (headless) can verify the Estimation step appears in the expected position relative to Extraction and Analysis.

Notes & Constraints:
- Estimation uses best-effort pricing metadata; final API billing may differ. Show a clear disclaimer in the UI.
- Moving the step may affect ordering assumptions in some tests; prefer to update tests to look up steps by name instead of fixed indices.

---

### TASK 17.10: Tooltips Restoration & Multi-Language UI ✅ DONE
**Priority:** MEDIUM | **Effort:** 6-12 hours | **Status:** COMPLETE

Goal: Restore and expand UI tooltips (previously present in legacy GUI), and add multi-language support so all UI text is translatable and languages can be selected via Options.

Motivation:
- Many GUI elements lack helpful inline explanations after refactor; restoring tooltips improves discoverability.
- Adding internationalization (i18n) first ensures tooltips and other UI strings can be localized.

Features:
- Consolidate all user-facing UI strings into a single translations directory `user/lang/` or `doc/lang/` with per-language files (e.g., `en.json`, `de.json`). Default language: English (`en`).
- Add language selection to Global Options (`gui/dialogs/global_options.py`) showing human-readable language names (e.g., "English", "Deutsch") rather than codes.
- Restore legacy tooltips and add many more where helpful; tooltips are optional (toggle in Options) and will be hidden when disabled.
- Ensure dynamic GUI elements (tables, step panels, dialogs) retrieve labels and tooltip text via a `functions/i18n.py` helper which loads selected language at runtime and falls back to English for missing keys.
- Provide a small developer guide `doc/i18n.md` describing how to add new languages and translate strings. Users should be encouraged to use the tool to make their own translation.

Implementation Notes:
- Create `functions/i18n.py` with simple loader: load language files (JSON) into a dict and expose `t(key)` function. Support placeholder interpolation with `.format()`.
- Move all hardcoded UI strings in `gui/` to use `functions.i18n.t()`; start by updating common dialogs and `gui/steps/estimate.py`, `gui/steps/input_extract.py`, and `gui/dialogs/global_options.py`.
- Add `user/lang/en.json` with all current English strings extracted; provide `user/lang/example_de.json` as a template.
- Options: add `ui.language` and `ui.tooltips_enabled` to `CherryAI.ini` via `functions/config.py` integration.
- Tooltips: implement a small `gui/helpers/tooltip.py` module to attach/detach tooltips to widgets consistently and respect the `tooltips_enabled` flag.

Testing & QA:
- Add `dev/test_i18n.py` to validate language file loading, fallback behavior, and that `t(key)` returns English for missing keys in other languages.
- Add GUI unit tests verifying that toggling `ui.tooltips_enabled` hides/shows tooltips and that language switching updates visible labels in headless test mode where possible.

Notes & Constraints:
- Start by extracting strings from high-impact UI parts; full coverage can be phased.
- Keep translation files simple JSON key→value maps; avoid pluralization complexity for the initial implementation.

=============================================================================

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

### Preprocessing/Postprocessing Future Enhancements
- **Speaker Name Replacement Rework**: Handle edge cases (speakers with colons in name, multiple dialogue formats, speaker extraction from non-standard patterns)
- **Code Spacing Rules Expansion**: Deeper integration with Code Database, expanded rule definitions, per-pattern spacing tags (visible/invisible, variable handling)
- **Advanced Deduplication Rules**: Pattern-based deduplication using Increase/Decrease equivalence, RPG stat names (Strength/Willpower/Dexterity) as equivalent, database of auto-translations for common patterns
- **Pattern Replacement Mode**: Replace patterns permanently before translation (not restored after)
- **Pattern Removal Mode**: Remove patterns permanently before translation (not restored after)
- **Functions Not Visible in GUI**: Restore additional processing functions that exist in code but lack GUI exposure
- **Context-Aware Deduplication**: Use semantic similarity rather than exact match for deduplication
- **Deduplication Variants Database**: Create database of pattern variants that should be treated as duplicates
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
functions/manifest_fields.py  - Field type helpers for GUI binding
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
| Project Name | `ProjectName` | text | "Project1" | - |
| Title | `Title` | text | "Title1" | prompt |
| Genre | `Genre` | text | "fictional, nonfictional" | prompt |
| Source Language | `SourceLanguage` | text | "Japanese" | api_client |
| Target Language | `TargetLanguage` | text | "English" | api_client |
| Summary | `Summary` | text | "[DEFAULT_SUMMARY_TEXT]" | prompt |
| Style Preset | `StylePreset` | text | "Natural" | prompt |
| Tone Preset | `TonePreset` | text | "Neutral" | prompt |
| Glossary (Characters) | `CharacterNotes` | special | [] | prompt |
| Code Database | `CodeGlossary` | special | [] | prompt |
| Prompt | `Prompt` | text | "[DEFAULT_SYSTEM_INSTRUCTIONS]" | prompt |
| SI Preset | `SIPreset` | text | "Default" | - |
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
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

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

---

### TASK 58.3: Project Name Dialog Enhancement
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Resize Create New Translation Project dialog to show all buttons.
Remove auto-suggestion for project name - field starts empty.

**Files to Modify:**
- `gui/dialogs/project_dialog.py` - Resize window, clear name field

**Tests to Add:**
- `dev/test_project_dialog.py`:
  - `test_dialog_minimum_size`
  - `test_name_field_empty_on_open`

---

### TASK 58.4: Automatic Pipeline Orchestrator
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Implement the 8-step automatic pipeline that executes on file load.

**Pipeline Steps:**
1. Create Manifest (Project Name Dialog)
2. Load Lines (extract from files)
3. Load Defaults (apply defaults.ini)
4. Run Analysis (functions/analysis.py)
5. Populate Inferences (optional, based on settings)
6. Run Original Estimation
7. Run Default Preprocessing
8. Run Preprocessed Estimation

**Files to Create:**
- `functions/auto_pipeline.py` - Pipeline orchestrator

**Files to Modify:**
- `gui/steps/input.py` - Trigger pipeline after load
- `gui/helpers/analysis_adapter.py` - Support programmatic run

**Tests to Add:**
- `dev/test_auto_pipeline.py`:
  - `test_pipeline_step_sequence`
  - `test_pipeline_skip_existing_manifest`
  - `test_pipeline_level_cutoff`
  - `test_pipeline_error_handling`

---

### TASK 58.5: Inference Population
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement optional inference population from analysis results.

**Inference Options:**
- `infer_speakers_to_glossary`: Add detected speakers to Glossary
- `infer_codes_to_database`: Add code patterns to Code Database
- `infer_pov`: Detect Point of View
- `infer_gender`: Use LLM to infer character gender

**Files to Modify:**
- `functions/auto_pipeline.py` - Inference step
- `functions/glossary.py` - Add entries from analysis
- `functions/options.py` - Add inference option fields

**Tests to Add:**
- `dev/test_inference.py`:
  - `test_speakers_to_glossary`
  - `test_codes_to_database`
  - `test_pov_detection`
  - `test_all_inference_disabled`

---

### TASK 58.6: Mock Translation Level
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Extend pipeline to Level 4 with mock translation and full validation.

**Additional Steps:**
9. Mock Translation (no API calls)
10. Run QA Validation
11. Run Postprocessing
12. Summary display

**Files to Modify:**
- `functions/auto_pipeline.py` - Level 4 extension
- `functions/mock_translation.py` - Mock engine integration

**Tests to Add:**
- `dev/test_auto_pipeline.py`:
  - `test_mock_translation_level`
  - `test_mock_pipeline_complete`
  - `test_mock_validation_runs`

---

### TASK 58.7: File Tree Improvements
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Improve Loaded Files Panel tree behavior.

**Requirements:**
- Folders always appear above files in same directory
- Tree collapsed by default on load
- Context menu: Remove Selected, Select All, Expand All, Collapse All

**Files to Modify:**
- `gui/steps/input.py` - Tree sorting and collapse behavior

**Tests to Add:**
- `dev/test_file_tree.py`:
  - `test_folders_above_files`
  - `test_collapsed_by_default`

---

### TASK 58.8: Manifest Pipeline Recording
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Record pipeline execution details in manifest for tracking.

**Manifest Fields:**
- `step_state.Input.pipeline_executed.level`
- `step_state.Input.pipeline_executed.steps_completed`
- `step_state.Input.pipeline_executed.execution_time_ms`

**Files to Modify:**
- `functions/auto_pipeline.py` - Write execution record
- `functions/manifest_manager.py` - Add pipeline state fields

**Tests to Add:**
- `dev/test_auto_pipeline.py`:
  - `test_pipeline_recording`
  - `test_execution_time_recorded`

---

### TASK 58.11: Manifest Loading & Startup Fixes
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix manifest lines not loading from resume, add auto-load checkbox to 
WelcomeDialog, sync GlobalOptions with startup setting, order manifest list
by date, and fix dictionary iteration error during autosave.

**Fixes Implemented:**
1. **Manifest Lines Not Loading:** When loading manifest via App menu or WelcomeDialog 
   Resume, lines now populate correctly in InputExtractionStep via `_populate_from_manifest()`
2. **Auto-Load Checkbox:** WelcomeDialog shows "Automatically load last project on startup"
   checkbox (always visible, not conditional on Resume availability), persisted via `set_load_last()`.
   Loads current INI setting on display; saves immediately on toggle (updated Phase 60).
3. **GlobalOptions Sync:** `load_last` in GlobalOptions now reads from and writes
   to `[session]` section to match startup behavior
4. **Manifest List Sorting:** LoadManifestDialog sorts manifests by modification date 
   (latest first) instead of alphabetically
5. **Dictionary Iteration Error:** ManifestManager.save() now uses deepcopy to prevent
   "dictionary changed size during iteration" error during autosave

**Files Modified:**
- `gui/steps/input_extract.py` - Added manifest data check in `on_enter()`
- `gui/app.py` - Added explicit `on_enter()` call after manifest load
- `gui/dialogs/project_dialog.py` - Added auto-load checkbox, sorted manifest list
- `gui/dialogs/global_options.py` - Sync load_last with [session] section
- `functions/manifest_manager.py` - Use deepcopy in save() method

**Tests to Add:**
- `dev/test_app_startup.py`:
  - `test_manifest_lines_load_on_resume`
  - `test_auto_load_checkbox_saves_setting`
  - `test_manifest_list_sorted_by_date`
  - `test_global_options_syncs_restore_setting`
- `dev/test_manifest_manager.py`:
  - `test_save_concurrent_modification_safe`

---

### TASK 58.12: Input Dialog UX Improvements
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Improve UnifiedInputDialog to remember last directory and integrate 
project name input to reduce dialog steps for new projects.

**Features Implemented:**
1. **Last Directory Persistence:** UnifiedInputDialog remembers the last used 
   input directory across sessions, stored in `[session].last_input_dir`
2. **Project Name Field Integration:** When creating a new project (no manifest 
   loaded), the dialog shows a "Project Name" field in the Options panel, 
   eliminating the separate ProjectNameDialog

**Files Modified:**
- `functions/ini_manager.py` - Added `get_last_input_dir()` and `set_last_input_dir()`
- `gui/dialogs/input_dialog.py` - Added `show_project_name` parameter, project name 
  field in options panel, last directory integration
- `gui/steps/input_extract.py` - Updated to use new dialog parameters and bypass 
  ProjectNameDialog when project name provided via dialog

**Test Files Created:**
- `dev/test_game/` - Comprehensive test game files for feature testing:
  - test_dialogue.txt - Speaker:Dialogue format, quotes, rolling context (uses __DIALOGUE__ markers)
  - test_code_patterns.txt - Code protection, placeholders, anchoring (uses __FILE__ markers)
  - test_deduplication.txt - Duplicate handling, aggressive dedup (uses __FILE__ markers)
  - test_menu_choice.txt - Context markers (__MENU__, __CHOICE__, __DIALOGUE__)
  - test_pov.txt - Point of view inference, pronouns
  - test_wordwrap.txt - Overflow, line length, width calculation (uses __FILE__ markers)
  - test_glossary.txt - Term matching, consistency, character names (uses __FILE__, __DIALOGUE__)
  - test_edge_cases.txt - Unicode, empty lines, special characters (uses __FILE__ markers)
  - TEST_GAME_GUIDE.md - Documentation of test file coverage
  - All files use __COMMENT__ for inline annotations (not # comments)
  - Context markers: __DIALOGUE__, __MENU__, __CHOICE__, __FILE__

- `dev/test_game_pipeline.py` - 133 tests validating manifest creation, __COMMENT__/marker system, preprocessing pipeline (dedup, protect code, standard helpers), request building (build_line_infos, build_requests, PromptBuilder), mock translation with flaw injection, postprocessing recovery, wordwrap (smart_wrap, pretty_wrap, apply_wordwrap, normalize_break_char, ignore codes, fixture data), game update detection (change detection, comparison results, update manifest generation), and import translations (idx-based merge, content-based import, full workflow)

**Tests to Add:**
- `dev/test_input_dialog.py`:
  - `test_last_dir_remembered`
  - `test_project_name_field_shown_when_no_manifest`
  - `test_project_name_validated`
  - `test_result_tuple_includes_project_name`

=============================================================================

PHASE 59: ANALYSIS ENHANCEMENT (Step 1 Enhancement)
----------------------------------------------------

**Status:** 🔲 PLANNED | **Effort:** 14-18 hours | **Priority:** HIGH

Goal: Enhance Analysis step with project-level language detection and actionable 
contextual controls. Add category-aware right-click functionality to the existing
Findings Table that allows direct population of Glossary and Code Database based
on whether the selected rows are Speakers or Code Patterns.

**Key Changes from Original Design:**
- Language detection is PROJECT-LEVEL, not per-line
- Japanese has unique kana (hiragana/katakana); Chinese does not
- Korean is separate and excluded from Japanese/Chinese threshold
- Existing Findings Table is ENHANCED, not replaced with separate tables
- Right-click menu is category-aware (different options for Speaker vs Code Pattern)

**Reference:** See `doc/specs.md` Section 2.2 → Step 1: Analysis for full spec.

### TASK 59.1: Project-Level Language Detection
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement project-level Japanese/Chinese classification using the 30%
threshold rule. Japanese has unique kana (hiragana/katakana); Chinese does not.

**Classification Logic:**
1. Identify all lines containing CJK characters
2. Classify each CJK line:
   - Japanese: Contains ANY hiragana or katakana (regardless of kanji)
   - Chinese-only: Contains CJK but NO hiragana or katakana
   - Korean: Contains Hangul only (handled separately)
3. Calculate: chinese_percentage = chinese_only_lines / total_cjk_lines
4. If chinese_percentage < 0.30 → project dominant_language = "Japanese"
5. Store threshold_applied = True if any Chinese-only reclassified

**Key Point:** This is PROJECT-LEVEL, not per-line classification.

**Files to Modify:**
- `functions/analysis.py` - Add project-level language detection
  - `is_hiragana_or_katakana(char)` - Check for Japanese kana
  - `classify_cjk_line(line)` - Returns 'japanese', 'chinese_only', 'korean', or None
  - `detect_project_language(lines)` - Apply threshold, return dominant language

**Manifest Fields:**
- `Analysis.dominant_language` - "Japanese", "Chinese", or "Unknown"
- `Analysis.threshold_applied` - Whether reclassification occurred
- `Analysis.chinese_percentage` - Percentage before threshold
- `Analysis.japanese_lines` - Lines with kana
- `Analysis.chinese_only_lines` - Lines with CJK but no kana
- `Analysis.korean_lines` - Lines with Hangul only

**Translation Step Integration:**
- When `skip_non_source_language` is enabled:
  - If dominant_language is "Japanese" and threshold_applied:
    - Do NOT skip Chinese-only lines (they're part of Japanese project)

**Tests to Add:**
- `dev/test_analysis.py`:
  - `test_japanese_line_has_kana`
  - `test_chinese_only_line_no_kana`
  - `test_korean_line_excluded_from_threshold`
  - `test_project_below_threshold_is_japanese`
  - `test_project_above_threshold_is_chinese`
  - `test_threshold_applied_flag`
  - `test_mixed_project_classification`

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
- Preserve / Remove / Translate (persisted to Code Database)
- Replace → (Generic | Custom Input)
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
- `dev/test_analysis_findings.py` - Persistence logic, protagonist names, type mapping

---

### TASK 59.6: LLM Speaker Inference
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Implement "Add to Glossary with Inference" LLM call for speakers.

**Workflow:**
1. Send speaker name to LLM with inference prompt
2. Parse response for English translation/romanization
3. Create glossary entry with suggested translation
4. Mark entry with `source: "analysis_inference"`

**Files to Modify:**
- `gui/helpers/analysis_adapter.py` - LLM inference call
- `functions/api_client.py` - Inference request support

**Tests to Add:**
- `dev/test_analysis_actions.py`:
  - `test_speaker_inference_success`
  - `test_speaker_inference_fallback`

---

### TASK 59.7: Ignore Pattern Storage
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Store ignored patterns in manifest and filter from future analysis.

**Storage:**
- `Analysis.ignored_patterns[]` in manifest
- Patterns in this list are excluded from Code Patterns table

**Files to Modify:**
- `functions/analysis.py` - Filter ignored patterns
- `functions/manifest_manager.py` - Ignored patterns field

**Tests to Add:**
- `dev/test_analysis.py`:
  - `test_ignored_pattern_filtered`
  - `test_ignore_pattern_persists`

=============================================================================

PHASE 60: UX POLISH & PRESET REWORK (Information Step Enhancement)
-------------------------------------------------------------------

**Status:** ✅ COMPLETE | **Effort:** 10 hours | **Priority:** HIGH

Goal: Improve usability of Information step with preset management, mass
operations, progress feedback, confirmation opt-out, and File menu fixes.

### TASK 60.1: Gender Inference Progress Bar
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

- Added progress dialog during `_infer_character_genders()` with:
  - "Checking 'name'" label, progress bar, and "X / Y" count
  - Pre-filters characters needing checking for accurate progress
- Prevents appearance of freezing during inference

### TASK 60.2: Speaker Mass Removal
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 min

- Changed char_tree `selectmode` from "browse" to "extended"
- Rewrote `_remove_character()` to handle multiple selections with reverse-index deletion

### TASK 60.3: Style/Tone Preset Rework
**Priority:** HIGH | **Status:** ✅ COMPLETE (migrated to INI 2026) | **Effort:** 4 hours

- Replaced enum-based system with string-based preset management:
  - `_BUILTIN_STYLE_DEFAULTS` / `_BUILTIN_TONE_DEFAULTS`: 7+8 built-in presets in `ini_manager.py`
  - ~~User presets stored in `user/presets/style_presets.json` and `tone_presets.json`~~
  - **2026 Update:** User presets stored in `user/CherryAI.ini` under `[style]`/`[tone]` sections
    via `ini_manager.set_preset_text()` / `ini_manager.delete_preset()` / `ini_manager.get_all_presets()`
  - JSON preset files deleted; `user/presets/` now only holds system instruction presets
  - Cases preserved thanks to `optionxform = str` in `_load_ini()`
  - Dropdown (combobox) + ScrolledText prompt field + Save/Delete buttons
  - "Custom" preset always available, cannot be overwritten or deleted
  - `_unique_preset_name()` auto-appends numbers for duplicate names
- ProjectMetadata changed: `style_preset: str = "Natural"`, `tone_preset: str = "Neutral"`

### TASK 60.4: Code Database Auto-Populate
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 30 min

- `_auto_import_code_patterns()` now prefers `individual_codes` (per-code detail) over grouped `code_patterns`

### TASK 60.5: Code Database Mass Removal
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 30 min

- Added `selectmode="extended"` to code_tree
- Rewrote `_remove_code_pattern()` for multi-select with reverse-index batch deletion

### TASK 60.6: File → New Project
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 min

- `_on_new_session()` now calls `on_enter()` on tab 0 after reset, sets `_current_tab_index = 0`
- Ensures window is fully cleared when starting a new project

### TASK 60.7: File → Open Project
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 min

- `_on_load_manifest()` checks for unsaved changes (askyesnocancel) before loading a different project

### TASK 60.8: Welcome Dialog Auto-Load Checkbox
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 30 min

- Auto-load checkbox now always visible (not conditional on Resume availability)
- Loads current INI setting on display; saves immediately on toggle via `_on_auto_load_toggled()`

### TASK 60.9: Confirmation Dialog Opt-Out
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Created `gui/helpers/confirmations.py`:
  - `confirm_action(parent, key, title, message)`: custom Toplevel with "Don't ask again" checkbox
  - `is_suppressed(key)` / `suppress(key)`: INI `[confirmations]` section
  - `reset_all_suppressions()`: removes entire `[confirmations]` section
- Added `remove_section(section)` to `functions/ini_manager.py`
- Applied to: character removal, code pattern removal, preset deletion
- Global Options → Session: "Reset All Confirmation Dialogs" and "Reset Style & Tone Presets" buttons

**Files Modified:**
- `gui/steps/information.py` - Tasks 60.1-60.5, 60.9 (progress bar, mass removal, preset system, confirmations)
- `gui/app.py` - Tasks 60.6-60.7 (New/Open project fixes)
- `gui/dialogs/project_dialog.py` - Task 60.8 (auto-load tickbox)
- `gui/dialogs/global_options.py` - Task 60.9 (reset buttons)
- `gui/helpers/confirmations.py` - Task 60.9 (NEW FILE)
- `functions/ini_manager.py` - Task 60.9 (remove_section method)
- `dev/test_gui_v2.py` - Task 60.3 (metadata defaults, custom values)
- `dev/test_information_manifest.py` - Task 60.3 (preset tests updated to capitalized names)
- `dev/test_information_step_phase41.py` - Task 60.3 (TestStyleTonePresets replacing TestStyleToneGraying)

=============================================================================

COMPLETED - INFORMATION STEP UI IMPROVEMENTS
---------------------------------------------

### Style/Tone Text Display Fix
**Status:** ✅ DONE

- `_ensure_style_tone_text()` method added: populates ScrolledText from preset when empty on step entry
- `_populate_form()` falls back to preset text when metadata style/tone is empty
- Called at end of `on_enter()` after all loading completes

### Style/Tone Delete Button Width
**Status:** ✅ DONE

- Delete button width increased from 8 to 10 to prevent emoji/text clipping

### Style/Tone Single-Line Height
**Status:** ✅ DONE

- ScrolledText height reduced from 3 to 1 for compact display

### Collapsible Right-Column Widgets
**Status:** ✅ DONE

- Glossary, Glossary Settings, Code Database, Global Database each have Collapse/Display toggle
- `_collapsible_state`, `_collapsible_content`, `_collapsible_buttons` dicts track state
- `_toggle_collapsible(widget_name)` uses `grid_remove()`/`grid()` for show/hide
- `_reconfigure_right_column_weights()` sets weight=1 for expanded, weight=0 for collapsed

### Glossary Moved to Right Column
**Status:** ✅ DONE

- `_build_character_section()` builds into `self._right_column` (grid row 0) instead of `self._left_column`
- Groups all table-based widgets together: Glossary (row 0), Glossary Settings (row 1), Code Database (row 2), Global Database (row 3)

### Taller Tables with Viewport Fill
**Status:** ✅ DONE

- All right-column Treeview widgets use height=8 (up from 4-5)
- Grid layout with `sticky="nsew"` and parent `rowconfigure(weight=1)` for expansion
- Canvas `<Configure>` binding stretches inner frame to viewport height
- When CherryAI window is maximized and other widgets collapsed, tables fill available space without needing to scroll

**Files Modified:**
- `gui/steps/information.py` - All 6 UI improvements
- `doc/features.md` - Updated Style & Tone, Glossary, UI Enhancements sections
- `doc/technical.md` - Updated Phase 41 Integration section
- `doc/tests.md` - Updated test count (56→57), added collapsible test coverage notes
- `doc/specs.md` - Updated Step 3 spec (layout, collapsible, style/tone, known issues)

=============================================================================

TYPE SAFETY & CODE CLEANLINESS ROADMAP
--------------------------------------

Goal: Achieve 100% mypy type safety and code cleanliness across all modules.

Principles:
- All core modules must be fully type-annotated (functions/, modi/, formats/, gui/)
- No mypy errors or warnings (run with --check-untyped-defs)
- All external dependencies must have type stubs (install types- packages as needed)
- Prefer absolute imports; avoid circular dependencies
- All dataclasses, function signatures, and class attributes must be annotated
- Add/extend tests to cover type edge cases

Prioritized Cleanup Plan:
1. **functions/** (core logic, highest impact)
   - options.py, api_client.py, config.py, glossary.py, chunker.py, etc.
   - Add/verify type hints, fix mypy errors, add/extend tests
2. **modi/** (processing modes)
   - Annotate all mode plugins, ensure shared interfaces are typed
3. **formats/** (file I/O)
   - Annotate all format handlers, especially new/complex ones
4. **gui/helpers/** and **gui/steps/** (UI adapters, workflow tabs)
   - Annotate all dataclasses, event handlers, and state objects
5. **dev/** (test utilities)
   - Annotate test helpers, fixtures, and test data classes
6. **CherryAI.py** and CLI entry points
   - Annotate main entry, CLI args, and config loading

Process:
- [ ] Run mypy on each module/folder, fix all errors
- [ ] Add missing type hints and stubs
- [ ] Refactor ambiguous or unsafe code
- [ ] Add/extend tests for type edge cases
- [ ] Document any unavoidable type ignores (with justification)

Status Tracking:
- [ ] All functions/ modules type clean
- [ ] All modi/ modules type clean
- [ ] All formats/ modules type clean
- [ ] All gui/ modules type clean
- [ ] All dev/ test helpers type clean
- [ ] All CLI/entry points type clean

**Type safety and code cleanliness are CRITICAL and must be addressed before new features.**

Last updated: February 2026

=============================================================================

COMPLETED - INFORMATION STEP FUNCTIONAL ENHANCEMENTS (Post Phase 60)
----------------------------------------------------------------------

### Style/Tone Translation Integration
**Status:** ✅ DONE

- translate.py `_build_system_prompt_from_manifest()` reads `CustomStyle`, `CustomTone`, `Summary`, `Prompt`, and glossary from manifest
- Replaces legacy config file reads (`config/translation_style.txt`, `config/game_summary.txt`)
- Style/Tone appended as `Style: ...` and `Tone: ...` lines in system prompt
- `_load_prompt_data()` now reads from manifest first, falls back to config files

### Summary Widget Enhancements
**Status:** ✅ DONE

- Height reduced from 5 to 2 rows
- `DEFAULT_SUMMARY_TEXT` constant added
- "🔄 Restore Default" button resets text to default
- `_ensure_default_texts()` populates with default when empty on step entry
- Hint label (description) removed

### System Instructions Preset System
**Status:** ✅ DONE

- Preset dropdown: Default / Custom / user-saved presets (mirrors Style/Tone pattern)
- `DEFAULT_SYSTEM_INSTRUCTIONS` loaded from `default/example.txt` at import time
- `_SI_PRESETS_FILE` = `user/presets/system_instructions_presets.json`
- Save/Delete buttons for managing user presets
- `_on_si_preset_changed()`, `_save_si_preset()`, `_delete_si_preset()` methods
- Manifest keys: `Prompt` (text), `SIPreset` (preset name)
- Hint label (description) removed

### Project Name Source Fix
**Status:** ✅ DONE

- `_apply_suggested_project_name()` now prefers manifest `ProjectName` (set during Input step) over step data `suggested_project_name` (folder name)

### Analysis→Glossary Character Data
**Status:** ✅ DONE

- `_show_nameable_dialog._apply()` in analysis.py now creates glossary entry when assigning variable codes to characters
- Glossary entry: source=replacement_name, notes="Gender: X; Role: Y; custom_notes"
- Uses `save_glossary_entries` / `load_glossary_entries` from manifest_fields

**Files Modified:**
- `gui/steps/information.py` - Default texts, summary restore, SI presets, hint removal, project name fix
- `gui/steps/translate.py` - `_build_system_prompt_from_manifest()`, manifest-first prompt loading
- `gui/steps/analysis.py` - Glossary entry creation in nameable dialog
- `doc/specs.md` - Updated Summary, Style/Tone, System Instructions widget specs
- `doc/features.md` - Updated Game Summary, Translation Style, added System Instructions
- `doc/technical.md` - Added SIPreset binding, new Phase 41+ integration notes
- `doc/tests.md` - Added Phase 41+ coverage table, updated binding count note
- `doc/todo.md` - Marked SI presets done, added SIPreset to manifest table

=============================================================================

COMPLETED - 2026 USER-FOLDER & SECURITY OVERHAUL
--------------------------------------------------

### User Folder Overhaul
**Status:** ✅ DONE

- CherryAI.ini moved to `user/CherryAI.ini` (auto-migrated from root on first run)
- `glossary.csv` renamed to `GlobalGlossary.csv` (auto-migrated by `_unified_glossary_path()`)
- `codeglossary.csv` replaced by `codeglossary.db` (SQLite, WAL mode, auto-migrated)
- `user/presets/style_presets.json` and `tone_presets.json` DELETED (presets moved to INI)
- New `[style]`/`[tone]`/`[defaults]`/`[manifest_defaults]` sections added to CherryAI.ini
- Old `[api_presets]`/`[project]`/`[translation]` sections REMOVED from CherryAI.ini
- `_REQUIRED_SECTIONS` in ini_manager ensures sections always survive partial saves

**Files Modified/Created:**
- `functions/ini_manager.py` - `_REQUIRED_SECTIONS`, `_ensure_required_sections()`, `_load_ini()` fix
- `functions/glossary.py` - GlobalGlossary.csv path + auto-migration; codeglossary.db path
- `functions/glossaries/code_glossary_db.py` (NEW) - SQLite persistence layer
- `functions/glossaries/code_glossary_functions.py` - Uses SQLite instead of CSV
- `gui/steps/information.py` - INI-based presets; ini_manager import; label update
- `gui/app.py` - `set_last_manifest()` called on manifest load; `load_last = true`
- `user/CherryAI.ini` - Restructured with all 13 required sections
- `user/GlobalGlossary.csv` (MIGRATED from glossary.csv)
- `user/codeglossary.db` (MIGRATED from codeglossary.csv)

### Encrypted API.ini
**Status:** ✅ DONE

- All API secrets and presets moved from CherryAI.ini to `user/API.ini`
- `functions/api_config.py` (NEW):
  - `set_password()` / `verify_password()` — bcrypt WF-10 + 100 ms brute-force trap
  - `set_api_key()` / `get_api_key()` — PBKDF2-SHA256 (390k iter.) + Fernet AES-256
  - `change_password()` — re-encrypts all keys atomically
  - `is_password_set()` — checks for bcrypt hash in [security]
  - `migrate_from_ini()` — one-time migration from old CherryAI.ini
  - `PasswordStrength.assess()` — HiveSystems 2025 tier assessment
- `user/API.ini` (NEW) — created by migrate_from_ini()
- See doc/passwords.md for full technical documentation

### Password Strength UI
**Status:** ✅ DONE

- `gui/widgets/password_strength.py` (NEW) — PasswordStrengthWidget (ttk.Frame):
  - Entry with "Show" toggle, real-time coloured strength block + tier text
  - on_change callback, strength_var/colour_var StringVars
- `gui/dialogs/password_dialog.py` (NEW) — SetPasswordDialog, ChangePasswordDialog, VerifyPasswordDialog
- `gui/dialogs/global_options.py` — Added OptionSection.SECURITY (9th section) with:
  - Password status + Set/Change buttons
  - In-situ PasswordStrengthWidget tester
  - HiveSystems tier legend with coloured swatches
  - Technical info + link to doc/passwords.md
- `dev/test_gui_v2.py` — Updated OptionSection count assertions (8 → 9)

### Documentation
**Status:** ✅ DONE

- `doc/passwords.md` (NEW) — Full password system documentation
- `doc/features.md` — Updated module counts, Security section, style presets note
- `doc/technical.md` — Updated directory tree, new module entries, glossary/INI sections
- `doc/tests.md` — Updated test count
- `doc/todo.md` — This section

=============================================================================
### INI Section Seeding & Preset Migration
**Status:** ✅ DONE

- `_BUILTIN_SYSTEM_INSTRUCTION` in `ini_manager.py` updated with full text including Output Examples section (with Japanese dialogue example and `Hey.` translation).
- `_seed_builtin_sections(config)` (NEW) added to `ini_manager.py`:
  - Seeds `[style]` with all 7 built-in style preset texts on first run
  - Seeds `[tone]` with all 8 built-in tone preset texts on first run
  - Seeds `[system_instructions].Default` with full built-in SI text
  - Seeds `[defaults].{default_style, default_tone, Summary, SystemInstruction}` keys
  - Seeds `[session].last_manifest = ` placeholder key
  - Never overwrites existing user values; returns True if anything written
- `_load_ini()` now calls `_seed_builtin_sections()` after `_populate_from_defaults()`
- `[session].last_manifest = ` added to `_FACTORY_DEFAULTS_INI_TEXT` as documented placeholder
- `gui/app.py` `create_new_project()` fixed: now calls `ini_manager.set_last_manifest()` and `ini_manager.add_to_recent_manifests()` after manifest creation (bug: `load_last = true` never worked for newly-created projects)
- `gui/steps/information.py` SI preset handling fully migrated from JSON to INI:
  - `_load_si_presets()` now returns `ini_manager.get_all_si_presets()` directly; migrates legacy JSON file once via rename to `.json.migrated`
  - `_save_si_preset()` uses `ini_manager.set_si_preset(name, text)` instead of `_save_si_presets_to_file()`
  - `_delete_si_preset()` uses `ini_manager.delete_si_preset(name)` instead of `_save_si_presets_to_file()`
  - `_ensure_default_texts()` uses `ini_manager.get_default_text()` fresh reads instead of stale module-level constants
- `gui/dialogs/global_options.py` broken reset methods fixed:
  - `_on_reset_presets()`: removed broken import of non-existent `_STYLE_PRESETS_FILE` etc.; now uses `ini_manager.restore_preset_defaults("style")` + `ini_manager.restore_preset_defaults("tone")` + `ini_manager.reload_ini()`
  - `_apply()` in `_on_restore_defaults()`: replaced `ini_manager._get_config()` (non-existent) with `ini_manager.remove_section("system_instructions")` + `ini_manager.reload_ini()`
- `dev/test_ini_sections.py` (NEW): 38 tests covering all seeding behaviour, SI preset CRUD, session last_manifest, and confirmations section
- **Documentation:** Updated `doc/features.md` (preset storage: INI not JSON), `doc/technical.md` (INI Population section; `_seed_builtin_sections()` entry), `doc/tests.md` (+38 tests)

**Files Modified:**
- `functions/ini_manager.py` — `_seed_builtin_sections()` (NEW), updated `_BUILTIN_SYSTEM_INSTRUCTION`, updated `_load_ini()`, updated `_FACTORY_DEFAULTS_INI_TEXT [session]`
- `gui/app.py` — `create_new_project()` calls `set_last_manifest()` + `add_to_recent_manifests()`
- `gui/steps/information.py` — SI presets: JSON → INI; `_ensure_default_texts()` fresh reads
- `gui/dialogs/global_options.py` — `_on_reset_presets()` and `_on_restore_defaults._apply()` fixed
- `dev/test_ini_sections.py` (NEW) — 38 passing tests
- `doc/features.md`, `doc/technical.md`, `doc/tests.md`, `doc/todo.md`

---

### Session 29: SystemInstruction Preset Name + Dropdown Live-Update ✅ DONE

**Changes made:**

- `functions/ini_manager.py`:
  - `_seed_builtin_sections()`: `[defaults].SystemInstruction` now seeded as `"Default"` (preset name reference)
    not the full ~2 KB prompt text — consistent with `default_style = Natural` and `default_tone = Neutral`.
    Per-key seeding of [style]/[tone] so built-in keys are added even when section is non-empty.
    Migration: if [defaults].SystemInstruction already contains newlines (legacy full text), replaces with `"Default"`.
  - `_migrate_preset_values()` (NEW): detects and corrects mis-assigned built-in preset values
    (e.g. Dramatic/Dark/Action tone presets stored with Neutral's text). Preserves genuine user edits.
    Called by `_load_ini()` before `_seed_builtin_sections()`.
  - `get_default_text("SystemInstruction")`: if stored value is short/no-newlines, treats it as a
    preset name and resolves via `get_si_preset(val)`; multi-line value returned as-is for backward compat.

- `gui/steps/information.py`:
  - `_on_style_changed()` / `_on_tone_changed()`: read fresh from `ini_manager.get_all_presets()` instead
    of stale `self._style_presets` / `self._tone_presets` dict. Custom preset clears the field.
  - `_on_si_preset_changed()`: reads via `ini_manager.get_si_preset(name)` directly instead of stale dict.
  - `_ensure_style_tone_text()`: **always** overwrites text fields for named presets from INI (removed
    "only if empty" guard that prevented stale manifest content from being updated).
  - `on_enter()`: refreshes `self._style_presets`, `self._tone_presets`, `self._si_presets` and combobox
    `values` from INI at the top of the method so all handlers have current data.

- `dev/test_ini_sections.py`: +18 new tests, total 56 passing.
  - `TestSeedSystemInstructionPresetName` — seed stores "Default" not full text
  - `TestSystemInstructionMigration` — full-text migrated to preset name; `get_default_text` resolves names
  - `TestPresetMigration` — mis-assigned builtin presets corrected by `_migrate_preset_values`
  - `TestPresetDropdownBehavior` — `get_all_presets` returns correct per-preset text after INI edit

- **Documentation:** Updated `doc/technical.md` (`_seed_builtin_sections()` + new `_migrate_preset_values()` entry; `get_default_text` note), `doc/tests.md` (count 38 → 56)

**Files Modified:**
- `functions/ini_manager.py` — `_seed_builtin_sections()`, `_migrate_preset_values()` (NEW), `get_default_text()`, `_load_ini()`
- `gui/steps/information.py` — `_on_style_changed()`, `_on_tone_changed()`, `_on_si_preset_changed()`, `_ensure_style_tone_text()`, `on_enter()`
- `dev/test_ini_sections.py` — +18 tests (56 total)
- `doc/technical.md`, `doc/tests.md`, `doc/todo.md`

=============================================================================

### DYNAMIC MODEL REGISTRY
**Priority:** COMPLETE | **Status:** ✅ DONE

**Goal:** Replace all hardcoded cloud provider/model/pricing data with a dynamic fetch system.

**Implemented:**
- `functions/model_registry.py` — NEW module: `ModelInfo` dataclass (25+ fields), `FALLBACK_MODELS` (23 models across 3 providers), `save_to_ini()` / `load_from_ini()` for `user/API.ini`, `refresh_models()` for live API fetch, `get_pricing_dict()` backward-compat helper, `get_registry_summary()`
- `functions/config.py` — `MODEL_PRICING` is now `_ModelPricingProxy` (lazy-loads from registry; all existing callers unchanged)
- `functions/options.py` — `API_PROVIDERS` is now `_APIProvidersProxy` (cloud model lists from registry; static providers unchanged); added `reload_api_providers()`
- `gui/dialogs/global_options.py` — "⟳ Refresh Models" button; `_update_model_list()` uses registry; `_on_refresh_models()` background thread
- `gui/steps/translate.py` — `MODEL_OPTIONS` updated to Feb 2026 models; `_update_model_list_from_global_options()` uses registry fallback
- `dev/test_model_registry.py` — 83 tests (79 pass + 4 skipped live API tests)
- `dev/test_costs_step_phase40.py` — updated 2 tests for removed legacy models

**Test results:** 194 passed, 4 skipped (live tests require `CHERRYAI_TEST_LIVE=1`)

**To enable live API fetching:**
```
set CHERRYAI_TEST_LIVE=1
set OPENAI_API_KEY=sk-...
set GOOGLE_API_KEY=...
set MISTRAL_API_KEY=...
python -m pytest dev/test_model_registry.py::TestLiveFetch -v
```

=============================================================================

### API KEY MANAGEMENT & CONNECTION TESTING
**Priority:** COMPLETE | **Status:** ✅ DONE

**Goal:** Full pipeline for saving/loading/encrypting API keys in `API.ini`, real connection testing, plaintext key mode, password disable/reset, per-model translation testing.

**Implemented:**
- `functions/api_config.py` — Extended:
  - `set_api_key(provider, key, password, name)` / `get_api_key()` now use `provider, name` INI key format
  - `set_api_key_plain(provider, key, name)` / `get_api_key_plain()` — plaintext storage (no password)
  - `list_api_keys()` returns `[(provider, name), …]` metadata without decryption
  - `delete_api_key(provider, name)` removes a saved key
  - `disable_password(current_password)` — decrypts all keys, clears hash/salt, stores plaintext
  - `reset_password()` — clears hash/salt, removes all stored keys
  - `test_api_connection(api_key, provider, base_url, timeout)` → `(bool, str, list)` via OpenAI-compatible `models.list()`; returns model ID list
  - `test_model_translation(api_key, model_id, provider, base_url, timeout)` → `dict` — 6-check translation test
  - `PROVIDER_BASE_URLS` — default base URLs for openai, gemini, anthropic, mistral, ollama, lmstudio, local
  - `_api_key_option(provider, name)` — builds `"provider, name"` INI option string
- `gui/dialogs/global_options.py` — Redesigned:
  - Dialog geometry `900x750`, minsize `(750, 600)`
  - "Saved Providers" table → "Saved API Keys" Treeview (Name, Provider columns)
  - `_save_api_key()` — saves current key (encrypted or plaintext based on password state)
  - `_load_api_key()` — decrypts/loads selected key into entry field
  - `_remove_api_key()` — deletes selected saved key
  - `_ensure_password_set()` — first-time password setup + verification flow
  - `_test_connection()` — real API test in background thread; on success shows API Test Results dialog
  - `_show_api_test_results()` — Toplevel dialog with filterable model Treeview (Structured, Batch, Thinking, Pricing, Context); Test Model Translation button
  - `_disable_pw_btn` / `_reset_pw_btn` — password disable and reset buttons in Security section
  - Save button inline with API key entry field
  - Test API Connection button inline with Provider dropdown
- `functions/model_registry.py` — `save_to_ini()` / `load_from_ini()` rewritten for per-model key format (`model.<id> = {JSON}`)
  - `ModelInfo` dataclass: added `flex_input_price`, `flex_output_price`, `priority_input_price`, `priority_output_price`
  - `FALLBACK_MODELS`: 27 models (12 OpenAI incl. gpt-5/5.1/5.2/5-nano, 10 Google, 5 Mistral)
  - All OpenAI models updated with flex/priority/batch pricing from live pricing page
- `dev/test_api_keys.py` — 50 tests: password management, key storage CRUD, INI format, connection testing (mock + live, 3-tuple returns), pipeline lifecycle

**Test results:** 119 passed (50 api_keys + 48 config + 21 defaults)

**INI format:**
```ini
[api_keys]
gemini, default = AIzaSyCL_GMLdAa33hSK6QL1VRrbxJxlB_9h1H4
openai, personal = gAAAAABp...
```

### Translation Step API Key Integration ✅ DONE
- **Bug fix:** Translation step now reads API keys from API.ini via `api_config.get_api_key_plain()` instead of the empty `CherryAI.ini [api]` section.
- **GUI changes:**
  - Added "Key" dropdown as first row in Request Options (populated from saved API keys in API.ini).
  - Model dropdown moved to row 2, filtered by the selected key's provider.
  - Temperature control removed from Translation Step GUI (value still used internally).
- **Data flow:** Key selection → provider auto-detected → model list filtered via `model_registry.get_provider_model_ids()` → on translate, `api_config.get_api_key_plain(provider, name)` retrieves key → injected into `APIClient.config` → client reinitialised.
- **Provider mapping:** `_KEY_PROVIDER_TO_REGISTRY` maps API.ini provider names (gemini, openai, mistral) to model_registry IDs (google, openai, mistral).
- **Manifest fields:** `RequestOptions.ApiKeyProvider`, `RequestOptions.ApiKeyName` persist key selection per project.
- **Modified:** `gui/steps/translate.py`
- **Test results:** 98 + 241 + 290 + 600 passed; 0 regressions from this change.

### GUI Overhaul Tasks 3–9 ✅ DONE

**Task 3 — Available Models window (from registry cache):**
- "Test API Connection" button renamed to "Details" in GO `_build_api_section()`.
- New `_show_available_models()` method loads cached models from `model_registry.get_provider_model_ids()`.
- `_show_api_test_results` renamed to `_show_available_models_window`; alias kept for backward compat.
- Window title changed to "Available Models — {provider}".
- "Update" button added — performs live API call (`test_api_connection()`) and refreshes table.

**Task 4 — Default model per key:**
- `api_config.get_default_model(provider, name)` / `set_default_model(provider, name, model_id)` added.
- Stored in API.ini `[api]` section as `default_model_{provider}_{name}`.
- "Set as Default" button added to Available Models window.
- `_on_key_changed()` in translate.py auto-selects saved default model.

**Task 5 — Structured Output default filter:**
- `struct_var` defaults to checked (True) so only structured-output models shown initially.
- Filter checkbox states saved/loaded from API.ini via `get_api_setting`/`set_api_setting` (keys: `filter_structured`, `filter_batch`, `filter_thinking`).
- Initial populate calls `_apply_filter()` instead of showing all models.
- translate.py `_filter_models_by_provider()` now uses `get_provider_models()` (ModelInfo objects) and applies capability filters.

**Task 6 — Fix Gemini "?" marks:**
- Model ID normalization: strips `models/` prefix from IDs in `_show_available_models_window`.
- Applied to both initial load and Update button refresh paths.

**Task 7 — Move/remove controls:**
- Thinking/Budget removed from translate.py GUI (kept as hidden `tk.BooleanVar`/`tk.IntVar` for compat).
- "Model Settings" LabelFrame (Model combo, Refresh, Temperature) removed from GO `_build_api_section`.
- Temperature scale moved to `_build_request_section` in GO (after Rate Limit row).
- Ban Tokens LabelFrame moved from `_build_prompt_editor` to `_build_request_options` in translate.py.

**Task 8 — Remove Prompt Editor:**
- `_build_prompt_editor()` stripped to only create hidden compat variables (no visible UI).
- "👁 Preview Requests" button moved to header bar, next to "↻ Refresh Lines". Opens `RequestPreviewDialog` showing actual API requests built with `_build_preview_requests()` (same manifest data and chunking as real translation). Three view modes (Pure/Formatted/Plain), toolbar with Jump To, Search (prev/next, match count), and Filter (9 checkboxes for Meta/System Instructions/Summary/Tone/Style/POV/Conditional Prompts/Glossary/Input Lines). Test file: `dev/test_request_preview.py` (40 tests, 38 passed, 2 skipped on headless Tk).

**Task 9 — Model Settings + Translation Options panels:**
- `OptionSection.TRANSLATION` added to enum (10 sections total).
- `SECTION_NAMES[REQUEST]` renamed from "Request Settings" to "Model Settings".
- TRANSLATION added to `SECTION_NAMES`, `SECTION_DESCRIPTIONS`, `CATEGORY_ORDER`.
- `_build_translation_section()` created with Workflow Defaults and Output Quality settings.
- Translation Step rows 3–4: "Model Settings" + "Change…" and "Translation Options" + "Change…" buttons.
- `_open_model_settings()` / `_open_translation_options()` open GO at the respective section.

**Modified files:**
- `gui/dialogs/global_options.py`
- `gui/steps/translate.py`
- `functions/api_config.py`
- `dev/test_gui_v2.py` (test count assertions updated 9→10)

**Test results:** 581 passed in test_gui_v2 (3 pre-existing deprecated model failures); 130 in api tests; 214 in settings/thinking/blacklist/manifest tests; 0 regressions.

=============================================================================
END OF ROADMAP
=============================================================================
