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

**Current Status:** 6278 tests passing (verified Q2 2026 via pytest)

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
- gui/dialogs/: 3 dialog modules (global_options, project_dialog, loading_progress)

=============================================================================

=============================================================================
[Archived: Sessions 43–24 + Phase 62 → see doc/archived.md]


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
- Model dropdown from api_config.get_default_model()
- Batch size spinbox (1–100, default 10)
- API.ini [term_translation] profile stores provider/key_name/model
- RuntimeError on missing key or API failure, caught in analysis.py

**Gender Inference:**
- Mode dropdown: Script only / Script + LLM
- "Script only" runs heuristic pass with configurable confidence (min/max)
- "Script + LLM" runs script first, then LLM on remaining unknowns
- Separate API key/model controls (stored in API.ini [gender_inference])
- LLM confidence spinboxes (min/max, default 3/5)
- ignore_unknown / do_all checkboxes for both script and LLM
- RuntimeError on LLM failure shown via messagebox

**UtilitySettings dataclass:** Expanded from 1 to 17 fields with full
to_dict/from_dict roundtrip and legacy mode migration.

**Files Modified:**
- `gui/dialogs/global_options.py` — UtilitySettings, _build_utility_section, _on_apply, save defaults
- `functions/term_translation.py` — Rewritten: batch splitting, API.ini profile, RuntimeError
- `functions/API2Glossary.py` — infer_gender_llm(), _has_consensus(), _call_api_for_excerpt_custom()
- `gui/steps/analysis.py` — try/except RuntimeError in _worker()
- `gui/steps/information.py` — Rewritten _infer_character_genders() with two modes

**Tests:**
- `dev/test_utility_settings.py` — 27 unit tests (dataclass, batching, consensus, error abort)
- `dev/test_utility_integration.py` — 7 live API tests with gpt-4.1-nano
- `dev/test_term_translation.py` — Updated assertion (52 tests, all pass)

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

END OF ROADMAP
=============================================================================