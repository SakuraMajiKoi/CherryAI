# CherryAI Module Stock Report

**Generated:** Manual audit against documentation (features.md, technical.md, specs.md)  
**Scope:** All Python files except dev/  
**Total Files:** 113 Python modules

---

## Executive Summary

| Package | Files | Classes | Functions | Documented |
|---------|-------|---------|-----------|------------|
| Root | 3 | 2 | ~25 | Partial |
| functions/ | 46 | ~90 | ~300 | 39 in docs |
| functions/glossaries/ | 5 | 0 | ~15 | 5 in docs |
| modi/ | 12 | 0 | ~30 | 12 in docs |
| formats/ | 10 | ~15 | ~25 | 7 in docs |
| gui/ | 3 | 6 | 0 | Partial |
| gui/steps/ | 13 | ~50 | 4 | 10 in docs |
| gui/helpers/ | 8 | 7 | ~60 | 6 in docs |
| gui/dialogs/ | 5 | ~15 | 0 | 4 in docs |
| gui/components/ | 2 | 3 | 0 | 1 in docs |
| gui/state/ | 2 | 3 | ~5 | 1 in docs |
| gui/theme/ | 3 | 3 | ~8 | 3 in docs |
| **Total** | **113** | **~195** | **~470** | |

---

## Part 1: Root-Level Modules

### CherryAI.py
**Purpose:** Main entry point with GUI launcher, CLI dispatcher, and legacy IO wrappers.  
**How it fits:** Primary application module that delegates to gui/app.py for GUI mode and functions/CLI.py for command-line operations.  
**Classes:**
- None (uses dataclasses from mainhelper)

**Functions:**
- `setup_logger()` - Initialize application logging via shared helper
- `derive_manifest_path()` - Get manifest path for input file
- `save_template_file()` - Save operation template to JSON
- `template_base_path()` - Get template file path
- `derive_output_path()` - Generate versioned output path
- `now_iso()` - UTC timestamp in ISO format
- `read_text()` - Read text file (delegates to mainhelper)
- `write_text()` - Write text file
- `detect_delimiter()` - Detect CSV/TSV delimiter
- `safe_regex_replace()` - Regex replacement with count
- `literal_replace()` - Literal string replacement
- `generate_token()` - Generate placeholder token
- `read_table()` - Read CSV/TSV table (delegates)
- `write_table()` - Write CSV/TSV table (delegates)
- `read_json_pairs()` - Read JSON pairs (delegates)
- `write_json_pairs()` - Write JSON pairs (delegates)
- `read_xlsx_pairs()` - Read Excel pairs (delegates)
- `write_xlsx_pairs()` - Write Excel pairs (delegates)
- `main()` - GUI entry point
- `run_smoke_test_cli()` - CLI smoke test helper
- `run_analysis_cli()` - CLI analysis helper
- `_cli_entry()` - CLI argument parser

---

### \_\_init\_\_.py
**Purpose:** Package initializer allowing module-mode execution.  
**How it fits:** Minimal stub enabling `python -m CherryAI.CherryAI` execution.  
**Classes:** None  
**Functions:** None

---

### conftest.py
**Purpose:** Pytest configuration for test environment setup.  
**How it fits:** Test infrastructure ensuring correct import paths and package aliases.  
**Classes:** None  
**Functions:**
- `_setup_cherryai_package()` - Set up CherryAI namespace for imports
- `pytest_configure()` - Pytest hook for session setup
- `ensure_cherryai_imports()` - Pytest fixture for import setup

---

## Part 2: functions/ Package (46 files)

Core shared processing logic used by both GUI and CLI.

### agent_modes.py
**Purpose:** Agent-assisted modes with LLM API for interactive help and script authoring.  
**How it fits:** Provides AI-assisted preprocessing mode configuration.  
**Classes:**
- `AgentMode` - Single agent mode with metadata
- `AgentRequest` - Request to agent
- `AgentResponse` - Response from agent
- `AuditEntry` - Audit trail entry
- `ReadScope` - File read permission enum
- `WriteScope` - File write permission enum

**Functions:**
- `register_mode()` - Register/replace agent mode
- `unregister_mode()` - Remove registered mode
- `get_mode()` - Get mode by name
- `list_modes()` - List all registered modes
- `gather_context()` - Gather context based on scope
- `agent_call()` - Execute single agent call

---

### analysis.py
**Purpose:** File analysis including metrics, code detection, speaker detection, and cost estimation.  
**Step Integration:** Step 1 (Analysis), Step 2 (Costs)  
**Classes:**
- `EstimationConfig` - Configuration for estimation

**Functions:**
- `set_ignored_patterns()` - Set patterns to ignore
- `get_ignored_patterns()` - Get ignored patterns
- `add_ignored_pattern()` - Add pattern to ignore
- `filter_ignored_patterns()` - Filter ignored patterns
- `count_tokens()` - Count tokens using tiktoken
- `analyze_file()` - Main analysis entry point

---

### API2Glossary.py
**Purpose:** LLM-based name translation and gender inference for glossary enrichment.  
**Step Integration:** Step 3 (Information)  
**Functions:**
- `enrich_speakers_via_api()` - Enrich speaker names via LLM
- `test_api_connection()` - Test API connection

---

### api_client.py
**Purpose:** LLM API communication with rate limiting, chunking, and error handling.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `APIConfig` - API client configuration
- `TranslationError` - Translation failure exception
- `APIClient` - Main API client class

**Functions (via APIClient):**
- `apply_preset()` - Apply API preset
- `supports_thinking_mode()` - Check thinking support
- `configure_logit_bias()` - Configure token banning
- `configure_cache()` - Configure caching
- `configure_rate_limiter()` - Configure rate limiting

---

### auto_pipeline.py
**Purpose:** Automatic pipeline orchestrator for 8-step translation workflow.  
**Step Integration:** Cross-step (1-Click automation)  
**Classes:**
- `PipelineLevel` - Pipeline execution level enum
- `PipelineResult` - Pipeline result
- `PipelineContext` - Pipeline context
- `AutoPipeline` - Main orchestrator

**Functions:**
- `AutoPipeline.execute()` - Execute pipeline

---

### auto_tagger.py
**Purpose:** Automatic content classification and tagging for translation lines.  
**Step Integration:** Step 1 (Analysis)  
**Classes:**
- `ContentTag` - Content type enum
- `StatusTag` - Workflow status enum
- `SeverityLevel` - Priority enum
- `LineTag` - Single tag
- `LineTags` - Complete tag set
- `AutoTagger` - Main tagger engine

**Functions:**
- `create_auto_tagger()` - Factory function
- `get_content_tag_description()` - Tag description

---

### batch_tracker.py
**Purpose:** OpenAI Batch API job management for async translation.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `BatchRequest` - Single batch request
- `BatchJob` - Batch job metadata

**Functions:**
- `load_batch_jobs()` - Load tracked jobs
- `save_batch_jobs()` - Persist jobs
- `add_batch_job()` - Add new job
- `get_active_jobs()` - Get processing jobs
- `get_completed_jobs()` - Get finished jobs

---

### chunker.py
**Purpose:** Token-based and line-based chunking for translation batches.  
**Step Integration:** Step 2 (Costs), Step 5 (Translation)  
**Classes:**
- `ChunkMode` - Chunking strategy enum
- `ChunkerConfig` - Chunker configuration
- `Chunker` - Main chunker class

**Functions:**
- `Chunker.count_tokens()` - Count tokens
- `Chunker.chunk_lines()` - Split lines into chunks

---

### chunk_optimizer.py
**Purpose:** Adaptive chunk sizing based on error rates during translation.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `ErrorType` - Error type enum
- `OptimizerConfig` - Optimizer configuration
- `BatchResult` - Batch result
- `ChunkOptimizer` - Adaptive chunk optimizer

**Functions:**
- `ChunkOptimizer.get_chunk_size()` - Get recommended size
- `ChunkOptimizer.record_batch()` - Record batch result

---

### CLI.py
**Purpose:** CLI implementation for estimate, translate, test, config, sample commands.  
**How it fits:** Alternative entry point to GUI, uses same processing modules.  
**Classes:**
- `Task` - CLI task definition
- `CLIProgressDisplay` - Progress display

**Functions:**
- `main()` - CLI entry point
- `run_translate()` - Translation command
- `run_estimate()` - Estimation command
- `run_test()` - Test command
- `run_config()` - Configuration command

---

### cli_io.py
**Purpose:** CLI IO adapter bridging CLI to the formats module.  
**How it fits:** Enables CLI to use same format handlers as GUI.  
**Functions:**
- `read_text_via_handler()` - Read text using handler
- `write_text_via_handler()` - Write text using handler
- `read_table_via_handler()` - Read table using handler
- `get_supported_extensions()` - Get supported extensions

---

### common_errors.py
**Purpose:** Centralized error handling with error codes and logging utilities.  
**How it fits:** Cross-cutting error infrastructure.  
**Classes:**
- `ErrorCode` - Error code enum
- `CherryError` - Structured error
- `ErrorCollector` - Error collector

**Functions:**
- `validate_config_for_api()` - Validate API config

---

### conditional_prompts.py
**Purpose:** Pattern-triggered prompt instructions injected into system prompt.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `ConditionalPrompt` - Conditional prompt
- `ConditionalPromptManager` - Prompt manager

**Functions:**
- `ConditionalPrompt.matches()` - Check pattern match
- `ConditionalPromptManager.get_active_prompts()` - Get matching prompts

---

### config.py
**Purpose:** Centralized INI-based configuration and model pricing constants.  
**How it fits:** Cross-cutting configuration management.  
**Functions:**
- `get_encoding_for_model()` - Get tiktoken encoding
- `get_model_pricing()` - Get model pricing
- `get_model_names()` - Get model IDs
- `estimate_cost()` - Estimate cost
- `load_config()` - Load from INI
- `save_config()` - Save to INI
- `get_api_config()` - Get API section

---

### consistency.py
**Purpose:** Translation consistency tracking for recurring terms.  
**Step Integration:** Step 8 (QA)  
**Classes:**
- `ConsistencyTerm` - Tracked term
- `ConsistencyStore` - Term collection
- `ConsistencyManager` - Main manager

**Functions:**
- `ConsistencyStore.get()` - Look up term
- `ConsistencyStore.add()` - Add term

---

### dedup.py
**Purpose:** Deduplication engine for pre/post processing to reduce API usage.  
**Step Integration:** Step 4 (Preprocessing)  
**Functions:**
- `deduplicate_pre()` - Pre-process deduplication
- `deduplicate_post()` - Post-process expansion
- `aggressive_normalize_line()` - Aggressive normalization

---

### dependencies.py
**Purpose:** Dependency checker and installer for requirements.txt.  
**How it fits:** Startup infrastructure.  
**Functions:**
- `compute_file_hash()` - Compute MD5 hash
- `install_requirements()` - Install packages
- `check_and_install_dependencies()` - Check and install
- `ensure_dependencies()` - Startup convenience

---

### estimation.py
**Purpose:** Token estimation, cost prediction, and inference options.  
**Step Integration:** Step 2 (Costs)  
**Classes:**
- `InferenceOptions` - Pipeline options
- `CostLineItem` - Cost line item
- `CostEstimate` - Complete estimate

**Functions:**
- `estimate_tokens_for_lines()` - Estimate tokens
- `estimate_chunks()` - Estimate chunks
- `compute_cost()` - Compute cost

---

### glossary.py
**Purpose:** Unified glossary management at user/glossary.csv.  
**Step Integration:** Step 3 (Information), Step 5 (Translation)  
**Classes:**
- `GlossaryEntry` - Glossary entry

**Functions:**
- `read_unified_glossary()` - Read glossary
- `write_unified_glossary()` - Write glossary
- `update_unified_glossary()` - Update glossary
- `filter_glossary_for_chunk()` - Filter for chunk

---

### i18n.py
**Purpose:** Internationalization module with JSON language files.  
**How it fits:** Cross-cutting UI localization.  
**Functions:**
- `init()` - Initialize i18n
- `t()` - Translate key
- `set_language()` - Switch language
- `get_language()` - Get current language
- `get_available_languages()` - List languages

---

### ini_manager.py
**Purpose:** INI file path resolution and typed access to configuration.  
**How it fits:** Cross-cutting configuration access.  
**Functions:**
- `get_ini_path()` - Get INI path
- `get_app_dir()` - Get app directory
- `reload_ini()` - Force reload
- `get_default()` - Get with type conversion
- `get_str()` / `get_int()` / `get_bool()` - Typed getters
- `get_last_manifest()` / `set_last_manifest()` - Session management
- `get_recent_manifests()` / `add_to_recent_manifests()` - Recent list
- `get_effective_default()` - User > initial > fallback

---

### key_manager.py
**Purpose:** Multi-key management with auto-rotation for API keys.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `PoolMode` - Key selection strategy enum
- `KeyStatus` - Runtime key status enum
- `APIKey` - Single API key
- `KeyPool` - Pool of keys

**Functions:**
- `load_keys()` - Load stored keys
- `save_keys()` - Persist keys
- `add_key()` - Add new key

---

### languages.py
**Purpose:** Single source of truth for supported languages.  
**How it fits:** Cross-cutting language definitions.  
**Classes:**
- `Language` - Language dataclass

**Functions:**
- `get_language_names()` - Get display names
- `get_language_codes()` - Get codes
- `get_language_by_code()` - Get by code
- `find_language()` - Find by identifier

---

### local_llm.py
**Purpose:** Local LLM integration for LM Studio, Ollama, and OpenAI-compatible servers.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `LocalLLMProvider` - Provider enum
- `LocalServerInfo` - Server info
- `ModelInfo` - Model info

**Functions:**
- `check_port_open()` - Check port
- `detect_local_servers()` - Detect servers
- `get_available_models()` - List models

---

### logit_bias.py
**Purpose:** Logit bias / token banning for LLM output control.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `LogitBiasConfig` - Configuration
- `LogitBiasManager` - Manager class

**Functions:**
- `LogitBiasManager.apply_preset()` - Apply preset
- `LogitBiasManager.get_logit_bias()` - Get bias dict
- `parse_ban_tokens_arg()` - Parse tokens
- `create_logit_bias_manager()` - Factory

---

### mainhelper.py
**Purpose:** Core helpers, data models (Manifest, LineEntry, Operation), and IO utilities.  
**How it fits:** Central processing engine used by all steps.  
**Classes:**
- `Operation` - Processing operation
- `LineEntry` - Manifest line entry
- `Manifest` - Main manifest structure
- `Processor` - Core processing engine

**Functions:**
- `read_text()` - Read text file
- `write_text()` - Write text file
- `read_table()` - Read CSV/TSV
- `read_json_pairs()` - Read JSON pairs
- `derive_output_path()` - Get output path
- `setup_logger()` - Configure logging

---

### manifest_fields.py
**Purpose:** Type-specific helpers for ManifestManager field operations.  
**How it fits:** Manifest field type handling.  
**Functions:**
- `save_text_field()` - Save text field
- `load_text_field()` - Load text field
- `save_bool_field()` - Save boolean
- `load_bool_field()` - Load boolean
- `save_int_field()` - Save integer
- `save_list_field()` - Save list

---

### manifest_manager.py
**Purpose:** Unified state management using manifest as single source of truth.  
**Step Integration:** All steps via state sync  
**Classes:**
- `StepState` - Step state
- `ProjectInfo` - Project metadata
- `GlossaryConfig` - Glossary config
- `ManifestManager` - Main manager

**Functions:**
- `ManifestManager.new_manifest()` - Create new
- `ManifestManager.load_manifest()` - Load from file
- `ManifestManager.save()` - Save manifest
- `ManifestManager.get_lines()` - Get line entries

---

### mock_translator.py
**Purpose:** Deterministic mock translation for pipeline testing, with flaw injection.  
**Step Integration:** Step 5 (Translation - testing)  
**Classes:**
- `FlawIntensity` - Flaw intensity enum
- `FlawConfig` - Flaw configuration
- `FlawReport` - Flaw report
- `MockTranslator` - Mock translator

**Functions:**
- `MockTranslator.translate_batch()` - Translate batch
- `MockTranslator.get_report()` - Get flaw report

---

### modehelper.py
**Purpose:** Shared helpers for modes (PROTECTED placeholder, anchor equivalence).  
**How it fits:** Utility functions for modi/ modules.  
**Functions:**
- `get_equivs()` - Get equivalent characters
- `find_all_equiv_positions()` - Find positions
- `restore_placeholders_in_line()` - Restore placeholders

---

### One_Click_Test.py
**Purpose:** Comprehensive one-click test of entire pipeline.  
**How it fits:** Testing infrastructure.  
**Classes:**
- `TestResult` - Single test result
- `TestReport` - Complete report
- `OneClickTester` - Test runner

**Functions:**
- `OneClickTester.run_all_tests()` - Run all tests

---

### options.py
**Purpose:** Options dialog and state management for GUI.  
**Step Integration:** Global options dialog  
**Classes:**
- `OptionsDialog` - Options modal

**Functions:**
- `get_api_urls()` - Get provider URLs
- `get_provider_models()` - Get provider models
- `get_provider_names()` - Get provider keys

---

### output.py
**Purpose:** Output resolution with 9-level injection priority chain.  
**Step Integration:** Step 9 (Output/Inject)  
**Functions:**
- `get_final_output()` - Resolve single line
- `resolve_all_lines()` - Resolve all lines
- `get_source_breakdown()` - Get priority breakdown

---

### postanalysis.py
**Purpose:** Post-translation analysis comparing manifest original lines against final output.  
**Step Integration:** Step 6 (QA)  
**Functions:**
- `compare_manifest_and_final()` - Compare original vs final

---

### postprocess.py
**Purpose:** Recovery mechanisms for translations with structural issues.  
**Step Integration:** Step 6 (Postprocess)  
**Classes:**
- `RecoveryType` - Recovery type enum
- `RecoveryAction` - Action enum
- `RecoveryIssue` - Issue descriptor
- `RecoveryResult` - Result for line
- `BatchRecoveryResult` - Batch result
- `RecoveryStats` - Statistics

**Functions:**
- `normalize_placeholder()` - Normalize placeholder
- `recover_placeholders()` - Recover missing
- `recover_line()` - Apply recovery

---

### preset_manager.py
**Purpose:** Save/load/delete operations for named presets.  
**How it fits:** Cross-cutting preset management.  
**Classes:**
- `Preset` - Single preset
- `PresetFile` - Preset collection
- `PresetManager` - Singleton manager

**Functions:**
- `PresetManager.save_preset()` - Save preset
- `PresetManager.load_preset()` - Load by name
- `PresetManager.delete_preset()` - Delete preset
- `PresetManager.list_presets()` - List all

---

### process_order.py
**Purpose:** Priority ordering for preprocessing and postprocessing operations.  
**Step Integration:** Step 4 (Preprocessing), Step 6 (Postprocess)  
**Functions:**
- `get_pre_order()` - Get preprocessing order
- `get_post_order()` - Get postprocessing order

---

### project_config.py
**Purpose:** Project-specific settings stored in manifest or API profiles.  
**Step Integration:** Step 3 (Information)  
**Classes:**
- `ProjectConfig` - Project configuration
- `APIProfile` - API profile

**Functions:**
- `ProjectConfig.from_dict()` - Create from dict
- `load_game_summary()` - Load summary
- `format_summary_for_prompt()` - Format for prompt
- `load_api_profile()` - Load profile
- `list_api_profiles()` - List profiles

---

### prompt_builder.py
**Purpose:** Dynamic prompt construction with game summary, style, and glossary injection.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `LineInfo` - Line representation
- `RequestFormationConfig` - Request config
- `TranslationRequest` - Structured request
- `PromptBuilder` - Main builder

**Functions:**
- `get_context_prompt()` - Get context prompt
- `build_requests()` - Build requests
- `PromptBuilder.build_system_prompt()` - Build system prompt

---

### rate_limiter.py
**Purpose:** Comprehensive rate limit tracking with RPM/daily limits.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `RateLimitType` - Limit type enum
- `RateLimitAction` - Action enum
- `ModelRateLimits` - Model limits
- `UsageRecord` - Usage record
- `RateLimiter` - Main limiter

**Functions:**
- `RateLimiter.can_proceed()` - Check capacity
- `RateLimiter.record_request()` - Record request
- `RateLimiter.wait_for_capacity()` - Wait for capacity

---

### replication.py
**Purpose:** Game update detection and translation update generation.  
**Step Integration:** Step 9 (Output/Inject)  
**Classes:**
- `ChangeType` - Change type enum
- `LineChange` - Single change
- `ComparisonResult` - Comparison result
- `ChangeDetector` - Detector class

**Functions:**
- `ChangeDetector.hash_text()` - Generate hash
- `compare_manifests()` - Compare manifests
- `generate_update_manifest()` - Generate update

---

### request_cache.py
**Purpose:** Request caching to avoid resending identical translation requests.  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `CacheMode` - Cache mode enum
- `CacheConfig` - Cache configuration
- `CacheEntry` - Cache entry
- `CacheStats` - Statistics
- `RequestCache` - Thread-safe cache

**Functions:**
- `RequestCache.get()` - Look up cached
- `RequestCache.store()` - Store in cache
- `RequestCache.get_stats()` - Get statistics
- `parse_cache_mode_arg()` - Parse mode

---

### retry_handler.py
**Purpose:** Retry strategies for failed translations (BATCH, CONTEXTUAL, ISOLATED, SKIP).  
**Step Integration:** Step 5 (Translation)  
**Classes:**
- `RetryStrategy` - Strategy enum
- `RetryConfig` - Configuration
- `RetryResult` - Result
- `BatchRetryResult` - Batch result
- `RetryHandler` - Handler class

**Functions:**
- `RetryHandler.handle_failed_lines()` - Handle failures

---

### style_presets.py
**Purpose:** Pre-built translation style guides for common scenarios.  
**Step Integration:** Step 3 (Information)  
**Classes:**
- `StyleCategory` - Category enum
- `Formality` - Formality enum
- `HonorificHandling` - Honorific enum
- `StylePreset` - Preset dataclass
- `StylePresetManager` - Manager

**Functions:**
- `get_style_preset()` - Get by name
- `list_style_presets()` - List presets
- `StylePreset.to_prompt_text()` - Convert to prompt

---

### usage_tracker.py
**Purpose:** SQLite-backed usage analytics tracking every API request.  
**How it fits:** Cross-cutting usage tracking.  
**Classes:**
- `UsageRecord` - Usage event

**Functions:**
- `record_usage()` - Insert record
- `query_usage()` - Query records
- `get_daily_summary()` - Daily summary
- `export_to_csv()` - Export to CSV

---

### validation.py
**Purpose:** Pre/post-translation validation including skip detection and speaker format preservation.  
**Step Integration:** Step 8 (QA)  
**Classes:**
- `SkipReason` - Skip reason enum
- `ValidationResult` - Result
- `BatchValidationResult` - Batch result
- `PlaceholderValidationResult` - Placeholder validation
- `SpeakerFormatInfo` - Speaker format

**Functions:**
- `extract_placeholders()` - Extract tokens
- `validate_pre()` - Pre-validation
- `validate_batch()` - Batch validation
- `validate_placeholder_preservation()` - Check placeholders
- `detect_speaker_dialogue_format()` - Detect format

---

### wordwrap.py
**Purpose:** Wordwrap utilities with smart wrapping and code-aware line breaking.  
**Step Integration:** Step 7 (Wordwrap)  
**Classes:**
- `WordwrapConfig` - Configuration

**Functions:**
- `normalize_break_char()` - Normalize break char
- `smart_wrap()` - Smart wrapping
- `manual_wrap_line()` - Manual wrap
- `apply_wordwrap()` - Apply to lines
- `get_wordwrap_modes()` - Get modes

---

## Part 3: functions/glossaries/ Package (5 files)

Glossary system for code patterns and speaker names.

### \_\_init\_\_.py
**Purpose:** Package exports for glossary modules.  
**Functions:** None (re-exports from submodules)

---

### code_glossary_constants.py
**Purpose:** Code pattern constants for placeholder detection.  
**Constants:**
- `COMMON_CODE_PATTERNS` - List of code pattern regex
- `LANGUAGE_SPECIFIC_PATTERNS` - Language-specific patterns
- `PLACEHOLDER_FORMATS` - Placeholder format definitions

---

### code_glossary_functions.py
**Purpose:** Code detection and classification functions.  
**Functions:**
- `is_code_line()` - Check if line is code
- `classify_code_pattern()` - Classify code type
- `extract_code_segments()` - Extract code from line
- `get_code_glossary_entries()` - Get glossary entries

---

### name_glossary_constants.py
**Purpose:** Speaker name patterns and romanization mappings.  
**Constants:**
- `COMMON_SPEAKER_PATTERNS` - Regex for speaker detection
- `ROMANIZATION_TABLES` - Character romanization
- `GENDER_HINTS` - Name-to-gender mappings

---

### name_glossary_functions.py
**Purpose:** Speaker detection and gender inference functions.  
**Functions:**
- `detect_speaker()` - Detect speaker in line
- `extract_speaker_name()` - Extract name from format
- `infer_gender()` - Infer gender from name
- `romanize_name()` - Romanize Japanese name
- `get_name_glossary_entries()` - Get glossary entries

---

## Part 4: modi/ Package (12 files)

Pre/post-processing mode plugins.

### \_\_init\_\_.py
**Purpose:** Mode loader and registry with apply_pre/apply_post interface.  
**Functions:**
- `load_modes()` - Load all modes
- `get_modi()` - Get mode by name
- `MODE_REGISTRY` - Global mode registry

---

### anchor.py
**Purpose:** Anchor-based text protection mode.  
**How it fits:** Protects text at specific positions, restores post-translation.  
**Functions:**
- `apply_pre()` - Store and replace anchored text
- `apply_post()` - Restore anchored text
**Mode Metadata:** NAME="Remove and Restore at Anchor", PHASE="Both", PRIORITY=100

---

### custom_placeholder.py
**Purpose:** User-defined placeholder replacement mode.  
**How it fits:** Replace custom patterns with placeholders.  
**Functions:**
- `apply_pre()` - Replace patterns with placeholders
- `apply_post()` - Restore from placeholders
**Mode Metadata:** NAME="Custom Placeholder", PHASE="Both", PRIORITY=50

---

### free.py
**Purpose:** Free-form processing mode for custom transformations.  
**How it fits:** User-defined regex/literal replacements.  
**Functions:**
- `apply_pre()` - Apply pre-transformation
- `apply_post()` - Apply post-transformation
**Mode Metadata:** NAME="Free", PHASE="Both", PRIORITY=200

---

### only_remove.py
**Purpose:** Remove-only pattern mode (no restoration).  
**How it fits:** Permanent removal of matched patterns.  
**Functions:**
- `apply_pre()` - Remove matched patterns
- `apply_post()` - No-op (nothing to restore)
**Mode Metadata:** NAME="Only Remove", PHASE="Pre", PRIORITY=150

---

### protect_code.py
**Purpose:** Code protection → __PROTECTED__ placeholders.  
**How it fits:** Main code protection mode using unified placeholder.  
**Functions:**
- `apply_pre()` - Replace code with __PROTECTED__
- `apply_post()` - Restore from __PROTECTED__
**Mode Metadata:** NAME="Protect Code", PHASE="Both", PRIORITY=10

---

### replace_after.py
**Purpose:** Post-translation replacement mode.  
**How it fits:** Apply replacements only after translation.  
**Functions:**
- `apply_pre()` - No-op
- `apply_post()` - Apply replacements
**Mode Metadata:** NAME="Only Replace After TL", PHASE="Post", PRIORITY=180

---

### replace_before.py
**Purpose:** Pre-translation replacement mode.  
**How it fits:** Apply replacements only before translation.  
**Functions:**
- `apply_pre()` - Apply replacements
- `apply_post()` - No-op
**Mode Metadata:** NAME="Only Replace Before TL", PHASE="Pre", PRIORITY=170

---

### sabotage.py
**Purpose:** Sabotage/corruption detection mode.  
**How it fits:** Detect and flag suspicious patterns.  
**Functions:**
- `apply_pre()` - Detect sabotage patterns
- `apply_post()` - Verify no corruption
**Mode Metadata:** NAME="Sabotage Detection", PHASE="Both", PRIORITY=5

---

### standard_mode.py
**Purpose:** Standard preprocessing (ellipsis, dedup).  
**How it fits:** Default preprocessing pipeline.  
**Functions:**
- `apply_pre()` - Apply standard preprocessing
- `apply_post()` - Apply standard postprocessing
**Mode Metadata:** NAME="Standard", PHASE="Both", PRIORITY=1

---

### template_mode.py
**Purpose:** Template-based processing mode.  
**How it fits:** Skipped by mode registry (base template).  
**Functions:**
- `apply_pre()` - Placeholder for pre-transformation
- `apply_post()` - Placeholder for post-transformation
**Note:** Not loaded by mode registry (skipped by convention)

---

### temporary_replacement.py
**Purpose:** Temporarily replace patterns with placeholders or text, restore in Post.  
**How it fits:** Temporary replacements that restore after translation.  
**Functions:**
- `apply_pre()` - Replace pattern, record for restoration
- `apply_post()` - Restore original text
**Mode Metadata:** NAME="Temporary Replacement", PHASE="Both", PRIORITY=100

---

## Part 5: formats/ Package (10 files)

File format handlers and parser scripts.

### \_\_init\_\_.py
**Purpose:** File format handler system with registry, IO configuration, and parser script support.  
**Step Integration:** Step 0 (Input/Extract), Step 9 (Output/Inject)  
**Classes:**
- `IOConfig` - Format handling configuration
- `FormatHandler` (ABC) - Abstract base class
- `FormatRegistry` - Handler registry
- `ParserRegistry` - Parser registry

**Functions:**
- `get_registry()` - Get global format registry
- `get_handler()` - Get handler by ID/extension
- `get_parser_registry()` - Get parser registry
- `detect_parser()` - Auto-detect parser

**Constants:** `SIMPLE_FORMATS`, `RPGMAKER_FORMATS`, `DOCUMENT_FORMATS`, `MARKDOWN_FORMATS`

---

### document.py
**Purpose:** Placeholder handlers for PDF and EPUB document formats.  
**Classes:**
- `PdfHandler` - PDF handler (PLACEHOLDER)
- `EpubHandler` - EPUB handler (PLACEHOLDER)

**Functions:**
- `get_handlers()` - Return document handlers

---

### html.py
**Purpose:** HTML file handler with inline tag placeholder system using BeautifulSoup4.  
**Classes:**
- `InlineTag` - Inline tag representation
- `TextBlock` - Extracted text block
- `HtmlHandler` - Basic HTML handler
- `HtmlHandlerAdvanced` - Full structure preservation

**Functions:**
- `get_handlers()` - Return HTML handlers

**Constants:** `SKIP_TAGS`, `INLINE_TAGS`, `BLOCK_TAGS`

---

### json_lenient.py
**Purpose:** Lenient JSON handler supporting comments, trailing commas, single quotes.  
**Classes:**
- `JsonLenientHandler` - Handler for .json5/.jsonc

**Functions:**
- `sanitise_json()` - Clean to strict JSON
- `get_handlers()` - Return lenient JSON handlers
- `_remove_line_comments()` - Remove // comments
- `_single_to_double_quotes()` - Convert quotes
- `_extract_strings()` - Extract translatable strings

---

### markdown.py
**Purpose:** Markdown file handler preserving code blocks and frontmatter.  
**Classes:**
- `MarkdownHandler` - Markdown with code protection

**Functions:**
- `get_handlers()` - Return Markdown handlers
- `reset_inline_store()` - Clear placeholder store
- `_protect_inline_code()` - Replace inline code
- `_restore_inline_code()` - Restore inline code

---

### parser_base.py
**Purpose:** Abstract base interface for game-engine-specific parser scripts.  
**Classes:**
- `WordwrapConfig` - Wordwrap configuration
- `ForbiddenChars` - Banned characters
- `TagRules` - Context patterns
- `ParserScript (ABC)` - Abstract parser base

---

### rpgmakermvmz.py
**Purpose:** RPG Maker MV/MZ handlers and parser implementations with structured JSON/plugin extraction, wordwrap, and context rules.  
**Classes:**
- `RpgMakerMVHandler` - MV format handler
- `RpgMakerMZHandler` - MZ format handler
- `RpgMakerMVParser` - MV parser
- `RpgMakerMZParser` - MZ parser
- `RpgMakerPluginHandler` - Plugin JS handler

**Functions:**
- `get_handlers()` - Return RPG Maker handlers

---

### simple.py
**Purpose:** Simple format handlers for txt, csv, tsv, json, xlsx files.  
**Classes:**
- `TxtHandler` - Plain text handler
- `CsvHandler` - CSV handler
- `TsvHandler` - TSV handler
- `JsonHandler` - JSON handler
- `XlsxHandler` - Excel handler

**Functions:**
- `get_handlers()` - Return simple handlers

---

### translator_plus.py
**Purpose:** Translator++ (.trans) SQLite database format handler.  
**Classes:**
- `TranslatorPlusHandler` - T++ handler

**Functions:**
- `get_handlers()` - Return T++ handlers
- `_find_table()` - Find translation table
- `_find_columns()` - Find column names

---

## Part 6: gui/ Package (37 files)

GUI v2 with 10 workflow steps and supporting infrastructure.

### gui/\_\_init\_\_.py
**Purpose:** Package initializer exporting App class.  
**Exports:** `App`

---

### gui/app.py
**Purpose:** Main application window with 10 workflow tabs, progress tracker, menu bar, status bar.  
**Classes:**
- `App` - Main Tkinter application

---

### gui/progress.py
**Purpose:** Progress tracker panel with preset selection, step status, skip/rollback.  
**Classes:**
- `Subtask` - Subtask entry
- `SubtaskGroup` - Subtask container
- `StepRow` - Step row display
- `ProgressPanel` - Progress panel widget
- `ProgressTracker` - Alias for ProgressPanel

---

### gui/steps/\_\_init\_\_.py
**Purpose:** Package exporting all workflow step implementations.  
**Exports:** All step classes

---

### gui/steps/base.py
**Purpose:** Abstract base class for workflow step tabs.  
**Classes:**
- `BaseStep` - Abstract base step
- `PlaceholderStep` - Placeholder for unimplemented steps

---

### gui/steps/input_extract.py
**Purpose:** Step 0 - File loading, preview, encoding detection, format filtering.  
**Step:** Input/Extraction  
**Classes:**
- `LoadedFile` - File metadata
- `InputExtractionStep` - Step implementation

---

### gui/steps/analysis.py
**Purpose:** Step 1 - Static analysis: line counts, duplicates, language, code, speakers.  
**Step:** Analysis  
**Classes:**
- `AnalysisStep` - Step implementation

---

### gui/steps/costs.py
**Purpose:** Step 2 - Cost and time estimation based on tokens and rate limits.  
**Step:** Costs  
**Classes:**
- `EstimationResult` - Estimation result
- `ComparisonResult` - Comparison result
- `CostsStep` - Step implementation
- `EstimationStep` - Backward-compat alias

**Functions:**
- `count_tokens()` - Count tokens
- `estimate_cost()` - Estimate cost
- `estimate_rate_limit_time()` - Rate limit time
- `_format_time()` - Format time display

---

### gui/steps/estimate.py
**Purpose:** Backward compatibility redirect to costs.py.  
**Note:** Re-exports from costs.py

---

### gui/steps/information.py
**Purpose:** Step 3 - Project metadata, LLM inference, style/tone, character notes.  
**Step:** Information  
**Classes:**
- `InferenceStatus` - Status enum
- `MetadataField` - Metadata field
- `StylePreset` - Style preset
- `TonePreset` - Tone preset
- `CharacterInfo` - Character info
- `CodePattern` - Code pattern
- `ProjectMetadata` - Project metadata
- `InferenceOptions` - Inference options
- `InferenceResult` - Result
- `InformationStep` - Step implementation

---

### gui/steps/preprocess.py
**Purpose:** Step 4 - Preprocessing rules: dedup, symbols, ellipsis, placeholders.  
**Step:** Preprocessing  
**Classes:**
- `PreprocessingStep` - Step implementation

---

### gui/steps/translate.py
**Purpose:** Step 5 - Translation with live progress, prompt editing, retry handling.  
**Step:** Translation  
**Classes:**
- `LineStatus` - Line status enum
- `TranslationState` - State enum
- `TranslationProgress` - Progress tracking
- `TranslationOptions` - Options
- `TranslatableLine` - Line entry
- `TranslationProgressWindow` - Progress window
- `TranslationStep` - Step implementation

---

### gui/steps/qa.py
**Purpose:** Step 8 - QA checks, issue flagging, validation, batch accept/reject.  
**Step:** QA  
**Classes:**
- `IssueType` - Issue type enum
- `IssueSeverity` - Severity enum
- `QAStatus` - Status enum
- `QAIssue` - Issue entry
- `QALine` - QA line
- `ValidationRule` - Validation rule
- `QAOptions` - QA options
- `QAStep` - Step implementation

---

### gui/steps/postprocess.py
**Purpose:** Step 6 - Placeholder/anchor restore, symbol conversion, recovery.  
**Step:** Postprocess  
**Classes:**
- `RecoveryType` - Recovery type enum
- `RecoveryAction` - Action enum
- `FailurePolicy` - Policy enum
- `PostprocessStatus` - Status enum
- `RecoveryIssue` - Issue entry
- `PostprocessLine` - Line entry
- `PostprocessOptions` - Options
- `RecoveryStats` - Statistics
- `PostprocessingStep` - Step implementation

---

### gui/steps/wordwrap_overwrite.py
**Purpose:** Step 7 - Wordwrap configuration, preview, overwrite/merge options.  
**Step:** Wordwrap  
**Classes:**
- `WrapMode` - Wrap mode enum
- `SpeakerMode` - Speaker handling enum
- `WrapStatus` - Status enum
- `WrapLine` - Line entry
- `FormatConfig` - Format config
- `WrapOptions` - Options
- `WrapStats` - Statistics
- `WordwrapOverwriteStep` - Step implementation

---

### gui/steps/output_inject.py
**Purpose:** Step 9 - Final output, format selection, naming, backup, file writing.  
**Step:** Output/Inject  
**Classes:**
- `OutputFormat` - Format enum
- `NamingStrategy` - Naming enum
- `BackupStrategy` - Backup enum
- `PairMode` - Pair mode enum
- `ExportStatus` - Status enum
- `OutputFile` - Output file
- `NamingOptions` - Naming options
- `BackupOptions` - Backup options
- `OutputOptions` - Output options
- `ExportStats` - Statistics
- `ManifestExportOptions` - Manifest export
- `OutputInjectStep` - Step implementation

---

### gui/helpers/\_\_init\_\_.py
**Purpose:** Package exporting all helper adapters.  
**Exports:** All adapter functions and classes

---

### gui/helpers/analysis_adapter.py
**Purpose:** Bridge between GUI and functions/analysis.py.  
**Functions:**
- `detect_language()` / `detect_language_batch()` - Language detection
- `detect_code_patterns()` / `detect_code_patterns_batch()` - Code detection
- `detect_speaker_in_line()` / `detect_speakers_batch()` - Speaker detection
- `summarize_lines()` - Line summary
- `count_duplicates()` - Duplicate count
- `count_tokens()` / `count_tokens_batch()` - Token counting
- `analyze_lines()` - Full analysis

---

### gui/helpers/chunker_adapter.py
**Purpose:** Bridge between GUI and functions/chunker.py.  
**Classes:**
- `ChunkModeView` - Mode view
- `ChunkConfigView` - Config view
- `ChunkResultView` - Result view
- `RateLimitView` - Rate limit view
- `TimeEstimateView` - Time estimate
- `OptimizerStatsView` - Optimizer stats

**Functions:**
- `count_tokens()` / `count_tokens_batch()` - Token counting
- `is_tiktoken_available()` - Check tiktoken
- `get_chunk_modes()` - Get modes
- `create_chunk_config()` - Create config
- `chunk_lines()` - Chunk lines
- `estimate_chunks()` - Estimate chunks
- `get_model_rate_limits()` - Get limits
- `estimate_rate_limit_time()` - Estimate time
- `estimate_translation_job()` - Full estimation

---

### gui/helpers/glossary_adapter.py
**Purpose:** Bridge between GUI and glossary/config/style modules.  
**Classes:**
- `GlossaryEntryView` - Entry view
- `StylePresetView` - Preset view

**Functions:**
- `load_glossary()` - Load glossary
- `save_glossary()` - Save glossary
- `add_glossary_entry()` / `remove_glossary_entry()` - Entry management
- `get_glossary_stats()` - Statistics
- `get_style_presets()` / `get_style_preset()` - Style presets
- `apply_style_preset()` - Apply preset

---

### gui/helpers/manifest_binding.py
**Purpose:** Widget-to-manifest binding with automatic save/load.  
**Classes:**
- `BindingInfo` - Binding metadata

**Functions:**
- `clear_binding_registry()` - Clear registry
- `get_binding_registry()` - Get registry
- `get_binding_for_field()` - Get binding
- `bind_entry_to_field()` - Bind entry widget
- `bind_checkbox_to_field()` - Bind checkbox
- `bind_combobox_to_field()` - Bind combobox
- `bind_spinbox_to_field()` - Bind spinbox
- `bind_text_to_field()` - Bind text widget
- `bind_radio_group_to_field()` - Bind radio group
- `bind_float_spinbox_to_field()` - Bind float spinbox
- `load_all_bindings()` - Load all bindings

---

### gui/helpers/mode_adapter.py
**Purpose:** Bridge between GUI and modi/ modules.  
**Functions:**
- `apply_ellipsis_compression()` / `apply_ellipsis_batch()` - Ellipsis
- `get_symbol_table()` - Get symbol table
- `apply_symbol_conversion()` / `apply_symbol_batch()` - Symbols
- `apply_prot_compression()` - PROTECTED compression
- `apply_protect_code()` - Apply protect code
- `apply_custom_placeholder()` - Custom placeholders
- `apply_preprocessing()` - Full preprocessing
- `get_common_patterns()` - Common patterns
- `get_available_modes()` - Available modes

---

### gui/helpers/prompt_adapter.py
**Purpose:** Bridge between GUI and prompt builder/retry handler.  
**Classes:**
- `RetryStrategyView` - Strategy view
- `RetryConfigView` - Config view
- `ConditionalPromptView` - Prompt view
- `PromptPreviewView` - Preview view

**Functions:**
- `get_translation_style()` - Get style
- `get_game_summary()` - Get summary
- `get_builtin_conditions()` - Get conditions
- `build_conditional_instructions()` - Build instructions
- `build_prompt_preview()` - Preview prompt
- `get_retry_strategies()` / `get_strategy_info()` - Retry strategies
- `create_retry_config()` - Create config
- `handle_failed_lines()` - Handle failures

---

### gui/helpers/tooltip.py
**Purpose:** Tooltip implementation for tkinter widgets.  
**Functions:**
- `set_tooltips_enabled()` - Enable/disable
- `are_tooltips_enabled()` - Check enabled
- `set_tooltip_delay()` - Set delay
- `attach_tooltip()` - Attach to widget
- `detach_tooltip()` - Remove from widget

---

### gui/dialogs/\_\_init\_\_.py
**Purpose:** Package exporting all dialog classes.  
**Exports:** All dialog classes

---

### gui/dialogs/global_options.py
**Purpose:** Centralized options with categorized settings.  
**Classes:**
- `OptionSection` - Section enum
- `OptionCategory` - Category enum
- `LogLevel` - Log level enum
- `ThemeMode` - Theme mode enum
- `LineEnding` - Line ending enum
- `EncodingOption` - Encoding enum
- `APISettings` - API settings
- `APIProviderEntry` - Provider entry
- `RequestSettings` - Request settings
- `CachingSettings` - Caching settings
- `LoggingSettings` - Logging settings
- `SessionSettings` - Session settings
- `SafetySettings` - Safety settings
- `FileIOSettings` - File I/O settings
- `GlobalOptions` - All options container
- `GlobalOptionsDialog` - Dialog implementation

---

### gui/dialogs/input_dialog.py
**Purpose:** Dual-pane file/folder selection dialog.  
**Classes:**
- `UnifiedInputDialog` - Dialog implementation

---

### gui/dialogs/loading_progress.py
**Purpose:** Modal progress dialog for file loading.  
**Classes:**
- `LoadingProgressDialog` - Dialog implementation

---

### gui/dialogs/project_dialog.py
**Purpose:** Project creation and startup dialogs.  
**Classes:**
- `WelcomeDialog` - Startup dialog
- `ProjectNameDialog` - Name prompt dialog
- `LoadManifestDialog` - File browser dialog

---

### gui/components/\_\_init\_\_.py
**Purpose:** Package exporting UI components.  
**Exports:** `ColumnDef`, `SharedTable`, `TableRow`

---

### gui/components/table.py
**Purpose:** Reusable table widget with virtualization and editing.  
**Classes:**
- `ColumnDef` - Column definition
- `TableRow` - Row data
- `SharedTable` - Table widget

---

### gui/state/\_\_init\_\_.py
**Purpose:** Package exporting state management.  
**Exports:** `SessionState`, `StepState`, `UndoAction`

---

### gui/state/store.py
**Purpose:** Session state with undo/redo and autosave.  
**Classes:**
- `StepState` - Step state
- `UndoAction` - Undo action
- `SessionState` - Session state

**Functions:**
- `get_session()` - Get session
- `reset_session()` - Reset session
- `load_session_from_autosave()` - Load autosave
- `get_preset_definitions()` - Get presets
- `get_preset_names()` - Get preset names

---

### gui/theme/\_\_init\_\_.py
**Purpose:** Package exporting theming utilities.  
**Exports:** `ColorPalette`, `Icons`

---

### gui/theme/colors.py
**Purpose:** Color schemes with ttk style configuration.  
**Classes:**
- `ThemeMode` - Mode enum
- `ColorPalette` - Color palette

**Functions:**
- `get_theme()` - Get theme
- `get_theme_mode()` - Get mode
- `set_theme()` - Set theme
- `get_ttk_style_map()` - Get style map
- `apply_theme()` - Apply theme

---

### gui/theme/icons.py
**Purpose:** Unicode/emoji icons for UI elements.  
**Classes:**
- `Icons` - Icon constants

**Functions:**
- `get_step_icon()` - Get step icon
- `get_status_icon()` - Get status icon
- `get_log_level_icon()` - Get log level icon

---

## Part 7: Organization by Cross-Step Features

These features span multiple workflow steps:

### 7.1 Manifest State Management
**Description:** Unified state via manifest file  
**Modules:**
- `functions/manifest_manager.py` - Core manager
- `functions/manifest_fields.py` - Field helpers
- `functions/mainhelper.py` - Manifest/LineEntry classes
- `gui/helpers/manifest_binding.py` - Widget bindings

### 7.2 Glossary System
**Description:** Speaker names, code patterns, terminology  
**Modules:**
- `functions/glossary.py` - Unified glossary
- `functions/glossaries/code_glossary_*.py` - Code glossary
- `functions/glossaries/name_glossary_*.py` - Name glossary
- `gui/helpers/glossary_adapter.py` - GUI adapter

### 7.3 Configuration System
**Description:** INI-based configuration persistence  
**Modules:**
- `functions/config.py` - Configuration persistence
- `functions/ini_manager.py` - Typed INI access
- `functions/project_config.py` - Per-project settings
- `gui/dialogs/global_options.py` - Options dialog

### 7.4 Format Handling
**Description:** File I/O for all supported formats  
**Modules:**
- `formats/__init__.py` - Registry
- `formats/simple.py` - TXT/CSV/TSV/JSON/XLSX
- `formats/html.py` - HTML
- `formats/markdown.py` - Markdown
- `formats/translator_plus.py` - Translator++
- `functions/cli_io.py` - CLI adapter

### 7.5 Processing Pipeline
**Description:** Pre/post-processing transformations  
**Modules:**
- `functions/mainhelper.py` - Processor class
- `functions/process_order.py` - Priority ordering
- `modi/*.py` - All mode plugins
- `gui/helpers/mode_adapter.py` - GUI adapter

### 7.6 API Integration
**Description:** LLM API communication  
**Modules:**
- `functions/api_client.py` - Main client
- `functions/rate_limiter.py` - Rate limiting
- `functions/request_cache.py` - Request caching
- `functions/retry_handler.py` - Retry handling
- `functions/key_manager.py` - Key management
- `functions/logit_bias.py` - Logit bias
- `functions/batch_tracker.py` - Batch API

### 7.7 Prompt System
**Description:** Dynamic prompt construction  
**Modules:**
- `functions/prompt_builder.py` - Prompt builder
- `functions/conditional_prompts.py` - Conditional prompts
- `functions/style_presets.py` - Style presets
- `gui/helpers/prompt_adapter.py` - GUI adapter

### 7.8 Validation & QA
**Description:** Pre/post-translation validation  
**Modules:**
- `functions/validation.py` - Validation engine
- `functions/postprocess.py` - Recovery
- `functions/consistency.py` - Term consistency
- `functions/postanalysis.py` - Post-analysis

### 7.9 Token/Cost Estimation
**Description:** Token counting and cost prediction  
**Modules:**
- `functions/estimation.py` - Estimation engine
- `functions/chunker.py` - Chunking
- `functions/chunk_optimizer.py` - Chunk optimization
- `gui/helpers/chunker_adapter.py` - GUI adapter

### 7.10 Theme & UI
**Description:** Visual theming and UI components  
**Modules:**
- `gui/theme/colors.py` - Color palettes
- `gui/theme/icons.py` - Icons
- `gui/components/table.py` - Table widget
- `gui/helpers/tooltip.py` - Tooltips

---

## Part 8: Organization by Workflow Step

### Step 0: Input/Extraction
**GUI Module:** `gui/steps/input_extract.py`  
**Functions Used:**
- `formats/__init__.py` - Registry, auto-detection
- `formats/simple.py` - Format handlers
- `functions/mainhelper.py` - Read utilities
- `gui/dialogs/input_dialog.py` - File selection

### Step 1: Analysis
**GUI Module:** `gui/steps/analysis.py`  
**Functions Used:**
- `functions/analysis.py` - File analysis
- `functions/auto_tagger.py` - Content tagging
- `functions/glossaries/*` - Pattern detection
- `gui/helpers/analysis_adapter.py` - Bridge

### Step 2: Costs
**GUI Module:** `gui/steps/costs.py`  
**Functions Used:**
- `functions/estimation.py` - Cost estimation
- `functions/chunker.py` - Chunking
- `functions/config.py` - Model pricing
- `gui/helpers/chunker_adapter.py` - Bridge

### Step 3: Information
**GUI Module:** `gui/steps/information.py`  
**Functions Used:**
- `functions/project_config.py` - Project settings
- `functions/glossary.py` - Glossary management
- `functions/style_presets.py` - Style presets
- `functions/API2Glossary.py` - LLM enrichment
- `gui/helpers/glossary_adapter.py` - Bridge

### Step 4: Preprocessing
**GUI Module:** `gui/steps/preprocess.py`  
**Functions Used:**
- `functions/mainhelper.py` - Processor
- `functions/dedup.py` - Deduplication
- `modi/*.py` - All preprocessing modes
- `gui/helpers/mode_adapter.py` - Bridge

### Step 5: Translation
**GUI Module:** `gui/steps/translate.py`  
**Functions Used:**
- `functions/api_client.py` - API client
- `functions/prompt_builder.py` - Prompt building
- `functions/rate_limiter.py` - Rate limiting
- `functions/request_cache.py` - Caching
- `functions/retry_handler.py` - Retry handling
- `functions/key_manager.py` - Key management
- `functions/conditional_prompts.py` - Conditional prompts
- `functions/mock_translator.py` - Mock translation
- `functions/batch_tracker.py` - Batch API
- `gui/helpers/prompt_adapter.py` - Bridge

### Step 6: Postprocessing
**GUI Module:** `gui/steps/postprocess.py`  
**Functions Used:**
- `functions/postprocess.py` - Recovery
- `functions/mainhelper.py` - Processor
- `modi/*.py` - All postprocessing modes

### Step 7: Wordwrap
**GUI Module:** `gui/steps/wordwrap_overwrite.py`  
**Functions Used:**
- `functions/wordwrap.py` - Wordwrap engine

### Step 8: QA
**GUI Module:** `gui/steps/qa.py`  
**Functions Used:**
- `functions/validation.py` - Validation
- `functions/consistency.py` - Term consistency
- `functions/postanalysis.py` - Analysis

### Step 9: Output/Inject
**GUI Module:** `gui/steps/output_inject.py`  
**Functions Used:**
- `formats/__init__.py` - Registry
- `formats/simple.py` - Format handlers
- `functions/output.py` - Priority resolution
- `functions/replication.py` - Update detection
- `functions/mainhelper.py` - Write utilities

---

## Part 9: Issues - Duplicates, Orphans, and Discrepancies

### 9.1 Duplicate Functions

| Function | Location 1 | Location 2 | Issue |
|----------|------------|------------|-------|
| `setup_logger()` | CherryAI.py | mainhelper.py | Delegate wrapper - OK |
| `read_text()` | CherryAI.py | mainhelper.py | Delegate wrapper - OK |
| `write_text()` | CherryAI.py | mainhelper.py | Delegate wrapper - OK |
| `read_table()` | CherryAI.py | mainhelper.py | Delegate wrapper - OK |
| `read_json_pairs()` | CherryAI.py | mainhelper.py | Delegate wrapper - OK |
| `derive_output_path()` | CherryAI.py | mainhelper.py | Delegate wrapper - OK |
| `count_tokens()` | costs.py (GUI) | chunker_adapter.py | Duplicated in GUI step |
| `estimate_cost()` | costs.py (GUI) | estimation.py | Duplicated in GUI step |

**Assessment:** CherryAI.py delegates are intentional for backward compatibility. The costs.py duplications should be reviewed for consolidation into chunker_adapter.py.

### 9.2 Potential Orphaned Modules

| Module | Issue |
|--------|-------|
| `functions/options.py` | Has `OptionsDialog` class but GUI uses `gui/dialogs/global_options.py` |
| `gui/steps/estimate.py` | Just re-exports from costs.py - could be removed |
| `formats/document.py` | Placeholder (not implemented) |
| `formats/rpgmakermvmz.py` | Implemented RPG Maker MV/MZ parser and handlers |
| `modi/template_mode.py` | Skipped by mode registry |

### 9.3 Documentation Discrepancies

| Category | Documentation Says | Actual Count | Diff |
|----------|-------------------|--------------|------|
| functions/ modules | 36 (+ 5 glossaries/) | 46 + 5 | +10 |
| formats/ modules | 5-7 | 10 | +3-5 |
| gui/helpers/ | 6 | 8 | +2 |
| gui/dialogs/ | 3 | 5 | +2 |

**Undocumented in technical.md:**
- `functions/agent_modes.py`
- `functions/auto_pipeline.py`
- `functions/batch_tracker.py`
- `functions/chunk_optimizer.py`
- `functions/key_manager.py`
- `functions/local_llm.py`
- `functions/output.py`
- `functions/process_order.py`
- `functions/usage_tracker.py`
- `formats/json_lenient.py`
- `formats/rpgmakermvmz.py`
- `gui/helpers/tooltip.py`
- `gui/dialogs/loading_progress.py`

### 9.4 GUI Integration Status

**Integration Architecture:**
The GUI v2 integrates with modi/ modules through `gui/helpers/mode_adapter.py` which 
provides a bridge layer. Processing steps import from mode_adapter rather than 
directly from modi/.

**Integration Detail by Mode:**

| Modi Mode | Documented | GUI v2 Status | Integration Details |
|-----------|------------|---------------|---------------------|
| standard_mode.py | ✅ | ✅ Partial | via mode_adapter: ellipsis_compress_text(), symbol_convert_text() |
| protect_code.py | ✅ | ✅ Partial | via mode_adapter: apply_protect_code(), save/load_protect_code_patterns() |
| custom_placeholder.py | ✅ | ❌ | No adapter functions, manual config only |
| anchor.py | ✅ | ❌ | No adapter functions |
| free.py | ✅ | ❌ | No adapter functions |
| only_remove.py | ✅ | ❌ | No adapter functions |
| replace_after.py | ✅ | ❌ | No adapter functions |
| replace_before.py | ✅ | ❌ | No adapter functions |
| sabotage.py | ✅ | ❌ | No adapter functions |
| temporary_replacement.py | ✅ | ❌ | No adapter functions |
| template_mode.py | ✅ | ❌ | No adapter functions |
| dedup.py | ✅ | ✅ Full | via functions/dedup.py, integrated in preprocess.py |

**mode_adapter.py Exports:**
```
Ellipsis: ellipsis_compress_text(), ellipsis_decompress_text()
Symbols: symbol_convert_text(), symbol_revert_text() 
PROT: compress_prot_tokens(), decompress_prot_tokens()
Protect Code: apply_protect_code(), save/load_protect_code_patterns()
```

**Preprocessing (Step 4) Integration:**
- Uses mode_adapter for: ellipsis compression, symbol conversion, protect_code patterns
- Direct dedup_lines() via functions/dedup.py
- Config-driven enable/disable for each preprocessing option
- Changes stored in manifest prepro_ops field

**Postprocessing (Step 6) Integration:**
- Uses functions/postprocess.py recover_line(), NOT direct modi/ imports
- Restores PROTECTED tokens, ellipses, symbols from prepro_ops
- Status tracking per-line with recovery issues

**Note:** technical.md marks most modi as "❌ Not integrated with GUI v2" but 
standard_mode, protect_code, and dedup ARE integrated via adapter layers

### 9.5 Missing Cross-References

| functions/ Module | Expected GUI Usage | Status |
|-------------------|-------------------|--------|
| agent_modes.py | Step 4 or Global | Not integrated |
| auto_pipeline.py | Cross-step automation | Documented but unclear |
| local_llm.py | Step 5 alternatives | Not referenced in steps |
| usage_tracker.py | Analytics display | No GUI component |

---

## Summary Statistics

| Directory | Files | Classes | Functions |
|-----------|-------|---------|-----------|
| Root | 3 | 2 | ~25 |
| functions/ | 46 | ~90 | ~300 |
| functions/glossaries/ | 5 | 0 | ~15 |
| modi/ | 12 | 0 | ~30 |
| formats/ | 10 | ~15 | ~25 |
| gui/ | 3 | 6 | 0 |
| gui/steps/ | 13 | ~50 | 4 |
| gui/helpers/ | 8 | 7 | ~60 |
| gui/dialogs/ | 5 | ~15 | 0 |
| gui/components/ | 2 | 3 | 0 |
| gui/state/ | 2 | 3 | ~5 |
| gui/theme/ | 3 | 3 | ~8 |
| **Total** | **113** | **~195** | **~470** |
