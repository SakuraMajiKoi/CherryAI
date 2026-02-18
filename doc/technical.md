CHERRYAI - TECHNICAL DOCUMENTATION

For Developers

=============================================================================

INSTRUCTIONS
---------------------

CRITICAL ARCHITECTURE PRINCIPLE:
The GUI must NOT contain processing logic. All processing functions belong 
in shared modules (functions/, modi/, formats/) that both CLI and GUI use.

GUI CODE RULES:
- gui/ modules handle ONLY display, user interaction, and state management
- NO text manipulation, parsing, or translation logic in GUI code
- Use functions/ modules for all shared processing logic
- Modi plugins handle all pre/post-processing transformations
- Formats handlers manage all file I/O operations

MODULE AWARENESS (Always check these when implementing features):
- functions/    : 46 modules - core shared functionality (+ glossaries/ subfolder with 5 files)
- modi/         : 12 processing modes - pre/post-processing plugins
- formats/      : 8 format handlers - file I/O for CSV, TXT, JSON, etc.
- gui/steps/    : 10 workflow tabs - display and user interaction only
- gui/components/: Reusable UI widgets (1 module: table.py)
- gui/dialogs/  : Modal dialogs and forms (4 modules: global_options.py, project_dialog.py, input_dialog.py, loading_progress.py)
- gui/helpers/  : 7 adapter modules bridging GUI config to processing (mode, analysis, glossary, chunker, prompt, manifest_binding, tooltip)
- gui/state/    : Application state management (1 module: store.py)

BEFORE MAKING CHANGES:
1. Check if functionality exists in functions/ or modi/
2. If processing logic, add to appropriate functions/ module
3. If file I/O, use or extend formats/ handlers
4. GUI code should call these modules, never duplicate logic
5. Run tests after changes: python dev/test_*.py

CROSS-REFERENCE DOCUMENTATION:
- User features: doc/features.md
- Test coverage: doc/tests.md
- Outstanding work: doc/todo.md
- Integration audit: doc/phase15_doc_integration.md

=============================================================================

TABLE OF CONTENTS
-----------------

1. ARCHITECTURE OVERVIEW
   1.1 Import Architecture & Circular Dependency Resolution
   1.2 Static Typing & Mypy
   1.3 Project Structure Overview

2. CORE CONCEPTS
   2.1 Operation Dataclass - Processing unit with protection data
   2.2 Manifest v3.0 & LineEntry - Per-line metadata system with GUI state
   2.3 prepro_ops Field - Pre-processing operation tracking
   2.4 Processor Class - Core text processing engine

3. FUNCTIONS/ MODULES (46 files - Core Shared Logic)
   ✅ = Verified exists | ⚠️ = Needs documentation | 🔗 = GUI integrated
   
   3.1  analysis.py ✅ - File analysis, metrics, glossary extraction
   3.2  API2Glossary.py ✅ - Extract glossary terms via LLM
   3.3  api_client.py ✅🔗 - LLM API communication (Step 5)
   3.4  auto_tagger.py ✅ - Automatic line tagging/classification
   3.5  chunker.py ✅ - Text chunking for API batches
   3.6  chunk_optimizer.py ✅ - Optimize chunk boundaries
   3.7  CLI.py ✅ - Command-line interface entry point
   3.8  cli_io.py ✅ - CLI IO adapter to formats module (TASK 16.10)
   3.9  common_errors.py ✅ - Error codes and messages
   3.10 conditional_prompts.py ✅ - Pattern-triggered AI instructions
   3.11 config.py ✅ - Configuration persistence
   3.12 dedup.py ✅ - Deduplication with aggressive mode
   3.13 dependencies.py ✅ - Dependency checks
   3.14 glossary.py ✅ - Unified glossary system
   3.15 languages.py ✅ - Language definitions (single source of truth)
   3.16 local_llm.py ✅ - Local LLM integration
   3.17 logit_bias.py ✅ - Token logit bias for API
   3.18 mainhelper.py ✅ - Core Processor, Manifest, Operation
   3.19 modehelper.py ✅ - Modi mode selection utilities
   3.20 One_Click_Test.py ✅ - 7-stage integration test
   3.21 options.py ✅ - Option management
   3.22 postanalysis.py ✅ - Post-translation analysis
   3.23 postprocess.py ✅🔗 - Post-processing utilities (Step 6, moved from Step 7)
   3.24 project_config.py ✅ - Per-project configuration
   3.25 prompt_builder.py ✅ - Build system prompts for API
   3.26 rate_limiter.py ✅ - API rate limiting
   3.27 replication.py ✅ - Translation replication/update detection
   3.28 request_cache.py ✅ - Cache API requests
   3.29 retry_handler.py ✅ - Retry logic for API calls
   3.30 style_presets.py ✅ - Translation style presets
   3.31 validation.py ✅🔗 - Translation validation (Step 8, moved from Step 6)
   3.32 wordwrap.py ✅🔗 - Word wrapping (Step 7, moved from Step 8)
   3.33 ini_manager.py ✅ - INI path resolution and typed access (TASK 21.1)
   3.34 manifest_manager.py ✅🔗 - Unified manifest state management (TASK 19)
   3.35 manifest_fields.py ✅ - Manifest field type helpers (TASK 22.1) + special format helpers (TASK 22.2)
   3.36 preset_manager.py ✅ - Preset save/load/delete operations (TASK 30.1)
   3.37 mock_translator.py ✅ - Mock translation engine with flaw injection (Phase 56)
   3.38 consistency.py ✅ - Consistency system for term translation tracking (Phase 55)
   3.39 auto_pipeline.py ✅🔗 - Automatic pipeline orchestrator (Phase 58)
   3.40 agent_modes.py ✅ - Agent-assisted processing modes (Phase 17.8)
   3.41 batch_tracker.py ✅ - Batch API job tracking (Phase 17.1)
   3.42 key_manager.py ✅ - Multi-key rotation for API load distribution (Phase 17.2)
   3.43 output.py ✅🔗 - Output generation utilities (Phase 31, Step 8)
   3.44 process_order.py ✅🔗 - Pre/post processing order management (Phase 26)
   3.45 usage_tracker.py ✅ - API usage analytics and tracking (Phase 17.5)
   3.46 estimation.py ✅ - Token estimation utilities (legacy CLI support)
   
   3.47 glossaries/ (subfolder - 5 files)
        - __init__.py - Package exports
        - code_glossary_constants.py - Code pattern definitions
        - code_glossary_functions.py - Code detection/classification
        - name_glossary_constants.py - Speaker patterns, romanization
        - name_glossary_functions.py - Speaker detection, gender inference

4. MODI/ MODULES (12 modes - Pre/Post Processing Plugins)
   ✅ = Verified exists | 🔗 = GUI integrated via mode_adapter | ❌ = Not integrated with GUI v2
   
   4.1  __init__.py ✅ - Mode loader, get_modi(), MODE_REGISTRY
   4.2  anchor.py ✅❌ - Anchor-based text protection
   4.3  custom_placeholder.py ✅❌ - User-defined placeholder replacement
   4.4  free.py ✅❌ - Free-form processing mode
   4.5  only_remove.py ✅❌ - Remove-only pattern mode
   4.6  protect_code.py ✅🔗 - Code protection → __PROT__ placeholders (via mode_adapter)
   4.7  replace_after.py ✅❌ - Post-translation replacement
   4.8  replace_before.py ✅❌ - Pre-translation replacement
   4.9  sabotage.py ✅❌ - Sabotage/corruption detection
   4.10 standard_mode.py ✅🔗 - Standard preprocessing (ellipsis, symbols via mode_adapter)
   4.11 template_mode.py ✅❌ - Template-based processing
   4.12 temporary_replacement.py ✅❌ - Temp replacement with restore

5. FORMATS/ MODULES (8 handlers - File I/O)
   ✅ = Verified exists | 🔗 = GUI integrated
   
   5.1 __init__.py ✅🔗 - FormatHandler base, FormatRegistry, ParserRegistry (Step 0)
   5.2 simple.py ✅🔗 - TXT, CSV, TSV, JSON, XLSX handlers (Step 0)
   5.3 document.py ✅ - PDF, EPUB handlers (placeholder)
   5.4 html.py ✅ - HTML parsing (under development)
   5.5 rpgmaker.py ✅ - RPG Maker MV/MZ (placeholder)
   5.6 parser_base.py ✅ - ParserScript ABC, WordwrapConfig, ForbiddenChars, ContextMarkerRules
   5.7 parser_rpgmaker.py ✅ - RpgMakerMVParser, RpgMakerMZParser implementations
   5.8 json_lenient.py ✅ - Lenient JSON parsing with error recovery

6. GUI V2 ARCHITECTURE (gui/ - 7 packages)
   
   6.1 gui/__init__.py - Package exports (App)
   6.2 gui/app.py - Main application window, step orchestration
   6.3 gui/progress.py - ProgressTracker, ProgressPanel
   
   6.4 gui/steps/ (10 files - 10 workflow tabs)
       - __init__.py - Step exports
       - base.py - BaseStep abstract class (TASK 43.14: tab caching infra)
       - input_extract.py - Step 0: Input/Extraction 🔗formats/
       - analysis.py - Step 1: Analysis ❌NO shared imports
       - costs.py - Step 2: Costs (renamed from estimate.py in Phase 40)
       - information.py - Step 3: Information ❌NO shared imports (moved from Step 2)
       - preprocess.py - Step 4: Preprocessing ❌NO shared imports (moved from Step 3)
       - translate.py - Step 5: Translation 🔗api_client, mock_translator (Phase 43: merged columns, mock translation, provider model list, language skip, prompt editor redesign, retry refinement, tab caching)
       - postprocess.py - Step 6: Postprocess 🔗postprocess (moved from Step 7)
       - wordwrap_overwrite.py - Step 7: Wordwrap 🔗wordwrap (moved from Step 8)
       - qa.py - Step 8: QA 🔗validation (moved from Step 6)
       - output_inject.py - Step 9: Output/Inject ❌NO shared imports
   
   6.5 gui/components/ (2 files)
       - __init__.py - Component exports
       - table.py - SharedTable, ColumnDef, TableRow (Phase 43: batch insertion for large datasets; Phase 17: version tracking to cancel stale batches)
   
   6.6 gui/dialogs/ (5 files - 4 dialog modules)
       - __init__.py - Dialog exports
       - global_options.py - GlobalOptionsDialog with section panels:
         - OptionSection enum: API, REQUEST, CACHING, LOGGING, SESSION, SAFETY, FILE_IO, PROMPTS
         - Settings dataclasses: APISettings, RequestSettings, CachingSettings, LoggingSettings,
           SessionSettings, SafetySettings, FileIOSettings, PromptsSettings
         - APIProviderEntry dataclass: name, provider_type, url, api_key, model (Task 43.6)
         - PROVIDER_PRESETS: 5 provider presets (Task 43.6)
         - _ProviderEditDialog, _PresetPickerDialog helper dialogs (Task 43.6)
         - GlobalOptions container: all settings + providers list, get_model_list(), get_provider_for_model()
         - RequestSettings: +thinking_enabled, +thinking_budget, +rolling_context_lines (Tasks 43.8, 43.9)
         - CachingSettings: +cache_mode (Task 43.7)
         - Sections organized in CATEGORY_ORDER: Connection, Processing, Application
         - TASK 33.2: PromptsSettings for Edit/TLC custom prompts
           - edit_prompt: str - Custom prompt for Edit steps
           - tlc_prompt: str - Custom prompt for TLC steps  
           - Supports {source_lang} and {target_lang} placeholders
           - Stored in [prompts] section of config/defaults.ini
       - project_dialog.py - Project management dialogs (TASK 19, TASK 21.4, Phase 58.11):
         - ProjectNameDialog: Prompt for project name on new project creation (500x280, empty name field)
         - LoadManifestDialog: File browser for loading existing manifests (sorted by date, latest first)
         - WelcomeDialog: First launch dialog with Resume/New/Load/Fresh options
           - Auto-load checkbox: "Automatically load last project on startup" (Phase 58.11)
           - Persists setting to [recent].restore_on_launch via ini_manager
       - input_dialog.py - Unified Input Dialog (Phase 58.1, Phase 58.12):
         - UnifiedInputDialog: Dual-pane file/folder selection
         - Left pane: File browser with multi-select
         - Right pane: Folder browser with multi-select
         - Path list display for selected items
         - **Phase 58.12:** Last directory persistence via ini_manager
         - **Phase 58.12:** Project Name field in Options panel (show_project_name parameter)
         - Returns 4-tuple: (paths, format, encoding, project_name)
       - loading_progress.py - Progress dialog for long-running operations
   
   6.7 gui/helpers/ (8 files - 7 adapter modules)
       - __init__.py - Helper exports
       - mode_adapter.py - Bridge between GUI config and modi/ modules (TASK 16.5)
       - analysis_adapter.py - Bridge between GUI and functions/analysis.py (TASK 16.6)
       - glossary_adapter.py - Bridge between GUI and glossary/config/style modules (TASK 16.7)
       - chunker_adapter.py - Bridge between GUI and functions/chunker.py
       - prompt_adapter.py - Bridge between GUI and functions/prompt_builder.py
       - manifest_binding.py - Widget-to-Manifest binding system (TASK 22.3)
       - tooltip.py - Tooltip display utilities for widgets
   
   6.8 gui/state/ (2 files)
       - __init__.py - State exports
       - store.py - SessionState, StepState (legacy, autosave disabled)
   
   6.9 functions/manifest_manager.py - ManifestManager (v3.1)
       - Primary state management for GUI projects
       - Singleton pattern for global access
       - Dataclasses: ProjectInfo, StepStateData, ManifestState
       - Loads/saves extended manifest v3.0 format
       - TASK 21.2: Creates manifests with ALL v3.0 fields from INI defaults
       - _ensure_all_fields_present() upgrades v2.x manifests on load
       - TASK 21.3: Settings helper methods for processing functions
       - TASK 32.1: Absolute path storage:
         - create_new() stores source_files with resolve() for absolute paths
         - set_source_files() stores with resolve() for absolute paths

   6.10 functions/ini_manager.py - INI Configuration (v3.0)
       - Central INI path resolution relative to main module
       - Typed access: get_str(), get_int(), get_float(), get_bool(), get_list()
       - Manifest defaults: get_all_manifest_defaults(), get_manifest_default()
       - TASK 21.4: Recent/Session management:
         - get_last_manifest() / set_last_manifest() - Last used manifest path
         - get_recent_manifests() / add_to_recent_manifests() - Recent list
         - get_restore_on_launch() / set_restore_on_launch() - Auto-restore toggle
       - **Phase 58.12:** Last input directory persistence:
         - get_last_input_dir() - Get last used input directory (returns Path or None)
         - set_last_input_dir() - Store last used input directory in [recent] section
       - TASK 31.2: User defaults management:
         - get_initial_default() - Load from config/defaults.ini
         - get_user_default() / set_user_default() / has_user_default() - User defaults in [user_defaults]
         - get_effective_default() - Resolves user > initial > fallback chain
         - save_as_user_defaults() - Save multiple values for a section
         - get_all_user_defaults() / get_all_initial_defaults() - Get all for section
         - clear_user_defaults() / restore_initial_defaults() - Reset to factory
         - reload_defaults_cache() - Clear defaults.ini cache
   
   6.11 gui/theme/ (3 files)
       - __init__.py - Theme exports
       - colors.py - THEME, ColorPalette, ThemeMode
       - icons.py - Icons, STEP_ICONS

       **ColorPalette Reference (gui/theme/colors.py):**
       *Primary:* `primary`, `primary_light`, `primary_dark`
       *Background:* `bg_main`, `bg_panel`, `bg_input`, `bg_hover`, `bg_selected`, `bg_disabled`
       *Text:* `text_primary`, `text_secondary`, `text_disabled`, `text_inverse`
       *Accent:* `accent_success`, `accent_info`, `accent_warning`, `accent_error`
       *Status:* `status_done`, `status_partial`, `status_pending`
       *Border:* `border_light`, `border_normal`, `border_focus`
       *Tab:* `tab_active`, `tab_inactive`, `tab_hover`
       *Button:* `btn_primary_bg`, `btn_primary_fg`, `btn_secondary_bg`, `btn_secondary_fg`, `btn_disabled_bg`, `btn_disabled_fg`

       **TTK Button Styles (gui/theme/colors.py):**
       - `TButton` - Default secondary button style (grey background)
       - `Primary.TButton` - Primary action button (blue background)
       - `Accent.TButton` - Accent/success action button (green background, black text)
         Used for positive actions like "Create Project" in dialogs.

   6.12 gui/helpers/manifest_binding.py - Widget-to-Manifest Binding (Phase 22-26)
       - Automatic save/load binding between tkinter widgets and manifest fields
       - **Binding Types:**
         - bind_entry_to_field() - Text entries with StringVar
         - bind_checkbox_to_field() - Boolean checkboxes with BooleanVar
         - bind_combobox_to_field() - Dropdown selection with StringVar
         - bind_spinbox_to_field() - Integer values with IntVar
         - bind_text_to_field() - Multiline Text widgets (FocusOut save)
         - bind_radio_group_to_field() - Radio button groups
         - bind_float_spinbox_to_field() - Float values with DoubleVar
       - **BindingInfo class:** Tracks save/load operations for testing
       - **load_all_bindings():** Batch load all registered bindings
       - **Phase 23 Integration:** InformationStep uses 11 bindings:
         - ProjectName, Title, Genre (text entries)
         - SourceLanguage, TargetLanguage (language comboboxes)
         - Summary (multiline text)
         - StylePreset, TonePreset (preset comboboxes)
         - CustomStyle, CustomTone (custom text entries)
         - Prompt (multiline text, renamed from Additional Notes)
       - **Phase 24 Integration:** PreprocessingStep uses 7 bindings + special format helpers:
         - Standard toggles: Deduplication, DeduplicationThreshold, EllipsisCompression,
           SymbolConversion, ProtCompression, SpeakerNameReplacement, CodeSpacingRules
         - Special formats: ProtectCodePatterns, CustomPlaceholders, AnchorRemoval
       - **Phase 25 Integration:** CostsStep (renamed from EstimationStep) and QAStep manifest bindings:
         - Analysis results: InputLines, InputTokens, OutputTokens (int fields)
         - ValidationRules nested: PlaceholderPreservation, AnchorPreservation,
           JapaneseCharacterDetection, SpeakerFormat, QuoteBalance, EmptyTranslation
       - **Phase 26 Integration:** QAStep and TranslationStep manifest bindings:
         - QAOptions nested: RerunPolicy (text), MaxJapaneseChars (int), MaxLineLength (int)
         - RequestOptions nested: Model (text), Temperature (float), LinesPerChunk (int),
           RetryStrategy (text), MaxRetries (int), EnableRequestCaching (bool),
           LineByLineMode (bool), ContextLines (int), Thinking (bool), ThinkingBudget (int)
       - **Phase 27 Integration:** PostprocessingStep manifest bindings:
         - PostProcessing nested (8 booleans): PlaceholderRecovery, BracketBalanceRecovery,
           QuoteBalanceRecovery, WhitespaceNormalization, RestoreCodeCharacters,
           RestoreLinebreaks, EnableSymbolConversion, FullwidthToHalfwidth
         - PostProcessing.FailureHandling (text enum: "skip", "flag", "retry")
       - **Phase 28 Integration:** WordwrapOverwriteStep manifest bindings:
         - WordwrapSettings nested: Mode (text), Width (int), BreakChar (text),
           MaxLines (int), PreventOrphans (bool), PreferPunctuationBreaks (bool),
           SpeakerHandling (text), Typography (text)
       - **Phase 28 Integration:** OutputInjectStep manifest bindings:
         - OutputFormat nested: PreserveFolderStructure (bool), Format (text),
           PairMode (text), Encoding (text), FileNaming (text: suffix/prefix/subfolder),
           TextOption (text), OverwriteExistingFiles (bool), Backup (text),
           BackupExtension (text), ExportManifestFile (bool), ExportProcessingLogs (bool),
           ExportGlossaryEntries (bool)
       - **Phase 29 Integration:** ManifestManager autosave system (TASK 29.1):
         - Background thread with configurable interval (default 15s, clamped 5-300s)
         - Only saves when `_dirty` flag is set
         - Settings from INI: enabled, interval_seconds, save_on_close
         - Auto-starts on create_new() and load(), stops on close()
         - Properties: autosave_enabled, autosave_interval, save_on_close
         - Methods: start_autosave(), stop_autosave()
       - **Phase 29 Integration:** Save triggers (TASK 29.2):
         - On close: App._on_close() calls ManifestManager.close()
         - After file load: InputExtractionStep._save_manifest_after_file_load()
         - Before translation: TranslationStep._save_manifest_before_translation()
         - All save methods check is_loaded, have try/except, log success/failure
       - **Phase 41 Integration:** Information Step UI enhancements:
         - Widget renames: Summary, System Instructions, Code Database
         - Genre dialog merges selected genres with existing (non_common preserved)
         - "Other" language triggers simpledialog; reverts on cancel via _prev_source_lang/_prev_target_lang
         - Style/Tone preset combos disabled when custom field has content (trace_add callback)
         - Glossary table: 4-column Treeview (Active ✓/✗, Original, Translation, Notes)
         - Inline editing via double-click with Entry overlay; Delete key removes entries
         - Import from Analysis: code patterns → category="Detected"; speakers → glossary entries with Notes
         - Code Database actions in prompt_builder: Preserve="Do not translate", Translate="Translate as", Remove=filtered out
         - Global Glossary/Database widget: mode switch, search filter, import/export JSON/CSV
         - Files: user/global_glossary.json, user/global_codes.json
         - Selective glossary: active field (bool) in manifest GlossaryEntries, defaults True
       - **Phase 42 Integration:** Preprocessing & Postprocessing complete implementation:
         - Anchoring Treeview: 5-column (Pattern, Action, Anchor Spec, RegEx, Description), _AnchorDialog, _sync_anchor_tree_to_manifest
         - Custom Placeholders RegEx: _RuleDialog.show_regex param, regex_result attr, checkbox in dialog
         - Protect Code Treeview: 3-column (Pattern, RegEx, Description), dict-based storage in config
         - Aggressive Dedup UI: _aggressive_dedup_var checkbox, set_aggressive_dedup() in dedup.py, wired via mainhelper.py
         - Code spacing manifest: visible/spacing fields in code_glossary, _apply_code_spacing(processor=) reads manifest overrides
         - Preview filtering: _preview_filter_var combobox (7 options), _filter_count_label, filter logic in _update_preview()
         - PostProcess validation: RecoveryType.PLACEHOLDER_POSITION_SHIFT/EXTRA, detect_position_shift(), detect_extra_tokens()
         - PostProcessManager.save_to_manifest(): stores recovery_analysis in manifest.mappings
         - Process order: functions/process_order.py, PRE_PRIORITIES (12 entries), POST_PRIORITIES (15 entries)
         - New file: functions/process_order.py (get_pre_order, get_post_order)
         - Modified: gui/steps/preprocess.py, gui/state/store.py, functions/dedup.py, functions/mainhelper.py
         - Modified: functions/manifest_fields.py, functions/postprocess.py, modi/standard_mode.py
       - **Phase 43 Integration:** Translation Tab Overhaul:
         - Merged Column: "To be Translated" replaces Original+Preprocessed (resolution: edited_prepro → preprocessed → original)
         - Newline Rendering: ↵ symbol in table cells, 200-char truncation
         - Mock Translation: MODEL_OPTIONS[0] = "Mock Translation", routes to MockTranslator(delay_per_chunk=0.1)
         - API Provider Management: APIProviderEntry dataclass, PROVIDER_PRESETS (5), providers Treeview, _ProviderEditDialog, _PresetPickerDialog
         - Settings Migration: CachingSettings.cache_mode, RequestSettings.thinking_enabled/budget/rolling_context_lines
         - _sync_from_global_options() applies Global Options overrides on tab enter
         - Retry Refinement: RETRY_STRATEGIES (2: Batch+Contextual for UI), ALL_RETRY_STRATEGIES (4 for CLI), min retries=0
         - Prompt Editor: Preview-only button, Ban Tokens LabelFrame with _BAN_PRESETS (None/Clean English/Strict)
         - Chunk Sync: costs.py reads/writes LinesPerChunk to manifest RequestOptions
         - Language Skip: detect_line_script() in analysis.py, _LANG_SCRIPT_MAP, _apply_language_skip()
         - Tab Caching: BaseStep._compute_cache_hash/_is_cache_valid/_update_cache/_invalidate_cache/_force_refresh
         - Performance: SharedTable batch insertion (500-row batches), _refresh_lines() batch manifest dict read
         - Bug Fix (Phase 17): Added _batch_insert_version counter to cancel stale batch insertions when _refresh_display() called multiple times
         - Modified: gui/steps/translate.py, gui/steps/base.py, gui/steps/costs.py, gui/components/table.py
         - Modified: gui/dialogs/global_options.py, functions/analysis.py
       - **Phase 44 Integration:** QA Step Placeholder & Shared Validation:
         - QA Step placeholder mode: _placeholder_mode bool, _placeholder_var toggle, _placeholder_toggle Checkbutton
         - Validation shared: Translation imports prompt_adapter for retry; Postprocessing imports recover_line + validate_character_word
         - Test file: dev/test_validation_shared.py (24 tests)
       - **Phase 45 Integration:** Postprocessing Tab Overhaul:
         - FailurePolicy enum: SKIP→WRITE (value="write"), FLAG (value="flag"), RETRY kept hidden
         - PostprocessOptions: convert_halfwidth_to_fullwidth bool field; placeholder/code/br hardcoded True
         - PostprocessLine: written/flagged bool fields for new filter system
         - HALFWIDTH_TO_FULLWIDTH: reverse dict comprehension from FULLWIDTH_TO_HALFWIDTH (30 entries)
         - Mutual exclusion: _on_fullwidth_change/_on_halfwidth_change trace callbacks
         - Diff View editing: _edit_text ScrolledText (height=4), _mark_fixed_btn, _mark_line_as_fixed()
         - Summary: _progress_bar (ttk.Progressbar), _written_label, _flagged_label; self.after(0, _update_summary) every 10 lines
         - Overwrite warning: messagebox.askokcancel in _apply_postprocessing()
         - Filters: All/Changed/Written/Flagged radio buttons; status icons ⚠/✓
         - Modified: gui/steps/postprocess.py (~1732 lines)
         - Test file: dev/test_postprocess_phase45.py (49 tests)

       - **Phase 46 Integration:**
         - WrapMode enum reduced to MANUAL only (removed RPGMAKER, DISABLED)
         - SpeakerMode enum reduced to IGNORE and COUNT (removed SAMELINE, SAMELINEINDENT, NEWLINE)
         - Removed enums: IgnorePattern, OverwriteStrategy, MergeMethod, TypographyStyle
         - Removed dataclasses: OverwriteOptions, TypographyOptions
         - WrapLine dataclass: added overwrite field and overwrite_differs property
         - WrapOptions dataclass: removed ignore_patterns field; hardcoded prevent_orphan/prefer_punct_breaks
         - Mode: ttk.Combobox replacing radio buttons
         - Speaker: ttk.Combobox with dynamic _speaker_desc_label
         - Ignore patterns: read-only ttk.Treeview from manifest CodeDatabase
         - Width: _width_mode_combo (Character/Pixel) with _char_width_frame and _pixel_width_frame
         - _on_width_mode_changed() toggles between character (20-200) and pixel (100-2000px + font 8-72) frames
         - Overwrite column in table with "↔ Differs" status
         - Filter radios: All/Changed/Exceeding/Overwrite Differs
         - _simple_wrap() sets exceeds_limit from max_lines
         - Modified: gui/steps/wordwrap_overwrite.py (~1200 lines)
         - Test file: dev/test_wordwrap_phase46.py (45 tests)

       - **Phase 47 Integration:**
         - New module: functions/output.py (~148 lines)
         - get_final_output(line_entry) -> (text, source_field): 9-level priority chain
         - Priority: overwrite → wordwr → postpro → edit{N} (highest) → tlc{N} (highest) → tl → preedit → prepro → orig
         - _find_highest_numbered_field(entry, prefix) scans for highest round number
         - resolve_all_lines(lines): batch resolution returning list of (text, source) tuples
         - get_source_breakdown(lines): Counter of source fields across all lines
         - PRIORITY_CHAIN constant: ordered list of field names
         - ManifestManager: get_dirty_flags() / set_dirty_flag() for {process, wordwrap} booleans
         - NamingOptions.strategy default: SUFFIX → SUBFOLDER
         - ExportStats.failure_log: List[Dict[str, str]] with file/error/timestamp entries
         - output_inject._run_export(): dirty flag pre-check with messagebox.askokcancel
         - output_inject._build_summary_panel(): _process_flag_label / _wordwrap_flag_label with ⚠/✓
         - output_inject._update_dirty_flags(): reads flags and updates indicator labels
         - input_extract._on_import_translations(): file dialog + JSON load + orig matching + field copy
         - TranslationOptions.skip_already_translated: bool field for skipping translated lines
         - translate._build_request_options(): Skip Already Translated checkbox + manifest binding
         - translate._do_translation(): skip logic checking tl field, marks LineStatus.SKIPPED
         - Modified: functions/output.py (new), functions/manifest_manager.py, gui/steps/output_inject.py, gui/steps/input_extract.py, gui/steps/translate.py
         - Test file: dev/test_output_phase47.py (51 tests)

      6.16 Pipeline Logging System Integration (Phase 48)
         - Log Rotation & Archival:
           - _rotate_log(project_dir, project_name, step_name) → archives existing log with ctime timestamp, returns fresh path
           - get_step_log_path(project_dir, project_name, step_name) → canonical path helper
           - Archive naming: {project}.{step}.{YYYYMMDD_HHMMSS}.log with collision avoidance
         - Status Vocabulary Constants:
           - LogStatus class: PASS constant, recovered()/partial_retrial()/partial_failure()/failure() static methods
           - FailureType class: 11 constants (TRANSLATION_EXHAUSTED, API_ERROR, VALIDATION_FAILED, etc.)
           - format_log_status(status, detail) → formatted status string
           - derive_step_status(line_statuses) → worst-of aggregation: FAILURE > PARTIAL > RECOVERED > PASS
         - Step Log I/O Functions:
           - write_step_log_header(log_path, header_dict) → writes separator-delimited header block; creates parent dirs
           - write_step_log_footer(log_path, footer_dict) → appends summary footer block
           - append_step_log_entry(log_path, entry_text) → free-form text append
           - All wrapped in try/except — never block processing
         - translation.log: APIClient._step_log_path attribute; write_log_header/footer/call integrate step log writes
         - postprocess.log: _do_postprocessing() emits header at start, footer with duration/lines/issues/recovered at completion
         - wordwrap.log: _apply_wordwrap() run_wrap() emits header with mode/width, footer with duration/total/changed/exceeding
         - output.log: _run_export() run_export() emits header with total files/naming, footer with duration/written/failed
         - Manifest Metrics: ManifestManager.set_step_metrics()/get_step_metrics() for per-step metric storage with merge-update
         - Log Export: _export_logs() discovers step logs via glob, copies to logs/ subfolder in export destination
         - Modified: functions/mainhelper.py, functions/api_client.py, functions/manifest_manager.py, gui/steps/postprocess.py, gui/steps/wordwrap_overwrite.py, gui/steps/output_inject.py
         - Test file: dev/test_pipeline_logging.py (52 tests)

      6.17 Request Formation 4-Step Process (Phase 49)
         - Data Model:
           - LineInfo dataclass: index, text, is_invalid, context_marker fields
           - RequestFormationConfig dataclass: max_lines, min_lines, max_tokens, model
           - TranslationRequest dataclass: lines, line_indices, context_type, is_split, provides_context, receives_context
         - build_requests(line_infos, config) → shared builder for Estimation + Translation
         - Step 1: _step1_split_menu_choice() → groups consecutive menu/choice lines into dedicated requests (no rolling context)
         - Step 2: _step2_split_at_file_boundaries() → splits at file_end markers, drops marker lines
         - Step 3: _step3_split_and_balance() → splits oversized groups, balances sub-groups evenly, respects max_lines and max_tokens
         - Step 4: _step4_merge_short_requests() → merges below-min same-type requests up to max_lines; menu/choice never merged
         - _extract_valid_lines() → separates valid from invalid (placeholder/dedup/marker) lines
         - _count_tokens_for_lines() → uses analysis.count_tokens for token estimation
         - Results sorted by first line index to maintain document order
         - Modified: functions/prompt_builder.py
         - Test file: dev/test_request_formation.py (50 tests)

   6.18 Context Markers Full Implementation (Phase 50)
         - Data Model (Task 50.1):
           - LineEntry.context_marker: Optional[str] field (None, "file_end", "dialogue", "menu", "choice")
           - LineEntry.VALID_MARKERS: frozenset of accepted marker types
           - is_context_marker() → bool: True when line is metadata-only
           - get_marker_type() → Optional[str]: returns marker type
           - Sparse serialization: to_dict() includes context_marker only when set
           - from_dict() restores context_marker (defaults to None)
         - Detection in Analysis (Task 50.2):
           - _is_choice_item(line) → bool: regex for numbered/bulleted choice patterns
           - _is_menu_item(line) → bool: short non-speaker items (≤60 chars)
           - _is_dialogue_line(line) → bool: speaker:dialogue via detect_speaker()
           - detect_context_markers(lines, min_run=3) → List[Optional[str]]: contiguous run detection
           - get_active_context_type(markers, index) → str: backwards scan for nearest marker
           - Modified: functions/analysis.py
         - Integration with Request Builder (Task 50.3):
           - build_line_infos(entries, detected_markers) → List[LineInfo]: converts LineEntry to LineInfo
           - Context propagation: marker entries → is_invalid=True; subsequent lines inherit active type
           - file_end does not propagate as content type (resets to "unknown")
           - Placeholder and empty lines flagged as invalid
           - build_requests() passes file_end markers to Step 2 for boundary splitting
           - _file_section tracking prevents Step 4 from merging across file boundaries
           - Modified: functions/prompt_builder.py
         - Conditional Prompt Templates (Task 50.4):
           - CONTEXT_PROMPT_DIALOGUE: character voice and emotional nuance instructions
           - CONTEXT_PROMPT_MENU: concise, action-oriented UI translation instructions
           - CONTEXT_PROMPT_CHOICE: distinct option formatting instructions
           - CONTEXT_PROMPT_UNKNOWN: mixed-content adaptive translation instructions
           - _CONTEXT_PROMPT_MAP: Dict[str, str] mapping context types to templates
           - get_context_prompt(context_type) → str: template lookup
           - _construct_system_prompt(lines, context_type) → str: injects template at slot 2
           - Modified: functions/prompt_builder.py
         - Test file: dev/test_context_markers.py (70 tests)

   6.19 Speaker Duplicate Removal (Phase 51)
         - Detection (Task 51.1):
           - _SPEAKER_PREFIX_RE: regex for Name: and Name： patterns
           - detect_consecutive_speakers(lines) → List[int]: returns indices of duplicate-speaker lines
           - Case-sensitive comparison, first occurrence never flagged
           - Modified: functions/validation.py
         - Preprocessing Removal (Task 51.2):
           - SpeakerDedupOp dataclass: speaker, colon_char, to_dict(), from_dict()
           - remove_duplicate_speakers(lines, indices?) → (modified, ops)
           - Strips speaker prefix; stores metadata for restoration
           - Modified: functions/validation.py
         - Postprocessing Restoration (Task 51.3):
           - restore_duplicate_speakers(lines, ops, line_indices?) → List[str]
           - Filters ops by op=="speaker_dedup_remove"
           - Supports explicit line_indices or sequential application
           - Modified: functions/validation.py
         - Global Option & Testing (Task 51.4):
           - RequestSettings.remove_duplicate_speakers: bool = False
           - UI: Checkbutton in Speaker Deduplication LabelFrame
           - Saved via to_dict/from_dict serialization
           - Modified: gui/dialogs/global_options.py
           - Test file: dev/test_speaker_dedup.py (47 tests)

   6.20 Selective Glossary Per Chunk (Phase 52)
         - Glossary Filter Function (Task 52.1):
           - filter_glossary_for_chunk(entries, chunk_lines, mode) → List[GlossaryEntry]
           - Mode "all": returns all entries unfiltered (default)
           - Mode "original_only": matches Original column against batch text
           - Mode "original_or_translation": matches both Original and Translation columns
           - Entries with empty Translation included when Original matches
           - Constants: GLOSSARY_FILTER_ALL, GLOSSARY_FILTER_ORIGINAL, GLOSSARY_FILTER_BOTH
           - Modified: functions/glossary.py
         - Prompt Builder Integration (Task 52.2):
           - PromptBuilder.glossary_filter_mode attribute (default "all")
           - _construct_system_prompt() uses filter_glossary_for_chunk() instead of inline loop
           - Import: filter_glossary_for_chunk, GLOSSARY_FILTER_ALL/ORIGINAL/BOTH
           - Modified: functions/prompt_builder.py
         - Global Option & GUI (Task 52.3):
           - RequestSettings.glossary_filter_mode: str = "all"
           - UI: Combobox with ["all", "original_only", "original_or_translation"]
           - Saved via to_dict/from_dict serialization
           - Modified: gui/dialogs/global_options.py
           - Test file: dev/test_glossary_selective.py (28 tests)

7. CLI ARCHITECTURE
   7.1 Command Line Interface Structure (CLI.py)
   7.2 CLI-Functions Integration
   7.3 Shared Processing Pipeline

8. API CLIENT & VALIDATION
   8.1 Multi-Provider Support (OpenAI, Claude, Gemini, etc.)
   8.2 Streaming vs Non-Streaming
   8.3 Response Validation Pipeline
   8.4 Error Handling and Retries

9. BATCH PROCESSING ARCHITECTURE
   9.1 Processing States
   9.2 Request Lifecycle
   9.3 Error Recovery

10. DATA FORMATS
    10.1 Manifest v3.0 JSON Schema
    10.2 Template CSV Format
    10.3 Glossary JSON Format
    10.4 Configuration INI Format

11. API REFERENCE
    11.1 Public APIs by Module
    11.2 Internal APIs
    11.3 Extension Points

12. TESTING STRATEGY
    12.1 Test File Organization
    12.2 Running Tests
    12.3 Coverage Requirements

**Running Tests:**
Run from `utility` root: `python -m pytest CherryAI/dev/ -v --timeout=10`
See `doc/tests.md` for full instructions.

=============================================================================

OVERVIEW

CherryAI is a Python 3.10+ application built with Tkinter for pre/post-processing
text before and after AI translation. The architecture separates concerns into:

- GUI layer (Tkinter UI)
- Processing layer (Processor, modes)
- Helper layer (utilities, glossary, analysis)
- Data layer (manifests, configurations)

=============================================================================

IMPORT ARCHITECTURE & CIRCULAR DEPENDENCY RESOLUTION

Critical Issue Fixed (Session X):
The project initially had a circular import problem when attempting to import
MODE_REGISTRY directly from mainhelper.py at module load time.

Problem:
- gui.py → mainhelper.py → modi imports MODE_REGISTRY
- But MODE_REGISTRY is only populated after load_modes() is called
- load_modes() is called in gui.py during App.__init__ (after mainhelper imports)
- Result: ImportError "cannot import name MODE_REGISTRY"

Solution:
- Replaced direct import of MODE_REGISTRY with a lazy getter function
- _get_mode_registry() in mainhelper.py fetches MODE_REGISTRY on-demand
- MODE_REGISTRY is only accessed during actual processing (Pre/Post phases)
- By that time, load_modes() has already been called by the GUI

Key Design Principle:
- Imports at module level are safe (functions, classes)
- Direct imports of module-level mutable state (dicts) at load time are unsafe
- Always use lazy getters for state populated by initialization code

=============================================================================

STATIC TYPING & MYPY

Goal: Full type coverage with mypy validation across `functions`, `formats`, and `modi`.

Status: ✅ COMPLETED - All three packages pass mypy cleanly (54 source files, 0 issues).

How to run:
- Full project (recommended):
    `python -m mypy -p CherryAI.functions -p CherryAI.formats -p CherryAI.modi`
- Or by paths:
    `python -m mypy CherryAI/functions CherryAI/formats CherryAI/modi`
- Per-file (fast during refactors):
    `python -m mypy CherryAI/functions/mainhelper.py --hide-error-context --no-error-summary --pretty --explicit-package-bases --follow-imports=skip`

Conventions:
- Optional checks: Prefer `is not None` over truthiness on callables/modules.
- Avoid `Any` leakage: Annotate `getattr` results and narrow with `typing.cast()` when needed.
- Precise containers: Use `list[str]`, `dict[str, str]`, etc. Avoid `Dict[str, Any]` except at boundaries (JSON/config).
- Lazy imports: Use lazy getters or `if TYPE_CHECKING:` for imports that can cause circulars.
- `type: ignore`: Remove unused ignores. When necessary, include error code (e.g., `# type: ignore[import-untyped]`) and a short rationale.
- Tkinter typing: Prefer `ttk.Widget.state([...])` for enable/disable; annotate `Toplevel`, variables, and handlers explicitly.

Notable implementations:
- Centralized mypy config in `pyproject.toml` with `follow_imports = "skip"`, `explicit_package_bases = true`.
- `openpyxl` imports use `type: ignore[import-untyped]` (no stubs available).
- `tiktoken` is typed as `Any` when unavailable and allows `None` assignment.
- OpenAI SDK call sites use localized `Any` casts for overload compatibility.
- Pillow text measurement uses `ImageDraw.textlength` with `textbbox` fallback (no `attr-defined` issues).

See also: `doc/typing.md` for full documentation.

=============================================================================

PROJECT STRUCTURE

CherryAI/
├── CherryAI.py              Entry point (GUI launcher, CLI dispatcher)
├── requirements.txt         Dependencies (openpyxl>=3.0.0, mostly stdlib)
├── CherryAI.ini            Config file (paths, UI state, API settings, IO config)
│
├── config/
│   ├── config.txt          Default configuration
│   ├── prompt.txt          Glossary API prompt template
│   └── game_summary.txt    Game/story context template for translation
│
├── formats/                File format handlers (NEW)
│   ├── __init__.py         FormatHandler base, FormatRegistry, IOConfig
│   ├── simple.py           txt, csv, tsv, json, xlsx handlers
│   ├── rpgmaker.py         RPG Maker MV/MZ handlers (placeholder)
│   └── document.py         PDF, EPUB handlers (placeholder)
│
├── gui/                    GUI v2 (10-step workflow)
│   ├── __init__.py         Package exports (App)
│   ├── app.py              Main application window
│   ├── progress.py         ProgressTracker, StepRow, ProgressPanel
│   ├── components/         Shared UI components
│   │   ├── __init__.py
│   │   └── table.py        SharedTable, ColumnDef, TableRow
│   ├── dialogs/            Modal dialogs
│   │   ├── __init__.py     Dialog exports
│   │   └── global_options.py GlobalOptionsDialog, settings dataclasses (incl. PromptsSettings)
│   ├── state/              Session state management
│   │   ├── __init__.py
│   │   └── store.py        SessionState, StepState, presets, undo/redo
│   ├── steps/              Workflow step tabs
│   │   ├── __init__.py     Step exports
│   │   ├── base.py         BaseStep abstract class, PlaceholderStep
│   │   ├── input_extract.py InputExtractionStep (step 0)
│   │   ├── analysis.py     AnalysisStep (step 1)
│   │   ├── information.py  InformationStep (step 2)
│   │   ├── preprocess.py   PreprocessingStep (step 3)
│   │   ├── costs.py        CostsStep (step 2, renamed Phase 40)
│   │   ├── estimate.py     Backward-compat redirect
│   │   ├── translate.py    TranslationStep (step 5)
│   │   ├── postprocess.py  PostprocessingStep (step 6, moved from Step 7)
│   │   ├── wordwrap_overwrite.py WordwrapOverwriteStep (step 7, moved from Step 8)
│   │   ├── qa.py           QAStep (step 8, moved from Step 6)
│   │   └── output_inject.py OutputInjectStep (step 9)
│   └── theme/              UI theming
│       ├── __init__.py     Theme exports (colors, icons)
│       ├── colors.py       ColorPalette, THEME, HIGH_CONTRAST_THEME, ThemeMode
│       └── icons.py        Icons, STEP_ICONS, status/step/log icon helpers
│
├── functions/              Core functionality
│   ├── mainhelper.py       Processor, Operation, Manifest (central hub)
│   ├── gui_legacy.py       Legacy Tkinter UI application (DEPRECATED - use gui/app.py)
│   ├── CLI.py              CLI with config, io, glossary, help commands
│   ├── One_Click_Test.py   Comprehensive pipeline testing module
│   ├── common_errors.py    Centralized error codes and messages
│   ├── modehelper.py       Shared utilities for modes
│   ├── analysis.py         Deep file analysis with glossary detection
│   ├── consistency.py      Consistency system (Phase 55)
│   ├── glossary.py         Unified glossary system (CSV-based)
│   ├── languages.py        Language definitions (single source of truth) - TASK 16.1
│   ├── API2Glossary.py     Optional LLM-based name enrichment
│   ├── dedup.py            Deduplication logic
│   ├── config.py           Config persistence (Session 4)
│   ├── options.py          Options dialog + API_PROVIDERS (single source) - TASK 16.2
│   ├── dependencies.py     Dependency management (Session 4)
│   ├── api_client.py       API Client for LLM communication (Session 12)
│   ├── mock_translator.py  Mock translation engine with flaw injection (Phase 56)
│   ├── validation.py       Pre/Post API validation (Session 13)
│   ├── prompt_builder.py   Dynamic prompt construction with game summary
│   ├── project_config.py   Project-level configuration (game summary, API profiles)
│   ├── wordwrap.py         Text analysis and wordwrap
│   ├── postanalysis.py     Post-processing analysis
│   ├── glossaries/         Glossary detection modules
│   │   ├── __init__.py
│   │   ├── name_glossary_constants.py   Speaker patterns and romanization
│   │   ├── name_glossary_functions.py   Speaker detection and gender inference
│   │   ├── code_glossary_constants.py   Code pattern definitions
│   │   └── code_glossary_functions.py   Code detection and classification
│   └── [mode-specific modules]
│
├── modi/                   Processing modes (plugins)
│   ├── __init__.py         Mode loader
│   ├── modehelper.py       Mode utilities
│   ├── protect_code.py     Code protection mode
│   ├── custom_placeholder.py Custom token replacement
│   ├── remove_restore.py   Remove and restore at anchors
│   ├── standard_mode.py    Dedup, ellipses, symbol conversion
│   └── [other modes]
│
├── dev/                    Development/testing utilities
│   └── [test files, cleanup scripts]
│
├── Projects/               Saved project files (.CherryAI.json manifests)
├── logs/                   Analysis and processing logs
├── templates/              Reusable rule templates
├── user/                   User data (glossary, state)
└── doc/                    This documentation

=============================================================================

CORE CONCEPTS

OPERATION

A single row in the GUI representing one processing rule.

Class: functions/mainhelper.py::Operation
```
{
    "modus": "Custom Placeholder",  # Mode name
    "inputs": [
        "pattern_regex",            # Input 1: what to find
        "replacement_token",        # Input 2: what to replace with
        "",                         # Input 3: unused
        ""                          # Input 4: unused
    ],
    "is_regex": True,              # Whether pattern is regex
    "pre_enabled": True,           # Run during Pre-TL
    "post_enabled": True,          # Run during Post-TL
    "description": ""              # Optional notes
}
```

MANIFEST

A JSON file containing:
- All operations (rules) for a translation file
- Mappings of what was protected
- File metadata
- Glossary entries matched

Stored at: Projects/{input_file_stem}.CherryAI.json

Example (v1.0 Legacy):
```
{
    "operations": [
        { "modus": "Custom Placeholder", "inputs": [...] },
        { "modus": "Protect Code", "inputs": [...] }
    ],
    "mappings": {
        "custom_placeholder_tokens": { "line_0": ["__NAME__", "__EMAIL__"] },
        "protected_segments": { "line_5": [{"start": 0, "end": 10, "value": "<tag>"}] }
    },
    "metadata": {
        "input_file": "input.txt",
        "created": "2025-11-13T10:30:00Z",
        "language": "ja"
    }
}
```

=============================================================================

MANIFEST v3.2 FORMAT (Implemented)

Version 3.2 extends v3.1 with source_root optimization (TASK 38).
Removes redundant source_file from lines and source_hint from filedir.
All v2.0 per-line entry features and v3.0 GUI state management are preserved.

**Status:** IMPLEMENTED (4428 tests passing)
**Locations:** 
- `functions/mainhelper.py` - LineEntry, Manifest (core)
- `functions/manifest_manager.py` - ManifestManager, ProjectInfo, StepStateData, FileDirEntry (GUI)
**Tests:** `dev/test_manifest_v2.py`, `dev/test_manifest_state.py`, `dev/test_manifest_defaults.py`, `dev/test_manifest_filedir.py`, `dev/test_manifest_v32.py`

DESIGN DOCUMENT: See doc/MANIFEST_UPDATE_DESIGN.md for full specification.

VERSION 3.2 OPTIMIZATIONS (TASK 38)

v3.2 optimizes manifest size by:
1. Storing `source_root` - the common path prefix for all source files
2. Removing redundant `source_file` from each line entry
3. Removing `source_hint` from filedir entries (use `source_root + rel_path` instead)

**Size Reduction:** For a project with 50,000 lines and a 60-character path prefix,
this saves ~4MB (60 chars × 50,000 lines + JSON overhead).

```json
{
    "version": "3.2",
    "source_root": "D:/Translations/MyGame/Data",
    "filedir": [
        {"first_idx": 0, "last_idx": 99, "format": "txt", "rel_path": "chapter1.txt"},
        {"first_idx": 100, "last_idx": 249, "format": "csv", "rel_path": "data/items.csv", "encoding": "shift_jis"}
    ],
    "step_state": {
        "InputExtractionStep": {"completed": true, "skipped": false, "metadata": {}},
        "AnalysisStep": {"completed": true, "skipped": false, "metadata": {}},
        ...
    },
    "project_info": {
        "name": "My Game Translation",
        "source_language": "Japanese",
        "target_language": "English",
        "genre": "Visual Novel",
        "tone": "Dramatic",
        "style_notes": "Maintain character speech patterns"
    },
    "glossary": [
        {"original": "太郎", "translation": "Taro", "gender": "male", "context": "main character"}
    ],
    "characters": [...],
    "code_patterns": [...],
    "lines": [
        {"idx": 0, "orig": "こんにちは"},
        {"idx": 1, "orig": "さようなら"}
    ],
    "metadata": {...}
}
```

**Path Resolution:** To get the full path for a file:
```python
# v3.2: source_root + rel_path
full_path = Path(manifest["source_root"]) / entry["rel_path"]

# Example: "D:/Translations/MyGame/Data" + "chapter1.txt"
#       -> "D:/Translations/MyGame/Data/chapter1.txt"
```

**Project Directory Structure (TASK 35.2/35.3):**
```
Projects/
  {project_name}/
    {project_name}.CherryAI.json   # Manifest file
    Original/                       # Copied source files
      chapter1.txt
      data/items.csv
    Patch/                          # Output files
      chapter1.txt
      data/items.csv
```

**GUI Session Restore with Filedir (v3.2 Format):**
When loading a manifest, the Input step's `_populate_from_manifest()` method uses
the v3.2 filedir format to reconstruct the file tree:
1. Reads `filedir` array with `first_idx`, `last_idx`, `rel_path` per file
2. Combines `source_root` + `rel_path` to reconstruct full file paths
3. Extracts lines for each file using the index range from `lines[]` array
4. Builds folder hierarchy with folders appearing above files (collapsed by default)
```

MANIFESTMANAGER CLASS

```python
@dataclass
class ProjectInfo:
    name: str = ""
    source_language: str = ""
    target_language: str = ""
    genre: str = ""
    tone: str = ""
    style_notes: str = ""

@dataclass
class StepStateData:
    completed: bool = False
    skipped: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FileDirEntry:
    """File directory entry for input/output decoupling (TASK 35.1, TASK 38).
    
    Maps global line index ranges to source files, enabling the Output step
    to reconstruct per-file outputs without consulting original input paths.
    
    TASK 38: source_hint removed - use source_root + rel_path for full path.
    """
    first_idx: int        # First line index (inclusive, global 0-based)
    last_idx: int         # Last line index (inclusive, global 0-based)
    format: str           # File format (txt, csv, json, xlsx, rpgm, etc.)
    rel_path: str         # Path relative to source_root
    encoding: str = "utf-8"  # File encoding
    
    @property
    def line_count(self) -> int:
        """Get number of lines in this file."""
        return self.last_idx - self.first_idx + 1
    
    def contains_idx(self, idx: int) -> bool:
        """Check if this entry contains the given line index."""
        return self.first_idx <= idx <= self.last_idx

class ManifestManager:
    # Singleton instance
    _instance: ClassVar[Optional['ManifestManager']] = None
    
    @classmethod
    def get_instance(cls) -> 'ManifestManager':
        """Get or create singleton instance."""
    
    def create_new_project(self, project_name: str) -> None:
        """Create new project with fresh state."""
    
    def load_manifest(self, path: Path) -> bool:
        """Load manifest from file."""
    
    def save_manifest(self, path: Optional[Path] = None) -> bool:
        """Save manifest to file."""
    
    def get_step_state(self, step_name: str) -> StepStateData:
        """Get state for a specific step."""
    
    def set_step_completed(self, step_name: str, completed: bool) -> None:
        """Mark step as completed/not completed."""
    
    # === Settings Access Methods (Task 21.3) ===
    
    def get_request_options(self) -> Dict[str, Any]:
        """Get request settings for API client (Model, Temperature, etc.)."""
    
    def set_request_options(self, options: Dict[str, Any]) -> None:
        """Update request options in manifest."""
    
    def get_preprocessing_options(self) -> Dict[str, Any]:
        """Get preprocessing settings (Deduplication, EllipsisCompression, etc.)."""
    
    def set_preprocessing_options(self, options: Dict[str, Any]) -> None:
        """Update preprocessing options in manifest."""
    
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules (PlaceholderPreservation, QuoteBalance, etc.)."""
    
    def set_validation_rules(self, rules: Dict[str, Any]) -> None:
        """Update validation rules in manifest."""
    
    def get_qa_options(self) -> Dict[str, Any]:
        """Get QA options (RerunPolicy, MaxJapaneseChars, etc.)."""
    
    def set_qa_options(self, options: Dict[str, Any]) -> None:
        """Update QA options in manifest."""
    
    def get_postprocessing_options(self) -> Dict[str, Any]:
        """Get postprocessing options (PlaceholderRecovery, FailureHandling, etc.)."""
    
    def set_postprocessing_options(self, options: Dict[str, Any]) -> None:
        """Update postprocessing options in manifest."""
    
    def get_wordwrap_options(self) -> Dict[str, Any]:
        """Get wordwrap settings (Mode, Width, BreakChar, etc.)."""
    
    def set_wordwrap_options(self, options: Dict[str, Any]) -> None:
        """Update wordwrap options in manifest."""
    
    def get_output_options(self) -> Dict[str, Any]:
        """Get output format options (Format, Encoding, FileNaming, etc.)."""
    
    def set_output_options(self, options: Dict[str, Any]) -> None:
        """Update output options in manifest."""
    
    def get_estimation_data(self) -> Dict[str, Any]:
        """Get estimation data (InputLines, InputTokens, OutputTokens)."""
    
    def set_estimation_data(self, data: Dict[str, Any]) -> None:
        """Update estimation data in manifest."""
    
    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings grouped by category."""
    
    # === File Directory Operations (TASK 35.1) ===
    
    def get_filedir(self) -> List[FileDirEntry]:
        """Get file directory entries mapping line ranges to files."""
    
    def set_filedir(self, entries: List[FileDirEntry]) -> None:
        """Set file directory entries."""
    
    def add_filedir_entry(self, entry: FileDirEntry) -> None:
        """Add a file directory entry."""
    
    def clear_filedir(self) -> None:
        """Clear all file directory entries."""
    
    def get_filedir_entry_for_idx(self, idx: int) -> Optional[FileDirEntry]:
        """Get the FileDirEntry that contains the given line index."""
    
    def get_lines_for_filedir_entry(self, entry: FileDirEntry) -> List[Dict[str, Any]]:
        """Get all lines belonging to a FileDirEntry."""
    
    def build_filedir_from_files(self, file_infos: List[Dict[str, Any]]) -> List[FileDirEntry]:
        """Build filedir entries from a list of file information."""
    
    # === Project Directory Operations (TASK 35.2/35.3) ===
    
    def get_project_dir(self) -> Path:
        """Get the project directory path: Projects/{project_name}/"""
    
    def get_original_dir(self) -> Path:
        """Get the Original/ directory for copied source files."""
    
    def get_patch_dir(self) -> Path:
        """Get the Patch/ directory for output files."""
    
    def copy_originals_to_project(self, force: bool = False) -> Dict[str, str]:
        """Copy source files into the project's Original/ directory."""
    
    def get_original_file_path(self, entry: FileDirEntry) -> Path:
        """Get the path to the copied original file for a filedir entry."""
    
    def get_patch_file_path(self, entry: FileDirEntry) -> Path:
        """Get the output path in Patch/ directory for a filedir entry."""
    
    def has_original_copies(self) -> bool:
        """Check if original files have been copied to the project."""
```

LINEENTRY DATACLASS (v2.0 Core)

Each line in the manifest stores a progressive entry:

```python
@dataclass
class LineEntry:
    idx: int                          # Line index (0-based)
    orig: str                         # Original text (always present)
    
    # Preprocessing (optional)
    prepro: Optional[str] = None      # Pre-processed text
    prepro_ops: Optional[List[Dict]] = None  # Operation metadata (NOT text)
    edited_prepro: Optional[str] = None  # User-edited preprocessed (Task 33.1)
    
    # Translation chain (optional, sparse)
    tl: Optional[str] = None          # Translation result
    # tlc1, tlc2, ... tlcN: TLC passes (dynamic attributes)
    # edit1, edit2, ... editN: Edit passes (dynamic attributes)
    
    # Post-processing (optional)
    postpro: Optional[str] = None     # Post-processed (restored) text
    wordwr: Optional[str] = None      # Word-wrapped text
    overwrite: Optional[str] = None   # User manual override
    
    # Metadata (never used as text input)
    log: Optional[str] = None         # Errors/warnings for this line
    deleted: bool = False             # True if line was deleted in game update
    updated: Optional[str] = None     # New content from game update
    
    # Extended Line Tags (Planned - v2.1)
    tags: Optional[List[str]] = None  # List of tag names (e.g., ["placeholder_error", "needs_review"])
    severity: Optional[str] = None    # Highest severity level ("INFO", "WARNING", "ERROR", "CRITICAL")
```

LINETAG ENUMERATION (Planned)

Standard tags with their severity levels and display colors:

| Tag Name           | Category   | Severity | Color  | Auto-Triggered By                    |
|--------------------|------------|----------|--------|--------------------------------------|
| needs_review       | Processing | WARNING  | Yellow | Manual flag or low_confidence        |
| code_mismatch      | Processing | ERROR    | Orange | Code count differs pre/post          |
| placeholder_error  | Processing | ERROR    | Orange | Restoration fails                    |
| dedup_source       | Processing | INFO     | Green  | Line is dedup representative         |
| dedup_target       | Processing | INFO     | Green  | Line duplicates another              |
| has_speaker        | Content    | INFO     | Blue   | Speaker name detected                |
| has_code           | Content    | INFO     | Blue   | Protected code detected              |
| long_line          | Content    | WARNING  | Yellow | Exceeds max_line_length              |
| short_line         | Content    | WARNING  | Yellow | Below min_line_length                |
| empty_translation  | Content    | ERROR    | Orange | Translation is empty/whitespace      |
| low_confidence     | Quality    | WARNING  | Yellow | API reports low confidence           |
| glossary_mismatch  | Quality    | WARNING  | Yellow | Term differs from glossary           |
| style_issue        | Quality    | WARNING  | Yellow | Style check fails                    |
| grammar_flag       | Quality    | WARNING  | Yellow | Grammar issue detected               |
| manual_edit        | Workflow   | INFO     | Blue   | User modified content                |
| api_translated     | Workflow   | INFO     | Green  | Translated via API                   |
| needs_tlc          | Workflow   | WARNING  | Yellow | TLC pass recommended                 |
| approved           | Workflow   | INFO     | Green  | User marked approved                 |
| rejected           | Workflow   | ERROR    | Orange | User marked rejected                 |

DYNAMIC TLC/EDIT PASS METHODS


```python
class LineEntry:
    def set_tlc(self, pass_num: int, value: str) -> None:
        """Set TLC pass N result."""
        
    def set_edit(self, pass_num: int, value: str) -> None:
        """Set Edit pass N result."""
        
    def get_tlc(self, pass_num: int) -> Optional[str]:
        """Get TLC pass N result, or None if not set."""
        
    def get_edit(self, pass_num: int) -> Optional[str]:
        """Get Edit pass N result, or None if not set."""
        
    def get_highest_tlc_pass(self) -> int:
        """Get the highest TLC pass number that exists (0 if none)."""
        
    def get_highest_edit_pass(self) -> int:
        """Get the highest Edit pass number that exists (0 if none)."""
```

SPECIAL FIELDS (Excluded from Input Resolution)

These fields are NEVER returned by get_input_for_*() methods:
- `log`: Error messages, not content
- `prepro_ops`: Metadata array for restoration operations
- `deleted`: Boolean flag
- `updated`: Game update content (separate workflow)

FIELD RESOLUTION METHODS

CRITICAL: There is no universal "rightmost" rule. Each operation has specific input logic.

```python
class LineEntry:
    def get_input_for_translation(self) -> str:
        """Input for Translation API call.
        
        Returns: edited_prepro if exists, else prepro if exists, else orig
        
        Resolution order (Task 33.1):
        1. edited_prepro (user-edited before translation)
        2. prepro (automated preprocessing result)
        3. orig (original text)
        """
        if self.edited_prepro is not None:
            return self.edited_prepro
        return self.prepro if self.prepro is not None else self.orig
    
    def get_input_for_tlc(self, pass_num: int) -> str:
        """Input for TLC Pass N.
        
        Resolution (backwards search):
        - Pass 1: Use "tl"
        - Pass N>1: Use edit{N-1} → tlc{N-1} → ... → tl
        
        Returns: Best available input for TLC pass
        """
        if pass_num == 1:
            return self.tl or self.prepro or self.orig
        
        # Search backwards: edit{N-1}, tlc{N-1}, edit{N-2}, ...
        for i in range(pass_num - 1, 0, -1):
            edit_val = getattr(self, f"edit{i}", None)
            if edit_val is not None:
                return edit_val
            tlc_val = getattr(self, f"tlc{i}", None)
            if tlc_val is not None:
                return tlc_val
        
        return self.tl or self.prepro or self.orig
    
    def get_input_for_edit(self, pass_num: int) -> str:
        """Input for Edit Pass N.
        
        Resolution (backwards search):
        - Use tlc{N} if exists
        - Else edit{N-1}, tlc{N-1}, ... → tl
        
        Returns: Best available input for Edit pass
        """
        # First try tlc{N} for this edit pass
        tlc_val = getattr(self, f"tlc{pass_num}", None)
        if tlc_val is not None:
            return tlc_val
        
        # Search backwards
        for i in range(pass_num - 1, 0, -1):
            edit_val = getattr(self, f"edit{i}", None)
            if edit_val is not None:
                return edit_val
            tlc_val = getattr(self, f"tlc{i}", None)
            if tlc_val is not None:
                return tlc_val
        
        return self.tl or self.prepro or self.orig
    
    def get_input_for_postprocessing(self) -> str:
        """Input for Post-processing (restoration).
        
        Resolution: Find latest in TLC/Edit chain, fallback to tl/prepro/orig.
        NOTE: Uses prepro_ops separately for restoration mappings.
        
        Returns: Latest translation result to restore into
        """
        # Find highest N with edit{N} or tlc{N}
        for n in range(100, 0, -1):  # Reasonable upper limit
            edit_val = getattr(self, f"edit{n}", None)
            if edit_val is not None:
                return edit_val
            tlc_val = getattr(self, f"tlc{n}", None)
            if tlc_val is not None:
                return tlc_val
        
        # Fallback chain
        if self.tl is not None:
            return self.tl
        if self.prepro is not None:
            return self.prepro
        return self.orig
    
    def get_input_for_wordwrap(self) -> str:
        """Input for Wordwrap operation.
        
        Returns: postpro if exists, else fallback via get_input_for_postprocessing()
        """
        return self.postpro if self.postpro is not None else self.get_input_for_postprocessing()
    
    def get_final_output(self) -> str:
        """Output for final export.
        
        This is the ONLY case where "rightmost available" logic applies.
        
        Returns: overwrite → wordwr → postpro (first available)
        Raises: ValueError if no output available
        """
        if self.overwrite is not None:
            return self.overwrite
        if self.wordwr is not None:
            return self.wordwr
        if self.postpro is not None:
            return self.postpro
        raise ValueError(f"Line {self.idx} has no final output (postpro/wordwr/overwrite)")
    
    def has_final_output(self) -> bool:
        """Check if any final output field is populated."""
        return self.overwrite is not None or self.wordwr is not None or self.postpro is not None
    
    def get_populated_fields(self) -> List[str]:
        """List of populated text fields (excludes metadata fields).
        
        Excludes: log, prepro_ops, deleted, updated
        Returns: List of field names that have values
        """
        text_fields = ['orig', 'prepro', 'tl', 'postpro', 'wordwr', 'overwrite']
        result = [f for f in text_fields if getattr(self, f, None) is not None]
        
        # Add dynamic TLC/Edit fields
        for n in range(1, 100):
            if getattr(self, f"tlc{n}", None) is not None:
                result.append(f"tlc{n}")
            if getattr(self, f"edit{n}", None) is not None:
                result.append(f"edit{n}")
        
        return result
```

MANIFEST CLASS HELPER METHODS

```python
class Manifest:
    # Core fields
    lines: List[LineEntry]          # Primary storage (v2.0)
    version: str = "2.0"            # Manifest format version
    origin_file: Optional[str]      # Relative path from root
    root_selected: Optional[str]    # User-selected game root
    
    def get_line(self, idx: int) -> Optional[LineEntry]:
        """Get LineEntry by index."""
    
    def ensure_line(self, idx: int, orig: str = "") -> LineEntry:
        """Get or create a LineEntry for the given index."""
    
    def set_field(self, idx: int, field_name: str, value: Any) -> None:
        """Set a field value on a LineEntry (sparse insert)."""
    
    def add_prepro_op(self, idx: int, op_data: Dict[str, Any]) -> None:
        """Add a preprocessing operation to a line's prepro_ops."""
    
    def get_prepro_ops(self, idx: int, mode: Optional[str] = None) -> List[Dict]:
        """Get preprocessing operations for a line, optionally filtered by mode."""
    
    def initialize_from_text(self, text: str) -> None:
        """Initialize lines array from input text."""
    
    def get_original_text(self) -> str:
        """Reconstruct original text from lines array."""
    
    def get_final_text(self) -> str:
        """Reconstruct final output text using get_final_output() for each line."""
```

MANIFEST v3.0 JSON STRUCTURE

```json
{
  "version": "3.0",
  "origin_file": "\\data\\scenario\\dialogue\\day1.txt",
  "root_selected": "C:\\Games\\MyGame",
  "created": "2025-11-27T10:00:00Z",
  "last_modified": "2025-11-27T14:30:00Z",
  "language_source": "ja",
  "language_target": "en",
  "operations": [...],
  "glossary_applied": "user/glossary.csv",
  "step_state": {
    "InputExtractionStep": {"completed": true, "skipped": false, "metadata": {}},
    "AnalysisStep": {"completed": true, "skipped": false, "metadata": {}},
    "InformationStep": {"completed": false, "skipped": false, "metadata": {}}
  },
  "project_info": {
    "name": "My Game Translation",
    "source_language": "Japanese",
    "target_language": "English"
  },
  "glossary": [],
  "lines": [
    {
      "idx": 0,
      "orig": "こんにちは",
      "prepro": "こんにちは",
      "prepro_ops": [{"mode": "protect_code", "mappings": {}}],
      "tl": "Hello",
      "tlc1": "Hello there",
      "postpro": "Hello there"
    },
    {
      "idx": 1,
      "orig": "[font_red]警告[/font_red]",
      "prepro": "__CODE_0__警告__CODE_1__",
      "prepro_ops": [{"mode": "protect_code", "mappings": {"__CODE_0__": "[font_red]", "__CODE_1__": "[/font_red]"}}],
      "tl": "__CODE_0__Warning__CODE_1__",
      "postpro": "[font_red]Warning[/font_red]"
    }
  ]
}
```

=============================================================================

MODI MODULE PREPRO_OPS INTEGRATION

All modi modules use prepro_ops exclusively for per-line operation data storage.

**Helper Pattern (in each modi module):**

```python
def _add_prepro_op(processor, idx: int, op_data: Dict[str, Any]) -> None:
    """Add a preprocessing operation to a line's prepro_ops."""
    processor.manifest.add_prepro_op(idx, op_data)


def _get_prepro_ops(processor, idx: int, mode: str) -> List[Dict[str, Any]]:
    """Get preprocessing operations for a line filtered by mode."""
    return processor.manifest.get_prepro_ops(idx, mode) or []
```

**Modi Module prepro_ops Formats:**

| Module | Mode Name | Format |
|--------|-----------|--------|
| protect_code.py | "Protect Code" | `{"mode": "Protect Code", "pattern": str, "items": [{value, context_before, context_after, orig_position}]}` |
| custom_placeholder.py | "Custom Placeholder" | `{"mode": "Custom Placeholder", "token": str, "values": [str, ...]}` |
| temporary_replacement.py | "Temporary Replacement" | `{"mode": "Temporary Replacement", "replacements": [{original, placeholder, pattern, replacement, is_regex}]}` |
| standard_mode.py | "Standard Helpers" | `{"mode": "Standard Helpers", "type": "ellipsis", "triplets": [(pos, count, chars), ...]}` or `{"mode": "Standard Helpers", "type": "empty_line"}` |
| anchor.py | "Remove and Restore at Anchor" | `{"mode": "Remove and Restore at Anchor", "removed": [{anchor_kind, anchor_char, text, ...}]}` |

**Temporary Replacement Behavior:**

Two modes of operation depending on whether a replacement value is provided:

1. **With Replacement Value** (e.g., `[player_name]` → `Steve`):
   - Pattern is replaced with the specified value
   - LLM sees the replacement value (e.g., "Steve") in the text
   - `placeholder` field in prepro_ops is `null`
   - Post-processing: replacement value → original pattern
   - Example: "Hello, Steve!" → "Hello, [player_name]!"

2. **Without Replacement Value** (empty replacement):
   - Pattern is replaced with indexed placeholder `__TEMPREPL_X_Y__`
   - `placeholder` field contains the placeholder string
   - Post-processing: placeholder → original pattern

**Read Pattern (apply_post):**

```python
# Read from prepro_ops (primary and only storage)
ops = _get_prepro_ops(processor, idx, MODE_NAME)
for op_data in ops:
    # ... restore logic using op_data
return changes
```

**Test Coverage:**

- Unit tests: `dev/test_manifest_v2.py` (51 tests)
- Modi module tests: `dev/test_modi_v2.py` (14 tests)
- Functions integration: `dev/test_functions_v2.py` (15 tests)
- Replication tests: `dev/test_replication.py` (40 tests)
- API translation sample: `dev/test_translation_sample.txt` (107 lines)
- Additional test files: validation, config, options, etc.
- Total: 1497 tests (see doc/tests.md for complete breakdown)

=============================================================================

FUNCTIONS MODULE V2.0 INTEGRATION (Phase 3 - Implemented)

Functions modules use manifest.lines as the primary data source.

**functions/postanalysis.py:**

Post-analysis validation and auto-recovery for translated text.

Key Functions:
- `compare_manifest_and_final(manifest, final_text)`: Compare original vs final
- `_try_code_recover(o, f)`: Insert missing code characters
- `_try_speaker_fix(o, f)`: Fix missing quotes after speaker colons
- `_try_br_recovery(o, f, orig_count, final_count)`: Insert missing <br> tags

Validation Checks:
1. **Speaker Structure**: Colon + quote pattern preservation
2. **Code Sequence**: CODE_CHARS (<{[]}>|=\\;#^*/) order preserved
3. **<br> Count**: HTML line break count matches original

```python
def compare_manifest_and_final(manifest, final_text):
    # Get original lines from manifest.lines array
    sorted_lines = sorted(manifest.lines, key=lambda x: x.idx)
    orig_lines = [line.orig for line in sorted_lines]
    
    # ... validation checks ...
    
    # <br> count validation (NEW)
    br_pattern = r"<br\s*/?\s*>"
    orig_br_count = len(re.findall(br_pattern, o, re.IGNORECASE))
    final_br_count = len(re.findall(br_pattern, f, re.IGNORECASE))
    if orig_br_count != final_br_count:
        # Attempt recovery...
```

**functions/One_Click_Test.py:**

```python
def _test_preprocessing(self):
    manifest = Manifest(summary="_test_sample.txt", operations=[], metadata={})
    
    # Initialize lines array from sample text
    manifest.initialize_from_text(SAMPLE_TEXT_JP)
    
    # ... processing ...
    
    # v2.0: Verify lines array was populated
    if not manifest.lines:
        raise ValueError("manifest.lines array not populated")
```

=============================================================================

REPLICATION MODULE V2.0 (Phase 4 - Implemented)

Game update detection and translation update generation.

**Location:** `functions/replication.py`

**Purpose:**
- Detect changes between game versions (NEW/MODIFIED/DELETED lines)
- Generate update manifests containing only lines needing translation
- Merge translated updates back into original manifests
- Support efficient game patch workflows

**Core Classes:**

```python
class ChangeType(Enum):
    """Type of change between manifest versions."""
    UNCHANGED = "unchanged"
    MODIFIED = "modified"  
    NEW = "new"
    DELETED = "deleted"

@dataclass
class LineChange:
    """Single line change with hash comparison."""
    idx: int
    change_type: ChangeType
    old_text: Optional[str]
    new_text: Optional[str]
    old_hash: Optional[str]    # SHA-256
    new_hash: Optional[str]    # SHA-256
    has_translation: bool      # Existing work to preserve

class ChangeDetector:
    """SHA-256 based change detection."""
    def hash_text(self, text: str) -> str
    def texts_match(self, text1, text2) -> bool
    def detect_line_change(self, old_line, new_text, idx) -> LineChange

class ManifestComparison:
    """Compare manifests for game updates."""
    def compare_with_text(self, manifest, new_text) -> ComparisonResult
    def compare_manifests(self, old_manifest, new_manifest) -> ComparisonResult

class UpdateOutputGenerator:
    """Generate translation update files."""
    def generate_update_manifest(self, original, comparison) -> Manifest
    def generate_update_text(self, comparison) -> str
    def merge_update_into_manifest(self, original, update) -> Manifest
```

**Convenience Functions:**

```python
def compare_manifest_with_source(manifest_path, source_path) -> ComparisonResult
def generate_update_files(manifest_path, source_path, output_dir) -> Tuple[Path, Path]
```

**Game Update Workflow:**

1. Load existing manifest (with translation work)
2. Compare against updated game source text
3. Generate update manifest with only NEW/MODIFIED lines
4. Translate update manifest
5. Merge translated updates back into original
6. Export final translation

=============================================================================

PROCESSOR

Central orchestrator that applies operations in sequence.

Class: functions/mainhelper.py::Processor

Key methods:
- process_pre(input_path, operations) → text with protections applied
- process_post(text, manifest) → text with protections restored
- trace_enabled: Boolean for debug tracing
- Processor.prepare_auto_translate(input_text) → Dict: Prepares API batches and estimates cost
- Processor.execute_auto_translate(batches) → Tuple[str, Dict]: Executes API calls and Post-processing
- Processor.run_full_auto_translate(input_text, callback) → Optional[str]: Orchestrates full pipeline

Pipeline (Pre-TL):
1. Custom Placeholder (mode)
2. Remove and Restore at Anchor (mode)
3. Protect Code (mode)
4. Standard Helpers (mode) - ellipses, empty lines
5. Other operations in UI order

Pipeline (Post-TL):
1. Protect Code restore (mode)
2. Remove and Restore restore (mode)
3. Custom Placeholder restore (mode)
4. Standard Helpers restore (mode)
5. Other operations in UI order
6. Deduplicate restore (if enabled)

=============================================================================

KEY MODULES

MAINHELPER.PY (Central Hub)

Purpose: Processing orchestration, data models, IO helpers, state persistence

Classes:
- Operation: Single processing rule
- Manifest: Complete rule set + mappings for a file
- Processor: Applies operations in sequence
- Manifest: JSON serialization of rules

Functions:
- _get_mode_registry() → Dict[str, ModuleType]: Lazy fetch of mode plugins (populated by load_modes())
- read_text(path) → str
- write_text(path, content) → bool
- read_table(path, delimiter) → List[List[str]]
- write_table(path, data, delimiter) → bool
- read_json_pairs(path) → List[Tuple[str, str]]
- write_json_pairs(path, data) → bool
- read_xlsx_pairs(path) → List[Tuple[str, str]]
- write_xlsx_pairs(path, data) → bool
- load_app_state() → Dict
- save_app_state(state) → bool
- Processor.prepare_auto_translate(input_text) → Dict: Prepares API batches and estimates cost
- Processor.execute_auto_translate(batches) → Tuple[str, Dict]: Executes API calls and Post-processing
- Processor.run_full_auto_translate(input_text, callback) → Optional[str]: Orchestrates full pipeline
- analyze_file(path, logs_dir) → analysis results

Dependencies:
- Stdlib: json, csv, configparser, datetime, logging, re, sys
- Third-party: openpyxl (optional, Excel support)
- Local: modi, modehelper, dedup (lazy-loaded in methods)

Notes:
- Central hub for all major operations
- Lazy-loads mode plugins to avoid circular imports via _get_mode_registry()
- Handles optional dependencies gracefully
- MODE_REGISTRY is populated by gui.py calling load_modes() during App initialization

GUI.PY (Tkinter Interface)

Purpose: Main application window with operation management, file handling, dialogs

Classes:
- App(tk.Tk): Main window
- OperationRow: UI row for each operation
- _Ctx: Lazy-loading helper for deferred imports

Key methods:
- load_file(): File dialog → load text
- load_manifest(): Load saved rules
- on_analyze(): Run analysis
- on_pre(): Apply pre-translation rules
- on_post(): Apply post-translation rules
- on_dry_run(): Test without modifying
- on_one_click(): Full pipeline orchestration
- on_translate(): Manual translation trigger

Dependencies:
- Stdlib: json, logging, re, configparser, tkinter, pathlib
- Third-party: tkinter (filedialog, messagebox, ttk, simpledialog)
- Local: mainhelper, modi, analysis, glossary (lazy-loaded via _Ctx)

Notes:
- Uses _Ctx helper class for lazy-loading complex imports
- Fallback import strategies (relative → absolute → sys.path)
- Heavy use of method-level imports to avoid circular dependencies

=============================================================================

GUI V2 MODULE INTEGRATION MATRIX (gui/)

Purpose: 10-step workflow interface replacing legacy gui_legacy.py.
Location: gui/app.py and gui/steps/*.py

Step Overview (Updated Phase 40 - Estimation renamed to Costs):

| Step | Tab Name | File | Primary Purpose |
|------|----------|------|-----------------|
| 0 | Input/Extract | input_extract.py | Load files/folders, extract text via format handlers |
| 1 | Analysis | analysis.py | Static analysis: line counts, duplicates, speakers |
| 2 | Costs | costs.py | Token/cost estimation, dual workflow, concurrent time |
| 3 | Information | information.py | Project info, glossary, game summary |
| 4 | Preprocess | preprocess.py | Preprocessing rules (dedup, placeholders, PROT) |
| 5 | Translation | translate.py | API translation with progress tracking |
| 6 | QA | qa.py | Quality checks, validation, comparison |
| 7 | Postprocess | postprocess.py | Reverse preprocessing operations |
| 8 | Wordwrap | wordwrap_overwrite.py | Word wrapping and final adjustments |
| 9 | Output/Inject | output_inject.py | Export to target format |

**Input/Extract Step Features:**
- **Load Files:** Select individual files via file dialog
- **Load Folder:** Recursively load all supported files from a directory
  - Files from subfolders display relative paths (e.g., "subdir/file.txt")
  - Supported formats: txt, csv, tsv, json, xlsx
- Format auto-detection and encoding options
- Manifest detection and auto-creation

Shared Module Integration Status:

| Step | functions/ Used | modi/ Used | formats/ Used | Status |
|------|-----------------|------------|---------------|--------|
| 0 | ❌ None | ❌ None | ✅ get_handler() | ⚠️ Partial |
| 1 | ❌ None | ❌ None | ❌ None | ❌ Missing |
| 2 | ❌ None | ❌ None | ❌ None | ❌ Missing |
| 3 | ❌ None | ❌ None | ❌ None | ❌ Missing |
| 4 | ❌ None | ❌ None | ❌ None | ❌ Missing |
| 5 | ✅ api_client | ❌ None | ❌ None | ⚠️ Partial |
| 6 | ✅ validation | ❌ None | ❌ None | ⚠️ Partial |
| 7 | ✅ postprocess | ❌ None | ❌ None | ⚠️ Partial |
| 8 | ✅ wordwrap | ❌ None | ❌ None | ✅ Good |
| 9 | ❌ None | ❌ None | ❌ None | ❌ Missing |

Expected Integrations (TODO):

| Step | Expected functions/ | Expected modi/ |
|------|---------------------|----------------|
| 1 | analysis.py, glossaries/* | - |
| 2 | chunker.py, chunk_optimizer.py, rate_limiter.py | - |
| 3 | project_config.py, glossary.py, style_presets.py | - |
| 4 | dedup.py | ALL (protect_code, custom_placeholder, etc.) |
| 5 | prompt_builder.py, conditional_prompts.py, logit_bias.py, retry_handler.py | - |
| 6 | postanalysis.py | sabotage.py |
| 7 | dedup.py (restore) | replace_after.py |
| 9 | - | - (formats/ only) |

Integration Notes:
- All step modules use lazy imports (inside methods) to avoid circular deps
- Import pattern: `from functions.module import Class` inside methods
- Session state (gui/state/store.py) bridges steps with shared data
- SharedTable (gui/components/table.py) provides consistent UI

COMMAND LINE INTERFACE (functions/CLI.py)

Purpose: Provides command-line access to CherryAI functionality.

CLI Commands:
| Command | Description |
|---------|-------------|
| `translate` | Run 1-Click translation (interactive or direct mode) |
| `sample` | Quick sample translation (default 50 lines) |
| `estimate` | Estimate translation cost without translating |
| `test` | Run diagnostic pipeline tests |
| `config` | View/set API configuration (URL, key, model, etc.) |
| `io` | Configure input/output file formats |
| `glossary` | Manage translation glossary |
| `languages` | List all supported languages |
| `help` | Show help and usage information |

Configuration Commands:
The config command supports a hierarchical usage pattern:
- `config` → Show all configurable options with current values
- `config <option>` → Show details and known values for option
- `config <option> <number>` → Select from numbered list
- `config <option> <value>` → Set with direct value (validated)

Configuration Options:
| Option | INI Key | Validation |
|--------|---------|------------|
| api_url | api.base_url | Must start with http:// or https:// |
| api_key | api.api_key | Any string (masked in display) |
| model | api.model | Any string, shows known models per provider |
| temperature | api.temperature | Float 0.0-2.0 |
| chunk_size | api.chunk_size | Integer 10-200 |
| timeout | api.timeout | Integer 10-600 |
| source_lang | api.source_lang | Valid language code |
| target_lang | api.target_lang | Valid language code |
| preset | N/A | Apply preset (gemini_free, gpt4, etc.) |

Known API Providers:
```python
KNOWN_API_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "anthropic": "https://api.anthropic.com/v1",
    "local": "http://localhost:1234/v1",
    "ollama": "http://localhost:11434/v1",
    "lmstudio": "http://localhost:1234/v1",
}

KNOWN_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
    "gemini": ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"],
    "anthropic": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
    "local": ["local-model"],
}
```

Glossary Commands:
| Action | Description |
|--------|-------------|
| (none) | Show glossary summary |
| list [type] | List entries (optional: names, terms) |
| search query | Search for matching entries |
| add orig trans [notes] | Add new entry |
| path | Show glossary file location |
| export path | Export to CSV or text file |

IO Configuration Commands:
The io command configures file format handling for extract (input) and inject (output):
| Command | Description |
|---------|-------------|
| io | Show current IO settings |
| io formats | List all available formats |
| io extract &lt;format&gt; | Set input format (txt, csv, tsv, json, xlsx) |
| io inject &lt;format&gt; | Set output format |
| io standard &lt;ext&gt; &lt;inj&gt; | Set both formats at once |
| io preserve_original true | Include original lines in output |

IO Configuration Options:
| Option | INI Key | Values |
|--------|---------|--------|
| extract | io.extract_format | txt, csv, tsv, json, xlsx |
| inject | io.inject_format | txt, csv, tsv, json, xlsx |
| preserve_original | io.preserve_original | true/false |

Format Pair Support:
- txt: No pair support (single column)
- csv, tsv, xlsx: Column A = translated, Column B = original
- json: Array of {"original": ..., "translated": ...} objects

Language Selection:
- Supported Languages: Japanese, English, Chinese (Simplified/Traditional), Korean, German, French, Spanish
- Multiple aliases per language (e.g., ja, jp, jpn, japanese all → "ja")
- Language normalization via LANGUAGE_ALIASES dictionary
- Persistent storage in CherryAI.ini [api] section

CLI Modes:
1. **Direct Mode**: `python CherryAI.py translate file.txt -s ja -t en`
   - All arguments provided upfront
   - Suitable for scripting and automation
   - Language args: `-s/--source`, `-t/--target`

2. **Interactive Mode**: `python CherryAI.py translate --interactive`
   - Step-by-step wizard with explanations
   - File selection with drag-and-drop hint
   - Language table display
   - Cost estimation before proceeding
   - Progress indicators

3. **Sample Mode**: `python CherryAI.py sample file.txt -n 100`
   - Quick sample translation for testing quality
   - Configurable number of lines (default 50)
   - Delegates to translate with line limit

Partial Translation Mode (TASK 9):
- Translate only first N lines, leave rest unchanged
- CLI argument: `--lines N` or `-n N`
- Example: `python CherryAI.py translate -n 50 myfile.txt`
- Configuration in CherryAI.ini [partial_translation] section
- CLI argument overrides config setting
- Skipped lines marked with configurable marker (default: "[UNTRANSLATED]")

CLI API Overrides (TASK 3):
- Override API settings for individual commands
- `--model MODEL`: Override model name (e.g., gpt-4o, gemini-2.0-flash)
- `--temperature TEMP`: Override temperature (0.0-2.0)
- `--timeout SECS`: Override API timeout in seconds (10-600)
- `--chunk-size N`: Override lines per API request (10-200)
- `--preset NAME`: Apply an API preset before translation
- Validation ensures values are within acceptable ranges
- Preset applied first, then individual overrides
- Example: `python CherryAI.py translate file.txt --preset gemini_pro --temperature 0.2`

Key Functions:
- `run_interactive_cli()`: Full interactive workflow
- `run_translate_cli(path, source_lang, target_lang, translate_lines, api_overrides)`: Direct translation
- `run_sample_cli(path, lines, source_lang, target_lang, api_overrides)`: Sample translation
- `run_config_cli(option, value)`: Configuration management
- `run_io_cli(option, value, value2)`: IO format configuration
- `run_glossary_cli(action, args)`: Glossary management
- `run_help_cli(topic)`: Help display
- `run_estimate_cli(path)`: Cost estimation only
- `run_list_languages_cli()`: Display language table
- `normalize_language_code(code)`: Normalize alias → standard code
- `get_language_name(code)`: Get full language name
- `get_partial_translation_config()`: Load partial translation settings
- `_apply_partial_translation(lines, translated, limit, marker)`: Merge translated with skipped
- `_apply_api_overrides(overrides)`: Apply CLI API overrides to config
- `validate_api_overrides(model, temperature, timeout, chunk_size, preset)`: Validate override values
- `_validate_config_value(option, opt_info, value)`: Validate config values
- `_set_io_standard(extract_fmt, inject_fmt)`: Set both IO formats
- `_detect_provider_from_url(url)`: Auto-detect provider from URL

Language Data Structures:
```python
SUPPORTED_LANGUAGES = {
    "ja": {"name": "Japanese", "native": "日本語", "description": "..."},
    "en": {"name": "English", "native": "English", "description": "..."},
    "de": {"name": "German", "native": "Deutsch", "description": "..."},
    # ... more languages
}

LANGUAGE_ALIASES = {
    "ja": "ja", "jp": "ja", "jpn": "ja", "japanese": "ja",
    "de": "de", "deu": "de", "ger": "de", "german": "de", "deutsch": "de",
    # ... more aliases
}
```

Dependencies:
- Local: mainhelper, config, glossary
- No external dependencies

=============================================================================

FILE FORMAT SYSTEM (formats/)

Purpose: Pluggable file format handlers with separate extract/inject operations.

Location: CherryAI/formats/

Module Structure:
```
formats/
├── __init__.py      FormatHandler base, FormatRegistry, IOConfig, get_handler()
├── simple.py        TxtHandler, CsvHandler, TsvHandler, JsonHandler, XlsxHandler
├── rpgmaker.py      RpgMakerMVHandler, RpgMakerMZHandler, RpgMakerPluginHandler (placeholder)
└── document.py      PdfHandler, EpubHandler (placeholder)
```

Core Classes:

1. **IOConfig** (dataclass):
   - extract_format: str = "txt"
   - inject_format: str = "txt"
   - preserve_original: bool = False
   - encoding: str = "utf-8"

2. **FormatHandler** (ABC):
   - format_id: str - Unique identifier (e.g., "txt", "json")
   - extensions: Tuple[str, ...] - Supported file extensions
   - description: str - Human-readable description
   - supports_pairs: bool - Whether format supports original+translated pairs
   - extract(path, encoding) → List[str] - Read text lines from file
   - inject(path, lines, original_lines, encoding) → None - Write lines to file
   - supports_original() → bool - Check pair support
   - get_metadata(path) → Dict - Get format-specific metadata

3. **FormatRegistry**:
   - register(handler) - Register a format handler
   - get(format_id) → FormatHandler - Get by format ID
   - get_by_extension(ext) → FormatHandler - Get by file extension
   - get_for_path(path) → FormatHandler - Get for file path
   - list_formats() → List[Dict] - List all registered formats
   - list_extensions() → List[str] - List all supported extensions

Simple Format Handlers (formats/simple.py):

| Handler | Format ID | Extensions | Pairs | Description |
|---------|-----------|------------|-------|-------------|
| TxtHandler | txt | .txt | No | Plain text (one line per line) |
| CsvHandler | csv | .csv | Yes | Comma-separated (col A = text, col B = original) |
| TsvHandler | tsv | .tsv | Yes | Tab-separated (col A = text, col B = original) |
| JsonHandler | json | .json | Yes | JSON - array or dictionary formats |
| XlsxHandler | xlsx | .xlsx | Yes | Excel (col A = text, col B = original) |

JSON Handler Structures:
- **Extract**: Reads multiple JSON structures:
  - Array of strings: `["line1", "line2", ...]`
  - Array of pairs: `[["original", "translated"], ...]`
  - Array of objects: `[{"original": "...", "translated": "..."}, ...]`
  - Dictionary format: `{"original_text": "translation", ...}` (keys=source, values=translation)
- **Inject without originals**: Writes simple array of strings
- **Inject with originals**: Writes [{"original": ..., "translated": ...}, ...]
- **Inject with preserve_format=True**: Preserves original dict format if source was dict
- **inject_dict()**: Writes dictionary format directly

Additional JsonHandler Methods:
- `extract_with_translations(path)` → List[Tuple[str, str]]: Extract (original, translation) pairs from dict format
- `get_metadata(path)` → Dict: Returns structure type ("array_of_strings", "array_of_pairs", "array_of_objects", "dictionary"), line_count, and translated_count for dicts

Usage Example:
```python
from CherryAI.formats import get_handler, get_registry

# Get handler for a file type
handler = get_handler("txt")
lines = handler.extract(path)
handler.inject(output_path, translated_lines, original_lines)

# List all formats
registry = get_registry()
for fmt in registry.list_formats():
    print(f"{fmt['id']}: {fmt['description']}")
```

Planned Formats (placeholder implementations):

1. **RPG Maker MV/MZ** (formats/rpgmaker.py):
   - Parse Actors.json, Items.json, Map*.json, CommonEvents.json
   - Extract name, description, note, message1-4 fields
   - Handle event dialogue in map files
   - Preserve JSON structure on inject

2. **Documents** (formats/document.py):
   - PDF: Text extraction via PyMuPDF, generation via reportlab
   - EPUB: Chapter-based extraction via ebooklib, beautifulsoup4

Configuration Storage (CherryAI.ini):
```ini
[io]
extract_format = txt
inject_format = json
preserve_original = true
```

Dependencies:
- openpyxl (optional, for xlsx support)
- Planned: PyMuPDF, reportlab, ebooklib, beautifulsoup4

=============================================================================

API CLIENT (functions/api_client.py)

Purpose: Handles communication with LLM providers (OpenAI, Gemini via OpenAI compat).

Classes:
- APIConfig: Dataclass for API settings (key, model, timeout, etc.)
- APIClient: Main client class
- TranslationError: Custom exception for API failures

Key Features:
- Rate Limiting: Enforces requests-per-minute limit (configurable)
- Chunking: Automatically splits large batches into chunks (default 50 lines)
- Structured Output: Uses JSON mode to ensure output line count matches input
- Retry Logic: Exponential backoff with jitter (3^n seconds, max 120s, 5+ retries)
- Error Handling: Validates line counts and checks for refusal messages
- Model Presets: Quick-switch between model configurations (TASK 8)
- **API Logging**: Request-response pair logging with API key redaction (TASK 11)
- **Token Tracking**: Running total of prompt/completion tokens (TASK 12)
- **Content Warning**: Detects explicit content terms (TASK 12)

API Logging (TASK 11 + TASK 12 enhancements):
- `enable_api_log` parameter in __init__ to enable logging
- `api_log_path` parameter to specify log file location
- `write_log_header()` writes summary at log start:
  - File name and timestamp
  - Total lines and chunk count
  - Model and structured output mode (JSON)
  - Cost per 1M tokens (FREE noted for Gemini)
  - Skipped lines tracking (DEDUP, symbols, no source lang)
  - Missing sections (Glossary, Rolling Context, etc.)
  - Content warnings detected
- `write_log_footer()` writes final statistics:
  - Chunks processed (N/M format)
  - Total prompt/completion tokens
  - Estimated cost (or FREE for Gemini)
- `_log_api_call()` method writes each request-response pair to file
- Captures: model, temperature, messages, response content, usage stats
- API key is automatically redacted with "[REDACTED]" in logs
- Token tracking: Running total shown in each chunk header
- Human-readable formatting with numbered lines and section headers
- Log file format:
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

  [MISSING SECTIONS]
    - Glossary (no matches found)
    - Rolling Context

  ================================================================================
  CHUNK #1 - 2025-11-30 08:00:49 | Tokens: 2259 in / 459 out | Running Total: 2718
  ================================================================================
  
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

**IMPORTANT**: Log formatting is for human readability only. The actual API 
request contains raw JSON messages without the section headers, dividers, 
or numbered line prefixes shown in the log.

Content Warning System (NEW - TASK 12):
- Detects explicit content terms in input chunks:
  - "erotic", "explicit", "sexual", "violent", "18+", "adult content"
  - "pornographic", "nsfw", "hentai", "rape", "incest"
- Warning logged to console and api_log.txt
- Recommends Gemini or local models for explicit content
- Disable with `content_warning_enabled = false` in [api] section

Logging Helper Methods:
- `write_log_header(filename, total_lines, chunk_count, missing_sections)`: Writes summary
- `write_log_footer()`: Writes final statistics (chunks, tokens, cost)
- `check_content_warning(text)`: Checks for explicit terms, returns warning if found
- `_format_system_prompt_for_log(content)`: Formats system prompt with section
  headers, respects \n as actual newlines for readability
- `_format_lines_for_log(lines, prefix)`: Formats lines with numbered indices
  like `[  1]`, `[  2]` etc. for easy reference
- `_format_translations_for_log(content)`: Parses JSON and formats output lines

Statistics Tracking (NEW - TASK 12):
- `_total_prompt_tokens`: Running total of input tokens
- `_total_completion_tokens`: Running total of output tokens  
- `_skipped_lines`: Dict tracking skipped lines by reason (dedup, symbols, etc.)
- `_content_warnings`: List of content warnings encountered

Retry Logic (Improved - TASK 11):
- Minimum 5 retries for empty response handling
- Exponential backoff: 3^attempt seconds (3, 9, 27, 81, 243)
- Random jitter: up to 20% of base wait time
- Maximum wait capped at 120 seconds
- Handles transient API issues gracefully

Model Presets (NEW - TASK 8):
- `apply_preset(name)` - Apply a named preset configuration
- `get_available_presets()` - List available preset names
- Presets defined in [api_presets] section of CherryAI.ini
- Format: "base_url|model|temperature|timeout|rate_limit"
- Default presets: gemini_free, gemini_pro, gpt4, gpt4_turbo, local
- Keeps API key separate (presets only change model settings)

Preset Examples:
```ini
[api_presets]
gemini_free = https://generativelanguage.googleapis.com/v1beta/openai/|gemini-2.0-flash-lite|0.3|120|15
gpt4 = |gpt-4o-mini|0.3|60|60
local = http://localhost:1234/v1|local-model|0.7|300|999
```

Integration:
- Designed to be called selectively (standalone translation step) or as part of a chained pipeline (One-Click).
- Allows granular control over when API calls occur, enabling manual review of pre-processed text before submission.

Dependencies:
- Third-party: openai>=1.0.0
- Local: config (for loading settings)

=============================================================================

MOCK TRANSLATOR (functions/mock_translator.py) ✓ NEW - Phase 56

Purpose: Standalone mock translation engine with deliberate flaw injection
for testing the postprocessing recovery pipeline without API keys or network.

Classes:
- MockTranslator: Deterministic mock translator with optional flaw injection
- FlawConfig: Dataclass for controlling flaw types and intensity
- FlawReport: Tracks all injected flaws for test assertions
- FlawIntensity: Enum (MILD=10%, MODERATE=30%, SEVERE=60%)

Key Features:
1. STANDARD MOCK TRANSLATION:
   - Replaces Japanese text segments with NATO phonetic words (alpha, bravo, ...)
   - Reverses non-Japanese text words as fallback
   - Preserves all `__PROT__`, `__DEDUP__`, `__CUSTOM__` placeholders
   - Preserves speaker:dialogue format (speaker names kept intact)
   - Preserves anchor characters (`[]{}()<>「」『』【】`) via tokenization
   - Deterministic output via seed-based `random.Random`

2. DELIBERATE FLAW INJECTION (Phase 56):
   - Placeholder malformation: removes/adds chars in `__PROT__` tokens
   - Anchor manipulation: removes existing anchors, inserts random ones
   - Code intrusion: replaces content inside code patterns (`[font]`, etc.)
   - Character surgery: random character insertion/deletion

3. FLAW REPORTING:
   - FlawReport tracks every injected flaw with before/after state
   - Enables test assertions that know exactly what was broken
   - Reports: total_lines, flawed_lines, per-type counters, details list

Factory Function:
- `create_mock_translator(enable_flaws, intensity, seed, delay_per_chunk)`
  Convenience factory for creating configured MockTranslator instances.

Integration:
- Called from `api_client.py._mock_translate()` when `model == "mock"`
- No external dependencies — uses only stdlib (random, re, time, logging)

Dependencies:
- Standard library only (no third-party packages)
- Local: none (standalone module)

=============================================================================

PROJECT CONFIGURATION (functions/project_config.py) ✓ NEW

Purpose: Manages project-specific settings and multi-API profile support.

Classes:
- ProjectConfig: Dataclass for project-level settings (name, summary_file, genre, tone, etc.)
- APIProfile: Dataclass for API configuration profiles (provider, model, key, etc.)

Key Features:
1. GAME SUMMARY LOADING (load_game_summary):
   - Loads summary from configured file path
   - Strips comment lines (# prefix, but preserves ## headers)
   - Removes template placeholder lines
   - Auto-truncates at MAX_SUMMARY_CHARS (2000) with warning
   - Supports both relative and absolute paths

2. SUMMARY FORMATTING (format_summary_for_prompt):
   - Wraps summary in "# Game Context" header
   - Adds project name, genre, tone metadata
   - Appends style notes section
   - Ready for prompt injection

3. PROJECT CONFIG PERSISTENCE:
   - `load_project_config_from_ini()` - Load from CherryAI.ini [project]
   - `save_project_config_to_ini()` - Save to CherryAI.ini [project]
   - `ProjectConfig.to_dict()` / `from_dict()` - Manifest serialization

4. API PROFILE MANAGEMENT (api_profiles.ini):
   - `load_api_profiles()` - Load all profiles from INI
   - `save_api_profile(profile)` - Save/update a profile
   - `get_api_profile(name)` - Get profile with fallback to main config
   - `delete_api_profile(name)` - Remove a profile
   - Supports multiple profiles for different purposes (translation, glossary)

Configuration Hierarchy:
```
CherryAI.ini (Global)
  ↓ defaults
api_profiles.ini (API Configurations)
  ↓ selected by name
Manifest.project_config (Per-Project)
  ↓ runtime override
CLI/GUI options
```

Security:
- API keys stored ONLY in CherryAI.ini or api_profiles.ini
- Manifest stores profile NAME, never the key
- Safe to share manifests with team

Dependencies:
- Stdlib: configparser, dataclasses, pathlib, logging

=============================================================================

PROMPT BUILDER (functions/prompt_builder.py)

Purpose: Constructs dynamic system prompts with game context, glossary, translation style, and conditional instructions.

Classes:
- RequestBatch: Dataclass holding lines, indices, context, and prompt for a single API request.
- RollingContextConfig: Dataclass for rolling context settings (enabled, lines_before, scene_markers, use_translated).
- PromptBuilder: Main class for generating prompts with project context.
- ConditionalPromptManager: Pattern-triggered instruction injection.

Constructor:
```python
PromptBuilder(
    config_dir: Path = Path("config"),
    project_config: Optional[ProjectConfig] = None,
)
```
- If project_config is None, loads from CherryAI.ini
- Loads RollingContextConfig from [rolling_context] section
- Loads translation style from [translation] style_file setting

Key Features:
- Game Summary Injection: Loads and formats game context from summary file
- Translation Style Injection: Loads user preferences from translation_style.txt (TASK 6)
- Dynamic Batching: Splits text into batches based on size limits and context markers (e.g., scene changes).
- Selective Glossary Injection: Scans batch text and only includes glossary terms actually present in the lines, reducing token usage.
- Context Injection: Appends character lists and metadata to the prompt.
- Rolling Context: Prepares slots for preceding lines (original or translated) to maintain coherence (TASK 7).
- Scene Marker Detection: Resets rolling context at scene breaks.
- Token Estimation: Provides estimates for prompt + content size.
- Conditional Prompts: Pattern-detected instructions for token handling.
- Empty Section Skipping: Skips game summary if placeholder text detected (TASK 12)

Prompt Construction Order (TASK 12 - Updated):
1. Base system prompt template
2. Game summary with metadata (if not empty/placeholder)
3. Output examples (from config/output_examples.txt)
4. Glossary terms (only those present in batch)
5. Character list (TYPE_NAME entries with gender)
6. Translation style preferences (if configured)
7. Conditional instructions (pattern-triggered)

Previous order (before TASK 12):
1. Base prompt template (config/prompt.txt)
2. Additional Instructions (prompt.txt)
3. Game summary with metadata
4. Translation style preferences
5. Glossary terms
6. Character list
7. Conditional instructions

Modular Prompt Files (TASK 12 - NEW):
- config/base_instructions.txt: Generic translation rules (17 bullet points)
- config/output_examples.txt: JSON format examples (4 examples)
- Allows per-project customization by overriding these files

Methods:
- `set_project_config(config)` - Update project config and reload summary
- `_load_game_summary()` - Load and format summary from file
- `_load_translation_style()` - Load style preferences from file
- `_load_output_examples()` - Load examples from output_examples.txt (NEW)
- `_is_game_summary_empty()` - Check if summary has placeholder text (NEW)
- `_construct_system_prompt(lines)` - Build full prompt for batch
- `build_batches(lines, ...)` - Split into RequestBatch objects
- `update_batch_context(batch, translated)` - Update context with translated lines
- `estimate_tokens(batches)` - Estimate total token count

Helper Functions:
- `load_translation_style(file, max_chars, config_dir)` - Load and clean style file
- `format_rolling_context(lines, is_translated)` - Format context for injection

Conditional Prompt System (functions/conditional_prompts.py) ✓ Enhanced Session 14+:
- Pattern-triggered instructions appended to system prompt
- Detects tokens like __PROT__, __DEDUP__, __TEMPREPL_X_Y__ in batch text
- Injects handling instructions only when relevant patterns present
- Configuration via config/conditional_prompts.json for customization
- 15 built-in conditions with priority ordering
- **Dynamic instructions with pattern-specific examples (TASK 5)**
- **Separate handling for <br> vs \\n, __PROT__ vs __COLOR__ vs __FONT__**
- **Bracket differentiation: [] vs {} vs <>**

Classes:
- ConditionalPrompt: Dataclass with name, patterns, instruction, priority, category, pattern_examples
- ConditionalPromptManager: Evaluates batches, builds dynamic instructions

Key Methods:
- `ConditionalPrompt.matches(text)` - Returns (matched: bool, matched_patterns: Set[str])
- `ConditionalPrompt.get_dynamic_instruction(matched_patterns)` - Generate instruction with relevant examples only
- `ConditionalPromptManager.evaluate_batch(lines)` - Evaluate which conditions match
- `ConditionalPromptManager.build_conditional_instructions(lines)` - Build dynamic instruction block

Built-in Conditional Prompts (with dynamic examples):
| Pattern | Purpose | Priority | Example When Matched |
|---------|---------|----------|---------------------|
| `__PROT__`, `__PROT_\d+__` | Code protection tokens | 100 | __PROT__, __PROT_1__ |
| `__COLOR__`, `__COLOR_\d+__` | Color placeholders | 100 | __COLOR__, __COLOR_2__ |
| `__FONT__`, `__FONT_\d+__` | Font placeholders | 100 | __FONT__, __FONT_1__ |
| `__DEDUP__` | Deduplication markers | 95 | __DEDUP__ |
| `__TEMPREPL_\d+_\d+__` | Temporary replacements | 90 | __TEMPREPL_1_0__ |
| `<br\s*/?\s*>` | HTML line breaks | 85 | <br>, <BR/> |
| `\\n(?!\[)` | Newline escapes | 84 | \\n |
| `\[.*?\]`, `\{.*?\}`, `<[^>]+>` | Brackets (dynamic) | 80 | [name], {var}, <tag> |
| `「.*?」`, `『.*?』`, `【.*?】`, `《.*?》` | Japanese brackets | 75 | 「」→"", 【】→[] |
| `\\c\[\d+\]` | Color codes | 70 | \\c[4] |
| `\\v\[\d+\]`, `\\n\[\d+\]` | Variables | 70 | \\v[15], \\n[1] |
| `\\se\[.*?\]`, `\\pic\[.*?\]` | Media commands | 70 | \\se[sound] |
| `\\fb`, `\\fr`, `\\i\[\d+\]` | Text formatting | 65 | \\fb, \\i[2] |
| `\\rb\[.*?,.*?\]` | Ruby text | 60 | \\rb[漢字,かんじ] |
| `…+`, `\.\.\.+` | Ellipsis | 40 | …, ... |
| `^[^\s:：]+[:：]\s*` | Speaker tags | 30 | Name: |
| `^[^\s:：]+[:：]\s*[\"'「『]` | Speaker dialogue format | 32 | Name: "text" |

Dependencies:
- Local: glossary (for term data), analysis (for token counting)

API VALIDATION (functions/validation.py) ✓ Enhanced Session 14+

Purpose: Multi-layer validation of lines before and after API translation.

Classes:
- SkipReason: Enum for why a line is skipped (EMPTY, COMMENT, DEDUP_ONLY, etc.)
- ValidationResult: Dataclass for single-line validation outcome
- BatchValidationResult: Dataclass for batch processing results
- PlaceholderValidationResult: Dataclass for placeholder preservation (NEW - TASK 4)
- RetryReason: Enum for retry triggers (NEW - TASK 4)
- TranslationValidationResult: Comprehensive per-line result (NEW - TASK 4)
- BatchTranslationValidationResult: Batch result with retry list (NEW - TASK 4)

Key Features:
1. PRE-TRANSLATION VALIDATION (validate_line_pre, validate_batch_pre):
   - Skip empty lines, comments (#), section markers (=)
   - Skip __DEDUP__ and __PROT__ only lines
   - Skip lines without Japanese characters
   - Skip already translated lines
   - Auto-translate symbol-only lines (normalize fullwidth → halfwidth)

2. POST-TRANSLATION VALIDATION (validate_line_post, validate_batch_post):
   - Japanese character count check (max 4 chars in translation)
   - Anchor character preservation verification
   - Uses ANCHOR_EQUIVS from modehelper.py for equivalence

3. PLACEHOLDER PRESERVATION (NEW - TASK 4):
   - extract_placeholders(text): Find __PROT__, __PROT_1__, __NAME__, etc.
   - count_placeholder(text, placeholder): Count with case/whitespace tolerance
   - validate_placeholder_preserved(original, translated): Check preservation
   - Detects: missing, extra, mangled placeholders
   - Returns: PlaceholderValidationResult with should_retry flag

4. COMPREHENSIVE VALIDATION (NEW - TASK 4):
   - validate_translation_comprehensive(): All checks in one call
   - validate_batch_comprehensive(): Batch with per-line retry list
   - RetryReason enum: EMPTY_TRANSLATION, PLACEHOLDER_MISSING,
     SPEAKER_FORMAT_LOST, TOO_MANY_JAPANESE, LINE_COUNT_MISMATCH
   - Returns lines_to_retry for targeted retry (not full batch)
   - success_rate property for batch quality assessment

5. SYMBOL NORMALIZATION (normalize_symbols):
   - Ellipsis: … → ...
   - Japanese punctuation: 。→., 、→,, ！→!, ？→?
   - Brackets: 「」→"", （）→(), ［］→[]
   - Fullwidth space: 　→ space

6. BATCH REASSEMBLY (reassemble_translations):
   - Combines API translations with auto-translations
   - Preserves skipped lines in correct positions
   - Maintains original order across categories

Helper Functions:
- has_japanese(text): Detect any Japanese characters
- count_japanese(text): Count Japanese characters
- is_symbol_only(text): Check for symbol-only content
- extract_anchors(text): Find anchor characters using ANCHOR_EQUIVS
- count_anchor_occurrences(text, anchor): Count anchor with equivalents

Placeholder Patterns:
- PROT_PLACEHOLDER_PATTERN: r"__\s*PROT(?:_\d+)?\s*__" (case-insensitive)
- CUSTOM_PLACEHOLDER_PATTERN: r"__[A-Z][A-Z0-9_]*(?:_\d+)?__"

Dependencies:
- Local: modehelper (for ANCHOR_EQUIVS, get_equivs)

Tests: 108 unit tests (56 in test_validation.py + 52 in test_api_validation.py)

SPEAKER FORMAT PRESERVATION (functions/validation.py) ✓ Implemented TASK 10

Purpose: Validate and preserve "Speaker: Dialogue" format in translations.

Two-Tier Validation System:
1. TIER 1 - Automatic Retranslation:
   - should_retry_for_speaker_format() determines if format is broken
   - Triggers automatic retry with format preservation emphasis
   
2. TIER 2 - Flagging for Review:
   - If retries exhausted, line tagged with needs_review + speaker_format_error
   - Logged for manual review

Constants:
- QUOTE_CHARS_OPENING: {'"', "'", "「", "『", "\u201c", "\u2018", "（", "(", "＂"}
- QUOTE_CHARS_CLOSING: {'"', "'", "」", "』", "\u201d", "\u2019", "）", ")", "＂"}
- QUOTE_PAIRS: Dict mapping opening to closing quotes
- COLON_CHARS: {":", "："}
- SIMPLE_COMMANDS_PATTERN: re.compile(r"^\\[a-zA-Z]$")

Classes:
- SpeakerFormatInfo: Dataclass with detection results
  - has_speaker_format: bool
  - speaker_name: str
  - colon_char: str, colon_pos: int
  - opening_quote: str, opening_quote_pos: int
  - closing_quote: str, closing_quote_pos: int
  - dialogue_content: str
  - is_balanced: bool

Key Functions:
1. detect_speaker_dialogue_format(line: str) -> SpeakerFormatInfo:
   - Detects Speaker: "Dialogue" format with balanced quotes
   - Handles space and simple commands (\b) between colon and quote
   
2. validate_speaker_format_preserved(orig_info, trans_info, strict=False) -> Tuple[bool, str]:
   - Compares original and translated format detection
   - strict=True warns on quote type changes
   
3. should_retry_for_speaker_format(orig_info, trans_info) -> bool:
   - Returns True if format broken and should retry

Conditional Prompt (CONDITION_SPEAKER_DIALOGUE):
- Pattern: `.+[:：]\s*[""「『\'\(（].+[\"\"」』\'\)）]\s*$`
- Priority: 82
- Instruction: Preserve Speaker: "Dialogue" format exactly

Tests: 45 tests in dev/test_speaker_format.py

API VALIDATOR (functions/api_validator.py - Planned for Future)

Purpose: Additional response validation with recovery strategies.

AUTO-TAGGER (functions/auto_tagger.py - Planned)

Purpose: Automatic tag assignment based on processing events and content analysis.

Classes (Planned):
- TagSeverity: Enum (INFO, WARNING, ERROR, CRITICAL)
- LineTag: Dataclass with name, severity, color, timestamp
- AutoTagger: Main class for automatic tag assignment

Tag Assignment Events:
| Event | Tags Added | Severity |
|-------|------------|----------|
| After translation | api_translated | INFO |
| User modifies line | manual_edit | INFO |
| Restoration fails | placeholder_error | ERROR |
| Code count mismatch | code_mismatch | ERROR |
| Speaker detected | has_speaker | INFO |
| Code detected | has_code | INFO |
| Line too long | long_line | WARNING |
| Line too short | short_line | WARNING |
| Empty translation | empty_translation | ERROR |
| Glossary term differs | glossary_mismatch | WARNING |

Tag Management Methods:
```python
class AutoTagger:
    def add_tag(self, line: LineEntry, tag: str) -> None:
        """Add a tag to a line (no duplicates)."""
        
    def remove_tag(self, line: LineEntry, tag: str) -> None:
        """Remove a tag from a line."""
        
    def has_tag(self, line: LineEntry, tag: str) -> bool:
        """Check if line has specific tag."""
        
    def get_severity(self, line: LineEntry) -> TagSeverity:
        """Get highest severity from all tags on line."""
        
    def get_color(self, line: LineEntry) -> str:
        """Get display color based on highest severity."""
        
    def filter_by_tag(self, lines: List[LineEntry], tag: str) -> List[LineEntry]:
        """Return lines that have the specified tag."""
        
    def filter_by_severity(self, lines: List[LineEntry], min_severity: TagSeverity) -> List[LineEntry]:
        """Return lines with severity >= min_severity."""
```

Dependencies:
- Local: manifest (for LineEntry access)

TABLE VIEW CONTROLLER (functions/table_controller.py - Planned)

Purpose: Professional table-based manifest editing with standard spreadsheet features.

Classes (Planned):
- TableColumn: Column configuration (name, width, sortable, editable)
- TableSelection: Current selection state (rows, cells)
- UndoAction: Single reversible action
- TableViewController: Main controller for table operations

Table Features:
| Feature | Description |
|---------|-------------|
| Sort | Click column header to sort (asc/desc toggle) |
| Filter | Filter rows by column value or tag |
| Search | Find text in any visible column |
| Multi-select | Shift+Click range, Ctrl+Click toggle |
| Edit cell | Double-click to edit in place |
| Resize columns | Drag column borders |
| Reorder columns | Drag column headers |

Bulk Operations:
| Operation | Description |
|-----------|-------------|
| Tag selected | Add/remove tags from selected rows |
| Translate selected | Send only selected lines to API |
| Clear field | Reset selected rows' field to previous stage |
| Delete lines | Mark selected lines as deleted |
| Copy selection | Copy selected cells to clipboard |

Search and Replace:
```python
class TableViewController:
    def search(self, query: str, columns: List[str] = None) -> List[int]:
        """Find rows matching query, optionally in specific columns."""
        
    def replace(self, old: str, new: str, column: str, indices: List[int] = None) -> int:
        """Replace text in column, optionally only in specific rows. Returns count."""
        
    def replace_all(self, old: str, new: str, column: str) -> int:
        """Replace all occurrences in column across all rows."""
```

Undo/Redo Stack:
```python
class TableViewController:
    def undo(self) -> bool:
        """Undo last action. Returns True if successful."""
        
    def redo(self) -> bool:
        """Redo last undone action. Returns True if successful."""
        
    def can_undo(self) -> bool:
        """Check if undo is available."""
        
    def can_redo(self) -> bool:
        """Check if redo is available."""
        
    def get_undo_description(self) -> str:
        """Get description of action that would be undone."""
```

Dependencies:
- Local: manifest (for data), auto_tagger (for tag operations), gui (for view)

REQUEST CACHE (functions/request_cache.py - Planned)

Purpose: Cache API responses to avoid resending identical translation requests.

Classes (Planned):
- CacheEntry: Dataclass with source_lines, translated_lines, timestamp, model, settings
- CacheMatchMode: Enum (STRICT, MODEL_ONLY, ANY)
- RequestCache: Main cache management class

Cache Matching Modes:
| Mode | Matches On |
|------|------------|
| STRICT | model + prompt_settings + llm_settings + source_lines |
| MODEL_ONLY | model + source_lines (ignores temperature, etc.) |
| ANY | source_lines only (any model, any settings) |

Cache Structure (JSON):
```json
{
  "version": "1.0",
  "entries": {
    "model_name": {
      "settings_hash": {
        "source_hash": {
          "source_lines": ["line1", "line2"],
          "translated_lines": ["trans1", "trans2"],
          "timestamp": "2025-12-01T12:00:00Z",
          "model": "gemini-2.0-flash",
          "settings": {"temperature": 0.5}
        }
      }
    }
  }
}
```

Key Methods:
```python
class RequestCache:
    def lookup(self, source_lines: List[str], model: str, 
               settings: Dict, mode: CacheMatchMode) -> Optional[List[str]]:
        """Look up cached translation for source lines."""
        
    def store(self, source_lines: List[str], translated_lines: List[str],
              model: str, settings: Dict) -> None:
        """Store translation result in cache."""
        
    def clear(self) -> int:
        """Clear all cache entries. Returns count of entries removed."""
        
    def clear_expired(self, max_age_days: int = 30) -> int:
        """Remove entries older than max_age_days."""
        
    def get_stats(self) -> Dict[str, int]:
        """Return cache statistics (entries, hits, misses, size)."""
```

Configuration (CherryAI.ini):
```ini
[cache]
enabled = true
mode = strict
max_entries = 10000
max_age_days = 30
cache_file = cache/request_cache.json
```

Dependencies:
- Standard: hashlib (for hashing), json, datetime
- Local: config (for settings)

RATE LIMITER (functions/rate_limiter.py - Planned)

Purpose: Comprehensive rate limit tracking for API requests.

Classes (Planned):
- RateLimitConfig: Per-model limit configuration
- UsageTracker: Tracks requests sent per time period
- RateLimiter: Main rate limiting class

Rate Limit Configuration:
```python
@dataclass
class RateLimitConfig:
    model: str
    requests_per_minute: int  # RPM limit
    daily_limit: Optional[int]  # None = unlimited
    reset_time: str  # "UTC" or "LOCAL" or specific hour
    concurrent_max: int  # Max concurrent requests
```

Default Limits:
| Model Pattern | RPM | Daily | Concurrent |
|---------------|-----|-------|------------|
| gemini-*-lite | 15 | 1500 | 3 |
| gemini-* | 60 | None | 5 |
| gpt-4o* | 60 | None | 5 |
| gpt-4-turbo* | 60 | None | 5 |
| local-* | 999 | None | 10 |

Key Methods:
```python
class RateLimiter:
    def can_send(self, model: str) -> Tuple[bool, str]:
        """Check if request can be sent. Returns (allowed, reason)."""
        
    def record_request(self, model: str) -> None:
        """Record that a request was sent."""
        
    def wait_for_slot(self, model: str) -> float:
        """Block until a request slot is available. Returns wait time."""
        
    def get_remaining_today(self, model: str) -> Optional[int]:
        """Get remaining requests for today (None = unlimited)."""
        
    def estimate_completion(self, model: str, lines: int, chunk_size: int) -> Dict:
        """Estimate when translation will complete, considering limits."""
        
    def get_usage_stats(self, model: str) -> Dict:
        """Get usage statistics for model."""
```

Persistent Storage (user/rate_limits.json):
```json
{
  "usage": {
    "gemini-2.0-flash-lite": {
      "today": "2025-12-01",
      "requests_today": 145,
      "last_request": "2025-12-01T14:30:00Z",
      "requests_this_minute": 3
    }
  }
}
```

Dependencies:
- Standard: datetime, time, threading
- Local: config (for settings)

SPEAKER QUOTE STRIPPER (functions/quote_stripper.py - Planned)

Purpose: Strip/restore quotes from speaker dialogue to save tokens.

Classes (Planned):
- QuoteStripResult: Dataclass with stripped_text, had_quotes, quote_style
- QuoteStripper: Main quote stripping class

Configuration:
| Setting | Default | Description |
|---------|---------|-------------|
| strip_speaker_quotes | true | Enable quote stripping |
| quote_styles | ["double", "single"] | Quote types to strip |
| preserve_inner_quotes | true | Keep quotes inside dialogue |

Supported Quote Patterns:
| Pattern | Example | Detected As |
|---------|---------|-------------|
| Double straight | `Speaker: "text"` | Standard |
| Double curly | `Speaker: "text"` | Smart quotes |
| Single straight | `Speaker: 'text'` | Alternative |
| Japanese quotes | `Speaker: 「text」` | JP standard |
| Japanese double | `Speaker: 『text』` | JP emphasis |

Key Methods:
```python
@dataclass
class QuoteStripResult:
    stripped_text: str
    had_quotes: bool
    quote_style: Optional[str]  # "double", "single", "jp_bracket", etc.
    original_text: str

class QuoteStripper:
    def strip_speaker_quotes(self, line: str) -> QuoteStripResult:
        """Strip outer quotes from Speaker: "dialogue" format."""
        
    def restore_quotes(self, translated: str, strip_info: QuoteStripResult) -> str:
        """Restore quotes after translation."""
        
    def detect_quote_style(self, line: str) -> Optional[str]:
        """Detect which quote style is used."""
        
    def is_speaker_line(self, line: str) -> bool:
        """Check if line matches Speaker: "..." pattern."""
```

Token Savings Calculation:
```python
# Per line: 2 tokens saved (opening + closing quote)
# For 50,000 speaker lines:
#   Input savings:  50,000 * 2 = 100,000 tokens
#   Output savings: 50,000 * 2 = 100,000 tokens (quotes in output too)
#   Total: ~200,000 tokens saved
#   At $0.40/1M tokens: $0.08 saved
#   At $4.00/1M tokens: $0.80 saved
```

Dependencies:
- Standard: re
- Local: validation (for speaker detection)

TOKEN-BASED CHUNKER (functions/chunker.py)

Purpose: Chunk translation batches by token count or hybrid mode.

Dependencies:
- tiktoken: Token counting
- config.py: MODEL_ENCODINGS, DEFAULT_ENCODING, get_encoding_for_model()

Constants (imported from config.py):
- MODEL_ENCODINGS: Dict mapping model names to tiktoken encodings
- DEFAULT_ENCODING: Fallback encoding for unknown models

Classes:
- ChunkConfig: Configuration dataclass
- TokenCounter: Token counting with caching
- Chunker: Main chunking class

Configuration:
| Setting | Default | Description |
|---------|---------|-------------|
| chunk_mode | "lines" | "lines", "tokens", or "hybrid" |
| chunk_size_lines | 50 | Max lines per chunk (line/hybrid mode) |
| chunk_size_tokens | 4000 | Max tokens per chunk (token/hybrid mode) |
| system_prompt_reserve | 1000 | Reserved tokens for system prompt |
| output_multiplier | 1.5 | Expected output/input ratio |

Chunk Modes:
| Mode | Description | Best For |
|------|-------------|----------|
| lines | Fixed line count | Consistent line lengths |
| tokens | Fixed token budget | Variable line lengths |
| hybrid | Whichever limit first | Mixed content, safety |

Key Methods:
```python
@dataclass
class ChunkConfig:
    mode: str  # "lines", "tokens", "hybrid"
    max_lines: int
    max_tokens: int
    system_prompt_tokens: int
    output_multiplier: float

class TokenCounter:
    def __init__(self, model: str = "gpt-4"):
        self.encoding = tiktoken.encoding_for_model(model)
        self._cache: Dict[str, int] = {}
        
    def count_tokens(self, text: str) -> int:
        """Count tokens with caching."""
        if text not in self._cache:
            self._cache[text] = len(self.encoding.encode(text))
        return self._cache[text]
        
    def count_lines(self, lines: List[str]) -> int:
        """Count total tokens for multiple lines."""
        return sum(self.count_tokens(line) for line in lines)

class Chunker:
    def __init__(self, config: ChunkConfig, counter: TokenCounter):
        self.config = config
        self.counter = counter
        
    def chunk_lines(self, lines: List[str]) -> List[List[str]]:
        """Split lines into chunks based on configured mode."""
        
    def get_available_tokens(self) -> int:
        """Calculate available tokens for content."""
        # context_window - system_prompt - output_reserve
        
    def estimate_chunks(self, lines: List[str]) -> int:
        """Estimate number of chunks without chunking."""
```

Hybrid Mode Logic:
```python
def chunk_hybrid(lines: List[str]) -> List[List[str]]:
    """Chunk by whichever limit is reached first."""
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for line in lines:
        line_tokens = self.counter.count_tokens(line)
        
        # Check both limits
        would_exceed_lines = len(current_chunk) >= self.config.max_lines
        would_exceed_tokens = (current_tokens + line_tokens) > self.config.max_tokens
        
        if current_chunk and (would_exceed_lines or would_exceed_tokens):
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0
            
        current_chunk.append(line)
        current_tokens += line_tokens
        
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks
```

Dependencies:
- External: tiktoken
- Standard: typing
- Local: config (for settings)

CHUNK OPTIMIZER (functions/chunk_optimizer.py - Planned)

Purpose: Dynamically adjust chunk size based on error rates.

Classes (Planned):
- ErrorTracker: Tracks errors per batch
- ChunkOptimizer: Adjusts chunk size based on error patterns

Configuration:
| Setting | Default | Description |
|---------|---------|-------------|
| error_threshold | 0.20 | Error rate that triggers adjustment |
| min_requests_before_adjust | 7 | Minimum requests before adjusting |
| reduction_factor | 0.75 | Multiply chunk size by this on trigger |
| min_chunk_size | 10 | Floor for chunk size reduction |
| success_streak_to_reset | 10 | Consecutive successes to restore original |

Error Types Tracked:
| Error Type | Description |
|------------|-------------|
| EMPTY_RESPONSE | LLM returned empty or whitespace |
| BATCH_RETRY | Entire batch needed retry |
| TIMEOUT | Request timed out |
| RATE_LIMITED | 429 response received |
| LINE_MISMATCH | Response had wrong line count |

Key Methods:
```python
class ChunkOptimizer:
    def record_success(self) -> None:
        """Record a successful batch."""
        
    def record_error(self, error_type: str) -> None:
        """Record an error. May trigger chunk adjustment."""
        
    def get_chunk_size(self) -> int:
        """Get current recommended chunk size."""
        
    def reset(self) -> None:
        """Reset to original chunk size."""
        
    def get_stats(self) -> Dict:
        """Get error statistics and adjustment history."""
```

Per-Model Learning:
```python
# Optimal chunk sizes learned per model
{
    "gemini-2.0-flash": {"optimal_chunk": 50, "samples": 100},
    "gpt-4o-mini": {"optimal_chunk": 75, "samples": 50},
    "local-model": {"optimal_chunk": 25, "samples": 30}
}
```

Dependencies:
- Local: config (for settings), api_client (for feedback)

PROGRESS TRACKER (functions/progress_tracker.py - Planned)

Purpose: Track and display translation progress for CLI and GUI.

Classes (Planned):
- ProgressState: Current progress state
- ProgressTracker: Main progress tracking class
- ProgressDisplay: Abstract display interface
- CLIProgressDisplay: Terminal progress bar
- GUIProgressDisplay: Tkinter progress widget

Progress State:
```python
@dataclass
class ProgressState:
    total_lines: int
    translated_lines: int
    current_batch: int
    total_batches: int
    current_file: str
    total_files: int
    file_index: int
    start_time: datetime
    tokens_used: int
    estimated_cost: float
    errors: int
    rate_limited: bool
```

Display Methods:
```python
class ProgressDisplay(ABC):
    @abstractmethod
    def update(self, state: ProgressState) -> None:
        """Update the progress display."""
        
    @abstractmethod
    def complete(self, state: ProgressState) -> None:
        """Mark progress as complete."""
        
    @abstractmethod
    def error(self, message: str) -> None:
        """Display an error message."""
```

CLI Output Format:
```
[████████░░░░░░░░] 45% (225/500 lines)
File 3/10: dialogue.txt | Batch 5/20 (lines 201-250)
Tokens: 12,500 | Cost: $0.0012 | ETA: 2m 30s
```

Dependencies:
- Standard: datetime, time
- Optional: tqdm (for enhanced CLI progress)
- Local: config (for settings)

LINE RECOVERY (functions/line_recovery.py - Planned)

Purpose: Automatic fix of malformed translations without LLM retry.

Classes (Planned):
- RecoveryResult: Dataclass with recovered_text, recovery_type, changes_made
- LineRecovery: Main recovery class

Recovery Types:
| Type | Pattern | Fix |
|------|---------|-----|
| PLACEHOLDER_CASE | `__prot__`, `__Prot__` | Uppercase to `__PROT__` |
| PLACEHOLDER_WHITESPACE | `__ PROT __` | Remove spaces |
| PLACEHOLDER_MANGLED | `_PROT_`, `__PROT_` | Fix underscore count |
| QUOTE_UNBALANCED | `"Hello` | Add closing quote |
| BRACKET_UNMATCHED | `[name` | Add closing bracket |
| SPEAKER_FORMAT | `Speaker Hello` | Add colon after speaker |
| BR_TAG_MISSING | Count mismatch | Insert <br> at end |
| CODE_CHAR_MISSING | Missing CODE_CHAR | Insert in order |

Recovery Methods:
```python
class LineRecovery:
    def attempt_recovery(self, original: str, translated: str, 
                        issues: List[ValidationIssue]) -> Optional[RecoveryResult]:
        """Attempt to fix translated line without LLM."""
        
    def fix_placeholder_case(self, text: str) -> str:
        """Uppercase all placeholder patterns."""
        
    def fix_placeholder_whitespace(self, text: str) -> str:
        """Remove spaces inside placeholders."""
        
    def balance_quotes(self, original: str, translated: str) -> str:
        """Add missing opening/closing quotes."""
        
    def balance_brackets(self, original: str, translated: str) -> str:
        """Add missing bracket pairs."""
        
    def fix_speaker_format(self, original: str, translated: str) -> str:
        """Restore Speaker: format."""
```

Decision Logic:
```python
def should_recover_or_retry(issues: List[ValidationIssue]) -> str:
    """Returns 'recover', 'retry', or 'skip'."""
    recoverable = [PLACEHOLDER_CASE, PLACEHOLDER_WHITESPACE, 
                   QUOTE_UNBALANCED, BR_TAG_MISSING]
    
    if all(issue.type in recoverable for issue in issues):
        return "recover"
    elif any(issue.type == EMPTY_TRANSLATION for issue in issues):
        return "retry"
    else:
        return "retry"  # Complex issues need LLM
```

Dependencies:
- Standard: re
- Local: validation (for issue types)

RETRY HANDLER (functions/retry_handler.py - Planned)

Purpose: Multiple retry strategies for failed translations.

Classes (Planned):
- RetryStrategy: Enum (BATCH, CONTEXTUAL, ISOLATED, SKIP)
- RetryRequest: Dataclass with lines, strategy, context, attempt
- RetryHandler: Main retry orchestration class

Strategy Descriptions:
| Strategy | Description | When to Use |
|----------|-------------|-------------|
| BATCH | Failed lines in smaller batch | Default, efficient |
| CONTEXTUAL | Include translated neighbors | Context-dependent lines |
| ISOLATED | Single line, minimal prompt | Independent lines |
| SKIP | Mark failed, continue | Non-critical content |

Contextual Retry Implementation:
```python
def build_contextual_prompt(failed_line: int, 
                           translated_before: List[str],
                           translated_after: List[str]) -> str:
    """Build prompt with surrounding context."""
    context = "Previously translated (for context only, do not output):\n"
    for line in translated_before[-3:]:
        context += f"  {line}\n"
    context += "\nTranslate this line:\n"
    context += f"  {source_line}\n"
    context += "\nFollowing lines (for context only):\n"
    for line in translated_after[:3]:
        context += f"  {line}\n"
    return context
```

Isolated Retry Implementation:
```python
MINIMAL_PROMPT = """Translate to {language}.
Preserve all placeholders exactly: __PROT__, [brackets], {braces}.
Keep numbers and formatting unchanged.

Input: {source}
Output:"""
```

Configuration (CherryAI.ini):
```ini
[retry]
strategy = batch
max_retries_per_line = 3
contextual_lines_before = 3
contextual_lines_after = 2
fallback_strategy = skip
```

Dependencies:
- Local: api_client, validation, prompt_builder

STYLE PRESETS (functions/style_presets.py - Planned)

Purpose: Pre-built translation style guides for common scenarios.

Classes (Planned):
- StylePreset: Dataclass with name, description, rules, avoid
- StylePresetLoader: Load and combine presets

Preset File Format (YAML):
```yaml
name: fantasy_medieval
description: Medieval fantasy setting vocabulary
formality: formal
honorifics: localize
vocabulary:
  - Use "thou/thee" for informal singular address
  - Use "you" for formal address or plural
  - Replace "hello" with "hail" or "well met"
  - Use "-eth" suffix for third person singular
  - "Said" becomes "quoth" or "spake"
avoid:
  - Modern contractions (don't, can't, won't)
  - Contemporary slang
  - Technology references
examples:
  - source: "Hello, how are you?"
    target: "Hail, how fares thee?"
  - source: "He says he's going."
    target: "He saith he goeth."
```

Built-in Preset Categories:
| Category | Presets |
|----------|---------|
| Time Period | archaic_english, victorian, modern_casual, futuristic_scifi |
| Regional | british_english, american_english, australian_english |
| Japanese | formal_japanese, casual_japanese |
| Genre | fantasy_medieval, fantasy_eastern, noir_detective, romance_flowery, horror_gothic, comedy_witty |
| Character | noble_aristocrat, street_slang, child_innocent, elderly_wise, military_formal, pirate_nautical, robot_mechanical |
| Dialect | scottish_dialect, irish_dialect, southern_us, cockney, jamaican_patois |

Key Methods:
```python
class StylePresetLoader:
    def load_preset(self, name: str) -> StylePreset:
        """Load preset by name from built-in or user folder."""
        
    def combine_presets(self, names: List[str]) -> StylePreset:
        """Combine multiple presets (later ones override earlier)."""
        
    def list_available(self) -> List[str]:
        """List all available preset names."""
        
    def to_prompt_text(self, preset: StylePreset) -> str:
        """Convert preset to text for system prompt injection."""
```

Preset Locations:
- Built-in: config/style_presets/*.yaml
- User-defined: user/style_presets/*.yaml (overrides built-in)

Dependencies:
- Standard: yaml (or json fallback)
- Local: config

ANALYSIS.PY (Deep File Analysis)


Purpose: File statistics, language detection, glossary matching, cost estimation

Functions:
- analyze_file(input_path, logs_dir) → JSON log with statistics
- detect_language(text) → language code
- count_tokens(text) → estimated token count
- estimate_cost(tokens, language) → USD estimate

Statistics computed:
- total_lines, empty_lines, unique_lines, duplicate_lines
- avg_line_length, max_line_length
- code.lines_with_code, code.code_segment_count
- speakers.count_lines_with_speaker, speakers.unique_speakers
- tokens.content_input_tokens, tokens.estimated_output_tokens
- tokens.pricing_usd
- duplicate_savings.duplicate_tokens_total
- glossary.selected_unique_total

Dependencies:
- Stdlib: json, logging, math, re, csv, difflib
- Local: mainhelper, dedup (lazy), glossary (lazy)

LANGUAGES.PY (Language Definitions - Single Source of Truth)

Purpose: Canonical language registry used by both CLI and GUI for consistent language handling.
Created in TASK 16.1 to consolidate duplicate definitions from options.py and CLI.py.

Data Model:
```python
@dataclass(frozen=True)
class Language:
    code: str           # ISO 639-1/BCP 47: "ja", "en", "zh-CN"
    name: str           # English display: "Japanese", "English"
    native: str         # Native script: "日本語", "English"
    aliases: tuple[str, ...]  # Alt codes: ("jp", "jpn", "japanese")
    description: str    # Human-readable description
```

Registry:
- LANGUAGES: Dict[str, Language] with 14 languages
- Supported: ja, en, zh-CN, zh-TW, ko, es, fr, de, pt, ru, it, ar, th, vi

Accessor Functions:
- get_language_names() → List[str]: For GUI dropdowns (sorted)
- get_language_codes() → List[str]: All canonical codes
- get_language_by_code(code) → Language|None: Direct lookup
- get_language_by_name(name) → Language|None: By English name
- get_language_by_alias(alias) → Language|None: By any identifier
- normalize_language_code(code) → str|None: Any input → canonical code
- get_language_name_from_code(code) → str: Code → display name
- get_language_dict() → Dict: CLI-compatible format
- build_language_aliases() → Dict: All alias→code mappings
- is_valid_language(identifier) → bool: Validate any input

Usage:
- options.py: `SUPPORTED_LANGUAGES = get_language_names()`
- CLI.py: `SUPPORTED_LANGUAGES = get_language_dict()`
- CLI.py: `LANGUAGE_ALIASES = build_language_aliases()`

Tests: dev/test_languages.py (87 tests)

Dependencies:
- Stdlib: dataclasses, typing
- No external dependencies (leaf module)

API_PROVIDERS (Single Source of Truth) - TASK 16.2

Purpose: Centralized API provider configuration in functions/options.py

Data Structure:
```python
API_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "models": [...]},
    "gemini": {"name": "Google Gemini", "base_url": "...", "models": [...]},
    "anthropic": {"name": "Anthropic Claude", "base_url": "...", "models": [...]},
    "local": {"name": "Local/Custom", "base_url": "http://localhost:11434/v1", "models": [...]},
    "ollama": {"name": "Ollama", "base_url": "http://localhost:11434/v1", "models": [...]},
    "lmstudio": {"name": "LM Studio", "base_url": "http://localhost:1234/v1", "models": [...]},
}
```

Accessor Functions (options.py):
- get_api_urls() → Dict[str, str] - Provider key to base URL mapping
- get_provider_models(provider) → List[str] - Models for specific provider
- get_all_provider_models() → Dict[str, List[str]] - All providers to models
- get_provider_names() → List[str] - List of provider keys
- get_provider_display_name(provider) → str - Human-readable name

Consumers:
- gui/dialogs/global_options.py: `from functions.options import API_PROVIDERS`
- functions/CLI.py: Imports accessors, derives KNOWN_API_URLS and KNOWN_MODELS

Usage:
- global_options.py: Direct import for GUI dropdowns
- CLI.py: `KNOWN_API_URLS = get_api_urls()` for backward compatibility
- CLI.py: `KNOWN_MODELS = get_all_provider_models()` for backward compatibility

Tests: dev/test_api_providers.py (60 tests)

Dependencies:
- Stdlib: typing
- No external dependencies

GLOSSARY.PY (Unified Glossary System)

Purpose: Central glossary management with automatic population from file analysis

Data Model:
```
Original | Translation | Notes | Source | Type | Gender | Refers_to_themselves_as | Referred_to_as
イオリ  | Iori       |       | API    | Name | Female | 私              | ちゃん
```

Classes:
- GlossaryEntry: Dataclass with 8 fields (original, translation, notes, source, entry_type, gender, refers_to_themself_as, referred_to_as)
  - Note: CSV column "Type" maps to Python field `entry_type` (to avoid conflict with built-in `type()`)

Functions:
- read_unified_glossary() → Dict[str, GlossaryEntry]
- write_unified_glossary(entries) → Path
- update_unified_glossary(new_entries, update_mode) → Path
- update_glossaries_from_analysis(input_path, logs_dir, confidence_threshold, update_mode) → Dict results

Update Modes:
- ADD: Only add new entries, preserve existing (default)
- UPDATE: Add new + fill empty fields in existing
- OVERWRITE: Add new + overwrite all fields
- NEW: Archive existing glossary and create fresh one

Location: user/glossary.csv

Automatic Population:
- Analysis automatically detects speakers, code patterns, and terms
- Results are suggested for glossary inclusion
- Users can approve or modify suggestions

Dependencies:
- Stdlib: csv, json, logging, dataclasses, pathlib
- Local: glossaries package (lazy-loaded)

Notes:
- 8-column CSV format for flexibility and future expansion
- Archiving with timestamp when creating fresh glossary
- Source field tracks what created/updated each entry

GLOSSARIES/ PACKAGE (Detection & Classification)

Submodules for automatic detection and classification.

name_glossary_constants.py:
- HONORIFIC_SUFFIXES: Japanese honorifics (さん, ちゃん, くん, etc.)
- HONORIFIC_RE: Regex for extracting honorifics
- HONORIFIC_ROMANIZATION: Mapping to romaji (san, chan, kun, etc.)
- HONORIFIC_GENDER: Gender inference from honorifics (chan→female, kun→male)
- PRONOUN_ROMANIZATION: Japanese pronouns to romaji (私→watashi, 俺→ore, etc.)
- PRONOUN_GENDER: Gender from pronouns (watashi→female, ore→male, etc.)
- EXPLICIT_GENDER_PATTERNS: Regex for status cards ("名前：X、性別：女性")
- EXPLICIT_GENDER_VALUES: Maps Japanese gender words to values (女性→female)
- REFERRED_BY_OTHERS_WEIGHT: Weight multiplier for others' honorifics (3.0)
- STRONG_GENDER_HONORIFICS: Strong gender indicators (ちゃん→female, くん→male)
- HIRAGANA_RANGE, KATAKANA_RANGE, KANJI_RANGE: Unicode ranges for script detection
- MIN_SPEAKER_OCCURRENCES: Minimum times speaker must appear (default: 2)
- MAX_SPEAKER_LENGTH: Maximum valid speaker name length (50 chars)
- DEFAULT_GENDER_CONFIDENCE_THRESHOLD: Confidence % for auto-assignment (75%)

name_glossary_functions.py:
- detect_speaker(line) → Optional[str]: Extract "NAME:" pattern
- extract_names_from_honorifics(lines) → Dict[str, int]: Find speakers with honorifics
- detect_explicit_gender(name, text) → (gender, confidence, source): Find explicit declarations
- detect_honorific_gender_from_others(name, lines, speaker_counts) → (gender, confidence): Weighted others' honorifics
- infer_gender_from_context(pronouns, honorifics, threshold) → (gender, confidence, pronoun_found, honorific_found)
- infer_gender_comprehensive(name, pronouns, honorifics, full_text, lines, speaker_counts, threshold) → (gender, confidence, pronoun_found, honorific_found, source): Multi-signal inference
- romanize_pronoun(jp_pronoun) → str: Convert to romaji
- romanize_honorific(jp_honorific) → str: Convert to romaji
- update_speakers_in_glossary(speakers_count, speaker_pronoun_counts, speaker_suffix_counts, additional_data, confidence_threshold, update_mode, full_text, lines) → Path
  - Now accepts full_text and lines for comprehensive gender inference
  - Uses infer_gender_comprehensive() instead of infer_gender_from_context()
- _is_valid_speaker_entry(name, count) → bool: Validate speaker for glossary
- _normalize_speaker(name) → Optional[str]: Clean speaker name
- _is_valid_name_candidate(base_token) → bool: Check if valid Japanese name
- _get_script_type(text) → Optional[str]: Detect hiragana/katakana/kanji

Key Features:
- Multi-signal gender inference with priority ordering:
  1. Explicit markers (status cards) → 100% confidence
  2. Others' honorifics (weighted 3x) → high confidence
  3. Self-pronouns (ore→male, atashi→female) → normal weight
- Handles edge cases like transformed characters (male pronouns, female identity)
- Detects gender from pronouns (watashi→female, ore→male, etc.)
- Extracts honorific suffixes and infers gender from them (chan→female, kun→male)
- Confidence scoring based on agreement between multiple cues
- One-script-only validation (no mixed hiragana/kanji)
- Placeholder pattern support ([n1], \N[1], {name})

code_glossary_constants.py:
- CODE_PATTERNS: Regex list for detecting code (tags, escapes, brackets)
- COLOR_NAMES: Set of color names for classification
- RPGM_VAR_RE, RPGM_ACTOR_RE: RPG Maker variable patterns
- CODE_GLOSSARY_HEADER: CSV structure (Code, Type, RegEx, Notes)
- TYPE_LINEBREAK, TYPE_VARIABLENAME, TYPE_VARIABLENUMBER, etc.: Code type constants

code_glossary_functions.py:
- detect_code(line) → Dict[str, Any]: Find all code segments in line
- classify_code_type(code) → str: Classify code into types (LINEBREAK, VARIABLENAME, COLOR, FONT, etc.)
- generate_regex_pattern(code, code_type) → str: Create regex to match code
- update_code_in_glossary(code_counts, update_mode) → Path
- _extract_all_balanced_code(line) → List[Tuple[int, int, str]]: Extract balanced tags/brackets
- _normalize_code_segment(seg) → str: Normalize for similarity grouping
- _find_balanced_code(line, start_idx, open_char) → Optional[int]: Find closing bracket
- _find_parenthesis_code(line) → List[Tuple[int, int]]: Detect function-like patterns

Key Features:
- Balanced bracket detection (handles nested structures)
- Escape sequence extraction as standalone codes
- Classification priority: linebreak → RPG Maker → ruby → colors → fonts → variables
- Color and font pattern recognition
- Similarity grouping for code normalization

Dependencies (glossaries/):
- Stdlib only: re, csv, json, logging, dataclasses, pathlib
- No external dependencies

API2GLOSSARY.PY (Optional LLM Enhancement)

Purpose: Optional LLM-based name translation and gender inference as fallback

Configuration (editable):
- API_KEY: OpenAI or Gemini API key (reads from CherryAI.ini [api] section)
- API_URL: API endpoint (default: Gemini OpenAI format)
- MODEL_NAME: Model to use (default: gemini-2.0-flash-lite)
- EXCERPT_LINES: Context lines per excerpt (5)
- EXCERPT_SPEAKER_OCCURRENCES: Required speaker occurrences (3)
- INITIAL_CHECKS: Number of initial excerpts (2)
- MAX_VALIDATION_CHECKS: Max total validation checks (10)
- CONFIDENCE_THRESHOLD: Required confidence % (70%)
- DEFAULT_ENABLED: Off by default (user opt-in via config)

API Key Loading Priority:
1. Module constant (API_KEY) - rare, discouraged
2. Environment variable (API2GLOSSARY_API_KEY)
3. CherryAI.ini [api] section (api_key) - recommended
4. config/config.txt (API2GLOSSARY_API_KEY)

Main Functions:
- enrich_speakers_via_api(speaker_data, all_lines, enabled, write_to_glossary) → Dict[speaker, enrichment_data]
  - Takes: Dict mapping speaker names to line indices
  - Extracts: Dialogue excerpts with 5+ context lines
  - Sends: To LLM with structured output schema
  - Returns: {speaker → {"romaji": ..., "gender": ..., "note": ...}}
  - Multi-check: Validates conflicting results up to MAX_VALIDATION_CHECKS
- test_api_connection() → (success: bool, details: dict)
  - Tests API connectivity with sample "太郎" (expected: Male)
  - Returns detailed status and error information
  - Used to verify API configuration is working

Integration with Enhanced Gender Inference:
- Serves as fallback when local inference is inconclusive
- Priority order in infer_gender_comprehensive():
  1. Explicit gender markers (100% confidence, local)
  2. Honorifics from others (weighted 3x, local)
  3. Self-pronouns (local analysis)
  4. API2Glossary (LLM fallback, optional)

How It Works:

1. Excerpt Construction:
   - Finds lines where speaker appears
   - Extracts N consecutive lines including speaker
   - Skips duplicates (sampling different contexts)

2. LLM Inference:
   - Sends structured prompt with excerpt
   - Uses JSON schema for reliable parsing
   - Requests: romanization, gender, optional note
   - Uses free Gemini API by default

3. Multi-Check Validation:
   - If results conflict, sends additional excerpts
   - Validates until confidence threshold met or max checks reached
   - Helps resolve ambiguous cases

4. Result Integration:
   - Optional: Writes results to glossary
   - Allows manual review before committing
   - Returns results for user approval

Advantages:
- Free tier support (Gemini)
- No manual romanization lookup needed
- Context-based gender inference
- Configurable confidence threshold
- Optional (off by default)

Dependencies:
- Stdlib: json, typing, pathlib, collections
- External: requests (for API calls)
- Conditional: Requires API key + internet

Notes:
- Graceful fallback if API fails (doesn't block analysis)
- Structured output schema prevents parsing errors
- Configurable model allows cost/performance tradeoff
- Multi-check validation improves accuracy

=============================================================================

ANALYSIS.PY (Enhanced with Glossary Detection)

Purpose: File statistics, language detection, glossary matching, cost estimation

Entry Point:
- analyze_file(input_path, logs_dir) → JSON log with comprehensive statistics

Automatic Glossary Detection:

Speaker Detection:
- Scans file for "NAME:" dialogue patterns
- Extracts speaker names and frequency
- Calls name_glossary_functions.detect_speaker()
- Tracks pronouns and honorifics used by each speaker
- Infers gender from linguistic patterns (pronouns, suffixes)
- Results: speakers.unique_speakers, speakers.speaker_data

Code Detection:
- Scans file for code patterns (tags, escapes, brackets)
- Calls code_glossary_functions.detect_code()
- Classifies code types (HTML, colors, variables, etc.)
- Results: code.code_patterns, code.classifications

Term Detection:
- Identifies frequently recurring terms
- Suggests entries for glossary

Statistics Computed:
- total_lines, empty_lines, unique_lines, duplicate_lines
- avg_line_length, max_line_length
- code.lines_with_code, code.code_segment_count, code.code_patterns[]
- speakers.count_lines_with_speaker, speakers.unique_speakers, speakers.speaker_data{}
- tokens.content_input_tokens, tokens.estimated_output_tokens
- tokens.pricing_usd
- duplicate_savings.duplicate_tokens_total
- glossary.selected_unique_total, glossary.matched_entries[]

Optional LLM Enhancement:
- If enabled: Calls enrich_speakers_via_api() to get AI translations/gender
- Results added to speaker_data for user review

Output Format (JSON log):
```json
{
    "input_file": "input.txt",
    "timestamp": "2025-11-13T10:30:00Z",
    "statistics": {
        "total_lines": 1000,
        "unique_lines": 800,
        "duplicate_lines": 150
    },
    "code": {
        "lines_with_code": 50,
        "code_patterns": [
            {"code": "<tag>", "type": "HTML", "occurrences": 10}
        ]
    },
    "speakers": {
        "unique_speakers": 5,
        "speaker_data": {
            "Iori": {
                "occurrences": 45,
                "pronouns": {"私": 30},
                "honorifics": {"ちゃん": 15},
                "inferred_gender": "Female",
                "confidence": 0.85,
                "api_enrichment": {"romaji": "Iori", "note": "protagonist"}
            }
        }
    },
    "tokens": {
        "estimated_input": 5000,
        "estimated_output": 5500,
        "pricing_usd": 0.15
    },
    "glossary": {
        "matched_entries": 25,
        "suggestions": [
            {"original": "イオリ", "type": "Name", "reason": "appears 45 times"}
        ]
    }
}
```

Dependencies:
- Stdlib: json, logging, math, re, csv, difflib, datetime
- Optional: tiktoken (for accurate token counting)
- Local: glossaries package, dedup (lazy), API2Glossary (lazy if enabled)

Point of View Inference:
- _RAW_POV_PATTERNS: Pronoun patterns for Japanese, English, Chinese, Korean (1st/2nd person)
- _COMPILED_POV: Cache dict for compiled regex patterns
- _get_pov_patterns(language): Returns compiled patterns; English uses re.IGNORECASE; falls back to Japanese
- POVResult dataclass: pov ("1st"/"2nd"/"3rd"/"mixed"/"unknown"), confidence ("high"/"low"), counts, total_narrative_lines; to_dict/from_dict
- detect_pov(lines, language, protagonist_name, context_markers): Filters dialogue/menu/choice lines, counts pronoun matches per category, infers 3rd person via protagonist name frequency, derives confidence (high if dominant >60%, mixed if dominant <60% and secondary ≥20%)
- Integrated into prompt_builder.py: PromptBuilder.pov_result attribute; "Narrative Perspective" section added to system prompt when confidence is "high"

Notes:
- Token counting uses tiktoken if available, else heuristic
- Cost estimation based on GPT-4.1 pricing (configurable)
- Language detection uses heuristics (Japanese, English, etc.)
- All glossary detection is non-blocking (failures don't stop analysis)

CONSISTENCY.PY (Consistency System - Phase 55)

Purpose: Ensure consistent translation of recurring terms across all requests.

Data Model:
- ConsistencyTerm: dataclass with original, canonical_translation, type, confidence, source_line_idx
- ConsistencyStore: collection with case-insensitive lookup, add/remove/update, serialisation
- InconsistencyFlag: dataclass for check mode results with translations_found locations

Type Detection:
- detect_code_terms(code_patterns): Scans Code Database for action='translate'
- detect_glossary_terms(glossary_entries): Finds empty translation/notes entries
- detect_span_terms(lines): Detects paired tags (RPG Maker \C[n], HTML <b>)
- build_consistency_store(): Combines all three detections

Modes:
- run_preliminary(store, lines, api_call, passes): Pre-translation LLM passes, multi-pass confidence
- during_scan_output(store, originals, translated): Captures first translations
- during_replace_in_requests(store, lines): Propagates canonical to pending chunks
- check_consistency(store, chunks, originals): Post-translation inconsistency flagging

Dependencies:
- Stdlib: logging, re, dataclasses
- No external dependencies

DEDUP.PY (Deduplication Logic)

Purpose: Identify and handle duplicate lines

Functions:
- deduplicate_pre(text, manifest) → deduplicated text with mappings
- deduplicate_post(text, manifest) → expanded with duplicates restored
- aggressive_normalize_line(line) → line with numbers masked
- normalize_dedup_entries(manifest) → clean old dedup format

Features:
- Exact-line deduplication
- Aggressive dedup (mask numbers before comparison)
- Token-based mapping for restoration

Dependencies:
- Stdlib: re, json

CONFIG.PY (Session 4 - Configuration Persistence)

Purpose: INI/JSON configuration management with automatic defaults.
Also serves as central registry for model encoding mappings (TASK 16.3).

Constants:
- DEFAULT_CONFIG: Dict with default values for all sections:
  - [api]: provider, api_key, model, temperature, timeout, etc.
  - [recent]: last_input, last_manifest
  - [ui]: geometry, state
- MODEL_ENCODINGS: Dict[str, str] - Tiktoken encoding per model:
  - "gpt-4": "cl100k_base"
  - "gpt-4-turbo": "cl100k_base"
  - "gpt-4-turbo-preview": "cl100k_base"
  - "gpt-4o": "o200k_base"
  - "gpt-4o-mini": "o200k_base"
  - "gpt-3.5-turbo": "cl100k_base"
  - "gpt-3.5-turbo-16k": "cl100k_base"
  - "text-davinci-003": "p50k_base"
  - "text-davinci-002": "p50k_base"
- DEFAULT_ENCODING: str = "cl100k_base" - Fallback for unknown models

Functions:
- load_config(config_file, with_defaults=True) → Dict
  - Loads INI file and merges with DEFAULT_CONFIG
  - Returns complete config with all default keys present
- save_config(config_file, state) → bool
- get_config_file() → Path (canonical config location)
- ensure_config_initialized(config_file) → bool
  - Creates/updates config file with missing default values
  - Called automatically by test command and validation
- get_api_config() → Dict (API section with defaults)
- set_api_config(settings) → None (update API settings)
- get_ui_state() → Dict
- set_ui_state(state) → bool
- _merge_with_defaults(config) → Dict (internal merge helper)
- get_encoding_for_model(model: str) → str
  - Returns tiktoken encoding name for model
  - Falls back to DEFAULT_ENCODING for unknown models
- get_supported_encodings() → List[str]
  - Returns unique list of all supported encodings
- get_models_for_encoding(encoding: str) → List[str]
  - Returns all models using specified encoding
- get_model_pricing(model: str) → Dict
  - Returns pricing dict with name, input, output for model
  - Falls back to DEFAULT_PRICING_MODEL for unknown models
- get_model_names() → List[str]
  - Returns list of all available model IDs for pricing
- get_model_display_name(model: str) → str
  - Returns human-readable display name for model
- estimate_cost(input_tokens, output_tokens, model=None) → Dict
  - Estimates translation cost with input_usd, output_usd, total_usd
  - Uses DEFAULT_PRICING_MODEL if model not specified
- get_all_model_pricing() → Dict
  - Returns complete MODEL_PRICING dictionary

Model Pricing (TASK 16.4 - Single Source of Truth):
- MODEL_PRICING: Dict with 11 models (4 OpenAI, 3 Claude, 4 Gemini)
- DEFAULT_PRICING_MODEL: str = "gpt-4o-mini"
- OUTPUT_TOKEN_MULTIPLIER: float = 1.2 (JP→EN output ratio)
- Imported by: gui/steps/estimate.py, functions/analysis.py

Dependencies:
- Stdlib only: configparser, json, pathlib, logging

Notes:
- Zero circular imports
- Pure stdlib, no CherryAI dependencies
- Auto-initializes missing config sections on first access

OPTIONS.PY (Session 4 → Session 13 - API Providers)

Purpose: API provider definitions (single source of truth) and helper functions.

Note: OptionsDialog was deprecated and removed. The GUI now uses 
gui/dialogs/global_options.py → GlobalOptionsDialog for option management.

Constants:
- API_PROVIDERS: Dict mapping provider ID to {name, base_url, models}
  - openai, gemini, anthropic, local, ollama, lmstudio
- SUPPORTED_LANGUAGES: List of translation languages (from languages.py)

Functions:
- get_api_urls() → Dict[str, str] - Provider to base URL mapping
- get_provider_models(provider) → List[str] - Models for a provider
- get_all_provider_models() → Dict[str, List[str]] - All providers' models
- get_provider_names() → List[str] - All provider keys
- get_provider_display_name(provider) → str - Human-readable name
- get_api_settings_summary() → str - Brief status for display

Dependencies:
- tkinter, tkinter.ttk, tkinter.messagebox, logging, typing
- Local: config.py (get_api_config, set_api_config, DEFAULT_CONFIG)

Notes:
- Fully integrated into gui.py on_options() method
- One-way dependency on config.py (no circular imports)
- 29 unit tests in dev/test_options.py

DEPENDENCIES.PY (Session 4 - Dependency Management)

Purpose: Automatic package checking and installation via MD5 hashing

Functions:
- ensure_dependencies() → bool (startup entry point)
- check_and_install_dependencies() → Tuple[bool, str]
- compute_file_hash(path) → str (MD5)
- load_cached_hash(version_file) → Optional[str]
- save_cached_hash(version_file, hash) → bool
- install_requirements(requirements_file) → bool

Workflow:
1. Compute MD5(requirements.txt)
2. Load cached hash from .cherryai_deps.hash
3. If match → skip pip (already installed)
4. If mismatch or cache missing → run pip install
5. Save new hash to cache

Dependencies:
- Stdlib only: hashlib, subprocess, sys, pathlib, logging

Call site:
- CherryAI.py::_cli_entry() early in startup sequence

MODES (modi/ package)

Plugin architecture for processing modes.

Base interface (each mode implements):
- apply_pre(text, operation, manifest) → (modified_text, mappings)
- apply_post(text, operation, manifest) → (modified_text)

Key modes:

1. protect_code.py
   - Finds regex matches
   - Replaces with __PROT__ (Pre)
   - Restores from manifest (Post)

2. custom_placeholder.py
   - Finds regex/literal patterns
   - Replaces with custom token (Pre)
   - Restores from manifest (Post)

3. remove_restore.py
   - Removes content at anchor points (Pre)
   - Reinserts at anchors (Post)
   - Logs unsafe restores

4. standard_mode.py
   - Handles ellipses normalization
   - Empty line placeholders
   - Deduplication
   - Symbol conversion (fullwidth → halfwidth)
   - Runs last in pipeline
   
   Symbol Conversion Implementation:
   - `_SYMBOL_SETS`: Dict mapping character categories to language-specific glyphs
   - `_LANG_ALIASES`: Maps language codes (ja, en, jpn, eng, etc.) to ISO 639-3
   - `_build_symbol_replacements(src, tgt)`: Builds translation table for language pair
   - `_apply_symbol_conversion(lines, cfg, stats)`: Applies conversions in-place
   
   Supported Character Categories:
   - Quotes: 「」→"", 『』→''
   - Punctuation: 、。！？：；
   - Brackets: （）【】《》
   - Operators: ＝＋－＊／
   - Misc: ％～＆＠
   - Fullwidth digits: ０-９ → 0-9
   - Fullwidth letters: Ａ-Ｚ, ａ-ｚ → A-Z, a-z

Dependencies:
- Stdlib: re, json, logging
- Local: modehelper only

=============================================================================

PHASE 17 MODULES

BATCH_TRACKER.PY (Batch API Job Tracking - Phase 17.1)

Purpose: Build JSONL payloads, submit/poll/cancel OpenAI-compatible batch jobs,
         persist job metadata to user/batch_jobs.json.

Classes:
- BatchRequest: Single request envelope (custom_id, method, url, body)
- BatchJob: Persistent batch job with status tracking and timing

Functions:
- build_batch_jsonl(chunks, model, system_prompt, temperature) → str
- parse_batch_results(jsonl_text) → Dict[str, str]
- submit_batch(client, jsonl, description) → BatchJob
- poll_batch_status(client, job) → BatchJob
- retrieve_batch_results(client, job) → Dict[str, str]
- cancel_batch(client, job) → BatchJob
- list_provider_batches(client, limit) → List[Dict]
- save_batch_job(job) / load_batch_jobs() / remove_batch_job(job_id)

Dependencies:
- Stdlib: json, pathlib, dataclasses, datetime, logging
- Third-party: openai (OpenAI client)
- Local: none

KEY_MANAGER.PY (Multi-Key Rotation - Phase 17.2)

Purpose: Manage pools of API keys with automatic rotation strategies.

Classes:
- APIKey: Dataclass holding key, provider, status, rate-limit counters
- KeyPool: Pool of APIKey objects with configurable rotation
- PoolMode(Enum): SEQUENTIAL | EVEN | PRIORITY
- KeyStatus(Enum): ACTIVE | EXHAUSTED | REVOKED | RATE_LIMITED

Functions:
- KeyPool.add(key) / remove(key_id) / get(key_id) → APIKey
- KeyPool.next_key() → APIKey | None (applies rotation strategy)
- KeyPool.mark_exhausted(key_id) / mark_rate_limited(key_id, until)
- KeyPool.save(path) / KeyPool.load(path) → KeyPool

Persistence: user/api_keys.json

Dependencies:
- Stdlib: dataclasses, enum, json, pathlib, datetime, logging
- Local: none

USAGE_TRACKER.PY (Usage Analytics - Phase 17.5)

Purpose: SQLite-backed usage database for token/cost analytics.

Functions:
- record_usage(task_type, model, input_tokens, output_tokens, cost, ...) → int
- query_usage(start, end, task_type, model) → List[Dict]
- usage_summary(start, end) → Dict (totals by model and task_type)
- total_cost(start, end) → float
- total_tokens(start, end) → Tuple[int, int]
- export_csv(path, start, end) → int
- purge_before(cutoff) → int
- record_count() → int

Storage: user/usage.db (SQLite)

TASK_TYPES: api_test, glossary, game_summary, translation, tlc, editing

Dependencies:
- Stdlib: sqlite3, csv, pathlib, datetime, logging
- Local: none

AGENT_MODES.PY (Agent-Assisted Modes - Phase 17.8)

Purpose: Mode registry for agent-assisted workflows with sandboxed writes
         and full audit logging.

Classes:
- AgentMode: Registered mode with name, description, scopes, system_prompt
- AgentRequest / AgentResponse: I/O dataclasses for agent_call()
- AuditEntry: Timestamped audit record
- ReadScope / WriteScope (Enum): Permission scopes

Built-in Modes:
- INTERACTIVE_HELP: Read-only help on CherryAI features
- LANGUAGE_ASSISTANT: Language/grammar questions
- SCRIPT_AUTHOR: Script authoring in sandbox
- TRANSLATION_CHECK: Review translated lines

Functions:
- register_mode(mode) / unregister_mode(name)
- get_mode(name) / list_modes() → List[AgentMode]
- agent_call(client, request) → AgentResponse
- gather_context(mode, request) → str
- write_to_sandbox(filename, content) → Path
- log_audit_entry(entry) / load_audit_log(limit) → List[AuditEntry]

Sandbox: dev/sandbox/
Audit log: logs/agent/audit.jsonl

Dependencies:
- Stdlib: dataclasses, enum, json, pathlib, datetime, logging
- Third-party: openai (OpenAI client)
- Local: none

ESTIMATION.PY (Estimation Engine - Phase 17.9)

Purpose: Token/cost estimation with itemized billing and model comparison.

Classes:
- InferenceOptions: Dataclass for estimation parameters
- CostLineItem: Single billing line (label, tokens, unit_cost, subtotal)
- CostEstimate: Full estimate with line items, totals, notes

Functions:
- estimate_tokens_for_lines(lines, chars_per_token) → int
- estimate_chunks(total_tokens, chunk_size) → int
- compute_cost(input_tokens, output_tokens, input_price, output_price, batch) → CostEstimate
- build_estimate(lines, options) → CostEstimate
- compare_models(lines, model_options_list) → List[CostEstimate]
- save_options(options, path) / load_options(path) → InferenceOptions

Dependencies:
- Stdlib: dataclasses, json, math, pathlib, logging
- Local: functions.config (MODEL_PRICING)

I18N.PY (Internationalization - Phase 17.10)

Purpose: Language string loading and translation helper.

Functions:
- init(lang, lang_dir) → None: Load language JSON from user/lang/
- t(key, **kwargs) → str: Look up translated string with format substitution
- set_language(lang) / get_language() → str
- get_available_languages() → List[str]
- has_key(key) → bool
- missing_keys(reference_lang) → List[str]
- _flatten_dict(d, prefix) → Dict[str, str]: Flatten nested JSON keys

Language files: user/lang/<code>.json (nested JSON, dot-separated keys)
Fallback: English strings when key missing in active language

Dependencies:
- Stdlib: json, pathlib, logging
- Local: none

GUI/HELPERS/TOOLTIP.PY (Tooltip Helper - Phase 17.10)

Purpose: Attach configurable tooltips to any Tkinter widget.

Functions:
- attach_tooltip(widget, text, delay, wrap_length, use_i18n) → str (tooltip_id)
- detach_tooltip(tooltip_id) → bool
- get_tooltip_text(tooltip_id) → str | None
- set_tooltips_enabled(enabled) / are_tooltips_enabled() → bool
- set_tooltip_delay(ms) → None

Implementation: Uses Tk Toplevel overrideredirect window with enter/leave bindings.
When use_i18n=True, text is treated as an i18n key resolved via i18n.t().

Dependencies:
- Stdlib: tkinter
- Local: functions.i18n (optional, for use_i18n mode)

=============================================================================

BATCH PROCESSING ARCHITECTURE

Batch processing is the primary workflow in CherryAI, allowing multiple files to
be processed with a shared set of rules in a single session.

TERMINOLOGY

- Single-file mode: Load one input → configure rules → process → output
- Batch mode: Load multiple inputs → configure shared rules → apply to all → 
             each gets unique manifest

BATCH WORKFLOW (GUI)

Sequence:
1. User opens GUI (File → Load Multiple)
2. User selects multiple input files (or single file)
3. Files are loaded into "selected_files" array in gui.Py context
4. User configures rules in operation rows (shared across all files)
5. User clicks "Process Pre" or "Process Post"
6. For each file in selected_files:
   a. Clone the shared operations list
   b. Create unique manifest for this file
   c. Call Processor.process_pre(file_path, cloned_ops, unique_manifest)
   d. Save manifest to Projects/{filename}.CherryAI.json
   e. Save processed output to output/{filename}
7. Status updates show progress (File 1/10, File 2/10, etc.)
8. Log aggregates results across all files

DATA STRUCTURES (BATCH SUPPORT)

In gui.py context (App class):

```python
class App(tk.Tk):
    def __init__(self):
        ...
        self.selected_files: List[Path] = []  # Loaded input files
        self.current_operation_row: int = 0   # For UI management
        self.is_batch_mode: bool = False      # True if multiple files
```

Operation cloning (per-file isolation):

```python
# Shared operations from UI
shared_operations = [
    Operation(modus="Custom Placeholder", inputs=[...]),
    Operation(modus="Protect Code", inputs=[...])
]

# For File 1: Clone operations
file1_ops = [
    Operation(modus=op.modus, inputs=op.inputs.copy(), ...)
    for op in shared_operations
]

# For File 2: Independent clone
file2_ops = [
    Operation(modus=op.modus, inputs=op.inputs.copy(), ...)
    for op in shared_operations
]

# Each file gets its own Manifest
manifest1 = Manifest(operations=file1_ops, ...)
manifest2 = Manifest(operations=file2_ops, ...)
```

BATCH PROCESSING (MAINHELPER)

Processor.process_pre() and process_post() handle batch scenarios by:

1. Accepting single file path OR list of file paths
2. For each file:
   - Create independent Manifest
   - Apply operations sequentially
   - Store mappings in Manifest
   - Save manifest to Projects/{stem}.CherryAI.json
3. Return list of results (one per file)

Pseudo-code:

```python
class Processor:
    def process_pre(self, input_paths, operations, manifest_template=None):
        """
        input_paths: str | List[str]
        operations: List[Operation]  (shared template)
        manifest_template: Optional[Manifest] (for settings)
        
        Returns: Dict[str, result_info]
        """
        if isinstance(input_paths, str):
            # Single file
            input_paths = [input_paths]
        
        results = {}
        for input_path in input_paths:
            # Clone manifest for this file
            manifest = self._clone_manifest(manifest_template)
            manifest.input_file = input_path
            
            # Load input
            text = read_text(input_path)
            
            # Apply operations
            for operation in operations:
                mode_plugin = modi.get_mode(operation.modus)
                if operation.pre_enabled:
                    text, mappings = mode_plugin.apply_pre(
                        text, operation, manifest
                    )
                    manifest.mappings.update(mappings)
            
            # Save results
            output_path = self._get_output_path(input_path)
            write_text(output_path, text)
            
            # Save manifest
            manifest_path = self._get_manifest_path(input_path)
            manifest.save(manifest_path)
            
            results[input_path] = {
                "status": "success",
                "output": output_path,
                "manifest": manifest_path
            }
        
        return results
```

BATCH MANIFEST MANAGEMENT

Each file gets its own manifest JSON:

```
Projects/
├── input1.txt.CherryAI.json
├── input2.txt.CherryAI.json
├── input3.txt.CherryAI.json
└── ...
```

Content isolation:

```json
// Projects/input1.txt.CherryAI.json
{
    "input_file": "input1.txt",
    "created": "2025-11-13T10:30:00Z",
    "operations": [...],
    "mappings": {
        "custom_placeholder_tokens": {"line_0": ["__PHONE__"]},
        ...
    }
}

// Projects/input2.txt.CherryAI.json
{
    "input_file": "input2.txt",
    "created": "2025-11-13T10:30:02Z",
    "operations": [...],  // Same operations as input1, but independent
    "mappings": {
        "custom_placeholder_tokens": {"line_0": ["__CODE__"]},
        ...
    }
}
```

BATCH POST-PROCESSING

User workflow:
1. AI translates each protected file separately
2. User places translated versions in input/ (or imports them)
3. User selects translated files for post-processing
4. For each translated file:
   a. Load corresponding manifest from Projects/
   b. Call Processor.process_post(translated_text, manifest)
   c. Restore protections using manifest's mappings
   d. Save final output to output/

Example:
```
Batch Pre-Processing:
  input1.txt (shared rules) → output/input1.txt (protected)
  input2.txt (same rules)   → output/input2.txt (protected)

[User translates with AI]

Batch Post-Processing:
  translated_input1.txt (+ manifest1) → output/final_input1.txt
  translated_input2.txt (+ manifest2) → output/final_input2.txt
```

GUI BATCH FEATURES

File selection:
- File → Load Multiple: Opens multi-select dialog
- File → Add to Batch: Adds more files to selected_files
- File → Clear Batch: Resets selected_files to empty

Operation management:
- Shared rules: All rows apply to all files
- Preview: Show first N lines of file[0] before processing
- Dry Run: Process first file, preview results without saving

Status display:
- Progress bar: File X of N
- Current file name in title bar
- Real-time log updates
- Error notification (if File 2/5 fails, highlight it)

Batch processing buttons:
- "Process All (Pre)" - Runs all selected files through pre-TL pipeline
- "Process All (Post)" - Runs all selected files through post-TL pipeline
- "Process Selected" - Only process highlighted files (subset)

=============================================================================

ARCHITECTURE DIAGRAM

User (CLI/GUI)
    │
    ├─→ CherryAI.py (entry point)
    │        │
    │        ├─→ gui.py (Tkinter App)
    │        │    │
    │        │    ├─→ mainhelper.py (Processor)
    │        │    │    │
    │        │    │    ├─→ modi/ (mode plugins)
    │        │    │    │    ├─→ protect_code
    │        │    │    │    ├─→ custom_placeholder
    │        │    │    │    ├─→ remove_restore
    │        │    │    │    └─→ standard_mode
    │        │    │    │
    │        │    │    ├─→ analysis.py (File stats)
    │        │    │    ├─→ glossary.py (Term management)
    │        │    │    └─→ dedup.py (Deduplication)
    │        │    │
    │        │    ├─→ config.py (Settings)
    │        │    └─→ options.py (Dialog)
    │        │
    │        └─→ functions/
    │             ├─→ mainhelper.py
    │             ├─→ analysis.py
    │             ├─→ dedup.py
    │             └─→ dependencies.py
    │
    └─→ Data (manifests, glossary, logs)

File I/O Flow:

Input File → Processor.process_pre() → Protected Text
         ↓
         Manifest (mappings saved)
         
Translated Text → Processor.process_post() → Final Text
           ↓
           Manifest (restore mappings)

=============================================================================

DATA FORMATS

MANIFEST (JSON)

Stored at: Projects/{stem}.CherryAI.json

```json
{
    "version": "1.0",
    "input_file": "input.txt",
    "created_timestamp": "2025-11-13T10:30:00Z",
    "language": "ja",
    "operations": [
        {
            "modus": "Custom Placeholder",
            "inputs": ["\\d{3}-\\d{4}", "__PHONE__", "", ""],
            "is_regex": true,
            "pre_enabled": true,
            "post_enabled": true
        }
    ],
    "mappings": {
        "custom_placeholder_tokens": {
            "line_0": ["__PHONE__"],
            "line_5": ["__NAME__", "__EMAIL__"]
        },
        "protected_segments": {
            "line_2": [{"start": 0, "end": 5, "value": "<tag>"}]
        },
        "removed_items": {
            "line_10": ["removed_text"]
        },
        "standard_mode_config": {
            "enable_dedup": true,
            "aggressive": false
        }
    }
}
```

GLOSSARY (CSV)

Location: user/glossary.csv

```csv
Original,Translation,Notes,Source,Type,Gender,Refers_to_themselves_as,Referred_to_as
イオリ,Iori,Female protagonist,API,Name,Female,私,ちゃん
メイド,Maid,Occupation,Analysis,Term,,,
<color>,,,Analysis,Code,,,
```

CONFIG (INI)

Location: CherryAI.ini

```ini
[Paths]
last_input_dir = /path/to/last/used
last_template_dir = /path/to/templates

[UI]
window_width = 1200
window_height = 800
last_selected_mode = Custom Placeholder

[Processing]
enable_dedup = true
aggressive_dedup = false
```

ANALYSIS LOG (JSON)

Location: logs/{timestamp}.json

```json
{
    "input_file": "input.txt",
    "timestamp": "2025-11-13T10:30:00Z",
    "statistics": {
        "total_lines": 1000,
        "empty_lines": 50,
        "unique_lines": 800,
        "duplicate_lines": 150,
        "avg_line_length": 45,
        "max_line_length": 200
    },
    "tokens": {
        "estimated_input": 5000,
        "estimated_output": 5500,
        "pricing_usd": 0.15
    },
    "language": "ja",
    "glossary_matches": 25
}
```

=============================================================================

API REFERENCE

PROCESSOR API

```python
from CherryAI.functions.mainhelper import Processor, Manifest, Operation

# Create processor
processor = Processor()

# Prepare text for AI (Pre-TL)
prepared_text = processor.process_pre(
    input_path="input.txt",
    operations=[operation1, operation2],
    manifest=manifest_obj
)

# Restore text after AI (Post-TL)
final_text = processor.process_post(
    text=translated_text,
    manifest=manifest_obj
)

# Enable debug tracing
processor.trace_enabled = True

# Prepare for auto-translation
batches = processor.prepare_auto_translate(input_text)

# Execute auto-translation
translated_text, post_process_info = processor.execute_auto_translate(batches)

# Run full auto-translate pipeline
result = processor.run_full_auto_translate(input_text, callback_function)
```

ANALYSIS API

```python
from CherryAI.functions.analysis import analyze_file

# Run analysis
results = analyze_file(
    input_path="input.txt",
    logs_dir="logs/"
)

# Results is dict with keys:
# - total_lines, empty_lines, unique_lines
# - tokens.estimated_input, tokens.estimated_output
# - tokens.pricing_usd
# - language
# - glossary_matches
```

GLOSSARY API

```python
from CherryAI.functions.glossary import (
    read_unified_glossary,
    write_unified_glossary,
    update_glossaries_from_analysis,
    GlossaryEntry
)

# Read all entries
entries = read_unified_glossary()  # Dict[str, GlossaryEntry]

# Access entry data
if "イオリ" in entries:
    entry = entries["イオリ"]
    print(entry.original)              # "イオリ"
    print(entry.translation)           # "Iori"
    print(entry.gender)                # "Female"
    print(entry.refers_to_themself_as) # "私"
    print(entry.referred_to_as)        # "ちゃん"
    print(entry.source)                # "API" or "User" or "Analysis"
    print(entry.entry_type)            # "Name", "Term", "Code", etc.

# Write entries
write_unified_glossary(entries)

# Update from analysis results
results = update_glossaries_from_analysis(
    input_path="input.txt",
    logs_dir="logs/",
    confidence_threshold=75.0,  # Gender inference threshold
    update_mode="Add"  # Add, Update, Overwrite, or New
)

# results contains: {"speakers": {...}, "code": {...}, "terms": {...}}
```

NAME GLOSSARY API

```python
from CherryAI.functions.glossaries.name_glossary_functions import (
    detect_speaker,
    extract_names_from_honorifics,
    infer_gender_from_context,
    infer_gender_comprehensive,
    detect_explicit_gender,
    detect_honorific_gender_from_others,
    romanize_pronoun,
    romanize_honorific,
    update_speakers_in_glossary
)

# Detect speaker from dialogue line
speaker = detect_speaker("アリス: Hello!")  # "アリス"
speaker = detect_speaker("No speaker here")  # None

# Extract names with honorific patterns
names = extract_names_from_honorifics(lines)  # Dict[str, count]
# {"Alice": 10, "Bob": 5, ...}

# Detect explicit gender from status cards
gender, confidence, source = detect_explicit_gender(
    name="リリィ",
    text="名前：リリィ、性別：女性"
)
# ("Female", 100.0, "status_card")

# Detect gender from how others address the character
gender, confidence = detect_honorific_gender_from_others(
    name="リリィ",
    lines=all_lines,
    speaker_suffix_counts={"リリィ": {"ちゃん": 5}}
)
# ("Female", 90.0)

# Basic gender inference from pronouns and honorifics
gender, confidence, pronoun_found, suffix_found = infer_gender_from_context(
    pronouns={"私": 30, "あたし": 5},  # Detected pronouns
    honorifics={"ちゃん": 15},          # Detected honorifics
    confidence_threshold=75.0
)
# ("Female", 0.85, True, True)

# Comprehensive multi-signal gender inference (recommended)
gender, confidence, pronoun_found, suffix_found, source = infer_gender_comprehensive(
    name="リリィ",
    full_text=full_file_content,    # For explicit detection
    lines=all_lines,                 # For others' honorifics
    speaker_suffix_counts=counts,    # From analysis
    pronouns={"俺様": 100},          # Would suggest male
    honorifics={"ちゃん": 5},        # Others call her -chan
    confidence_threshold=75.0
)
# ("Female", 100.0, True, True, "explicit")  # Explicit overrides pronouns

# Romanize Japanese pronoun
print(romanize_pronoun("私"))    # "watashi"
print(romanize_pronoun("俺"))    # "ore"

# Romanize Japanese honorific
print(romanize_honorific("ちゃん"))  # "chan"
print(romanize_honorific("さん"))   # "san"

# Update glossary with detected speakers (with comprehensive inference)
path = update_speakers_in_glossary(
    speakers_count={"Alice": 10, "Bob": 5},
    speaker_pronoun_counts={"Alice": {"私": 8}},
    speaker_suffix_counts={"Alice": {"ちゃん": 10}},
    update_mode="Add",
    full_text=full_file_content,  # For explicit gender detection
    lines=all_lines               # For honorifics-from-others detection
)
```

CODE GLOSSARY API

```python
from CherryAI.functions.glossaries.code_glossary_functions import (
    detect_code,
    classify_code_type,
    generate_regex_pattern,
    update_code_in_glossary
)

# Detect all code segments in a line
code_info = detect_code("Hello <tag>world</tag>!")
# Returns: {
#   "has_code": True,
#   "code_segments": [
#     {"code": "<tag>", "type": "HTML", "position": (6, 11)},
#     {"code": "</tag>", "type": "HTML", "position": (16, 22)}
#   ]
# }

# Classify code type
code_type = classify_code_type("<tag>")        # "HTML" or similar
code_type = classify_code_type("\\n")          # "LINEBREAK"
code_type = classify_code_type("\\V[10]")      # "VISIBLEVARIABLE"
code_type = classify_code_type("[font color]") # "COLOR"

# Generate regex pattern for code
pattern = generate_regex_pattern("<tag>", "HTML")  # "<.*?>"

# Update glossary with detected code
path = update_code_in_glossary(
    code_counts={"<tag>": 10, "\\n": 50},
    update_mode="Add"
)
```

API2GLOSSARY API (Optional LLM Enhancement)

```python
from CherryAI.functions.API2Glossary import enrich_speakers_via_api

# Get AI enrichment for speakers
speaker_data = {
    "Alice": [0, 5, 10, 15, 20],    # Line indices where "Alice" appears
    "Bob": [1, 6, 11, 16]
}

all_lines = [...]  # Full file content

enrichment = enrich_speakers_via_api(
    speaker_data=speaker_data,
    all_lines=all_lines,
    enabled=True,  # Use API
    write_to_glossary=True  # Save to glossary
)

# enrichment contains:
# {
#     "Alice": {
#         "romaji": "Arisu",
#         "gender": "Female",
#         "note": "protagonist"
#     },
#     "Bob": {
#         "romaji": "Bobu",
#         "gender": "Male",
#         "note": "friend"
#     }
# }
```

DEDUP API

```python
from CherryAI.functions.dedup import deduplicate_pre, deduplicate_post

# Prepare for AI (find duplicates)
deduped_text, mappings = deduplicate_pre(original_text, manifest)

# After AI (restore duplicates)
final_text = deduplicate_post(translated_text, manifest_with_mappings)
```

CONFIG API

```python
from CherryAI.functions.config import load_config, save_config

# Load
config = load_config()  # Dict

# Save
save_config(config)
```

OPTIONS API

```python
# API provider definitions (single source of truth)
from CherryAI.functions.options import API_PROVIDERS, get_provider_models

# Get available models for a provider
models = get_provider_models("openai")  # ["gpt-4o", "gpt-4o-mini", ...]

# Get current API status summary
from CherryAI.functions.options import get_api_settings_summary
status = get_api_settings_summary()  # "openai/gpt-4o (Key: configured)"

# For options dialog, use GlobalOptionsDialog from gui/dialogs/global_options.py
from CherryAI.gui.dialogs.global_options import GlobalOptionsDialog
```

DEPENDENCIES API

```python
from CherryAI.functions.dependencies import ensure_dependencies

# Call at startup
success = ensure_dependencies()  # bool

# Returns True if all dependencies OK, False if failed
# (failure doesn't block app startup - graceful fallback)
```

=============================================================================

DEPENDENCIES

Runtime:
- Python 3.10+
- tkinter (stdlib, usually included)
- openpyxl >= 3.0.0 (optional, for .xlsx support)

Development (optional):
- pytest (testing)
- black (code formatting)
- mypy (type checking)

All other imports are Python standard library.

=============================================================================

DEVELOPMENT GUIDELINES

ADDING A NEW MODE

1. Create modi/new_mode.py
2. Implement apply_pre(text, operation, manifest) → (text, mappings)
3. Implement apply_post(text, operation, manifest) → text
4. Register in modi/__init__.py MODE_REGISTRY
5. Add to CherryAI.MODES list
6. Update documentation

ADDING A NEW FEATURE

1. Keep in mind the pipeline order:
   - Pre-TL runs first (protect → restore sequence)
   - Post-TL runs reverse
2. Use lazy imports where possible
3. Update manifest format if needed
4. Add to analysis output if user-relevant
5. Document in features.doc

MODIFYING DATA FORMATS

1. Update Manifest/Operation dataclasses
2. Add version field to manifest JSON
3. Add migration code to handle old formats
4. Update example data in logs

ERROR HANDLING

- Graceful fallback for optional dependencies (openpyxl)
- Log errors, don't crash
- GUI shows status messages
- Analysis logs detailed information

=============================================================================

=============================================================================

TESTING STRATEGY

CherryAI employs two test types for comprehensive validation:

SCRIPT TEST (pytest)
- Location: dev/test_*.py (1497 tests)
- Purpose: Fast unit tests, no LLM required
- Coverage: Manifest v2.0, modi integration, functions, replication, validation, config
- Run: pytest dev/ -v

API TEST (One_Click_Test)
- Location: functions/One_Click_Test.py (7 stages)
- Purpose: Full pipeline validation with LLM
- Coverage: Dependencies, config, I/O, pre/post processing, API
- Run: python CherryAI.py test (or --skip-api for offline)

For complete test reference, see doc/tests.md

=============================================================================

COMMON PATTERNS

LAZY IMPORT (avoid circular deps):

```python
# Instead of:
from CherryAI.functions.glossary import read_glossary

# Do this:
def my_function():
    from CherryAI.functions.glossary import read_glossary
    glossary = read_glossary()
```

OPTIONAL IMPORT (graceful fallback):

```python
try:
    import openpyxl
    XLSX_AVAILABLE = True
except ImportError:
    XLSX_AVAILABLE = False

# Later:
if XLSX_AVAILABLE:
    # Use openpyxl
else:
    # Skip xlsx support
```

PATHLIB (always use Path, not strings):

```python
from pathlib import Path

file_path = Path("output.txt")
file_path.parent.mkdir(parents=True, exist_ok=True)
file_path.write_text(content)
```

=============================================================================

ENTRY POINTS

GUI Mode:
```
python -m CherryAI.CherryAI
```

CLI Smoke Test:
```
python -m CherryAI.CherryAI --run-smoke [path]
```

CLI Analysis:
```
python -m CherryAI.CherryAI --analyze [file]
```

Check Dependencies:
```
python CherryAI/functions/dependencies.py --verbose
python CherryAI/functions/dependencies.py --force
```
