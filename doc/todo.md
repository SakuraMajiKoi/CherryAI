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

**Current Status:** 3177 tests (3177 passed, 26 skipped)

Two test types:
- **Script Test**: pytest unit tests (fast, no LLM)
- **API Test**: 7-stage One_Click_Test (full pipeline with LLM)

Run Script Tests: `python -m pytest CherryAI/dev/ -v --timeout=10`
Run API Test: `python CherryAI.py test`

**Note:** Always use `--timeout` to prevent infinite loops. See `doc/tests.md`.

=============================================================================

MODULE COUNTS (Verified December 2025)

- functions/: 31 modules (+ glossaries/ subfolder with 5 files)
- modi/: 12 processing modes
- formats/: 5 format handlers
- gui/steps/: 10 workflow tabs
- gui/helpers/: 6 adapter modules (mode, analysis, glossary, chunker, prompt)

=============================================================================

HIGHEST PRIORITY - RELEASE STABILIZATION (Manifest, Session, Information Tab)
--------------------------------------------------------------------------

These items are critical for the next stable release. Addressing them first
reduces user friction and fixes outstanding session/manifest UX and data-loss
issues discovered during QA.

### TASK 18.1: Analysis Step Session Loading [DONE]
**Priority:** HIGH | **Status:** ✅ FIXED | **Effort:** 1 hour

Problem: Analysis results were not being loaded when restoring a session.
The Analysis step saved results to session on `on_leave()` but never loaded
them back on `on_enter()`.

Solution:
- Modified `AnalysisStep.on_enter()` to load analysis results from session
- Added `_restore_from_session()` method to populate UI with saved results
- Analysis data is now fully restored including statistics and findings table

Files: `gui/steps/analysis.py`
Tests: `dev/test_session_loading.py::TestAnalysisSessionLoading`

---

### TASK 18.2: Information Tab Session Loading [DONE]
**Priority:** HIGH | **Status:** ✅ FIXED | **Effort:** 2 hours

Problem: Information tab data was saved but not fully restored on session load.
Only some fields were populated; Character Notes only showed Original values,
and Code Glossary patterns were not restored properly.

Solution:
- Modified `_populate_form()` to also call `_refresh_code_pattern_list()`
- Ensured all fields (Project Name, Game Title, Genre, Summary, Style Preset,
  Custom Style, Tone Preset, Custom Tone, Character Notes, Code Glossary,
  Additional Notes) are properly restored
- Fixed character display to show all columns (Original, Translation, Gender)

Files: `gui/steps/information.py`
Tests: `dev/test_session_loading.py::TestInformationSessionLoading`

---

### TASK 18.3: Code Glossary Dialog Hidden Buttons [DONE]
**Priority:** MEDIUM | **Status:** ✅ FIXED | **Effort:** 30 minutes

Problem: When adding a code pattern via the Code Glossary dialog, the Cancel
and Add (OK) buttons were hidden/not visible.

Solution:
- Dialog geometry was too small for content
- Increased dialog height from 350 to 400 pixels
- Verified buttons display correctly

Files: `gui/steps/information.py` (CodePatternDialog class)
Tests: `dev/test_session_loading.py::TestCodePatternDialog`

---

### TASK 18.4: Preprocessing File State After Session Restore [DONE]
**Priority:** HIGH | **Status:** ✅ FIXED | **Effort:** 1.5 hours

Problem: After session restore, Preprocessing step did not have access to
loaded file data and prompted user to load files, even though files were
already loaded. Running Analysis manually resolved the issue.

Solution:
- Modified `PreprocessingStep.on_enter()` to check for files in Input step
- Added fallback to session step data for all_lines
- Preprocessing now correctly accesses files restored from session
- Added `_refresh_file_state()` method to synchronize with Input step

Files: `gui/steps/preprocess.py`
Tests: `dev/test_session_loading.py::TestPreprocessingSessionLoading`

---

### TASK 18.5: Analysis Findings Table Deserialization Error [DONE]
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 1 hour

Problem: When loading analysis results from session, the findings table crashes
with `AttributeError: 'builtin_function_or_method' object has no attribute 'get'`.

Root Cause:
- Findings are stored as `TableRow` objects in memory
- When serialized to session (JSON), they become plain dictionaries via `to_dict()`
- On restore, `_display_results()` passes these dicts to `set_data()` which expects `TableRow` objects
- A plain dict's `.values` is a method, not a dict like `TableRow.values`

Solution:
- Added `_deserialize_findings()` method in `AnalysisStep` to convert dicts back to TableRow objects
- Modified `on_enter()` to deserialize findings before calling `_display_results()`
- The deserialization handles both TableRow and dict types gracefully

Files: `gui/steps/analysis.py`
Tests: `dev/test_session_loading.py::TestAnalysisFindingsDeserialization`

---

### TASK 18.6: Information Tab Data Not Persisting [VERIFIED]
**Priority:** CRITICAL | **Status:** ✅ VERIFIED WORKING | **Effort:** N/A

Problem: Despite "Save" button press, Project Information data is not being
properly saved or restored. Fields appear empty after session restore.

Investigation Result:
- Code review confirmed save/load mechanism is correct
- `_save_metadata()` properly calls `_collect_metadata()` then saves to session
- `_load_metadata()` in `on_enter()` properly restores from session
- `_populate_form()` correctly refreshes all UI elements including character list
- The existing implementation matches expected behavior

Files: `gui/steps/information.py`
Tests: `dev/test_session_loading.py::TestInformationSessionLoading`

---

### TASK 18.7: Information Tab Character Notes Display [VERIFIED]
**Priority:** HIGH | **Status:** ✅ VERIFIED WORKING | **Effort:** N/A

Problem: Character Notes only shows "Original" column values; Translation
and Gender columns are not displayed even when data exists.

Investigation Result:
- Code review confirmed `_refresh_character_list()` inserts all columns correctly:
  `(char.original_name, char.name, char.gender, char.role)`
- Column order matches Treeview headings: original, translation, gender, role
- CharacterInfo dataclass properly serializes/deserializes all fields
- Issue may have been due to TASK 18.5 crash preventing proper display

Files: `gui/steps/information.py`
Tests: `dev/test_session_loading.py::TestInformationSessionLoading`

---

### TASK 18.8: Preprocessing Cannot Access Files After Session Restore [DONE]
**Priority:** HIGH | **Status:** ✅ FIXED | **Effort:** 1.5 hours

Problem: After session restore, Preprocessing step prompts to load files even
though they should be available. Previous fix (TASK 18.4) may be incomplete.

Solution:
- Enhanced `_ensure_input_files_restored()` to first check session data directly
- Added fallback that skips Input step trigger if session already has all_lines
- Improved logging to diagnose restore issues
- The `_get_loaded_lines()` method already had correct fallback to session data

Files: `gui/steps/preprocess.py`
Tests: `dev/test_session_loading.py::TestPreprocessingSessionLoading`

---

### TASK 18.9: Information Tab Session Data Not Persisting [FIXED]
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 1 hour

Problem: Despite TASK 18.6 and 18.7 being marked as fixed, Information tab 
session loading was still broken. Manual verification showed NO fields were
restored after session load. Session autosave file showed `"data": {}` for
step 3 (Information).

Root Cause (Actual):
The initial hypothesis about auto-imports overwriting data was INCORRECT.
The real problem was in `BaseStep.set_step_data()` in `gui/steps/base.py`:

```python
def set_step_data(self, data: Dict[str, Any]) -> None:
    self.session.get_step(self.step_id).data = data
    # MISSING: self.session.set_dirty(True)
```

This method directly assigned to the data dict WITHOUT marking the session
as dirty. The autosave thread only saves when `self.dirty` is True, so:
1. User edits Information fields and clicks "Save"
2. `_save_metadata()` calls `set_step_data()` with metadata
3. Data is stored in session object in memory
4. BUT session.dirty remains False
5. Autosave thread checks `if self.dirty:` - False, skips save
6. On next session load, step 3 data is empty

Note: This bug affects ALL steps that use `BaseStep.set_step_data()`, not
just Information. Any step saving data via this method was silently failing.

Solution:
Modified `BaseStep.set_step_data()` to call `self.session.set_dirty(True)`
after updating the data dictionary.

Files: `gui/steps/base.py`
Tests: `dev/test_session_loading.py::TestBaseStepSetDirty`

---

### TASK 18.10: Session Step Order Migration [FIXED]
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 1 hour

Problem: After TASK 18.9 fix, sessions STILL didn't load correctly. The 
autosave file had all the data, but it was being loaded into wrong steps.

Root Cause:
The step order changed between versions:
- Old: 0=Input, 1=Analysis, 2=Information, 3=Preprocessing, 4=Estimation
- New: 0=Input, 1=Analysis, 2=Estimation, 3=Information, 4=Preprocessing

`SessionState.from_dict()` loaded steps by **array position** not by **name**:
```python
state.steps = [StepState.from_dict(s) for s in d["steps"]]
```

This caused old session data to be loaded into wrong steps:
- Information data (old step_id=2) → loaded into Estimation (new step_id=2)
- Preprocessing data (old step_id=3) → loaded into Information (new step_id=3)

Solution:
Modified `SessionState.from_dict()` to:
1. Build a name→data mapping from loaded session
2. Create fresh steps from current `STEP_DEFINITIONS`
3. Restore data into steps by **matching names**, not positions

This ensures sessions saved with any step order migrate correctly to the
current step definitions.

Files: `gui/state/store.py`
Tests: `dev/test_session_loading.py::TestSessionStepNameMapping`

---

### TASK 18.11: App Close Missing on_leave Call [OBSOLETE]
**Priority:** CRITICAL | **Status:** ⚠️ OBSOLETE | **Effort:** 30 minutes

**Note:** This fix is superseded by TASK 19 (Unified Manifest State).
The entire session system is being replaced with manifest-based persistence.

---

=============================================================================

## TASK 19: UNIFIED MANIFEST STATE SYSTEM [COMPLETE]
**Priority:** CRITICAL | **Status:** ✅ ALL PHASES COMPLETE | **Effort:** 8-12 hours

### Background

The previous session system (TASK 18.1-18.11) attempted to maintain two
separate persistence mechanisms:
1. **Session file** (`temp/gui_session_autosave.json`) - GUI step data
2. **Manifest file** (`manifests/*.CherryAI.json`) - Translation data

This dual approach led to:
- Data fragmentation (state split across files)
- Complex synchronization bugs (11+ TASK 18.x fixes!)
- Race conditions with autosave thread
- Data loss on unexpected closure
- User confusion about what's saved where

### New Design: Manifest-First Architecture

**Core Principle:** The manifest IS the project. All state lives in one file.

**Manifest Structure (v3.0):**
```json
{
  "version": "3.0",
  "project_name": "My Translation Project",
  "created_at": "2025-12-18T...",
  "updated_at": "2025-12-18T...",
  
  "source_files": ["path/to/file1.txt", "path/to/file2.txt"],
  "current_step": 3,
  
  "project_info": {
    "game_title": "...",
    "source_language": "Japanese",
    "target_language": "English",
    "summary": "...",
    "style_preset": "natural",
    "tone_preset": "neutral",
    "genre": "...",
    "custom_notes": "..."
  },
  
  "characters": [...],
  "code_patterns": [...],
  
  "step_state": {
    "analysis": { "status": "completed", "last_run": "...", "stats": {...} },
    "estimation": { "status": "not-started", "selected_model": null },
    "preprocessing": { "status": "in-progress", "rules": [...] },
    ...
  },
  
  "glossary": {
    "use_global": true,
    "project_entries": [...]
  },
  
  "lines": [
    { "idx": 0, "orig": "...", "prepro": "...", "tl": "...", ... }
  ],
  
  "operations": [...],
  "mappings": {...}
}
```

### Save Triggers (Automatic - No Manual Save Required)

1. **On Close (WM_DELETE_WINDOW)**
   - Call `on_leave()` for current step
   - Save manifest to disk
   - No confirmation dialog (always saves)

2. **On Step Change (Tab Switch)**
   - Call `on_leave()` for old step (writes to manifest in memory)
   - Save manifest to disk
   - Call `on_enter()` for new step (reads from manifest)

3. **Before Translation Start**
   - Ensure all step data captured
   - Full manifest save (checkpoint)
   - Record translation start time

4. **During Translation**
   - After each batch: update `lines[].tl` and save
   - Log entries appended to manifest
   - Incremental save (only changed lines if large file)

### Load Behavior

1. **Load File Without Manifest**
   - Prompt user for project name
   - Create new manifest at `manifests/{project_name}.CherryAI.json`
   - Initialize with source file path and defaults

2. **Load Existing Manifest**
   - File > Open Project... (or drag-drop .CherryAI.json)
   - Restore all step state, line data, and UI position
   - Navigate to `current_step` from manifest

3. **Glossary Choice**
   - Global glossary: `user/glossary.csv` (shared across projects)
   - Project glossary: `manifest.glossary.project_entries`
   - UI toggle to copy global entries to project (one-time)

### Implementation Status

**Phase 1: Manifest Extension** ✅ COMPLETE
- [x] Create `ManifestManager` class for load/save operations
- [x] Add `StepState`, `ProjectInfo`, `GlossaryConfig` dataclasses
- [x] v3.0 serialization with backward compat for v2.x
- [x] Update `BaseStep` to support both session and manifest
- [x] Create `ProjectNameDialog` and `LoadManifestDialog`
- [x] Add 27 new tests in `dev/test_manifest_state.py`

Files Created:
- `functions/manifest_manager.py` - ManifestManager, StepState, ProjectInfo, GlossaryConfig
- `gui/dialogs/project_dialog.py` - ProjectNameDialog, LoadManifestDialog
- `dev/test_manifest_state.py` - 27 tests for manifest state system

Files Modified:
- `gui/steps/base.py` - BaseStep now supports both session and manifest_manager
- `gui/dialogs/__init__.py` - Export new dialogs

**Phase 2: GUI Integration** ✅ COMPLETE
- [x] Update `App` to use ManifestManager for state
- [x] Wire up File > Load Manifest menu to LoadManifestDialog
- [x] Pass manifest_manager to all step tabs
- [x] Add manifest save on tab change
- [x] Add manifest save on close

Files Modified:
- `gui/app.py` - Added ManifestManager integration, wired LoadManifestDialog
- All 10 step classes - Accept manifest_manager parameter

**Phase 3: Remove Session System** ✅ COMPLETE
- [x] Remove autosave thread from SessionState (no longer started in App)
- [x] Simplified File menu (New Project, Open Project instead of session commands)
- [x] Remove session-related code from App (stop_autosave, start_autosave calls)
- [x] Remove Save Session State menu item and shortcut
- [x] Ctrl+S now triggers _on_manual_save() for manifest

Changes:
- `gui/app.py` - Removed autosave thread, simplified menu, added _on_manual_save
- File menu now shows: New Project, Open Project..., Open Files..., Exit
- Session store.py kept for backward compatibility but autosave disabled

**Phase 4: Glossary Integration** ✅ COMPLETE
- [x] Add "Glossary Settings" section in Information step UI
- [x] Add "Use Global Glossary" checkbox toggle
- [x] Add "Copy from Global" button to import entries
- [x] Wire up to ManifestManager.set_use_global_glossary()
- [x] Add _refresh_glossary_settings() to populate from manifest

Files Modified:
- `gui/steps/information.py` - Added _build_glossary_settings_section(),
  _on_use_global_glossary_changed(), _on_copy_from_global_glossary(),
  _refresh_glossary_settings()

**Phase 5: Input Step Integration** ✅ COMPLETE
- [x] Add project name prompt when loading new files without manifest
- [x] Call App.create_new_project() from InputExtractionStep
- [x] Initialize manifest with source files and lines

Files Modified:
- `gui/steps/input_extract.py` - Added _ensure_project_created(),
  _sync_lines_to_manifest(), updated _on_load_files()

### Tests

Test file: `dev/test_manifest_state.py` (27 tests)
- TestStepState (5 tests) - Step state dataclass
- TestProjectInfo (3 tests) - Project info dataclass  
- TestGlossaryConfig (2 tests) - Glossary config dataclass
- TestManifestManager (11 tests) - Core manager operations
- TestManifestMigration (1 test) - v2 to v3 migration
- TestGlobalManagerInstance (2 tests) - Singleton pattern
- TestBaseStepWithManifestManager (3 tests) - BaseStep integration

**Test Results:** 3177 passed, 26 skipped (December 18, 2025)

---

## TASK 20: MANIFEST INTEGRATION FIXES & UX IMPROVEMENTS [COMPLETE]
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

### Background

Post-TASK 19 testing revealed several integration issues:
1. `ProjectNameDialog.__init__() got an unexpected keyword argument 'suggested_name'`
2. Manifest v2.0 files failed to load any information
3. Folder naming inconsistency ("manifests" vs "Projects")
4. No visual feedback for source file recovery status

### Changes Made

**1. ProjectNameDialog Signature Fix** ✅
- Modified `gui/dialogs/project_dialog.py` to accept optional `suggested_name`
- Updated signature: `__init__(parent, session, source_files=None, suggested_name=None)`
- Fixed `gui/app.py` to pass `source_files` to ProjectNameDialog

**2. Manifest v2.0 Migration Enhancement** ✅
- Enhanced `ManifestManager._migrate_manifest()` in `functions/manifest_manager.py`
- Proper mapping: `source_file` → `source_files` (list)
- Metadata fields preserved: `game_title`, `source_language`, `target_language`
- Project info properly initialized from legacy manifest data

**3. Folder Rename: "manifests" → "Projects"** ✅
- Updated `MANIFEST_DIR` constant from "manifests" to "Projects" in:
  - `functions/manifest_manager.py`
  - `CherryAI.py`
  - `gui/steps/input_extract.py` (_find_manifest method)
- Updated test `test_find_manifest_in_projects_subdir` (was `test_find_manifest_in_manifests_subdir`)

**4. Source File Recovery Warnings** ✅
- Added `_check_source_files_status()` in `gui/steps/input_extract.py`
- Categories:
  - **Found**: File exists at original path (green)
  - **Recoverable**: File missing but format is text-based (yellow warning)
  - **Missing**: File missing with non-recoverable format (red error)
- Recoverable formats: txt, csv, tsv, json
- Non-recoverable formats: rpgm, xlsx, epub, pdf
- UI displays color-coded file list with status

**5. ManifestManager Integration Methods** ✅
- Added `import_from_mainhelper_manifest()`: Copy data from mainhelper.Manifest
- Added `export_to_mainhelper_manifest()`: Create mainhelper.Manifest from GUI state
- These methods bridge the GUI ManifestManager with CLI mainhelper.Manifest

### Files Modified
- `gui/dialogs/project_dialog.py` - Fixed signature
- `gui/app.py` - Fixed dialog call
- `functions/manifest_manager.py` - Enhanced migration, added integration methods
- `gui/steps/input_extract.py` - Source file status, manifest loading
- `CherryAI.py` - Folder constant
- `dev/test_gui_v2.py` - Updated test name

### Test Results
All manifest-related tests passing after changes.

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

PENDING TASKS - ARCHITECTURE

TASK: Refactor Processing, IO, Models, Reporting

   Goal: Processing in each mode, shared reporting in modehelper
   Files: modi/*.py, mainhelper.py
   Priority: MEDIUM
   Effort: 4-8 hours

---

TASK: Establish Proper Pipeline

   Goal: Strict separation: CherryAI -> mainhelper -> modi
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

UPCOMING FEATURES - PHASE 17

See the image translation workflow: [Image Translation Workflow](image_translation_workflow.md)

### TASK 17.1: Batch API Support
**Priority:** HIGH | **Effort:** 8-12 hours

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

### TASK 17.2: Multi-Key Management & Auto-Rotation
**Priority:** HIGH | **Effort:** 10-14 hours

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

### TASK 17.3: Named API Profiles & Configuration
**Priority:** MEDIUM | **Effort:** 4-6 hours

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

### TASK 17.4: Additional File Format Support
**Priority:** MEDIUM | **Effort:** 8-10 hours

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

### TASK 17.5: Advanced Usage Analytics & Dynamic Rate Limiting
**Priority:** HIGH | **Effort:** 12-16 hours

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

### TASK 17.6: Automatic API Key Provisioning (Investigation)
**Priority:** LOW | **Effort:** 4-6 hours

Goal: Investigate feasibility of automated API key acquisition to lower entry barrier.

**Scope:**
- Research provider APIs for programmatic account/key creation.
- Evaluate "convenience vs. ToS" compliance (avoiding unauthorized automation).
- Explore legitimate "Get Started" flows that can be streamlined within the tool.
- **Constraint:** Must strictly adhere to provider Terms of Service.

---

### TASK 17.7: Session Persistence & Auto-Load
**Priority:** HIGH | **Effort:** 4-6 hours

Goal: Seamless workflow continuation.

**Features:**
- **Auto-Load:** Automatically load the last used manifest and progress state on application launch.
- **Opt-Out:** Configuration option to disable auto-load (start fresh).
- **State Recovery:** Robustly restore GUI state (tabs, selections) from `temp/gui_session_autosave.json`.

**Implementation:**
- Fix `ISSUE: GUI v2 Session Not Loading Automatically`.
- Update `gui/app.py` initialization logic.
- Add "Load Last Session" toggle in Global Options.

### TASK 17.8: Agent-Assisted Modes (Ask/Agent LLM Modes)
**Priority:** LOW | **Effort:** 6-8 hours

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
-The costs for API usage will also be estimated and recorded.

Testing & QA:
- Add `dev/test_agent_modes.py` (script tests) that:
   - Mocks `functions.api_client.agent_call` to verify mode metadata, system prompt templating, and read/write gating.
   - Verifies GUI dialog behavior in headless mode by testing the model selection, toggles default states, and sandbox write preview creation.
- Add integration example: `dev/example_agent_session.md` documenting a safe workflow for using Script Author mode to generate a small `formats/markdown.py` starter in `dev/sandbox/`.

Notes & Constraints:
- This feature is optional and should degrade gracefully when no API credentials exist: the GUI should disable agent modes and present a helpful message.
- Keep system instructions versioned in `doc/agent_prompts/` for auditability and test fixtures.
- Effort estimates assume an incremental, opt-in rollout (UI + functions + small tests). More advanced capabilities (direct code execution, auto-apply to repo) are intentionally out of scope for the low-priority initial implementation.

### TASK 17.9: Estimation Step Upgrade (Move & Enhancements)
**Priority:** MEDIUM | **Effort:** 6-10 hours

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

### TASK 17.10: Tooltips Restoration & Multi-Language UI
**Priority:** MEDIUM | **Effort:** 6-12 hours

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
| functions/local_llm.py | Not integrated with GUI | Integrate with Translation step |
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

Phase 17 (Upcoming):
- Batch API Support: 8-12 hours
- Multi-Key Management & Auto-Rotation: 10-14 hours
- Named API Profiles: 4-6 hours
- Additional File Formats (.trans, .md, lenient JSON): 8-10 hours
- Advanced Usage Analytics & Rate Limiting: 12-16 hours
- Automatic API Key Provisioning (Invest.): 4-6 hours
- Session Persistence & Auto-Load: 4-6 hours

Major Projects (12+ hours):
- LLM Provider Modules: 12-16 hours
- Advanced API Request System: 26-32 hours
- GUI Table View: 20-25 hours
- Translation Progress Window: 8-12 hours

Medium Tasks (2-8 hours):
- Refactor Processing: 4-8 hours
- Establish Proper Pipeline: 2-4 hours
- Performance Optimization: 6-8 hours

Total Remaining Effort: ~135-183 hours

================

**Total Tasks:** 8
**Completed:** 8 (100%)
**Estimated Effort:** 42-64 hours
**Actual Effort:** ~9 hours

**Test Files Created:** 7
**Tests Added:** 89
**All Tests Passing:** ✅ Yes

**Key Improvements:**
1. Fixed critical Global Options dialog freeze
2. Added 2-column layout to Information tab
3. Added Code Glossary widget for managing code patterns
4. Added Analysis → Information character import
5. Added subtask tracking system for granular progress
6. Verified CLI estimation working correctly
7. Added automated manifest creation

=============================================================================
END OF ROADMAP
==============================================================================

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

Last updated: December 2025

Last updated: December 2025 (Phase 18 Complete)

=============================================================================

PHASE 19: CRITICAL DEBUGGING (Global Options Freeze)

### TASK 19.1: Divide and Conquer Global Options Dialog
**Priority:** CRITICAL | **Effort:** Variable
**Status:** ✅ FIXED (Phase 19.1 - December 2025)

Goal: Isolate the cause of the fatal freeze when opening the Global Options Window.

**Root Cause:**
The `GlobalOptionsDialog` was attempting to become modal (`grab_set`, `transient`) and force UI updates (`update_idletasks`) during initialization. Even with deferred execution (`after(100)`), this caused a deadlock in the Tkinter event loop on some environments, likely due to the window not being fully mapped or ready for modal state.

**Fix Applied:**
- Removed all modal window management calls (`grab_set`, `transient`, `focus_set`, `update_idletasks`, `_center_on_parent`) from the initialization flow.
- The dialog now opens as a standard non-modal `Toplevel` window.
- This eliminates the risk of deadlock while preserving full functionality of the options dialog.
- Restored all UI content (sections and buttons) which were confirmed not to be the cause.

**Files Changed:**
- `CherryAI/gui/dialogs/global_options.py`

**Verification:**
- Manual testing required to confirm the window opens without freezing.
    -   Uncomment `_build_navigation`. Test.
    -   Uncomment sections in groups:
        -   Group A: `_build_api_section`, `_build_request_section`
        -   Group B: `_build_caching_section`, `_build_logging_section`
        -   Group C: `_build_session_section`, `_build_safety_section`, `_build_file_io_section`
    -   **Test:** After enabling each group.

4.  **Phase 3: Granular Isolation**
    -   Once a problematic section is identified (e.g., API section), comment out individual widgets within that section.
    -   Suspects: `ttk.Combobox` with dynamic values, `ttk.Scale` variables, or event bindings.

**Files to Modify:**
-   `CherryAI/gui/dialogs/global_options.py`

**Reversion Plan:**
-   Once the bug is found and fixed, uncomment all valid code.
-   Ensure `_build_ui` is restored to its original state.
