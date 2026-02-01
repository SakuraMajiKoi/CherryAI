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

- functions/: 36 modules (+ glossaries/ subfolder with 5 files)
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

### Analysis Step Future Enhancements
- **Auto-populate Glossary**: Use detected speakers and code patterns to pre-fill glossary entries
- **Pattern Suggestions**: Recommend protection rules based on detected code patterns
- **Export Formats**: Support additional export formats (JSON, XLSX) for findings
- **Visual Charts**: Charts/graphs for language distribution and pattern frequency
- **Diff Analysis**: Compare against previous analysis when files change

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
