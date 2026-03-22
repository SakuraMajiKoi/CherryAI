  - postprocess.py - Step 6: Postprocess 🔗postprocess, manifest_fields; _FAILURE_POLICY_MAP for legacy enum mapping; translated input uses stage ceiling `tl → prepro → orig`; dedup-tagged rows skip batch placeholder fallback and `recover_line()` so duplicate rows are restored only from source-line postprocessing and do not accumulate false placeholder/code-pattern flags; aggressive number restoration now routes through shared `aggressive_restore_line()` and accepts both legacy number lists and indexed token maps (`<NUM1>`, `<NUM2>`, ...); Processed Lines adds a dynamic flagged-case combobox and stores recovery-detail text in row metadata for searchable filtering
6. Aggressive Number Restoration — replace aggressive dedup numeric placeholders from `aggr_numbers`; single-slot rows use `<NUM>`, while multi-slot rows use indexed tokens such as `<NUM1>`, `<NUM2>`, ... so reordered translations restore by explicit slot instead of left-to-right position
9. Aggressive Dedup Restoration (P5) — restore numbers from per-line data, including sources reached through chained dedup resolution; step data accepts legacy lists and indexed token maps for backward-compatible manifest recovery
CHERRYAI - TECHNICAL DOCUMENTATION

For Developers

=============================================================================

INSTRUCTIONS
---------------------

CRITICAL ARCHITECTURE PRINCIPLE:
The GUI must NOT contain processing logic. All processing functions belong 
in shared modules (functions/, modi/, formats/) that both CLI and GUI use.

PARSER CONTRACT PRINCIPLE:
Parsers in formats/ may identify and tag translatable payloads, but they must
NOT strip, split, normalize away, or silently drop valid quoted payloads.
Code stripping/protection and code recovery belong in downstream modi/functions
stages that intentionally transform text, not in extraction.

GUI CODE RULES:
- gui/ modules handle ONLY display, user interaction, and state management
- NO text manipulation, parsing, or translation logic in GUI code
- Use functions/ modules for all shared processing logic
- Modi plugins handle all pre/post-processing transformations
- Formats handlers manage all file I/O operations

MODULE AWARENESS (Always check these when implementing features):
- functions/    : 48 modules - core shared functionality (+ glossaries/ subfolder with 5 files)
- providers/    : 7 LLM provider modules - unified provider interface (Provider Handshake)
- modi/         : 12 processing modes - pre/post-processing plugins
- formats/      : 8 format handlers - file I/O for CSV, TXT, JSON, etc.
- gui/steps/    : 10 workflow tabs - display and user interaction only
- gui/components/: Reusable UI widgets (1 module: table.py)
- gui/dialogs/  : Modal dialogs and forms (7 modules: global_options.py, project_dialog.py, input_dialog.py, loading_progress.py, password_dialog.py, table_view.py, api_log_view.py)
- gui/widgets/  : Reusable standalone widgets (1 module: password_strength.py) [NEW 2026]
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

3. FUNCTIONS/ MODULES (47 files - Core Shared Logic)
   ✅ = Verified exists | ⚠️ = Needs documentation | 🔗 = GUI integrated
   
   3.1  analysis.py ✅ - File analysis, metrics, glossary extraction
   3.2  API2Glossary.py ✅ - LLM gender inference with json_schema structured output (details field), configurable prompt, case-insensitive normalization
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
   3.14 glossary.py ✅ - Unified glossary system (Phase 62 complete)
        * Global glossary file: `user/globalglossary.tsv` (4 columns: Original, Translation, Notes, Active)
        * Auto-migration on first access: glossary.csv → GlobalGlossary.csv → globalglossary.tsv; global_glossary.json merged then renamed .migrated
        * GlossaryEntry: original, translation, notes, source, entry_type, gender, refers_to_themself_as, referred_to_as
        * Metadata encoded in Notes as "(source=X; type=Y; gender=Z)" for TSV compatibility
        * Env var override for tests: CHERRYAI_TEST_GLOSSARY_PATH
        * ✅ Phase 62: `gui/steps/information.py` widget now reads/writes same `globalglossary.tsv`
   3.15 languages.py ✅ - Language definitions (single source of truth)
   3.16 local_llm.py ✅ - Local LLM integration
   3.17 logit_bias.py ✅ - Token logit bias for API
   3.18 mainhelper.py ✅ - Core Processor, Manifest, Operation
   3.19 modehelper.py ✅ - Modi mode selection utilities
   3.20 One_Click_Test.py ✅ - 7-stage integration test
   3.21 options.py ✅ - Option management
   3.22 postanalysis.py ✅ - Post-translation analysis
   3.23 postprocess.py ✅🔗 - Post-processing utilities (Step 6, moved from Step 7)
        * Bracket/Quote Balance Recovery uses anchor-relative positioning with ANCHOR_EQUIVS equivalence
        * Bracket recovery is gated: it only runs when the original line is bracket-balanced and the latest translated text is not
        * Bracket canonicalisation treats `【】` as square-bracket equivalents and can remove extra unmatched translated brackets before missing-bracket insertion
        * Key constants: BRACKET_EQUIV, QUOTE_EQUIV, _CANON_MAP, _CLOSING_TO_OPENING, _RECOVERY_ANCHOR_CHARS
       * Key functions: _normalize_bracket(), _find_anchor_near(), _try_anchor_bracket_insert(), _has_balanced_brackets()
        * recover_bracket_balance() defers bracket-quote hybrids (「」→ canon ") to quote recovery
        * recover_quote_balance() handles bracket-quote equivalents (「」≡"") via ANCHOR_EQUIVS
        * No absolute positional calculations — all insertion is line-start/end or anchor-relative
         * Code Pattern Recovery: recover_code_patterns() restores preserve-action patterns translated by the LLM using delimiter-aware regex matching; _detect_delimiters() identifies bracket pairs, including doubled delimiters such as `{{...}}`; nested inner matches (e.g. `{主人公}` inside `{{主人公}}`) are filtered so validation/recovery only acts on the outer token; RecoveryType.CODE_PATTERN added
   3.24 project_config.py ✅ - Per-project configuration
   3.25 prompt_builder.py ✅ - Build system prompts for API
   3.26 rate_limiter.py ✅ - API rate limiting (sliding window)
   3.26b header_rate_limiter.py ✅ - Header-based rate limiting (per-model, response-header driven)
   3.27 replication.py ✅ - Translation replication/update detection
   3.28 request_cache.py ✅ - Cache API requests
   3.29 retry_handler.py ✅ - Retry logic for API calls
   3.30 style_presets.py ✅ - Translation style presets
   3.31 validation.py ✅🔗 - Translation validation (Step 8, moved from Step 6)
        * validate_translation_comprehensive() check #7: code pattern preservation — verifies preserve-action patterns survive translation; triggers RetryReason.CODE_PATTERN_TRANSLATED
       * validate_code_patterns_preserved() filters nested balanced-code substring matches so doubled-delimiter patterns do not also trigger single-delimiter warnings on the same text
       * validate_line_pre() is the shared skip-classification path for Costs, Preview Requests, and Start Translation; it now handles preserve-pattern CODE_ONLY detection plus source-language-aware CJK/Hangul filtering
        * validate_line_post() treats code pattern failures as errors (not warnings)
    3.31a prompt_builder.py ✅🔗 - Shared prompt helpers and pre-translation code/placeholder classification
      * is_code_pattern_only() now uses a cached combined regex for preserve-action patterns instead of re-running one regex substitution per pattern per line during Translation status-summary rebuilds
      * Preserve-pattern matching still honors the `<NUM>` wildcard by mapping it to concrete digit runs before compiling the cached regex
      * The cached combined matcher is shared by Translation, Request Preview, and Estimation paths through `validate_line_pre()` so large manifests avoid repeated per-pattern regex work during passive tab entry
  3.32 wordwrap.py ✅🔗 - Word wrapping (Step 8)
   3.33 ini_manager.py ✅ - INI path resolution, typed access, preset management, defaults (TASK 21.1 + 2026)
        * INI location: user/CherryAI.ini (automigrared from root on first run)
        * optionxform = str: case-preserving keys (required for preset names like "Natural")
        * _REQUIRED_SECTIONS: all 10 sections always present; auto-initialised + saved on load
       * `[ui]` stores GUI-only persistence: `design`, `save_window_dimensions`, `launch_maximized`, `window_geometries`, `window_states`
       * GUI helpers: get/set GUI design, save-window toggle, maximize toggle, and per-window geometry/state JSON accessors
        * get_all_presets("style"|"tone") — returns built-in + user presets merged
        * set_preset_text / delete_preset — saves to [style] or [tone] section
        * get_default_text / set_default_text — long-text defaults from [defaults] section
        * restore_preset_defaults — clears user overrides from a section
        * set_last_manifest / get_last_manifest — persist last opened manifest
        * add_to_recent_manifests / get_recent_manifests — manifest history
     3.34 manifest_manager.py ✅🔗 - Unified manifest state management (TASK 19)
       * Sparse line-field helpers include `clear_line_field()` for removing redundant per-line stage output when a result matches its stage input
  3.35 manifest_fields.py ✅ - Manifest field type helpers (TASK 22.1) + special format helpers (TASK 22.2) + shared priority resolution API: resolve_line_field(), resolve_line_field_with_source(), resolve_line_field_from(), resolve_line_field_for_stage(), get_final_field_source(), get_latest_line_text(), get_line_text_for_stage(), get_all_lines_resolved(), get_all_lines_for_stage(); PIPELINE_FIELDS chain: final → wordwr → qa → postpro → tl → prepro → orig for final display/output, while stage helpers enforce ceilings (Postprocessing: tl → prepro → orig; QA: postpro → tl → prepro → orig; Wordwrap: qa → postpro → tl → prepro → orig); save_code_glossary/load_code_glossary support count as int or `[total, inst1_ct, ...]` list with instance_counts deserialization; save_character_notes/load_character_notes with count field
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
   3.47 api_log.py ✅🔗 - Structured API log store with per-project persistence (JSON lines format), category/status filtering, live subscriptions for GUI updates
   3.47 term_translation.py ✅🔗 - Unified term translation dispatcher (Romaji/LLM); json_schema structured output, prompt_type, configurable prompts; extract_code_segments() and validate_translation_code() for bracket-balanced code preservation validation
   
   3.48 glossaries/ (subfolder - 6 files)
        - __init__.py - Package exports
        - code_glossary_constants.py - Code pattern definitions
        - code_glossary_functions.py - Code detection/classification (updated: uses TSV via code_glossary_db)
        - code_glossary_db.py ✅ — TSV persistence layer (Phase 62: replaced SQLite with `codedatabase.tsv`)
            * init_db(), read_all_rows() (4-col compat), read_all_rows_extended() (9-col), write_all_rows(), upsert_rows(), delete_row()
            * 9 columns: Pattern, Type, RegEx, Notes, Visible, IsInvisible, IsCouple, IsNumber, IsWord
            * Migration on first access: codeglossary.db → codedatabase.tsv; global_codes.json merged then renamed .migrated
            * Env var override for tests: CHERRYAI_TEST_CODEGLOSSARY_PATH
            * ✅ Phase 62: `gui/steps/information.py::_global_db_path()` now uses same `codedatabase.tsv`
        - name_glossary_constants.py - Speaker patterns, romanization
        - name_glossary_functions.py - Speaker detection, gender inference

   3.50 api_config.py ✅ — Encrypted API configuration manager (user/API.ini); Phase 62 extended
        * Single source of ALL API meta information: provider profiles, model, temperature, URL, timeout, rate limits, encrypted keys
        * ✅ Phase 62: api_profiles.ini consolidated; `[translation]` and `[glossary]` sections added
        * Cache size helpers: `get_optimal_cache_size(model_id, provider)` reads per-model `optimal_cache_size` from API.ini; `_CACHE_DEFAULTS` per-provider thresholds (OpenAI: 1024+128); `_MODEL_SETTING_KEYS` includes `optimal_cache_size`
        * Key management: set_password(), verify_password(), is_password_set(), set_api_key(provider, key, password, name), get_api_key(provider, password, name), change_password(), migrate_from_ini(), disable_password(current_password), reset_password(), set_api_key_plain(provider, key, name), get_api_key_plain(provider, name)
        * Key listing: list_api_keys() returns [(provider, name), …] metadata; delete_api_key(provider, name) removes a saved key
        * INI format: `[api_keys]` section stores keys as `provider, name = encrypted_value` (Fernet AES-256) or plaintext when password disabled
        * Connection testing: test_api_connection(api_key, provider, base_url, timeout) → (bool, str, list); returns model ID list; uses OpenAI-compatible models.list()
        * Translation testing: test_model_translation(api_key, model_id, provider, base_url, timeout) → dict; 6-check translation probe (structured output, line count, code preservation, glossary adherence, completeness, output length)
        * PROVIDER_BASE_URLS: default base URLs for openai, gemini, anthropic, mistral, ollama, lmstudio, local
        * Profile settings (Phase 62 new): get_profile_setting(profile, key), set_profile_setting(profile, key, value), get_all_profile_settings(profile)
        * Migration: migrate_profiles_ini(path) — migrates non-secret fields from api_profiles.ini, renames to .migrated
        * PasswordStrength.assess(pw) / meter_text(pw) — Tiers: Instantly/Weak/Good/Great/Safe
        * See doc/passwords.md for full security documentation

   3.51 io_examples.py ✅ — I/O example text generator for system prompt enrichment
        * generate_io_examples(code_patterns, source_language, target_language, target_tokens) → (text, token_count)
        * calculate_fill_target(static_prompt_tokens, model_id, provider) → int — fills to optimal cache boundary
        * estimate_tokens(text) → int — tiktoken cl100k_base with heuristic fallback (len/1.7 JP, len/4 Latin)
        * _Example dataclass with language-keyed fields (`jp`, `en`), tags, and priority
        * _resolve_example_keys(source_language, target_language) → (source_key, target_key) — maps language names to example keys with en/jp fallback
        * _EXAMPLE_BANK: ~35 example pairs covering PLACEHOLDER, VARIABLE, COLOR, LINEBREAK, MEDIA, ICON, FONT, SPEAKER, PRESERVE, RUBY, SPAN, COMPLEX, PLAIN
        * _detect_project_tags() maps manifest code_patterns to example bank tags
        * _renumber_lines() ensures sequential LineN keys across grouped output blocks; Input/Output pairs share same numbering

3A. PROVIDERS/ MODULES (7 providers - Unified LLM Provider Interface)
    ✅ = Verified exists | 🔗 = Integrated with api_client.py & options.py

    Provider Handshake — pluggable provider abstraction replacing scattered
    if/elif provider branches with self-contained provider classes.

    3A.1 __init__.py ✅🔗 - ProviderBase ABC, ProviderRegistry, validate_provider(),
         shared types (TokenUsage, ProviderResponse, ThinkingConfig,
         TemperatureConfig, CachedInputConfig, BatchConfig),
         error hierarchy (ProviderError → 7 subtypes), _load_providers()
         ThinkingConfig: available/mode/mandatory/effort_levels/effort_default/budget;
         modes: ""(unavail), "builtin"(o-series), "explicit"(Claude), "optional"(GPT-4.1),
         "mandatory"(GPT-5); build_params() returns Chat Completions format
    3A.2 openai_provider.py ✅🔗 - OpenAIProvider (reference), OpenAICompatProvider
         (base for compatible providers). GPT-5 family: mandatory reasoning w/ effort
         levels (low/medium/high), no temperature. GPT-4.1: optional reasoning w/
         effort levels. O-series: builtin reasoning. Prompt caching, batch support.
         _is_gpt41_family(), _is_gpt5_family(), _is_reasoning_model() helper functions.
    3A.3 google_provider.py ✅ - GoogleProvider (inherits OpenAICompatProvider).
         Thinking via FALLBACK_MODELS lookup.
    3A.4 mistral_provider.py ✅ - MistralProvider (inherits OpenAICompatProvider).
         Temperature max 1.0. Magistral models have thinking.
    3A.5 anthropic_provider.py ✅ - AnthropicProvider (inherits OpenAICompatProvider).
         Explicit thinking mode via extra_body, budget default 10K.
    3A.6 local_provider.py ✅ - LocalProvider (direct ProviderBase), LMStudioProvider
         (port 1234), OllamaProvider (port 11434). json_schema format, $0 pricing.
    3A.7 provider_template.py - Documented skeleton for adding new providers.
         See also doc/adding_a_provider.md.

4. MODI/ MODULES (12 modes - Pre/Post Processing Plugins)
   ✅ = Verified exists | 🔗 = GUI integrated via mode_adapter | ❌ = Not integrated with GUI v2
   
   4.1  __init__.py ✅ - Mode loader, get_modi(), MODE_REGISTRY
   4.2  anchor.py ✅❌ - Anchor-based text protection
   4.3  custom_placeholder.py ✅❌ - User-defined placeholder replacement
   4.4  free.py ✅❌ - Free-form processing mode
   4.5  only_remove.py ✅❌ - Remove-only pattern mode
   4.6  protect_code.py ✅🔗 - Code protection → __PROTECTED__ placeholders (via mode_adapter)
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
  5.6 parser_base.py ✅ - ParserScript ABC, WordwrapConfig, ForbiddenChars, TagRules, ExtractedLine, SpeakerInfo; _split_speaker_dialogue() helper; inject_to() standardized 4-step Speaker:Dialogue-aware handshake (load→extract_tagged with speaker metadata→split speaker/dialogue and replace independently→save) returning List[int] failures, with a legacy adjacent `_translated` fallback only when a non-tagged parser cannot match any extracted key at all
   5.7 parser_rpgmaker.py ✅ - RpgMakerMVParser, RpgMakerMZParser implementations
   5.8 json_lenient.py ✅ - Lenient JSON parsing with error recovery
   5.9 handshake.py ✅ - ParserHandshake protocol: SpeakerInfo, ExtractedLine, ParserError, validate_parser()
   5.10 LightVN.py ✅ - LightVNParser: Light VN visual novel script parser (dialogue, menu, variable extraction/injection)

6. GUI V2 ARCHITECTURE (gui/ - 7 packages)
   
   6.1 gui/__init__.py - Package exports (App)
   6.2 gui/app.py - Main application window, step orchestration
   6.3 gui/progress.py - ProgressTracker, ProgressPanel
   
   6.4 gui/steps/ (10 files - 10 workflow tabs)
       - __init__.py - Step exports
       - base.py - BaseStep abstract class (TASK 43.14: tab caching infra; on_new_project() lifecycle method for state flush)
      - input_extract.py - Step 0: Input/Extraction 🔗formats/ (Phase 60: clickable column header sort with ▲/▼ indicators, file list filter entry, type column refresh fix, cross-file preview search with idx column and auto file-switching; non-destructive file addition with source root validation; Import Translation selection dialog with line fields and settings sections; preview columns: Project/File 1-based; parser-backed files are staged to `Original/` before final manifest sync and then re-extracted from that staged tree so LightVN project-scoped extraction stays aligned with Output injection)
       - analysis.py - Step 1: Analysis ❌NO shared imports
       - costs.py - Step 4: Costs (renamed from estimate.py in Phase 40; _estimate_via_formation() returns FormationResult with per-request line lists; _compute_per_request_prompt_overhead() uses gather_prompt_data()+build_request_prompt() per chunk for selective filtering; _get_prompt_tokens() and _get_static_prompt_tokens() also unified via gather_prompt_data()+build_request_prompt(); per-model API.ini settings take priority over Global Options — _do_estimation() reads chunk_size/tokens_limit from _chunk_var/_tokens_var (set by _load_model_settings()), only request_slicing read from GlobalOptions; respects request_slicing mode; Per-model settings saved/loaded via api_config; "📤 Apply Settings to Model" button is a one-way write to API.ini — model changes do NOT reload settings, loaded once on first tab entry via _settings_loaded_once flag; Translation Options row with Thinking, Translated Context, Rolling Context spinboxes; Request Mode 2×2 grid (Normal/Batch/Flex/Priority) with "(Available)"/"(Unavailable)" suffix labels and Selected (blue) states driving mode-specific pricing; _recalculate_costs_for_mode() instantly updates costs from existing token counts without re-estimation; _reprice_for_model() fast-reprices all cost and time labels when model changes using stored EstimationResult token counts — no re-estimation required; EstimationResult.num_requests stores per-side request count to enable fast reprice; EstimationProgressDialog is a non-blocking Toplevel that shows 7 step indicators (○/●/✓) and a ttk.Progressbar — opened by _run_estimation(), updated via _report_progress() from background thread using after(), closed by _estimation_complete(); Model combo disabled during estimation (_run_estimation sets state="disabled", _estimation_complete restores state="readonly"); CACHE_HIT_RATE=0.80 applied to static prompt prefix via _get_static_prompt_tokens() for cache savings calculation; Token Counts panel shows Input/Prompt/Cached/Total/Output rows — Prompt Tokens displays the non-cached portion (prompt_tokens − cached_tokens) so that Input + Prompt + Cached = Total Input; EstimationResult dataclass includes content_tokens, prompt_tokens, cached_tokens, num_requests; input_cost stores content-only cost, prompt_cost stores non-cached prompt cost, cached_input_cost stores cached portion cost; Cost Estimate panel is purely additive: Input (content) + Prompt (non-cached) + Cached + Output = Total; all four cost rows are primary un-indented rows; module-level _ceil_to_cents() and _fmt_cost() helpers format every displayed dollar amount rounded up to the next cent; Full estimation persisted to manifest via _save_estimation_to_manifest(); Estimate button renamed to "↻ Update Counts" after first run)
       - information.py - Step 2: Information 🔗manifest_fields (Bug Fix: on_leave() and _save_metadata() now merge *_enabled toggle BooleanVar values into metadata dict after ProjectMetadata.to_dict() — fixes toggle state erasure on tab change; Save button removed from header — auto-save on tab change is sufficient; Bug Fix: on_enter() reordered to load _load_metadata() BEFORE _load_characters_from_manifest()/_load_code_patterns_from_manifest() so authoritative top-level manifest data overrides stale step_state; on_leave() now calls _save_characters_to_manifest() and _save_code_patterns_to_manifest() to sync dual storage; _import_analysis_speakers() persists to top-level immediately)
      - preprocess.py - Step 3: Preprocessing 🔗manifest_fields; `_update_step_data()` persists `prepro` / `tags` by mutating loaded manifest line dicts in one indexed pass and then calling `_mark_dirty()` once, matching the `9721cba` behavior restored to avoid large-project tab-entry and Apply Rules freezes
      - translate.py - Step 5: Translation 🔗api_client, mock_translator, prompt_adapter, manifest_fields (Phase 43: merged columns, mock translation, provider model list, language skip, prompt editor redesign, retry refinement, tab caching; Preview Requests: PreviewRequest dataclass with _format_input_lines() for numbered line display and io_examples field, FILTER_PARTS constant (13 entries: meta, language, system_instructions, io_examples, style, tone, summary, genre, pov, conditional_prompts, glossary, rolling_context, input_lines), RequestPreviewDialog class with Pure/Formatted/Plain views and Jump/Search/Filter toolbar, _plain_text() preserves curly braces for game text, _build_preview_requests() mirrors real translation request building and gates each labeled section by *_enabled metadata flags, generates io_examples block with fill mode support, syncs _translation_options from current UI before _build_chunks(); _build_system_prompt_from_manifest() reads from `step_state.Information.data.metadata`; _load_model_settings() loads per-model API.ini settings (chunk_size, temperature, rolling_context, thinking) with Global Options fallback on tab entry; _build_chunks() reads rolling_context_between/after and chunk_max_tokens from per-model API.ini via get_model_settings() with Global Options fallback; Request Options: Key, Model, Request Mode combobox (Normal/Batch/Flex/Priority with "(Unavailable)" suffixes via _refresh_request_mode_options()), Model Settings/Translation Options Change… buttons, Character Whitelist/Blacklist (manifest-bound), Ban Tokens; TranslationOptions.request_mode field passed to APIConfig.request_mode in _do_translation(); _apply_char_filters() post-processes translations; _sync_from_global_options() syncs all hidden vars from GlobalOptions including TranslationSettings; _get_request_slicing_mode() reads slicing from GlobalOptions.translation)
      - postprocess.py - Step 6: Postprocess 🔗postprocess, manifest_fields; _FAILURE_POLICY_MAP for legacy enum mapping; translated input uses stage ceiling `tl → prepro → orig`; dedup-tagged rows skip batch placeholder fallback and `recover_line()` so duplicate rows are restored only from source-line postprocessing and do not accumulate false placeholder/code-pattern flags; Processed Lines adds a dynamic flagged-case combobox and stores recovery-detail text in row metadata for searchable filtering
      - qa.py - Step 7: QA 🔗validation, manifest_fields; table columns are Original / Quality Assurance / Overwrite; review input uses stage ceiling `postpro → tl → prepro → orig`; `qa` is review/display text only, while `qa_overwrite` is only persisted for explicit user edits that differ from QA input; includes inline overwrite editing and Copy to Overwrite action
      - wordwrap_overwrite.py - Step 8: Wordwrap 🔗wordwrap, manifest_fields; internal step id 8 but ninth user-facing tab after QA; preview column "Input"; input uses stage ceiling `qa → postpro → tl → prepro → orig`; manifest `filedir[].format` drives the preview format selector and per-format configs; stored `wordwr` is restored into the Wordwrap column without input fallback, and only explicit Apply persists sparse `wordwr` output; WrapMode now exposes `CUSTOM` and `SIMPLE` while still mapping legacy `manual` manifests to `CUSTOM`; WrapTarget adds `TAGS_FIRST`, `TAGS_ONLY`, `FILE_FIRST`, and `FILE_ONLY` strategies persisted in `WordwrapSettings.Target`; unresolved targets are preserved unchanged instead of defaulting to dialogue; Simple mode applies one shared wrap rule set to the selected file scope and does not auto-run when the mode changes; preview includes a compact Full-Table-View-derived file selector plus `View in File`; speaker-ignore width uses manifest `characters[]` as its allowlist, includes translated speaker aliases, falls back to parser `detect_speakers()` for the loaded preview rows when manifest speaker data is absent, and zero-width code comes only from manifest `code_patterns[]` entries marked `IsInvisible`
       - output_inject.py - Step 9: Output/Inject 🔗manifest_fields; _NAMING_STRATEGY_MAP for legacy enum mapping; OutputFormat.INJECTION enum; _get_fresh_lines_for_file() for stale-data fix; _write_injection() 4-step parser handshake; _get_same_as_source_dir() returns parent of Original/
   
   6.5 gui/components/ (2 files)
       - __init__.py - Component exports
      - table.py - SharedTable, ColumnDef, TableRow (Phase 43: batch insertion for large datasets; Phase 17: version tracking to cancel stale batches; TASK 71: bulk delete, 2000-row batches; TASK 72: page-based display (5000 rows/page), show_count_filter parameter, "Search:" label rename; text search now scans row values, tags, and nested metadata so Processed Lines can match Recovery Details text)
   
   6.6 gui/dialogs/ (7 files - 6 dialog modules)
       - __init__.py - Dialog exports
       - global_options.py - GlobalOptionsDialog with section panels:
         - OptionSection enum: API, REQUEST, TRANSLATION, CACHING, LOGGING, SESSION, GUI, LIMIT, FILE_IO, PROMPTS, SECURITY, UTILITY (12 sections)
         - Settings dataclasses: APISettings, RequestSettings, TranslationSettings, CachingSettings, LoggingSettings,
           SessionSettings, GUISettings, LimitSettings (SafetySettings=alias), FileIOSettings, PromptsSettings, UtilitySettings
         - TranslationSettings (NEW): overwrite_translation, skip_non_source_language, retry_strategy, request_slicing
         - GUISettings: GUI design dropdown + window-behavior toggles backed by `[ui]` in CherryAI.ini
         - Session keeps the legacy `theme` field for compatibility, but the live GUI design selector moved to Application → GUI
         - GlobalOptions container: all settings including `translation: TranslationSettings` + providers list; `safety` property is alias for `limit`
         - APIProviderEntry dataclass: name, provider_type, url, api_key, model (Task 43.6)
         - PROVIDER_PRESETS: 5 provider presets (Task 43.6)
         - _PresetPickerDialog helper dialog (Task 43.6)
         - API Key Management: "Saved API Keys" Treeview with Save Key/Load Key/Remove buttons;
           _save_api_key(), _load_api_key(), _remove_api_key(), _ensure_password_set(), _prompt_password()
         - Connection Test: _test_connection() calls api_config.test_api_connection() in background thread;
           on success opens _show_available_models_window() dialog with filterable model table and per-model translation testing
         - "Details" button inline with Provider dropdown (opens Available Models from registry cache)
         - _show_available_models() loads cached models; _show_available_models_window() displays filterable table
         - "Update" button in Available Models window triggers live API call to refresh models; saves metadata to API.ini via model_registry.refresh_models()
         - "Set as Default" button saves default model per key via api_config.set_default_model()
         - "Save" button persists filtered model list to API.ini saved_models setting
         - Gemini model IDs normalized (strips "models/" prefix) for display consistency
         - Filter states (Structured/Batch/No-Optional-Thinking/Cached-Input) saved to API.ini; Structured defaults to checked
         - "No / Optional Thinking" filter: shows "✓" for mandatory/builtin, "Optional" for optional, "—" for unavailable; filter excludes mandatory/builtin models (inverted logic)
         - "Cached Input" filter keeps only models with cached_input_price; Treeview includes Cached $/1M column
         - Temperature moved from API section to Request section (renamed "Model Settings")
         - TRANSLATION section: Workflow Defaults + Output Quality settings
         - API key entry with inline Save button between key entry and Show checkbox
         - GlobalOptions container: all settings + providers list; `safety` property is alias for `limit`
         - RequestSettings: +thinking_enabled, +thinking_budget, +reasoning_effort, +rolling_context_lines (Tasks 43.8, 43.9), +max_input_tokens (Task 41)
         - CachingSettings: fields renamed — dir, age (days), size (MB), mode; defaults 0=unlimited
         - _persist_to_ini(): Writes ALL settings sections to CherryAI.ini on every Apply/OK
         - _save_options() calls _persist_to_ini() for guaranteed persistence
         - Saving options reloads the active GUI design and reapplies it across the app plus open Toplevel windows
         - open_or_focus(): single-instance dialog helper keyed on the root window; reuses existing dialog, switches sections, and deduplicates save listeners
         - Sections organized in CATEGORY_ORDER: Connection (incl. Utility), Processing, Application (incl. Add-ons)
       - gui/theme/colors.py - Shared palette registry + live `THEME` proxy; `apply_theme()` styles ttk and classic Tk widgets, and `apply_window_preferences()` restores geometry/maximize preferences while applying the active palette
       - gui/dialogs/api_log_view.py / gui/dialogs/table_view.py - custom `refresh_theme()` hooks recolor rich text tags, Treeview row tags, alternating dark table rows, and selection bars when the GUI design changes at runtime
         - UtilitySettings: 18 fields for Term Translation, Gender Inference, and Misc (speaker_threshold) configuration
           - Term Translation: mode (Romaji/LLM), api_key_provider, api_key_name, model, batch_size
           - Gender Inference: mode (Script only/Script + LLM), api_key_provider, api_key_name, model
           - Script Confidence: minimum, maximum, ignore_unknown, do_all (defaults 30/50/True/True)
           - LLM Confidence: minimum, maximum, ignore_unknown, do_all (defaults 3/5/True/False)
           - API settings persisted to API.ini [term_translation] and [gender_inference] sections
           - Non-API settings persisted to CherryAI.ini [utility] section
         - UTILITY section: _build_utility_section() — Term Translation and Gender Inference panels
           - Term Translation: Mode dropdown, API Key combobox (from list_api_keys()), Model Combobox (auto-populated via _update_term_model_list → get_provider_models()), Batch Size spinbox
           - Gender Inference: Mode dropdown, API Key combobox, Model Combobox (auto-populated via _update_gender_model_list → get_provider_models()), Script/LLM Confidence sub-panels
           - Model Comboboxes update their values when the API key selection changes (provider extracted from "provider / name" combo value)
           - Each Confidence sub-panel: min/max spinboxes + Ignore Unknown + Do all Requests checkboxes
         - ADDONS section: _build_addons_section() — Treeview of installed addons (name/size), Delete/Refresh buttons
         - TASK 33.2: PromptsSettings for Edit/TLC custom prompts + Utility prompts
           - term_glossary: str - Configurable prompt for translating glossary/character terms
           - term_code: str - Configurable prompt for explaining code pattern labels
           - gender_inference: str - Configurable prompt for LLM gender inference
           - edit: str - Custom prompt for Edit steps (hidden from UI)
           - tlc: str - Custom prompt for TLC steps (hidden from UI)
           - Supports {source_lang} and {target_lang} placeholders (term prompts add {count})
           - Gender prompt uses {name} and {excerpt} placeholders
           - Stored in [prompts] section of CherryAI.ini (factory defaults embedded in ini_manager._FACTORY_DEFAULTS_INI_TEXT)
           - PROMPTS section UI: Utility prompts at top (Glossary, Code, Gender Inference); Edit/TLC hidden
         - **Session 24+: Conditional Prompts in PromptsSettings (dialogue/menu/choice/unknown):**
           - PromptsSettings gains 4 new fields: dialogue, menu, choice, unknown
           - DEFAULT_DIALOGUE_PROMPT / DEFAULT_MENU_PROMPT / DEFAULT_CHOICE_PROMPT / DEFAULT_UNKNOWN_PROMPT constants
           - Initialized from [conditional_prompts] in defaults.ini; persisted to [prompts] in CherryAI.ini
           - get/set_conditional_prompt() helpers in ini_manager for typed access
           - Configurable via Global Options → Prompts section (4-row table: 3-line Text + scrollbar + Reset)
           - Used by get_context_prompt() in prompt_builder.py for live translation and mock translation
         - Security Section (2026): Set/Change/Disable/Reset master password, PasswordStrengthWidget tester,
           HiveSystems tier legend, bcrypt + AES-256 info, plaintext key mode, links to doc/passwords.md
       - project_dialog.py - Project management dialogs (TASK 19, TASK 21.4, Phase 58.11):
         - ProjectNameDialog: Prompt for project name on new project creation (500x280, empty name field)
         - LoadManifestDialog: File browser for loading existing manifests (sorted by date, latest first)
         - WelcomeDialog: First launch dialog with Resume/New/Load/Fresh options
           - Auto-load checkbox: "Automatically load last project on startup" (Phase 58.11)
           - Persists setting to [session].load_last via ini_manager
       - input_dialog.py - Unified Input Dialog (Phase 58.1, Phase 58.12):
         - UnifiedInputDialog: Dual-pane file/folder selection
         - Left pane: File browser with multi-select
         - Right pane: Folder browser with multi-select
         - Path list display for selected items
         - **Phase 58.12:** Last directory persistence via ini_manager
         - **Phase 58.12:** Project Name field in Options panel (show_project_name parameter)
         - Returns 4-tuple: (paths, format, encoding, project_name)
       - loading_progress.py - Progress dialog for long-running operations
       - password_dialog.py - Master password dialogs (2026):
         - SetPasswordDialog: First-time password creation with PasswordStrengthWidget + confirm field
         - ChangePasswordDialog: Authenticated password change with old/new/confirm fields
         - VerifyPasswordDialog: Single-entry unlock prompt (used to authenticate API key access)
         - All dialogs delegate to functions/api_config.py for hashing and encryption
       - table_view.py - Full Table View dialog (2026):
         - FullTableViewDialog: Spreadsheet-like view of all manifest line entries
         - Constants: LINE_FIELDS (12 fields), COLUMN_DISPLAY_NAMES (human-readable names), DISPLAY_NAME_TO_FIELD (reverse lookup), DEFAULT_HIDDEN (empty set), NON_EDITABLE_FIELDS (idx, orig), METADATA_FIELDS (log, tags, prepro_ops)
         - Column display names: idx→Line #, orig→Original, prepro→Preprocessed, tl→Translated, postpro→Postprocessed, qa→Quality Assurance, qa_overwrite→Overwrite, wordwr→Wordwrap, final→Final, overwrite→Overwrite (Legacy), tags→Tags
         - Column visibility: auto-hides empty columns; slim tk.Menu dropdown with Show All/Show Visible/Show Latest presets; all columns including Line # are hideable
         - Column selection bar: "Select / Selected" labels above each column, synced widths via Canvas, for search/replace scoping
         - Sort indicators: ▲/▼ arrows in column headers; _sort_column and _sort_reverse state tracking
          - Cell editing (double-click), deletion (Del key), multi-select, and a Clear Columns dialog for `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, `wordwr`, and `final`; clearing `tl` requires double confirmation
           - `Wrap Selection` toolbar action opens a modal dialog mirroring Step 8 Simple mode (`Max Char`, `Max Line`, `Break Char`, `Pretty Wrap`), displays the literal newline note for `\n` versus `\\n`, persists those values into `WordwrapSettings`, and applies the shared wrapper to selected rows via `resolve_line_field_for_stage(..., "wordwrap")`
          - `final` editing is table-local until Save: empty cells prefill from the first non-empty lower stage when editing starts, and edits that collapse back to that source text are cleared back to sparse-empty in the working copy
         - Read-only Original: double-click shows copyable text widget (_show_readonly_cell)
         - File filter dropdown: hierarchical folder navigation with Back/All navigation; font size 11
         - Two-row toolbar: search row (top) with file filter, search entry, column selector, Results Only toggle, Prev/Next arrows; replace row (bottom) with replace entry, Replace All, action buttons
         - Results Only mode: inverted Show Misses (_on_toggle_results_only)
         - Search/replace scopes to visible columns or _selected_columns when populated
         - Tags (tag) and Line # (idx) are searchable (removed from METADATA_FIELDS)
         - Row selection with highlighting; Ctrl+click and Shift+click support
         - Pagination: Show All / Show X with configurable page size (default 100)
         - Save/Reset/Diff buttons: saves changes to manifest, resets from snapshot, diff mode
         - Change tracking: unsaved changes highlighted; close prompt to save/discard
         - Accessed via "Full Table View" menu bar entry (direct command, no dropdown)
         - _FileFilterDropdown helper: hierarchical listbox with scrolling and keyboard nav
       - api_log_view.py - API Log viewer dialog (2026):
         - APILogViewDialog: Non-blocking Toplevel window for viewing structured API log entries; calls self.lift() at end of __init__ to stay visible above translation progress
         - open_or_focus(): single-instance dialog helper keyed on the root window; reuses the existing API Log window and focuses it instead of creating duplicates
         - Toolbar: search entry, category filter combobox, view mode radio buttons (Sent/Received/Both), display-limit spinbox (All/1000/2500/5000/Nothing), Clear Log button
         - Log display: tk.Text widget with word wrap, color-coded tags (success=green, recovered=yellow, failed=red, pending=grey)
         - Display limit is persisted via `ini_manager` in `[log].api_log_display_limit`; default is `All`, so `_render_wrapped_content()` renders every stored line unless the user chooses a smaller viewer-only limit
         - Entry status handling: `LogEntry.status` is plain `str` (deserialized from JSON); `_render_entry()` uses `entry.status.upper()` (not `.value.upper()`); dict lookups with `LogStatus` enum keys work via str-enum equality
         - Sent blocks: model, provider, temperature, chunk info, full system prompt, full user content
         - Received blocks: token statistics, duration, finish reason, error messages, response content
         - Status bar: filtered/total entry count, aggregated token totals
         - Live updates: subscribes to APILogStore for real-time display; thread-safe via after() scheduling
         - Category filter: All Categories, Main Translation, Term Translation, Gender Inference, Other
         - Search: case-insensitive text search with yellow highlights across all entry fields
         - Accessed via "API Log" menu bar entry (direct command, no dropdown)

   6.7 gui/widgets/ (2 files - 1 widget module) [NEW 2026]
       - __init__.py - Widget package
       - password_strength.py - PasswordStrengthWidget (ttk.Frame subclass):
         - Entry field with "Show" toggle (bullet / plaintext)
         - Real-time coloured strength indicator (tk.Label background colour)
         - Tier text label (e.g. "Safe (16 chars, 3 character types)")
         - on_change callback for external validation (e.g. enable/disable OK button)
         - Public API: get(), set(), clear(), focus(), bind_entry(), configure_entry()
         - strength_var / colour_var: tkinter StringVars exposing current tier + hex
   
   6.7 gui/helpers/ (9 files - 7 adapter modules + 1 confirmation module)
       - __init__.py - Helper exports
       - mode_adapter.py - Bridge between GUI config and modi/ modules (TASK 16.5; TASK 72: tags_by_line tracking, progress_cb parameter; TASK 73: apply_dedup_batch, apply_aggressive_dedup_batch, DEDUP_PLACEHOLDER, aggressive helper fallbacks)
         - Custom Placeholder preprocessing persists both flat captures and token-aware `placeholder_records` so postprocessing can restore named replacements batch-wide when an LLM shifts them onto another line
       - analysis_adapter.py - Bridge between GUI and functions/analysis.py (TASK 16.6)
         - detect_individual_codes_batch(): Individual code patterns with counts, types, and instances dict (raw_code → occurrence count per normalized pattern)
         - analyze_lines(): Full analysis with speaker_samples and individual_codes
         - _friendly_code_type(): Internal type constant → display name mapping
       - glossary_adapter.py - Bridge between GUI and glossary/config/style modules (TASK 16.7)
         - Note: Speaker actions in analysis.py write to character glossary (`characters` key)
           via `_upsert_character_entry()`, not to project glossary entries
       - chunker_adapter.py - Bridge between GUI and functions/chunker.py
       - prompt_adapter.py - Bridge between GUI and functions/prompt_builder.py (TASK 73: build_full_system_prompt shared builder — single source of truth for §5.2 prompt assembly)
         - Unified request builder: `gather_prompt_data(mgr)` centralises ALL data gathering (metadata, glossary, characters, code patterns, POV, sample_lines) with fallback field merging for source_language/target_language/genre; `build_request_prompt(prompt_data)` thin wrapper calls `build_full_system_prompt()` with the gathered data — all features (Estimation Step 4, Request Preview, Start Translation Step 5) use these two functions to guarantee identical prompts
         - Section toggle flags: `build_full_system_prompt()` reads `*_enabled` boolean keys from metadata to gate prompt sections (genre_enabled, summary_enabled, style_enabled, tone_enabled, system_instructions_enabled, glossary_enabled, code_database_enabled)
         - I/O Examples injection: slot 2b between System Instructions and Style; reads `metadata.io_examples` mode; imports `generate_io_examples`, `calculate_fill_target`, `estimate_tokens` from `functions/io_examples.py`; never modifies System Instructions; fill mode pre-computes tokens for ALL later static sections (style, tone, summary, genre, protagonist, POV, context-type) before calculating fill target
         - Code patterns in slot 9: code patterns with action="translate" are included alongside glossary entries and characters in the glossary section, with per-chunk selective filtering
       - manifest_binding.py - Widget-to-Manifest binding system (TASK 22.3)
       - tooltip.py - Tooltip display utilities for widgets
       - confirmations.py - Confirmation dialog with "Don't ask again" opt-out (Phase 60)
         - confirm_action(parent, key, title, message): custom Toplevel with checkbox
         - is_suppressed(key) / suppress(key): INI-backed suppression state
         - reset_all_suppressions(): removes entire [confirmations] section
   
   6.8 gui/state/ (2 files)
       - __init__.py - State exports
       - store.py - SessionState, StepState (legacy, autosave disabled)
   
   6.9 functions/manifest_manager.py - ManifestManager (v3.1)
       - Primary state management for GUI projects
       - Singleton pattern for global access
       - Dataclasses: ProjectInfo, StepStateData, ManifestState
       - Loads/saves extended manifest v3.0 format
       - TASK 21.2: Creates manifests with ALL v3.0 fields from INI defaults
       - TASK 21.3: Settings helper methods for processing functions
       - TASK 32.1: Absolute path storage:
         - create_new() computes folder name for source_root, copies files to Original/
         - source_files is no longer stored; file resolution uses Original/ directory
       - Shared import + patch helpers now live here so Input step stays GUI-only: manifest-to-manifest import, batch file pruning, identical-Original comparison, and Create Patch orchestration all execute in `functions/manifest_manager.py`

   6.10 functions/ini_manager.py - INI Configuration (v3.0 + Phase 62)
       - Central INI path resolution relative to main module
       - Typed access: get_str(), get_int(), get_float(), get_bool(), get_list()
       - Manifest defaults: get_all_manifest_defaults(), get_manifest_default()
       - **Atomic save:** _save_ini() writes to `.tmp` file, fsync, `os.replace()` to final path — prevents corruption from interrupted writes. All write paths (set_default, clear_user_defaults, save_ui_state) route through _save_ini().
       - **Centralized UI state:** load_ui_state() / save_ui_state() — JSON-serializable dict stored in [ui] state; uses shared _ini_cache and atomic save so UI state writes never wipe other INI sections. mainhelper.save_app_state() and load_app_state() delegate to these functions.
       - **Phase 62:** Directory initialisation on startup:
         - ensure_app_dirs() — creates user/, Projects/, logs/, cache/ under app root; called from _load_ini()
       - TASK 21.4: Recent/Session management:
         - get_last_manifest() / set_last_manifest() - Last used manifest path
         - get_recent_manifests() / add_to_recent_manifests() - Recent list
         - get_load_last() / set_load_last() - Auto-restore toggle (was get/set_restore_on_launch)
       - Phase 60: Section management:
         - remove_section(section) - Remove entire INI section (used by reset_all_suppressions)
       - **Phase 58.12:** Last input directory persistence:
         - get_last_input_dir() - Get last used input directory (returns Path or None)
         - set_last_input_dir() - Store last used input directory in [session] section
       - TASK 31.2: User defaults management:
         - get_initial_default() - Load from embedded _FACTORY_DEFAULTS_INI_TEXT constant (Session 25)
         - get_user_default() / set_user_default() / has_user_default() - User defaults in [user_defaults]
         - get_effective_default() - Resolves user > initial > fallback chain
         - save_as_user_defaults() - Save multiple values for a section
         - get_all_user_defaults() / get_all_initial_defaults() - Get all for section
         - clear_user_defaults() / restore_initial_defaults() - Reset to factory
         - reload_defaults_cache() - Clear defaults.ini cache
       - **INI Population (Session 24+, updated Session 25+):** Auto-seed CherryAI.ini from embedded factory defaults on first load:
         - _DEFAULTS_POPULATE_MAP: maps factory-default sections → CherryAI.ini sections
         - _populate_from_defaults(config): reads embedded _FACTORY_DEFAULTS_INI_TEXT; seeds empty CherryAI.ini
           sections; special handling routes [conditional_prompts] → [prompts] keys
           (dialogue/menu/choice/unknown); unescapes `\n` to real newlines
           (dialogue/menu/choice/unknown); unescapes `\n` to real newlines
         - _seed_builtin_sections(config): seeds Python-constant long-text data not in factory INI text —
           [style] (7 built-in style presets, seeded **per-key** so user presets are preserved),
           [tone] (8 built-in tone presets, same per-key approach),
           [system_instructions].Default (full SI with Output Examples section),
           [defaults].{default_style="Natural", default_tone="Neutral", Summary,
           SystemInstruction="Default"} — SystemInstruction stores the **preset name** (e.g. "Default")
           not the full text, consistent with default_style/default_tone.
           Migration: if [defaults].SystemInstruction contains newlines (legacy full text), replaces with "Default".
           Only writes keys that are absent; never overwrites user values. Returns True if anything written.
         - _migrate_preset_values(config): detects and corrects **mis-assigned** built-in preset values —
           if a built-in preset name (e.g. Dramatic) has the exact text of a *different* built-in
           (e.g. Neutral), restores the correct built-in text. Ignores user-customised values.
           Returns True if any value was corrected. Called by _load_ini() before _seed_builtin_sections().
         - Called by _load_ini() after _populate_from_defaults()
         - get_default_text("SystemInstruction"): resolves the stored preset name via get_si_preset();
           if stored value has newlines (legacy full text) returns it directly for backward compat.
       - **Conditional Prompt Helpers (Session 24+):**
         - _CONDITIONAL_PROMPT_DEFAULTS: hardcoded fallbacks per context type
         - get_conditional_prompt(context_type, fallback="") → str: reads [prompts] section; falls back to hardcoded defaults
         - set_conditional_prompt(context_type, value) → bool: writes to [prompts] section via set_default()
       - **Pattern Prompt Helpers (new):**
         - PATTERN_PROMPT_NAMES: list of 9 pattern-triggered prompt names
         - get/set_pattern_prompt_enabled(name): reads/writes [pattern_prompts] section enabled flag
         - get/set_pattern_prompt_text(name): reads/writes [pattern_prompts] section instruction text
         - get/set_merged_request_text(kind): reads/writes merged-request instruction texts
   
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
       - **Phase 23 Integration:** InformationStep uses 13 bindings:
         - ProjectName, Title, Genre (text entries)
         - SourceLanguage, TargetLanguage (language comboboxes)
         - Summary (multiline text)
         - StylePreset, TonePreset (preset comboboxes, string-based since Phase 60)
         - CustomStyle, CustomTone (ScrolledText fields, saved on FocusOut since Phase 60)
         - Prompt (multiline text, renamed from Additional Notes)
         - SIPreset (System Instructions preset combobox, string-based)
         - io_examples (I/O Examples mode combobox, metadata field via `_on_io_examples_changed()`)
       - **Phase 24 Integration:** PreprocessingStep uses 7 bindings + special format helpers:
         - Standard toggles: Deduplication, DeduplicationThreshold, EllipsisCompression,
           SymbolConversion, ProtCompression, SpeakerNameReplacement, CodeSpacingRules
         - Special formats: ProtectCodePatterns, CustomPlaceholders, AnchorRemoval
       - **Phase 25 Integration:** CostsStep (renamed from EstimationStep) and QAStep manifest bindings:
         - Analysis results: InputLines, InputTokens, OutputTokens (int fields)
         - ValidationRules nested: PlaceholderPreservation, AnchorPreservation,
           SourceLanguageDetection, SpeakerFormat, QuoteBalance, EmptyTranslation
       - **Phase 26 Integration:** QAStep and TranslationStep manifest bindings:
         - QAOptions nested: RerunPolicy (text), MaxSourceLanguageChars (int), MaxLineLength (int)
         - RequestOptions nested: Model (text), Temperature (float), LinesPerChunk (int),
           RetryStrategy (text), MaxRetries (int), EnableRequestCaching (bool),
           LineByLineMode (bool), ContextLines (int), Thinking (bool), ThinkingBudget (int), ReasoningEffort (str: low/medium/high)
       - **Phase 27 Integration:** PostprocessingStep manifest bindings:
         - PostProcessing nested (8 booleans): PlaceholderRecovery, BracketBalanceRecovery,
           QuoteBalanceRecovery, WhitespaceNormalization, RestoreCodeCharacters,
           RestoreLinebreaks, EnableSymbolConversion, FullwidthToHalfwidth
         - PostProcessing.FailureHandling (text enum: "skip", "flag", "retry")
       - **Phase 28 Integration:** WordwrapOverwriteStep manifest bindings:
         - WordwrapSettings nested: Mode (text), Width (int), BreakChar (text),
           MaxLines (int), PrettyWrap (bool), SpeakerHandling (text),
           TagConfigs (legacy list of dicts), FormatConfigs (per-format list of dicts)
       - **Phase 28 Integration:** OutputInjectStep manifest bindings:
         - OutputFormat nested: Destination (text), PreserveFolderStructure (bool), Format (text),
           PairMode (text), Encoding (text), FileNaming (text: suffix/prefix/subfolder),
           TextOption (text), OverwriteExistingFiles (bool), Backup (text),
           BackupExtension (text), ExportManifestFile (bool), ExportProcessingLogs (bool),
           ExportGlossaryEntries (bool)
         - Defaults are manifest-backed: Destination=`Same as Source`, PreserveFolderStructure=True,
           PairMode=`custom`, FileNaming=`subfolder`, OverwriteExistingFiles=True,
           Backup=`timestamp`, BackupExtension=`.bk`, export extras disabled
         - Format and Encoding are seeded from the first loaded input file when the manifest has no valid OutputFormat values yet
       - **Phase 29 Integration:** ManifestManager autosave system (TASK 29.1):
         - Background thread with configurable interval (default 60s, clamped 5-300s)
         - Only saves when `_dirty` flag is set
         - Settings from INI `[session]` section: `autosave` (bool), `interval` (int seconds)
         - Auto-starts on create_new() and load(), stops on close()
         - Atomic saves: write to `.tmp` file, fsync, `os.replace()` to final path
         - Thread-safe: `save()` acquires `_autosave_lock` to prevent concurrent writes from autosave thread and main thread; `os.replace()` retries 3 times with back-off for transient Windows file locks
         - `_SafeManifestEncoder`: fallback JSON encoder for non-serializable objects (str coercion)
         - Deep-copy safety: callers that mutate `get_step_data()` results use `deepcopy()`
         - SessionState autosave: disabled (no-op stubs); all autosave handled by ManifestManager
         - Properties: autosave, interval, save_on_close
         - Methods: start_autosave(), stop_autosave()
       - **Phase 29 Integration:** Save triggers (TASK 29.2):
         - On close: App._on_close() saves manifest with retry logic (3 attempts, exponential backoff); on persistent failure prompts user to force-quit or retry; structured sequence: save manifest → save INI → stop autosave → write session ref → destroy
         - After file load: InputExtractionStep._save_manifest_after_file_load()
         - Before translation: TranslationStep._save_manifest_before_translation()
         - All save methods check is_loaded, have try/except, log success/failure
       - **Phase 41 Integration:** Information Step UI enhancements:
         - Widget renames: Summary, System Instructions, Code Database
         - Genre dialog merges selected genres with existing (non_common preserved)
         - "Other" language triggers simpledialog; reverts on cancel via _prev_source_lang/_prev_target_lang
         - Style/Tone preset system (Phase 60): replaced trace-based graying with full preset management
           - Dropdown (combobox) + ScrolledText prompt field + Save/Delete buttons for Style and Tone
           - DEFAULT_STYLE_PRESETS / DEFAULT_TONE_PRESETS dicts with LLM prompt text
           - User presets in `user/presets/` as JSON files
           - `_unique_preset_name()` appends ascending numbers for duplicates
           - `confirm_action()` for preset deletion with opt-out
         - Glossary table: 4-column Treeview (Active ✓/✗, Original, Translation, Notes)
         - Speaker multi-select removal: selectmode="extended" with reverse-index batch deletion
         - Gender inference progress dialog: Toplevel with progress bar, "Checking 'name'" label, X/Y count; both script and LLM passes run in background threads with queue-based polling via `after(100)` to keep UI responsive; Cancel button visible from the start via `threading.Event`
         - Inline editing via double-click with Entry overlay; Delete key removes entries
         - Import from Analysis: choice dialog (Top N / All) with spinbox; code patterns → category="Detected"; speakers → character glossary entries; non-destructive merge; uses `_get_analysis_step_data()` (ManifestManager first, session fallback)
         - Code Database actions in prompt_builder: Preserve="Do not translate", Provides Context="Translate as" hint, Custom Placeholder/Protect/Strip with Anchor/Part of a Span=default "Do not translate"; legacy migration: translate→provides_context, remove→preserve; action sync via sync_code_pattern_actions() auto-populates ProtectCodePatterns/CustomPlaceholders/AnchorRemoval
         - Code Database multi-select removal with reverse-index batch deletion (Phase 60)
         - Code Database auto-populate: prefers `individual_codes` over grouped `code_patterns` (Phase 60)
         - Knowledge Base widget: unified mode switch (Glossary / Code Database), search/column filter, inline Active toggle, Enabled/Disabled button, mixed-selection Activate/Deactivate failsafe
         - Files: user/globalglossary.tsv (4-col TSV) and user/codedatabase.tsv (10-col TSV) ✅ Phase 62 + TASK 76 complete
         - Selective glossary: active field (bool) in TSV and manifest GlossaryEntries, defaults True
         - **Collapsible right-column widgets:** `_collapsible_state` dict tracks collapse state; `_build_collapsible_labelframe(parent, title, widget_name, row, extra_header_widgets)` helper creates header row (▾/▸ toggle button + bold label + optional extra widgets + horizontal `ttk.Separator`) and collapsible body Frame; `_toggle_collapsible(widget_name)` toggles `grid()`/`grid_remove()` on body frames and swaps button text between "▾"/"▸"; `_reconfigure_right_column_weights()` sets row weight=1 for expanded, weight=0 for collapsed; applies to Glossary (row 0), Code Database (row 1), Knowledge Base (row 2)
         - **Glossary moved to right column:** `_build_character_section()` now builds into `self._right_column` (grid row 0) instead of `self._left_column`; uses grid layout with sticky="nsew" for expansion; Code Database at row 1, Knowledge Base at row 2
         - **Taller tables:** All right-column Treeview widgets use height=8 (up from 4-5); parent frames use `rowconfigure(weight=1)` and `sticky="nsew"`; canvas `<Configure>` binding stretches inner frame to viewport height
         - **Disabled text field styling:** `_apply_widget_enabled_state(widgets, enabled)` static method sets ScrolledText background/foreground to `THEME.bg_disabled`/`THEME.text_disabled` when disabled, white/black when enabled; called by `_toggle_section_enabled()` and `_load_section_toggles()`
         - **Button alignment:** Save, Delete, and Toggle buttons for Style, Tone, and System Instructions use `side="right"` pack (reversed creation order) to right-align, matching Summary section layout
         - **Table column sorting:** Glossary and Code Database default to count descending. All column headings are clickable via `command=` parameter — ascending → descending → third click resets to count. Sort arrows (▲/▼) in heading text. Glossary uses `char_{idx}` tags via `_get_char_idx()` for display-order-independent row-to-data mapping. Manifest saves in count-descending order.
         - **Style/Tone text display:** `_ensure_style_tone_text()` called at end of `on_enter()` populates empty text fields from preset; `_populate_form()` falls back to preset text when metadata style/tone is empty
         - **Style/Tone compact display:** ScrolledText height=1 (down from 3); Delete button width=10 (up from 8)
         - **Summary defaults & restore:** `DEFAULT_SUMMARY_TEXT` constant; height=2; "🔄 Restore Default" button; `_ensure_default_texts()` populates on step entry when empty
         - **System Instructions preset system:** mirrors Style/Tone pattern — `_SI_PRESETS_FILE` in `user/presets/`, `DEFAULT_SI_PRESETS` dict, `_load_si_presets()`, Combobox (Default/Custom/user), Save/Delete buttons, `_on_si_preset_changed()`, `_save_si_preset()`, `_delete_si_preset()` methods; manifest key `SIPreset` for preset name, `Prompt` for text content; `DEFAULT_SYSTEM_INSTRUCTIONS` loaded from `temp/example.txt`
         - **Hint labels removed:** Description labels removed from Summary and System Instructions widgets
         - **Project Name source fix:** `_apply_suggested_project_name()` now prefers manifest `ProjectName` (set during Input step) over step data `suggested_project_name` (folder name)
         - **Style/Tone translation integration:** translate.py `_build_system_prompt_from_manifest()` reads all prompt data from `step_state.Information.data.metadata` via `mgr.get_step_data_value(3, "metadata", {})`; reads `style`, `tone`, `summary`, `custom_notes`, `genre`, `characters`, `source_language`, `target_language`; appends `# Translation Style Guidelines\n...` and `# Translation Tone\n...` to system prompt; also reads glossary entries and characters from metadata
         - **Analysis→Glossary data flow:** `_show_nameable_dialog._apply()` in analysis.py now creates glossary entry with source=replacement_name and notes="Gender: X; Role: Y; custom_notes" when assigning variable codes to characters
       - **Phase 60 Integration:** Confirmation opt-out, File menu fixes, WelcomeDialog update:
         - `gui/helpers/confirmations.py`: confirm_action(), is_suppressed(), suppress(), reset_all_suppressions()
         - INI `[confirmations]` section stores suppressed dialog keys
         - `ini_manager.remove_section()`: removes entire INI section
         - App._on_new_session(): calls tab.on_new_project() on ALL tabs then on_enter() on tab 0 after reset; fully flushes cached state (loaded files, analysis results, lines, etc.) via BaseStep.on_new_project() overrides in each step
         - App._on_load_manifest(): unsaved-changes check (askyesnocancel) before loading
         - App._load_manifest_from_path(): now loads into a fresh ManifestManager first, then swaps it in only after successful load and replays the same runtime reset path as New Project so cached tab state cannot leak into the newly opened project
         - `ini_manager.set_last_manifest(None)`: removes `[session].last_manifest`; startup seeding no longer recreates an empty placeholder key
         - WelcomeDialog: auto-load checkbox always visible, saves on toggle
         - Global Options Session: reset buttons for confirmations and presets
       - **Phase 42 Integration:** Preprocessing & Postprocessing complete implementation:
         - Anchoring Treeview: 5-column (Pattern, Action, Anchor Spec, RegEx, Description), _AnchorDialog, _sync_anchor_tree_to_manifest
         - Custom Placeholders RegEx: _RuleDialog.show_regex param, regex_result attr, checkbox in dialog
         - Protect Code Treeview: 3-column (Pattern, RegEx, Description), dict-based storage in config
         - Aggressive Dedup UI: _aggressive_dedup_var checkbox, set_aggressive_dedup() in dedup.py, wired via mainhelper.py
         - Code spacing manifest: visible/spacing fields in code_glossary, _apply_code_spacing(processor=) reads manifest overrides
         - Preview filtering: _preview_filter_var combobox (7 options), _filter_count_label, filter logic in _update_preview()
         - PostProcess validation: RecoveryType.PLACEHOLDER_POSITION_SHIFT/EXTRA, detect_position_shift(), detect_extra_tokens()
         - PostProcessManager.save_to_manifest(): stores recovery_analysis in manifest.mappings
         - Process order: functions/process_order.py, PRE_PRIORITIES (12 entries), POST_PRIORITIES (15 entries); ellipsis_compression at P36 (after symbol P30 and width P35)
         - New file: functions/process_order.py (get_pre_order, get_post_order)
         - Modified: gui/steps/preprocess.py, gui/state/store.py, functions/dedup.py, functions/mainhelper.py
         - Modified: functions/manifest_fields.py, functions/postprocess.py, modi/standard_mode.py
         - Bug Fix (Task 3): _update_step_data() persists preprocessed lines to manifest `lines[].prepro`; the current implementation uses one bulk pass over loaded manifest lines instead of per-row `get_line()` + `set_line_field()` / `clear_line_field()` calls because that helper path regressed Preprocessing responsiveness on large projects
       - **Phase 43 Integration:** Translation Tab Overhaul:
         - Merged Column: "To be Translated" replaces Original+Preprocessed (resolution: edited_prepro → preprocessed → original)
         - Newline Rendering: ↵ symbol in table cells, 200-char truncation
         - Mock Translation: MODEL_OPTIONS[0] = "Mock Translation", routes to MockTranslator (no delay, cancel_event from _cancel_event)
         - API Provider Management: APIProviderEntry dataclass, PROVIDER_PRESETS (5), "Saved API Keys" Treeview with Save/Load/Remove; _PresetPickerDialog
         - Settings Migration: CachingSettings.mode, RequestSettings.thinking_enabled/budget/reasoning_effort/rolling_context_lines
         - _sync_from_global_options() applies Global Options overrides on tab enter
         - Retry Refinement: RETRY_STRATEGIES (2: Batch+Contextual for UI), ALL_RETRY_STRATEGIES (4 for CLI), min retries=0
         - Prompt Editor: Preview-only button, Ban Tokens LabelFrame with _BAN_PRESETS (None/Clean English/Strict)
         - Shared skip planning: `_collect_translatable_lines()` and `_build_translation_status_text()` reuse `validate_line_pre()` so refresh, Preview Requests, and execution agree on already-translated, placeholder, code-only, symbol-only, and non-source filtering; the grouped header label now uses `non-source`
         - TranslationProgressWindow: non-modal progress dialog with shared API Log button; quick-access Global Options buttons route through the root window so API Log and Global Options stay single-instance
         - Chunk Sync: costs.py reads/writes LinesPerChunk to manifest RequestOptions
         - Language Skip: detect_line_script() in analysis.py, _LANG_SCRIPT_MAP, _apply_language_skip() — strips placeholder tokens (via _PLACEHOLDER_TOKEN_RE) before ratio-based script detection so CJK lines with placeholders are not wrongly classified as 'latin'
         - Tab Caching: BaseStep._compute_cache_hash/_is_cache_valid/_update_cache/_invalidate_cache/_force_refresh; TranslationStep.on_enter() reloads prompt/request/global-option state before cache checks and refreshes table/status on cache hits so stale overwrite_translation values cannot survive a cached tab re-entry
         - New Project Lifecycle: BaseStep.on_new_project() invalidates cache; each step override clears instance-level cached state (_loaded_files, _lines, _analysis_results, etc.) to prevent old project data from leaking into a new session
         - Performance: SharedTable batch insertion (2000-row batches), bulk *children delete, page-based display (5000 rows/page, TASK 72), _refresh_lines() batch manifest dict read
         - TASK 71: Removed redundant all_lines/processed_lines/postprocessed_lines/files from step_data; manifest migration strips on load; new ManifestManager.get_all_orig_lines() API
         - TASK 72: Per-line tags in mode_adapter (tags_by_line dict); preprocessing progress bar; skip unchanged prepro writes; tag-based filter dropdown (12 entries); pagination (5000 rows/page); "Search:" label; show_count_filter=False for 6 step tables; set_line_field skip-unchanged guard; wordwrap/QA on_leave skip unchanged lines
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
         - PostprocessLine: written/flagged bool fields for new filter system; preprocessed str field for dedup source resolution
         - HALFWIDTH_TO_FULLWIDTH: reverse dict comprehension from FULLWIDTH_TO_HALFWIDTH (30 entries)
         - Mutual exclusion: _on_fullwidth_change/_on_halfwidth_change trace callbacks
         - Diff View editing: _edit_text ScrolledText (height=4), _mark_fixed_btn, _mark_line_as_fixed()
         - Summary: _progress_bar (ttk.Progressbar), _written_label, _flagged_label; self.after(0, _update_summary) every 10 lines
         - Overwrite warning: messagebox.askokcancel in _apply_postprocessing()
         - Filters: All/Changed/Written/Flagged radio buttons; status icons ⚠/✓
         - Modified: gui/steps/postprocess.py (~1732 lines)
         - Test file: dev/test_postprocess_phase45.py (49 tests)
         - Bug Fix (Task 3): _mark_line_as_fixed() called nonexistent update_line_field(); fixed to set_line_field(). _on_postprocess_complete() now calls set_line_field(line.idx, "postpro", line.postprocessed) to persist results to manifest.

       - **Phase 46 Integration:**
         - WrapMode enum now exposes CUSTOM and SIMPLE in the GUI; legacy Manual/manual manifest values are mapped to CUSTOM for compatibility
         - WrapTarget enum adds TAGS_FIRST / TAGS_ONLY / FILE_FIRST / FILE_ONLY and persists the selected strategy in `WordwrapSettings.Target`
         - SpeakerMode enum reduced to IGNORE and COUNT (removed SAMELINE, SAMELINEINDENT, NEWLINE)
         - Removed enums: IgnorePattern, OverwriteStrategy, MergeMethod, TypographyStyle
         - Removed dataclasses: OverwriteOptions, TypographyOptions
         - WrapLine dataclass no longer carries the obsolete Step 8 overwrite preview field; unresolved targets stay unchanged instead of falling back to dialogue
         - WrapOptions dataclass: removed ignore_patterns field; hardcoded prevent_orphan/prefer_punct_breaks
         - Mode: ttk.Combobox replacing radio buttons; Custom shows the per-format/per-tag panel while Simple shows the lightweight character-limit panel
         - Speaker: ttk.Combobox with dynamic _speaker_desc_label
         - Ignore patterns: read-only ttk.Treeview from manifest CodeDatabase
         - Width: _width_mode_combo (Character/Pixel) with _char_width_frame and _pixel_width_frame
         - _on_width_mode_changed() toggles between character (20-200) and pixel (100-2000px + font 8-72) frames
         - Target dropdown selects whether wrapping resolves from canonical tags, filedir type, or both in priority order
         - Preview toolbar: compact `Select File:` dropdown reuses `gui/dialogs/table_view.py::_FileFilterDropdown`; `View in File` filters the preview to the selected row's source file
         - Simple mode scope: `_get_process_indices()` restricts Apply to the selected file filter while preserving untouched rows outside that file, and mode changes into Simple do not auto-refresh the preview
         - Filter radios: All/Changed/Exceeding/New Textbox
         - _simple_wrap() sets exceeds_limit from max_lines
         - Modified: gui/steps/wordwrap_overwrite.py (~1200 lines)
         - Test file: dev/test_wordwrap_phase46.py (updated for target strategies and removed overwrite preview)
         - Bug Fix (Task 3): _save_to_session() now calls set_line_field(line.idx, "wordwr", line.wrapped) to persist wrapped lines to manifest. Previously only stored in step_state.

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
         - input_extract._on_import_translations(): selection dialog + per-field and per-section import logic
         - _ImportTranslationDialog: Toplevel with Line Fields and Settings Sections checkbox groups
         - input_extract._import_line_fields() / _import_settings_sections(): thin wrappers that delegate manifest import processing to ManifestManager so Step 0 remains UI-only
         - input_extract._on_create_patch(): UI-only source-manifest picker + summary dialog; refreshes the file tree from manifest state after pruning
         - input_extract._load_selected_paths(): non-destructive file addition with source root validation
         - input_extract._add_files_to_existing_manifest(): builds file_infos/lines, calls mgr.add_files(), copies new originals
         - ManifestManager.add_files(): merges new files into sorted filedir, recomputes contiguous idx, preserves existing line data
         - ManifestManager.import_line_fields_from_manifest_data() / import_settings_sections_from_manifest_data(): shared import logic used by both Import Translations and Create Patch
         - ManifestManager.remove_files(): batch-prunes filedir entries and rewrites remaining `idx` ranges in one pass; optionally deletes copied `Original/` files
         - ManifestManager.find_identical_original_files(): compares shared `Original/rel_path` files by size + SHA-256 hash
         - ManifestManager.create_patch_from_manifest_path(): imports all supported fields/settings from another manifest, prunes identical files first, then prunes fully matched files as a missing-Original fail-safe
         - ManifestManager canonicalizes `lines[]` on load/save/set_lines: merges legacy `tag` into `tags` and writes canonical key order `idx`, `tags`, `orig`, `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, `wordwr`, then auxiliary fields without stripping later-stage fields from dedup placeholder rows
         - output_inject._safe_output_format(): prevents ValueError on empty/invalid OutputFormat string
         - Preview tree headings: "Idx" → "Project", "#" → "File"; display uses 1-based global idx
         - TranslationOptions.skip_already_translated: bool field for skipping translated lines
         - TranslationOptions.api_key_provider / api_key_name: API key selection from API.ini
         - translate._build_request_options(): Key dropdown (row 1), Model (row 2, filtered by provider), Temperature removed from GUI
         - translate._do_translation(): resolves API key from API.ini via api_config.get_api_key_plain(), injects into APIClient.config, reinitialises client
         - translate._populate_key_dropdown(): lists saved keys from api_config.list_api_keys()
         - translate._filter_models_by_provider(): filters model_registry by KEY_PROVIDER_TO_REGISTRY mapping (gemini→google)
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
           - LineInfo dataclass: index, text, is_invalid, tag fields
           - RequestFormationConfig dataclass: max_lines, min_lines, max_tokens, model (max_tokens wired from RequestSettings.max_input_tokens — Task 41)
           - TranslationRequest dataclass: lines, line_indices, context_type, is_split, provides_context, receives_context
         - Shared Functions:
           - is_placeholder_only(text) → bool: strips all placeholder tokens (any ``__TOKEN__`` pattern — ``__PROTECTED__``, ``__COLOR__``, ``__FONT__``, ``__DEDUP__``, ``__CUSTOM__``, ``__TEMPREPL__``, ``__NAME__``, and indexed variants) and returns True only when nothing remains; lines with CJK + placeholder are NOT placeholder-only
           - _PLACEHOLDER_TOKEN_RE: compiled regex ``__[A-Z][A-Z0-9_]*__`` matching any uppercase double-underscore placeholder token (case-insensitive)
         - build_requests(line_infos, config) → shared builder for Estimation + Translation
         - Step 1: _step1_split_menu_choice() → groups consecutive menu/choice lines into dedicated requests (no rolling context)
         - Step 2: _step2_split_at_file_boundaries() → splits at file_end markers, drops marker lines
         - Step 3: _step3_split_and_balance() → splits oversized groups, balances sub-groups evenly, respects max_lines and max_tokens
         - Step 4: _step4_merge_short_requests() → merges below-min same-type requests up to max_lines; menu/choice never merged
         - _extract_valid_lines() → separates valid from invalid (placeholder/dedup/marker) lines
         - _count_tokens_for_lines() → uses analysis.count_tokens for token estimation
         - Callers (Costs _estimate_via_formation, Translation _build_chunks, Preview _build_preview_requests) all import is_placeholder_only for the is_invalid flag — no inline substring checks
         - Results sorted by first line index to maintain document order
         - Modified: functions/prompt_builder.py
         - Test file: dev/test_request_formation.py (50 tests), dev/test_request_building_unification.py (68 tests)

   6.18 Context Markers Full Implementation (Phase 50)
         - Data Model (Task 50.1):
           - LineEntry.tag: Optional[str] field (None, "file_end", "dialogue", "menu", "choice")
           - LineEntry.VALID_TAGS: frozenset of accepted marker types
           - is_tag() → bool: True when line is metadata-only
           - get_tag() → Optional[str]: returns marker type
           - Sparse serialization: manifests store canonical `tags`; legacy `tag` remains runtime/backward-compatibility only
           - from_dict() restores tag semantics from canonical `tags` or legacy `tag`
         - Detection in Analysis (Task 50.2):
           - _is_choice_item(line) → bool: regex for numbered/bulleted choice patterns
           - _is_menu_item(line) → bool: short non-speaker items (≤60 chars)
           - _is_dialogue_line(line) → bool: speaker:dialogue via detect_speaker()
           - detect_tags(lines, min_run=3) → List[Optional[str]]: contiguous run detection
           - get_active_context_type(markers, index) → str: backwards scan for nearest marker
           - Modified: functions/analysis.py
         - Integration with Request Builder (Task 50.3):
           - build_line_infos(entries, detected_markers) → List[LineInfo]: converts LineEntry to LineInfo
           - Context propagation: marker entries → is_invalid=True; subsequent lines inherit active type
           - file_end does not propagate as content type (resets to "unknown")
           - Placeholder-only and empty lines flagged as invalid via is_placeholder_only()
           - build_requests() passes file_end markers to Step 2 for boundary splitting
           - _file_section tracking prevents Step 4 from merging across file boundaries
           - Modified: functions/prompt_builder.py
         - Conditional Prompt Templates (Task 50.4):
           - CONTEXT_PROMPT_DIALOGUE: character voice and emotional nuance instructions
           - CONTEXT_PROMPT_MENU: concise, action-oriented UI translation instructions
           - CONTEXT_PROMPT_CHOICE: distinct option formatting instructions
           - CONTEXT_PROMPT_UNKNOWN: mixed-content adaptive translation instructions
           - _CONTEXT_PROMPT_MAP: Dict[str, str] mapping context types to templates
           - get_context_prompt(context_type) → str: reads INI first via get_conditional_prompt(),
             falls back to _CONTEXT_PROMPT_MAP; templates are user-configurable via Global Options
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

   6.21 Typing Feature
         - File-Level Classification:
           - classify_file_type(lines) → str: uses detect_speaker() with 10% threshold
           - >10% speakers → "dialogue"; ≤10% ≥2 → "menu?"; 0 speakers → "menu"
           - Called during _sync_lines_to_manifest() when typing_enabled INI setting is True
           - Result stored in FileDirEntry.type field (sparse serialization)
           - Modified: functions/analysis.py, gui/steps/input_extract.py
         - Per-Line Tagging:
           - Users set Dialogue/Menu/Choice tags on preview lines via right-click context menu
           - Tags stored in LineEntry.tags field; displayed in Preview tags column
           - Search bar above Preview tree for live filtering
         - Type Resolution at Translation Time:
           - resolve_chunk_type(line_indices, lines, filedir) → str
           - Priority: per-line tags > filedir type > "unknown"
           - Mixed filedir types → "mixed"
           - Modified: functions/analysis.py
         - Prompt Integration:
           - build_full_system_prompt() accepts context_type parameter
           - Context-type prompt injected at slot 7b (static, cacheable)
           - Cache boundary comment between slots 7b and 8
           - Pattern-triggered prompts remain dynamic at slot 8
           - Modified: gui/helpers/prompt_adapter.py, functions/prompt_builder.py
         - GUI Controls:
           - Typing Enabled toggle button in UnifiedInputDialog (gui/dialogs/input_dialog.py)
           - Sort combobox (Filetree / Count / Type) above Loaded Files tree
           - Type column in file tree; Select Type cascade in file context menu
           - INI setting: [session] typing_enabled (bool, default True)
         - Test file: dev/test_typing_feature.py (24 tests)

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
├── requirements.txt         Dependencies (openpyxl>=3.0.0, bcrypt, cryptography)
│
├── user/                    User data directory (excluded from version control)
│   ├── CherryAI.ini         Main config (UI state, presets, defaults, recent manifests; all non-meta prompt content)
│   ├── API.ini              All API meta settings: encrypted keys + provider/model/temperature/URL profiles
│   ├── globalglossary.tsv   Global character/term glossary — Original, Translation, Notes (3 columns; Session 26: renamed/reformatted from GlobalGlossary.csv)
│   ├── codedatabase.tsv     Global code pattern database — Pattern, Type, RegEx, Notes, Visibility, extended props (Session 26: replaces codeglossary.db SQLite)
│   └── presets/             System instructions JSON presets
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
│   │   ├── global_options.py GlobalOptionsDialog (12 sections incl. Security, Utility, Add-ons)
│   │   └── password_dialog.py SetPasswordDialog, ChangePasswordDialog, VerifyPasswordDialog
│   ├── widgets/            Reusable standalone widgets [NEW 2026]
│   │   ├── __init__.py
│   │   └── password_strength.py PasswordStrengthWidget (real-time HiveSystems strength meter)
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
│   │   ├── wordwrap_overwrite.py WordwrapOverwriteStep (step 8)
│   │   ├── qa.py           QAStep (step 7, moved from Step 6)
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
│   ├── glossary.py         Unified glossary (globalglossary.tsv path + auto-migration; codedatabase.tsv path)
│   ├── languages.py        Language definitions (single source of truth) - TASK 16.1
│   ├── API2Glossary.py     Optional LLM-based gender inference
│   ├── dedup.py            Deduplication logic
│   ├── config.py           Config persistence (Session 4)
│   ├── options.py          Options dialog + API_PROVIDERS (single source) - TASK 16.2
│   ├── dependencies.py     Dependency management (Session 4)
│   ├── api_client.py       API Client for LLM communication (Session 12)
│   ├── api_config.py       Encrypted API config manager [NEW 2026]
│   │                           bcrypt WF-10 + PBKDF2-SHA256 + Fernet AES-256
│   │                           PasswordStrength class (HiveSystems 2025 tiers)
│   │                           See doc/passwords.md
│   ├── api_log.py          Structured API log store with per-project persistence [NEW 2026]
│   │                           LogCategory, LogStatus, LogEntrySent, LogEntryReceived, LogEntry
│   │                           APILogStore: entries, subscribe/unsubscribe, filtering, JSONL save/load
│   ├── mock_translator.py  Mock translation engine with flaw injection (Phase 56)
│   ├── validation.py       Pre/Post API validation (Session 13)
│   ├── prompt_builder.py   Dynamic prompt construction with game summary
│   ├── project_config.py   Project-level configuration (game summary, API profiles)
│   ├── rate_limiter.py     Sliding-window rate limiter
│   ├── header_rate_limiter.py  Header-based rate limiter (per-model, response-header driven) [NEW]
│   ├── romanization.py     Japanese kana → rōmaji (Modified Hepburn, Task 75)
│   ├── term_translation.py Unified term translation dispatcher (Romaji/LLM)
│   ├── wordwrap.py         Text analysis and wordwrap
│   ├── postanalysis.py     Post-processing analysis
│   ├── glossaries/         Glossary detection modules
│   │   ├── __init__.py
│   │   ├── name_glossary_constants.py   Speaker patterns and romanization
│   │   ├── name_glossary_functions.py   Speaker detection and gender inference
│   │   ├── code_glossary_constants.py   Code pattern definitions
│   │   ├── code_glossary_functions.py   Code detection/classification (uses SQLite)
│   │   └── code_glossary_db.py          SQLite persistence layer [NEW 2026]
│   │                                        init_db(), read_all_rows(), write_all_rows()
│   │                                        upsert_rows(), delete_row(); WAL mode
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

v3.2 optimizes manifest size and privacy by:
1. Storing `source_root` as a display-only **folder name** (not a full path)
2. Removing `source_files` array, `source_file` from lines, `source_hint` from filedir
3. File resolution uses the project’s `Original/` directory instead of absolute source paths

**Size Reduction:** For a project with 50,000 lines and a 60-character path prefix,
this saves ~4MB (60 chars × 50,000 lines + JSON overhead).

```json
{
    "version": "3.2",
    "source_root": "Data",
    "filedir": [
        {"first_idx": 0, "last_idx": 99, "format": "txt", "rel_path": "chapter1.txt"},
        {"first_idx": 100, "last_idx": 249, "format": "csv", "rel_path": "data/items.csv", "encoding": "shift_jis"}
    ],
    "step_state": {
        "Input": {"name": "Input", "status": "completed"},
        "Analysis": {"name": "Analysis", "status": "completed"},
        "Information": {
            "name": "Information",
            "status": "completed",
            "data": {
                "metadata": {
                    "project_name": "My Game Translation",
                    "source_language": "Japanese",
                    "target_language": "English",
                    "genre": "Visual Novel",
                    "summary": "",
                    "style_preset": "Natural",
                    "custom_style": "",
                    "tone_preset": "Dramatic",
                    "custom_tone": "",
                    "custom_notes": "Maintain character speech patterns"
                }
            }
        }
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

**Path Resolution:** Files are resolved against the project's `Original/` directory:
```python
# v3.2: resolve via project-local copy (source_root is display-only)
full_path = mgr.get_original_dir() / entry["rel_path"]

# Example: Projects/MyGame/Original/ + "chapter1.txt"
#       -> Projects/MyGame/Original/chapter1.txt
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
2. Resolves files from `Original/` directory (project-local copies)
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
    type: str = ""        # Content type (dialogue, menu, menu?, ""); set by classify_file_type()
    
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
    
    def get_all_orig_lines(self) -> List[str]:
        """Return lines[].orig as flat list (TASK 71 replacement for all_lines)."""
    
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
        """Get QA options (RerunPolicy, MaxSourceLanguageChars, etc.)."""
    
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
    
    def get_wordwrap_tag_configs(self) -> List[Dict]:
        """Get per-tag wordwrap configs from WordwrapSettings.TagConfigs."""
    
    def set_wordwrap_tag_configs(self, configs: List[Dict]) -> None:
        """Replace TagConfigs list in WordwrapSettings, marks dirty."""

    def get_wordwrap_format_configs(self) -> List[Dict]:
      """Get per-format wordwrap configs from WordwrapSettings.FormatConfigs."""

    def set_wordwrap_format_configs(self, configs: List[Dict]) -> None:
      """Replace FormatConfigs list in WordwrapSettings, marks dirty."""
    
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
    
    def copy_originals_to_project(self, source_paths=None, force: bool = False) -> Dict[str, str]:
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
        
      Resolution: tl → prepro → orig.
        
      Returns: Best available pre-postprocessing text
        """
        if self.tl is not None:
            return self.tl
        if self.prepro is not None:
            return self.prepro
        return self.orig
    
    def get_input_for_wordwrap(self) -> str:
        """Input for Wordwrap operation.
        
      Resolution: qa → postpro → tl → prepro → orig.
        """
        return self.postpro if self.postpro is not None else self.get_input_for_postprocessing()
    
    def get_final_output(self) -> str:
        """Output for final export.
        
        This is the ONLY case where "rightmost available" logic applies.
        
        Returns: final → wordwr → qa → postpro → tl → prepro → orig (first available)
        Raises: ValueError if no output available
        """
        if self.wordwr is not None:
          return self.wordwr
        if self.qa_overwrite is not None:
          return self.qa_overwrite
        if self.qa is not None:
          return self.qa
        if self.overwrite is not None:
          return self.overwrite
        if self.postpro is not None:
          return self.postpro
        raise ValueError(f"Line {self.idx} has no final output (postpro/qa/qa_overwrite/wordwr/overwrite)")
    
    def has_final_output(self) -> bool:
        """Check if any final output field is populated."""
        return any(field is not None for field in (self.wordwr, self.qa_overwrite, self.qa, self.overwrite, self.postpro))
    
    def get_populated_fields(self) -> List[str]:
        """List of populated text fields (excludes metadata fields).
        
        Excludes: log, prepro_ops, deleted, updated
        Returns: List of field names that have values
        """
        text_fields = ['orig', 'prepro', 'tl', 'postpro', 'qa', 'qa_overwrite', 'wordwr', 'overwrite']
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

Pipeline (Pre-TL) — lower priority number runs first:
1. Deduplication (P10, runs first)
2. Protect Code Patterns (P15, before symbol conversion so fullwidth chars match)
3. Custom Placeholders (P17, before symbol conversion to capture originals)
4. Anchoring / Remove and Restore at Anchor (P20, before symbol conversion)
5. Symbol Conversion (P30, JP→EN symbols)
6. Width Conversion (P35)
7. Ellipsis Compression (P36, after symbol/width conversion)
8. Speaker Name Replacement (P38)
9. Code Spacing (P50)
10. PROTECTED Token Compression (P60, after all __PROTECTED__ tokens exist)
11. Quote Stripping (P76)
12. Aggressive Deduplication (P90, runs last)

Pipeline (Post-TL) — Phase 1: preprocessing reversal, Phase 2: post-exclusive LLM recovery:
Phase 1 reversal (MUST run before LLM recovery to avoid token corruption):
1. PROT Token Decompression (P40) — __PROTECTED_N__ → N × __PROTECTED__
2. Protect Code Restoration (P20) — __PROTECTED__ → captured originals
3. Custom Placeholder Restoration (P30) — tokens → captured originals
4. Ellipsis Expansion (P80) — ... → original length using stored counts
5. Anchoring Restoration (P10) — re-insert anchors using anchor-relative records (rfind with symbol-conversion equivalents); patterns only removed during preprocessing when adjacent to a valid anchor character
6. <NUM> Restoration — replace <NUM> tokens with original numbers from aggr_numbers
Phase 2: recover_line(enable_placeholder_recovery=False) — bracket/quote balance (anchor-relative with ANCHOR_EQUIVS equivalence), whitespace normalization on restored text
7. Symbol Conversion (P70, optional reverse)
After all lines:
8. Deduplication Restoration (P90) — recursively resolve source text through chained `dedup_map` / `aggr_dedup_map` links using `postpro → tl → prepro → orig`
9. Aggressive Dedup Restoration (P5) — restore numbers from per-line data, including sources reached through chained dedup resolution

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

Parser Handshake (formats/handshake.py):
- Formal contract definition for all parsers (mandatory M1-M3, optional O1-O10)
- `SpeakerInfo(name, line_idx)`: Speaker detected by parser
- `ExtractedLine(text, tag, speaker, context)`: Tagged extraction result
- `ParserError(message, parser_name, component)`: Mandatory component failure
- `validate_parser(parser) → list[str]`: Check parser satisfies M1-M3
- **O9 Injection Rewrite Hook:** `rewrite_injected_content(source_path, original_content, injected_content, *, search_keys, translated_lines, orig_lines=None, tagged_lines=None) → Optional[str]` — optional post-injection structural rewrite pass for parser-specific code edits that must happen after normal replacement
- **O10 Pretty Wrap Hook:** `pretty_wrap(text, width, break_char, max_lines) → Optional[str]` — lighter
  core-wrap replacement; replaces built-in `pretty_wrap` while keeping speaker handling intact
- **Handler Retrofit (P4):** All registered FormatHandlers verified via `validate_parser()`.
  RPG Maker stubs (`formats/rpgmaker.py`) raise `ParserError` with `parser_name` and `component`
  metadata instead of silent `logging.warning()` + empty returns.

Parser Input Routing (gui/steps/input_extract.py):
- `list_parser_names() → List[str]`: Returns display names from ParserRegistry
- Dynamic format combobox: Parser names appended to base format values in input dialog
- `_extract_lines()`: Routes to `parser.extract()` when format_id is a parser name
- `_load_file()`: Resolves parser/format before encoding; auto-detects parser via `detect_parser()` for format="auto" and, when a parser format is explicitly forced, uses that parser's `detect_encoding()` before generic fallback
- `_file_matches_format()`: Delegates to `parser.can_handle()` for parser format IDs
- `_collect_files_for_format()`: Collects files via `can_handle()` for parser filters
- `_validate_parser_selection(format_id)`: Runs `validate_parser()`, error popup if fails
- `_validate_extracted_lines(lines, filename)`: Per-line token check (>2048 error, >1024 warning)
- `_estimate_tokens(text)`: Static — tiktoken with `len(text) * 0.3` fallback
- `_detect_encoding(path)`: 8 KB probe: BOM → parser `detect_encoding()` → utf-8 → shift_jis → cp932 → latin-1
- `_sync_output_defaults_to_manifest()`: Seeds manifest `OutputFormat` with Destination=`Same as Source`, the loaded input Format/Encoding, PairMode=`custom`, FileNaming=`subfolder`, OverwriteExistingFiles=True, Backup=`timestamp`, BackupExtension=`.bk`, and all export extras off when those values are missing or invalid

Pipeline Wiring of Optional Components (P3):
- `_wire_parser_optionals(format_id)`: Post-extraction hook in `_load_selected_paths` between
  `_ensure_project_created` and `_save_manifest_after_file_load`. Writes manifest Options:
  - `ParserName` — stores active parser identifier
  - `ParserHandlesSpeakers` (bool) — O4: calls `parser.detect_speakers()`, writes to `characters[]`
  - `ParserHandlesWordwrap` (bool) — O6: detected via `type(parser).wordwrap is not ParserScript.wordwrap`
  - `has_custom_pretty_wrap` (bool) — O10: detected via `type(parser).pretty_wrap is not ParserScript.pretty_wrap`
  - `has_injection_rewrite` (bool) — O9: detected via `type(parser).rewrite_injected_content is not ParserScript.rewrite_injected_content`
  - `ParserForbiddenChars` (dict) — O7: `forbidden_chars.to_dict()` serialised to manifest
  - `ParserHandlesContextMarkers` (bool) — O8: compiled rules applied to lines, tags written
- `gui/steps/analysis.py` `_perform_analysis()`: Reads `ParserHandlesSpeakers` flag; always runs
  speaker detection via `analyze_lines(include_speakers=True)`, then uses parser-detected speaker
  names from `characters[]` as an allowlist to filter false positives from regex-based detection
- `gui/steps/wordwrap_overwrite.py` `_process_wrap()`: Reads per-tag `TagWrapConfig` settings
  (enabled, width, break_char, max_lines, speaker_handling, pretty_wrap) inside the selected
  manifest-driven `FormatConfig`, then delegates to `apply_wordwrap()` over the already loaded
  preview rows (`self._lines`), so Apply/Refresh operate on the same stage-bounded input shown in
  the table. `_build_line_format_map()` resolves each line to its `filedir[].format` and rel_path,
  preview filtering stays scoped to the selected format, and Apply skips disabled formats or tags.
  Parser defaults still seed configs via `_apply_parser_wordwrap_defaults()`, but settings remain
  editable. Per-tag processing via `_build_tag_maps()`: resolves canonical line `tags` primary
  content tag → filedir type → "dialogue" fallback. `max_lines` is treated as an exceed/overflow
  check in Step 8 rather than destructive truncation so parser-side textbox splitting can still
  realize the full wrapped result during output. Speaker mode `ignore` preserves the speaker prefix
  in `wordwr` while excluding it from width calculations. Literal non-RPG break commands such as
  `\n` are converted into explicit wrap boundaries, and new-textbox-capable tags can write their
  separator string directly into `wordwr` via `apply_new_textbox_injection()`. Overflow without
  textbox support is previewed as `Exceeding` but cleared from manifest `wordwr`; overflow with
  textbox support is previewed as `New Textbox` and persisted. `_get_ignore_codes()` now combines
  the legacy built-in invisible span families with manifest `code_patterns[]` entries marked
  `IsInvisible`, and Apply reports determinate progress through a worker-thread queue while both
  wrapping and sparse manifest writes stay off the UI thread.
- `gui/steps/output_inject.py` `_write_file()`: Detects parser format from `filedir[].format`; when a
  parser is found via `get_parser_registry().get(format)`, slices per-file lines using
  `all_lines[entry.first_idx:entry.last_idx + 1]` and calls `parser.inject_to(source, output, lines)`
  for surgical injection that preserves script structure. Falls back to standard format writers when
  no parser matches or when inject_to raises an exception.
- `gui/steps/translate.py`: After logit bias setup, reads `ParserName`, calls
  `api_client.apply_parser_forbidden_chars(parser_name)` to merge O7 into logit bias
- `functions/analysis.py` `detect_tags()`: Accepts optional `parser_rules` kwarg
  (compiled regex dict from `TagRules.compiled()`); when provided, uses parser patterns
  instead of built-in heuristics (`_is_choice_item`, `_is_dialogue_line`, `_is_menu_item`)

Light VN Parser (formats/LightVN.py):
- `LightVNParser(ParserScript)`: Full Light VN visual novel script parser
- **No deduplication**: Every occurrence is returned including duplicates; CherryAI's manifest
  stores per-line entries so dedup is handled by the Preprocessing step if enabled
- **M1 Extract**: `extract(path)` → flat list; `extract_tagged(path)` → `List[ExtractedLine]`
- **M2 Inject**: `inject(path, lines)` — writes to `{stem}_translated.txt` (delegates to `inject_to`); `inject_to(source, output, lines)` — surgical injection reading from source, writing to output
- **M3 Identity**: `can_handle()` scans the entire file for `_DETECT_PATTERNS` (`~【`, `~栞`, `~文字`, `~ボタン`, `~絵`, `~効果音`, `~選択`, `~スクリプト`, `~保存変数`, `~臨時全域変数`) plus `_DETECT_LINE_PREFIXES` (`栞 `, `スクリプト `, `保存変数 `, `臨時全域変数 `) so script/config-style LightVN files do not fall back to plain txt
- **Tag propagation**: `LoadedFile.tags` stores per-line tags from `extract_tagged()`; `_sync_lines_to_manifest()` merges them into the manifest's canonical `tags` field; O8 regex pass skips pre-tagged lines
- **O3 Encoding**: Priority chain: utf-8, utf-8-sig, shift_jis, cp932, euc-jp, utf-16; this path is now used both for auto-detected LightVN files and for explicit `lightvn` input selection when Encoding remains `auto`
- **O4 Speakers**: `detect_speakers()` parses `Speaker: text` format from extracted lines
- **O5 Wordwrap**: 60 chars, 3 lines per textbox, explicit separator `\w` + newline + `"`
- **O6 Custom Wrap**: LightVN exposes parser wordwrap defaults for dialogue (60 chars, 3 lines, explicit separator `\w` + newline + `"`) while CherryAI currently keeps Step 8 on the shared `apply_wordwrap()` path
- **Textbox realization**: Explicit multiline wrapped dialogue is preserved during injection; when wrapped dialogue exceeds one textbox, `_wrap_for_textbox()` chunks the logical lines into successive 3-line boxes and `_inject_dialogue_block()` emits them with exact LightVN ordering (`...\w` + newline + next opening `"`). If Step 8 already stored that separator string inside `wordwr`, `_format_prewrapped_dialogue()` preserves it while parser injection restores exactly one final terminal `\w`, including conditional-dialogue output.
- **O9 Injection Rewrite Hook**: LightVN now overrides `rewrite_injected_content()` to safely separate display text from hardcoded machine keys in the equipment UI. The hook inserts a translated surrogate variable (`防具_選択中部位表示`) after `防具_選択中部位` assignments and rewrites visible menu strings to use that surrogate while leaving jumps, asset paths, and dynamic variable names on the original machine keys.
- **O10 Pretty Wrap Hook**: `pretty_wrap()` delegates to `_pretty_wrap()` as LightVN's balanced wrap helper; explicit wrapped lines supplied by Step 8 are preserved rather than rebalanced away during injection
- **O7 Forbidden**: Tab and carriage return characters
- **O8 Context**: Patterns for dialogue (`^"`), menu (`~?文字`), choice (`~選択`)
- **Tags**: `dialogue` (with speaker), `menu`, `variable`, `items`
- **Variable classification**: Shared variable-name classification distinguishes normal translatable assignments from item-like assignments; names such as `剥ぎ取り素材1` and `獲得食材` are tagged as `items`, including when preceded by conditional `もし (...)` prefixes
- **Project-scoped variable safety**: For quoted `保存変数` / `臨時全域変数` assignments outside the built-in allowlists, LightVN now builds a project-level usage index from the active `Original/` tree and only treats a variable as translatable when its interpolations are display-only. Interpolations inside `文字*`, `文字窓`, `~文字`, or dialogue segments mark the variable as display text; interpolations in non-display commands (image/audio/script paths, etc.) or bare references inside `もし (...)` mark it unsafe. This keeps display-only variables such as `bt_勝利条件` translatable while excluding mixed-use values such as `胎児` and control variables such as `付与対象`.
- **Targeted exact-variable path**: A dedicated exact-name whitelist now handles visible string literals tied to specific gameplay/UI variables such as `主人公`, `ev_メイン`, `ev_メイン内容`, `子宮状態`, `開発_初めての相手`, `防具_選択中部位`, the `武器*` name/effect fields, `設定_出産設定説明文`, `スキル名`, `スキル効果`, `敵次スキル名`, `敵発動スキル`, `bat_ヒロイン次スキル名`, plus targeted loot/material names such as `剥ぎ取り素材1`-`剥ぎ取り素材3`, `獲得食材`, `調合素材`, `道具効果`, and `道具名`. The helper now returns the final tag itself, so targeted item-style assignments still surface as `items` while the rest stay `variable`. The targeted filter also keeps parity with the broader assignment parser on padded placeholder literals such as `"{{道具_馬名前}}  "` for `開発_初めての相手`, skips file-like literals such as `.txt`, and keeps those same names out of the generic project-scoped classifier so they are not extracted twice.
- **Hardcoded equipment display safety**: For `dev/scripts/PYUpgrade/scripts/e_armor.txt`, hardcoded equipment part keys such as `頭`, `胴`, `腕`, `顔`, `胸`, and `腹` are now extracted as normal rows, but direct menu/targeted injection leaves their machine-key occurrences untouched. The rewrite hook consumes those translations to build a display-only surrogate variable for visible UI strings, preventing the earlier breakage where translated part names corrupted control flow and asset lookup.
- **Uni16 overlap result**: On the verified `Projects/Uni16/Original` corpus, the broad project-scoped helper no longer extracts any quoted variable assignments after the whitelist expansion, but the generic path is still retained for other projects because it remains the only safe route for display-only variables outside the exact-name list.
- **Quoted-parenthesis preservation**: `_remove_parenthetical_content()` now ignores ASCII parentheses while inside quoted menu strings, which fixes labels such as `回復薬(粗悪品)` that previously extracted as `回復薬` and then failed to inject.
- **Staged-sync contract**: Because that variable classification depends on the active `Original/` tree, Step 0 now stages parser-backed files first and re-extracts them from `Original/` before committing `lines[]` / `filedir`. Without this, the same LightVN file can produce different extracted key counts at load time versus inject time and trigger cascading Output verification mismatches.
- **Output routing split**: Step 9 now has two parser injection paths again: explicit `OutputFormat.INJECTION` uses `_write_injection()` with manifest `orig` verification and `orig_lines`, while direct parser format IDs such as `lightvn` keep the older `first_idx:last_idx+1` slicing route and call `parser.inject_to(source, output, file_lines)` directly.
- **Bookmark semantics**: `~栞 ...` lines are treated as bookmarks/interaction anchors, not speaker tags; they clear the carried `~【Speaker】` state before later dialogue extraction so prior speakers cannot leak into unrelated map text
- **Placeholder filtering**: Editor scaffolding lines such as `ここにテキストを入力` / `Enter your text here.` are skipped during extraction and therefore never enter the translation pipeline
- **Code recovery**: Balanced bracket matching for 10 bracket types, angle bracket safety
- **Conditional handling**: `~もし (condition)` prefix stripped for keys, preserved on injection
- **Verified**: 55604 total / 50212 unique from 1056 files, 843 unique speakers

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
- **Local LLM Support**: Automatic provider detection and response format adaptation
  - `LOCAL_PROVIDERS = ("local", "lmstudio", "ollama")` — class constant
  - `is_local_provider()` — checks provider name against `LOCAL_PROVIDERS` and falls back to `local_llm.is_local_url()` for URL-based detection
  - `_init_client()` — auto-detects local providers; uses placeholder key `"lm-studio"` when no API key is configured
  - `_translate_chunk()` — uses `json_schema` response format for local providers (LM Studio rejects `json_object` with HTTP 400); cloud providers continue using `json_object`. Uses the caller's `system_prompt` as the primary prompt and appends `# Output Format` with JSON structure instructions. Falls back to a minimal default prompt only when `system_prompt` is not provided.
  - JSON schema enforces `{"translations": ["...", "..."]}` structure with `strict: True` and `additionalProperties: False`
- **Prompt Caching (OpenAI)**: Automatic prompt prefix caching for gpt-4o+ models
  - `PROMPT_CACHE_MODEL_PREFIXES` — tuple of model prefixes supporting prompt caching
  - `EXTENDED_CACHE_MODEL_PREFIXES` — tuple of model prefixes supporting 24h extended retention
  - `resolve_prompt_cache_key(explicit_key, project_name, created_at)` — returns configured key or auto-generated manifest-derived key
  - `build_prompt_cache_params(...)` — shared helper used by translation + Preview Requests to compute the effective OpenAI cache request metadata
  - `supports_prompt_caching()` — checks model/provider compatibility (OpenAI only, Gemini excluded)
  - `supports_extended_cache_retention()` — checks for 24h retention support
  - `set_prompt_cache_context(project_name, created_at)` — stores manifest context on `APIClient` so auto-generated keys match the current project
  - `get_prompt_cache_params()` — returns the effective `prompt_cache_retention` and optional `prompt_cache_key` for live requests; safe on spec-mocked clients via `getattr()` fallback for unset manifest context
  - `_total_cached_tokens` — running counter of cached prompt tokens from `usage.prompt_tokens_details.cached_tokens`
  - `_total_reasoning_tokens` — running counter of reasoning tokens from `usage.completion_tokens_details.reasoning_tokens`
  - Completion token breakdown: `reasoning_tokens`, `accepted_prediction_tokens`, `rejected_prediction_tokens` extracted from `completion_tokens_details` and logged per-chunk + footer
  - APIConfig fields: `prompt_cache_enabled` (bool, default True), `prompt_cache_retention` (str, "" / "in_memory" / "24h"), `prompt_cache_key` (str, routing hint for cache slot affinity), `request_mode` (str, "normal" / "batch" / "flex" / "priority" — set from translation step mode selector)
  - `generate_prompt_cache_key(project_name, created_at)` — builds key as `"{first 5 alpha chars}-{seconds}"` from manifest metadata
  - `check_static_prompt_cache_status(token_breakdown)` — evaluates static prefix size: "ok" (≥1280 tokens), "suggest" (1024-1279), "warn" (<1024); uses `_STATIC_PROMPT_SECTIONS` frozenset for section classification
  - Request propagation: `_translate_chunk()` and `_translate_single_line()` both merge the effective prompt cache params into the OpenAI request metadata and mirror them into plain-text logs + structured API log `LogEntrySent.extra`
  - Preview propagation: `PreviewRequest.request_params` carries the same effective cache params into Pure JSON output, while `_build_preview_requests()` appends them to the Meta block for visual inspection
  - Logging: per-chunk cached token count, cache hit rate %, savings estimate in footer, CSV summary column
- **Thinking/Reasoning Mode**: Provider-based thinking parameter generation
  - `THINKING_MODELS` — list of model patterns supporting thinking/reasoning (Claude, o-series, GPT-4.1, GPT-5)
  - `get_thinking_params()` — uses provider's `ThinkingConfig.build_params()` when available; falls back to legacy hardcoded logic
  - Provider path: mandatory models (GPT-5) always send params regardless of `thinking_enabled`; optional models (GPT-4.1) respect the toggle
  - OpenAI models: `reasoning_effort` as top-level Chat Completions parameter (not nested `reasoning: {effort}`)
  - Claude models: `thinking` dict via `extra_body` for OpenAI SDK compatibility
  - `is_openai_reasoning_model()` — includes o-series, GPT-4.1, GPT-5 families
  - APIConfig fields: `thinking_enabled`, `thinking_budget`, `reasoning_effort` (str, "low"/"medium"/"high")

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

Structured API Log (NEW - 2026):
- Separate from the text-based file logging above; provides machine-readable log for GUI display
- Module: `functions/api_log.py`
- `LogCategory(str, Enum)`: MAIN_TRANSLATION, TERM_TRANSLATION, GENDER_INFERENCE, OTHER
- `LogStatus(str, Enum)`: SUCCESS (green), RECOVERED (yellow), FAILED (red), PENDING (awaiting response)
- `LogEntrySent`: model, provider, temperature, system_prompt (full, not truncated), user_content, chunk_index, total_chunks, line_count, extra
- `LogEntrySent.extra` is also used for sent-only request metadata that is not part of the prompt text itself, including OpenAI `prompt_cache_key` / `prompt_cache_retention` when present
- `LogEntryReceived`: content, prompt_tokens, completion_tokens, total_tokens, cached_tokens, reasoning_tokens, finish_reason, error_message, duration_ms, extra
- `LogEntry`: entry_id (int), timestamp, category, status, attempt, max_attempts, sent, received; to_dict() / from_dict()
- `APILogStore`: singleton per project, entries list, subscribe/unsubscribe, log_sent/log_received/log_pair, get_filtered(category, status, search_text, view_mode), save/load (JSON lines format), clear
- Persistence: `.api_log.jsonl` file alongside manifest, atomic writes (write .tmp → fsync → os.replace)
- Manifest integration: `"log"` key in manifest with log filename; reset/load on create_new/load, save on manifest save, save+clear on close
- Hooked into: api_client._translate_chunk (success), api_client._translate_single_line (success+failure), term_translation._translate_llm_batch (success+failure), API2Glossary._call_api_for_excerpt_custom (success), api_config.test_api_connection (success+failure), api_config.test_model_translation (success+failure)
- Structured log producers pass full prompt/content text to `LogEntrySent` / `LogEntryReceived`; viewer limits are applied only at render time, never during storage
- GUI: `gui/dialogs/api_log_view.py` — non-blocking Toplevel, subscribes for live updates, search/filter/view mode controls, and keeps a persistent per-block display-limit preference

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
- Presets defined in [api_presets] section of **user/API.ini** (moved from CherryAI.ini in 2026)
- Format: "base_url|model|temperature|timeout|rate_limit"
- Default presets: gemini_free, gemini_pro, gpt4, gpt4_turbo, local
- Keeps API key separate (presets only change model settings)
- **NOTE (2026):** The old [api_presets] section in CherryAI.ini has been removed.
  Presets and encrypted API keys now live exclusively in user/API.ini.
  See functions/api_config.py for the encrypted configuration manager.

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
   - Preserves all `__PROTECTED__`, `__DEDUP__`, `__CUSTOM__` placeholders
   - Preserves speaker:dialogue format (speaker names kept intact)
   - Preserves anchor characters (`[]{}()<>「」『』【】`) via tokenization
   - Deterministic output via seed-based `random.Random`

2. DELIBERATE FLAW INJECTION (Phase 56):
   - Placeholder malformation: removes/adds chars in `__PROTECTED__` tokens
   - Anchor manipulation: removes existing anchors, inserts random ones
   - Code intrusion: replaces content inside code patterns (`[font]`, etc.)
   - Character surgery: random character insertion/deletion

3. FLAW REPORTING:
   - FlawReport tracks every injected flaw with before/after state
   - Enables test assertions that know exactly what was broken
   - Reports: total_lines, flawed_lines, per-type counters, details list

4. CANCELLATION SUPPORT:
   - Optional `cancel_event: threading.Event` parameter on constructor and factory
   - `translate_batch()` checks event between lines; early-exits with empty padding
   - GUI translate step passes `_cancel_event` so Cancel button stops mock processing

5. SPEED:
   - No artificial delay (default `delay_per_chunk=0.0`)
   - 1000 lines in < 100 ms without delay
   - GUI table updates throttled to 150 ms minimum interval via `_schedule_table_update()`

Factory Function:
- `create_mock_translator(enable_flaws, intensity, seed, delay, context_type, cancel_event)`
  Convenience factory for creating configured MockTranslator instances.

Integration:
- Called from `api_client.py._mock_translate()` when `model == "mock"`
- GUI route in `gui/steps/translate.py._do_translation()` when model is "Mock Translation"
- No external dependencies — uses only stdlib (random, re, time, logging, threading)

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
- API keys stored ONLY in **user/API.ini** (encrypted via functions/api_config.py) [updated 2026]
- Legacy storage in CherryAI.ini [api] section has been removed — non-secret settings remain
- Manifest stores profile NAME, never the key
- Safe to share manifests with team
- See doc/passwords.md for the full bcrypt + AES-256 encryption system

Dependencies:
- Stdlib: configparser, dataclasses, pathlib, logging

=============================================================================

PROMPT BUILDER (functions/prompt_builder.py)

Purpose: Constructs dynamic system prompts with game context, glossary, translation style, and conditional instructions.

Classes:
- RequestBatch: Dataclass holding lines, indices, context, and prompt for a single API request.
- RollingContextConfig: Dataclass for rolling context settings (enabled, lines_before, lines_between, lines_after, scene_markers, use_translated).
- PromptBuilder: Main class for generating prompts with project context.
- ConditionalPromptManager: Pattern-triggered instruction injection.
- RequestFormationConfig: 4+1 step formation settings (max_lines, min_lines, max_tokens, model, efficient_merge, rolling_context_between, rolling_context_after).
- TranslationRequest: Request produced by `build_requests()` with `_merge_boundaries` and `is_merged` for Step 5 efficient merge.
- `is_code_pattern_only(text, preserve_patterns)`: Returns True when text consists entirely of preserved code patterns (`<NUM>` wildcard → `\d+`); used as CODE_ONLY skip condition in both Estimation and Translation.

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
- Rolling Context: Prepares slots for preceding, interspersed, and following lines (original or translated) to maintain coherence (TASK 7, extended TASK 78).
- Between/After Context: Collects skipped lines within chunk range and already-translated lines following the chunk (TASK 78).
- Scene Marker Detection: Resets rolling context at scene breaks.
- Token Estimation: Provides estimates for prompt + content size.
- Conditional Prompts: Pattern-detected instructions for token handling.
- Empty Section Skipping: Skips game summary if placeholder text detected (TASK 12)

Prompt Construction Order (Phase 62 — 10-slot design):
1. Language direction header: "# Language\nTranslate from {source} to {target}."
2. System Instructions (from `metadata.custom_notes` or preset)
3. Style (from `metadata.style`; prefixed "# Translation Style Guidelines")
4. Tone (from `metadata.tone`; prefixed "# Translation Tone")
5. Summary (from `metadata.summary`; prefixed "# Game Context")
6. Genre (from `metadata.genre` or top-level `Genre`; prefixed "# Genre")
7. Conditional block (merged): context-type instructions + POV + pattern-triggered prompts
8. Glossary (selective: manifest entries + characters from `metadata.characters` with gender)
9. Rolling Context (preceding translated lines, prefixed "# Rolling Context")
10. Output Format (JSON structure instructions — appended by `api_client._translate_chunk()`)
Note: All metadata keys read from `step_state.Information.data.metadata` via `mgr.get_step_data_value(3, "metadata", {})`.
Note: Output examples removed from system prompt in Phase 62.

Previous order (before TASK 12):
1. Base prompt template (embedded in _DEFAULT_PROMPT_TEMPLATE constant, prompt_builder.py)
2. Additional Instructions (prompt.txt)
3. Game summary with metadata
4. Translation style preferences
5. Glossary terms
6. Character list
7. Conditional instructions

Modular Prompt Files (TASK 12 - NEW):
- Base instructions: Embedded in _DEFAULT_PROMPT_TEMPLATE (prompt_builder.py, Session 25 — removed config/base_instructions.txt)
- Output examples: Embedded in _DEFAULT_OUTPUT_EXAMPLES (prompt_builder.py, Session 25 — removed config/output_examples.txt)
- Allows per-project customization by overriding via config_dir files

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
- Detects tokens like __TEMPREPL_X_Y__, __CUST__, delimiters, linebreaks in batch text
- Injects handling instructions only when relevant patterns present
- Configuration via user/conditional_prompts.json for custom patterns
- All 11 built-in conditions configurable in Global Options → Prompts → Conditional Prompts (Pattern Triggered)
- Settings stored in CherryAI.ini [pattern_prompts] section (enabled + text per prompt)
- **Dynamic instructions with pattern-specific examples (TASK 5)**
- **Delimiter differentiation: [square] / {curly} / <angle> / __dunder__**
- **Linebreak differentiation: <br> tags, \\n escapes, literal newlines**

Classes:
- ConditionalPrompt: Dataclass with name, patterns, instruction, priority, category, pattern_examples
- ConditionalPromptManager: Evaluates batches, builds dynamic instructions, applies INI overrides

Key Methods:
- `ConditionalPrompt.matches(text)` - Returns (matched: bool, matched_patterns: Set[str])
- `ConditionalPrompt.get_dynamic_instruction(matched_patterns)` - Generate instruction with relevant examples only
- `ConditionalPrompt._build_delimiter_instruction(matched_patterns)` - Dynamic delimiter type listing
- `ConditionalPrompt._build_linebreak_instruction(matched_patterns)` - Dynamic linebreak kind listing
- `ConditionalPromptManager._apply_ini_overrides()` - Apply enabled/text from CherryAI.ini
- `ConditionalPromptManager.evaluate_batch(lines)` - Evaluate which conditions match
- `ConditionalPromptManager.build_conditional_instructions(lines)` - Build dynamic instruction block
- `build_merged_request_instruction(merge_boundaries)` - Generate block-relatedness text for Step 5 merged requests (TASK 78)

Built-in Conditional Prompts (9 total, all configurable):
| Name | Patterns | Priority | Category | Dynamic |
|------|----------|----------|----------|---------|
| temp_replacement | `__TEMPREPL_\d+_\d+__`, `__CUST__` | 90 | code | examples |
| delimiter_protection | `\[...\]`, `\{...\}`, `<...>`, `__...__` | 80 | anchors | lists matched types |
| linebreaks | `<br>`, `\\n`, `\r\n\|\r\|\n` | 85 | code | lists detected kinds |
| color_codes | `\\c\[\d+\]`, `\\c\[#hex\]` | 70 | code | examples |
| media_commands | `\\se\[...\]`, `\\pic\[...\]`, `\\wait\[...\]`, `\\fadein\[...\]` | 70 | code | examples |
| text_formatting | `\\fb`, `\\fr`, `\\i\[\d+\]`, `\\b` | 65 | code | examples |
| ruby_text | `\\rb\[.*?,.*?\]` | 60 | code | examples |
| ellipsis | `…+`, `\.\.\.+` | 40 | format | examples |
| speaker_dialogue_format | `(?m)^Name[:：] text` | 32 | format | examples |

INI Helpers (ini_manager.py):
- `PATTERN_PROMPT_NAMES`: List of all 9 pattern prompt names
- `get/set_pattern_prompt_enabled(name)`: Read/write enabled state
- `get/set_pattern_prompt_text(name)`: Read/write instruction text
- `get/set_merged_request_text(kind)`: Read/write merged-request instruction texts (all_unrelated, block_unrelated)

Dependencies:
- Local: glossary (for term data), analysis (for token counting)

API VALIDATION (functions/validation.py) ✓ Enhanced Session 14+

Purpose: Multi-layer validation of lines before and after API translation.

Classes:
- SkipReason: Enum for why a line is skipped (EMPTY, COMMENT, TAG, DEDUP_ONLY, PROT_ONLY, CODE_ONLY, NO_JAPANESE, ALREADY_TRANSLATED, SYMBOL_ONLY)
- ValidationResult: Dataclass for single-line validation outcome
- BatchValidationResult: Dataclass for batch processing results
- PlaceholderValidationResult: Dataclass for placeholder preservation (NEW - TASK 4)
- RetryReason: Enum for retry triggers (NEW - TASK 4)
- TranslationValidationResult: Comprehensive per-line result (NEW - TASK 4)
- BatchTranslationValidationResult: Batch result with retry list (NEW - TASK 4)

Key Features:
1. PRE-TRANSLATION VALIDATION (validate_line_pre, validate_batch_pre):
   - Skip empty lines, __COMMENT__-prefixed lines
   - Skip context marker lines (__DIALOGUE__, __MENU__, __CHOICE__, __FILE__)
   - Skip __DEDUP__ and __PROTECTED__ only lines
   - Skip lines consisting entirely of preserved code patterns (CODE_ONLY)
   - Skip lines without Japanese characters
   - Skip already translated lines
   - Auto-translate symbol-only lines (normalize fullwidth → halfwidth)
   - Note: # and = lines are treated as normal text (not skipped)

2. POST-TRANSLATION VALIDATION (validate_line_post, validate_batch_post):
   - Japanese character count check (max 4 chars in translation)
   - Anchor character preservation verification
   - Uses ANCHOR_EQUIVS from modehelper.py for equivalence

3. PLACEHOLDER PRESERVATION (NEW - TASK 4):
   - extract_placeholders(text): Find __PROTECTED__, __PROTECTED_1__, __NAME__, etc.
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

HEADER-BASED RATE LIMITER (functions/header_rate_limiter.py - Implemented)

Purpose: Per-model rate limiting driven by API response headers. Reusable
across providers with different URLs and header names.

Classes:
- `ProviderRateLimitConfig`: Configurable header names and defaults per provider
- `ModelWindowState`: Runtime counters and reset timers for a single model
- `HeaderBasedRateLimiter`: Thread-safe, per-model rate limit enforcement

Pre-built configs:
- `OPENAI_RATE_LIMIT_CONFIG` — x-ratelimit-limit-requests/tokens headers
- `GEMINI_RATE_LIMIT_CONFIG` — same header names (Gemini-compatible)

Flow:
1. On startup: `_init_header_rate_limiter()` loads stored RPM/TPM from API.ini
2. Before each request: `pre_request(model, estimated_tokens)` — blocks until capacity
3. After each response: `update_from_headers(model, headers)` — reads reset timing
4. Counters reset automatically when the monotonic reset instant elapses

Token estimation formula:
```
estimated_tokens = sent_request_token_count + (input_line_token_count × 1.5)
```

Duration parser handles OpenAI reset header formats: "1s", "6m0s", "200ms", "1h2m3s"

Dependencies:
- Standard: threading, time, re, logging
- Local: api_config (for stored limits)

Integration:
- `api_client.py._wait_for_rate_limit()` — primary enforcement (priority over sliding window)
- `api_client.py._translate_chunk()` — uses `with_raw_response` to capture HTTP headers
- `model_registry.py.refresh_models()` — calls `fetch_openai_model_limits()` after model update
- `providers/openai_provider.py.send_request()` — returns headers in `ProviderResponse`

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
| PLACEHOLDER_CASE | `__PROTECTED__`, `__PROTECTED__` | Uppercase to `__PROTECTED__` |
| PLACEHOLDER_WHITESPACE | `__ PROTECTED __` | Remove spaces |
| PLACEHOLDER_MANGLED | `_PROT_`, `__PROTECTED_` | Fix underscore count |
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
Preserve all placeholders exactly: __PROTECTED__, [brackets], {braces}.
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
- detect_speaker(line) → Optional[str]: Extract "NAME:" pattern with validation:
  - Balanced brackets check (all bracket types including CJK must be paired)
  - No-newline rule (colon must appear on first line; multiline text rejected)
  - Length limit (≤30 chars Latin-dominant, ≤20 chars CJK-dominant speakers)
- _has_balanced_brackets(text) → bool: Stack-based bracket balance validation
- _speaker_length_ok(name) → bool: Script-aware length limit check
- _is_cjk_char(ch) → bool: Detect CJK/kana/fullwidth characters
- SPEAKER_MAX_LEN_LATIN = 30, SPEAKER_MAX_LEN_CJK = 20: Length constants
- _CJK_RANGES: Unicode ranges for CJK detection
- _BRACKET_PAIRS: Mapping of open→close brackets (ASCII + CJK)
- extract_names_from_honorifics(lines) → Dict[str, int]: Find speakers with honorifics
- detect_explicit_gender(name, text) → (gender, confidence, source): Find explicit declarations
- detect_honorific_gender_from_others(name, lines, speaker_counts) → (gender, confidence): Weighted others' honorifics
- infer_gender_from_context(pronouns, honorifics, threshold) → (gender, confidence, pronoun_found, honorific_found)
- infer_gender_comprehensive(name, pronouns, honorifics, full_text, lines, speaker_counts, threshold) → (gender, confidence, pronoun_found, honorific_found, source): Multi-signal inference
- infer_genders_batch(names, all_lines, speaker_counts, *, confidence_threshold, max_lines_per_speaker, min_evidence, ignore_unknown, do_all, cancel_check, progress_callback) → Dict[str, Tuple]: Batch gender inference optimized for large manifests. Uses five-phase single-pass scanning (index pass → explicit gender → honorifics from others → self-pronouns → combine signals) instead of per-speaker rescanning. Supports cancellation and progress reporting.
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
- Batch processing via `infer_genders_batch()`: single-pass scanning for all speakers simultaneously, optimized for large manifests (845+ speakers, 64K+ lines in ~5 seconds)
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

Purpose: Optional LLM-based gender inference as fallback

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
4. user/API.ini [api2glossary] key (Session 25: replaced config/config.txt)

Main Functions:
- enrich_speakers_via_api(speaker_data, all_lines, enabled, write_to_glossary) → Dict[speaker, enrichment_data]
  - Takes: Dict mapping speaker names to line indices
  - Extracts: Dialogue excerpts with 5+ context lines
  - Sends: To LLM with structured output schema (single `details` string field)
  - Returns: {speaker → {"gender": ..., "checks": ...}}
  - Gender values are case-insensitive normalized (e.g. "female" → "Female")
  - Accepts any gender value from the LLM; no enum constraint
  - Multi-check: Validates conflicting results up to MAX_VALIDATION_CHECKS
- test_api_connection() → (success: bool, details: dict)
  - Tests API connectivity with sample "太郎" (expected: Male)
  - Accepts any non-"Unknown" gender as a valid response
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
   - Uses JSON schema for reliable parsing (single `details` field)
   - Requests: gender only (no romanization, no note)
   - Case-insensitive normalization maps any response to canonical form
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
- Context-based gender inference from dialogue
- Accepts any gender value (not limited to Male/Female)
- Case-insensitive normalization for consistent output
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
- Calls name_glossary_functions.detect_speaker() with enhanced validation:
  - Balanced brackets: rejects names with unmatched brackets (e.g. skill descriptions with 〈 but no 〉)
  - No-newline: only checks first line of multiline input; rejects if colon is on a later line
  - Length limit: ≤30 chars for Latin-dominant names, ≤20 for CJK-dominant (rejects long NPC descriptions)
- Tracks pronouns and honorifics used by each speaker
- Infers gender from linguistic patterns (pronouns, suffixes)
- Results: speakers.unique_speakers, speakers.speaker_data
- Speaker Threshold (from UtilitySettings.speaker_threshold, default 10):
  - Speakers below threshold are collapsed into "[+] N Speakers" row in findings table
  - Double-click toggles expansion to show individual below-threshold speakers
  - Below-threshold speaker names stored as comma-separated string in results["collapsed_speakers"]
  - Commas in speaker names replaced with fullwidth comma (，) to avoid delimiter conflicts

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

Protagonist Detection + POV Re-run (Task 75):
- get_protagonists_from_characters(characters) → List[Dict]: Scans notes for "Protagonist" tag (case-insensitive)
- get_protagonists_from_code_database(code_patterns) → List[Dict]: Finds code patterns with "Protagonist" in notes
- run_pov_with_protagonists(lines, language, characters, code_patterns, context_markers) → POVResult: Merged POV detection across all protagonist names; deduplicates 1st/2nd counts for multiple protagonists
- format_protagonist_prompt(characters, code_patterns, pov_result) → str: Builds "Protagonist: {Original} - {Translation} ({Details})\nNarration: {pov} View" section; strips "Protagonist" from details to avoid redundancy; comma-separates multiple protagonists
- Prompt slot 4b: Between Tone and Summary in both prompt_adapter.py and prompt_builder.py; old POV slot 7 skipped when protagonist section has narration
- GUI integration: _set_speaker_role("Protagonist") triggers _rerun_pov_with_protagonists() in gui/steps/analysis.py; stores result in manifest["POV"]

Notes:
- Token counting uses tiktoken if available, else heuristic
- Cost estimation based on GPT-4.1 pricing (configurable)
- Language detection uses heuristics (Japanese, English, etc.)
- All glossary detection is non-blocking (failures don't stop analysis)

ROMANIZATION.PY (Japanese Kana → Rōmaji — Task 75)

Purpose: Dependency-free Modified Hepburn romanization of Japanese hiragana/katakana.

Data:
- _HIRAGANA: Dict[str, str] — 46 base + dakuten + handakuten + small kana
- _KATAKANA: Dict[str, str] — 46 base + dakuten + handakuten + small kana
- _HIRAGANA_DIGRAPHS: Dict[str, str] — 15 yōon combinations (きゃ→kya, etc.)
- _KATAKANA_DIGRAPHS: Dict[str, str] — 15 yōon + extended foreign digraphs (ファ→fa, ティ→ti, etc.)
- _SINGLE_KANA: Merged single-char lookup
- _DIGRAPH_KANA: Merged two-char digraph lookup
- _SMALL_TSU: {"っ", "ッ"} — consonant doubling markers
- _KANA_RE: Regex for detecting any kana character

Public API:
- romanize(text) → str: Convert kana to rōmaji; digraphs before singles; small tsu doubles next consonant; long vowel extends; non-kana passed through
- contains_kana(text) → bool: True if text contains any hiragana/katakana
- romanize_if_japanese(text) → str: Romanize only if kana detected, else return unchanged
- capitalize_name(text) → str: Title-case romanized output; hyphens treated as word separators (e.g. "ko-no-ha" → "Ko-No-Ha")

Integration:
- name_glossary_functions.py: Auto-fills GlossaryEntry.translation with romanize_if_japanese(name) when translation is empty
- code_glossary_functions.py: Auto-fills Notes with _auto_romanize_notes(pattern) for kana code patterns

TERM_TRANSLATION.PY (Unified Term Translation Dispatcher)

Purpose: Route term translation through the mode configured in Global Options → Utility.

Constants:
- MODES: ("Romaji", "LLM") — valid mode identifiers

Mode Detection:
- get_current_mode() → str: Reads term_translation_mode from INI [utility] section; falls back to "Romaji". Migrates legacy "MTL" values to "Romaji".

Public API:
- translate_term(term, source_lang, target_lang, *, mode, context) → str: Translate a single term
- translate_terms(terms, source_lang, target_lang, *, mode, context) → List[str]: Batch-translate (LLM mode batches for efficiency)

Internal:
- _translate_simple(term): romanize_if_japanese + capitalize_name
- _translate_llm(term, src, tgt, ctx): Single-term LLM call (delegates to batch)
- _translate_llm_batch(terms, src, tgt, ctx): OpenAI-compatible API call; structured JSON prompt → {"translations": [...]}
- _get_api_key(): Retrieves active API key from api_config or ini_manager

Dependencies:
- functions/romanization.py — Romaji mode
- functions/ini_manager.py — configuration reading
- openai — for LLM mode

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

Purpose: Identify and handle duplicate lines via per-line tags

Functions:
- deduplicate_pre(processor) → tags LineEntry with "dedup,D{source_idx}" for top MAX_DEDUP_GROUPS (10) groups
- deduplicate_post(processor) → tag-based restoration (primary), legacy dedup_by_doc fallback
- _tag_dedup_line(processor, idx, source_idx) → writes dedup tags to LineEntry
- _read_dedup_tags(processor, line_count) → reads dedup source mappings from tags → Dict[int, int]
- _restore_from_legacy_mappings(processor) → legacy dedup_by_doc restoration path
- _restore_aggressive_numbers(processor) → aggressive number restoration
- aggressive_normalize_line(line) → line with numbers masked
- normalize_dedup_entries(manifest) → clean old dedup format

Features:
- Two-pass deduplicate_pre: collect all dup groups → rank by count → process top MAX_DEDUP_GROUPS
- Per-line tags (comma-separated on LineEntry.tags) replace dedup_by_doc mapping dict
- Tag-based restoration in deduplicate_post with legacy fallback for backward compatibility
- Exact-line deduplication and aggressive dedup (mask numbers before comparison)

Dependencies:
- Stdlib: re, json

CONFIG.PY (Session 4 - Configuration Persistence)

Purpose: INI/JSON configuration management with automatic defaults.
Also serves as central registry for model encoding mappings (TASK 16.3).

Constants:
- DEFAULT_CONFIG: Dict with default values for all sections:
  - [api]: provider, api_key, model, temperature, timeout, etc.
  - [session]: last_input, last_manifest
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
- estimate_cost(input_tokens, output_tokens, model=None, cached_tokens=0) → Dict
  - Estimates translation cost with input_usd, output_usd, total_usd
  - When cached_tokens > 0 and model has cached_input pricing, also returns prompt_usd and cached_input_usd
  - Formula: (input - cached) × input_price + cached × cached_input_price + output × output_price
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
   - Replaces with __PROTECTED__ (Pre)
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

GLOBAL GLOSSARY (TSV)

Location: user/globalglossary.tsv  [Session 26: renamed from GlobalGlossary.csv; changing to TSV with 4-column design (TASK 76: added Active)]
⚠️ CONFLICT: gui/steps/information.py::_global_db_path() currently returns user/global_glossary.json
   for the Global Glossary widget. Both systems must be consolidated into globalglossary.tsv (Phase 62).

```tsv
Original	Translation	Notes	Active
イオリ	Iori	Female protagonist. API.女性. 私と言う。ちゃんと呼ばれる	True
メイド	Maid	Occupation term	True
<color>		Control code — preserve as-is	True
```

Note: The Notes column carries all additional context (gender, role, source, pronouns) as plain text
within a single field. No extra CSV columns. Four columns (TASK 76 added Active column, defaults to True).

CODE DATABASE (TSV)

Location: user/codedatabase.tsv  [Session 26: replaces codeglossary.db SQLite and global_codes.json]
⚠️ CONFLICT: gui/steps/information.py::_global_db_path() returns user/global_codes.json
   for the Code Database widget. Both must be consolidated into codedatabase.tsv (Phase 62).
⚠️ CONFLICT: functions/glossaries/code_glossary_db.py uses SQLite (user/codeglossary.db).
   This module must be replaced with TSV-based I/O (Phase 62).

```tsv
Pattern	Type	RegEx	Notes	Visible	IsInvisible	IsCouple	IsNumber	IsWord	Active
\V[\d+]	RPGMakerVariable	\\V\[\d+\]	Game variable reference	1	0	0	1	0	True
\c[\d+]	ColorCode	\\c\[\d+\]	Color control code	0	1	0	0	0	True
```

Note: Visibility and extended property columns (IsInvisible, IsCouple, IsNumber, IsWord)
are the explicit in-file representation of the Code Database Extended Properties (see §5.7).
Active column (TASK 76) defaults to True; entries with active=False are excluded from prompts.

```ini
[session]
last_manifest = /path/to/last.cherryproj
manifest_history = /path/a.cherryproj, /path/b.cherryproj
last_step = 0
load_last = true

[ui]
geometry = 
state = normal

[confirmations]
remove_character = true

[api]
; Non-secret settings only. Encrypted secrets are in user/API.ini
provider = openai
model = gpt-4o-mini
temperature = 0.3

[manifest_defaults]
; Default values for newly created manifests

[defaults]
; Long-text defaults (SystemInstructions, Summary)

[style]
; User-saved style presets (built-ins always available without entries here)

[tone]
; User-saved tone presets
```

ENCRYPTED API CONFIG (INI)

Location: user/API.ini  [NEW 2026 — managed by functions/api_config.py]
Purpose: ALL API meta information — encrypted keys + provider profiles (model, temperature, URL, etc.)
⚠️ PLANNED (Phase 62): `api_profiles.ini` at project root to be consolidated here.
Full intended structure:

```ini
[security]
password_hash = $2b$10$...     ; bcrypt WF-10 hash
key_salt      = <32-byte hex>  ; PBKDF2 salt

[translation]
; Primary translation API profile (from api_profiles.ini, to be moved here)
provider = openai
api_key = gAAAAAB...           ; Fernet AES-256 encrypted
base_url =
model = gpt-4o-mini
temperature = 0.3
timeout = 60
retries = 3
rate_limit_requests = 60

[glossary]
; API profile for LLM-assisted glossary generation (API2Glossary)
provider = gemini
api_key = gAAAAAB...
model = gpt-4o-mini
temperature = 0.3

[api2glossary]
; API key for optional glossary LLM extraction
key =

[api_presets]
gemini_free = https://...|gemini-2.0-flash-lite|0.3|120|15

[rate_limits]
; Per-model rate limit settings
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

# Detect speaker from dialogue line (with balanced brackets, length, and newline validation)
speaker = detect_speaker("アリス: Hello!")  # "アリス"
speaker = detect_speaker("No speaker here")  # None
speaker = detect_speaker("〈戦闘中回数制限: text")  # None (unbalanced bracket)
speaker = detect_speaker("A" * 31 + ": text")  # None (too long for Latin)

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
#         "gender": "Female",
#         "checks": 2
#     },
#     "Bob": {
#         "gender": "Male",
#         "checks": 2
#     }
# }
# Gender values are case-insensitive normalized (e.g. "female" → "Female")
# Any gender value is accepted; no enum constraint
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


=============================================================================

## functions/model_registry.py

New module (Dynamic Model Registry). Single source of truth for model metadata.

**Key classes/functions:**
- `ModelInfo` — dataclass with 30+ fields (standard/batch/flex/priority pricing, limits, capabilities, timestamps)
- `FALLBACK_MODELS` — curated built-in data for openai/google/mistral (27 models total)
- `refresh_models(api_keys, path, providers)` — fetch from live APIs + save to INI
- `save_to_ini(provider, models, path)` — persist to `[model_registry_<provider>]` section
- `load_from_ini(provider, path)` → `(models, last_updated_iso)`
- `get_all_models(path, providers, max_age_hours)` — load from INI or fallback
- `get_all_models_flat(path, max_age_hours)` — flat list across all providers
- `get_provider_models(provider, path, max_age_hours)` → `List[ModelInfo]`
- `get_provider_model_ids(provider, path)` → `List[str]`
- `get_model_info(model_id, path)` → `Optional[ModelInfo]`
- `get_pricing_dict(path, max_age_hours)` → `MODEL_PRICING`-compatible dict
- `get_registry_summary(path)` → status dict per provider
- `is_data_fresh(provider, path, max_age_hours)` → `bool`

**Provider constants:** `PROVIDER_OPENAI = "openai"`, `PROVIDER_GOOGLE = "google"`, `PROVIDER_MISTRAL = "mistral"`

**INI sections added to user/API.ini:**
- `[model_registry]` — version, last_refreshed
- `[model_registry_openai]`, `[model_registry_google]`, `[model_registry_mistral]` — `last_updated` + `data` (JSON blob)

**API endpoints:**
- OpenAI: `GET https://api.openai.com/v1/models` (Bearer key)
- Google: `GET https://generativelanguage.googleapis.com/v1beta/models?key={key}`
- Mistral: `GET https://api.mistral.ai/v1/models` (Bearer key)

**Fallback data (27 models):**
- OpenAI (12): gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini, o4-mini, o3, gpt-5-mini, gpt-5, gpt-5.1, gpt-5.2, gpt-5-nano
- Google (7): gemini-3.1-pro-preview, gemini-3-flash-preview, gemini-2.5-pro, gemini-2.5-flash, gemini-2.5-flash-lite, gemini-2.0-flash, gemini-2.0-flash-lite
- Mistral (8): mistral-large-latest, mistral-medium-latest, mistral-small-latest, magistral-medium-latest, magistral-small-latest, codestral-latest, ministral-8b-latest, ministral-3b-latest

**Pricing tiers (ModelInfo fields):**
- Standard: `input_price`, `cached_input_price`, `output_price`
- Batch: `batch_input_price`, `batch_output_price` (async batch API, ~50% of standard)
- Flex: `flex_input_price`, `flex_output_price` (same as batch rates, higher latency)
- Priority: `priority_input_price`, `priority_output_price` (~1.75-2x standard, lower latency)
- GPT-4.1 family: standard + batch only (no flex, no priority)
- GPT-5 family: all four tiers (standard, batch, flex, priority)

**Thinking/Reasoning mode (ModelInfo fields):**
- `thinking: bool` — legacy field, True if model supports any reasoning
- `thinking_mode: str` — three-state classification: "optional" (GPT-4.1), "mandatory" (GPT-5), "builtin" (o-series), "explicit" (Claude, Gemini thinking, Magistral), "" (unavailable)
- `to_pricing_entry()` includes `thinking_mode` in output dict

**functions/config.py:** `MODEL_PRICING` is now `_ModelPricingProxy` — lazily syncs from registry on every dict access. Backward-compatible: all existing code using `MODEL_PRICING` works unchanged.

**functions/options.py:** `API_PROVIDERS` is now `_APIProvidersProxy` — cloud providers (openai/gemini/mistral) get model lists from registry; static providers (anthropic/local/ollama/lmstudio) unchanged. Added `reload_api_providers()`.

**gui/dialogs/global_options.py:** Added "⟳ Refresh Models" button; `_update_model_list()` uses `get_provider_models()` from registry; `_on_refresh_models()` runs in background thread.

**gui/steps/translate.py:** `MODEL_OPTIONS` updated to Feb 2026 models; `_update_model_list_from_global_options()` falls back to registry before hardcoded list.

=============================================================================

## Task 74 — Request Preview Overhaul & Formation Integration

### gui/steps/translate.py Changes

**`SECTION_DESCRIPTIONS` dict:** Maps 12 section keys to informative descriptions displayed
in `build_full_request_text()` headers as `=== Label (description) ===`.

**`_build_chunks()` rewrite:** Replaced simple fixed-size chunking with formation-aware logic:
1. Converts `TranslatableLine` → `LineInfo` (index, text, is_invalid flag for __DEDUP__/__PROTECTED__/__CUSTOM__)
2. Injects `file_end` context markers from `mgr.get_filedir()` entries
3. Calls `build_requests(line_infos, RequestFormationConfig(max_lines=chunk_size))`
4. Maps `TranslationRequest.line_indices` back to `List[List[TranslatableLine]]`
5. Stores `_formation_ctx` dict on first line of each chunk (receives_context, provides_context, context_type)
6. Falls back to simple `range(0, len, chunk_size)` on ImportError or pipeline failure

**Rolling context in `_do_translation()` loop:**
- Reads `rolling_context_lines` from `session.global_options.request` (default 3)
- Maintains `rolling_ctx_buffer: list[str]` of all completed translations
- For chunks with `receives_context=True` (from formation metadata or chunk_idx > 0 fallback):
  formats last N translations as `rolling_context_text` and passes to `_translate_chunk()`
- `_translate_chunk()` passes `rolling_context_text` to `_build_system_prompt_from_manifest()`
- Chunks with `provides_context=True` append their translations to the buffer

**`_translate_chunk()` signature change:** Added `rolling_context_text: str = ""` parameter.
Now passes both `rolling_context_text` and `chunk_lines` (filtered for __DEDUP__) to
`_build_system_prompt_from_manifest()`.

**`_build_preview_requests()` rolling context hint:** For chunks that would receive rolling
context at translation time, the preview shows a descriptive placeholder:
`[Rolling context: last N translated lines from previous chunk will be inserted here]`.

**Step index bug fixes:** Two occurrences of `get_step_data_value(3, "metadata", {})` →
`get_step_data_value(2, "metadata", {})` — Information step is index 2, not 3.

**`_log_request_json()` method:** Writes timestamped JSON to `logs/requests/` when
`global_options.logging.log_requests` is True. Payload: timestamp, chunk_index, model,
temperature, system_prompt, input_lines, line_count.

**Cross-request search:** `RequestPreviewDialog` tracks `_cross_counts` (per-request match
counts), `_cross_total`, `_cross_global_idx`. `_do_search()` scans all requests via
`_render_text_for_request()`. Navigation methods: `_resolve_global_index()` maps to
(request_idx, local_match_idx); `_navigate_to_global_match()` switches request;
`_search_next()`/`_search_prev()` use modular wrapping.

### gui/helpers/prompt_adapter.py Changes

**`build_full_system_prompt()` `chunk_lines` parameter:** `Optional[List[str]]` that enables
per-chunk selective filtering:
- Section 8 (Conditional): detects against `chunk_lines` instead of `sample_lines`
- Section 9 (Glossary): filters entries by `source` term presence in chunk text
- Section 9 (Characters): filters by `original_name` presence in chunk text

### gui/dialogs/global_options.py Changes

**`LoggingSettings.log_requests`:** `bool = False` field. Wired to `self.log_requests_var`
BooleanVar, checkbox UI in `_build_logging_section`, `logging_defaults` dict for INI
save/load, `ini_manager` for defaults loading, `LoggingSettings` constructor in options build.

### Rename custom_notes → system_instructions

Updated across 6 files: `ProjectMetadata` dataclass + to_dict/from_dict in information.py,
`ProjectInfo` dataclass + pascal_map "Prompt" mapping in manifest_manager.py (migration reads
both keys), `metadata.get()` calls in prompt_adapter.py and translate.py,
`"system_instructions"` key in test_prompt_builder_shared.py.

## Bug Fix — Section Toggle Persistence & Preview Gating

### gui/steps/information.py Changes

**`on_leave()` toggle merging:** `ProjectMetadata.to_dict()` does NOT include `*_enabled`
keys (by design — they are not part of the dataclass). Previously, `on_leave()` replaced
the entire metadata dict with `to_dict()` output via `set_step_data()`, erasing the toggle
flags that `_toggle_section_enabled()` had written via `set_info_metadata_field()`. Fixed by
reading current BooleanVar values for all seven toggles (`genre_enabled`, `summary_enabled`,
`style_enabled`, `tone_enabled`, `system_instructions_enabled`, `glossary_enabled`,
`code_database_enabled`) and merging them into the metadata dict after `to_dict()`.

**`_save_metadata()` cleanup:** Removed `messagebox.showinfo("Saved", ...)` popup. Now
merges toggle states identically to `on_leave()` for consistency. Retained as internal
helper for programmatic use.

**Save button removed:** Removed `ttk.Button(header, text="Save", command=self._save_metadata)`
from `_build_header()`. Auto-save on tab change via `on_leave()` → `set_step_data()` is
sufficient.

### gui/steps/translate.py Changes

**`_build_preview_requests()` toggle gating:** Added enabled flag reads from metadata dict.
Each labeled section (sys_instructions, style, tone, summary, genre) is now wrapped in an
`if *_enabled:` guard. Per-chunk glossary and character sections are gated by
`glossary_enabled`. Matches the gating logic in `build_full_system_prompt()`.

Variables added: `si_enabled`, `style_enabled`, `tone_enabled`, `summary_enabled`,
`genre_enabled`, `glossary_enabled` — all read from `metadata.get("*_enabled", default)`.

### Tests: dev/test_section_toggles.py (35 tests)

8 test classes covering prompt toggle gating (15), ProjectMetadata boundary (1),
on_leave toggle preservation (2), prompt token count (2), manifest metadata field (5),
Save button removal (1), preview section gating (6), tab change save/load (3).

## Phase 78 — Estimation, Validation & Formation Fixes

### functions/validation.py Changes

**`FilterEntry` dataclass:** Represents a parsed blacklist/whitelist entry.
Fields: `raw` (original text), `pattern` (compiled regex or None), `is_regex`.
Method `matches(text)` checks if the text contains the entry.

**`parse_filter_entries(raw)`:** Splits a comma-separated filter string into
`FilterEntry` objects.  `\,` escapes a literal comma; `re=<pattern>` compiles
as a regex; plain tokens match literally.

**`check_filter_violations(text, wl, bl)`:** Returns a list of human-readable
violation strings when *text* contains blacklisted entries or characters not
covered by the whitelist.

### gui/steps/translate.py Changes

**`LineStatus.NEEDS_REVIEW`:** New enum value for lines flagged during character
validation.  Displayed as `⚠ Review` in the translation table.

**`_apply_char_filters()` rewrite:** No longer strips characters.  Parses
entries via `parse_filter_entries`, checks via `check_filter_violations`, then
applies the three configurable strategies (exchange → retry → flag).  Accepts
optional `line_objects` parameter to set line status.

**Caller update (translation loop):** Passes `line_objects=chunk` to
`_apply_char_filters`.  Preserves `NEEDS_REVIEW` / `PENDING` status set by
the filter instead of unconditionally marking `COMPLETED`.

### gui/dialogs/global_options.py Changes

**`TranslationSettings` new fields:** `exchange_forbidden_chars: bool = True`,
`flag_for_qa_review: bool = True`, `retry_forbidden_chars: bool = False`.
Serialized via `to_dict()` / `from_dict()`.

**New BooleanVars:** `exchange_forbidden_var`, `flag_qa_review_var`,
`retry_forbidden_var` — initialized from `TranslationSettings`, written back
in `_collect` and loaded in `_load_initial_defaults`.

**Character Validation LabelFrame:** Three checkboxes added to the Translation
section between Request Slicing and Consistency System.

### functions/prompt_builder.py Changes

**`build_requests()` file-section tagging:** Tracks `first_in_section` per
file group.  The first request of each file section gets
`receives_context=False`, preventing stale rolling context from prior files.

### gui/steps/costs.py Changes

**Per-request prompt overhead (Task 42):** `_estimate_via_formation()`
returns `FormationResult` dataclass (num_requests, request_line_lists).
New `_compute_per_request_prompt_overhead()` iterates each request's lines,
calls `build_full_system_prompt(chunk_lines=...)` for selective glossary/
conditional filtering, counts tokens individually, and sums them.  Replaces
the old pattern of building one maximum-sized prompt and multiplying by
all requests.

**`_update_ui()` prompt overhead format:** Changed from
`~X tokens/request × Y requests = ~Z total` to
`~Z total (Y Requests, ~X avg/request)`.

**`_render_current_request()` token counting:** Uses `count_tokens()` for
separate prompt-token and input-token counts instead of `len // 4`.

## Phase 78.2 — API Error Classification & Concurrent Execution

### functions/common_errors.py Changes

**5 New `ErrorCode` values:** `TRANSLATION_NON_STRUCTURED_OUTPUT`,
`TRANSLATION_LINE_COUNT_MISMATCH`, `TRANSLATION_EMPTY_RESPONSE`,
`TRANSLATION_REFUSED`, `TRANSLATION_ABORT`.

**`APIErrorCategory` enum (20 categories):** AUTH_INVALID, AUTH_PERMISSION,
MODEL_NOT_FOUND, RATE_LIMIT, QUOTA_EXCEEDED, CONTEXT_LENGTH, CONTENT_FILTER,
BAD_REQUEST, INVALID_JSON_SCHEMA, TIMEOUT, SERVER_ERROR, SERVER_OVERLOADED,
CONNECTION_ERROR, BILLING, API_DEPRECATED, REGION_UNAVAILABLE,
NON_STRUCTURED_OUTPUT, LINE_COUNT_MISMATCH, EMPTY_RESPONSE, UNKNOWN.

**`ClassifiedAPIError` dataclass:** Fields: category, user_message, steps
(remediation), raw_message, is_retryable, is_fatal.

**`_API_ERROR_INFO` dict:** Maps each category to a user-facing message and
list of remediation steps.

**`classify_api_error(error: Exception) -> ClassifiedAPIError`:** Inspects
`type(error).__name__` and message text against known patterns. Returns a
fully-populated `ClassifiedAPIError`.

**`TranslationAbortError(Exception)`:** Wraps a `ClassifiedAPIError`.
Properties: `user_message`, `category`, `classified`. Method
`format_for_display()` returns user-facing text with steps; shows raw error
for UNKNOWN category.

### functions/api_client.py Changes

**`_translate_chunk_with_retry()`:** Rewritten to classify errors before
deciding whether to retry. Fatal errors (auth, model-not-found, quota,
content-filter, billing) raise `TranslationAbortError` immediately — no
retries. Retryable errors (rate-limit, timeout, server-error) use
exponential backoff. Exhausted retries produce a classified abort.

**`_translate_chunk()`:** API call exceptions are now classified via
`classify_api_error()` before re-raising. Fatal → `TranslationAbortError`;
retryable → `TranslationError`. JSON parse failures and non-list translations
raise `TranslationAbortError` directly.

### functions/prompt_builder.py Changes

**`_CONTEXT_TYPE_PRIORITY` dict:** Maps context types to sort priority
(dialogue=0, choice=1, mixed/unknown=2, menu=3).

**`RequestString` dataclass:** Fields: requests, context_type,
has_rolling_context. Properties: priority, line_count.

**`sort_requests_by_type(requests) -> List[RequestString]`:** Groups requests
into rolling-context chains (sequential runs where `receives_context=True`).
Sorts chains by type priority → RC chains first → longer chains first.

**`_build_string()` helper:** Determines dominant context type by line count
across the chain.

### gui/steps/translate.py Changes

**Imports added:** `threading`, `concurrent.futures` (ThreadPoolExecutor,
as_completed, Future), `TranslationAbortError`.

**`_group_chunks_into_strings()` (static):** Reconstructs
`TranslationRequest` objects from chunk `_formation_ctx` metadata, calls
`sort_requests_by_type()`, maps results back to chunk groups. Returns
`List[List[List[TranslatableLine]]]` — sorted string groups.

**`_process_single_chunk()`:** Extracted chunk processing logic: builds
rolling context, translates, applies char filters, updates progress with
thread-safe locking. Returns `"ok"`, `"abort"`, or `"cancel"`.

**`_handle_chunk_retry()`:** Extracted retry logic using the standard retry
handler. Thread-safe progress updates via `threading.Lock`.

**`_execute_string_sequential()`:** Processes all chunks of one request
string in order. Designed for `ThreadPoolExecutor` threads. Each string
has its own rolling context buffer — no cross-thread buffer conflicts.
Raises `TranslationAbortError` for fatal errors.

**`_do_translation()` rewrite (concurrent engine):**
1. Calls `_group_chunks_into_strings()` to get sorted string groups.
2. **Validation gate:** First chunk of first string sent alone. If fatal
   error → abort immediately with user-facing dialog.
3. Remaining strings execute via `ThreadPoolExecutor(max_workers=
   max_concurrent)`. Sequential fallback when `max_concurrent ≤ 1`.
4. Thread-safe progress via `threading.Lock`. Abort in any thread sets
   `_cancel_requested` and breaks the `as_completed()` loop.

**`_translate_chunk()` context_type fix:** Now extracts `context_type` from
`_formation_ctx` and passes it to `_build_system_prompt_from_manifest()`,
enabling §5.2 item 7b (context-type conditional prompt) injection.

### Tests

| Test File | Count | Focus |
|-----------|-------|-------|
| `dev/test_api_error_classification.py` | 56 | APIErrorCategory, classify_api_error, TranslationAbortError |
| `dev/test_first_request_gate.py` | 14 | Fatal abort (no retry), retryable errors, validation gate |
| `dev/test_request_sorting.py` | 22 | sort_requests_by_type, RC chains, type priority |
| `dev/test_concurrent_execution.py` | 23 | _process_single_chunk, _execute_string_sequential, ThreadPoolExecutor parallel, thread safety |
| `dev/test_context_type_prompts.py` | 18 | get_context_prompt, build_full_system_prompt context_type, _translate_chunk flow |
| **Total** | **133** | |

## Phase 79 — Output Injection Standardization

### Overview

Adds explicit INJECTION output format with standardized parser handshake,
fixes stale data in Output step, and corrects Same as Source directory
resolution.

### formats/parser_base.py Changes

**`inject_to()` rewrite:** New signature `inject_to(self, source_path,
output_path, lines, *, orig_lines=None) -> List[int]`. Default
implementation follows 4-step Speaker:Dialogue-aware handshake:
(0) Load source file into memory (respects `detect_encoding()`).
(1) Extract keys via `self.extract_tagged()` (preferred) or `self.extract()`
for search strings and per-line speaker metadata.
(2) Speaker-aware replacement — lines with a non-empty speaker are split
via `_split_speaker_dialogue()` (half-width `: ` or fullwidth `：`)
into speaker and dialogue parts. Speaker name replaced only on first
occurrence for consecutive same-speaker lines (`last_replaced_speaker`
tracking). Dialogue text replaced separately. Lines without a speaker
use plain `content.find(search)` find-and-replace. No-change positions
(search == translated) are skipped. Failures (not found) appended to
return list with logger warning.
(3) Save to output_path (creates parent dirs).
When `orig_lines` is provided, uses those as search strings instead of
extracted keys. Returns `List[int]` of failed indices.

**`_split_speaker_dialogue()` helper (NEW):** Module-level function that
splits `"Speaker: dialogue"` into `(speaker, dialogue)` tuple using
`_SPEAKER_DIALOGUE_RE` regex (half-width `: ` or fullwidth `：`).
Returns `("", text)` when no separator found.

### formats/LightVN.py Changes

**`inject_to()` signature updated:** Accepts `*, orig_lines=None` kwarg
(ignored — LightVN uses its own `_extract_all_keys()` / `_inject_all()`
pipeline since extracted keys like "Speaker: dialogue" differ from raw
file text). Returns `List[int]`. Internal logic unchanged.

### gui/steps/output_inject.py Changes

**`OutputFormat.INJECTION` enum:** New member `INJECTION = "injection"`.
FORMAT_DESCRIPTIONS: "Parser injection (original format preserved)".
FORMAT_EXTENSIONS: empty string (preserves original file extension).

**`_get_same_as_source_dir()` fix:** Returns `mgr.get_original_dir().parent`
instead of `mgr.get_original_dir()`. Fallback returns
`source_path.parent.parent`. Output subfolders (e.g. `translated/`) now
sit next to `Original/` rather than inside it.

**`_write_file()` rewrite:** Routes to `_write_injection()` for INJECTION
format. For generic formats, calls `_get_fresh_lines_for_file()` instead
of stale `step_data["lines"]` cache.

**`_get_fresh_lines_for_file(output_file) -> List[str]` (NEW):** Reads
directly from manifest manager using filedir entry's `first_idx:last_idx+1`
range. Calls `resolve_line_field()` per line. Falls back to
`get_all_lines_resolved(mgr)` or legacy session data.

**`_write_injection(output_file, output_path, mgr)` (NEW):** Implements
standardized 4-step handshake:
(0) Load `\Original` via `mgr.resolve_file_path(entry.rel_path)`.
(1) Get parser from `ParserRegistry` by `entry.format`. Extract keys.
(2) Sequential match — verify each extracted key matches manifest `orig`
field. Resolve best text via `resolve_line_field()`. Mismatches preserve
original text and log warnings.
(3) Call `parser.inject_to(source, output, translated_lines,
orig_lines=orig_lines)`. Report inject failures via logger.

**`_build_file_list_from_filedir()`:** Updated `is_parser_format` check
to include `is_injection = raw_fmt == OutputFormat.INJECTION.value`.
INJECTION format preserves original file extension.

### Tests

| Test File | Count | Focus |
|-----------|-------|-------|
| `dev/test_output_injection.py` | 39 | Standardized inject_to (8), LightVN signature (2), fresh line reads (2), Same as Source dir (3), INJECTION format enum (4), write injection handshake (2), build file list (1), edge cases (3), _split_speaker_dialogue helper (4), Speaker:Dialogue injection (10) |

---

## Phase 80 — Manifest Overwrite Prevention

### Problem

Loading a manifest and then saving (via step change or close) silently overwrites stored `RequestOptions`, `Information` metadata, and step results (preprocessing maps, input paths, analysis results). Root causes:

1. **`TranslationStep.__init__()`** fires `_populate_key_dropdown()` which calls `_on_key_changed()` → writes default `ApiKeyProvider`/`ApiKeyName` to manifest. The Model combobox's `trace_add("write")` fires on `.set()` during init, writing the first filtered model over the stored one.
2. **`InformationStep._ensure_style_tone_text()`** unconditionally deletes text widget content, then only inserts replacement if the active `si_preset` exists in the INI. When the preset is missing, text is wiped. `_ensure_default_texts()` then detects empty fields and overwrites `si_preset` to "Default".
3. **`PreprocessingStep._update_step_data()`**, **`InputStep._update_step_data()`**, and **`AnalysisStep.on_leave()`** create fresh dicts with only current config/counts, discarding all other stored keys when calling `set_step_data()`.

### gui/steps/translate.py Changes

**`_initializing` guard pattern:**
- Flag set `True` before `super().__init__()`, `False` after `_build_ui()` completes.
- `_populate_key_dropdown()` calls `_filter_models_by_provider()` directly during init (no `_on_key_changed()`, no manifest writes).
- `_on_key_changed()` returns early when `_initializing` is `True`.
- `bind_combobox_to_field` for Model and RequestMode uses a `manager_getter` lambda that returns `None` during init, suppressing the trace callback's save path.

### gui/steps/information.py Changes

**`_ensure_style_tone_text()` conditional delete:**
- Each of the three sections (Style Instructions, Tone Instructions, System Instructions) now guards both `delete("1.0", "end")` and `insert("1.0", prompt_text)` inside `if prompt_text:`.
- When the preset is missing from the INI (empty `prompt_text`), the existing widget text is preserved.

### gui/steps/preprocess.py Changes

**`_update_step_data()` merge pattern:**
- Changed from `data = {"key": val, ...}` to `data = self.get_step_data()` followed by `data["key"] = val` for each updated key.
- Preserves `dedup_map`, `aggr_dedup_map`, `aggr_numbers`, `ellipsis_counts`, `placeholder_captured`, `anchor_captured` when `_last_stats` is empty.

### gui/steps/input_extract.py Changes

**`_update_step_data()` merge pattern:**
- Same change as preprocess.py. Starts from existing step data and merges config keys.
- Preserves `manifest_path`, `suggested_project_name`, and other stored keys.

### gui/steps/analysis.py Changes

**`on_leave()` merge pattern:**
- Changed from `self.set_step_data({"analysis_results": results})` to get existing data, update `analysis_results` key, then `set_step_data(merged)`.
- Preserves all other analysis step keys.

### Tests

| Test File | Count | Focus |
|-----------|-------|-------|
| `dev/test_manifest_overwrite.py` | 14 | Preprocessing data preservation (2), Input data preservation (1), Analysis data preservation (1), RequestOptions preservation (3), Info metadata preservation (2), Manifest round-trip (3), Manifest comparison regression (2) |

(End of technical.md)
