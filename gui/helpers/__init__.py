"""GUI Helper modules for CherryAI.

Provides adapter layers and utility functions for GUI components.
"""

from CherryAI.gui.helpers.mode_adapter import (
    apply_ellipsis_compression,
    apply_symbol_conversion,
    apply_prot_compression,
    apply_protect_code,
    apply_custom_placeholder,
    apply_preprocessing,
    get_common_patterns,
    get_available_modes,
)

from CherryAI.gui.helpers.analysis_adapter import (
    detect_language,
    detect_language_batch,
    detect_code_patterns,
    detect_code_patterns_batch,
    detect_speaker_in_line,
    detect_speakers_batch,
    summarize_lines,
    count_duplicates,
    count_tokens,
    count_tokens_batch,
    analyze_lines,
)

from CherryAI.gui.helpers.manifest_binding import (
    # Classes
    BindingInfo,
    # Registry functions (for testing)
    clear_binding_registry,
    get_binding_registry,
    get_binding_for_field,
    # Binding functions
    bind_entry_to_field,
    bind_checkbox_to_field,
    bind_combobox_to_field,
    bind_spinbox_to_field,
    bind_text_to_field,
    bind_radio_group_to_field,
    bind_float_spinbox_to_field,
    # Utility functions
    load_all_bindings,
)

from CherryAI.gui.helpers.chunker_adapter import (
    # Constants
    DEFAULT_CHUNK_MODE,
    DEFAULT_MAX_LINES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_RPM,
    DEFAULT_TPM,
    DEFAULT_RPD,
    ERROR_THRESHOLD_WARNING,
    ERROR_THRESHOLD_REDUCE,
    # View Classes
    ChunkModeView,
    ChunkConfigView,
    ChunkResultView,
    RateLimitView,
    TimeEstimateView,
    OptimizerStatsView,
    # Token Functions
    count_tokens as chunker_count_tokens,
    count_tokens_batch as chunker_count_tokens_batch,
    is_tiktoken_available,
    # Chunking Functions
    get_chunk_modes,
    create_chunk_config,
    chunk_lines,
    estimate_chunks,
    # Rate Limiting Functions
    get_model_rate_limits,
    get_all_model_limits,
    estimate_rate_limit_time,
    estimate_time_for_model,
    # Optimizer Functions
    create_optimizer_stats,
    get_adaptive_chunk_size,
    get_optimizer_recommendation,
    # Combined Functions
    estimate_translation_job,
)

from CherryAI.gui.helpers.glossary_adapter import (
    # Data classes
    GlossaryEntryView,
    StylePresetView,
    # Constants
    TYPE_NAME,
    TYPE_LOCATION,
    TYPE_TERM,
    TYPE_CODE,
    GENDER_MALE,
    GENDER_FEMALE,
    GENDER_NEUTRAL,
    GENDER_UNKNOWN,
    MAX_SUMMARY_CHARS,
    # Glossary functions
    load_glossary,
    save_glossary,
    add_glossary_entry,
    get_glossary_entries_by_type,
    get_glossary_names,
    get_glossary_stats,
    search_glossary,
    # Style preset functions
    get_style_presets,
    get_style_preset_names,
    get_style_preset_by_name,
    get_style_preset_prompt,
    get_presets_by_category,
    # Project config functions
    create_project_config,
    load_project_config,
    get_project_api_overrides,
    # Character functions
    get_characters_from_glossary,
    sync_characters_to_glossary,
)

from CherryAI.gui.helpers.prompt_adapter import (
    # Constants
    DEFAULT_ROLLING_CONTEXT_LINES,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_MIN_BATCH_SIZE,
    DEFAULT_MAX_STYLE_CHARS,
    DEFAULT_RETRY_STRATEGY,
    DEFAULT_MAX_RETRIES,
    DEFAULT_CONTEXT_LINES,
    # View Classes
    RetryStrategyView,
    ConditionalPromptView,
    PromptPreviewView,
    RollingContextView,
    RetryConfigView,
    RetryResultView,
    BatchRetryResultView,
    # Translation style functions
    get_translation_style,
    format_style_section,
    get_game_summary,
    # Quote stripping functions
    strip_quotes_from_lines,
    restore_quotes_to_lines,
    # Conditional prompt functions
    get_builtin_conditions,
    evaluate_conditions_for_batch,
    build_conditional_instructions,
    # Retry handler functions
    get_retry_strategies,
    get_strategy_info,
    create_retry_config,
    handle_failed_lines,
    # Prompt builder functions
    build_prompt_preview,
    create_prompt_builder,
    get_rolling_context_config,
    format_rolling_context_section,
)

__all__ = [
    # Mode adapter
    "apply_ellipsis_compression",
    "apply_symbol_conversion",
    "apply_prot_compression",
    "apply_protect_code",
    "apply_custom_placeholder",
    "apply_preprocessing",
    "get_common_patterns",
    "get_available_modes",
    # Analysis adapter
    "detect_language",
    "detect_language_batch",
    "detect_code_patterns",
    "detect_code_patterns_batch",
    "detect_speaker_in_line",
    "detect_speakers_batch",
    "summarize_lines",
    "count_duplicates",
    "count_tokens",
    "count_tokens_batch",
    "analyze_lines",
    # Chunker adapter - Constants
    "DEFAULT_CHUNK_MODE",
    "DEFAULT_MAX_LINES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_RPM",
    "DEFAULT_TPM",
    "DEFAULT_RPD",
    "ERROR_THRESHOLD_WARNING",
    "ERROR_THRESHOLD_REDUCE",
    # Chunker adapter - View Classes
    "ChunkModeView",
    "ChunkConfigView",
    "ChunkResultView",
    "RateLimitView",
    "TimeEstimateView",
    "OptimizerStatsView",
    # Chunker adapter - Token Functions
    "chunker_count_tokens",
    "chunker_count_tokens_batch",
    "is_tiktoken_available",
    # Chunker adapter - Chunking Functions
    "get_chunk_modes",
    "create_chunk_config",
    "chunk_lines",
    "estimate_chunks",
    # Chunker adapter - Rate Limiting Functions
    "get_model_rate_limits",
    "get_all_model_limits",
    "estimate_rate_limit_time",
    "estimate_time_for_model",
    # Chunker adapter - Optimizer Functions
    "create_optimizer_stats",
    "get_adaptive_chunk_size",
    "get_optimizer_recommendation",
    # Chunker adapter - Combined Functions
    "estimate_translation_job",
    # Glossary adapter - Data classes
    "GlossaryEntryView",
    "StylePresetView",
    # Glossary adapter - Constants
    "TYPE_NAME",
    "TYPE_LOCATION",
    "TYPE_TERM",
    "TYPE_CODE",
    "GENDER_MALE",
    "GENDER_FEMALE",
    "GENDER_NEUTRAL",
    "GENDER_UNKNOWN",
    "MAX_SUMMARY_CHARS",
    # Glossary adapter - Glossary functions
    "load_glossary",
    "save_glossary",
    "add_glossary_entry",
    "get_glossary_entries_by_type",
    "get_glossary_names",
    "get_glossary_stats",
    "search_glossary",
    # Glossary adapter - Style preset functions
    "get_style_presets",
    "get_style_preset_names",
    "get_style_preset_by_name",
    "get_style_preset_prompt",
    "get_presets_by_category",
    # Glossary adapter - Project config functions
    "create_project_config",
    "load_project_config",
    "get_project_api_overrides",
    # Glossary adapter - Character functions
    "get_characters_from_glossary",
    "sync_characters_to_glossary",
    # Prompt adapter - Constants
    "DEFAULT_ROLLING_CONTEXT_LINES",
    "DEFAULT_MAX_BATCH_SIZE",
    "DEFAULT_MIN_BATCH_SIZE",
    "DEFAULT_MAX_STYLE_CHARS",
    "DEFAULT_RETRY_STRATEGY",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_CONTEXT_LINES",
    # Prompt adapter - View Classes
    "RetryStrategyView",
    "ConditionalPromptView",
    "PromptPreviewView",
    "RollingContextView",
    "RetryConfigView",
    "RetryResultView",
    "BatchRetryResultView",
    # Prompt adapter - Translation style functions
    "get_translation_style",
    "format_style_section",
    "get_game_summary",
    # Prompt adapter - Quote stripping functions
    "strip_quotes_from_lines",
    "restore_quotes_to_lines",
    # Prompt adapter - Conditional prompt functions
    "get_builtin_conditions",
    "evaluate_conditions_for_batch",
    "build_conditional_instructions",
    # Prompt adapter - Retry handler functions
    "get_retry_strategies",
    "get_strategy_info",
    "create_retry_config",
    "handle_failed_lines",
    # Prompt adapter - Prompt builder functions
    "build_prompt_preview",
    "create_prompt_builder",
    "get_rolling_context_config",
    "format_rolling_context_section",
    # Manifest binding - Classes
    "BindingInfo",
    # Manifest binding - Registry functions (testing)
    "clear_binding_registry",
    "get_binding_registry",
    "get_binding_for_field",
    # Manifest binding - Binding functions
    "bind_entry_to_field",
    "bind_checkbox_to_field",
    "bind_combobox_to_field",
    "bind_spinbox_to_field",
    "bind_text_to_field",
    "bind_radio_group_to_field",
    "bind_float_spinbox_to_field",
    # Manifest binding - Utility functions
    "load_all_bindings",
]
