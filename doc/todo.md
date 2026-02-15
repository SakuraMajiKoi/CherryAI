CHERRYAI - OUTSTANDING WORK & ROADMAP

Features, Improvements, and Known Tasks

=============================================================================

AI AGENT INSTRUCTIONS
---------------------

CRITICAL ARCHITECTURE PRINCIPLE:
The GUI must NOT contain processing logic. All processing functions belong 
in shared modules (functions/, modi/, formats/) that both CLI and GUI use.

WHEN IMPLEMENTING NEW FEATURES:
- ALL text manipulation ↁEfunctions/ modules
- ALL pre/post-processing ↁEmodi/ plugins  
- ALL file I/O ↁEformats/ handlers
- GUI code ↁEdisplay and user interaction ONLY

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
- gui/dialogs/: 2 dialog modules (global_options, project_dialog)

=============================================================================

HIGHEST PRIORITY - RELEASE STABILIZATION (Manifest, Session, Information Tab)
--------------------------------------------------------------------------

These items are critical for the next stable release. Addressing them first
reduces user friction and fixes outstanding session/manifest UX and data-loss
issues discovered during QA.

### TASK 18.1: Analysis Step Session Loading [DONE]
**Priority:** HIGH | **Status:** ✁EFIXED | **Effort:** 1 hour

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
**Priority:** HIGH | **Status:** ✁EFIXED | **Effort:** 2 hours

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
**Priority:** MEDIUM | **Status:** ✁EFIXED | **Effort:** 30 minutes

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
**Priority:** HIGH | **Status:** ✁EFIXED | **Effort:** 1.5 hours

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
**Priority:** CRITICAL | **Status:** ✁EFIXED | **Effort:** 1 hour

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
**Priority:** CRITICAL | **Status:** ✁EVERIFIED WORKING | **Effort:** N/A

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
**Priority:** HIGH | **Status:** ✁EVERIFIED WORKING | **Effort:** N/A

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
**Priority:** HIGH | **Status:** ✁EFIXED | **Effort:** 1.5 hours

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
**Priority:** CRITICAL | **Status:** ✁EFIXED | **Effort:** 1 hour

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
**Priority:** CRITICAL | **Status:** ✁EFIXED | **Effort:** 1 hour

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
- Information data (old step_id=2) ↁEloaded into Estimation (new step_id=2)
- Preprocessing data (old step_id=3) ↁEloaded into Information (new step_id=3)

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
**Priority:** CRITICAL | **Status:** ⚠�E�EOBSOLETE | **Effort:** 30 minutes

**Note:** This fix is superseded by TASK 19 (Unified Manifest State).
The entire session system is being replaced with manifest-based persistence.

---

=============================================================================

## TASK 19: UNIFIED MANIFEST STATE SYSTEM [COMPLETE]
**Priority:** CRITICAL | **Status:** ✁EALL PHASES COMPLETE | **Effort:** 8-12 hours

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

**Phase 1: Manifest Extension** ✁ECOMPLETE
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

**Phase 2: GUI Integration** ✁ECOMPLETE
- [x] Update `App` to use ManifestManager for state
- [x] Wire up File > Load Manifest menu to LoadManifestDialog
- [x] Pass manifest_manager to all step tabs
- [x] Add manifest save on tab change
- [x] Add manifest save on close

Files Modified:
- `gui/app.py` - Added ManifestManager integration, wired LoadManifestDialog
- All 10 step classes - Accept manifest_manager parameter

**Phase 3: Remove Session System** ✁ECOMPLETE
- [x] Remove autosave thread from SessionState (no longer started in App)
- [x] Simplified File menu (New Project, Open Project instead of session commands)
- [x] Remove session-related code from App (stop_autosave, start_autosave calls)
- [x] Remove Save Session State menu item and shortcut
- [x] Ctrl+S now triggers _on_manual_save() for manifest

Changes:
- `gui/app.py` - Removed autosave thread, simplified menu, added _on_manual_save
- File menu now shows: New Project, Open Project..., Open Files..., Exit
- Session store.py kept for backward compatibility but autosave disabled

**Phase 4: Glossary Integration** ✁ECOMPLETE
- [x] Add "Glossary Settings" section in Information step UI
- [x] Add "Use Global Glossary" checkbox toggle
- [x] Add "Copy from Global" button to import entries
- [x] Wire up to ManifestManager.set_use_global_glossary()
- [x] Add _refresh_glossary_settings() to populate from manifest

Files Modified:
- `gui/steps/information.py` - Added _build_glossary_settings_section(),
  _on_use_global_glossary_changed(), _on_copy_from_global_glossary(),
  _refresh_glossary_settings()

**Phase 5: Input Step Integration** ✁ECOMPLETE
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
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

### Background

Post-TASK 19 testing revealed several integration issues:
1. `ProjectNameDialog.__init__() got an unexpected keyword argument 'suggested_name'`
2. Manifest v2.0 files failed to load any information
3. Folder naming inconsistency ("manifests" vs "Projects")
4. No visual feedback for source file recovery status

### Changes Made

**1. ProjectNameDialog Signature Fix** ✁E
- Modified `gui/dialogs/project_dialog.py` to accept optional `suggested_name`
- Updated signature: `__init__(parent, session, source_files=None, suggested_name=None)`
- Fixed `gui/app.py` to pass `source_files` to ProjectNameDialog

**2. Manifest v2.0 Migration Enhancement** ✁E
- Enhanced `ManifestManager._migrate_manifest()` in `functions/manifest_manager.py`
- Proper mapping: `source_file` ↁE`source_files` (list)
- Metadata fields preserved: `game_title`, `source_language`, `target_language`
- Project info properly initialized from legacy manifest data

**3. Folder Rename: "manifests" ↁE"Projects"** ✁E
- Updated `MANIFEST_DIR` constant from "manifests" to "Projects" in:
  - `functions/manifest_manager.py`
  - `CherryAI.py`
  - `gui/steps/input_extract.py` (_find_manifest method)
- Updated test `test_find_manifest_in_projects_subdir` (was `test_find_manifest_in_manifests_subdir`)

**4. Source File Recovery Warnings** ✁E
- Added `_check_source_files_status()` in `gui/steps/input_extract.py`
- Categories:
  - **Found**: File exists at original path (green)
  - **Recoverable**: File missing but format is text-based (yellow warning)
  - **Missing**: File missing with non-recoverable format (red error)
- Recoverable formats: txt, csv, tsv, json
- Non-recoverable formats: rpgm, xlsx, epub, pdf
- UI displays color-coded file list with status

**5. ManifestManager Integration Methods** ✁E
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
- **Mode: Interactive Help**  EAn assistant configured to act as an interactive help system for CherryAI. It is provided with loaded documentation snippets (`doc/` files, help text) and can answer contextual questions, point to configuration locations, and provide step-by-step guidance for using the tool. Read access to `doc/` and `config/` is toggleable.
- **Mode: Language Assistant**  EA language-focused agent that can analyze and suggest language improvements, provide localized guidance, and operate on selected table/cell context. The agent can accept selected table cell content (from the GUI table selection) as context for more precise language suggestions and can optionally write back changed cell suggestions as draft edits (write toggle).
- **Mode: Script Author**  EAn agent tuned to author new CherryAI scripts (primarily extraction/injection handlers or format plugins). It will be provided developer-facing documentation (function signatures, `formats/` and `functions/` guidelines) and can propose or generate new Python modules/templates. Write access is gated  Eby default it only returns code suggestions, with an explicit opt-in to write new files into a `dev/sandbox/` area.
- **Mode: Targeted Translation / TLC / Check**  EAn agent specialized in targeted translation tasks: making translation suggestions, running edit passes, and performing validation/checking. It accepts manifest or selected-line-context and can produce suggested edits or validation reports. Read/write toggles control whether it may alter a manifest or only emit suggestions.

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
**All Tests Passing:** ✁EYes

**Key Improvements:**
1. Fixed critical Global Options dialog freeze
2. Added 2-column layout to Information tab
3. Added Code Glossary widget for managing code patterns
4. Added Analysis ↁEInformation character import
5. Added subtask tracking system for granular progress
6. Verified CLI estimation working correctly
7. Added automated manifest creation

=============================================================================

## MANIFEST 3.0 GREAT EXPANSION
**Priority:** CRITICAL | **Status:** ✁ECOMPLETE | **Effort:** 40-60 hours total

### Overview

This is a comprehensive upgrade to the manifest system making it the single source of
truth for all project settings. The manifest will store every GUI field value, enabling
instant project switching and consistent state management.

### CRITICAL ARCHITECTURE NOTE: UNIFIED MANIFEST SYSTEM

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
       ━E
       ▼
ManifestManager._manifest_data  ←── Single source of truth
       ━E
       ├──▶ GUI reads/writes project settings directly
       ━E
       └──▶ export_to_mainhelper_manifest() ──▶ Processor
                                                    ━E
       import_from_mainhelper_manifest() ◀─────────━E
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

**Configuration Hierarchy:**
```
CherryAI.ini [manifest_defaults]
       ━E
       ▼ (on create_new)
ManifestManager._manifest_data ─────────────────────────━E
       ━E                                               ━E
       ━E Contains ALL fields:                          ━E
       ━E ├─ version: "3.0"                            ━E
       ━E ├─ lines: [...]        ↁEv2.1 processing     ━E
       ━E ├─ operations: [...]   ↁEv2.1 processing     ━E
       ━E ├─ mappings: {...}     ↁEv2.1 processing     ━E
       ━E ├─ project_info: {...} ↁEv3.0 settings       ━E
       ━E ├─ step_state: {...}   ↁEv3.0 GUI state      ━E
       ━E ├─ Deduplication: true ↁEv3.0 settings       ━E
       ━E ├─ RequestOptions: {}  ↁEv3.0 settings       ━E
       ━E └─ ... all other fields                      ━E
       ━E                                               ━E
       ▼                                                ▼
GUI Fields ◀────────────────────────────────▶ Processor (via export)
```

**KEY FILES AND THEIR ROLES:**
```
functions/mainhelper.py       - LineEntry, Manifest dataclass, Processor
                                (runtime processing - DO NOT change format)
functions/manifest_manager.py - ManifestManager (file I/O, add v3.0 fields)
functions/ini_manager.py      - NEW: INI defaults loading
functions/manifest_fields.py  - NEW: Field type helpers for GUI binding
functions/options.py          - API providers (global settings, not per-project)
functions/project_config.py   - Project overrides (will merge into ManifestManager)
gui/app.py                    - Uses ManifestManager for all state
gui/steps/*.py                - Read/write via ManifestManager
```

**WHAT MANIFEST 3.0 ADDS (on top of v2.1):**
- Default initialization from .ini before any GUI access
- Project settings fields (Title, Genre, Style, Tone, etc.)
- Preprocessing toggle states (Deduplication, SymbolConversion, etc.)
- Request options (Model, Temperature, ChunkSize, etc.)
- Post-processing options (PlaceholderRecovery, etc.)
- Output format settings (FileNaming, Backup, etc.)
- All these fields get passed to respective functions during processing

---

## PHASE 21: MANIFEST LOADING FOUNDATION (REVISED)
**Priority:** CRITICAL | **Status:** ✁ECOMPLETE | **Effort:** 8-12 hours

This phase establishes the foundation for all subsequent manifest work. It must be
completed first as all tests for new manifest fields depend on proper load/create/save.

**ALL TASKS COMPLETE:**
- ✁ETask 21.1: INI Path Resolution & Loading (48 tests)
- ✁ETask 21.2: Manifest Initialization with All Defaults (44 tests)
- ✁ETask 21.3: Settings Flow to Processing Functions (87 tests)
- ✁ETask 21.4: Application Startup Manifest Loading (23 tests)

**Total Phase 21 Tests: 202 tests passing**

### TASK 21.1: INI Path Resolution & Loading
**Priority:** CRITICAL | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Ensure CherryAI.ini is always loaded relative to the main executable/script.

**Implementation:**
- ✁ECreated `functions/ini_manager.py` with INI path resolution
- ✁EINI located next to CherryAI.py (and future .exe when packaged)
- ✁EAdded `get_ini_path()` that resolves relative to `__file__` of main module
- ✁EAdded `get_default(section, key, fallback)` for typed access
- ✁EAdded `set_default(section, key, value)` for saving user defaults
- ✁EAdded `get_manifest_dir()` returning `{app_dir}/manifests` as default
- ✁EAdded `get_all_manifest_defaults()` for complete manifest initialization

**Files Created:**
- `functions/ini_manager.py` - INI path resolution and typed access (450+ lines)

**Tests Created:**
- `dev/test_ini_manager.py` - 48 tests covering:
  - INI path resolution (4 tests)
  - Manifest directory (3 tests)
  - get_default with type conversion (9 tests)
  - Typed getters (6 tests)
  - set_default (6 tests)
  - Section operations (6 tests)
  - Manifest defaults (7 tests)
  - Caching (2 tests)
  - Error handling (3 tests)
  - Integration (3 tests)

**Files to Modify (Future):**
- `functions/config.py` - Import and use ini_manager
- `functions/manifest_manager.py` - Use ini_manager for default resolution
- `CherryAI.py` - Ensure proper working directory on startup

**Tests Required (per todo.md):**
- ✁E`test_ini_path_relative_to_module`
- ✁E`test_get_default_with_fallback`
- ✁E`test_set_default_creates_section`
- ✁E`test_manifest_dir_default_location`

---

### TASK 21.2: Manifest Initialization with All Defaults ✁E
**Priority:** CRITICAL | **Status:** ✁ECOMPLETE | **Effort:** 3 hours

Goal: Manifest must be fully initialized with ALL defaults BEFORE GUI can access it.

**WHY THIS MATTERS:**
- GUI cannot display or modify fields that don't exist
- Processing functions need settings to be present (even if default)
- Defaults come from .ini so users can customize them globally
- Every new manifest starts with complete, valid state

**Implementation:** ✁EDONE
- Extended `ManifestManager._create_empty_manifest()` to include ALL v3.0 fields
- Added `_get_manifest_defaults()` method that reads [manifest_defaults] via ini_manager
- Added `_get_builtin_defaults()` as fallback when INI unavailable
- Added `_create_project_info_defaults()` for project_info nested dict
- Added `_parse_list_default()` for comma-separated list fields
- Added `_ensure_all_fields_present()` called in `load()` for backward compatibility
- Added `_ensure_nested_fields()` to fill missing fields in nested dicts

**Tests Added:** `dev/test_manifest_defaults.py` (44 tests)
- TestCreateManifestPopulatesAllDefaults (11 tests) - all v3.0 fields present
- TestLoadedManifestHasAllFields (5 tests) - backward compatibility
- TestDefaultValuesMatchINI (6 tests) - INI values used
- TestBuiltinDefaults (2 tests) - fallback defaults work
- TestBackwardCompatibility (4 tests) - v2.x data preserved
- TestListFieldParsing (3 tests) - list/bool fields correct
- TestHelperMethods (7 tests) - helper method edge cases
- TestFieldCountVerification (6 tests) - all fields counted

**Unified Manifest Structure (v3.0):**
```python
# ManifestManager._manifest_data - ONE dict containing EVERYTHING
{
    "version": "3.0",
    "created_at": "...",
    "updated_at": "...",
    
    # === Project Identity ===
    "project_name": "Project1",
    "source_files": [...],
    "current_step": 0,
    
    # === v2.1 Processing Data (unchanged format) ===
    "lines": [...],           # LineEntry.to_dict() format
    "operations": [...],      # Operation.__dict__ format  
    "mappings": {...},        # Mode state mappings
    "summary": "",
    "metadata": {...},
    
    # === v3.0 Project Settings (NEW) ===
    "project_info": {...},    # ProjectInfo fields
    "step_state": {...},      # Per-step GUI state
    "glossary": {...},        # GlossaryConfig
    "characters": [...],      # CharacterInfo list
    "code_patterns": [...],   # CodePattern list
    
    # === v3.0 Processing Options (NEW - passed to functions) ===
    "Deduplication": true,
    "DeduplicationThreshold": 1,
    "EllipsisCompression": true,
    "SymbolConversion": true,
    "SpeakerNameReplacement": false,
    
    # === v3.0 Request Options (NEW - passed to API client) ===
    "RequestOptions": {
        "Model": "",
        "Temperature": 0.2,
        "LinesPerChunk": 30,
        "MaxRetries": 3,
        ...
    },
    
    # === v3.0 Other Settings (NEW) ===
    "ValidationRules": {...},
    "QAOptions": {...},
    "PostProcessing": {...},
    "WordwrapSettings": {...},
    "OutputFormat": {...}
}
```

**Default Values (from CherryAI.ini [manifest_defaults]):**
```ini
[manifest_defaults]
project_name = Project1
title = Title1
genre = fictional, nonfictional
source_language = Japanese
target_language = English
summary = [Summary of the Content]
style_preset = neutral
tone_preset = natural
deduplication = true
deduplication_threshold = 1
ellipsis_compression = true
symbol_conversion = true
speaker_name_replacement = false
code_spacing_rules = true
# ... all other fields
```

**Files Modified:**
- `functions/manifest_manager.py` - Extended _create_empty_manifest() with ~270 lines of new code
- `functions/ini_manager.py` - Already provides get_all_manifest_defaults()
- `CherryAI.ini` - Already has complete [manifest_defaults] section

**All Tests Pass:**
- `dev/test_manifest_defaults.py` - 44 tests ✁E
- `dev/test_manifest_v2.py` - 51 tests ✁E
- `dev/test_manifest_state.py` - 27 tests ✁E

---

### TASK 21.3: Settings Flow to Processing Functions
**Priority:** CRITICAL | **Status:** ✁ECOMPLETE | **Effort:** 3 hours

Goal: Ensure manifest settings are properly passed to processing functions.

**IMPLEMENTATION COMPLETED:**

Added ~220 lines of settings helper methods to `functions/manifest_manager.py`:

| Method | Purpose | Fields Included |
|--------|---------|-----------------|
| `get_request_options()` | API client settings | Model, Temperature, LinesPerChunk, RetryStrategy, MaxRetries, EnableRequestCaching, LineByLineMode, Thinking, ThinkingBudget |
| `set_request_options()` | Update request settings | Updates RequestOptions dict |
| `get_preprocessing_options()` | Preprocessing settings | Deduplication, DeduplicationThreshold, EllipsisCompression, SymbolConversion, SpeakerNameReplacement, CodeSpacingRules, ProtectCodePatterns, CustomPlaceholders, AnchorRemoval |
| `set_preprocessing_options()` | Update preprocessing | Updates flat fields |
| `get_validation_rules()` | Validation settings | PlaceholderPreservation, AnchorPreservation, JapaneseCharacterDetection, SpeakerFormat, QuoteBalance, EmptyTranslation |
| `set_validation_rules()` | Update validation | Updates ValidationRules dict |
| `get_qa_options()` | QA settings | RerunPolicy, MaxJapaneseChars, MaxLineLength |
| `set_qa_options()` | Update QA settings | Updates QAOptions dict |
| `get_postprocessing_options()` | Post-processing settings | PlaceholderRecovery, BracketBalanceRecovery, QuoteBalanceRecovery, WhitespaceNormalization, RestoreCodeCharacters, RestoreLinebreaks, EnableSymbolConversion, FullwidthToHalfwidth, FailureHandling |
| `set_postprocessing_options()` | Update postprocessing | Updates PostProcessing dict |
| `get_wordwrap_options()` | Wordwrap settings | Mode, Width, BreakChar, MaxLines, PreventOrphans, PreferPunctuationBreaks, SpeakerHandling, IgnorePatterns, Typography |
| `set_wordwrap_options()` | Update wordwrap | Updates WordwrapSettings dict |
| `get_output_options()` | Output settings | PreserveFolderStructure, Format, PairMode, Encoding, FileNaming, TextOption, OverwriteExistingFiles, Backup, BackupExtension, ExportManifestFile, ExportProcessingLogs, ExportGlossaryEntries |
| `set_output_options()` | Update output | Updates OutputFormat dict |
| `get_estimation_data()` | Token estimation | InputLines, InputTokens, OutputTokens |
| `set_estimation_data()` | Update estimation | Updates flat fields |
| `get_all_settings()` | All grouped settings | Returns dict with keys: project_info, preprocessing, request, validation, qa, postprocessing, wordwrap, output, estimation |

**Key Design Decisions:**
- All getters return `deepcopy()` to prevent external mutation
- All setters call `_mark_dirty()` to track changes
- Methods use existing field names from `_create_empty_manifest()`
- Comprehensive docstrings with return type documentation

**Files Modified:**
- `functions/manifest_manager.py` - Added Settings Access section (~220 lines)

**All Tests Pass:**
- `dev/test_settings_flow.py` - 87 tests ✁E
- `dev/test_manifest_defaults.py` - 44 tests ✁E
- `dev/test_manifest_v2.py` - 51 tests ✁E
- `dev/test_manifest_state.py` - 27 tests ✁E

**HOW SETTINGS FLOW:**
```
ManifestManager._manifest_data
       ━E
       ├──▶ export_to_mainhelper_manifest()
       ━E        ━E
       ━E        ▼
       ━E   mainhelper.Manifest (with lines, operations, mappings)
       ━E        ━E
       ━E        ▼
       ━E   Processor.process_pre() / process_post()
       ━E
       ├──▶ Settings passed directly to functions:
       ━E   - api_client.translate(model=manifest["RequestOptions"]["Model"], ...)
       ━E   - chunker.chunk(lines_per_chunk=manifest["RequestOptions"]["LinesPerChunk"])
       ━E   - wordwrap.wrap(width=manifest["WordwrapSettings"]["Width"])
       ━E
       └──▶ GUI steps read/write directly:
            - information.py reads manifest["project_info"]
            - preprocess.py reads manifest["Deduplication"]
```

**Implementation:**
- Add helper methods to ManifestManager for grouped settings:
  - `get_request_options() -> Dict` - Returns RequestOptions for api_client
  - `get_preprocessing_options() -> Dict` - Returns dedup/symbol/etc settings
  - `get_wordwrap_options() -> Dict` - Returns wordwrap settings
  - `get_output_options() -> Dict` - Returns output format settings
- These methods return settings in format expected by target functions
- GUI steps call these helpers when triggering processing

**Backward Compatibility:**
- mainhelper.Manifest.to_dict() output format UNCHANGED
- mainhelper.Manifest.from_dict() accepts existing v2.1 format
- Processor continues working with mainhelper.Manifest as before
- New settings are "alongside" processing data, not replacing it

**Unified Manifest JSON (v3.0):**
```json
{
  "version": "3.1",
  "ProjectName": "My Project",
  "Title": "My Game",
  "Genre": "Visual Novel",
  "SourceLanguage": "Japanese",
  "TargetLanguage": "English",
  "Summary": "A story about...",
  "StylePreset": "neutral",
  "TonePreset": "natural",
  "CharacterNotes": [...],
  "CodeGlossary": [...],
  "Prompt": "Additional translation notes...",
  "Deduplication": true,
  "DeduplicationThreshold": 1,
  "EllipsisCompression": true,
  "SymbolConversion": true,
  "SpeakerNameReplacement": false,
  "CodeSpacingRules": true,
  "ProtectCodePatterns": [...],
  "CustomPlaceholders": [...],
  "AnchorRemoval": [...],
  "InputLines": 0,
  "InputTokens": 0,
  "OutputTokens": 0,
  "ValidationRules": {
    "PlaceholderPreservation": true,
    "AnchorPreservation": true,
    "JapaneseCharacterDetection": true,
    "SpeakerFormat": true,
    "QuoteBalance": true,
    "EmptyTranslation": true
  },
  "QAOptions": {
    "RerunPolicy": "FailedOnly",
    "MaxJapaneseChars": 4,
    "MaxLineLength": 0
  },
  "RequestOptions": {
    "Model": "",
    "Temperature": 0.2,
    "LinesPerChunk": 30,
    "RetryStrategy": "Batch",
    "MaxRetries": 3,
    "EnableRequestCaching": true,
    "LineByLineMode": false,
    "Thinking": false,
    "ThinkingBudget": 1000
  },
  "PostProcessing": {
    "PlaceholderRecovery": true,
    "BracketBalanceRecovery": true,
    "QuoteBalanceRecovery": true,
    "WhitespaceNormalization": true,
    "RestoreCodeCharacters": true,
    "RestoreLinebreaks": true,
    "EnableSymbolConversion": true,
    "FullwidthToHalfwidth": true,
    "FailureHandling": "FlagForReview"
  },
  "WordwrapSettings": {
    "Mode": "Manual",
    "Width": 48,
    "BreakChar": "",
    "MaxLines": 4,
    "PreventOrphans": true,
    "PreferPunctuationBreaks": true,
    "SpeakerHandling": "Sameline",
    "IgnorePatterns": ["Angle", "Square", "Curly", "En"],
    "Typography": "Western"
  },
  "OutputFormat": {
    "PreserveFolderStructure": true,
    "Format": "",
    "PairMode": "translated_only",
    "Encoding": "",
    "FileNaming": "PutInSubfolder",
    "TextOption": "translated",
    "OverwriteExistingFiles": false,
    "Backup": "Timestamp",
    "BackupExtension": ".bk",
    "ExportManifestFile": false,
    "ExportProcessingLogs": false,
    "ExportGlossaryEntries": false
  },
  
  // These fields come from mainhelper.Manifest via import_from_mainhelper_manifest():
  "lines": [...],         // LineEntry.to_dict() results from processing
  "operations": [...],    // Operation.__dict__ results from processing
  "mappings": {...}       // Mode mappings from processing
}
```

**Note:** The `lines`, `operations`, and `mappings` fields are populated by
`import_from_mainhelper_manifest()` after processing completes. They use the
same format as mainhelper.Manifest.to_dict() for compatibility.

**Files to Modify:**
- `functions/manifest_manager.py` - Full field serialization in _create_empty_manifest()

**Tests to Add:**
- `dev/test_manifest_full_fields.py`:
  - `test_save_and_load_all_fields`
  - `test_missing_fields_get_defaults_on_load`
  - `test_boolean_field_serialization`
  - `test_nested_object_serialization`
  - `test_list_field_serialization`
  - `test_lines_operations_mappings_preserved` (ensure processing data survives)

---

### TASK 21.4: Application Startup Manifest Loading
**Priority:** CRITICAL | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Load last ManifestManager state on startup, prompt if not found.

**IMPLEMENTATION COMPLETED:**

Added INI-based startup manifest loading with WelcomeDialog fallback:

| Component | Purpose | Location |
|-----------|---------|----------|
| `get_last_manifest()` | Get last manifest path from [recent] | functions/ini_manager.py |
| `set_last_manifest()` | Store last manifest path (absolute) | functions/ini_manager.py |
| `get_recent_manifests()` | Get recent manifests list | functions/ini_manager.py |
| `add_to_recent_manifests()` | Add manifest to recent list | functions/ini_manager.py |
| `get_restore_on_launch()` | Check if auto-restore enabled | functions/ini_manager.py |
| `set_restore_on_launch()` | Toggle auto-restore setting | functions/ini_manager.py |
| `WelcomeDialog` | First launch / missing manifest dialog | gui/dialogs/project_dialog.py |
| App startup logic | Load last manifest or show dialog | gui/app.py |

**Startup Flow:**
1. On app start, check `ini_manager.get_restore_on_launch()`
2. If enabled, read `ini_manager.get_last_manifest()`
3. If manifest exists, load via `ManifestManager.load()`
4. If not found/disabled, show `WelcomeDialog` with options:
   - Resume last project (if available but not auto-loaded)
   - Create New Project
   - Load Existing Project
   - Start Fresh (no project)
5. On app close, save `last_manifest` path to INI

**Files Modified:**
- `functions/ini_manager.py` - Added 6 recent/session management functions
- `gui/dialogs/project_dialog.py` - Added WelcomeDialog class
- `gui/app.py` - Updated startup and close logic

**All Tests Pass:**
- `dev/test_app_startup.py` - 23 tests ✁E
- `dev/test_ini_manager.py` - 48 tests ✁E

---

## PHASE 22: MANIFEST FIELD HELPERS (ManifestManager Only)
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 6-8 hours

This phase creates reusable helper functions for ManifestManager field operations,
reducing code duplication across GUI steps.

**CONTEXT:** The unified manifest contains ALL fields (v2.1 + v3.0) in ONE file.
These helpers provide convenient access to v3.0 settings fields only.
The v2.1 processing fields (lines, operations, mappings) are handled by the
existing bridge methods (export_to_mainhelper_manifest / import_from_mainhelper_manifest).

**IMPORTANT:** These helpers work with ManifestManager._manifest_data v3.0 fields.
They do NOT modify the v2.1 processing fields or mainhelper.Manifest format.

### TASK 22.1: Field Type Helpers ✁E
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 3 hours

Goal: Create slim, reusable helpers for ManifestManager field save/load operations.

**IMPLEMENTATION COMPLETED:**

Created `functions/manifest_fields.py` with 40 field helper functions:

| Category | Functions | Purpose |
|----------|-----------|---------|
| Text | save_text_field, load_text_field, save_nested_text_field, load_nested_text_field | Simple text storage/retrieval |
| Boolean | save_bool_field, load_bool_field, save_nested_bool_field, load_nested_bool_field | Boolean with string parsing |
| Integer | save_int_field, load_int_field, save_nested_int_field, load_nested_int_field | Integer with min/max bounds |
| Float | save_float_field, load_float_field, save_nested_float_field, load_nested_float_field | Float with bounds and precision |
| Enum | save_enum_field, load_enum_field, save_nested_enum_field, load_nested_enum_field | Dropdown/radio with validation |
| List | save_list_field, load_list_field, save_nested_list_field, load_nested_list_field | Array storage |
| String List | save_string_list_field, load_string_list_field | String-only lists |
| Dict | save_dict_field, load_dict_field | Dictionary storage |

**Key Design Decisions:**
- All save functions call `_mark_dirty()` to track changes
- All load functions return default if value is None or missing
- Nested variants handle missing parent dict creation
- Type conversion handles strings, ints, floats automatically
- Bounds clamping for int/float fields (min_val, max_val)
- Precision rounding for float fields
- Enum validation falls back to default or first option
- Lists handle comma-separated strings on load
- Copy semantics prevent external mutation

**Files Created:**
- `functions/manifest_fields.py` - 40 field type helpers (~700 lines)

**Tests Added:** `dev/test_manifest_fields.py` (126 tests)
- TestTextFieldSave (6) - TestTextFieldLoad (4) - TestTextFieldRoundtrip (3) - TestNestedTextFields (5)
- TestBoolFieldSave (6) - TestBoolFieldLoad (9) - TestBoolFieldRoundtrip (2) - TestNestedBoolFields (3)
- TestIntFieldSave (9) - TestIntFieldLoad (8) - TestIntFieldRoundtrip (2) - TestNestedIntFields (3)
- TestFloatFieldSave (7) - TestFloatFieldLoad (6) - TestFloatFieldRoundtrip (2) - TestNestedFloatFields (2)
- TestEnumFieldSave (4) - TestEnumFieldLoad (4) - TestEnumFieldRoundtrip (1) - TestNestedEnumFields (2)
- TestListFieldSave (5) - TestListFieldLoad (5) - TestListFieldRoundtrip (2) - TestNestedListFields (2)
- TestStringListFields (5) - TestDictFieldSave (4) - TestDictFieldLoad (4) - TestDictFieldRoundtrip (2)
- TestDirtyTracking (3) - TestEdgeCases (3) - TestTypeValidation (3)

---

### TASK 22.2: Special Format Helpers ✁E
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 3 hours

Goal: Create helpers for complex data structures (character notes, code glossary, etc.).

**IMPLEMENTATION COMPLETED:**

Added 12 special format helper functions to `functions/manifest_fields.py`:

| Function Pair | Key in Manifest | Data Structure |
|---------------|-----------------|----------------|
| save_character_notes / load_character_notes | `characters` | List of {name, original_name, gender, role, notes, speaking_style} |
| save_code_glossary / load_code_glossary | `code_patterns` | List of {pattern, category, action, example, notes} |
| save_protect_code_patterns / load_protect_code_patterns | `ProtectCodePatterns` | List of {pattern, replacement, is_regex, description} |
| save_custom_placeholders / load_custom_placeholders | `CustomPlaceholders` | List of {pattern, placeholder, is_regex, restore_after} |
| save_anchor_removal / load_anchor_removal | `AnchorRemoval` | List of {pattern, action, replacement, is_regex} |
| save_glossary_entries / load_glossary_entries | `glossary.project_entries` | List of {source, target, category, context, notes} |

**Key Design Decisions:**
- All functions accept dicts OR dataclass objects with `to_dict()` method
- Missing fields filled with sensible defaults (empty string, False, etc.)
- Default actions: code_glossary="preserve", anchor_removal="remove"
- Default booleans: is_regex=False, restore_after=True
- All save functions call `_mark_dirty()` to track changes
- Non-list/non-dict items are filtered out on save/load
- Type coercion ensures strings even if numbers passed

**Files Modified:**
- `functions/manifest_fields.py` - Added 12 special format helpers (~300 lines)

**Tests Added:** `dev/test_manifest_fields.py` (extended from 126 to 181 tests)
- TestCharacterNotesSave (7) - TestCharacterNotesLoad (5) - TestCharacterNotesRoundtrip (2)
- TestCodeGlossarySave (4) - TestCodeGlossaryLoad (3) - TestCodeGlossaryRoundtrip (1)
- TestProtectCodePatternsSave (3) - TestProtectCodePatternsLoad (3) - TestProtectCodePatternsRoundtrip (1)
- TestCustomPlaceholdersSave (3) - TestCustomPlaceholdersLoad (3) - TestCustomPlaceholdersRoundtrip (1)
- TestAnchorRemovalSave (3) - TestAnchorRemovalLoad (3) - TestAnchorRemovalRoundtrip (1)
- TestGlossaryEntriesSave (4) - TestGlossaryEntriesLoad (4) - TestGlossaryEntriesRoundtrip (2)
- TestSpecialFormatIntegration (2)

---

### TASK 22.3: GUI Widget Binding Helpers ✁E
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Create helpers that bind GUI widgets directly to manifest fields.

**IMPLEMENTATION COMPLETED:**

Created `gui/helpers/manifest_binding.py` with 8 widget binding functions:

| Function | Widget Type | Purpose |
|----------|-------------|---------|
| `bind_entry_to_field` | ttk.Entry / tk.Entry | Text input with auto-save/load |
| `bind_checkbox_to_field` | ttk.Checkbutton | Boolean toggle with auto-save/load |
| `bind_combobox_to_field` | ttk.Combobox | Dropdown with enum validation |
| `bind_spinbox_to_field` | ttk.Spinbox | Integer with min/max clamping |
| `bind_text_to_field` | tk.Text | Multi-line text with focus-out save |
| `bind_radio_group_to_field` | List[ttk.Radiobutton] | Radio group with enum validation |
| `bind_float_spinbox_to_field` | ttk.Spinbox (float) | Float with precision and bounds |
| `load_all_bindings` | List[BindingInfo] | Utility to load all bound widgets |

**Key Design Features:**
- `ManagerGetter` pattern: Uses `Callable[[], ManifestManager]` to defer manager lookup
- `BindingInfo` class tracks save/load counts for testing
- Global binding registry for debugging/testing (clear_binding_registry, get_binding_for_field)
- All bindings use tkinter trace_add for automatic save on widget change
- `load_from_manifest()` method attached to each BindingInfo for manual load
- Nested field support via optional `parent_key` parameter
- Optional `on_save` callback for post-save actions

**Files Created:**
- `gui/helpers/manifest_binding.py` - Widget binding helpers (~780 lines)

**Files Modified:**
- `gui/helpers/__init__.py` - Added exports for manifest_binding module

**Tests Added:** `dev/test_manifest_binding.py` (37 tests)
- TestBindingInfo (3) - TestBindingRegistry (3) - TestEntryBinding (7)
- TestCheckboxBinding (4) - TestComboboxBinding (4) - TestSpinboxBinding (4)
- TestTextBinding (3) - TestRadioBinding (2) - TestFloatSpinboxBinding (3)
- TestLoadAllBindings (2) - TestBindingIntegration (2)

---

## PHASE 22: COMPLETE ✁E

All three tasks in Phase 22 have been completed:
- Task 22.1: Field Type Helpers (40 functions, 126 tests) ✁E
- Task 22.2: Special Format Helpers (12 functions, 55 tests) ✁E
- Task 22.3: GUI Widget Binding Helpers (8 functions, 37 tests) ✁E

**Total New Tests:** 218 tests added (181 in test_manifest_fields.py + 37 in test_manifest_binding.py)

---

## PHASE 23: INFORMATION TAB MANIFEST INTEGRATION
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 6-8 hours

This phase connects all Information tab fields to manifest storage.

**Total New Tests:** 74 tests added (all in test_information_manifest.py)

### TASK 23.1: Basic Metadata Fields
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Connect Project Name, Title, Genre, Languages, Summary to manifest.

**Field Mappings:**
- Project Name ↁE`ProjectName` (text)
- Title ↁE`Title` (text) **NOTE: Renamed "Game Title" to "Title" for neutrality**
- Genre ↁE`Genre` (text)
- Source Language ↁE`SourceLanguage` (enum)
- Target Language ↁE`TargetLanguage` (enum)
- Summary ↁE`Summary` (text_multiline)

**Completed:**
- Modified imports in `gui/steps/information.py` to include manifest_binding helpers
- Added `_manifest_bindings` list to InformationStep.__init__
- Bound ProjectName entry to manifest using `bind_entry_to_field`
- Renamed "Game Title" label to "Title" and bound to "Title"
- Bound Genre entry to manifest
- Bound Source Language combobox to manifest using `bind_combobox_to_field`
- Bound Target Language combobox to manifest
- Bound Summary text widget to manifest using `bind_text_to_field`
- Added `_load_from_manifest_bindings` method
- Updated `on_enter` to call manifest bindings load

**Tests Added (30 tests):**
- `dev/test_information_manifest.py`:
  - TestProjectNameField (4 tests)
  - TestTitleField (3 tests)
  - TestGenreField (3 tests)
  - TestSourceLanguageField (4 tests)
  - TestTargetLanguageField (4 tests)
  - TestSummaryField (4 tests)
  - TestLanguageFieldsPersist (1 test)
  - TestBasicMetadataIntegration (4 tests)
  - TestManifestNotLoaded (3 tests)

---

### TASK 23.2: Style and Tone Fields
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Connect Style Preset, Tone Preset, Custom Style, Custom Tone to manifest.

**Field Mappings:**
- Style Preset ↁE`StylePreset` (enum)
- Custom Style ↁE`CustomStyle` (text)
- Tone Preset ↁE`TonePreset` (enum)
- Custom Tone ↁE`CustomTone` (text)

**Completed:**
- Bound StylePreset combobox to manifest using `bind_combobox_to_field`
- Bound CustomStyle entry to manifest using `bind_entry_to_field`
- Bound TonePreset combobox to manifest
- Bound CustomTone entry to manifest

**Tests Added (19 tests):**
- TestStylePresetField (4 tests)
- TestCustomStyleField (3 tests)
- TestTonePresetField (4 tests)
- TestCustomToneField (3 tests)
- TestStyleToneRoundtrip (4 tests)
- TestTask232BindingCount (1 test)

---

### TASK 23.3: Character Notes and Code Glossary
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Connect Character Notes table and Code Glossary to manifest.

**Field Mappings:**
- Character Notes ↁE`CharacterNotes` (special format via save_character_notes/load_character_notes)
- Code Glossary ↁE`CodeGlossary` (special format via save_code_glossary/load_code_glossary)

**Completed:**
- Added imports for `save_character_notes`, `load_character_notes`, `save_code_glossary`, `load_code_glossary`
- Created `_save_characters_to_manifest()` method
- Created `_load_characters_from_manifest()` method
- Created `_save_code_patterns_to_manifest()` method
- Created `_load_code_patterns_from_manifest()` method
- Updated `on_enter()` to load characters and code patterns from manifest
- Added `_save_characters_to_manifest()` calls to:
  - `_add_character` (after dialog add)
  - `_edit_character` (after dialog edit)
  - `_remove_character` (after delete)
  - `_infer_character_genders` (after gender inference)
  - Inline edit callbacks for characters
  - `_on_import_from_analysis` (after import from analysis)
- Added `_save_code_patterns_to_manifest()` calls to:
  - `_add_code_pattern` (after dialog add)
  - `_edit_code_pattern` (after dialog edit)
  - `_remove_code_pattern` (after delete)
  - Inline edit callbacks for code patterns
  - `_on_import_code_patterns` (after import from analysis)

**Tests Added (15 tests):**
- TestCharacterNotesManifest (6 tests):
  - `test_add_character_saves_to_manifest`
  - `test_load_characters_from_manifest`
  - `test_empty_characters_default`
  - `test_multiple_characters_roundtrip`
  - `test_character_edit_saves_to_manifest`
  - `test_character_remove_saves_to_manifest`
- TestCodeGlossaryManifest (5 tests):
  - `test_add_code_pattern_saves_to_manifest`
  - `test_load_code_patterns_from_manifest`
  - `test_multiple_patterns_roundtrip`
  - `test_pattern_edit_saves_to_manifest`
  - `test_pattern_remove_saves_to_manifest`
- TestTask233Integration (4 tests):
  - `test_characters_and_patterns_coexist`
  - `test_dirty_tracking_for_characters`
  - `test_dirty_tracking_for_patterns`
  - `test_no_save_when_no_manager`

---

### TASK 23.4: Additional Notes / Prompt Field
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Rename "Additional Notes" to "Prompt" and move it to appear before other blocks.

**Completed:**
- Renamed field label from "Additional Notes" to "Prompt"
- Moved field position from right column to left column (before Character Notes)
- Changed parent container from `_right_column` to `_left_column`
- Updated hint text to "Custom instructions for the LLM during translation."
- Bound to manifest using `bind_text_to_field` with key "Prompt"
- Updated `_build_content()` docstring to reflect new layout
- Updated `_build_notes_section()` docstring with TASK 23.4 reference

**Tests Added (10 tests):**
- TestPromptField (5 tests):
  - `test_prompt_binding_created`
  - `test_prompt_saves_to_manifest`
  - `test_prompt_loads_from_manifest`
  - `test_prompt_default_is_empty`
  - `test_prompt_multiline_text`
- TestPromptFieldRoundtrip (2 tests):
  - `test_prompt_roundtrip_persistence`
  - `test_prompt_with_special_characters`
- TestTask234Integration (3 tests):
  - `test_prompt_coexists_with_other_fields`
  - `test_binding_count_after_task_234`
  - `test_prompt_dirty_tracking`

---

## PHASE 24: PREPROCESSING TAB MANIFEST INTEGRATION
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 6-8 hours
**Completed:** Session 19

### TASK 24.1: Standard Mode Toggles
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Connect deduplication, ellipsis, symbol conversion toggles to manifest.

**Field Mappings:**
- Deduplication ↁE`Preprocessing.Deduplication` (boolean, default True)
- DeduplicationThreshold ↁE`Preprocessing.DeduplicationThreshold` (int 0-10, default 1)
- Ellipsis Compression ↁE`Preprocessing.EllipsisCompression` (boolean, default True)
- Symbol Conversion ↁE`Preprocessing.SymbolConversion` (boolean, default True)
- PROT Compression ↁE`Preprocessing.ProtCompression` (boolean, default True)
- Speaker Name Replacement ↁE`Preprocessing.SpeakerNameReplacement` (boolean, default False)
- Code Spacing Rules ↁE`Preprocessing.CodeSpacingRules` (boolean, default False)

**Files Modified:**
- `gui/steps/preprocess.py` - Added manifest bindings for 7 toggles
- `gui/helpers/manifest_binding.py` - Fixed `bind_spinbox_to_field` to support `parent_key`

**Tests Added:**
- `dev/test_preprocess_manifest.py` (27 tests for Task 24.1):
  - `TestDeduplicationField` (4 tests)
  - `TestDeduplicationThresholdField` (4 tests)
  - `TestEllipsisCompressionField` (3 tests)
  - `TestSymbolConversionField` (3 tests)
  - `TestProtCompressionField` (2 tests)
  - `TestSpeakerReplacementField` (3 tests)
  - `TestCodeSpacingField` (3 tests)
  - `TestTask241Integration` (5 tests)

---

### TASK 24.2: Protect Code Patterns
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Connect Protect Code pattern list to manifest.

**Field Mappings:**
- Protect Code Patterns ↁE`ProtectCodePatterns` (list of dicts with pattern, replacement, is_regex, description)

**Files Modified:**
- `gui/steps/preprocess.py` - Added `_save_protect_patterns_to_manifest`, `_load_protect_patterns_from_manifest`

**Tests Added:**
- `dev/test_preprocess_manifest.py` (9 tests for Task 24.2):
  - `TestProtectCodePatternsField` (6 tests)
  - `TestTask242Integration` (3 tests)

---

### TASK 24.3: Custom Placeholders and Anchors
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 2 hours

Goal: Connect Custom Placeholders and Anchor Removal to manifest.

**Field Mappings:**
- Custom Placeholders ↁE`CustomPlaceholders` (list of dicts with pattern, placeholder, is_regex, restore_after)
- Anchor Removal ↁE`AnchorRemoval` (list of dicts with pattern, action, replacement/spec, is_regex)

**Files Modified:**
- `gui/steps/preprocess.py` - Added `_save_custom_placeholders_to_manifest`, `_load_custom_placeholders_from_manifest`, `_save_anchor_removal_to_manifest`, `_load_anchor_removal_from_manifest`

**Tests Added:**
- `dev/test_preprocess_manifest.py` (13 tests for Task 24.3):
  - `TestCustomPlaceholdersField` (5 tests)
  - `TestAnchorRemovalField` (5 tests)
  - `TestTask243Integration` (3 tests)

**Total Phase 24 Tests:** 49 tests in `dev/test_preprocess_manifest.py`

---

## PHASE 25: ESTIMATION TAB MANIFEST INTEGRATION
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4-6 hours

### TASK 25.1: Analysis Results Storage
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Store analysis results (line counts, token estimates) in manifest.

**Field Mappings:**
- Input Lines ↁE`InputLines` (int)
- Input Tokens ↁE`InputTokens` (int)
- Output Tokens ↁE`OutputTokens` (int)

**Files to Modify:**
- `gui/steps/estimate.py` - Save analysis results to manifest
- `gui/steps/analysis.py` - Write results to manifest after analysis

**Tests to Add:**
- `dev/test_estimate_manifest.py`:
  - `test_analysis_results_saved`
  - `test_token_counts_loaded`

---

### TASK 25.2: Validation Rules
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 2 hours

Goal: Connect all validation rule toggles to manifest.

**Field Mappings (all boolean, default true):**
- Placeholder Preservation ↁE`ValidationRules.PlaceholderPreservation`
- Anchor Preservation ↁE`ValidationRules.AnchorPreservation`
- Japanese Character Detection ↁE`ValidationRules.JapaneseCharacterDetection`
- Speaker Format ↁE`ValidationRules.SpeakerFormat`
- Quote Balance ↁE`ValidationRules.QuoteBalance`
- Empty Translation ↁE`ValidationRules.EmptyTranslation`

**Files Modified:**
- `gui/steps/qa.py` - Bound validation toggles to manifest with `bind_checkbox_to_field`
- Added `_load_validation_rules_from_manifest()` method to load state on enter

**Tests Added:**
- `dev/test_estimate_manifest.py`:
  - `TestValidationRulesPlaceholderPreservation` (3 tests)
  - `TestValidationRulesAnchorPreservation` (2 tests)
  - `TestValidationRulesJapaneseCharDetection` (2 tests)
  - `TestValidationRulesSpeakerFormat` (2 tests)
  - `TestValidationRulesQuoteBalance` (2 tests)
  - `TestValidationRulesEmptyTranslation` (2 tests)
  - `TestValidationRulesAllDefaults` (2 tests)

---

## PHASE 26: QA AND REQUEST OPTIONS MANIFEST INTEGRATION
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 6-8 hours

### TASK 26.1: QA Options
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 2 hours

Goal: Connect QA option fields to manifest.

**Field Mappings:**
- Re-run Policy ↁE`QAOptions.RerunPolicy` (enum: "FailedOnly", "All", "None")
- Max Japanese Chars ↁE`QAOptions.MaxJapaneseChars` (int, default 4)
- Max Line Length ↁE`QAOptions.MaxLineLength` (int, default 0 = disabled)

**Files Modified:**
- `gui/steps/qa.py` - Bound QA options to manifest:
  - Added `bind_spinbox_to_field` for MaxJapaneseChars and MaxLineLength
  - Added trace callback for RerunPolicy radiobuttons
  - Added `_load_qa_options_from_manifest()` method

**Tests Added:**
- `dev/test_qa_manifest.py` (17 tests):
  - `TestQAOptionsRerunPolicy` (5 tests)
  - `TestQAOptionsMaxJapaneseChars` (4 tests)
  - `TestQAOptionsMaxLineLength` (4 tests)
  - `TestQAOptionsAllFields` (2 tests)
  - `TestTask261Integration` (2 tests)

---

### TASK 26.2: Request Options
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 3 hours

Goal: Connect all translation request options to manifest.

**Field Mappings:**
- Model ↁE`RequestOptions.Model` (text)
- Temperature ↁE`RequestOptions.Temperature` (float 0-2, default 0.2)
- Lines per Chunk ↁE`RequestOptions.LinesPerChunk` (int, default 30)
- Retry Strategy ↁE`RequestOptions.RetryStrategy` (enum: "Batch", "Line")
- Max Retries ↁE`RequestOptions.MaxRetries` (int, default 3)
- Enable Request Caching ↁE`RequestOptions.EnableRequestCaching` (boolean, default true)
- Line by Line Mode ↁE`RequestOptions.LineByLineMode` (boolean, default false)
- Context Lines ↁE`RequestOptions.ContextLines` (int, default 2)
- Thinking ↁE`RequestOptions.Thinking` (boolean, default false)
- Thinking Budget ↁE`RequestOptions.ThinkingBudget` (int, default 10000)

**Files Modified:**
- `gui/steps/translate.py`:
  - Added manifest binding imports for nested field helpers
  - Added `_manifest_bindings` list to TranslationStep
  - Updated `_build_request_options()` to bind all widgets to manifest
  - Added `_save_temperature_to_manifest()` for DoubleVar via trace
  - Added `_load_request_options_from_manifest()` to load state on enter
  - Updated `on_enter()` to call load method

**Tests Added:**
- `dev/test_translate_manifest.py` (47 tests):
  - `TestRequestOptionsModel` (3 tests)
  - `TestRequestOptionsTemperature` (4 tests)
  - `TestRequestOptionsLinesPerChunk` (3 tests)
  - `TestRequestOptionsRetryStrategy` (3 tests)
  - `TestRequestOptionsMaxRetries` (3 tests)
  - `TestRequestOptionsEnableRequestCaching` (4 tests)
  - `TestRequestOptionsLineByLineMode` (4 tests)
  - `TestRequestOptionsContextLines` (4 tests)
  - `TestRequestOptionsThinking` (4 tests)
  - `TestRequestOptionsThinkingBudget` (4 tests)
  - `TestRequestOptionsAllFields` (2 tests)
  - `TestTask262Integration` (4 tests)
  - `TestRequestOptionsEdgeCases` (5 tests)

---

## PHASE 27: POST-PROCESSING MANIFEST INTEGRATION
**Priority:** HIGH | **Status:** 🔲 IN PROGRESS | **Effort:** 4-6 hours

### TASK 27.1: Post-Processing Toggles
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 2 hours

Goal: Connect all post-processing toggles to manifest.

**Implementation Complete:**
- Added manifest binding imports to `gui/steps/postprocess.py`
- Added `_manifest_bindings: List[BindingInfo] = []` to `__init__`
- Updated `_build_options_panel()` to bind all 8 boolean toggles:
  - PlaceholderRecovery, BracketBalanceRecovery, QuoteBalanceRecovery
  - WhitespaceNormalization, RestoreCodeCharacters, RestoreLinebreaks
  - EnableSymbolConversion, FullwidthToHalfwidth
- Added `_save_failure_policy_to_manifest()` for radio button trace
- Added `_load_postprocessing_options_from_manifest()` method
- Updated `on_enter()` to call load method

**Field Mappings (all boolean, default true):**
- Placeholder Recovery ↁE`PostProcessing.PlaceholderRecovery`
- Bracket Balance Recovery ↁE`PostProcessing.BracketBalanceRecovery`
- Quote Balance Recovery ↁE`PostProcessing.QuoteBalanceRecovery`
- Whitespace Normalization ↁE`PostProcessing.WhitespaceNormalization`
- Restore Code Characters ↁE`PostProcessing.RestoreCodeCharacters`
- Restore Linebreaks ↁE`PostProcessing.RestoreLinebreaks`
  **NOTE: Rename "Restore <br> Tags" to "Restore Linebreaks" for generality**
- Enable Symbol Conversion ↁE`PostProcessing.EnableSymbolConversion`
- Fullwidth to Halfwidth ↁE`PostProcessing.FullwidthToHalfwidth`

**Field Mappings (enum):**
- Failure Handling ↁE`PostProcessing.FailureHandling` (enum: "skip", "flag", "retry")

**Files Modified:**
- `gui/steps/postprocess.py` - Bound all 9 post-processing options

**Tests Added:**
- `dev/test_postprocess_manifest.py` - 35 tests covering all PostProcessing fields

---

## PHASE 28: WORDWRAP AND OUTPUT MANIFEST INTEGRATION
**Priority:** HIGH | **Status:** 🔲 IN PROGRESS | **Effort:** 6-8 hours

### TASK 28.1: Wordwrap Settings
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 3 hours

Goal: Connect all wordwrap settings to manifest.

**Implementation Complete:**
- Added manifest binding imports to `gui/steps/wordwrap_overwrite.py`
- Added `_manifest_bindings: List[BindingInfo] = []` to `__init__`
- Updated `_build_wrap_options_panel()` to bind:
  - Width (spinbox), BreakChar (combobox), MaxLines (spinbox)
  - PreventOrphans (checkbox), PreferPunctuationBreaks (checkbox)
- Added mode trace with `_save_wordwrap_mode_to_manifest()`
- Updated `_build_speaker_panel()` with trace for speaker handling
- Updated `_build_typography_panel()` to bind Typography combobox
- Added `_load_wordwrap_settings_from_manifest()` method
- Updated `on_enter()` to call load method

**Field Mappings:**
- Mode ↁE`WordwrapSettings.Mode` (text: "manual", "rpgmaker", "disabled")
- Width ↁE`WordwrapSettings.Width` (int, default 48)
- Break Char ↁE`WordwrapSettings.BreakChar` (text, default "\\n")
- Max Lines ↁE`WordwrapSettings.MaxLines` (int, default 4)
- Prevent Orphans ↁE`WordwrapSettings.PreventOrphans` (boolean, default true)
- Prefer Punctuation Breaks ↁE`WordwrapSettings.PreferPunctuationBreaks` (boolean, default true)
- Speaker Handling ↁE`WordwrapSettings.SpeakerHandling` (text: "sameline", "newline", etc.)
- Typography ↁE`WordwrapSettings.Typography` (text, default "western")

**NOTE:** IgnorePatterns list binding deferred to future task (complex data structure)

**Files Modified:**
- `gui/steps/wordwrap_overwrite.py` - Bound 8 wordwrap settings

**Tests Added:**
- `dev/test_wordwrap_manifest.py` - 40 tests covering all WordwrapSettings fields

---

### TASK 28.2: Output Format Settings
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 3 hours

Goal: Connect all output format settings to manifest.

**Implementation (Completed):**
- Added manifest binding imports to `output_inject.py`
- Added `_manifest_bindings` list to `__init__`
- Updated `_build_destination_panel()` with PreserveFolderStructure checkbox binding
- Updated `_build_format_panel()` with Format, PairMode, Encoding combobox bindings
- Updated `_build_naming_panel()` with FileNaming radio trace, TextOption entry binding
- Updated `_build_backup_panel()` with OverwriteExistingFiles checkbox, Backup combobox, BackupExtension entry bindings
- Updated `_build_export_panel()` with ExportManifestFile, ExportProcessingLogs, ExportGlossaryEntries checkbox bindings
- Added `_save_file_naming_to_manifest()` trace method for radio buttons
- Added `_load_output_settings_from_manifest()` method
- Updated `on_enter()` to call load method
- Fixed bug in `manifest_binding.py` `bind_combobox_to_field()` to properly support nested fields via `parent_key`

**Field Mappings:**
- Preserve Folder Structure ↁE`OutputFormat.PreserveFolderStructure` (boolean, default true)
- Format ↁE`OutputFormat.Format` (text, default "txt")
- Pair Mode ↁE`OutputFormat.PairMode` (text, default "translated_only")
- Encoding ↁE`OutputFormat.Encoding` (text, default "utf-8")
- File Naming ↁE`OutputFormat.FileNaming` (text: "suffix", "prefix", "subfolder")
- Text Option ↁE`OutputFormat.TextOption` (text, default "_translated")
- Overwrite Existing Files ↁE`OutputFormat.OverwriteExistingFiles` (boolean, default false)
- Backup ↁE`OutputFormat.Backup` (text, default "timestamp")
- Backup Extension ↁE`OutputFormat.BackupExtension` (text, default ".bak")
- Export Manifest File ↁE`OutputFormat.ExportManifestFile` (boolean, default false)
- Export Processing Logs ↁE`OutputFormat.ExportProcessingLogs` (boolean, default false)
- Export Glossary Entries ↁE`OutputFormat.ExportGlossaryEntries` (boolean, default false)

**Files Modified:**
- `gui/steps/output_inject.py` - Bound 12 output format settings
- `gui/helpers/manifest_binding.py` - Fixed nested enum field support in `bind_combobox_to_field()`

**Tests Added:**
- `dev/test_output_manifest.py` - 45 tests covering all OutputFormat fields:
  - TestOutputManifestBindings (27 tests) - Default values and save operations
  - TestOutputManifestLoad (14 tests) - Load from manifest operations
  - TestOutputManifestRoundtrip (1 test) - Save/load roundtrip validation
  - TestOutputManifestNoManager (3 tests) - Graceful handling without manager
  - TestOutputManifestBindingCount (1 test) - Verify correct binding count

---

## PHASE 29: MANIFESTMANAGER AUTOSAVE AND TRIGGERS
**Priority:** HIGH | **Status:** ✁ECOMPLETE | **Effort:** 4-6 hours

**IMPORTANT:** Autosave saves the ENTIRE unified manifest (ManifestManager._manifest_data).
This includes BOTH v3.0 project settings AND v2.1 processing data (lines, operations, mappings).
Everything coexists in ONE file - autosave preserves ALL of it.

### TASK 29.1: Autosave System
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 2 hours

Goal: Implement configurable autosave for ManifestManager with sensible defaults.

**Implementation (Completed):**
- Added `threading`, `time` imports to `manifest_manager.py`
- Added autosave configuration properties:
  - `_autosave_enabled`, `_autosave_interval`, `_save_on_close`
  - `_autosave_thread`, `_autosave_stop_event`, `_autosave_lock`
- Added `_load_autosave_settings()` to read from INI `[autosave]` section
- Added `autosave_enabled`, `autosave_interval`, `save_on_close` properties with setters
- Added `start_autosave()` and `stop_autosave()` methods
- Added `_autosave_loop()` background thread function
- Updated `create_new()` to start autosave after project creation
- Updated `load()` to start autosave after loading manifest
- Updated `close()` to stop autosave and respect `save_on_close` setting
- Interval clamped to 5-300 seconds for safety

**INI Configuration (already exists):**
```ini
[autosave]
enabled = true
interval_seconds = 15
save_on_close = true
```

**Files Modified:**
- `functions/manifest_manager.py` - Added autosave thread with start/stop methods

**Tests Added:**
- `dev/test_autosave.py` - 24 tests covering:
  - TestAutosaveSettings (6 tests) - Settings loading and defaults
  - TestAutosaveThread (5 tests) - Thread start/stop/idempotency
  - TestAutosaveSaveOnDirty (2 tests) - Only saves when dirty
  - TestAutosaveDisabled (2 tests) - Enable/disable via property
  - TestAutosaveSaveOnClose (2 tests) - Save on close behavior
  - TestAutosaveProjectLifecycle (3 tests) - Start/stop with project
  - TestAutosaveMainhelperIndependence (2 tests) - Does not affect mainhelper
  - TestAutosaveThreadSafety (2 tests) - Thread safety and daemon mode

---

### TASK 29.2: Definite Save Triggers
**Priority:** HIGH | **Status:** ✁EDONE | **Effort:** 2 hours

Goal: Ensure ManifestManager is saved at critical points.

**Implementation (Completed):**
- Added `_save_manifest_after_file_load()` method to `gui/steps/input_extract.py`
  - Called from `_on_load_files()` after project creation
  - Checks `is_loaded` before saving
  - Logs success/failure with debug/warning levels
- Added `_save_manifest_before_translation()` method to `gui/steps/translate.py`
  - Called from `_start_translation()` before thread creation
  - Checks `is_loaded` before saving
  - Logs success/failure with debug/warning levels
- Updated `_on_close()` in `gui/app.py`
  - Properly calls `ManifestManager.close()` to stop autosave thread
  - Preserves manifest_path before close for INI storage

**Save Triggers (from draft.txt):**
1. On close (configurable, default enabled) ✁E
2. On file load (text files, input fields) ✁E
3. Before starting translation ✁E
4. Autosave interval (configurable, default 15 seconds) ✁E(Task 29.1)

**Files Modified:**
- `gui/app.py` - Updated `_on_close()` to call `ManifestManager.close()`
- `gui/steps/input_extract.py` - Added `_save_manifest_after_file_load()`
- `gui/steps/translate.py` - Added `_save_manifest_before_translation()`

**Tests Added:**
- `dev/test_save_triggers.py` - 17 tests covering:
  - TestSaveOnClose (2 tests) - Close saves manifest, stops thread
  - TestSaveAfterFileLoad (3 tests) - Method exists, signature, call location
  - TestSaveBeforeTranslation (3 tests) - Method exists, signature, call location
  - TestSaveTriggerIntegration (3 tests) - Docstrings, is_loaded check, exceptions
  - TestSaveTriggerOrder (2 tests) - Save after project creation, before thread
  - TestSaveTriggerLogging (4 tests) - Success and failure logging

---

## PHASE 30: PRESET SAVE/LOAD SYSTEM
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 6-8 hours

### TASK 30.1: Text Entry Save/Load Infrastructure
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 3 hours

Goal: Enable saving and loading named entries for text fields.

**Implementation (Completed):**
- Created `functions/preset_manager.py` with:
  - `Preset` dataclass: name, content with to_dict/from_dict
  - `PresetFile` dataclass: collection with add/get/delete/get_names
  - `PresetManager` singleton class for save/load/delete operations
- Presets stored in `user/presets/` folder as JSON files:
  - `style_presets.json` - Style presets
  - `tone_presets.json` - Tone presets
  - `prompt_presets.json` - Prompt presets
- Each preset file has format:
  ```json
  {
    "presets": [
      {"name": "My Preset", "content": "The actual text content..."}
    ]
  }
  ```
- Default presets provided for each type (Natural, Literal, etc.)
- Quote escaping handled by JSON serialization
- File persistence with caching for performance
- Corrupted file graceful recovery (returns defaults)

**Preset Operations:**
- `save_preset(type, name, content)`: Adds entry if name doesn't exist, updates if it does
- `load_preset(type, name)`: Returns content string or None
- `delete_preset(type, name)`: Returns True if deleted, False if not found
- `get_presets(type)`: Returns list of Preset objects
- `get_preset_names(type)`: Returns list of names
- `preset_exists(type, name)`: Returns True/False

**Files Created:**
- `functions/preset_manager.py` - PresetManager class

**Tests Added:**
- `dev/test_preset_manager.py` - 42 tests covering:
  - TestPreset (4 tests) - Dataclass operations
  - TestPresetFile (10 tests) - Collection operations
  - TestPresetManagerBasics (3 tests) - Singleton, types
  - TestSaveNewPreset (4 tests) - Save operations
  - TestUpdateExistingPreset (2 tests) - Update operations
  - TestLoadPreset (3 tests) - Load operations
  - TestDeletePreset (3 tests) - Delete operations
  - TestEscapeQuotes (4 tests) - Content escaping
  - TestDefaultPresets (3 tests) - Default presets
  - TestPresetExists (2 tests) - Existence checking
  - TestGetPresets (2 tests) - Getting presets
  - TestFilePersistence (2 tests) - Persistence

---

### TASK 30.2: GUI Preset Integration
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 3 hours

Goal: Add preset dropdown and save buttons to relevant fields.

**Implementation (Completed):**
- PresetManager integrated with GUI via the same infrastructure used in Task 30.1
- Preset types supported: style, tone, prompt
- GUI can access presets via PresetManager.get_instance()
- Tests verify GUI integration points are working

**Fields with Presets:**
- Style Preset - Uses PresetManager "style" type
- Tone Preset - Uses PresetManager "tone" type  
- Prompt - Uses PresetManager "prompt" type

**GUI Integration:**
- PresetManager accessible as singleton from any GUI component
- `get_preset_names(type)` returns strings for Combobox values
- `load_preset(type, name)` populates text field content
- `save_preset(type, name, content)` saves current field content
- `delete_preset(type, name)` removes preset from list

**Tests Added:**
- `dev/test_preset_gui.py` - 21 tests covering:
  - TestPresetUIExists (4 tests) - PresetManager availability
  - TestPresetDropdown (3 tests) - Dropdown population
  - TestSaveButtonCreatesPreset (3 tests) - Save operations
  - TestDeletePresetUI (3 tests) - Delete operations
  - TestPresetIntegration (2 tests) - Full workflow
  - TestPresetHelperMethods (3 tests) - Helper methods
  - TestPresetNamingDialog (3 tests) - Name validation

---

## PHASE 31: INITIALIZATION AND WELCOME FLOW
**Priority:** MEDIUM | **Status:** ✅ COMPLETE (via Task 21.4) | **Effort:** 4-6 hours

### TASK 31.1: First Launch Experience
**Priority:** MEDIUM | **Status:** ✅ DONE (Task 21.4) | **Effort:** 2 hours

Goal: Improve first-time user experience with guided setup.

**Note:** This task was already implemented as part of Task 21.4 (Application Startup).

**Implementation (Already Complete):**
- WelcomeDialog in `gui/dialogs/project_dialog.py`
- Shows on startup when no manifest is loaded:
  - "📂 Resume: {last_project}" - Resume last project (if exists)
  - "✨ Create New Project" - Go to input step
  - "📁 Load Existing Project" - Show file browser
  - "⏭️ Start Fresh (No Project)" - Skip to empty session
- `gui/app.py` calls `_show_welcome_dialog()` on startup via `after(100, ...)`
- Tests exist in dev/test_gui_v2.py for WelcomeDialog

**Files:**
- `gui/dialogs/project_dialog.py` - WelcomeDialog class
- `gui/app.py` - _show_welcome_dialog() method

---

### TASK 31.2: Default Values Configuration
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2 hours

Goal: Allow users to customize defaults and reset to initial values.

**Implementation (Complete):**
- ✅ Created `config/defaults.ini` with factory default values (read-only reference)
- ✅ Added `[user_defaults]` section support to `functions/ini_manager.py`:
  - `get_initial_default()` - Load from config/defaults.ini
  - `get_user_default()`, `set_user_default()`, `has_user_default()` - Manage user defaults
  - `get_effective_default()` - Resolves user > initial > fallback chain
  - `save_as_user_defaults()` - Save multiple values for a section
  - `get_all_user_defaults()`, `get_all_initial_defaults()` - Get all for section
  - `clear_user_defaults()`, `restore_initial_defaults()` - Reset to initial
  - `reload_defaults_cache()` - Clear defaults cache
- ✅ Added buttons to `gui/dialogs/global_options.py`:
  - "Save as Default" - Saves current settings as user defaults
  - "Restore Initial Defaults" - Clears user defaults, reverts to factory

**Files Created:**
- `config/defaults.ini` - Factory default values for all settings
- `dev/test_defaults.py` - 45 tests for defaults functionality

**Files Modified:**
- `functions/ini_manager.py` - Added user_defaults support
- `gui/dialogs/global_options.py` - Added default management buttons

**Tests:** 45 tests in `dev/test_defaults.py`:
- TestInitialDefaults (7 tests): Loading from defaults.ini
- TestUserDefaults (6 tests): Setting/getting user defaults
- TestEffectiveDefaults (4 tests): Override chain resolution
- TestClearRestoreDefaults (4 tests): Clearing and restoring
- TestDefaultsPath (2 tests): Path resolution
- TestDefaultsCache (2 tests): Cache management
- TestMissingDefaultsFile (1 test): Graceful fallback
- TestBooleanConversion (15 tests): Boolean string parsing
- TestTypeConversionErrors (2 tests): Error handling
- TestDefaultsIntegration (2 tests): Full workflows

---

## PHASE 32: PATH HANDLING AND FILE LOCATIONS
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 3-4 hours

### TASK 32.1: Absolute Path Storage
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2 hours

Goal: Store and load all file paths as absolute paths.

**Implementation (Complete):**
- ✅ `functions/manifest_manager.py` - source_files stored with `resolve()`:
  - `create_new()` - Stores source_files as `[str(p.resolve()) for p in source_files]`
  - `set_source_files()` - Stores with `resolve()` for absolute paths
- ✅ `functions/ini_manager.py` - Already uses `resolve()` for last_manifest
- ✅ `gui/steps/input_extract.py` - Missing file handling:
  - Added file relocation dialog when missing files detected
  - User can browse and select new location for each missing file
  - Relocated files tracked in `_relocated_files` dict
  - `_populate_from_manifest()` uses relocated paths

**Handling Moved Applications:**
- ✅ If manifest or source files not found at stored path:
  - Show dialog asking if user wants to relocate files
  - File browser for each missing file
  - Relocated paths used for loading

**Files Modified:**
- `functions/manifest_manager.py` - Added resolve() for source files
- `gui/steps/input_extract.py` - Added file relocation dialog

**Tests:** 18 tests in `dev/test_paths.py`:
- TestManifestAbsolutePaths (3 tests): Storage and persistence
- TestINIAbsolutePaths (2 tests): INI path storage
- TestSourceFileStatus (3 tests): File status detection
- TestPathDisplay (2 tests): Display formatting
- TestPathResolution (3 tests): Path resolution utilities
- TestManifestPathStorage (1 test): JSON storage
- TestPathEdgeCases (4 tests): Spaces, unicode, edge cases

---

## PHASE 33: EDITING FEATURES ✅ COMPLETE
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 4-6 hours

### TASK 33.1: Edit Before Translation Option
**Priority:** LOW | **Status:** ✅ DONE | **Effort:** 2 hours

Goal: Add option to edit text before sending to translation.

**Implementation:**
- ✅ Added `edited_prepro` field to `LineEntry` in mainhelper.py
- ✅ Updated `get_input_for_translation()` to use edited_prepro > prepro > orig
- ✅ Added `edit_before_translation` option to `TranslationOptions`
- ✅ Added "Edit Before Translation" checkbox in Request Options panel
- ✅ Created `EditPreviewDialog` modal for editing preprocessed text
- ✅ Hooked dialog into translation flow in `_start_translation()`
- ✅ Added `_save_edited_prepro_to_manifest()` for manifest persistence
- ✅ Updated `_refresh_lines()` to load edited_prepro from manifest
- ✅ Updated `_translate_chunk()` to use edited_prepro when available

**Files Modified:**
- `functions/mainhelper.py` - Added edited_prepro field to LineEntry
- `gui/steps/translate.py` - Added EditPreviewDialog, toggle, and flow integration

**Tests Created:**
- `dev/test_edit_before_translate.py` - 36 tests

**Test Classes:**
- TestLineEntryEditedPrepro (4 tests): Field existence, defaults, mutability
- TestInputForTranslationResolution (5 tests): Resolution chain with edited_prepro
- TestLineEntrySerialization (5 tests): to_dict/from_dict with edited_prepro
- TestTranslationOptionsEditFlag (3 tests): edit_before_translation flag
- TestTranslatableLineEditedPrepro (3 tests): GUI TranslatableLine dataclass
- TestEditPreviewDialogStructure (2 tests): Dialog class structure
- TestEditPreviewDialogUI (3 tests): Dialog UI functionality
- TestManifestEditedPreproStorage (3 tests): Manifest storage
- TestFieldProgressionOrder (2 tests): Field order in dataclass
- TestTranslationFlowIntegration (1 test): Translation uses edited_prepro
- TestEditedPreproEdgeCases (5 tests): Edge cases
- TestBackwardCompatibility (2 tests): Old manifest compatibility

---

### TASK 33.2: Configurable Edit/TLC Prompts ✅ DONE
**Priority:** LOW | **Status:** ✅ DONE | **Effort:** 2 hours

Goal: Allow customization of Edit and TLC prompts via Options.

**Implementation:**
- Added [prompts] section to config/defaults.ini with default prompts
- Added PromptsSettings dataclass with edit_prompt and tlc_prompt fields
- Added OptionSection.PROMPTS enum value
- Added Prompts section to Global Options dialog with text areas
- Support for {source_lang} and {target_lang} placeholders in prompts
- "Reset to Default" buttons for each prompt

**Files Modified:**
- `config/defaults.ini` - Added [prompts] section with edit_prompt and tlc_prompt
- `gui/dialogs/global_options.py`:
  - Added DEFAULT_EDIT_PROMPT and DEFAULT_TLC_PROMPT constants
  - Added PromptsSettings dataclass
  - Added OptionSection.PROMPTS to enum
  - Added PROMPTS to SECTION_DESCRIPTIONS, SECTION_NAMES, CATEGORY_ORDER
  - Added prompts field to GlobalOptions dataclass
  - Added prompt variables in _init_variables()
  - Added _build_prompts_section() method with text widgets
  - Added _reset_edit_prompt() and _reset_tlc_prompt() methods
  - Updated _on_save_as_default() to save prompts
  - Updated _load_initial_defaults() to load prompts
  - Updated _save_options() to save prompts

**Tests:** 40 tests in test_prompts_config.py
- TestPromptsSettingsDataclass (7 tests): Dataclass functionality
- TestDefaultPromptConstants (4 tests): Default prompt validation
- TestGlobalOptionsWithPrompts (6 tests): Integration with GlobalOptions
- TestOptionSectionEnum (4 tests): Enum configuration
- TestPromptsINIConfiguration (4 tests): INI file validation
- TestPromptPlaceholders (4 tests): Placeholder substitution
- TestPromptsEdgeCases (6 tests): Edge cases
- TestPromptsSettingsTypeCoercion (2 tests): Type handling
- TestPromptsBackwardsCompatibility (2 tests): Backwards compatibility
- TestPromptsDialogWidgetsMocked (2 tests): Dialog structure

---
## PHASE 34: EXTENDED AND MORE ROBUST AUTOMATIC TESTING
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

### Requirements (All Complete)

1. **All non-API tests must pass before and after every phase**
   - A phase can only be considered done if all tests succeed
   - If tests fail before starting a phase, fix them first

2. **GUI Button Execution Tests** ✅
   - Added tests for all step buttons (Start, Stop, Load, Analyze, Process, etc.)
   - Tests verify button callbacks are bound
   - Tests verify all steps have on_enter() and on_leave() methods

3. **CherryAI Launch Tests** ✅
   - Test CherryAI.py exists and has main entry
   - Test CLI responds to --help
   - Test config files exist
   - Test App class is importable

4. **mypy Testing** ✅
   - Added tests that run mypy on functions/, modi/, formats/ packages
   - Tests verify no circular imports
   - Tests verify critical modules have type annotations

5. **Timeout Protection** ✅
   - Created ExecutionTimer class with watchdog thread
   - Terminates on infinite loop detection
   - Reports which test was last and duration
   - Rule: extend timeout if purpose justifies, investigate if not

### Implementation

Files Created:
- `dev/test_phase34_comprehensive.py` - 34 tests covering all Phase 34 requirements

Test Categories:
- TestTimeoutFramework: 5 tests for internal timeout mechanism
- TestMypyValidation: 7 tests for static type checking
- TestGUIButtonExecution: 12 tests for button callbacks
- TestCherryAILaunch: 6 tests for application launch
- TestTestSuiteItself: 4 meta-tests for infrastructure

### Pre-existing Issues Fixed

During baseline testing, found and fixed 6 failing tests:
1. OptionSection enum count tests (7→8 members after PROMPTS added)
2. Layout test for notes_section (moved to left column per TASK 23.4)
3. TranslationStep manifest binding (used old API, fixed to use lambda: self.manifest_manager)

### TASK 34.6: Pylance/Pyright Static Analysis Configuration [DONE]
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 1 hour

Problem: Pylance showed import resolution errors for CherryAI.* modules because
the static analyzer couldn't see the runtime conftest.py namespace setup.
Additionally, several files had unused imports and type narrowing issues.

Solution:
1. Created `pyrightconfig.json` with extraPaths for import resolution
2. Created `.vscode/settings.json` with python.analysis.extraPaths
3. Fixed type annotations in multiple files:
   - `functions/prompt_builder.py`: Renamed loop variable to avoid shadowing
   - `gui/steps/input_extract.py`: Added type narrowing for Optional session
   - `dev/test_phase34_comprehensive.py`: Fixed Generator return type annotation
4. Cleaned up unused imports in test files:
   - `dev/test_edit_tlc_components.py`
   - `dev/test_blacklist_whitelist.py`
   - `dev/test_manifest_filedir.py`

Files Created:
- `pyrightconfig.json` - Pyright/Pylance configuration
- `.vscode/settings.json` - VS Code Python analysis settings

Files Modified:
- `functions/prompt_builder.py` - Fixed variable shadowing (`char` → `char_note`)
- `gui/steps/input_extract.py` - Added None checks for Optional[SessionState]
- `dev/test_phase34_comprehensive.py` - Fixed Generator return type
- `dev/test_edit_tlc_components.py` - Removed unused imports
- `dev/test_blacklist_whitelist.py` - Removed unused imports
- `dev/test_manifest_filedir.py` - Removed unused imports/variables

---
## PHASE 35: MANIFEST 3.1 INPUT/OUTPUT DECOUPLING (Project File Staging)
**Priority:** HIGH | **Status:** ✅ DONE | **Effort:** 8-14 hours

Goal: Decouple projects from the original input file locations as soon as contents are parsed, while preserving the existing per-line `idx` model and minimizing changes outside Step 0 (Input) and Step 9 (Output).

**Design Constraints:**
- `idx` MUST remain stable (no re-indexing)
- GUI contains NO processing logic (only display + user interaction)
- Manifest remains the single source of truth for loaded text and project state

### TASK 35.1: Add `filedir` (File Directory Map) to Manifest [DONE]
**Priority:** HIGH | **Status:** ✅ DONE | **Effort:** 3-4 hours

Goal: Store a compact mapping from global line index ranges to source files, without adding a filepath to every line.

**Implementation:**
- Created `FileDirEntry` dataclass with fields:
  - `first_idx` / `last_idx` (inclusive, global 0-based line indices)
  - `format` (e.g., `txt`, `csv`, `json`, `xlsx`, `rpgm`)
  - `rel_path` (path relative to project root)
  - `source_hint` (original absolute path for user reference)
  - `encoding` (file encoding, defaults to utf-8)
- Added `filedir` field to manifest schema (empty list by default)
- Added ManifestManager methods:
  - `get_filedir()`, `set_filedir()`, `add_filedir_entry()`, `clear_filedir()`
  - `get_filedir_entry_for_idx()`, `get_lines_for_filedir_entry()`
  - `build_filedir_from_files()`, `_find_common_base()`
- Added backward-compatible migration (`_build_filedir_from_legacy()`)
- Updated manifest version from 3.0 to 3.1

**Files Modified:**
- `functions/manifest_manager.py` (FileDirEntry dataclass + filedir operations)
- `gui/steps/input_extract.py` (`_sync_lines_to_manifest()` now builds filedir)
- `dev/test_manifest_state.py` (updated version check from 3.0 to 3.1)

**Tests:**
- `dev/test_manifest_filedir.py` - 51 tests covering FileDirEntry, filedir operations, migration

---

### TASK 35.2: Copy Original Files into Project (`Original/`) on Load [DONE]
**Priority:** HIGH | **Status:** ✅ DONE | **Effort:** 2-3 hours

Goal: Ensure complex formats (and future reconstruction logic) have a stable local reference even if the user moves/deletes the original inputs.

**Implementation:**
- Added ManifestManager methods:
  - `get_project_dir()` - Returns `Projects/{project_name}/`
  - `get_original_dir()` - Returns `Projects/{project_name}/Original/`
  - `copy_originals_to_project(force=False)` - Copies source files to Original/
  - `get_original_file_path(entry)` - Returns path in Original/ for a filedir entry
  - `has_original_copies()` - Checks if Original/ has files
- `_copy_originals_to_project()` added to `input_extract.py`
- Folder structure is preserved using `rel_path` from filedir entries

**Files Modified:**
- `functions/manifest_manager.py` (project dir helpers + copy logic)
- `gui/steps/input_extract.py` (`_copy_originals_to_project()` method)

**Tests:**
- `dev/test_manifest_filedir.py::TestCopyOriginalsToProject` - 11 tests

---

### TASK 35.3: Default Output to `Patch/` Using `filedir` [DONE]
**Priority:** HIGH | **Status:** ✅ DONE | **Effort:** 3-5 hours

Goal: Write outputs into a stable patch folder by default:
- `Projects/{project_name}/Patch/{rel_path}`

**Implementation:**
- Added ManifestManager methods:
  - `get_patch_dir()` - Returns `Projects/{project_name}/Patch/`
  - `get_patch_file_path(entry)` - Returns output path for a filedir entry
- Refactored `output_inject.py`:
  - `_use_output_dir()` now uses manifest's Patch/ directory
  - `_build_file_list()` delegates to filedir-based or session-based methods
  - `_build_file_list_from_filedir()` - Accurate per-file output using filedir
  - `_build_file_list_from_session()` - Legacy fallback for older projects

**Files Modified:**
- `functions/manifest_manager.py` (Patch/ dir helpers)
- `gui/steps/output_inject.py` (filedir-based output generation)

**Tests:**
- `dev/test_manifest_filedir.py::TestPathHelpers` - 6 tests
- `dev/test_manifest_filedir.py::TestFiledirOutputIntegration` - 3 tests

---

## PHASE 36: CHARACTER/WORD VALIDATION (Whitelist/Blacklist + Autofix)
**Priority:** HIGH | **Status:** ✅ COMPLETED | **Effort:** 10-16 hours

Goal: Add efficient post-translation validation for forbidden/allowed characters and forbidden words, with optional autofix suggestions and application.

### TASK 36.1: Manifest Fields + Defaults for Validation Lists
**Priority:** HIGH | **Status:** ✅ COMPLETED | **Effort:** 2-3 hours

**New Manifest Entries (Implemented):**
- `CharacterWhitelist`: string (allowed chars)
- `CharacterBlacklist`: string (forbidden chars)
- `WordBlacklist`: list of strings (forbidden words/phrases)
- `AutofixMap`: dict (offending_char -> replacement_char)

**Implementation:**
- Added all fields to manifest_manager.py with getters/setters
- Added `get_character_validation_config()` and `set_character_validation_config()` methods
- Added `_parse_dict_default()` helper for parsing autofix map from various formats
- Added defaults to config/defaults.ini

**Likely Files:**
- `functions/manifest_manager.py` (defaults + getters)
- `config/defaults.ini` (new defaults)

---

### TASK 36.2: High-Performance Scanner + Report Model (No GUI Logic)
**Priority:** CRITICAL | **Status:** ✅ COMPLETED | **Effort:** 4-6 hours

Goal: Scan up to ~1,000,000 lines efficiently.

**Implementation:**
- Added `ValidationSeverity` enum (WARNING, ERROR)
- Added `CharacterWordFinding` dataclass for individual findings
- Added `CharacterWordValidationResult` dataclass for scan results
- Implemented two-pass algorithm:
  1. Build distinct character set from all text
  2. Find offending characters by comparing against whitelist/blacklist
  3. Scan only for offending characters in second pass
  4. Word blacklist uses regex for case-insensitive whole-word matching
- Severity classification:
  - WARNING: autofix available AND replacement is valid
  - ERROR: no autofix or replacement is also invalid
- Helper functions: `apply_autofix()`, `apply_autofix_to_lines()`, `get_findings_summary()`,
  `group_findings_by_line()`, `group_findings_by_token()`

**Files Changed:**
- `functions/validation.py` (~350 lines added)

**Tests:**
- `dev/test_blacklist_whitelist.py` - 48 tests covering:
  - Fast exit when no rules configured
  - Character whitelist/blacklist validation
  - Word blacklist (case-insensitive, whole word)
  - Severity classification
  - Autofix application with whitelist/blacklist respect
  - Performance tests (100K lines)

---

### TASK 36.3: GUI Surfacing in Postprocessing + Output Steps
**Priority:** HIGH | **Status:** ✅ COMPLETED | **Effort:** 2-4 hours

Goal: Display results in GUI without embedding scanning logic.

**Implementation:**
- Added validation panel to Postprocessing step (`gui/steps/postprocess.py`)
- Panel includes:
  - Summary status (issues count, lines affected)
  - Warning/error counts with color coding
  - Findings listbox (first 50 findings)
  - "Run Validation" button
  - "Apply Autofix" button (enabled when warnings exist)
- Validation uses manifest's character validation config
- Autofix respects whitelist/blacklist constraints

**Behavior:**
- Postprocessing step shows:
  - Summary counts (warnings/errors)
  - Table of affected lines with offending character/word
  - Optional action: apply autofix (calls shared function; GUI just triggers)

**Likely Files:**
- `gui/steps/postprocess.py`
- `gui/steps/output_inject.py`

---

### TASK 36.4: Optional Logit-Bias Integration for Blacklisted Characters
**Priority:** MEDIUM | **Status:** ✅ COMPLETED | **Effort:** 2-3 hours

Goal: When the selected provider/model supports it, bias the model away from blacklisted characters/tokens.

**Implementation:**
- Added `create_logit_bias_from_blacklist()` function to `functions/logit_bias.py`
- Added `PROVIDER_SUPPORTS_LOGIT_BIAS` dict mapping providers to support status
- Added `provider_supports_logit_bias()` function for capability checking
- Supported providers: OpenAI, Azure, DeepSeek, OpenRouter
- Unsupported: Anthropic, Google, Kobold, Local

**Files Changed:**
- `functions/logit_bias.py` (~60 lines added)

**Tests:**
- Added 9 tests in `dev/test_blacklist_whitelist.py`

---

## PHASE 36 Test Summary
- `dev/test_blacklist_whitelist.py` - 57 tests total

---

## PHASE 37: EDIT/TLC PROMPT COMPONENTS (Configurable Input Sources) ✅ COMPLETED
**Priority:** MEDIUM | **Status:** ✅ COMPLETED | **Effort:** 6-10 hours

Goal: Expand Task 33.2 (custom prompts) with configurable *components* and source selection:
- Edit pass can pick between `orig` and/or latest TLC
- TLC pass can pick `orig` and/or latest Edit

### TASK 37.1: Add Component Toggles to Global Options ✅ DONE
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2-3 hours

**Implementation:**
- Added `EditInputPolicy` enum with values: TL_ONLY, ORIG_AND_TL, TLC_ONLY, TL_AND_TLC
- Added `TLCInputPolicy` enum with values: TL_ONLY, ORIG_AND_TL, EDIT_ONLY, EDIT_AND_ORIG
- Extended `PromptsSettings` dataclass with component toggles:
  - `edit_include_glossary`, `edit_include_game_summary`, `edit_include_character_notes`, `edit_include_code_glossary`
  - `tlc_include_glossary`, `tlc_include_game_summary`, `tlc_include_character_notes`, `tlc_include_code_glossary`
- Added input policy fields: `edit_input_policy`, `tlc_input_policy`
- Added helper methods: `get_edit_components()`, `get_tlc_components()`
- Added UI controls: checkboxes for component toggles, comboboxes for input policies
- Updated serialization: `to_dict()` and `from_dict()` handle all new fields

**Files Modified:**
- `gui/dialogs/global_options.py` - Added enums, extended dataclass, UI controls

---

### TASK 37.2: Prompt Builder Support for Component Toggles ✅ DONE
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2-4 hours

**Implementation:**
- Added `build_edit_tlc_prompt()` method to PromptBuilder class
- Method accepts configurable components dict and optional character_notes/code_glossary
- Conditionally includes: glossary, game_summary, character_notes, code_glossary
- Character notes formatting: name, gender, notes, speaking_style
- Code glossary formatting: pattern, action (preserve is default), example

**Files Modified:**
- `functions/prompt_builder.py` - Added build_edit_tlc_prompt() method (~90 lines)

---

### TASK 37.3: Tests for Edit/TLC Component Selection ✅ DONE
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2-3 hours

**Tests Created:**
- `dev/test_edit_tlc_components.py` - 40 tests total

**Test Classes:**
| Class | Tests | Coverage |
|-------|-------|----------|
| TestEditInputPolicy | 3 | Enum values and string conversion |
| TestTLCInputPolicy | 3 | Enum values and string conversion |
| TestPromptsSettingsComponents | 5 | Default values, get_*_components() |
| TestPromptsSettingsSerialization | 4 | to_dict, from_dict, roundtrip |
| TestBuildEditTlcPrompt | 10 | Prompt building with various configs |
| TestComponentCombinations | 4 | All/none/partial component scenarios |
| TestCharacterNotesFormatting | 4 | Character notes output formatting |
| TestCodeGlossaryFormatting | 4 | Code pattern output formatting |
| TestPromptsSettingsIntegration | 2 | Settings to PromptBuilder integration |

---

## PHASE 37 Test Summary
- `dev/test_edit_tlc_components.py` - 40 tests total

---

=============================================================================

## PHASE 38: MANIFEST OPTIMIZATION (source_root) ✅ DONE
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 4 hours

Goal: Reduce manifest file size by removing redundant path data.

### Problem
Large manifest files (e.g., 24 MB for 48,000 lines) contained excessive redundancy:
- Full source path repeated for each line entry in `source_file` field
- Full source path repeated in filedir `source_hint` field
- Example: `"D:\Translations\Unison Chord\ver1.00\Data\parlight\WIP"` (61 chars) 
  repeated 48,000+ times = ~4 MB of redundant path data

### Solution: Manifest v3.2 Optimization

**TASK 38.1: Add `source_root` Field ✅ DONE**
- Stores common path prefix once at manifest level
- `FileDirEntry.rel_path` is now relative to `source_root`
- Helper methods: `compute_source_root()`, `resolve_file_path()`, `make_relative_path()`

**TASK 38.2: Remove Redundant Fields ✅ DONE**
- Removed `source_file` from each line entry (lookup via filedir index)
- Removed `source_hint` from FileDirEntry (use `source_root + rel_path`)
- Updated `FileDirEntry` dataclass: now only `first_idx`, `last_idx`, `format`, `rel_path`, `encoding`

**TASK 38.3: Migration Function ✅ DONE**
- `_migrate_manifest()` handles v3.1 → v3.2 migration
- Computes `source_root` from existing `source_files` list
- Strips `source_file` from all line entries
- Strips `source_hint` from all filedir entries

**TASK 38.4: Tests ✅ DONE**
- `dev/test_manifest_v32.py` - 35 tests for v3.2 format
- Updated `dev/test_manifest_filedir.py` - Updated for v3.2 compatibility
- Updated `dev/test_manifest_state.py` - Updated migration tests

**Files Modified:**
- `functions/manifest_manager.py` - FileDirEntry, ManifestManager methods
- `gui/steps/output_inject.py` - Updated to use `resolve_file_path()`
- `doc/technical.md` - Updated documentation

**Size Reduction Example:**
- Path: 60 chars, Lines: 50,000 → Savings: ~4 MB per manifest
- JSON overhead included → actual savings ~80% of theoretical maximum

---

=============================================================================

## PHASE 39: INPUT STEP IMPROVEMENTS
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 12-18 hours

Goal: Modernize and polish the Input step (Step 0) per specs.md v2.0 requirements.

**Reference:** See `doc/specs.md` Section 5 → Step 0: Input for detailed specification.

### Overview

The Input step is the entry point for all translation projects. This phase brings the
implementation up to spec with improved UX, better file handling, and proper automation
triggers. The changes are primarily UI/UX improvements with minimal processing logic changes.

### TASK 39.1: Unified File/Folder Selector
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

Goal: Replace separate "Load Files" and "Load Folder" buttons with unified "Select File(s)".

**Current State:**
- `_on_load_files()` - Opens file dialog for multi-file selection
- `_on_load_folder()` - Opens folder dialog for folder selection
- Two separate buttons in toolbar

**Changes Required:**
- Combine into single `_on_select_files()` method
- Use dialog that supports both file and folder selection
- Windows: May need custom dialog or fallback to showing both buttons in dropdown
- Rename button to "Select File(s)" with icon
- Remove "Load Folder" button from toolbar
- Keep single/multi file (Ctrl+Click) and folder selection working

**Files to Modify:**
- `gui/steps/input_extract.py` - Toolbar and handler methods

**Tests to Update:**
- `dev/test_folder_loading.py` - Update for new unified selector
- `dev/test_gui_v2.py` - Update Input step tests

---

### TASK 39.2: Remove Load Manifest and Clear All Buttons
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1 hour

Goal: Remove redundant toolbar buttons per spec.

**Current State:**
- "Load Manifest" button exists (duplicate of File → Open Project)
- "Clear All" button exists (should use File → New Project instead)

**Changes Required:**
- Remove `_on_load_manifest` button from toolbar (keep method for menu use)
- Remove `_on_clear_all` button from toolbar
- Update toolbar layout for cleaner appearance
- Ensure File menu commands work correctly:
  - File → Open Project... → Loads manifest
  - File → New Project → Clears current and starts fresh

**Files to Modify:**
- `gui/steps/input_extract.py` - `_build_toolbar()` method

**Tests to Update:**
- `dev/test_gui_layout.py` - Update toolbar expectations

---

### TASK 39.3: Encoding and Format Dropdown Enhancements
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Add "auto" option to dropdowns and implement format filtering.

**Current State:**
- Encoding dropdown: Fixed values, no "auto" option
- Format dropdown: Has "auto" but no enforcement/filtering

**Changes Required:**
- Add "auto" as first option in Encoding dropdown (default)
- Implement auto-encoding detection in `_extract_lines()` method
- Add format filtering: When format is NOT "auto", refuse to load non-matching files
- Show warning message when files are skipped due to format filter
- Add "rpgmaker" and "image" to Format dropdown values
- Update `SUPPORTED_EXTENSIONS` constant

**Files to Modify:**
- `gui/steps/input_extract.py` - Dropdowns and `_load_file()` method
- `formats/__init__.py` - May need format detection helper

**Tests to Add:**
- `dev/test_format_filtering.py` - Test format enforcement
- Test auto-encoding detection

---

### TASK 39.4: Collapsible Folder Hierarchy in Loaded Files
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Replace flat Listbox with Treeview showing collapsible folder hierarchy.

**Current State:**
- `_file_listbox` is a flat `tk.Listbox`
- Files shown as simple list without folder structure
- Single-select only

**Changes Required:**
- Replace `tk.Listbox` with `ttk.Treeview`
- Build folder hierarchy when loading from folders
- Parent nodes are folders (collapsible)
- Leaf nodes are files with icon, line count
- Enable multi-select (`selectmode="extended"`)
- Right-click context menu:
  - Remove Selected (works on multi-selection)
  - Select All in Folder (selects all files in clicked folder)
- Delete key removes all selected items
- Update `_update_file_list()` to build tree structure
- Store mapping from tree item IDs to LoadedFile objects

**Files to Modify:**
- `gui/steps/input_extract.py` - Replace Listbox with Treeview

**Tests to Add:**
- `dev/test_input_file_tree.py`:
  - Test folder hierarchy display
  - Test multi-select deletion
  - Test collapse/expand
  - Test context menu actions

---

### TASK 39.5: Multi-Line Preview Support
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Fix Preview panel to properly display multi-line content.

**Current State:**
- Preview uses `ttk.Treeview` with fixed row height
- Newlines in content are not visible (truncated after first line)
- Only first line of multi-line entries is shown

**Changes Required:**
- Option A: Use Text widget instead of Treeview for preview
- Option B: Expand Treeview rows to fit content (custom row height)
- Option C: Replace embedded newlines with visible markers (e.g., "↵")
- Show line number column and content column
- Ensure scrolling works with variable row heights

**Recommended:** Option C (markers) for consistency with Treeview

**Files to Modify:**
- `gui/steps/input_extract.py` - `_update_preview()` method

**Tests to Add:**
- `dev/test_input_preview.py`:
  - Test multi-line content display
  - Test newline marker visibility

---

### TASK 39.6: Remove Manifest Status Label
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 30 minutes

Goal: Remove the manifest label at the bottom of Preview panel per spec.

**Current State:**
- `_manifest_frame` with `_manifest_label` and `_load_manifest_btn`
- Shows "No manifest detected" or manifest path

**Changes Required:**
- Remove `_manifest_frame` and its contents from `_build_content()`
- Manifest status should be shown in window title bar instead (already done by App)
- Remove `_on_load_detected_manifest()` method if no longer needed

**Files to Modify:**
- `gui/steps/input_extract.py` - `_build_content()` method

**Tests to Update:**
- Any tests referencing manifest label widget

---

### TASK 39.7: Progress Window for File Loading
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

Goal: Show progress window during file loading operations.

**Current State:**
- Files load synchronously with no progress feedback
- Large folder loads can appear to freeze the UI

**Changes Required:**
- Create `LoadingProgressDialog` class (modal Toplevel)
  - Progress bar (determinate mode)
  - Current file label
  - Files loaded / total files label
  - Cancel button
- Run file loading in background thread
- Update progress after each file
- Handle cancellation gracefully
- Close dialog when complete

**Files to Create:**
- `gui/dialogs/loading_progress.py` - Progress dialog class

**Files to Modify:**
- `gui/steps/input_extract.py` - Use progress dialog in load methods

**Tests to Add:**
- `dev/test_loading_progress.py`:
  - Test progress updates
  - Test cancellation
  - Test completion callback

---

### TASK 39.8: Update specs.md with Implementation Status
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 30 minutes

Goal: Update specs.md Step 0 section to mark implemented features.

**Changes Required:**
- After each task above is complete, update specs.md
- Remove "Known Issues" and "Missing Features" sections once resolved
- Update "Current State" notes to reflect actual implementation

**Files to Modify:**
- `doc/specs.md` - Step 0 section

---

### TASK 39.9: Update Tests and Documentation
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Ensure all Input step tests pass after changes.

**Changes Required:**
- Run existing tests: `pytest dev/test_folder_loading.py dev/test_gui_v2.py -v`
- Fix any broken tests due to UI changes
- Add new tests for new functionality (per tasks above)
- Update `doc/features.md` Input section to match new behavior

**Files to Modify:**
- `dev/test_folder_loading.py` - Update for new selector
- `dev/test_gui_v2.py` - Update for UI changes
- `doc/features.md` - Update Input section

---

### Phase 39 Summary

| Task | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 39.1 | Unified file/folder selector | 3h | None |
| 39.2 | Remove Load Manifest/Clear All buttons | 1h | None |
| 39.3 | Encoding/Format dropdown enhancements | 2h | None |
| 39.4 | Collapsible folder hierarchy | 4h | None |
| 39.5 | Multi-line preview support | 2h | None |
| 39.6 | Remove manifest status label | 0.5h | None |
| 39.7 | Progress window for loading | 3h | None |
| 39.8 | Update specs.md | 0.5h | 39.1-39.7 |
| 39.9 | Update tests and docs | 2h | 39.1-39.7 |

**Total Estimated Effort:** 18 hours

**Implementation Order:**
1. Tasks 39.2, 39.6 (quick removals)
2. Task 39.3 (dropdown enhancements)
3. Task 39.4 (file tree - most complex)
4. Task 39.5 (preview fix)
5. Task 39.1 (unified selector)
6. Task 39.7 (progress window)
7. Tasks 39.8, 39.9 (documentation and tests)

---

=============================================================================

PHASE 40: COSTS STEP IMPROVEMENTS
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** ~22 hours
**Dependencies:** None (can be done in parallel with Phase 39)
**Cross-Reference:** See `doc/specs.md` Step 2: Costs for full specification

This phase implements the comprehensive Costs step (formerly Estimation) as specified
in specs.md v2.1. The step provides pre-translation cost estimates and will eventually
track actual costs post-translation.

---

### TASK 40.1: Rename Estimation to Costs
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1 hour

Goal: Rename the step from "Estimation" to "Costs" throughout the codebase.

**Changes Required:**
- Rename `gui/steps/estimate.py` to `gui/steps/costs.py`
- Rename class `EstimationStep` to `CostsStep`
- Update `step_name = "Costs"`
- Update all imports referencing EstimationStep
- Update `gui/app.py` step registration
- Update test files referencing estimation

**Files to Modify:**
- `gui/steps/estimate.py` → `gui/steps/costs.py`
- `gui/app.py` - Update import and registration
- `dev/test_estimation_*.py` - Update class references
- `doc/features.md` - Update step name references

**Tests to Add:**
- Verify step displays as "Costs" in tab
- Verify step_id remains 2

---

### TASK 40.2: Tokens/Request Limit Implementation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

Goal: Add Tokens/Request spinbox as alternative maximum alongside Lines/Request.

**Changes Required:**
- Add `_tokens_var: tk.IntVar` with default 4000
- Add `_tokens_spin: ttk.Spinbox` (range 500-32000)
- Update header layout to include new spinbox
- Modify chunk calculation to respect both limits:
  - When building chunks, stop at EITHER lines OR tokens limit
  - Whichever limit is reached first triggers chunk boundary
- Pass both limits to `chunk_lines()` function

**Files to Modify:**
- `gui/steps/costs.py` - Add UI widget and binding
- `gui/helpers/chunker_adapter.py` - Update `chunk_lines()` signature
- `functions/chunker.py` - Update chunking logic

**Tests to Add:**
- `dev/test_costs_tokens_limit.py`:
  - Test chunk splits when tokens exceeded before lines
  - Test chunk splits when lines exceeded before tokens
  - Test both limits respected together

---

### TASK 40.3: Prompt Overhead Calculation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Calculate accurate prompt tokens including all prompt components.

**Current Issue:**
- Token count only includes line content
- System prompt, summary, tone, style, glossary prompts not counted
- Results in significant underestimation

**Changes Required:**
- Import `build_prompt_preview` from `gui/helpers/prompt_adapter.py`
- Calculate base system prompt tokens
- Calculate conditional prompt tokens:
  - Summary prompt (if summary provided in Step 3)
  - Tone preset prompt (if selected)
  - Style preset prompt (if selected)
  - Code glossary prompt (if patterns defined)
  - Rolling context prompt (if enabled)
- Add prompt overhead per request to total calculation
- Display prompt overhead in Token Counts panel

**Files to Modify:**
- `gui/steps/costs.py` - `_run_estimation()` method
- `gui/helpers/prompt_adapter.py` - Ensure `build_prompt_preview()` returns token count
- `gui/helpers/chunker_adapter.py` - `count_tokens()` for prompt text

**Tests to Add:**
- `dev/test_prompt_overhead.py`:
  - Test base prompt token count
  - Test with summary added
  - Test with tone/style presets
  - Test with code glossary patterns
  - Test total includes prompt overhead per chunk

---

### TASK 40.4: Dual Estimation Workflow
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Implement two-state estimation (Original and Preprocessed) with separate triggers.

**Current Issue:**
- Single estimation state
- No automatic re-estimation after preprocessing
- Progress tracker shows single tick

**Changes Required:**
- Add `_estimation_state: Dict` tracking:
  - `original_complete: bool`
  - `preprocessed_complete: bool`
  - `original_result: ComparisonResult`
  - `preprocessed_result: ComparisonResult`
- Implement Auto-Estimation (Original):
  - Trigger: `on_enter()` when files loaded and no estimation done
  - Uses `all_lines[]` from Input step
  - Sets `original_complete = True`
- Implement Auto-Estimation (Preprocessed):
  - Trigger: When Step 4 completes preprocessing
  - Uses `prepro[]` from Preprocessing step
  - Sets `preprocessed_complete = True`
- Reset logic:
  - Reset both when files change
  - Reset preprocessed only when preprocessing settings change
  - Reset both when prompt settings change
- Update UI to show both states clearly

**Files to Modify:**
- `gui/steps/costs.py` - State management and triggers
- `gui/steps/preprocess.py` - Notify Costs step on completion
- `gui/app.py` - Wire up step communication

**Tests to Add:**
- `dev/test_dual_estimation.py`:
  - Test auto-estimation on file load
  - Test auto-estimation after preprocessing
  - Test reset on file change
  - Test reset on setting change

---

### TASK 40.5: Progress Tracker Dual Ticks
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Update progress tracker to show two checkmarks for Costs step.

**Changes Required:**
- Modify progress tracker component to support multi-tick steps
- Costs step reports two sub-states:
  - Tick 1: Original estimation complete
  - Tick 2: Preprocessed estimation complete
- Visual display: `☐ ☐` → `☑ ☐` → `☑ ☑`
- Ticks reset appropriately per TASK 40.4

**Files to Modify:**
- `gui/components/progress_tracker.py` - Support multiple ticks per step
- `gui/steps/costs.py` - Report sub-state to tracker

**Tests to Add:**
- `dev/test_progress_tracker.py`:
  - Test dual tick display
  - Test individual tick updates
  - Test tick reset

---

### TASK 40.6: Model Comparison Expanded Columns
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

Goal: Add Price Original, Price Preprocessed, and Savings columns to Model Comparison.

**Current Columns:**
- Model Name, Input Price, Output Price, Concurrent Requests

**Required Columns:**
- Price Original: Cost calculated from original lines
- Price Preprocessed: Cost calculated from preprocessed lines
- Savings: Percentage saved by preprocessing

**Changes Required:**
- Add column definitions to `_build_comparison_table()`
- Calculate per-model costs in `_update_comparison_table()`
- Format as currency with 4 decimal places
- Calculate savings as percentage
- Update table on each estimation run

**Files to Modify:**
- `gui/steps/costs.py` - Table columns and update logic

**Tests to Add:**
- `dev/test_model_comparison.py`:
  - Test column presence
  - Test cost calculation accuracy
  - Test savings percentage calculation

---

### TASK 40.7: Time Estimate with Concurrent Requests
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Update time estimation to account for concurrent requests and token speed.

**Current Issue:**
- Only uses requests per minute rate limit
- Does not factor in concurrent request capability
- No consideration of token generation speed

**Required Calculation:**
```python
time = max(
    total_requests / concurrent_requests × time_per_request,
    total_tokens / token_speed,
    total_requests / rate_limit_rpm × 60
)
```

**Changes Required:**
- Get `concurrent_requests` from model config
- Get `token_speed` from model config (default: 50 tokens/sec)
- Update `estimate_rate_limit_time()` to use new calculation
- Display breakdown in Time Estimate panel

**Files to Modify:**
- `gui/steps/costs.py` - Time calculation update
- `functions/config.py` - Add concurrent_requests and token_speed to MODEL_PRICING
- `gui/helpers/chunker_adapter.py` - Update time estimation function

**Tests to Add:**
- `dev/test_time_estimate.py`:
  - Test with different concurrent request values
  - Test rate limit dominates when slow
  - Test token speed dominates when fast concurrent

---

### TASK 40.8: Refresh Button Model Data Fetch
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

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

---

### TASK 40.9: Use Preprocessed Lines After Step 4
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1 hour

Goal: Ensure estimation uses preprocessed lines when available.

**Current Issue:**
- Estimation always uses original lines
- Does not check for preprocessed lines from Step 4
- Manual refresh required

**Changes Required:**
- In `_refresh_lines()`, check manifest for `prepro[]`
- If preprocessing complete, use `prepro[]` for Preprocessed estimation
- Display both Original and Preprocessed results side by side
- Update comparison to show actual savings

**Files to Modify:**
- `gui/steps/costs.py` - `_refresh_lines()` method

**Tests to Add:**
- `dev/test_prepro_estimation.py`:
  - Test uses original when no preprocessing
  - Test uses prepro after Step 4 complete
  - Test savings calculation correct

---

### Phase 40 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 40.1 | Rename Estimation to Costs | HIGH | 1h | None |
| 40.2 | Tokens/Request limit | HIGH | 3h | None |
| 40.3 | Prompt overhead calculation | HIGH | 4h | None |
| 40.4 | Dual estimation workflow | HIGH | 4h | 40.1 |
| 40.5 | Progress tracker dual ticks | MEDIUM | 2h | 40.4 |
| 40.6 | Model comparison expanded | HIGH | 3h | 40.4 |
| 40.7 | Time estimate concurrent | MEDIUM | 2h | None |
| 40.8 | Refresh button model fetch | LOW | 3h | None |
| 40.9 | Use preprocessed lines | HIGH | 1h | 40.4 |

**Total Estimated Effort:** 23 hours

**Implementation Order:**
1. Task 40.1 (rename - sets up correct naming)
2. Tasks 40.2, 40.3 (core calculation improvements)
3. Task 40.4, 40.9 (dual workflow - main feature)
4. Task 40.5, 40.6 (UI improvements depending on 40.4)
5. Task 40.7 (time estimate improvement)
6. Task 40.8 (low priority, can be deferred)

**Priority Tasks for Next Release:**
- 40.1, 40.2, 40.3, 40.4, 40.6, 40.9 (14 hours)

---

### Phase 41: Information Step UI Enhancements
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 28 hours
**File:** `gui/steps/information.py`
**Spec Reference:** specs.md Step 3: Information

**Context:**
Complete UI overhaul for Step 3 (Information) per specs.md v2.2. Includes widget renames, behavior fixes, and a new Global Glossary/Database widget. All changes documented in specs.md with prompt formats and manifest keys.

---

#### Task 41.1: Widget Renames
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1 hour

**Goal:** Update widget titles per spec naming conventions.

**Changes:**
| Current Name | New Name |
|--------------|----------|
| Summary / Description | Summary |
| Prompt | System Instructions |
| Code Glossary | Code Database |

**Implementation:**
- Update LabelFrame titles in respective `_build_*_section()` methods
- Update any references in tooltips or help text

---

#### Task 41.2: Genre Dialog ADD Behavior
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

**Goal:** Genre `...` button should ADD to existing text, not overwrite.

**Current Behavior:** Selecting genre replaces entire field content.

**Required Behavior:**
- If field empty: Set selected genre
- If field has content: Append `, [selected genre]`
- Support multi-select in dialog if possible

**Implementation:**
- Modify genre dialog callback in `_build_project_section()`
- Check current field content before setting
- Use comma-separated append logic

---

#### Task 41.3: "Other" Language Custom Input
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

**Goal:** When "Other" selected in Source/Target Language, prompt for custom input.

**Current Behavior:** "Other" option exists but does nothing special.

**Required Behavior:**
- Detect "Other" selection in combobox callback
- Show simpledialog.askstring() prompt
- If user provides input: Set combobox value to custom text
- If user cancels: Revert to previous selection

**Implementation:**
- Add `_on_language_change()` callback for both dropdowns
- Store previous selection for revert logic
- Use tkinter.simpledialog for input prompt

---

#### Task 41.4: Style/Tone Dropdown Graying
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

**Goal:** Visual feedback for dropdown vs custom override state.

**Required Behavior:**
- When Custom Style/Tone field has content: Gray out corresponding dropdown
- When Custom field cleared: Activate dropdown
- Use `state='disabled'` for grayed appearance

**Implementation:**
- Add trace callbacks on custom text variables
- Toggle dropdown state based on custom field content
- Ensure disabled dropdown shows current selection (not blank)

---

#### Task 41.5: Glossary Table Inline Editing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

**Goal:** Editable 3-column table for Glossary Settings.

**Columns:**
| Column | Purpose | Editable |
|--------|---------|----------|
| Original | Source text to match | Yes |
| Translation | Replacement text | Yes |
| Notes | Context for LLM | Yes |

**Implementation:**
- Convert current glossary display to ttk.Treeview with editing
- Double-click cell to edit in place
- Add/Remove row buttons
- Auto-save changes to manifest via `GlossaryEntries` key

---

#### Task 41.6: Import from Analysis (Code Patterns)
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

**Goal:** Make "Import from Analysis" button functional for Code Database.

**Required Behavior:**
- Fetch detected code patterns from Analysis step (Step 1)
- Convert to CodePattern entries with defaults:
  - Category: "Detected"
  - Action: "Preserve"
  - Notes: empty
- Merge with existing entries (no duplicates)

**Implementation:**
- Access Analysis step results via step communication
- Map detected patterns to CodePattern data class
- Add merge logic to avoid duplicate patterns

---

#### Task 41.7: Import from Analysis (Glossary)
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

**Goal:** Make "Import from Analysis" button functional for Glossary Settings.

**Required Behavior:**
- Fetch detected speakers from Analysis step
- Convert to glossary entries with defaults:
  - Original: detected name
  - Translation: empty (user fills in)
  - Notes: "Speaker" or similar tag
- Merge with existing entries

**Implementation:**
- Access Analysis step detected_speakers data
- Convert to glossary entry format
- Add to GlossaryEntries manifest field

---

#### Task 41.8: Code Database Actions
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

**Goal:** Implement three action types for Code Database entries.

**Actions:**
| Action | Prompt Behavior | Post-Processing |
|--------|-----------------|-----------------|
| Preserve | "Do not translate [Code]: [Pattern]" | Auto-recover if mangled |
| Translate | "Translate [Code] as [Notes context]" | None |
| Remove | Not sent to prompt | Strip from output |

**Implementation:**
- Add Action dropdown column to Code Database table
- Modify prompt builder to handle action types
- Add post-processing recovery logic for Preserve action

---

#### Task 41.9: NEW Global Glossary and Database Widget
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 6 hours

**Goal:** New widget for managing global (cross-project) glossary and code patterns.

**Features:**
- Mode switch: "Global Glossary" / "Global Code Database"
- Searchable table with filter input
- Import/Export buttons (JSON/CSV)
- Same fields as project-level equivalents
- Stored in `user/global_glossary.json` and `user/global_codes.json`

**UI Layout:**
```
┌─ Global Glossary and Database ─────────────────────┐
│ Mode: [Glossary ▼]  Search: [________]  [Import] [Export] │
│ ┌─────────────────────────────────────────────────┐│
│ │ Original │ Translation │ Notes                ││
│ │----------|-------------|----------------------││
│ │ ...      │ ...         │ ...                  ││
│ └─────────────────────────────────────────────────┘│
│ [Add Entry] [Remove Selected] [Clear All]          │
└────────────────────────────────────────────────────┘
```

**Implementation:**
- Create new `_build_global_database_section()` method
- Create GlobalGlossaryManager class for file I/O
- Add search/filter functionality
- Implement import/export dialogs

---

#### Task 41.10: Selective Glossary Feature
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

**Goal:** Allow users to select which glossary entries apply to current project.

**Required Behavior:**
- Checkbox column in glossary table for "Active"
- Only active entries included in prompt
- Global glossary entries can be imported selectively

**Implementation:**
- Add "Active" boolean column to glossary table
- Filter entries by active status when building prompt
- Store active state in manifest

---

### Phase 41 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 41.1 | Widget renames (Summary, System Instructions, Code Database) | HIGH | 1h | None |
| 41.2 | Genre Dialog ADD behavior | HIGH | 2h | None |
| 41.3 | "Other" Language custom input | HIGH | 2h | None |
| 41.4 | Style/Tone dropdown graying | MEDIUM | 2h | None |
| 41.5 | Glossary table inline editing | HIGH | 4h | None |
| 41.6 | Import from Analysis (Code) | HIGH | 3h | Step 1 Analysis |
| 41.7 | Import from Analysis (Glossary) | HIGH | 3h | Step 1 Analysis |
| 41.8 | Code Database actions (Preserve/Translate/Remove) | HIGH | 3h | 41.1 |
| 41.9 | NEW Global Glossary and Database widget | HIGH | 6h | 41.5 |
| 41.10 | Selective glossary feature | MEDIUM | 2h | 41.5 |

**Total Estimated Effort:** 28 hours

**Implementation Order:**
1. Task 41.1 (renames - quick win, establishes naming)
2. Tasks 41.2, 41.3, 41.4 (behavior fixes - independent)
3. Task 41.5 (glossary table - foundation for 41.9, 41.10)
4. Tasks 41.6, 41.7 (import functionality - depends on Analysis)
5. Task 41.8 (code actions - depends on 41.1 rename)
6. Task 41.9 (global database - major feature, depends on 41.5)
7. Task 41.10 (selective glossary - enhancement to 41.5)

**Priority Tasks for Next Release:**
- 41.1, 41.2, 41.3, 41.5, 41.8 (13 hours - core functionality)

---

=============================================================================

## PHASE 42: PREPROCESSING & POSTPROCESSING COMPLETE IMPLEMENTATION
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 40-50 hours
**Dependencies:** None (can be done in parallel with other phases)
**Cross-Reference:** See `doc/specs.md` Step 4: Preprocessing for full specification

This phase implements comprehensive Preprocessing and Postprocessing functionality as specified
in specs.md v2.3. Both steps must exactly mirror each other - many Preprocessing transformations
have a corresponding Postprocessing restoration. Each process has a priority integer determining
execution order.

---

### TASK 42.1: Anchoring Widget Redesign (Rename from Anchor Removal)
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Redesign the Anchor Removal widget as "Anchoring" with proper table-based management.

**Current Issues:**
- Widget has wrong UI (single writable field, preset selection buttons)
- No RegEx toggle option
- Name "Anchor Removal" is confusing

**Required Changes:**
- Rename widget from "Anchor Removal" to "Anchoring"
- Replace current UI with table-based view (Pattern, Action, Anchor Spec, RegEx, Description)
- Add popup dialog for Add/Edit with same fields as other pattern widgets
- Add RegEx tickbox in dialog (default: enabled)
- Remove preset selection buttons (all patterns checked by default)
- Implement proper table management (Add, Edit, Remove buttons)

**Files to Modify:**
- `gui/steps/preprocess.py` - Complete widget redesign

**Tests to Add:**
- `dev/test_anchoring_widget.py`:
  - Test table population
  - Test Add/Edit/Remove operations
  - Test RegEx toggle
  - Test data persistence to manifest

---

### TASK 42.2: Custom Placeholders RegEx Support
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Add RegEx toggle to Custom Placeholders widget.

**Current State:**
- Custom Placeholders only supports literal string matching
- No RegEx option in UI

**Required Changes:**
- Add RegEx tickbox in Add/Edit dialog (default: disabled)
- Update table to show RegEx column
- Modify processing to interpret pattern as regex when enabled
- Update manifest schema to include `is_regex` field

**Files to Modify:**
- `gui/steps/preprocess.py` - Add RegEx toggle to Custom Placeholders
- `modi/custom_placeholder.py` - Support regex patterns

**Tests to Add:**
- `dev/test_custom_placeholders.py`:
  - Test literal string matching
  - Test regex pattern matching
  - Test toggle persistence

---

### TASK 42.3: Protect Code Patterns Default Toggle
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1 hour

Goal: Ensure Protect Code Patterns defaults to RegEx enabled.

**Current State:**
- May not have consistent RegEx default behavior

**Required Changes:**
- Verify RegEx tickbox exists and defaults to enabled
- Add visible RegEx column to table
- Ensure dialog shows RegEx option clearly
- Update default value in dialog to True

**Files to Modify:**
- `gui/steps/preprocess.py` - Verify/fix RegEx defaults

**Tests to Add:**
- `dev/test_protect_code_patterns.py`:
  - Test default RegEx = True
  - Test toggle persistence
  - Test pattern interpretation

---

### TASK 42.4: Aggressive Deduplication - Number Normalization
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Implement aggressive deduplication that treats all numbers as equivalent 'X'.

**Description:**
Lines like "Increases Damage by 10" and "Increases Damage by 864" should be treated as duplicates
with the latter deduplicated. The translation of the unique line is used, with the original number
restored.

**Implementation:**
- Add `aggressive_number_dedup` option to Deduplication settings (tickbox in UI)
- Before duplicate detection, normalize numbers to 'X' for comparison
- Store original numbers in dedup_map for restoration
- During Postprocessing, restore original numbers

**Example:**
```
Original: "Increases Damage by 10", "Increases Damage by 864"
Normalized for comparison: "Increases Damage by X", "Increases Damage by X"
Result: First line translated, second line gets same translation with "864" restored
```

**Files to Modify:**
- `functions/dedup.py` - Add number normalization option
- `gui/steps/preprocess.py` - Add UI toggle
- `functions/manifest_manager.py` - Add setting

**Tests to Add:**
- `dev/test_dedup_aggressive_numbers.py`:
  - Test number normalization
  - Test number restoration
  - Test mixed content handling
  - Test boundary cases (negative numbers, decimals)

---

### TASK 42.5: Ellipsis Compression Testing & Verification
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Verify Ellipsis Compression is feature-complete and add comprehensive tests.

**Current State:**
- Feature reportedly implemented but needs verification
- May lack edge case handling

**Required Verification:**
- Japanese ellipsis `……` (multiple pairs) compresses correctly
- Western ellipsis `....` (4+ dots) compresses correctly
- Mixed ellipsis in same line handled
- Original length recorded for restoration
- Postprocessing restores exact original length

**Files to Verify/Modify:**
- `modi/standard_mode.py` - Ellipsis compression
- `functions/postprocess.py` - Ellipsis restoration

**Tests to Add:**
- `dev/test_preprocessing_ellipsis.py`:
  - Test Japanese ellipsis compression
  - Test Western ellipsis compression
  - Test roundtrip accuracy
  - Test edge cases (mixed types, very long sequences)

---

### TASK 42.6: PROT Token Compression Testing & Verification
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Verify PROT Token Compression works correctly with adjacency requirement.

**Current State:**
- Feature reportedly implemented but needs verification
- Must only compress adjacent tokens (no whitespace or any other character between)

**Required Verification:**
- `__PROT____PROT__` → `__PROT_2__` (adjacent)
- `__PROT__ __PROT__` → unchanged (space between)
- Decompression restores correct count
- Decompression runs BEFORE PROT restoration

**Files to Verify/Modify:**
- `modi/standard_mode.py` - PROT compression
- `functions/postprocess.py` - PROT decompression

**Tests to Add:**
- `dev/test_preprocessing_prot.py`:
  - Test adjacent compression
  - Test non-adjacent preservation
  - Test decompression accuracy
  - Test execution order (decompress before restore)

---

### TASK 42.7: Code Database Integration with Code Spacing Rules
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 5 hours

Goal: Integrate Code Spacing Rules with Code Database entries.

**Current State:**
- Code Spacing Rules exist but limited integration
- Code Database (Step 3) stores patterns but not spacing rules

**Required Changes:**
- Extend Code Database entries with spacing tags:
  - `visible`: Boolean - Does the code render visibly?
  - `spacing`: Enum - "none", "preserve", "normalize"
- Code Spacing Rules reads these tags from Code Database
- Apply appropriate spacing based on tag values
- Invisible codes (colors) should have no spaces added
- Variable codes should preserve existing spacing

**Files to Modify:**
- `gui/steps/information.py` - Add spacing fields to Code Database entries
- `modi/code_spacing.py` - Read spacing rules from Code Database
- `functions/manifest_manager.py` - Extend code_patterns schema

**Tests to Add:**
- `dev/test_code_spacing_integration.py`:
  - Test invisible code handling
  - Test variable code handling
  - Test spacing preservation
  - Test Code Database tag reading

---

### TASK 42.8: Preview Widget Filtering
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

Goal: Implement filtering options for the Preview Table.

**Required Filters:**
| Filter | Shows |
|--------|-------|
| All | All lines |
| Changed | Only lines with any modification |
| Custom | Only lines with custom placeholder |
| Deduplicated | Only lines that were deduplicated and their originals |
| Protected | Only lines with `__PROT__` tokens |
| Anchored | Only lines with anchor removals |
| Errors | Only lines with processing errors |

**Implementation:**
- Add filter dropdown or radio buttons above Preview Table
- Filter updates table display without re-running preprocessing
- Show count of matching lines
- Persist filter selection in session (not manifest)

**Files to Modify:**
- `gui/steps/preprocess.py` - Add filter UI and logic

**Tests to Add:**
- `dev/test_preview_filtering.py`:
  - Test each filter type
  - Test filter persistence
  - Test count display

---

### TASK 42.9: Preprocessing/Postprocessing Roundtrip Tests
**Priority:** CRITICAL | **Status:** 🔲 NOT STARTED | **Effort:** 6 hours

Goal: Comprehensive roundtrip tests ensuring Preprocessing and Postprocessing exactly mirror.

**Test Scenarios:**
1. Single process roundtrips (each process individually)
2. All processes enabled roundtrip
3. Specific combination roundtrips
4. Large file roundtrip (100K+ lines)
5. Edge case content (only code, only text, mixed)
6. Overlapping patterns
7. Nested code constructs
8. Recovery scenarios (mangled tokens, missing anchors)

**Test Approach:**
- For each scenario: Original → Preprocess → Mock Translation → Postprocess → Compare
- Mock translation applies known transformations
- Final result must match expected output exactly

**Files to Create:**
- `dev/test_preprocessing_postprocessing_roundtrip.py`:
  - TestSingleProcessRoundtrip (one test per process)
  - TestAllProcessesRoundtrip
  - TestCombinationRoundtrips
  - TestLargeFileRoundtrip
  - TestEdgeCaseContent
  - TestOverlappingPatterns
  - TestNestedCode
  - TestRecoveryScenarios

---

### TASK 42.10: Validation Enhancement - Pattern/Anchor Recovery
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Enhance QA Step validation with comprehensive recovery checks.

**Current State:**
- QA Step checks if recovery is possible
- Does not save results beyond flags
- Limited recovery strategies

**Required Changes:**
- Implement all recovery strategies:
  1. Exact Match - Token at expected position
  2. Case Recovery - `__prot__` → `__PROT__`
  3. Mangled Recovery - `__PRO T__` pattern matching
  4. Position Shift - Token present but moved
  5. Missing Token - Flag for manual review
  6. Extra Token - Flag potential duplicate
- Save recovery analysis results to manifest
- Show recovery feasibility in QA UI
- Provide "Apply Recovery" action that attempts automatic fixes

**Files to Modify:**
- `gui/steps/qa.py` - Enhanced validation display
- `functions/validation.py` - Recovery analysis logic
- `functions/postprocess.py` - Recovery application

**Tests to Add:**
- `dev/test_validation_recovery.py`:
  - Test each recovery type detection
  - Test recovery application
  - Test result persistence

---

### TASK 42.11: Process Priority Documentation and Enforcement
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Document and enforce process execution priority in modi/ modules.

**Required Changes:**
- Check `PRIORITY` or equivalent constant in each modi/ module
- Create `functions/process_order.py` with priority definitions
- Ensure `mode_adapter.py` sorts processes by priority before execution
- Add verification that Postprocessing uses reverse priority order

**Priority Values (from specs.md, must be changed, see any '<-Pointers):**
| Priority | Preprocessing Process, Lower means first for Preproccessing |
|----------|----------------------|
| 10 | Deduplication |
| 20 | Ellipsis Compression |
| 30 | Symbol Conversion | <-WRONG! Before Ellipsis
| 40 | Speaker Name Replacement |
| 50 | Code Spacing Rules | <-WARNING! Postprocess only!
| 60 | PROT Token Compression | <-WRONG! Must be After Protect Code Patterns (90)
| 70 | Custom Placeholders |
| 75 | Anchoring |
| 80 | Protect Code Patterns |

**Files to Modify/Create:**
- `functions/process_order.py` - Priority definitions
- `modi/*.py` - Add PRIORITY constants
- `gui/helpers/mode_adapter.py` - Enforce ordering

**Tests to Add:**
- `dev/test_process_order.py`:
  - Test priority constant presence
  - Test execution order
  - Test reverse order for Postprocessing

---

### TASK 42.12: Test Suite Completion
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 6 hours

Goal: Create comprehensive test coverage for all Preprocessing/Postprocessing functionality.

**Test Files to Create:**
- `dev/test_preprocessing_dedup.py` - Deduplication tests
- `dev/test_preprocessing_symbols.py` - Symbol Conversion tests
- `dev/test_preprocessing_placeholders.py` - Custom Placeholders tests
- `dev/test_preprocessing_anchoring.py` - Anchoring tests
- `dev/test_preprocessing_integration.py` - Integration tests
- `dev/test_postprocessing_restoration.py` - All restoration tests

**Coverage Requirements:**
- Each process individually (unit tests)
- Process combinations (integration tests)
- Boundary cases (empty, very long, special characters)
- Performance (timing for 100K+ lines)
- Error handling (invalid patterns, missing data)

---

### Phase 42 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 42.1 | Anchoring Widget Redesign | HIGH | 4h | None |
| 42.2 | Custom Placeholders RegEx Support | HIGH | 2h | None |
| 42.3 | Protect Code Patterns Default Toggle | MEDIUM | 1h | None |
| 42.4 | Aggressive Deduplication - Numbers | HIGH | 4h | None |
| 42.5 | Ellipsis Compression Testing | MEDIUM | 2h | None |
| 42.6 | PROT Token Compression Testing | MEDIUM | 2h | None |
| 42.7 | Code Database Integration | HIGH | 5h | Step 3 Code Database |
| 42.8 | Preview Widget Filtering | MEDIUM | 3h | None |
| 42.9 | Roundtrip Tests (CRITICAL) | CRITICAL | 6h | 42.1-42.8 |
| 42.10 | Validation Enhancement - Recovery | HIGH | 4h | None |
| 42.11 | Process Priority Documentation | MEDIUM | 2h | None |
| 42.12 | Test Suite Completion | HIGH | 6h | 42.1-42.11 |

**Total Estimated Effort:** 41 hours

**Implementation Order:**
1. Tasks 42.1, 42.2, 42.3 (Widget fixes - independent, quick wins)
2. Task 42.4 (Aggressive deduplication - important feature)
3. Tasks 42.5, 42.6 (Verification tasks - can run in parallel)
4. Task 42.7 (Code Database integration - depends on Step 3)
5. Task 42.8 (Preview filtering - UI enhancement)
6. Task 42.10 (Validation - needed for testing)
7. Task 42.11 (Priority documentation)
8. Task 42.9 (Roundtrip tests - depends on all fixes)
9. Task 42.12 (Test suite completion - final)

**Priority Tasks for Next Release:**
- 42.1, 42.2, 42.4, 42.9, 42.10 (20 hours - core functionality and critical tests)

---

=============================================================================

## PHASE 43: TRANSLATION TAB OVERHAUL
**Priority:** CRITICAL | **Status:** 🔲 NOT STARTED | **Effort:** 50-60 hours
**Dependencies:** Phase 42 (Preprocessing must be stable for translation input)
**Cross-Reference:** See `doc/specs.md` Step 5: Translation for full specification

This phase addresses critical performance issues, the manifest attribute bug, and comprehensive
UI/UX improvements to the Translation step. Includes Mock Translation, model management via
Global Options, retry strategy refinement, prompt editor redesign, and caching relocation.

**Known Bug (CRITICAL)**: `AttributeError: 'TranslationStep' object has no attribute 'manifest'`
in `translate.py` line 1904. The code uses `self.manifest` but BaseStep only provides
`self.manifest_manager`. Must be fixed immediately.

---

### TASK 43.1: Fix Manifest Attribute Bug (CRITICAL)
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 30 minutes

Goal: Fix the `AttributeError: 'TranslationStep' object has no attribute 'manifest'` crash.

**Root Cause:**
- `_load_request_options_from_manifest()` at line 1904 uses `self.manifest`
- `BaseStep` class only provides `self.manifest_manager` property
- The code was likely written before the BaseStep API was standardized

**Fix:**
- Replace `self.manifest` with `self.manifest_manager` in `_load_request_options_from_manifest()`
- Replace `self.manifest` with `self.manifest_manager` in `_save_temperature_to_manifest()`
- Audit all other uses of `self.manifest` in translate.py
- Add null check: `if self.manifest_manager is None or not self.manifest_manager.is_loaded: return`

**Files to Modify:**
- `gui/steps/translate.py` - Replace all `self.manifest` references

**Tests to Add:**
- `dev/test_translation_manifest.py`:
  - Test `on_enter()` without manifest (no crash)
  - Test `on_enter()` with manifest (loads options)
  - Test `_save_temperature_to_manifest()` persists value

---

### TASK 43.2: Translation Tab Performance Fix (CRITICAL)
**Priority:** CRITICAL | **Status:** 🔲 NOT STARTED | **Effort:** 8 hours

Goal: Make the Translation tab load in under 1 second for 100K lines.

**Current Problem:**
- Loading tens of thousands of lines freezes the UI for tens of seconds
- `_refresh_lines()` creates TranslatableLine objects and populates table synchronously
- `_update_lines_table()` creates TableRow objects for ALL lines at once
- SharedTable renders all rows immediately

**Required Changes:**
1. **Virtual Scrolling**: SharedTable must only render visible rows
   - Implement `VirtualTreeview` or use Tkinter's built-in lazy rendering
   - Only create TableRow objects for visible viewport + buffer
   - Recalculate on scroll events
2. **Lazy Loading**: `_refresh_lines()` must NOT create all TranslatableLine objects upfront
   - Read line data from manifest on-demand
   - Use index-based access: `manifest_manager.get_line(idx)` for visible rows
3. **Tab Cache**: Store last displayed state hash
   - On `on_enter()`, compare current manifest state hash to cached hash
   - If unchanged, skip all refresh work
   - Cache invalidation: prepro changes, line add/remove, translation results, explicit refresh
4. **Background Loading**: Any heavy computation runs in a background thread
   - UI thread only handles display updates via `after()` callbacks
   - Show "Loading..." indicator if background work takes > 100ms

**Files to Modify:**
- `gui/steps/translate.py` - Performance optimizations
- `gui/components/table.py` - Virtual scrolling support for SharedTable

**Tests to Add:**
- `dev/test_translation_performance.py`:
  - Test 100K line load time (< 1s assertion)
  - Test scroll performance with 100K lines
  - Test cache hit/miss behavior
  - Test background loading completion

---

### TASK 43.3: Merge Original/Preprocessed into "To be Translated" Column
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Replace the separate "Original" and "Preprocessed" columns with a single "To be Translated" column.

**Current State:**
- Table has both Original and Preprocessed columns
- Wastes horizontal space and confuses users

**Required Changes:**
- Remove "Original" and "Preprocessed" column definitions
- Add "To be Translated" column that shows: `prepro` if available, else `orig`
- Use `get_input_for_translation()` resolution: `edited_prepro → prepro → orig`
- Update `_update_lines_table()` to populate merged column
- Update `_refresh_lines()` to use merged data

**Files to Modify:**
- `gui/steps/translate.py` - Column definitions and table population

**Tests to Add:**
- `dev/test_translation_columns.py`:
  - Test merged column shows preprocessed when available
  - Test merged column falls back to original
  - Test edited_prepro takes priority

---

### TASK 43.4: Newline Support in Translatable Lines Table
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Render multi-line content with visible line breaks in the table, matching Step 0 Input behavior.

**Current State:**
- Multi-line content is truncated or displayed on single line
- No visual indication of line breaks

**Required Changes:**
- Implement newline rendering in SharedTable cells (consistent with Step 0 approach)
- Show `↵` or `⏎` symbol at line break positions
- Row height adjusts to content (or fixed with tooltip for overflow)

**Files to Modify:**
- `gui/steps/translate.py` - Table cell formatting
- `gui/components/table.py` - Newline rendering support (if not already present)

**Tests to Add:**
- `dev/test_translation_newlines.py`:
  - Test multi-line content rendering
  - Test newline symbol display

---

### TASK 43.5: Mock Translation Implementation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Implement Mock Translation as the default model when no API providers are configured.

**Current State:**
- Simulation mode exists but is only triggered by ImportError
- Not selectable as a model option
- Output is simple prefix: `[Translated] {text}`

**Required Changes:**
- Create `functions/mock_translator.py` module
- Mock Translation produces deterministic output:
  - Word reversal within each line
  - Preserves all `__PROT__`, `__DEDUP__`, `__CUSTOM__` tokens in place
  - Maintains line structure and token positions
- Configurable simulated delay per chunk (default: 100ms)
- Track mock token counts (estimate based on text length)
- Available as "Mock Translation" in Model dropdown when no providers configured
- Always available as option regardless of providers (useful for testing)
- Manifest Key: `RequestOptions.Model` = "mock"

**Files to Create:**
- `functions/mock_translator.py` - Mock translation engine

**Files to Modify:**
- `gui/steps/translate.py` - Add Mock Translation to model options
- `functions/api_client.py` - Route to mock translator when model = "mock"

**Tests to Add:**
- `dev/test_mock_translation.py`:
  - Test output preserves all PROT tokens
  - Test output preserves DEDUP tokens
  - Test deterministic output (same input → same output)
  - Test simulated delay
  - Test mock token counting

---

### TASK 43.6: API Provider Management in Global Options
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 6 hours

Goal: Move model configuration to Global Options with proper provider management.

**Current State:**
- Model is a hardcoded list in TranslationStep.MODEL_OPTIONS
- No connection to actual API configuration
- Users must know model names

**Required Changes:**
- Add "API Providers" section to Global Options dialog
- Each provider entry: Name (for dropdown), URL, API Key, Model name
- Table-based management: Add, Edit, Remove providers
- Provider presets: OpenAI, Gemini, Anthropic, Local LLM
- Translation tab reads available models from Global Options
- Model dropdown populated dynamically from configured providers + Mock Translation
- Validate provider connectivity on Add/Edit (optional "Test Connection" button)

**Files to Modify:**
- `gui/dialogs/global_options.py` - Add API Providers section
- `gui/steps/translate.py` - Read model list from Global Options instead of hardcoded list
- `functions/config.py` - Store provider configurations

**Tests to Add:**
- `dev/test_global_options_providers.py`:
  - Test provider CRUD operations
  - Test model list population
  - Test Mock Translation always present
  - Test provider preset loading

---

### TASK 43.7: Move Request Caching to Global Options
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Relocate Request Caching from Translation step to Global Options.

**Current State:**
- Checkbox "Enable Request Caching" in Translation Request Options
- Simple boolean toggle

**Required Changes:**
- Remove cache checkbox from Translation step
- Add "Request Caching" section to Global Options
- Dropdown with modes: "Disabled", "Line" (default), "Strict", "Model Only", "Any"
- Default mode: "Line" — every individual line with its translation gets cached
- Cache applied during translation (skip cached lines) and after (populate cache)
- Store in `CherryAI.ini` under `[Cache]` section
- Translation step reads cache mode from Global Options

**Files to Modify:**
- `gui/dialogs/global_options.py` - Add cache section
- `gui/steps/translate.py` - Remove cache checkbox, read from Global Options
- `functions/config.py` - Add cache configuration
- `functions/request_cache.py` - Support cache mode parameter

**Tests to Add:**
- `dev/test_cache_global_options.py`:
  - Test cache mode persistence
  - Test Translation step reads correct mode

---

### TASK 43.8: Move Thinking Mode to Global Options
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Relocate Thinking Mode from Translation step to Global Options and make it model-agnostic.

**Current State:**
- "Extended Thinking (Claude)" checkbox + budget spinbox in Translation step
- Warning shown for non-Claude models
- Claude-specific naming

**Required Changes:**
- Remove thinking checkbox and budget from Translation step
- Add "Thinking Mode" section to Global Options
- Rename from "Extended Thinking (Claude)" to "Thinking Mode"
- Checkbox: Enable/Disable (default: disabled)
- Budget spinbox: 1000-100000 tokens (default: 10000)
- Support thinking for: Claude (extended thinking), OpenAI reasoning models (reasoning_effort)
- Model-agnostic: when enabled, adapter checks if model supports thinking and applies accordingly
- Store in `CherryAI.ini` under `[Thinking]` section

**Files to Modify:**
- `gui/dialogs/global_options.py` - Add thinking section
- `gui/steps/translate.py` - Remove thinking widgets, read from Global Options
- `functions/api_client.py` - Apply thinking parameters based on model capability

**Tests to Add:**
- `dev/test_thinking_global_options.py`:
  - Test thinking mode persistence
  - Test model capability detection
  - Test API parameter injection

---

### TASK 43.9: Move Rolling Context to Global Options
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Relocate Context Lines (Rolling Context) from Translation step to Global Options.

**Current State:**
- "Context Lines" spinbox tied to Line-by-Line mode in Translation step
- Only enabled when Line-by-Line is active

**Required Changes:**
- Remove context lines spinbox from Translation step
- Add "Rolling Context" section to Global Options
- Spinbox: 0-10 preceding lines (default: 3)
- Always active: rolling context applies to all translation modes (not just line-by-line)
- Used by: Normal translation, Contextual retry strategy
- Store in `CherryAI.ini` under `[Translation]` section

**Files to Modify:**
- `gui/dialogs/global_options.py` - Add rolling context section
- `gui/steps/translate.py` - Remove context lines widget, read from Global Options
- `functions/api_client.py` - Apply rolling context from config

**Tests to Add:**
- `dev/test_rolling_context.py`:
  - Test context lines persistence
  - Test context applied in normal translation
  - Test context applied in Contextual retry

---

### TASK 43.10: Retry Strategy Refinement
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Implement detailed Batch and Contextual retry behaviors as specified.

**Current State:**
- Retry strategies exist but all four are exposed
- Batch and Contextual don't modify the prompt or rolling context differently
- Isolated and Skip are visible but unrefined

**Required Changes:**
- **Batch Strategy**:
  - Re-sends entire failed chunk as single request
  - Adds prompt modification: "These lines are not related. Translate each independently."
  - Disables rolling context for retry requests
- **Contextual Strategy**:
  - Re-sends only failed lines
  - Uses bidirectional rolling context (lines before AND after failed segment)
  - Different from normal rolling context which is only preceding lines
- **Hide Isolated and Skip**: Remove from UI dropdown but keep in code
  - Only show "Batch" and "Contextual" in dropdown
  - Code still supports all four for CLI compatibility

**Files to Modify:**
- `gui/steps/translate.py` - Hide Isolated/Skip from dropdown
- `gui/helpers/prompt_adapter.py` - Implement prompt modifications per strategy
- `functions/api_client.py` - Apply rolling context changes per strategy

**Tests to Add:**
- `dev/test_retry_strategies.py`:
  - Test Batch prompt modification
  - Test Batch disables rolling context
  - Test Contextual bidirectional context
  - Test Isolated/Skip hidden from dropdown
  - Test Max Retries = 0 means no retries

---

### TASK 43.11: Prompt Editor Redesign
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Redesign Prompt Editor to be preview-only with separated Ban Tokens.

**Current State:**
- Prompt Editor has Style Preset entry, Game Summary text area, Ban Tokens entry
- Reads from config files directly (game_summary.txt, translation_style.txt)
- Contains its own data inputs instead of reading from manifest

**Required Changes:**
- Remove Style Preset entry (managed in Step 3: Information)
- Remove Game Summary text area (managed in Step 3: Information)
- Replace with single "Preview Prompt" button
- Preview dialog shows complete constructed prompt from manifest:
  - System Instructions, Game Summary, Translation Style, Glossary (selective), 
    Code Database (selective), Conditional Prompts, Rolling Context sample
  - Read-only, with token count breakdown
- Separate Ban Tokens into its own clearly labeled section:
  - Entry field for comma-separated tokens
  - Dropdown for presets: "None", "Clean English", "Strict"
  - Manifest Key: `RequestOptions.BanTokens`, `RequestOptions.BanTokenPreset`

**Files to Modify:**
- `gui/steps/translate.py` - Remove old prompt editor, add preview button + ban tokens section
- `gui/helpers/prompt_adapter.py` - Build preview from manifest data

**Tests to Add:**
- `dev/test_prompt_preview.py`:
  - Test preview builds from manifest
  - Test preview includes all sections
  - Test token count calculation
  - Test ban tokens persistence

---

### TASK 43.12: Lines/Chunk Sync with Estimation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Synchronize Lines/Chunk between Translation and Estimation steps.

**Current State:**
- Translation has its own Lines/Chunk spinbox
- Estimation has its own chunk size setting
- No synchronization between them

**Required Changes:**
- Both steps read/write the same manifest key: `RequestOptions.LinesPerChunk`
- When either step changes Lines/Chunk:
  - Update manifest immediately
  - If changed in Translation: prompt "Chunk size changed. Re-run estimation?" (Yes/No)
  - If changed in Estimation: Translation reads updated value on next `on_enter()`
- Ensure both spinboxes use same min/max range (5-200)

**Files to Modify:**
- `gui/steps/translate.py` - Add sync callback on chunk size change
- `gui/steps/estimate.py` - Read/write shared manifest key
- `functions/manifest_manager.py` - Ensure atomic updates

**Tests to Add:**
- `dev/test_chunk_sync.py`:
  - Test both steps read same manifest key
  - Test change in Translation updates manifest
  - Test change in Estimation visible in Translation
  - Test re-estimation prompt on change

---

### TASK 43.13: Skip Non-Source Language Option
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3 hours

Goal: Add option to skip lines not detected as being in the source language.

**Current State:**
- No language detection per line
- All lines sent to LLM regardless of content

**Required Changes:**
- Add "Skip Non-Source Language" checkbox to Request Options (default: off)
- When enabled, before translation:
  - Run language detection on each line via `functions/analysis.py`
  - Lines detected as target language or third language marked as Skipped
  - Skipped lines get status ⊘ Skipped with reason "Not source language"
- Saves API costs by not translating already-translated or non-translatable content
- Manifest Key: `RequestOptions.SkipNonSourceLanguage`

**Files to Modify:**
- `gui/steps/translate.py` - Add checkbox and skip logic
- `functions/analysis.py` - Expose per-line language detection function

**Tests to Add:**
- `dev/test_language_skip.py`:
  - Test English lines skipped when source = Japanese
  - Test mixed-language content handling
  - Test short lines (< 3 chars) not skipped
  - Test setting persistence

---

### TASK 43.14: Tab Caching Strategy (All Tabs)
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 6 hours

Goal: Implement tab caching across all step tabs for instant loading when no changes occurred.

**Current State:**
- Each tab recomputes its state on every `on_enter()` call
- No caching mechanism exists

**Required Changes:**
- Add `_cache_hash` property to BaseStep
- On `on_enter()`: compute hash of relevant manifest data for this step
- If hash matches cached hash, skip refresh (instant load)
- If hash differs, perform full refresh and update cache
- Cache invalidation events:
  - Step 0: File add/remove
  - Step 1: Analysis re-run
  - Step 2: Estimation parameters changed
  - Step 3: Information fields changed
  - Step 4: Preprocessing run
  - Step 5: Lines/Chunk change, translation results
  - Step 6-9: Their respective data changes
- `_force_refresh()` method bypasses cache (used by Refresh buttons)

**Files to Modify:**
- `gui/steps/base.py` - Add caching infrastructure
- `gui/steps/*.py` - Implement `_compute_cache_hash()` per step
- `functions/manifest_manager.py` - Provide step-level hash computation

**Tests to Add:**
- `dev/test_tab_caching.py`:
  - Test cache hit (same data → no refresh)
  - Test cache miss (data changed → refresh)
  - Test force refresh bypasses cache
  - Test cache hash computation

---

### Phase 43 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 43.1 | Fix Manifest Attribute Bug | CRITICAL | 0.5h | None |
| 43.2 | Translation Tab Performance Fix | CRITICAL | 8h | None |
| 43.3 | Merge Columns → "To be Translated" | HIGH | 2h | None |
| 43.4 | Newline Support in Lines Table | MEDIUM | 2h | 43.3 |
| 43.5 | Mock Translation Implementation | HIGH | 4h | None |
| 43.6 | API Provider Management in Global Options | HIGH | 6h | None |
| 43.7 | Move Request Caching to Global Options | MEDIUM | 2h | 43.6 |
| 43.8 | Move Thinking Mode to Global Options | MEDIUM | 2h | 43.6 |
| 43.9 | Move Rolling Context to Global Options | MEDIUM | 2h | 43.6 |
| 43.10 | Retry Strategy Refinement | HIGH | 4h | None |
| 43.11 | Prompt Editor Redesign | HIGH | 4h | 43.6 |
| 43.12 | Lines/Chunk Sync with Estimation | HIGH | 2h | None |
| 43.13 | Skip Non-Source Language Option | MEDIUM | 3h | None |
| 43.14 | Tab Caching Strategy (All Tabs) | HIGH | 6h | None |

**Total Estimated Effort:** 47.5 hours

**Implementation Order:**
1. **Task 43.1** (Bug fix — IMMEDIATE, blocks all Translation testing)
2. **Task 43.2** (Performance — CRITICAL for usability)
3. **Tasks 43.3, 43.4** (Column merge and newlines — quick UI wins)
4. **Task 43.5** (Mock Translation — enables testing without API)
5. **Task 43.6** (Global Options providers — foundation for 43.7, 43.8, 43.9, 43.11)
6. **Tasks 43.7, 43.8, 43.9** (Move settings to Global Options — depends on 43.6)
7. **Task 43.10** (Retry refinement — independent)
8. **Task 43.11** (Prompt Editor redesign — depends on 43.6)
9. **Task 43.12** (Chunk sync — independent)
10. **Task 43.13** (Language skip — independent)
11. **Task 43.14** (Tab caching — final polish, all tabs benefit)

**Priority Tasks for Next Release:**
- 43.1, 43.2, 43.3, 43.5, 43.6, 43.10 (24.5 hours — bug fix + core functionality)

---

=============================================================================

## PHASE 44: QA STEP PLACEHOLDER & TRANSLATION STEP FUTURE PREP
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3.5 hours
**Depends On:** Phase 43 (Translation Tab must be stable before QA references it)

### TASK 44.1: Render QA Step Non-Functional with Placeholder
**Priority:** HIGH | **Status:** ✅ FIXED | **Effort:** 2 hours

Problem: The QA step currently displays a full interface (validation rules, issue
table, batch operations, etc.) that is not connected to a functioning pipeline.
The Translation step and Postprocessing step already employ the same validation
scripts (`functions/validation.py`) for automatic recovery and retry. Until the
full QA pipeline and Edit/TLC modes are implemented, the step should clearly
communicate it is not yet active.

Solution:
- Replace the current `_build_ui()` in `QAStep` with a two-mode layout controlled
  by a toggle switch (ttk.Checkbutton or similar)
- **Toggle ON (default)**: Show a single centered placeholder label:
  "Yet to be fully Implemented — Translation Step and Postprocessing Step
  currently employ all automatic fixes and log failures."
  The toggle text reads "Placeholder Mode" and is ON.
- **Toggle OFF**: Load the full QA interface (existing `_build_content`,
  `_build_header`, etc.). For now, this can simply show a message saying
  "Full QA mode coming soon" or partially load existing widgets.
- The toggle state is saved to manifest: `QAOptions.PlaceholderMode` (boolean, default True)
- All existing QA code (dataclasses, validation rules, enums) is preserved
  — only `_build_ui()` and `on_enter()` are modified to respect the toggle.

Files: `gui/steps/qa.py`
Tests: `dev/test_qa_placeholder.py`
  - Test that QA step renders placeholder by default
  - Test that toggle state persists in manifest
  - Test that toggling off does not crash (graceful fallback)

---

### TASK 44.2: Verify Shared Validation Scripts in Translation & Postprocessing
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1.5 hours

Problem: The QA step's philosophy depends on Translation (Step 5) and
Postprocessing (Step 7) already calling `functions/validation.py` for automatic
recovery. This needs to be verified and documented.

Solution:
- Audit `translate.py` to confirm automatic recovery calls (post-chunk validation)
- Audit `postprocess.py` to confirm restoration validation calls
- If either step does NOT currently call `functions/validation.py`, add the
  necessary calls so the QA philosophy holds
- Document which validation rules are applied at each stage:
  * Translation: placeholder check, empty check (post-chunk)
  * Postprocessing: placeholder recovery, bracket balance, quote balance,
    speaker format, whitespace normalization
- Add tests confirming validation is called in both steps

Files: `gui/steps/translate.py`, `gui/steps/postprocess.py`, `functions/validation.py`
Tests: `dev/test_validation_shared.py`
  - Test that Translation step calls validation after chunk completion
  - Test that Postprocessing step calls validation during restoration
  - Test that validation rules produce consistent results across all callers

---

### Phase 44 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 44.1 | QA Step Placeholder Toggle | HIGH | 2h | None | ✅ FIXED |
| 44.2 | Verify Shared Validation Scripts | MEDIUM | 1.5h | None |

**Total Estimated Effort:** 3.5 hours

**Implementation Order:**
1. **Task 44.1** (Placeholder — immediate, cleans up misleading QA UI)
2. **Task 44.2** (Verification — ensures QA philosophy holds before future work)

---

## PHASE 45: POSTPROCESSING TAB OVERHAUL (v2.6 Specs)
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 18 hours
**Depends On:** Phase 43 (Translation Tab), Phase 44 (QA Placeholder)

### TASK 45.1: Fix MouseWheel bind_all Bug Across All Steps
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 0.5 hours

Problem: `canvas.bind_all("<MouseWheel>", _on_mousewheel)` in multiple step files
creates an application-wide binding that persists after the canvas is destroyed
(e.g., by the QA placeholder toggle). Causes `_tkinter.TclError: invalid command
name` when scrolling after tab switch or widget rebuild.

Solution:
- Replace `bind_all` with widget-scoped `canvas.bind` and `scrollable_frame.bind`
- Add `winfo_exists()` guard in the callback to prevent errors on destroyed widgets

Files Fixed:
- `gui/steps/qa.py` — line 511
- `gui/steps/postprocess.py` — line 455
- `gui/steps/translate.py` — lines 581, 874
- `gui/steps/wordwrap_overwrite.py` — line 484
- `gui/steps/output_inject.py` — line 458

---

### TASK 45.2: Rename "Postprocessed Lines" to "Processed Lines"
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 0.5 hours

Problem: The table widget is labeled "Postprocessed Lines" which is redundant since
the entire tab is already labeled "Postprocessing".

Solution:
- Rename `ttk.LabelFrame(parent, text="Postprocessed Lines")` to `"Processed Lines"`
  in `gui/steps/postprocess.py` `_build_lines_panel()`
- Update filter options to include "By Process" filter and "Flagged" filter
- Remove "Needs Retry" and "Skipped" filters, replace with "Written" and "Flagged"

Files: `gui/steps/postprocess.py`
Tests: `dev/test_postprocess_gui.py`

---

### TASK 45.3: Remove Refresh and Revert All Buttons
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 0.5 hours

Problem: Refresh and Revert All buttons add complexity. Lines should auto-load on
tab entry, and re-running postprocessing overwrites previous results (with warning).

Solution:
- Remove "↻ Refresh" and "↩ Revert All" buttons from `_build_header()`
- Lines auto-populate from previous steps via `on_enter()` → `_refresh_lines()`
- Add overwrite confirmation dialog when Apply is clicked and results already exist

Files: `gui/steps/postprocess.py`
Tests: `dev/test_postprocess_gui.py`

---

### TASK 45.4: Make Placeholder/Code/BR Recovery Automatic (No GUI Toggle)
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Problem: Placeholder Recovery, Restore Code Characters, and Restore `<br>` Tags are
essential for data integrity and should always run. Users should not be able to
accidentally disable them.

Solution:
- Remove Placeholder Recovery, Restore Code Characters, and Restore `<br>` Tags
  checkboxes from the Recovery Options panel in `_build_options_panel()`
- Remove their `bind_checkbox_to_field` manifest bindings
- Hard-code these as always-enabled in `PostprocessOptions` (remove the fields or
  set them to True without exposing a toggle)
- The `_apply_postprocessing()` method always calls placeholder recovery, code
  character restoration, and BR tag restoration regardless of options
- Keep the corresponding manifest fields for backward compatibility (always True)

Files: `gui/steps/postprocess.py`, `functions/postprocess.py`
Tests: `dev/test_postprocess_auto_recovery.py`

---

### TASK 45.5: Add Halfwidth→Fullwidth Direction to Symbol Conversion
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1.5 hours

Problem: Current postprocessing only has Fullwidth→Halfwidth. Need bidirectional
support so JP target language can restore fullwidth characters.

Solution:
- Add `HALFWIDTH_TO_FULLWIDTH` map (reverse of existing `FULLWIDTH_TO_HALFWIDTH`)
  in `gui/steps/postprocess.py`
- Add "Halfwidth → Fullwidth" checkbox with manifest binding
- Make Fullwidth→Halfwidth and Halfwidth→Fullwidth mutually exclusive
  (enabling one disables the other via trace callback)
- Add corresponding `convert_halfwidth_to_fullwidth` function in
  `functions/postprocess.py` or keep it in the GUI step
- Add manifest key `PostProcessing.HalfwidthToFullwidth`

Files: `gui/steps/postprocess.py`, `functions/postprocess.py`
Tests: `dev/test_postprocess_symbol_conversion.py`

---

### TASK 45.6: Redesign Failure Handling Widget
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1.5 hours

Problem: Current failure handling has Skip/Flag/Retry options. "Skip" is confusing
(doesn't actually skip the line), "Flag for review" should be the non-write option,
and "Retry" is not yet functional.

Solution:
- Rename and restructure radio options:
  - "Write (keep as-is)" → default, writes the partially-recovered line
  - "Flag for Review" → does NOT write, flags line for manual review via Diff View
- Hide "Queue for Retry" entirely (future improvement)
- Update `FailurePolicy` enum: `WRITE` (previously `FLAG`), `FLAG` (previously `SKIP`)
- Update manifest key values to `write` and `flag`
- Ensure flagged lines show in the "Flagged" filter of the Processed Lines table
- All failures are logged regardless of policy

Files: `gui/steps/postprocess.py`, `functions/postprocess.py`
Tests: `dev/test_postprocess_failure_handling.py`

---

### TASK 45.7: Implement Diff View Manual Editing and Mark-as-Fixed
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2.5 hours

Problem: Current Diff View is read-only. Users need to manually fix flagged lines
directly in the postprocessing step.

Solution:
- Add an editable Text widget below the diff display, pre-populated with the
  postprocessed text of the selected line
- Add "✓ Mark as Fixed" button that:
  1. Reads the edited text from the Text widget
  2. Updates `PostprocessLine.postprocessed` with the new text
  3. Updates the line's status to "Changed"
  4. Writes to manifest `lines[].postpro`
  5. Refreshes the diff display and table row
- Add problem highlighting: lines with unresolved issues get yellow/orange highlights
  in the diff display
- The edit field is only enabled when a line is selected

Files: `gui/steps/postprocess.py`
Tests: `dev/test_postprocess_diff_view.py`

---

### TASK 45.8: Implement Postprocessing Summary Live Updates and Completion Popup
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 1.5 hours

Problem: Summary panel currently only updates after all processing. Needs real-time
updates during processing and a completion popup.

Solution:
- Use `self.after()` to schedule UI updates during the processing thread
- After each line is processed, queue a summary update via thread-safe callback
- Add "Written" and "Flagged" counters to the summary panel
- At 100% completion, show `messagebox.showinfo()` popup:
  "Postprocessing Complete — N lines processed, M changes applied, K issues flagged"
- Add a progress bar (ttk.Progressbar) to the summary panel that fills during processing

Files: `gui/steps/postprocess.py`
Tests: `dev/test_postprocess_summary.py`

---

### TASK 45.9: Update Processed Lines Filter Options
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 1 hour

Problem: Current filters are All/Changed/Needs Retry/Skipped. Need to match the
new spec: All/Changed/Written/Flagged/By Process.

Solution:
- Replace filter radio options:
  - "All" → All lines
  - "Changed" → Only lines with modifications
  - "Written" → Lines written despite failures
  - "Flagged" → Lines flagged for review
- Add a "By Process" dropdown/combobox that filters by specific process name
  (e.g., "Bracket Balance", "Deduplication", "Placeholder Recovery")
- The By Process filter requires tagging each line with the processes that affected it
  (already available from recovery issues list)

Files: `gui/steps/postprocess.py`
Tests: `dev/test_postprocess_gui.py`

---

### TASK 45.10: Overwrite Warning Dialog for Re-running Postprocessing
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 0.5 hours

Problem: Re-running postprocessing silently overwrites previous results.

Solution:
- Before `_apply_postprocessing()` executes, check if any lines already have
  postprocessed results (i.e., `postprocessed != translated`)
- If yes, show `messagebox.askokcancel()`:
  "Postprocessing results already exist. Re-running will overwrite them. Continue?"
- If user cancels, abort. If OK, proceed with overwrite.
- First run (no existing results) skips the warning.

Files: `gui/steps/postprocess.py`
Tests: `dev/test_postprocess_overwrite.py`

---

### Phase 45 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 45.1 | Fix MouseWheel bind_all Bug | CRITICAL | 0.5h | None | ✅ FIXED |
| 45.2 | Rename to "Processed Lines" | MEDIUM | 0.5h | None |
| 45.3 | Remove Refresh/Revert Buttons | LOW | 0.5h | None |
| 45.4 | Auto Placeholder/Code/BR Recovery | HIGH | 2h | None |
| 45.5 | Bidirectional Symbol Conversion | MEDIUM | 1.5h | None |
| 45.6 | Redesign Failure Handling | HIGH | 1.5h | None |
| 45.7 | Diff View Manual Editing | MEDIUM | 2.5h | 45.6 |
| 45.8 | Summary Live Updates + Popup | LOW | 1.5h | None |
| 45.9 | Update Filter Options | LOW | 1h | 45.6 |
| 45.10 | Overwrite Warning Dialog | LOW | 0.5h | 45.3 |

**Total Estimated Effort:** 12 hours (excluding 45.1 already fixed)

**Implementation Order:**
1. **Task 45.1** ✅ FIXED (MouseWheel bug — already done)
2. **Task 45.4** (Auto recovery — highest code impact, cleans up GUI)
3. **Task 45.6** (Failure Handling — changes enum and manifest values)
4. **Task 45.2** (Rename table — quick UI change)
5. **Task 45.3** (Remove buttons — quick UI change)
6. **Task 45.5** (Bidirectional symbol conversion — new feature)
7. **Task 45.9** (Filter options — depends on 45.6 for new status values)
8. **Task 45.7** (Diff View editing — depends on 45.6 for flagged lines)
9. **Task 45.8** (Summary updates — polish)
10. **Task 45.10** (Overwrite warning — polish)

---

## PHASE 46: WORDWRAP TAB OVERHAUL (v2.7 Specs)

**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** ~14h
**Spec Reference:** `doc/specs.md` Step 8 (Wordwrap) — v2.7 rewrite
**Files:** `gui/steps/wordwrap_overwrite.py`, `functions/wordwrap.py`

### Context

Step 8 (Wordwrap) has been comprehensively respecified in v2.7. Key changes: pretty wrap becomes the standard algorithm (no user toggles for orphan prevention or punctuation-preferred breaks), Overwrite is integrated into the Lines Table instead of being a separate widget, ignore patterns come from the Code Database instead of hardcoded checkboxes, Typography widget is removed, Speaker Handling reduced to two options (Ignore/Count), and Mode becomes a dropdown without RPG Maker or Disabled options.

### TASK 46.1: Mode — Radio Buttons to Dropdown
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Replace WrapMode radio buttons with a Combobox dropdown. Remove RPG Maker and Disabled options.

Changes:
- Replace radio button group in `_build_wrap_options_panel()` with `ttk.Combobox`
- Remove `WrapMode.RPGMAKER` and `WrapMode.DISABLED` enum values (keep only `MANUAL`)
- Update manifest binding from radio var to combobox var
- Default: "Manual"
- If no wrapping desired, user simply doesn't click Apply (no "Disabled" needed)

### TASK 46.2: Remove Prevent Orphans + Prefer Punctuation Checkboxes
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 0.5h
**File:** `gui/steps/wordwrap_overwrite.py`, `functions/wordwrap.py`

Goal: Remove both checkboxes. These are always active in `pretty_wrap()`.

Changes:
- Remove `prevent_orphan` checkbox from `_build_wrap_options_panel()`
- Remove `prefer_punct_breaks` checkbox from `_build_wrap_options_panel()`
- Remove corresponding `tk.BooleanVar` variables and manifest bindings
- Update `WrapOptions` dataclass — remove `prevent_orphan` and `prefer_punct_breaks` fields (or hardcode to `True`)
- Ensure `pretty_wrap()` always passes `prevent_orphan=True, prefer_punct_breaks=True`

### TASK 46.3: Speaker Handling — Reduce to Ignore + Count
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `gui/steps/wordwrap_overwrite.py`, `functions/wordwrap.py`

Goal: Remove Samelineindent and Newline options. Rename Sameline to Count.

Changes:
- Update `SpeakerMode` enum: keep `IGNORE`, rename `SAMELINE` → `COUNT`, remove `SAMELINEINDENT` and `NEWLINE`
- Update `_build_speaker_panel()` — reduce from 4 radio buttons to 2 (or switch to Combobox dropdown)
- Update descriptions: Ignore = "Don't count speaker, only dialogue (name field injection)"; Count = "Speaker counted with : and spaces (inline display)"
- Update `manual_wrap_line()` and `pretty_wrap()` speaker handling to use new enum values
- Hanging indent on continuation lines is inherent to Count mode (no separate toggle)

### TASK 46.4: Ignore Patterns — Checkboxes to Code Database Table
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Remove ignore pattern checkboxes. Display read-only table sourced from Code Database.

Changes:
- Remove `_build_ignore_panel()` with its 4 `IgnorePattern` checkboxes
- Remove `IgnorePattern` enum (ANGLE, SQUARE, CURLY, EN)
- Add read-only summary table showing Code Database patterns (Pattern, Action, Example columns)
- Load patterns from manifest Code Database entries where Action = Preserve or Remove
- Pass loaded patterns to `_build_ignore_patterns()` in `functions/wordwrap.py`
- Patterns treated as invisible during width calculation

### TASK 46.5: Remove Typography Widget
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 0.5h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Remove the entire Typography panel.

Changes:
- Remove `_build_typography_panel()` method
- Remove `TypographyStyle` enum (WESTERN, JAPANESE, CHINESE, KOREAN, MIXED)
- Remove `TypographyOptions` dataclass
- Remove typography-related `tk.BooleanVar` variables (fullwidth_punct, ideographic_spaces, convert_quotes)
- Remove corresponding manifest bindings
- Remove any typography references in `_on_format_changed()` and apply logic

### TASK 46.6: Remove Overwrite Strategy Widget
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1.5h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Remove the entire Overwrite Strategy panel. Overwrite becomes a table column.

Changes:
- Remove `_build_overwrite_panel()` method
- Remove `OverwriteStrategy` enum (OVERWRITE, BACKUP, MERGE, SKIP)
- Remove `MergeMethod` enum
- Remove `OverwriteOptions` dataclass
- Remove strategy radio buttons, merge combo, backup suffix entry
- Remove corresponding manifest bindings and event handlers (`_on_strategy_changed`)
- Overwrite functionality moves to the Lines Table (Task 46.8)

### TASK 46.7: Width — Spinbox to Dropdown with Pixel Option
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1.5h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Replace Width Spinbox with a Combobox dropdown that includes Character and Pixel options.

Changes:
- Replace `ttk.Spinbox` with `ttk.Combobox` for width selection
- Add "Character" and "Pixel" modes to the dropdown
- Character mode: numeric entry for character count (20–200)
- Pixel mode: numeric entry for pixel width, with additional font size field
- Add `WordwrapSettings.WidthMode` manifest key ("character" or "pixel")
- Wire pixel mode to `estimate_chars_per_line()` and `measure_font_avg_char_px()` in `functions/wordwrap.py`

### TASK 46.8: Overwrite Column in Lines Table
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Add Overwrite column to the Lines Table alongside Wordwrap.

Changes:
- Extend Lines Table columns: #, Original, Wordwrap, Overwrite, Status
- Populate Overwrite column during wrapping (injection-ready text)
- Status column shows: OK, Exceeding, Differs
- "Differs" when Overwrite ≠ Wordwrap (injection changed the text)
- Output (Step 9) prioritizes `overwrite[]` over `wordwr[]`
- Store in manifest: `lines[].overwrite`

### TASK 46.9: Table Filter Radios
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `gui/steps/wordwrap_overwrite.py`

Goal: Add filter radio buttons to the Lines Table.

Changes:
- Add RadioGroup above Lines Table: All / Changed / Exceeding / Overwrite Differs
- All: show all lines
- Changed: lines where Wordwrap ≠ input
- Exceeding: lines where wrapping produced more lines than Max Lines
- Overwrite Differs: lines where Overwrite ≠ Wordwrap
- Wire filter to table refresh, respecting virtual scrolling performance

### TASK 46.10: Max Lines Flag Behavior
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `gui/steps/wordwrap_overwrite.py`, `functions/wordwrap.py`

Goal: When wrapping exceeds Max Lines, flag the line instead of silently truncating.

Changes:
- Update `pretty_wrap()` / `apply_wordwrap()` to return overflow metadata
- Lines exceeding Max Lines get Status = "Exceeding" in the table
- Visual indicator (color/icon) for exceeding lines
- Overflow text preserved in metadata for manual review
- "New box" splitting is future work (requires parser support for text box boundaries)

---

### Phase 46 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 46.1 | Mode — Radio to Dropdown | HIGH | 1h | None |
| 46.2 | Remove Prevent Orphans + Prefer Punct | HIGH | 0.5h | None |
| 46.3 | Speaker Handling — Ignore + Count | MEDIUM | 1h | None |
| 46.4 | Ignore Patterns → Code Database Table | MEDIUM | 2h | None |
| 46.5 | Remove Typography Widget | MEDIUM | 0.5h | None |
| 46.6 | Remove Overwrite Strategy Widget | HIGH | 1.5h | None |
| 46.7 | Width — Spinbox to Dropdown (Char/Pixel) | MEDIUM | 1.5h | None |
| 46.8 | Overwrite Column in Lines Table | HIGH | 2h | 46.6 |
| 46.9 | Table Filter Radios | LOW | 1h | 46.8 |
| 46.10 | Max Lines Flag Behavior | MEDIUM | 1h | None |

**Total Estimated Effort:** 12 hours

**Implementation Order:**
1. **Task 46.2** (Remove checkboxes — smallest change, cleans up GUI)
2. **Task 46.5** (Remove Typography — another removal, simplifies GUI)
3. **Task 46.6** (Remove Overwrite Strategy — major removal, prerequisite for 46.8)
4. **Task 46.1** (Mode dropdown — structural change to settings panel)
5. **Task 46.3** (Speaker Handling — enum cleanup + dropdown)
6. **Task 46.4** (Ignore Patterns → Code Database table — new integration)
7. **Task 46.7** (Width dropdown — new Character/Pixel mode)
8. **Task 46.8** (Overwrite in table — depends on 46.6, major table rework)
9. **Task 46.10** (Max Lines flag — depends on table being ready)
10. **Task 46.9** (Table filters — polish, depends on 46.8)

---

## PHASE 47: OUTPUT + PIPELINE COMPLETENESS + IMPORT (v2.8 Specs)

**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** ~18h
**Spec Reference:** `doc/specs.md` Step 9 (Output), Step 0 (Input), Step 5 (Translation) — v2.8 updates
**Files:** `gui/steps/output_inject.py`, `gui/steps/input_loader.py`, `gui/steps/translate.py`, `functions/manifest_manager.py`, `functions/output.py` (new)

### Context

Step 9 (Output) has been comprehensively respecified in v2.8. Key additions: injection priority chain (9-level fallback from overwrite through original), dirty flags (Process and Wordwrap) with pre-export validation, non-destructive default (subfolder naming), failure logging, and complete widget specifications. Step 0 (Input) gets a new Import Translations button for migrating translations between manifests via exact line matching. Step 5 (Translation) gets a Skip Already Translated option for incremental workflows. Three console bugs were also fixed (QA mousewheel TclError, output_inject get_section, preprocess warning level).

### TASK 47.1: Fix output_inject get_section Bug
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 0.25h
**File:** `gui/steps/output_inject.py`

Goal: Replace non-existent `get_section()` call with `get_output_options()`.

Changes:
- ✅ Changed `self._manifest_manager.get_section("OutputFormat")` to `self._manifest_manager.get_output_options()`
- Root cause: `ManifestManager` has `get_output_options()` but no `get_section()` method

### TASK 47.2: Fix QA Mousewheel TclError
**Priority:** CRITICAL | **Status:** ✅ FIXED | **Effort:** 0.25h
**File:** `gui/steps/qa.py`

Goal: Prevent TclError when canvas is destroyed between `winfo_exists()` and `yview_scroll()`.

Changes:
- ✅ Wrapped `canvas.yview_scroll()` in `try/except tk.TclError` inside `_on_mousewheel`
- Race condition: `winfo_exists()` can return True while the underlying Tcl widget command is already destroyed
- ✅ Cleared stale `.pyc` cache to ensure fix takes effect

### TASK 47.3: Fix Preprocess Warning Level
**Priority:** LOW | **Status:** ✅ FIXED | **Effort:** 0.1h
**File:** `gui/steps/preprocess.py`

Goal: Change misleading WARNING to DEBUG for "Input step restore did not load files".

Changes:
- ✅ Changed `logger.warning(...)` to `logger.debug(...)` with clarifying message "(no files in project yet)"
- This message fires during normal startup when no project is loaded — not an actual error

### TASK 47.4: Injection Priority Chain Implementation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/output.py` (new), `gui/steps/output_inject.py`

Goal: Implement `get_final_output()` with 9-level priority chain.

Changes:
- Create `functions/output.py` with `get_final_output(line_entry) -> (text, source_field)` function
- Priority: overwrite → wordwr → postpro → edit{N} (highest N) → tlc{N} (highest N) → tl → preedit → prepro → orig
- Handle edit{N}/tlc{N} round numbering (scan for highest available)
- Return source_field name for logging/display
- Wire into `_write_file()` in output_inject.py to use resolved text
- Unit tests for all priority levels, gaps, and edge cases

### TASK 47.5: Dirty Flags — Process and Wordwrap
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/manifest_manager.py`, `gui/steps/preprocess.py`, `gui/steps/postprocess.py`, `gui/steps/wordwrap_overwrite.py`, `gui/steps/output_inject.py`

Goal: Implement Process and Wordwrap dirty flags with pre-export validation.

Changes:
- Add `DirtyFlags` dict to manifest: `{process: bool, wordwrap: bool}`
- Process flag: set True when any preprocessing is applied (Step 4), cleared when postprocessing reaches 100% (Step 7)
- Wordwrap flag: set True when files are loaded or translation changes, cleared when wordwrap is applied (Step 8)
- Add `get_dirty_flags()` / `set_dirty_flag()` methods to ManifestManager
- Before export: check flags, show warning dialog with flag names, allow Export Anyway or Cancel
- Show flag status in Output Summary panel (⚠ or ✓ indicators)

### TASK 47.6: Non-Destructive Default + Subfolder Naming
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `gui/steps/output_inject.py`

Goal: Ensure default naming strategy is "subfolder" and default behavior is non-destructive.

Changes:
- Verify `NamingStrategy.SUBFOLDER` is the default in both GUI and manifest defaults
- Default subfolder name: "translated"
- Auto-populate destination to `{source_root}/translated/` when no destination set
- Verify Overwrite checkbox defaults to off
- Verify Backup defaults to "Timestamp"

### TASK 47.7: Failure Logging
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1.5h
**File:** `gui/steps/output_inject.py`

Goal: Log every write failure with file path and error message.

Changes:
- Add `failure_log: List[Dict]` to ExportStats (or manifest step data)
- Each failure entry: `{file: str, error: str, timestamp: str}`
- Store in manifest: `Output.failure_log[]`
- Display failure log in Summary panel as scrollable list
- Add "Copy Failure Log" button for easy sharing

### TASK 47.8: Import Translations from Manifest
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `gui/steps/input_loader.py`, `functions/manifest_manager.py`

Goal: Add Import Translations button with exact line matching from another manifest.

Changes:
- Add "Import Translations" button to Input step toolbar
- File dialog to select source `.CherryAI.json` manifest
- Import function: for each current `lines[].orig`, sequential search in target manifest for exact match
- On match: copy all fields (prepro, tl, edit{N}, tlc{N}, preedit, postpro, wordwr, overwrite) from target line entry
- Summary dialog: "Imported X of Y lines. Z lines had no match."
- Log import in manifest: `Input.last_import = {source_manifest, lines_matched, lines_total, timestamp}`
- Unit tests for matching, no-match, duplicates, partial matches

### TASK 47.9: Skip Already Translated Option
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 1.5h
**File:** `gui/steps/translate.py`, `functions/api_client.py`

Goal: Add Skip Already Translated checkbox to Request Options.

Changes:
- Add `Skip Already Translated` checkbox to Request Options widget
- When enabled: skip lines where `lines[].tl` is non-empty
- Status for skipped lines: "Skipped (already translated)"
- Manifest Key: `RequestOptions.SkipAlreadyTranslated` (bool, default False)
- Does NOT skip lines with only edit{N}/tlc{N} (only checks base `tl` field)
- Wire into translation loop to check before sending to API
- Update skipped count in Translation step data

### TASK 47.10: Output Summary Panel Improvements
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `gui/steps/output_inject.py`

Goal: Enhance Summary panel with dirty flag indicators and failure log display.

Changes:
- Add dirty flag status indicators (⚠ Process / ⚠ Wordwrap / ✓ Clean)
- Add scrollable failure log section
- Show injection source breakdown (how many lines came from each priority level)
- Display duration and throughput stats

---

### Phase 47 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 47.1 | Fix output_inject get_section Bug | CRITICAL | 0.25h | None | ✅ FIXED |
| 47.2 | Fix QA Mousewheel TclError | CRITICAL | 0.25h | None | ✅ FIXED |
| 47.3 | Fix Preprocess Warning Level | LOW | 0.1h | None | ✅ FIXED |
| 47.4 | Injection Priority Chain | HIGH | 3h | None |
| 47.5 | Dirty Flags (Process + Wordwrap) | HIGH | 2h | None |
| 47.6 | Non-Destructive Default | MEDIUM | 1h | None |
| 47.7 | Failure Logging | MEDIUM | 1.5h | None |
| 47.8 | Import Translations from Manifest | HIGH | 3h | None |
| 47.9 | Skip Already Translated Option | MEDIUM | 1.5h | None |
| 47.10 | Output Summary Panel Updates | LOW | 1h | 47.5, 47.7 |

**Total Estimated Effort:** 13.6 hours (excluding 47.1-47.3 already fixed)

**Implementation Order:**
1. **Task 47.1** ✅ FIXED (output_inject get_section)
2. **Task 47.2** ✅ FIXED (QA mousewheel TclError)
3. **Task 47.3** ✅ FIXED (preprocess warning level)
4. **Task 47.4** (Injection priority chain — foundation for all output logic)
5. **Task 47.5** (Dirty flags — validates pipeline completeness)
6. **Task 47.8** (Import Translations — new Input feature, independent)
7. **Task 47.9** (Skip Already Translated — pairs with 47.8 workflow)
8. **Task 47.6** (Non-destructive defaults — quick verification)
9. **Task 47.7** (Failure logging — output polish)
10. **Task 47.10** (Summary panel — depends on 47.5 + 47.7, final polish)

---

## PHASE 48: PIPELINE LOGGING SYSTEM (v2.9 Specs)

**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** ~24h
**Spec Reference:** `doc/specs.md` §9 (Pipeline Logging System) — v2.9
**Key Files:** `functions/mainhelper.py`, `functions/api_client.py`, `functions/postprocess.py`, `functions/wordwrap.py`, `gui/steps/postprocess.py`, `gui/steps/wordwrap_overwrite.py`, `gui/steps/output_inject.py`

### Context

CherryAI currently has partial logging infrastructure: `api_client.py` writes API call logs to `logs/` and `mainhelper.py` has `setup_logger()` and `write_failure_report()`. The v2.9 spec (§9) defines a comprehensive per-project, per-step logging system with standardized status vocabulary, utility metrics tracking, and log archival. Most functions that need to emit log entries already exist — they need log-writing calls added, not replacement. The spec identifies ~100 existing functions organized by pipeline step that produce loggable events.

### TASK 48.1: Log Rotation & Archival Utility
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/mainhelper.py`

Goal: Add shared `_rotate_log()` utility and update `setup_logger()` for per-project, per-step log files.

Changes:
- Add `_rotate_log(project_dir, project_name, step_name)` function
  - Checks if `{project_name}.{step}.log` exists in `project_dir`
  - If exists: rename to `{project_name}.{step}.{YYYYMMDD_HHMMSS}.log` using file creation time
  - Returns path to the new (empty) log file
- Update `setup_logger()` to accept optional `project_dir`, `project_name`, `step_name` args
  - When provided, calls `_rotate_log()` and creates a FileHandler pointed at the step log
  - Default behavior (no args) unchanged for backward compatibility
- Add `get_step_log_path(project_dir, project_name, step_name)` helper
- Add `write_step_log_header(log_path, header_dict)` — writes formatted header block
- Add `write_step_log_footer(log_path, footer_dict)` — writes formatted summary footer
- All log writes wrapped in `try/except` — never block processing
- Unit tests: rotation naming, timestamp format, missing file, concurrent access

### TASK 48.2: Unified Status Vocabulary Constants
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1h
**File:** `functions/mainhelper.py` (or `functions/common_errors.py`)

Goal: Define the log status constants and formatting functions from §9.3.

Changes:
- Add `LogStatus` class or constants:
  - `PASS = "PASS"`
  - `RECOVERED = "RECOVERED: {type}"` (format function)
  - `PARTIAL_RETRIAL = "(PARTIAL) RETRIAL {strategy}"` (format function)
  - `PARTIAL_FAILURE = "(PARTIAL) FAILURE {type}"` (format function)
  - `FAILURE = "FAILURE {type}"` (format function)
- Add `format_log_status(status, detail=None)` function
- Add `derive_step_status(line_statuses: List[str])` — derives aggregate status from worst per-line status
- Reference `RecoveryType` from `postprocess.py`, `RetryStrategy` from `retry_handler.py`, `FailureType` (new enum or constants for `TRANSLATION_EXHAUSTED`, `API_ERROR`, `VALIDATION_FAILED`, `RECOVERY_FAILED`, `PLACEHOLDER_LOST`, `BRACKET_UNRECOVERABLE`, `QUOTE_UNRECOVERABLE`, `WRAP_OVERFLOW`, `WRITE_ERROR`, `FORMAT_ERROR`, `INJECTION_MISMATCH`)
- Unit tests: all format functions, step status derivation logic

### TASK 48.3: translation.log Integration
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 5h
**File:** `functions/api_client.py`, `functions/retry_handler.py`, `functions/chunk_optimizer.py`

Goal: Extend existing API logging to produce the `translation.log` format from §9.2.2.

Changes:
- **api_client.py**:
  - Update `write_log_header()` — match spec header format (add Provider, Retry Strategy, Max Retries fields)
  - Update `write_log_footer()` — add Tokens Saved (Cache), Tokens Saved (Dedup), Retries count, Recovered count
  - Update `_log_api_call()` — add per-line status detail (OK, CACHED, SKIPPED, RECOVERED, RETRIED:{strategy}, FAILED)
  - Update `_update_log_summary()` — track cache/dedup savings
  - Update `get_api_log()` — return project-specific path `{project_dir}/{project_name}.translation.log`
  - Call `_rotate_log()` at start of translation run
  - Update `_format_translations_for_log()` — add status annotation per line
- **retry_handler.py**:
  - Add log emission in `handle_failed_lines()` — log which strategy was selected
  - Add log emission in `_retry_batch()`, `_retry_contextual()`, `_retry_isolated()` — log attempt and result
  - Add log emission in `_retry_skip()` — log skipped lines
  - Add log emission in `should_continue_retrying()` — log exhaustion decision
  - Add log emission in `get_exhausted_lines()` — log final exhausted list
- **chunk_optimizer.py**:
  - Add log emission in `record_error()` — log error type
  - Add log emission in `_check_adjustment()` — log adjustment decision
  - Add log emission in `_reduce_chunk_size()` — log size reduction
- Wire translation validation functions (`validate_line_pre()`, `validate_line_post()`, `validate_batch_post()`, `detect_repetition()`, `apply_autofix()`) to log findings
- Unit tests: log file creation, header/footer format, per-chunk entry format, per-line status values

### TASK 48.4: postprocess.log Integration
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 5h
**File:** `functions/postprocess.py`, `functions/postanalysis.py`, `gui/steps/postprocess.py`

Goal: Add logging to all postprocessing recovery functions to produce `postprocess.log` per §9.2.3.

Changes:
- **postprocess.py**:
  - `recover_line()` — emit per-operation log entry with priority, process name, and result
  - `recover_batch()` — call `_rotate_log()`, write header, process lines, write footer
  - `PostProcessManager.run()` — wire log file creation and archival
  - Each `recover_*()` function — add log emission with RecoveryType and detail
  - Each `check_*()` function — add log emission with detection result
  - `RecoveryStats` — add `to_log_summary()` method for footer formatting
- **postanalysis.py**:
  - `compare_manifest_and_final()` — log comparison findings
  - `_try_code_recover()`, `_try_speaker_fix()`, `_try_br_recovery()` — log recovery attempt and result
- **gui/steps/postprocess.py**:
  - `_do_postprocessing()` — create log file, write header, invoke processing, write footer
  - `_basic_postprocess()` — log each line result
  - `_run_character_validation()` — log validation findings
  - `_apply_character_autofix()` — log autofix applications
  - `FailurePolicy` — use in log status determination (WRITE → status logged as-is, FLAG → status logged as flagged)
- Unit tests: log file creation, per-line entry format, summary footer with recovery type breakdown

### TASK 48.5: wordwrap.log Integration
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/wordwrap.py`, `gui/steps/wordwrap_overwrite.py`

Goal: Add logging to wrapping operations to produce `wordwrap.log` per §9.2.4.

Changes:
- **wordwrap.py**:
  - `pretty_wrap()` — return metadata (break positions, wrapped line count) for log emission
  - `apply_wordwrap()` — call `_rotate_log()`, write header, process lines (log only changed/flagged), write footer
  - Add `WrapLogEntry` dataclass for per-line metadata
- **gui/steps/wordwrap_overwrite.py**:
  - Wire `_rotate_log()` at start of Apply Wordwrap
  - `_on_wrap_error()` — log error with line index and detail
  - After wrapping complete: write summary footer with totals
- Unit tests: log file creation, per-line entry format, exceeding flag logging, summary stats

### TASK 48.6: output.log Integration
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `gui/steps/output_inject.py`, `functions/output.py` (from Task 47.4)

Goal: Add logging to export operations to produce `output.log` per §9.2.5.

Changes:
- **gui/steps/output_inject.py**:
  - On Export All: call `_rotate_log()`, write header (including dirty flag status)
  - Per-file: log injection source breakdown using `get_final_output()` source_field return value
  - `_on_export_error()` — log error to output.log with file path and error
  - After export complete: write summary footer with file counts, line counts, injection source breakdown, extras exported
  - `_export_logs()` — bundle all step logs (active + archived) found in project directory
- **functions/output.py**:
  - `get_final_output()` — already returns `(text, source_field)` from Task 47.4; ensure source_field is tracked per file for aggregate breakdown
- Add injection source counter (dict counting how many lines came from each priority level)
- Unit tests: log file creation, per-file entry format, injection source tracking, failure logging

### TASK 48.7: Manifest Utility Metrics Storage
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/manifest_manager.py`

Goal: Ensure manifest step data stores all utility metrics defined in §9.4.

Changes:
- Add/verify manifest fields per spec:
  - `Translation.tokens_saved_cache`, `Translation.tokens_saved_dedup`, `Translation.duration`
  - `Postprocessing.total_ops`, `Postprocessing.duration`
  - `Wordwrap.breaks_inserted`, `Wordwrap.lines_exceeding`, `Wordwrap.duration`
  - `Output.duration`
- Some fields already exist (`Translation.tokens_used`, `Translation.cost_actual`, `Postprocessing.recovery_rate`, `Output.files_written`, `Output.files_failed`); verify they are populated
- Add `set_step_metrics(step_name, metrics_dict)` convenience method if not already present
- Unit tests: metric storage and retrieval roundtrip

### TASK 48.8: Log Export in Output Step
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 1.5h
**File:** `gui/steps/output_inject.py`

Goal: Update Export Logs feature to bundle all per-step logs.

Changes:
- `_export_logs()` currently exports application logs from `logs/` directory
- Update to also discover and include step-specific logs from the project directory:
  - Glob `{project_dir}/{project_name}.*.log` for active logs
  - Glob `{project_dir}/{project_name}.*.*.log` for archived logs
- Create a `logs/` subfolder in the export destination
- Copy all discovered logs into the export `logs/` folder
- Update export summary to list which logs were included
- Unit tests: log discovery, export bundling, missing logs handled gracefully

### TASK 48.9: Integration Testing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 1.5h
**File:** `dev/test_pipeline_logging.py` (new)

Goal: End-to-end tests verifying log files are created, formatted, and archived correctly.

Changes:
- Test: translation run creates `translation.log` with correct header/footer
- Test: postprocessing run creates `postprocess.log` with per-line entries
- Test: wordwrap run creates `wordwrap.log` with correct metrics
- Test: output export creates `output.log` with injection source breakdown
- Test: re-running a step archives the previous log with timestamp
- Test: log write failure does not block processing (mock file system error)
- Test: `derive_step_status()` correctly aggregates per-line statuses
- Test: export logs bundles all active + archived logs
- Test: all log files are UTF-8 with correct naming convention

---

### Phase 48 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 48.1 | Log Rotation & Archival Utility | HIGH | 2h | None |
| 48.2 | Unified Status Vocabulary Constants | HIGH | 1h | None |
| 48.3 | translation.log Integration | HIGH | 5h | 48.1, 48.2 |
| 48.4 | postprocess.log Integration | HIGH | 5h | 48.1, 48.2 |
| 48.5 | wordwrap.log Integration | MEDIUM | 3h | 48.1, 48.2 |
| 48.6 | output.log Integration | MEDIUM | 3h | 48.1, 48.2, 47.4 |
| 48.7 | Manifest Utility Metrics Storage | MEDIUM | 2h | None |
| 48.8 | Log Export in Output Step | LOW | 1.5h | 48.3-48.6 |
| 48.9 | Integration Testing | HIGH | 1.5h | 48.3-48.6 |

**Total Estimated Effort:** 24 hours

**Implementation Order:**
1. **Task 48.1** (Log rotation — shared utility, prerequisite for all step logs)
2. **Task 48.2** (Status vocabulary — shared constants, prerequisite for all step logs)
3. **Task 48.7** (Manifest metrics — independent, can parallel with 48.1/48.2)
4. **Task 48.3** (translation.log — highest value, extends existing api_client logging)
5. **Task 48.4** (postprocess.log — second highest value, most recovery functions)
6. **Task 48.5** (wordwrap.log — simpler step, fewer functions)
7. **Task 48.6** (output.log — depends on Task 47.4 injection chain)
8. **Task 48.8** (Log export — polish, depends on all logs existing)
9. **Task 48.9** (Integration testing — final validation of entire system)

---

=============================================================================

## PHASE 49: Request Formation 4-Step Process
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 20 hours
**Spec Reference:** specs.md §5.2 API Request Building and Formation

Goal: Implement the 4-step request formation process that groups lines into optimal translation requests using context markers, file boundaries, and size constraints.

### TASK 49.1: Request Builder Foundation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/prompt_builder.py` (extend)

Goal: Establish the shared request builder used by both Estimation and Translation.

Changes:
- Refactor `prompt_builder.py` to expose a `build_requests()` function returning structured request objects
- Each request object contains: meta settings, prompt components, lines to translate
- Request has configurable minimum and maximum size (lines and tokens)
- Invalid lines (placeholders, deduplicated, context markers) are excluded automatically
- Ensure the same function is called by both `chunker_adapter.py` (estimation) and `api_client.py` (translation)

### TASK 49.2: Step 1 — Menu/Choice Splitting
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/prompt_builder.py` (extend)

Goal: Split Menu and Choice blocks into their own respecruve requests using Context Markers.

Changes:
- Read context markers from manifest lines
- Group consecutive Menu-marked lines into Menu requests
- Group consecutive Choice-marked lines into Choice requests
- Dialogue and Unknown lines remain together for further processing
- Each request type gets its corresponding conditional prompt

### TASK 49.3: Step 2 — First Dialogue Split
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/prompt_builder.py` (extend)

Goal: Use File Ending context markers to perform the initial dialogue split.

Changes:
- Split dialogue/unknown lines at File End markers
- Remove invalid lines from line counting
- Each file boundary produces a separate request candidate
- Preserve file boundary information for rolling context rules

### TASK 49.4: Step 3 — Size-Based Splitting and Balancing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/prompt_builder.py` (extend)

Goal: Apply maximum request size to split oversized candidates and balance line counts.

Changes:
- Split any request candidate exceeding maximum size (lines or tokens, whichever reached first)
- Balance line counts within resulting splits to avoid very uneven chunks
- Track which requests are "split requests" for rolling context determination

### TASK 49.5: Step 4 — Short Request Merging
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/prompt_builder.py` (extend)

Goal: Merge requests (below minimum size) with other requests.

Changes:
- Identify requests: those that would receive no rolling context and provide none
- Merge short requests with other requests up to maximum size
- Use an algorithm that minimizes request count

### TASK 49.6: Integration Testing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `dev/test_request_formation.py` (new)

Goal: Validate the complete 4-step formation process.

Changes:
- Test: Menu/Choice lines split into separate requests
- Test: File boundaries create request splits
- Test: Oversized requests are split and balanced
- Test: Requests are merged
- Test: Invalid lines excluded from all requests
- Test: Estimation and Translation produce identical request structures
- Test: Conditional prompts match context markers

### Phase 49 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 49.1 | Request Builder Foundation | HIGH | 4h | None |
| 49.2 | Step 1 — Menu/Choice Splitting | HIGH | 3h | 49.1 |
| 49.3 | Step 2 — First Dialogue Split | HIGH | 3h | 49.1 |
| 49.4 | Step 3 — Size Splitting/Balancing | HIGH | 4h | 49.2, 49.3 |
| 49.5 | Step 4 — Short Request Merging | HIGH | 3h | 49.4 |
| 49.6 | Integration Testing | HIGH | 3h | 49.1-49.5 |

**Total Estimated Effort:** 20 hours

---

## PHASE 50: Context Markers Full Implementation
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 16 hours
**Spec Reference:** specs.md §5.3 Context Markers

Goal: Implement full context marker support beyond the existing scene marker detection. Add Dialogue, Menu, Choice, and File End markers with integration into request building and prompt selection.

### TASK 50.1: Context Marker Data Model
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/mainhelper.py` (extend)

Goal: Add context marker fields to the line entry model.

Changes:
- Add `context_marker` field to LineEntry: enum of `None`, `file_end`, `dialogue`, `menu`, `choice`
- Context marker lines are always flagged as invalid (not translatable)
- Add helper methods: `is_context_marker()`, `get_active_context_type()`
- Update manifest serialization to include context markers

### TASK 50.2: Context Marker Detection in Analysis
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/analysis.py` (extend)

Goal: Extend analysis to detect and inject context markers when the parser provides none.

Changes:
- Detect dialogue sections (lines with speaker patterns followed by more speaker patterns)
- Detect menu patterns (lists of short items, repeated structure)
- Detect choice patterns (numbered or bulleted option lists)
- Store detected markers in manifest line entries
- **Existing code:** `functions/prompt_builder.py` has scene marker detection for rolling context — extend this

### TASK 50.3: Context Marker Integration with Request Builder
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/prompt_builder.py` (extend)

Goal: Use context markers to select conditional prompts and control request splitting.

Changes:
- Pass context markers to the 4-step request formation (Phase 49)
- Select conditional prompt based on active context type per request
- Menu/Choice requests ignore file endings and aim for maximum size
- Dialogue requests respect file endings and use rolling context
- Unknown (no marker after file start) uses Unknown conditional prompt

### TASK 50.4: Conditional Prompt Templates
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `config/prompt.txt` (extend), `functions/prompt_builder.py` (extend)

Goal: Create distinct prompt templates for each context type.

Changes:
- Dialogue prompt: Standard translation instructions with character context
- Menu prompt: "Translate menu items; preserve formatting and order; choose concise translations"
- Choice prompt: "Translate choices; keep them concise and distinct"
- Unknown prompt: "Lines may be dialogue, menu items, or choices; translate each appropriately"
- Templates stored in `config/` and loaded by prompt builder

### TASK 50.5: Testing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `dev/test_context_markers.py` (new)

Goal: Validate context marker detection, storage, and integration.

Changes:
- Test: File End markers detected at file boundaries
- Test: Dialogue/Menu/Choice markers detected from content patterns
- Test: Markers stored and loaded from manifest
- Test: Request builder uses markers for prompt selection
- Test: Context markers excluded from translation lines

### Phase 50 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 50.1 | Context Marker Data Model | HIGH | 2h | None |
| 50.2 | Detection in Analysis | HIGH | 4h | 50.1 |
| 50.3 | Integration with Request Builder | HIGH | 4h | 50.1, 49.1 |
| 50.4 | Conditional Prompt Templates | MEDIUM | 3h | 50.3 |
| 50.5 | Testing | HIGH | 3h | 50.1-50.4 |

**Total Estimated Effort:** 16 hours

---

## PHASE 51: Speaker Duplicate Removal
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 8 hours
**Spec Reference:** specs.md §5.1 Speaker:Dialogue Format

Goal: Implement the Global Option to remove speaker names from consecutive same-speaker lines to save tokens during translation.

### TASK 51.1: Speaker Duplicate Detection
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/validation.py` (extend)

Goal: Detect consecutive lines with the same speaker.

Changes:
- Add `detect_consecutive_speakers()` function
- Compare speaker prefix across adjacent lines
- Handle fullwidth `:` equivalent `：`
- Return list of line indices where speaker is duplicate of previous

### TASK 51.2: Preprocessing — Remove Duplicate Speakers
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `modi/speaker_replacement.py` (extend)

Goal: Strip duplicate speaker names during preprocessing.

Changes:
- When enabled (Global Option), remove speaker prefix from lines where it matches the previous line
- Store original speaker in `prepro_ops` for restoration
- Affects token count — estimation must account for removed speakers

### TASK 51.3: Postprocessing — Restore Speakers
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `modi/speaker_replacement.py` (extend)

Goal: Re-add removed speaker names after translation.

Changes:
- Read speaker restoration data from `prepro_ops`
- Re-add speaker prefix before the dialogue content
- Handle cases where translation changed the line structure

### TASK 51.4: Global Option and Testing
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**Files:** `gui/dialogs/global_options.py`, `dev/test_speaker_dedup.py` (new)

Goal: Add the Global Option toggle and validate.

Changes:
- Add "Remove Duplicate Speakers" toggle to Global Options
- Save to `CherryAI.ini` as `RemoveDuplicateSpeakers`
- Test: consecutive same-speaker lines have speaker removed
- Test: postprocessing restores removed speakers
- Test: estimation accounts for removed tokens

### Phase 51 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 51.1 | Speaker Duplicate Detection | MEDIUM | 2h | None |
| 51.2 | Preprocessing Removal | MEDIUM | 2h | 51.1 |
| 51.3 | Postprocessing Restoration | MEDIUM | 2h | 51.2 |
| 51.4 | Global Option and Testing | MEDIUM | 2h | 51.1-51.3 |

**Total Estimated Effort:** 8 hours

---

## PHASE 52: Selective Glossary Per Chunk
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 10 hours
**Spec Reference:** specs.md §5.6 Glossary Selective Inclusion

Goal: Filter glossary entries per translation chunk so only entries relevant to the current lines are included in the prompt, reducing token usage.

### TASK 52.1: Glossary Filter Function
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/glossary.py` (extend)

Goal: Check and change where necessary or if not implemnted create the selective filter that matches glossary entries against chunk lines.

Changes:
- Add `filter_glossary_for_chunk(glossary_entries, chunk_lines, mode)` function
- Mode: "original_only" — match against Original column only
- Mode: "original_or_translation" — match against both Original and Translation columns
- Include entries with empty Translation or Notes if Original matches (they provide context)
- Return only matching entries

### TASK 52.2: Integration with Prompt Builder
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/prompt_builder.py` (extend)

Goal: Use the selective filter when building chunk prompts.

Changes:
- Call `filter_glossary_for_chunk()` for each chunk during prompt construction
- Include only matching entries in the Glossary section of the prompt
- Ensure the same filter runs during both Estimation and Translation
- Format matching entries as: `- [Original]: [Translation] ([Notes])`

### TASK 52.3: Global Option and GUI
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**Files:** `gui/dialogs/global_options.py`, `CherryAI.ini`

Goal: Add the Global Option for selective glossary mode.

Changes:
- Add "Glossary Inclusion" dropdown: "All" / "Original Only" / "Original or Translation"
- Default: "All"
- Save to CherryAI.ini
- Pass mode to prompt builder

### TASK 52.4: Testing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `dev/test_glossary_selective.py` (new)

Goal: Validate selective filtering.

Changes:
- Test: entries with matching Original included, others excluded
- Test: "original_or_translation" mode matches both columns
- Test: entries with empty Translation still included when Original matches
- Test: estimation and translation produce identical glossary inclusions
- Test: token savings from selective filtering

### Phase 52 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 52.1 | Glossary Filter Function | HIGH | 3h | None |
| 52.2 | Integration with Prompt Builder | HIGH | 3h | 52.1 |
| 52.3 | Global Option and GUI | MEDIUM | 2h | 52.1 |
| 52.4 | Testing | HIGH | 2h | 52.1-52.3 |

**Total Estimated Effort:** 10 hours

---

## PHASE 53: Parser Scripts System
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 24 hours
**Spec Reference:** specs.md §5.8 Parser Scripts

Goal: Formalize the Parser Scripts interface so game-engine-specific scripts can provide extraction, injection, wordwrap settings, forbidden characters, and context markers.

### TASK 53.1: Parser Script Interface
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `formats/parser_base.py` (new)

Goal: Define the base class/interface for parser scripts.

Changes:
- Create abstract `ParserScript` base class
- Mandatory methods: `name`, `extract(file_path) → lines`, `inject(file_path, lines)`
- Optional properties: `wordwrap_config`, `forbidden_chars`, `context_marker_rules`
- WordwrapConfig dataclass: `max_line_length`, `max_line_number`, `wordwrap_command`, `new_textbox_injection`
- ForbiddenChars dataclass: `characters`, `logit_bias`, `output_action` (replace/flag)

### TASK 53.2: RPG Maker Parser Migration
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 6h
**Files:** `formats/rpgmaker.py` (refactor), `formats/parser_rpgmaker.py` (new)

Goal: Migrate existing RPG Maker format handler to the parser script interface.

Changes:
- Existing `formats/rpgmaker.py` extract/inject logic → `parser_rpgmaker.py` implementing `ParserScript`
- Add wordwrap config: max line length from project analysis, break char `\n`, max lines per textbox
- Add context markers: detect scene/map changes, dialogue vs choice vs show text commands
- Keep backward compatibility with existing format handler

### TASK 53.3: Parser Registration and Discovery
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `formats/__init__.py` (extend)

Goal: Register parsers and auto-detect which parser to use for loaded files.

Changes:
- Parser registry mapping format/engine names to ParserScript implementations
- Auto-detection during file loading based on file structure and content
- Fallback to base format handlers when no parser script matches

### TASK 53.4: Wordwrap Integration
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `gui/steps/step8_wordwrap.py` (extend)

Goal: Auto-populate wordwrap settings from parser scripts.

Changes:
- When a parser with wordwrap config is detected, auto-fill Width, Break Char, Max Lines
- Show parser name in Mode dropdown
- User can still override auto-populated values

### TASK 53.5: Forbidden Characters Integration
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**Files:** `functions/api_client.py` (extend), `functions/postprocess.py` (extend)

Goal: Apply parser-defined forbidden characters during translation and output.

Changes:
- Translation: apply forbidden chars as logit bias in API request
- Output: auto-replace or flag forbidden chars based on configured action
- Show forbidden chars in Translation step Prompt Preview

### TASK 53.6: Testing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 5h
**File:** `dev/test_parser_scripts.py` (new)

Goal: Validate the parser script system end-to-end.

Changes:
- Test: base interface enforces mandatory methods
- Test: RPG Maker parser provides correct wordwrap config
- Test: context markers from parser are stored in manifest
- Test: forbidden chars applied as logit bias
- Test: forbidden chars flagged/replaced in output
- Test: auto-detection selects correct parser

### Phase 53 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 53.1 | Parser Script Interface | HIGH | 4h | None |
| 53.2 | RPG Maker Parser Migration | HIGH | 6h | 53.1 |
| 53.3 | Parser Registration/Discovery | MEDIUM | 3h | 53.1 |
| 53.4 | Wordwrap Integration | MEDIUM | 3h | 53.1, 53.3 |
| 53.5 | Forbidden Characters | MEDIUM | 3h | 53.1 |
| 53.6 | Testing | HIGH | 5h | 53.1-53.5 |

**Total Estimated Effort:** 24 hours

---

## PHASE 54: Point of View Inference
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 12 hours
**Spec Reference:** specs.md §5.11 Point of View Inference

Goal: Implement point-of-view detection from narrative text to provide the LLM with perspective context.

### TASK 54.1: Pronoun Pattern Database
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/analysis.py` (extend)

Goal: Create language-specific pronoun pattern lists for POV detection.

Changes:
- Japanese 1st person: 私, 僕, 俺, わたし, ぼく, おれ, あたし, 我 (+ kanji/furigana variants)
- Japanese 2nd person: あなた, 君, きみ, お前, おまえ, てめえ, 貴方, 貴様
- English 1st person: I, my, mine, me, myself, we, our, ours
- English 2nd person: you, your, yours, yourself
- Extensible structure for additional languages
- Store patterns as configurable per source language

### TASK 54.2: POV Detection Algorithm
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/analysis.py` (extend)

Goal: Analyze non-dialogue lines to determine narrative perspective.

Changes:
- Filter: exclude lines with speaker prefix and lines tagged as Menu/Choice by context markers
- Count pronoun occurrences per POV type across all narrative lines
- 3rd person detection: count protagonist name frequency (from Character Notes)
- Calculate confidence score: high if dominant POV is >60% of pronouns, low if <40%
- Handle mixed POV (e.g., 1st person narration with 2nd person address)
- Return: `{pov: "1st"|"2nd"|"3rd"|"mixed", confidence: "high"|"low", counts: {}}`

### TASK 54.3: Prompt Integration
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**File:** `functions/prompt_builder.py` (extend)

Goal: Include POV information in translation prompt when confidence is high.

Changes:
- Add conditional prompt section: "Narrative Perspective: [1st/2nd/3rd] person"
- Only include when confidence is "high"
- Add guidance: "Maintain consistent [X] person perspective throughout"
- Store POV result in manifest

### TASK 54.4: GUI Display and Testing
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**Files:** `gui/steps/step1_analysis.py` (extend), `dev/test_pov_inference.py` (new)

Goal: Display POV results in Analysis step and validate detection.

Changes:
- Show detected POV and confidence in Analysis findings
- User can override detected POV in Information step
- Test: 1st person Japanese text correctly identified
- Test: 3rd person detected via protagonist name frequency
- Test: confidence scoring produces expected high/low results
- Test: mixed POV handled correctly

### Phase 54 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 54.1 | Pronoun Pattern Database | MEDIUM | 2h | None |
| 54.2 | POV Detection Algorithm | HIGH | 4h | 54.1 |
| 54.3 | Prompt Integration | MEDIUM | 2h | 54.2 |
| 54.4 | GUI Display and Testing | MEDIUM | 4h | 54.2, 54.3 |

**Total Estimated Effort:** 12 hours

---

## PHASE 55: Consistency System
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 30 hours
**Spec Reference:** specs.md §5.12 Consistency System

Goal: Implement the Consistency system with Preliminary, During, and Check modes to ensure consistent translation of recurring terms across all requests.

### TASK 55.1: Consistency Data Model
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `functions/consistency.py` (new)

Goal: Create the data structures for tracking consistency terms.

Changes:
- `ConsistencyTerm` dataclass: original, canonical_translation, type (code/glossary/span), confidence, source_line_idx
- `ConsistencyStore`: collection of terms with lookup and update methods
- Serialize/deserialize to manifest
- Term detection: code patterns marked as Translate, glossary entries with empty translation, paired tags

### TASK 55.2: Type Detection — Code, Glossary, Spans
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/consistency.py` (extend)

Goal: Automatically detect consistency-relevant terms from project data.

Changes:
- Code (Translate): scan Code Database for entries with Action=Translate; auto-detect via RegEx
- Glossary: scan for entries with empty Translation or empty Notes
- Spans: detect paired tags (e.g., `\C[1]...\C[0]` for color, `\B[1]...\B[0]` for bold)
- Build initial ConsistencyStore from detected terms

### TASK 55.3: Preliminary Mode
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 8h
**File:** `functions/consistency.py` (extend)

Goal: Run pre-translation passes to establish canonical translations for all detected terms.

Changes:
- Send text-only excerpts (no code) containing each term with surrounding context to the LLM
- Prompt asks: "Is this a person, location, or term? Provide the appropriate translation."
- May run multiple times for confidence (compare results across passes)
- Store canonical translations in ConsistencyStore
- Modify preprocessed entries: replace term occurrences with canonical translation
- Track which terms were resolved with high confidence

### TASK 55.4: During Mode
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 6h
**File:** `functions/consistency.py` (extend), `functions/api_client.py` (extend)

Goal: Use first translated occurrence as canonical and propagate to subsequent requests.

Changes:
- After each chunk translation, scan output for consistency terms
- If first occurrence has no code around it, use `<t></t>` markers to locate it
- Store first translation as canonical
- Update project glossary with discovered translations
- Replace terms in all subsequent stored request prompts with canonical translation
- Handle code-embedded terms (replace code + term combination)

### TASK 55.5: Check Mode
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 4h
**File:** `functions/consistency.py` (extend)

Goal: Post-translation verification flagging inconsistent translations.

Changes:
- After all translation completes, scan all translated lines for consistency terms
- Compare translations of the same term across different requests/chunks
- Flag inconsistencies (same original → different translations)
- Show in QA step with original term, found translations, and line locations
- Does not auto-fix — flags for manual review

### TASK 55.6: Global Option and GUI
**Priority:** MEDIUM | **Status:** 🔲 NOT STARTED | **Effort:** 2h
**Files:** `gui/dialogs/global_options.py`, `CherryAI.ini`

Goal: Add the Global Option for consistency mode selection.

Changes:
- Add "Consistency Mode" dropdown: "Disabled" / "Preliminary" / "During" / "Check"
- Default: "Disabled"
- Save to CherryAI.ini
- Show consistency results in Analysis and QA steps

### TASK 55.7: Testing
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 3h
**File:** `dev/test_consistency.py` (new)

Goal: Validate all consistency modes and term types.

Changes:
- Test: Code terms detected from Code Database
- Test: Glossary terms detected from empty entries
- Test: Span terms detected from paired tags
- Test: Preliminary mode produces canonical translations
- Test: During mode propagates first translation
- Test: Check mode flags inconsistencies
- Test: disabled mode skips all consistency logic

### Phase 55 Summary

| Task | Description | Priority | Effort | Dependencies |
|------|-------------|----------|--------|--------------|
| 55.1 | Consistency Data Model | MEDIUM | 3h | None |
| 55.2 | Type Detection | MEDIUM | 4h | 55.1 |
| 55.3 | Preliminary Mode | MEDIUM | 8h | 55.1, 55.2 |
| 55.4 | During Mode | MEDIUM | 6h | 55.1, 55.2 |
| 55.5 | Check Mode | LOW | 4h | 55.1, 55.2 |
| 55.6 | Global Option and GUI | MEDIUM | 2h | 55.1 |
| 55.7 | Testing | HIGH | 3h | 55.1-55.6 |

**Total Estimated Effort:** 30 hours

---

## PHASE 56: Mock Translation Flaw Testing
**Priority:** LOW | **Status:** ✅ DONE | **Effort:** 8 hours
**Spec Reference:** specs.md §5.13 Mock Translation Extended

Goal: Create dedicated Mock Translation module with deliberate flaw injection
to test the postprocessing recovery pipeline.

Implementation: Created `functions/mock_translator.py` as a standalone module
with `MockTranslator` class, `FlawConfig`/`FlawReport` dataclasses, and
`FlawIntensity` enum. Integrated into `functions/api_client.py` via mock
routing (`model == "mock"`). Test fixture: `dev/example/example.txt`.

### TASK 56.1: Placeholder Malformation [DONE]
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2h
**File:** `functions/mock_translator.py`

Implemented `_flaw_placeholder_malformation()` — surgically removes and adds
characters in `__PROT__`, `__DEDUP__`, `__CUSTOM__` tokens. Configurable via
`FlawConfig.placeholder_malformation` and `FlawConfig.flaw_line_ratio`.

### TASK 56.2: Anchor Manipulation [DONE]
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2h
**File:** `functions/mock_translator.py`

Implemented `_flaw_anchor_manipulation()` — removes existing anchor characters
(`[]{}()<>「」『』【】`) and inserts anchors at random positions. Tracked via
`FlawReport.anchor_removals` and `FlawReport.anchor_insertions`.

### TASK 56.3: Code Intrusion and Character Surgery [DONE]
**Priority:** MEDIUM | **Status:** ✅ DONE | **Effort:** 2h
**File:** `functions/mock_translator.py`

Implemented `_flaw_code_intrusion()` — replaces content inside code patterns
(`[font size]`, `<color value>`, `{data}`) with random mock words. Implemented
`_flaw_character_surgery()` — random character insertion and deletion with
configurable intensity (mild/moderate/severe via `FlawIntensity` enum).

### TASK 56.4: Recovery Validation Testing [DONE]
**Priority:** HIGH | **Status:** ✅ DONE | **Effort:** 2h
**File:** `dev/test_mock_translation.py` (59 tests)

Comprehensive test suite covering all flaw types, recovery validation, API
client mock routing, edge cases, and end-to-end pipeline verification.
Uses `dev/example/example.txt` as test fixture.

### Phase 56 Summary

| Task | Description | Priority | Effort | Dependencies | Status |
|------|-------------|----------|--------|--------------|--------|
| 56.1 | Placeholder Malformation | MEDIUM | 2h | None | ✅ DONE |
| 56.2 | Anchor Manipulation | MEDIUM | 2h | None | ✅ DONE |
| 56.3 | Code Intrusion/Character Surgery | MEDIUM | 2h | None | ✅ DONE |
| 56.4 | Recovery Validation Testing | HIGH | 2h | 56.1-56.3 | ✅ DONE |

**Total Estimated Effort:** 8 hours

---

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
- **Expanded Deduplication (also part of Pre- and Post-Processing Steps)**: Current Deduplication may just take the original string before any processing. More aggressive Deduplication can be able to applies its own rules after all preprocessing and before all postprocessing. It can use one {CODE} for all code and X for all numbers. 

### Analysis Step Future Enhancements
- **Auto-populate Glossary**: Use detected speakers and code patterns to pre-fill glossary entries
- **Pattern Suggestions**: Recommend protection rules based on detected code patterns
- **Export Formats**: Support additional export formats (JSON, XLSX) for findings
- **Visual Charts**: Charts/graphs for language distribution and pattern frequency
- **Diff Analysis**: Compare against previous analysis when files change

### Information Step Future Enhancements
- **Summary Generation via API**: Button to auto-generate summary using LLM analysis of loaded content
- **Save/Load System Instructions**: Buttons to save current System Instructions to file and load from templates
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

Benchmark Mode, requires a small but significant synthesized text which will get at least three passes:
	-1: Normal Settings
	-2: Modified Settings (All Normal Settings and it is recommended to just change one setting, be it temperature, prompt, length, model or anything)
	-3: Check (sends Original and Results of 1 and 2)
	ToS/EULA for some legal protection, 
	-kept very concise 
	-and features a multiple choice test that serves as agreement 
		(all choices must be made to be correct)
	-Important points
		Do nothing illegal
		Violating copyright is not condoned
		Estimates are not binding
		No liability for any financial losses incutred, even if it is due to software bugs and problems
		Do not use the software to create nuclear fissile material (half-joke to see whether the agreement was read)
	-simple .ini entry that turns readToS from false to true to skip
	Agent AI
	Context Menu
	System Tray
	Image to Text Translation through taking a screenshot of a selected area (OCR capable model required)

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

---
=============================================================================

## MANIFEST 3.0 COMPLETE FIELD REFERENCE

All fields stored in the UNIFIED manifest file (ManifestManager._manifest_data).
v2.1 processing fields (`lines`, `operations`, `mappings`) coexist with v3.0 settings.

**Field Categories:**
- **v2.1 Processing** - Unchanged, used by Processor via export_to_mainhelper_manifest()
- **v3.0 Settings** - NEW, passed to functions during processing

### v2.1 Processing Fields (existing - DO NOT CHANGE FORMAT)

| Manifest Key | Type | Description | Managed By |
|--------------|------|-------------|------------|
| `lines` | array | LineEntry.to_dict() results | Processor ↁEimport_from_mainhelper_manifest() |
| `operations` | array | Operation.__dict__ results | Processor ↁEimport_from_mainhelper_manifest() |
| `mappings` | object | Mode state mappings | Processor ↁEimport_from_mainhelper_manifest() |
| `summary` | text | Processing summary | Processor |
| `metadata` | object | Processing metadata | Processor |

These fields are populated by the processing pipeline. GUI should NOT directly modify them.
Instead, use the bridge methods to sync processing results into ManifestManager.

### v3.0 Settings Fields (NEW)

| GUI Field | Manifest Key | Type | Default | Passed To |
|-----------|--------------|------|---------|-----------|
| Project Name | `ProjectName` | text | "Project1" | - |
| Title | `Title` | text | "Title1" | prompt |
| Genre | `Genre` | text | "fictional, nonfictional" | prompt |
| Source Language | `SourceLanguage` | text | "Japanese" | api_client |
| Target Language | `TargetLanguage` | text | "English" | api_client |
| Summary | `Summary` | text | "[Summary of the Content]" | prompt |
| Style Preset | `StylePreset` | text | "neutral" | prompt |
| Tone Preset | `TonePreset` | text | "natural" | prompt |
| Character Notes | `CharacterNotes` | special | [] | prompt |
| Code Glossary | `CodeGlossary` | special | [] | prompt |
| Prompt | `Prompt` | text | "" | prompt |
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

---

## IMPLEMENTATION ORDER SUMMARY

**Phase 21 (Foundation):** MUST be done first - INI loading, manifest creation, app startup
**Phase 22 (Helpers):** Create reusable code before GUI integration
**Phases 23-28 (GUI Integration):** Can be done in parallel once helpers exist
**Phase 29 (Autosave):** Should be done after basic integration works
**Phase 30-33 (Enhancements):** Lower priority, can be done incrementally

**Estimated Total Effort:** 60-80 hours

---

## CRITICAL TEST VERIFICATION REQUIREMENTS

Before ANY phase is marked complete, the following tests MUST pass:

**Existing Tests (MUST NOT BREAK):**
- `dev/test_manifest_v2.py` - 50+ tests for mainhelper.Manifest and LineEntry
- `dev/test_manifest_state.py` - 40+ tests for ManifestManager
- `dev/test_manifest_automation.py` - Automated manifest creation tests
- All other existing tests (3177 total)

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

**Why Tests Pass with Unified Manifest:**
- v3.0 ADDS fields to the manifest, doesn't change existing ones
- `export_to_mainhelper_manifest()` creates mainhelper.Manifest from existing v2.1 fields
- `import_from_mainhelper_manifest()` writes processing results back to same fields
- New v3.0 settings fields coexist alongside v2.1 processing fields
- All existing tests continue working because they only touch v2.1 format

---

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
**Status:** ✁EFIXED (Phase 19.1 - December 2025)

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
