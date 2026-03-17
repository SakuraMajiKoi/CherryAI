# CherryAI Specification Document

Version 3.0 | February 2026

This document provides a complete functional specification of CherryAI, an LLM-based translation application designed to achieve high-quality translations using Large Language Models. The application requires substantial input and processing which can optimally be performed automatically once an input is selected.

These specs describe every component, data flow, user interaction, and file dependency in detail suitable for both human users and AI assistants.

---

## Terminology

CherryAI features terms that may not be clear at first glance or slightly differ from normal definitions:
- Steps: Tabs in the GUI which guide through the translation pipeline and have their own interface 
- Widgets: Elements that make up the Steps / Tabs and are filled with buttons, tables, dropdowns &c. 
- Manifest: Refers to the file that is created and update for each project. It functions as save file that contains all information and processes. See 7. for what it all entails.
- API: The API is between the user and the LLM. CherryAI -> API -> LLM -> API CherryAI.
- LLM: Large Language Model, a predictive software that calculates output based on input, settings and its own knowledge base. Excellent at natural language but costs more time and resources than previous technology.
- Model: Countless LLM are developed, refined and literally cut. Performance between them vastly differs.
- Cloud / Local LLM: LLM require a lot of RAM, specifically VRAM, to work and they can be run on one's own device for pretty much free. Cloud Providers offer their hardware and resource for a price that usually depends on Input and Output Tokens.
- Tokens: Not characters or words but the metric and data LLM work with. Simply out, tokens are categorized based on their meaning. The application also features tokens that temporarily replace code during translation for protection and context
- Request: The entirity sent to the API: Metainformation, Prompt and Input Lines.
- Metainformation: The part of the Request that is not counted and instead has the API apply various settings.
- Prompt: The part of the Request that contains context that manipulates the weights and probability for a better translation.
- System Instructions: Part of the Prompt, always present.
- Conditional: Certain criteria must be met for that part of the prompt to appear.
- Selectively: When a condition is met, selected parts are provided in the prompt. Usually the part that triggers the condition.
- Rolling Context: Lines that directly preceed those that will be translated. Conditional. 
- Glossary: Conditionally and selectively used to achieve consistent translations for terms and provides further information primarily for characters and location. Part of the Prompt
- Code Database: Conditionally and selectively used to deal with code.
- Editing: Optional process that is done to ensure that a translation has no problems.
- TLC: Translation Check. Optional process that specifically ensures that a translation is accurate.
- Deduplication: Deals with lines that occur more than once and prevents them from being translated entirely. Various settings allow for more or less aggressive techniques.
- Placeholders: A system designed to deal with code by having it replaced with placeholders and recovered before Injection.
- Anchoring: Similar purpose as Placeholders except that the code can be entirely removed and readded safely where it should be. Requires Anchor characters like punctuation or line start/end.
- Parsing / Extraction & Input / Injection & Output: Parsing entails both processes that deal with what is first loaded into CherryAI and what is finally produced. 

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Flow Summary](#2-data-flow-summary)
3. [External Files and Storage](#3-external-files-and-storage)
4. [Global Options](#4-global-options)
5. [Cross-Step Specifications](#5-cross-step-specifications)
   - [5.1 Speaker:Dialogue Format](#51-speakerdialogue-format)
   - [5.2 API Request Building and Formation](#52-api-request-building-and-formation)
   - [5.3 Context Markers](#53-context-markers)
   - [5.4 Lines to Translate Rules](#54-lines-to-translate-rules)
   - [5.5 Rolling Context](#55-rolling-context)
   - [5.6 Glossary Selective Inclusion](#56-glossary-selective-inclusion)
   - [5.7 Code Database Extended Properties](#57-code-database-extended-properties)
   - [5.8 Parser Scripts](#58-parser-scripts)
   - [5.9 Pre/Post Processing Priority System](#59-prepost-processing-priority-system)
   - [5.10 Wordwrap Extended Rules](#510-wordwrap-extended-rules)
   - [5.11 Point of View Inference](#511-point-of-view-inference)
   - [5.12 Consistency System](#512-consistency-system)
   - [5.13 Mock Translation Extended](#513-mock-translation-extended)
6. [GUI Mode: Step-by-Step Specification](#6-gui-mode-step-by-step-specification)
   - [Step 0: Input](#step-0-input)
   - [Step 1: Analysis](#step-1-analysis)
   - [Step 2: Information](#step-2-information)
   - [Step 3: Preprocessing](#step-3-preprocessing)
   - [Step 4: Costs](#step-4-costs)
   - [Step 5: Translation](#step-5-translation)
   - [Step 6: Postprocessing](#step-6-postprocessing)
  - [Step 7: Quality Assurance](#step-7-quality-assurance)
  - [Step 8: Wordwrap](#step-8-wordwrap)
   - [Step 9: Output](#step-9-output)
7. [CLI Mode: Automatic Pipeline](#7-cli-mode-automatic-pipeline)
8. [Manifest Structure](#8-manifest-structure)
9. [Processing Modules Reference](#9-processing-modules-reference)
10. [Pipeline Logging System](#10-pipeline-logging-system)

---

## 1. Architecture Overview

CherryAI is designed to achieve high-quality translation using LLMs through extensive input processing and automation. The application separates concerns into four layers:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| GUI | `gui/` | Display, user interaction, widget binding (10 workflow steps/tabs) |
| Processing | `functions/` | Core logic, translation, validation |
| Modes | `modi/` | Pre/post-processing transformations |
| Formats | `formats/` | File I/O for TXT, CSV, JSON, XLSX, RPG Maker, Light VN, Images |

**Critical Rule:** GUI code contains NO processing logic. All text manipulation occurs in `functions/` or `modi/`. Both GUI and CLI share identical processing paths.

### GUI Structure

The GUI is organized as:
- **Menu Bar**: File (dropdown), Full Table View (direct command), API Log (direct command), Options (direct command), Help (dropdown)
  - **New Project** (`_on_new_session`): Resets ManifestManager (creates empty manifest), resets SessionState, and calls `on_new_project()` on ALL step tabs to flush cached instance state (loaded files, analysis results, lines, estimation data, etc.). Prevents old project data from leaking into the new session.
  - **Open Project...** (`_on_load_manifest` / `_load_manifest_from_path`): After the unsaved-changes prompt, loads the selected manifest into a fresh ManifestManager, swaps it in only after successful load, resets SessionState, and calls `on_new_project()` on ALL tabs before entering the saved step. This must behave like New Project plus manifest activation, so an already-open project can never leak cached state into the newly opened project.
- **Full Table View** (`_on_full_table_view`): Opens FullTableViewDialog — spreadsheet-like view and editor for all manifest line entries. Requires a loaded project. Features: named columns (Line #, Original, Preprocessed, Translated, Postprocessed, Quality Assurance, Overwrite, Wordwrap, Overwrite (Legacy), Log, Tags), column filter dropdown with Show All/Show Visible/Show Latest presets, all columns hideable, column selection bar for search/replace scoping, sort indicators (▲/▼) in headers, read-only Original with copy support, two-row search/replace toolbar, Results Only mode, file filter, RegEx search/replace, pagination, save/reset/diff, and a Clear Columns workflow for `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, and `wordwr`. Clearing `tl` must require a second destructive confirmation because it removes the base translation stage. Show Latest follows the active pipeline `orig → prepro → tl → postpro → qa → qa_overwrite → wordwr`.
- **API Log** (`_on_api_log`): Opens APILogViewDialog — non-blocking viewer for structured API log entries. Requires a loaded project. Features: search bar, category filter (Main Translation/Term Translation/Gender Inference/Other), view mode switch (Sent/Received/Both), display-limit spinbox (All/1000/2500/5000/Nothing), color-coded entries (green=success, yellow=recovered, red=failed), live updates via subscription, token statistics, per-project JSONL persistence alongside manifest. Sent entries must show actual request metadata from the stored log, including OpenAI `prompt_cache_key` / `prompt_cache_retention` when present. Reopening API Log must reuse the existing window and bring it to the foreground instead of opening duplicates.
- **Options** (`_on_options`): Opens Global Options dialog directly from menu bar. Reopening Options must reuse the existing dialog and bring it to the foreground instead of opening duplicates.
- **Step Tabs**: 10 workflow tabs (Steps 0-9) progressing from Input to Output
- **Global Options**: Application-wide settings accessed via Options menu bar entry
- **Progress Tracker**: Visual indicator showing completion status of each step

### Module Counts

- `functions/`: 36 modules (core processing)
- `providers/`: 7 LLM provider modules (Provider Handshake — unified provider interface)
- `modi/`: 12 pre/post-processing modes
- `formats/`: 5+ file format handlers (expanding to support images and game engines)
- `gui/steps/`: 10 workflow tabs
- `gui/helpers/`: 6 adapter modules
- `gui/dialogs/`: 7 dialog modules (incl. table_view.py, api_log_view.py)

### State Management

All application state is stored in the Manifest (`.CherryAI.json`), not in GUI memory. For every translation project, a manifest file is created which loads all project data and saves all process steps. The ManifestManager handles:
- Auto-save on step change, close, and periodic interval (60s default)
- Atomic saves: write to `.tmp`, fsync, `os.replace()` to prevent corruption; retry loop (3 attempts with back-off) handles transient Windows file locks
- Thread-safe saves: `save()` acquires `_autosave_lock` to prevent races between autosave thread and main thread
- Skip-unchanged guard: `set_line_field()` returns early when new value equals existing (TASK 72)
- Per-step data storage with automatic serialization
- Line-by-line translation state tracking with per-line `tags` field (TASK 72)
- Manifest line canonicalization on load/save/set: legacy `tag` is merged into `tags`, dedup placeholder rows cannot retain translation-stage outputs, and line keys are written in canonical order `idx`, `tags`, `orig`, `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, `wordwr`, then auxiliary fields
- Project recovery and session restoration
- Step data merge-not-replace: `on_leave()` and `_update_step_data()` must start from `get_step_data()` and merge updated keys — never create a fresh dict that discards stored results (PHASE 80)
- Init guard pattern: steps that populate comboboxes during `__init__()` must suppress trace-triggered manifest writes until initialization completes (PHASE 80)
- Conditional text replacement: `_ensure_*_text()` helpers must only delete existing widget content when replacement text is available (PHASE 80)

---

## 2. Data Flow Summary

CherryAI processes text through a 10-step pipeline. Each step produces outputs that feed into subsequent steps. Once an input is selected, the entire pipeline can run automatically based on configured settings.

```
User Files (TXT/CSV/JSON/XLSX/RPG Maker/Images)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 0: Input          │ Load files, detect format         │
│  Produces: lines[].orig │ Store in manifest filedir         │
│  Auto-Trigger: Analysis │ Starts pipeline when files loaded │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: Analysis       │ Count lines, detect duplicates    │
│  Produces: stats,       │ language, speakers, code patterns │
│  findings[]             │ (Runs automatically if enabled)   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: Information    │ Project metadata, style, tone     │
│  Produces: metadata{},  │ characters[], code_glossary[]     │
│  prompt_context         │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Preprocessing  │ Dedup, placeholders, protect code │
│  Produces: prepro[],    │ prepro_ops[], dedup_map, tags[]   │
│  protected_patterns     │ (Runs automatically if enabled)   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Costs          │ Token count, cost projection      │
│  Produces: token_count, │ cost_original, cost_preprocessed  │
│  time_estimate          │ (Two-state: Original + Prepro)    │
│  Auto-Trigger: On load  │ Auto-Trigger: After Preprocessing │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: Translation    │ Send chunks to LLM, receive tl    │
│  Produces: tl[],        │ tokens_used, cost_actual          │
│  tlc[], edit[]          │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 6: Postprocessing │ Restore placeholders, symbols     │
│  Produces: postpro[],   │ recovery_stats, retry_list        │
│  validation_result      │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7: QA             │ Manual review, validation UI      │
│  Produces: qa[],        │ qa_overwrite[], issues[]          │
│  report_data            │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 8: Wordwrap       │ Line breaking, typography         │
│  Produces: wordwr[],    │ wrap_stats, break_positions       │
│  merge_preview          │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 9: Output         │ Write files, inject translations  │
│  Produces: output_files │ Injects into original file copies │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
Translated Files (Same format as input, injected into copies)
```

### Automation Triggers

When global options enable automation, loading files triggers a cascade:
1. **Input** → Files loaded → Triggers Analysis
2. **Analysis** → Complete → Triggers Auto-Estimation (Original)
3. **Costs** → Original estimation → First tick complete
4. **Preprocessing** → Complete → Triggers Auto-Estimation (Preprocessed)
5. **Costs** → Preprocessed estimation → Second tick complete
6. **Translation** → Complete → Triggers QA and Postprocessing
7. **Output** → Injects translations into copies of original files

**Estimation State Tracking:**
- Costs step has two progress indicators (ticks)
- First tick: Original estimation complete (from raw input)
- Second tick: Preprocessed estimation complete (after Step 4)
- Ticks reset when relevant settings change (prompt, preprocessing)
- **Model change does NOT trigger re-estimation** — stored token counts
  (content_tokens, prompt_tokens, cached_tokens, input_tokens, output_tokens,
  num_requests) are reused; only pricing/rate-limit arithmetic is repeated.
  Full re-estimation is only triggered by the "↻ Update Counts" button.

---

## 3. External Files and Storage

### 3.1 Configuration Files

| File | Location | Purpose | Format |
|------|----------|---------|--------|
| `CherryAI.ini` | `user/` | General config, defaults, UI state, last manifest; all non-meta prompt content (system instructions, style, tone, summary, conditionals) | INI |
| `API.ini` | `user/` | All API meta settings: encrypted keys, model, temperature, URL, provider profiles (AES-256 via master password) | INI |
| `api_profiles.ini` | Project root | **DEPRECATED — consolidated into `user/API.ini` in Phase 62.** Renamed to `.migrated` on first load. | INI |
| `_FACTORY_DEFAULTS_INI_TEXT` | `functions/ini_manager.py` | Factory default settings embedded as constant; auto-seeds `CherryAI.ini` on first load | Python constant |
| `.vscode/settings.json` | `.vscode/` | VS Code analysis paths | JSON | Dev only
| `pyrightconfig.json` | Project root | Type checking config | JSON | Dev only

### 3.2 Project Files

| File | Location | Purpose | Format |
|------|----------|---------|--------|
| `*.CherryAI.json` | `Projects/` | Project manifest (all state) | JSON |
| `globalglossary.tsv` | `user/` | Global translation glossary: three columns — Original, Translation, Notes | TSV |
| `codedatabase.tsv` | `user/` | Global code pattern database: Pattern, Type, RegEx, Notes, Visibility, and extended properties | TSV |
| `speakers.analysis.tsv` | Auto-generated | Speaker name mappings | TSV |
| `code.analysis.tsv` | Auto-generated | Code pattern analysis | TSV |

### 3.3 Temporary Files

| File | Location | Purpose | Lifecycle |
|------|----------|---------|-----------|
| `gui_session_autosave.json` | `temp/` | Legacy session backup | Cleared on new project |
| `*.cache` | `temp/cache/` | Request cache | Max 24h / 100MB |
| `api_log_*.txt` | `logs/` | API request/response logs | Persistent per session |
| `cherryai.log` | `logs/` | Application log | Rolling |

### 3.4 User Data

| Directory | Purpose |
|-----------|---------|
| `user/` | User glossary, custom templates |
| `Projects/` | All project manifests |
| `output/` | Default translation output location |
| `templates/` | Prompt and style templates |

---

## 4. Global Options

Global Options are application-wide settings accessed via Tools → Options. They are NOT saved per-project in the manifest.

### 4.1 Settings Categories

#### API Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Provider | enum | openai | API provider (openai, gemini, anthropic, local, ollama, lmstudio) |
| API Key | secret | "" | Authentication key |
| Base URL | url | Provider default | Custom endpoint URL |
| Model | string | gpt-4o-mini | Model identifier |
| Temperature | float | 0.3 | Generation temperature (0.0-2.0) |

#### Request Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Timeout | int | 60 | Request timeout in seconds |
| Retries | int | 3 | Max retry attempts |
| Rate Limit | int | 60 | Requests per minute |
| Chunk Size | int | 50 | Lines per API request (1–99999) |
| Max Input Tokens | int | 0 | Maximum token count for input lines per request (0 = no limit; counts input lines only, not prompt/meta) |

#### Translation Settings (NEW)
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Overwrite Translation | bool | false | Re-translate already translated lines (inverse of skip-translated) |
| Skip Non-Source Language | bool | true | Skip lines not detected as source language |
| Retry Strategy | enum | batch | Retry mode for failed chunks (batch/contextual/isolated/skip) |
| Request Slicing | enum | conservative | Request formation aggressiveness (conservative/efficient) |

**Request Slicing Modes:**
- **Conservative** (default): `min_lines = max(2, chunk_size // 5)` — more granular requests, respects file boundaries strictly.
- **Efficient**: `min_lines = max(5, chunk_size // 2)` — merges small requests more aggressively across file boundaries (Step 5), reducing total API calls. Invokes slot 8b Merged-Request Instruction for combined requests.

**Per-Model Settings Priority (Translation & Preview):**
- `_load_model_settings()` loads chunk_size, temperature, rolling_context_before/between/after, thinking from per-model API.ini `[model_settings]` via `get_model_settings(model_id)`, falling back to Global Options when no per-model entry exists. Called on tab entry after `_sync_from_global_options()`.
- `_build_preview_requests()` syncs `_translation_options` from current UI values before calling `_build_chunks()`, ensuring Preview Requests uses live settings.
- `_build_chunks()` reads rolling_context_between, rolling_context_after, and chunk_max_tokens from per-model API.ini via `get_model_settings()`, falling back to Global Options `go.request.*`.
- Rolling context "before" in Preview reads per-model `rolling_context_before` from API.ini, falling back to Global Options.
- Priority chain: Per-model API.ini `[model_settings]` → Global Options CherryAI.ini `[request]`/`[translation]` → dataclass defaults.

**Code-Only Skip Condition:**
Lines consisting entirely of preserved code patterns (code_patterns with `action="preserve"`) are automatically skipped during both Estimation and Translation. The `<NUM>` wildcard in patterns matches concrete numbers (e.g. `<文字色 <NUM> <NUM> <NUM>>` matches `<文字色 255 50 50>`). This avoids sending non-translatable code-only lines to the LLM.

#### Caching Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Enabled | bool | true | Enable request caching |
| Cache Dir | path | temp/cache | Cache file location |
| Max Age | int | 24 | Cache expiry in hours |
| Max Size | int | 100 | Max cache size in MB |

#### Session Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Autosave Enabled | bool | true | Enable periodic autosave |
| Autosave Interval | int | 60 | Autosave interval in seconds |
| Restore on Launch | bool | true | Restore last project on start |
| Auto-analyze on Load | bool | true | Run analysis after file load |
| Auto-preprocess on Load | bool | true | Run preprocessing after analysis |

**Restore on Launch (Phase 58.11, updated Phase 60):**
- Accessible via GlobalOptions (Session section) and WelcomeDialog checkbox
- WelcomeDialog checkbox always visible (not conditional on Resume option availability)
- Loads current INI setting on display; saves immediately on toggle
- Setting stored in `[session].load_last` for app startup behavior
- GlobalOptions reads from and writes to `[session]` section for sync

#### Safety Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Banned Tokens | list | [em_dash, smart_quotes] | Tokens to ban via logit bias |
| Content Warning | bool | true | Warn on explicit content |
| Max Output Tokens | int | 4096 | Maximum output token limit |

#### File I/O Settings
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Default Encoding | enum | utf-8 | File encoding |
| Line Ending | enum | auto | Line ending style |
| Preserve BOM | bool | true | Keep UTF-8 BOM if present |
| Backup Originals | bool | true | Create backup before overwrite |

### 4.2 Data Source

Global options are loaded from and saved to `CherryAI.ini`. The `GlobalOptions` dataclass in `gui/dialogs/global_options.py` provides the in-memory representation.

`GlobalOptions.load_from_ini()` loads **all** settings sections (API, Request, Translation, Caching, Logging, Session, Limit, FileIO, Utility, Prompts) using `get_effective_default()` which resolves user defaults → factory defaults → dataclass fallback. This ensures the GUI always reflects the actual INI values, including user overrides set via `[user_defaults]`.

All INI writes use atomic saves (write to `.tmp`, fsync, `os.replace()`) via `ini_manager._save_ini()` to prevent file corruption. The `[ui] state` section is managed by centralized `ini_manager.load_ui_state()` / `save_ui_state()` functions that use the shared in-memory cache, preventing scenarios where a UI state save could wipe other sections.

`CherryAI.ini` is auto-seeded from the embedded `_FACTORY_DEFAULTS_INI_TEXT` constant in `ini_manager.py` on first load via `_populate_from_defaults()`. Conditional context-type prompts (dialogue/menu/choice/unknown) are initialised from the `[conditional_prompts]` section of the embedded constant and stored in the `[prompts]` section of `CherryAI.ini`. They are configurable via **Global Options → Prompts** and are used at translation time by `get_context_prompt()` in `prompt_builder.py`.

---

## 5. Cross-Step Specifications

The following systems span multiple pipeline steps. They are documented here as cross-cutting concerns rather than within any single step, since their behaviour affects analysis, preprocessing, request building, translation, postprocessing, and output.

---

### 5.1 Speaker:Dialogue Format

**Implementation Status:** ✅ Phase 51 DONE — All 4 tasks implemented (47 tests passing, 5100 total suite)

**Affects**: Analysis (Step 1), Preprocessing (Step 4), Translation (Step 5), Postprocessing (Step 6), Wordwrap (Step 7), QA (Step 8)

**Purpose**: CherryAI uses the `Speaker: "Dialogue"` and `Speaker: Dialogue` formats throughout the pipeline as a structural indicator. Speaker detection is performed during Analysis and the format is preserved or leveraged in every subsequent step.

#### Detection

- Uses Speaker Inference from `functions/validation.py`
- Matches the `:` separator and its fullwidth equivalent `：` to catch all occurrences with minimal false positives
- Speaker names are validated against the character glossary when available
- **Enhanced validation rules** reduce false positives:
  - Balanced brackets: all bracket/paren types (ASCII + CJK) must be paired; rejects skill descriptions like `〈戦闘中回数制限:`
  - No-newline: colon must appear on the first line; multiline text before a colon is rejected
  - Length limit: speaker names must be ≤30 chars (Latin-dominant) or ≤20 chars (CJK-dominant); rejects long NPC descriptions

#### Cross-Step Behaviour

| Step | Behaviour |
|------|-----------|
| Analysis (1) | Detect speaker patterns, count occurrences, build speaker list |
| Preprocessing (4) | Speaker Name Replacement: optionally replace original speaker names with translated equivalents from glossary |
| Translation (5) | Speaker format informs the conditional prompt (Dialogue vs Menu vs Choice). Rolling Context is dialogue-only |
| Postprocessing (7) | Speaker format validated and restored; quote balance respects speaker prefix |
| Wordwrap (8) | Speaker Handling mode (Ignore / Count) determines whether the speaker prefix counts toward line width |

#### Duplicate Speaker Removal (Global Option)

- **Purpose**: Save tokens by removing the speaker name when it is the same as the previous line's speaker
- **Affects Estimation**: Removed speakers reduce input count and consequently output token calculation; the request builder accounts for this
- **Preprocessing**: Speaker is stripped from the line along with the `:` separator and trailing spaces
- **Postprocessing**: Speaker with : and trailing spaces is re-added after translation, before the dialogue content
- **Manifest Key**: `Options.RemoveDuplicateSpeakers`

---

### 5.2 API Request Building and Formation

**Implementation Status:** ✅ Phase 49 DONE — All 6 tasks implemented (50 tests passing, 4985 total suite)

**Affects**: Costs (Step 4), Translation (Step 5)

**Purpose**: Define how translation requests are structured and how lines are grouped into requests. The same request builder function is shared between Estimation (Step 4) and Translation (Step 5) to ensure cost estimates match actual usage.

#### Request Structure

Each API request consists of three layers:

| Layer | Contents | Token Counting |
|-------|----------|----------------|
| **Meta Settings** | URL, API Key, Model, Temperature, Logit Bias, No Thinking, Structured Output — sourced from `user/API.ini` | NOT counted toward token estimates |
| **Prompt** | Language direction, System Instructions, Style, Tone, Summary, Conditional Prompts (selective), Glossary (selective, content-based), Rolling Context (conditional) — sourced from `user/CherryAI.ini` and manifest | Counted as input tokens |
| **Input Lines** | Preprocessed lines (preferred) or original lines when preprocessed is empty — sourced from manifest | Counted as input tokens; output estimated via language multiplier |

#### Prompt Injection Order

The system prompt is assembled in the following fixed order. Empty sections are always skipped (zero token cost):

| Slot | Component | Source | Condition |
|------|-----------|--------|-----------|
| 1 | **Language Direction** | `step_state.Information.data.metadata.source_language` + `target_language` (fallback: top-level `SourceLanguage`/`TargetLanguage`) | Always present |
| 2 | **System Instructions** | `metadata.custom_notes` / preset from `user/CherryAI.ini` | Gated by `system_instructions_enabled` (default: **true**) |
| 2b | **I/O Examples** | Generated by `functions/io_examples.py` from code patterns + example bank | Gated by `metadata.io_examples` (`disabled`/`fill`/`1500`/`2500`); language keys resolved from manifest source/target; never modifies System Instructions |
| 3 | **Style** | `metadata.style` (fallback: `CustomStyle`) | Gated by `style_enabled` (default: **false**) |
| 4 | **Tone** | `metadata.tone` (fallback: `CustomTone`) | Gated by `tone_enabled` (default: **false**) |
| 4b | **Protagonist + Narration** | Characters + Code patterns + `manifest POV` | Skip when no protagonist tagged (Task 75) |
| 5 | **Summary** | `metadata.summary` | Gated by `summary_enabled` (default: **false**) |
| 6 | **Genre** | `metadata.genre` (fallback: top-level `Genre`) | Gated by `genre_enabled` (default: **false**) |
| 7 | **POV** | `manifest POV` dict (`pov`, `confidence`) | Skip when confidence ≠ "high" **or** when slot 4b has narration |
| 7b | **Context-Type Prompt** | `resolve_chunk_type()` → `get_context_prompt()` | Resolved from per-line tags → filedir type → "unknown" fallback. Static, cacheable. |
| | **— cache boundary —** | | Everything above is cacheable; everything below varies per chunk |
| 8 | **Pattern-Triggered Prompts** | `user/CherryAI.ini [pattern_prompts]` or `user/conditional_prompts.json` | Selective — injected only when [Input Lines] contain the trigger pattern. 11 built-in pattern-triggered prompts (configurable in Global Options) |
| 8b | **Merged-Request Instruction** | `_merge_boundaries` from formation | Efficient mode only — describes block relatedness for Step 5 merged requests |
| 9 | **Glossary** | Manifest `Glossary` + `user/globalglossary.tsv` + `metadata.characters` + `code_patterns` (action=Translate) | Gated by `glossary_enabled` (default: **true**); selective — rows injected only when Original/pattern found in [Input Lines] |
| 10 | **Rolling Context** | Preceding translated lines from manifest | Conditional — dialogue/unknown requests only; disabled for Menu/Choice |
| 11 | **Input Lines** | Manifest `lines[].prepro` (fallback: `orig`) | Always present |

**Notes on ordering:**
- Slots 1-7b are non-selective (included when non-empty regardless of line content)
- Slot 7b resolves the content type via priority chain: per-line tags > filedir type > "unknown"
- POV (slot 7) maps "1st"→"first person", "2nd"→"second person", "3rd"→"third person"
- Slot 4b format: `Protagonist: {Original} - {Translation} ({Details})\nNarration: {1st/2nd/3rd/Mixed} View`
- When slot 4b is present, slot 7 (POV) is skipped to avoid duplication
- Slots 8-9 are selective/conditional (content-based or pattern-triggered)
- Rolling Context (slot 10) appears just before Input Lines to maximise contextual proximity
- Meta Settings (URL, key, model, temperature, etc.) are passed separately and never counted
- **Single source of truth**: `build_full_system_prompt()` in `gui/helpers/prompt_adapter.py` assembles the prompt for Costs (Step 4) and Translation (Step 5)
- **Unified data gathering**: `gather_prompt_data(mgr)` centralises all data gathering (metadata with fallback field merging for source_language/target_language/genre, glossary entries via `load_all_glossary_entries`, characters, code patterns, POV) into a single function. `build_request_prompt(prompt_data)` wraps `build_full_system_prompt()` with the gathered data. All features (Estimation, Request Preview, Start Translation) call these two functions to guarantee identical prompts.
- **API Log stores exact copies**: `LogEntrySent.system_prompt`, `LogEntrySent.user_content`, and `LogEntryReceived.content` store the full text that was actually sent or received (not truncated). This applies to the main translation path, line-by-line translation, term translation, gender inference, and model-translation tests whenever those call sites have the data available. The API Log viewer only displays stored entries — it never builds its own requests. The display-limit spinbox affects rendering only, not storage.
- **Section toggles**: Each togglable slot reads a `*_enabled` boolean from `step_state.Information.data.metadata`. When the key is missing, backward-compatible defaults apply (System Instructions/Glossary: enabled; Genre/Summary/Style/Tone: disabled)

#### Prompt Caching (OpenAI)

OpenAI automatically caches identical prompt prefixes (≥1024 tokens) across API requests. The injection order above is designed to maximise cache efficiency:

- **Static prefix** (slots 1-7b including 2b): Language, System Instructions, I/O Examples, Style, Tone, Protagonist, Summary, Genre, POV, Context-Type Prompt — semi-identical for every chunk within a project. This prefix is the cacheable portion.
- **Dynamic suffix** (slots 8-10): Pattern-Triggered Prompts, Glossary, Rolling Context — vary per chunk and are not cached.

**Extended retention**: Models prefixed with `gpt-4.1` or `gpt-5` support 24-hour cache retention via the `prompt_cache_retention` API parameter (value `"24h"`). Other supported models (gpt-4o, o1, o3, chatgpt-4o) use default in-memory retention (5-10 minutes).

**Implementation**: `APIClient.get_prompt_cache_params()` in `functions/api_client.py` returns the effective parameters for the current provider/model/project. When `prompt_cache_key` is not explicitly configured, `resolve_prompt_cache_key()` derives one from manifest `project_name` + `created_at`, and both `_translate_chunk()` and `_translate_single_line()` inject that metadata into the live OpenAI request. `supports_prompt_caching()` checks model and provider (OpenAI only; Gemini excluded). Cached tokens are tracked via `usage.prompt_tokens_details.cached_tokens` in the API response. Completion token breakdown (reasoning, predictions) tracked via `completion_tokens_details`. Preview Requests and the structured API Log must surface the same effective cache params so users can verify what is actually being sent.

**Cache key generation**: `generate_prompt_cache_key(project_name, created_at)` builds a semi-unique routing hint from manifest metadata. Format: `"{first 5 alpha chars}-{seconds}"`.

**Static prompt size check**: `check_static_prompt_cache_status(token_breakdown)` evaluates whether the static prefix is large enough for caching: "ok" (≥1280 tokens), "suggest" (1024-1279), "warn" (<1024).

**Configuration** (APIConfig fields):
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `prompt_cache_enabled` | bool | true | Enable prompt caching support |
| `prompt_cache_retention` | str | "" | Retention mode: "", "in_memory", or "24h" |
| `prompt_cache_key` | str | "" | Routing hint for cache slot affinity |

#### Request Size

- Requests have a configurable **Minimum** and **Maximum** request size
- **Maximum**: Hard limit — no request exceeds this (controlled by Lines/Chunk, Max Input Tokens, and Tokens/Chunk)
- **Minimum**: Soft target — requests below this are merged with adjacent requests when possible (see Step 4 of Formation)
- When both lines and tokens limits exist, whichever is reached first triggers the chunk boundary
- **Max Input Tokens** counts only input line tokens (not prompt, glossary, or meta tokens). When set to 0, the token limit is disabled and only the line limit applies.
- **Maximum** and **Minimum** can be the same, **Minimum** can not exceed **Maximum**

#### Request Formation (4+1 Step Process)

Invalid lines (placeholders, deduplicated, context markers, code-pattern-only) are never counted and are excluded from the final request.

**Step 1**: Split off Menu and Choice blocks into their own requests using Context Markers. Dialogue and Unknown lines remain together.

**Step 2**: Using File Ending Context Markers only, perform the First Dialogue Split. Remove invalid lines from count. Each file boundary produces a separate request candidate.

**Step 3**: Apply the Maximum Request Size (line count and/or token count via `max_tokens`) to split any oversized First Dialogue Splits. When `max_tokens > 0`, input line tokens are counted and chunks are split when the token budget is reached. Balance line counts within each resulting Second Dialogue Split where necessary to avoid very uneven chunks.

**Step 4**: Smartly merge Second Dialogue Splits below Minimum Request Size with other requests, up to the Maximum Request Size. In a merge, the 2nd request onwards must not have any rolling context that could be provided.

**Step 5** *(Efficient mode only)*: After Steps 1-4, merge small requests **across file boundaries** when they carry no rolling context. Merge candidates are requests with `receives_context=False` whose next request also has `receives_context=False` (i.e. singleton file sections). Merging is blocked when `Lines (Between)` or `Lines (After)` are configured and a line-index gap exists. Original block sizes are tracked in `_merge_boundaries` so that the merged-request conditional prompt (slot 8b) can describe block relatedness.

#### Request Content Selection

- Lines to translate prioritize the preprocessed line (`prepro`); fall back to original (`orig`) when preprocessed is empty
- The conditional prompt section is selected based on Context Markers:
  - Dialogue marker → Dialogue prompt
  - Choice marker → Choice prompt
  - Menu marker → Menu prompt
  - No context marker (only file start) → Unknown prompt (treated like Dialogue but with the Unknown conditional)

#### Shared Builder

The request builder function in `functions/prompt_builder.py` is called by both:
- **Estimation** (Step 2): To calculate accurate token counts matching the actual translation requests
- **Translation** (Step 5): To build the actual requests sent to the API

This ensures cost estimates are never out of sync with translation behaviour.

---

### 5.3 Context Markers

**Implementation Status:** ✅ Phase 50 DONE — All 5 tasks implemented (70 tests passing, 5010 total suite)

**Affects**: Analysis (Step 1), Preprocessing (Step 4), Translation (Step 5)

**Purpose**: Context Markers are metadata lines injected by Parser Scripts (§5.8) or detected during Analysis that inform request building and prompt selection. They are never translated and never sent to the LLM.

#### Marker Types

| Marker | Meaning | Effect |
|--------|---------|--------|
| **File End** | Marks the boundary between files in a multi-file project | Splits requests at file boundaries; rolling context does not cross file boundaries |
| **Dialogue** | Everything after this marker is dialogue until the next marker | Selects the Dialogue conditional prompt; enables Rolling Context |
| **Menu** | Everything after this marker is a menu | Selects the Menu conditional prompt; aims for Maximum Request Size, ignores file endings | No rolling context | 
| **Choice** | Everything after this marker is a set of choices | Selects the Choice conditional prompt; aims for Maximum Request Size, ignores file endings | No rolling context | 

#### Rules

- Context Markers apply from their position until the next Context Marker (including File End)
- File Start without a Dialogue/Choice/Menu marker immediately after is treated as **Unknown** — lines can be anything (dialogue, choices, menu) and the Unknown conditional prompt is used
- Context Markers are entirely optional but significantly increase translation quality by enabling appropriate prompt selection and request grouping
- Context Markers are marked as invalid lines — they are never counted toward request size and never included in the lines sent to the LLM
- Parser Scripts provide context markers when the game engine format supports them (see §5.8)

---

### 5.4 Lines to Translate Rules

**Affects**: Preprocessing (Step 4), Translation (Step 5)

**Purpose**: Determine which lines are actually sent to the LLM for translation. Lines failing these rules are skipped automatically.

#### Filtering Rules

| Rule | Type | Default | Description |
|------|------|---------|-------------|
| Skip already translated | Global Option | On | Lines with a non-empty `tl` field are not re-translated |
| Skip non-source language | Global Option | On | Lines detected as not being in the configured source language are skipped |
| No Placeholders | Mandatory | Always | Lines consisting entirely of placeholder tokens (any ``__TOKEN__`` type) are skipped |
| No Deduplicated | Mandatory | Always | Lines marked as deduplicated (`__DEDUP_{idx}__`) are skipped |
| No Context Markers | Mandatory | Always | Context Marker lines are metadata and are never translated |

#### Behaviour

- The mandatory rules cannot be disabled — placeholder-only lines, deduplicated lines, and context markers must never be sent to the LLM
- **Placeholder-only** is determined by ``is_placeholder_only()`` in ``prompt_builder.py`` which strips all placeholder tokens and checks if anything remains.  A line like ``攻撃力+__PROTECTED__`` is **not** placeholder-only because it contains CJK content alongside the placeholder
- The optional Global Option rules provide user control over incremental translation and language filtering
- **Language detection** for the "Skip non-source language" rule operates on the **prioritized** text (``edited_prepro → preprocessed → original``) with placeholder tokens stripped before classification.  Placeholder token names (``PROTECTED``, ``COLOR``, etc.) are Latin letters that would skew ratio-based script detection, so they are removed first.  After stripping, the remaining text is correctly detected as either source or non-source: if CJK content remains the line is kept for translation; if only non-source text remains the line is skipped
- Preview Requests and Start Translation must classify from the full loaded line set, not only lines still marked pending, so changing overwrite/skip-translated immediately changes the actual request set
- The Translation tab header shows both the translatable count and a grouped policy-skip breakdown (already translated, non-source, empty, placeholders, code-only, symbols-only, context markers)
- Lines that are skipped are marked accordingly in the Translation step status column (e.g., "Skipped (already translated)", "Skipped (wrong language)")
- All three callers — Request Preview, Estimate, and Start Translation — apply the same filtering rules via shared functions: ``validate_line_pre()`` handles already-translated, placeholder, code-only, symbol-only, and source-language checks; callers only decide whether the optional non-source reasons are enforced, and Translation tab entry must re-sync Global Options before any cache short-circuit so the active overwrite setting immediately affects both Preview Requests and Start Translation

---

### 5.5 Rolling Context

**Affects**: Translation (Step 5), Costs (Step 2)

**Purpose**: Provide surrounding lines as context to the LLM for each translation request to improve coherence and consistency.

#### Rules

- **Dialogue only**: Rolling Context is only applied to Dialogue and Unknown requests (not Menu or Choice)
- **Enabled by default**: Global Option with configurable line counts (default: Before=3, Between=0, After=0)
- **Three context types**:
  - **Lines (Before)**: Preceding translated lines from the prior request (classic rolling context)
  - **Lines (Between)**: Skipped/already-translated lines _within_ the chunk's index range (gaps)
  - **Lines (After)**: Already-translated lines _following_ the chunk in the manifest (forward context)
- **Prefer translated vs original**: Global Option controlling whether rolling context uses already-translated lines or original lines. Default: "Prefer translated". Batch API automatically falls back to original
- **File boundary**: "Before" context does not cross file boundaries (respects File End context markers)
- **Merge blocking**: All three context types block Efficient-mode Step 5 merging for affected requests

#### Split Request Logic

After the first step of request formation (§5.2), the system determines which requests get or provide rolling context:

| Condition | Gets Rolling Context | Provides Rolling Context |
|-----------|---------------------|------------------------|
| 2nd request onward of a Split Request (a request that was deemed too big and split) | Yes | — |
| Not the last request of a Split Request | — | Yes |
| First request of a new file | No | — |
| Single request (not split) | No | No |

- **Gets**: The request will include preceding lines from the previous request as rolling context in the prompt
- **Provides**: The last N lines of this request are stored for the next request to use as rolling context. When "Prefer translated" is enabled (default), stores translated output; otherwise stores original/preprocessed text.

#### Between / After Context Collection

- **Between**: At translation time, for each chunk, manifest lines between the chunk's first and last index that were skipped (already translated or non-source language) are collected up to the configured limit
- **After**: Manifest lines following the chunk's last index that already have translations are collected up to the configured limit
- Both types respect the "Prefer translated" global option
- Both types are formatted with distinct labels ("Interspersed context" / "Following context") and appended after the before-context in the prompt

#### Fallback Rules

- When "Prefer translated" is selected but the previous request's translation is not yet available (e.g., during the first pass), falls back to using original lines
- When rolling context is fully disabled (all line counts = 0), no context is included regardless of request type

---

### 5.6 Glossary Selective Inclusion

**Implementation Status:** ✅ Phase 52 DONE — All 4 tasks implemented (28 tests passing, 5130 total suite)

**Affects**: Translation (Step 5), Costs (Step 2)

**Purpose**: Include only relevant glossary entries in the translation prompt for each chunk, reducing token usage while maintaining translation consistency.

#### Behaviour

- For each chunk of lines to translate, the glossary is filtered to include only entries whose **Original** term appears in the current chunk's lines
- **Global Option**: "Original Only" vs "Original or Translation" — controls whether matching is done against the Original column only or against both Original and Translation columns
- Project glossary and Global glossary are both filtered selectively
- Glossary entries with empty Translation or empty Notes still appear if the Original matches (they serve as context for the LLM)
- The selective filter runs identically during Estimation and Translation via the shared request builder

#### Prompt Format

When glossary entries match, they are included in the prompt as:
```
Glossary:
- [Original]: [Translation] ([Notes])
```

Only matching entries appear — the LLM never sees the full glossary.

---

### 5.7 Code Database Extended Properties

**Affects**: Preprocessing (Step 4), Postprocessing (Step 7), Wordwrap (Step 8)

**Purpose**: The Code Database categorizes code patterns with both an Action (how to handle during translation) and extended properties that control spacing and width behaviour.

#### Actions

| Action | Translation Behaviour | Postprocessing Behaviour |
|--------|----------------------|-------------------------|
| **Translate** | Added to prompt with notes for contextual translation | No special handling |
| **Preserve** | Added to prompt with "do not translate" instruction; validated after translation and recovered or retried when missing | Code Pattern Recovery restores translated patterns from original |
| **Protect** | Optionally replaced with `__PROTECTED__` token during Preproccessing, checks translation and tries to recover or retry when missing | Restored from `prepro_ops` |
| **Custom Placeholder** | Replaced with a custom named token during Preproccessing; token may be a human-readable replacement such as `Jane` and is tracked with token-aware records | Restored from `prepro_ops`; postprocessing restores per-line first, then batch-wide if the LLM moved the token to another line; dedup-tagged duplicate rows are skipped during that batch fallback and later rebuilt from their dedup source line so duplicate rows do not create false placeholder/code-pattern flags |
| **Placeholder** | Generic `__PROTECTED__` / `__PROTECTED_X__` replacement during Preproccessing, checks translation and tries to recover or retry when missing | Restored from `prepro_ops` |
| **Anchor** | Entirely removed; position stored relative to anchors during Preproccessing | Restored at anchor positions |

#### Extended Properties

| Property | Type | Description |
|----------|------|-------------|
| **IsInvisible** | bool | Code renders with zero visible width. Adjacent characters are spaced depending on whether they are symbols, punctuation, numbers, words, or a mix. Used by Code Spacing Rules and Wordwrap width calculation. |
| **IsCouple** | bool | Like IsInvisible but the code is a pair (e.g., font and color with their reset commands). The second element of the pair gets a space after instead of before it when applicable (if word or number and not already present). |
| **IsNumber** | bool | Code renders as a number (like a variable showing `100G`). Must be treated like a written number. Requires a whitelist of characters — `100m` is different from `100 meters`. All single characters with a space after are whitelisted through RegEx. |
| **IsWord** | bool | Code renders as a written word. Must be spaced like a word — whitespace before and after in running text. |

#### Code Spacing Rules

Code Spacing Rules (processed in both Pre and Post steps) apply these extended properties:
- **IsInvisible**: No spaces added around the code; adjacent characters determine spacing
- **IsCouple**: Treated like IsInvisible but the closing/reset command gets a trailing space
- **IsNumber**: Spaced like a numeric value following its specific whitelist rules
- **IsWord**: Spaced like any other word in the text

---

### 5.8 Parser Scripts

**Affects**: Input (Step 0), Analysis (Step 1), Preprocessing (Step 4), Wordwrap (Step 8), Output (Step 9)

**Purpose**: Parser Scripts are game-engine-specific or format-specific scripts that handle extraction, injection, and optionally provide wordwrap settings and context markers. They extend the base format handlers in `formats/` with engine-aware logic.

**Status**: Implemented (Phase 53 + Parser Handshake) — `formats/parser_base.py` defines the `ParserScript` ABC with `WordwrapConfig`, `ForbiddenChars`, and `TagRules` dataclasses plus optional handshake methods (`extract_tagged`, `detect_speakers`, `wordwrap_for_tag`, `wordwrap`, `detect_encoding`). `formats/handshake.py` defines the handshake protocol types (`ExtractedLine`, `SpeakerInfo`, `ParserError`) and `validate_parser()`. RPG Maker MV/MZ parsers live in `formats/parser_rpgmaker.py`. The Light VN parser lives in `formats/LightVN.py` and is the reference handshake-compliant implementation. A `ParserRegistry` in `formats/__init__.py` handles discovery and auto-detection. Wordwrap step auto-populates settings from detected parsers; forbidden characters integrate with logit bias and postprocessing.

**Input Routing Rule**: Step 0 resolves the effective parser format before auto-encoding. When the user keeps Encoding on `auto` but explicitly selects a parser format such as `lightvn`, that parser's `detect_encoding()` result is used before generic BOM or fallback detection. The first successfully loaded file also seeds missing Output defaults for Destination, Format, and Encoding.

#### Handshake Protocol

The Parser Handshake (`formats/handshake.py`) formalizes what every parser must and may provide:

**Mandatory Components** (M1–M3):
| Component | Requirement |
|-----------|-------------|
| M1: Extract | `extract(file_path) → List[str]` — flat list of translatable strings |
| M2: Inject | `inject(file_path, lines)` — write translations into adjacent copy; `inject_to(source_path, output_path, lines)` — surgical injection reading source, writing to output path |
| M3: Identity | Either `format_id + extensions` (FormatHandler) or `can_handle(file_path)` (ParserScript) |

**Optional Components** (O1–O8):
| Component | Method / Attribute | Description |
|-----------|--------------------|-------------|
| O1 | `decrypt(file_path)` | Decrypt before extraction |
| O2 | `encrypt(file_path)` | Re-encrypt after injection |
| O3 | `detect_encoding(file_path)` | Parser-specific encoding detection |
| O4 | `detect_speakers(lines)` | Return `List[SpeakerInfo]` from extracted text |
| O5 | `wordwrap_config` / `wordwrap_for_tag(tag)` | Wrapping config (global or per-tag) |
| O6 | `wordwrap(line, config)` | Custom wrapping function |
| O9 | `pretty_wrap(text, width, break_char, max_lines)` | Custom core-wrap replacement (lighter than O6) |
| O7 | `forbidden_chars` | Characters that must not appear in output |
| O8 | `tag_rules` | Engine-specific context marker definitions |

**Surgical Injection** (extends M2): `inject_to(source_path, output_path, lines, *, orig_lines=None) → List[int]` reads the original script from *source_path*, surgically replaces only translatable text with entries from *lines*, and writes the complete script to *output_path*. The default implementation follows a standardized 4-step Speaker:Dialogue-aware handshake: (0) Load `\Original` into memory, (1) Extract keys via `extract_tagged()` (preferred) or `extract()` to get real line positions and speaker metadata, (2) Sequential search-and-replace with speaker awareness — lines with a non-empty speaker are split into a **speaker part** and a **dialogue part** via `_split_speaker_dialogue()` (recognises half-width `: ` and fullwidth `：`); the speaker name is replaced only on its first occurrence for consecutive same-speaker lines, the dialogue part is replaced separately; lines without a speaker use plain find-and-replace, (3) Save the result to *output_path*. Returns a list of failed indices (empty on full success). When *orig_lines* is provided they are used as search strings; when ``None`` the extracted keys are used directly (legacy compatibility). Parsers override this for engine-specific surgical injection (e.g. LightVN uses its own key extraction since extracted text is cleaned and does not appear verbatim in raw files). The Output step (Step 9) calls `inject_to` via the INJECTION format or when `filedir[].format` matches a registered parser.

**Tagged Extraction** (extends M1): `extract_tagged(file_path) → List[ExtractedLine]` returns lines with tag, speaker, and context metadata. When provided, `extract()` delegates to it for backward compatibility.

**Validation**: `validate_parser(parser) → List[str]` checks M1–M3 compliance and returns a list of error strings (empty = valid).

#### Data Types

| Type | Fields | Description |
|------|--------|-------------|
| `ExtractedLine` | `text`, `tag`, `speaker`, `context` | Tagged extraction result with serialization (`to_dict`/`from_dict`) |
| `SpeakerInfo` | `name`, `line_idx` | Speaker detection result linking name to line index |
| `ParserError` | `message`, `parser_name`, `component` | Structured error with source identification |

#### Interface (Legacy)

**Mandatory Fields**:
| Field | Type | Description |
|-------|------|-------------|
| Name | string | Parser identifier (e.g., "RPGMakerMV", "LightVN", "RenPy") |
| Extract | function | Extract translatable lines from source files |
| Inject | function | Inject translated lines back into file copies |

**Optional Fields**:
| Field | Type | Description |
|-------|------|-------------|
| Wordwrap | object | Engine-specific wrapping configuration |
| Wordwrap.MaxLineLength | int | Maximum characters or pixels per line |
| Wordwrap.MaxLineNumber | int | Maximum lines per text box |
| Wordwrap.WordwrapCommand | string | Line break command for the engine (e.g., `\n`, `[br]`) |
| Wordwrap.NewTextboxInjection | string | Command to start a new text box when overflow occurs |
| ForbiddenCharacters | list | Characters that must not appear in output |
| ForbiddenCharacters.logit_bias | dict | Applied during Translation (Step 5) via API logit bias |
| ForbiddenCharacters.output_action | enum | "replace" (auto) or "flag" (manual review and block) |
| ContextMarkers | object | Engine-specific context marker definitions |
| ContextMarkers.Scenes | pattern | RegEx or rule to detect scene/file boundaries |
| ContextMarkers.Dialogue | pattern | RegEx or rule to detect dialogue sections |
| ContextMarkers.Menu | pattern | RegEx or rule to detect menu sections |
| ContextMarkers.Choices | pattern | RegEx or rule to detect choice sections |

#### Light VN Parser (`formats/LightVN.py`)

Reference handshake-compliant parser for Light VN visual novel scripts. Adapted from the standalone `parlight.py` extraction tool.

**No Deduplication**: Every occurrence of a translatable line is returned, including duplicates. CherryAI's manifest stores per-line entries so deduplication must NOT happen at the parser level — it is handled downstream by the Preprocessing step (Deduplication mode) if enabled.

**Capabilities**: M1 ✓, M2 ✓, M3 ✓ (via `can_handle`), O3 ✓, O4 ✓, O5 ✓ (per-tag), O6 ✓, O7 ✓, O8 ✓, O9 ✓

**Tags**:
| Tag | Content | Wordwrap |
|-----|---------|----------|
| `dialogue` | Quoted dialogue, continuations, conditional dialogue | 60 chars / 3 lines |
| `menu` | `~文字` and `~ボタン文字` menu strings | No wrap |
| `variable` | `臨時全域変数` and `保存変数` assignments | No wrap |
| `items` | Item-like variable assignments such as `剥ぎ取り素材1` and `獲得食材` | No wrap |

**Variable Classification**: LightVN classifies translatable assignment lines by variable name. Existing story/system assignments such as `スキル名` continue to use the `variable` tag, while loot/material style fields such as `臨時全域変数 剥ぎ取り素材1 = "角兎の素材×1"` and conditional forms such as `もし (獲得ボーナス >= 2) 臨時全域変数 獲得食材 = "食用の肉×3"` are extracted and injected with the `items` tag.

**Detection**: Scans the entire file for any of the `_DETECT_PATTERNS` set (`~【`, `~栞`, `~文字`, `~ボタン`, `~絵`, `~効果音`, `~選択`, `~スクリプト`, `~保存変数`, `~臨時全域変数`) or `_DETECT_LINE_PREFIXES` (`栞 `, `スクリプト `, `保存変数 `, `臨時全域変数 `). This keeps script/config-style LightVN files such as map stubs and variable-only setup files on the parser path instead of falling back to raw `txt` extraction.

**Bookmark Semantics**: `~栞 ...` is treated as a bookmark/interaction anchor rather than a displayed speaker tag. Encountering a bookmark clears any previously active `~【Speaker】` state so later quoted dialogue is not accidentally prefixed with the wrong speaker.

**Placeholder Dialogue Filtering**: Template scaffolding such as `ここにテキストを入力` / `Enter your text here.` is rendered dialogue text in the script, but it is not real game content. The parser excludes these placeholder lines from extraction so they are not translated and do not pollute speaker analysis.

**Surgical Injection**: `inject_to(source, output, lines)` reads the original script, re-extracts translatable keys, maps them 1:1 with the provided translations, and calls `_inject_all()` for surgical replacement of dialogue, menu, variable, and item-assignment text while preserving all non-translatable commands and structure. `inject()` delegates to `inject_to()` for backward compatibility.

**Tag Propagation**: When `extract_tagged()` is used during loading, per-line tags (`dialogue`, `menu`, `variable`, `items`) are stored in `LoadedFile.tags` and merged into the manifest's canonical `tags` field during `_sync_lines_to_manifest()`. The O8 `tag_rules` regex pass in `_wire_parser_optionals` skips lines that already have a primary content tag.

#### Wordwrap Integration

When a Parser Script provides wordwrap settings, these auto-populate the Wordwrap step (Step 7):
- `MaxLineLength` → Width setting
- `MaxLineNumber` → Max Lines setting
- `WordwrapCommand` → Break Character
- `NewTextboxInjection` → Used when overflow exceeds Max Lines to create a new text box instead of flagging

**Per-Tag Wordwrap**: Step 7 resolves each line's tag (canonical line `tags` primary content tag → filedir `type` → `"dialogue"` fallback) and applies per-tag settings from `WordwrapSettings.TagConfigs`. Tags whose wrapping is dictated by the parser (via `wordwrap_for_tag`) are marked `ParserManaged` and displayed read-only in the UI.

**O9 pretty_wrap Hook**: A lighter alternative to O6. When a parser implements `pretty_wrap(text, width, break_char, max_lines) → Optional[str]`, Step 7 uses it as the core wrapping algorithm while keeping speaker handling, ignore patterns, and the rest of the pipeline intact. If the parser also provides O6, that takes priority for parser-managed tags; O9 is used for user-managed tags or as a fallback when O6 is not present.

#### Forbidden Characters

Parser-defined forbidden characters affect:
- **Translation (Step 5)**: Applied as logit bias to prevent the LLM from producing them
- **Output (Step 9)**: Characters are either auto-replaced or flagged for manual review, depending on the configured action

---

### 5.9 Pre/Post Processing Priority System

**Affects**: Preprocessing (Step 4), Postprocessing (Step 7)

**Purpose**: Document the complete priority ordering for all pre- and post-processing operations. Preprocessing runs lowest-priority-first; Postprocessing runs in reverse (highest-priority-first, matching the table below top-to-bottom for Post).

#### Full Priority Table

The following table lists all processes in their execution order. Preprocessing reads top-to-bottom; Postprocessing reads bottom-to-top.

| Order | Process | Pre Step | Post Step | Notes |
|-------|---------|----------|-----------|-------|
| 1 | Deduplication | First (P10) | Last (P90) | Replaces duplicates with `__DEDUP__`; post recovers from unique translation via `postpro → tl → prepro → orig` resolution; GUI: `apply_dedup_batch()` in mode_adapter; tags D{idx}; reduplication reads step data from ManifestManager |
| 2 | Protect Code Patterns | P15 | P20 | Generic `__PROTECTED__` / `__PROTECTED_X__` protection; runs before symbol conversion so fullwidth patterns (e.g. `（圧縮あり）`) still match the original text |
| 3 | Custom Placeholder | P17 | P30 | Custom named replacement tokens for variables; runs before symbol conversion to capture fullwidth originals; postprocessing uses per-line restoration plus a batch-wide exact-token fallback for shifted replacements |
| 4 | Anchoring | P20 | P10 | Remove code at anchor-relative positions; records anchor char, side, and type for restoration; patterns without adjacent anchors are left in place; restore first in Post using symbol-conversion equivalents |
| 5 | Symbol Conversion | P30 (Pre only) | P70 | JP→EN symbols; Post optionally converts back; runs after protection/placeholders so `__PROTECTED__` tokens remain intact |
| 6 | Width Conversion | P35 (Pre only) | — | Fullwidth↔Halfwidth character width; Pre only |
| 7 | Ellipsis Compression | P36 | P80 | Normalize ellipsis length; runs after symbol (P30) and width (P35) conversion; handles ASCII dots, fullwidth periods (\uff0e), and Unicode ellipsis (\u2026); stores per-line triplet counts for postprocessing decompression |
| 8 | Speaker Name Replacement | P38 | P60 | Replaces speaker names with translations from character glossary |
| 9 | Code Spacing Rules | P50 | P50 (Post for recovery) | Post-exclusive spacing recovery; also pre for normalization |
| 10 | PROTECTED Compression | P60 | P40 | Adjacent `__PROTECTED__` → `__PROTECTED_N__` |
| 11 | Quote Stripping | P76 (after PROT) | P9 (before Anchoring restore) | Strip quotes at dialogue boundaries to save tokens |
| 12 | Aggressive Deduplication | Last (P90) | First (P5) | Variant-aware dedup with generic substitutions; GUI: `apply_aggressive_dedup_batch()` in mode_adapter; tags AD{idx} |
| 13 | Whitespace Normalization | — | P120 (Post-exclusive) | Post-exclusive: matches indentation to original |
| 14 | Bracket Balance | — | P110 (Post-exclusive) | Post-exclusive: fixes unmatched brackets |
| 15 | Quote Balance | — | P100 (Post-exclusive) | Post-exclusive: fixes unmatched quotes |
| 16 | Code Pattern Recovery | — | P105 (Post-exclusive) | Post-exclusive: restores preserve-action code patterns translated by the LLM; uses delimiter-aware regex matching to find translated substitutes and replace with originals, including doubled delimiters such as `{{...}}`; flags unrecoverable patterns as NEEDS_RETRY |

#### Width Conversion (Pre only)

- Converts character width from source language width to target language width
- Most languages use halfwidth characters; East Asian (Chinese/Japanese/Korean) use fullwidth
- Runs after Symbol Conversion and before Anchoring (in case of missing anchor equivalents)
- No postprocessing reversal needed — the target language width is the desired output width

#### Quote Stripping

- Removes quotes at line/dialogue start and end to save tokens
- Runs after Anchoring in preprocessing (quotes at anchored boundaries)
- Restored before Anchoring restoration in postprocessing
- Distinct from Quote Balance (which is post-exclusive and fixes LLM-introduced mismatches)

#### Aggressive Deduplication

- Similar to standard Deduplication except that variations of lines are deduplicated
- Uses generic substitutions: one `{CODE}` for all code, `X` for all numbers
- Runs last in preprocessing (after all other transformations have normalized the text)
- Restored first in postprocessing (before any other restoration)
- Lines deduplicated aggressively use the postprocessed result of their unique original (`X` turns back into the respective number &c)

---

### 5.10 Wordwrap Extended Rules

**Affects**: Wordwrap (Step 8)

**Purpose**: Additional rules and terminology for the wordwrap system beyond the step-level specification.

#### Overflow and Runaway

- **Overflow**: Text exceeds the horizontal boundary (characters/pixels per line exceeded). Flagged as "Overflow".
- **Runaway**: Text exceeds the vertical boundary (more lines than the textbox maximum). Flagged as "Runaway".
- Both must be prevented; `pretty_wrap` handles overflow, and Max Lines handles runaway.
- When a parser defines `NewTextboxInjection`, runaway can be automatically resolved by injecting a new textbox command instead of flagging.

#### Variable Words

- Engine variables rendered in text (e.g., `\V[1]` displaying a character name) have variable visible length
- Width calculation must use the **maximum** value/token length for each variable
- Variables marked as `IsInvisible` in the Code Database are excluded from width calculation entirely

#### Fontresize Commands

- Some engines support inline font size changes (e.g., `\{` to increase, `\}` to decrease in RPG Maker)
- When font resize commands are present, width calculation must account for the changed character width after each command
- Parser Scripts can provide `size_up`, `size_down`, `size_increments`, `set_size`, `get_size` commands

#### PrettyWrap Rules

PrettyWrap is the standard wrapping algorithm. Its priority rules:

1. **Prevent Overflow and Runaway** — Top priority. Never exceed width or max lines.
2. **Prefer breaks after Punctuation/Symbols** — Break after `.`, `,`, `!`, `?`, `;`, `—`, `…` or before bullet points (`•`, `→`, `▶`, and equivalents)
3. **Balance Lines** — Avoid single or few words on the last line by pulling words from the previous line. Default balance threshold: 30% (Global Option). A last line should contain at least 30% of the line width in characters.

---

### 5.11 Point of View Inference

**Affects**: Analysis (Step 1), Translation (Step 5)

**Status**: Implemented (Phase 54) — `functions/analysis.py` contains `_RAW_POV_PATTERNS` (Japanese, English, Chinese, Korean), `_get_pov_patterns()` with compiled caching, `POVResult` dataclass, and `detect_pov()` algorithm. Prompt integration via `PromptBuilder.pov_result` in `functions/prompt_builder.py`. Tests in `dev/test_pov_inference.py` (36 tests).

**Task 75 Extension**: Protagonist-aware POV re-run — `get_protagonists_from_characters()`, `get_protagonists_from_code_database()`, `run_pov_with_protagonists()`, `format_protagonist_prompt()` in `functions/analysis.py`. GUI trigger: `_set_speaker_role("Protagonist")` → `_rerun_pov_with_protagonists()` stores updated POV in manifest. Prompt slot 4b between Tone and Summary. Tests in `dev/test_protagonist_romanization.py` (18 protagonist tests).

**Task 75 Romanization + Term Translation**: `functions/romanization.py` — Modified Hepburn kana→rōmaji conversion with `capitalize_name()` (first-letter-only capitalization) and `contains_kanji()` (skips mixed kanji+kana terms to avoid garbled output). `functions/term_translation.py` — unified dispatcher supporting Romaji (romanize) and LLM modes. LLM mode reads API key/model from API.ini `[term_translation]` profile section via `api_config.get_profile_setting()`. Uses strict JSON-schema structured output (`response_format=json_schema`) with `store=False` and `max_tokens` cap to minimise output-token waste. Accepts `prompt_type` kwarg (`"glossary"` or `"code"`) to route to the appropriate configurable prompt template from CherryAI.ini `[prompts]`. Terms are split into batches of configurable `term_batch_size` (default 10). API failures raise `RuntimeError`; the Analysis step saves any partial results translated before the error, then shows an error messagebox with saved count. GUI button renamed to "Translate Terms". `_translate_terms()` runs in a background thread with a modal progress dialog (determinate progress bar, per-term status label, Cancel button) for all modes. Auto-populates glossary Translation field and code database Translation column. Code pattern translations are saved to the manifest `code_patterns` field only (not the global TSV). Translation results are flushed to disk immediately after each chunk via `manifest_manager.save()`. After translation, the findings table Details column updates immediately. `_translate_terms()` reads source/target language from manifest `step_state.Information.data.metadata`. Mode configurable in Global Options → Utility. Model fields are Comboboxes that auto-populate via `get_provider_models()` when the API key changes. Code validation via `extract_code_segments()` (balanced bracket matching for `[]`, `{}`, `<>` and fullwidth variants) and `validate_translation_code()` — translations with missing code segments are skipped and reported. Empty/whitespace-only results are silently discarded. Prompts configurable in Global Options → Prompts. Tests in `dev/test_protagonist_romanization.py` (22 romanization tests), `dev/test_term_translation.py` (84 tests), `dev/test_utility_settings.py` (57 tests), and `dev/test_utility_integration.py` (7 live API tests).

**Purpose**: Infer the narrative point of view from non-dialogue text to provide the LLM with accurate context for pronoun and perspective handling.

#### Detection Rules

- Applies only to non-dialogue lines (no speaker prefix) and non-menu lines (using Context Markers to exclude menus and choices)
- Requires proper RegEx, counting, and calculation to avoid false numbers and provide confidence scores

| Point of View | Indicators | Notes |
|---------------|------------|-------|
| **1st Person** | I, my, mine; Japanese equivalents (私, 僕, 俺, わたし, ぼく, おれ — both furigana and kanji); extensible per language | High confidence when multiple 1st-person pronouns appear consistently |
| **2nd Person** | You, yours; Japanese equivalents (あなた, 君, きみ, お前, おまえ); extensible per language | Less common as primary narrative perspective |
| **3rd Person** | Frequent use of the protagonist's name (from Glossary); absence of 1st/2nd person markers | Requires protagonist name to be configured in Glossary or detected by Analysis |

#### Output

- Produces a confidence score (high/low) based on pronoun frequency and consistency
- Result stored in manifest and included in the translation prompt when confidence is high
- Extensible: language-specific pronoun lists can be configured per source language

---

### 5.12 Consistency System

**Affects**: Preprocessing (Step 4), Translation (Step 5), Postprocessing (Step 7)

**Status**: Implemented (Phase 55).

**Purpose**: Ensure consistent translation of recurring terms, code-embedded text, and styled spans across all requests.

#### Global Option: Mode

The Consistency system operates in one of three modes (Global Option, can be disabled):

| Mode | When | Description |
|------|------|-------------|
| **Preliminary** | Before translation requests are prepared | Runs additional LLM requests to establish consistent translations. Does not send code, only text. May run multiple times for confidence. Modifies the preprocessed entry directly. |
| **During** | During translation | Uses the first translated occurrence of each term as the canonical translation. If the first occurrence has no code, uses `<t></t>` tags to mark and locate it. Updates the glossary dynamically. Replaces codes and spans in all subsequent stored requests. |
| **Check** | After translation | Post-translation verification pass that flags inconsistent translations of the same term across different requests. Does not auto-fix — flags for manual review. |

#### Types

| Type | Detection | Behaviour |
|------|-----------|-----------|
| **Code (Translate)** | Code categorized as "Translate" in the Code Database; automatically covers any found through RegEx | Term and surrounding context are provided to the LLM for consistent translation |
| **Glossary** | Glossary entries with empty Translation or empty Notes | Lines containing the term with surrounding context are provided. Prompt asks whether it is a person with gender, location, or term. |
| **Spans** | Automatically discovered through paired tags (e.g., color and color reset commands, bold start/end) | Content within spans is extracted and tracked for consistency across requests |

---

### 5.13 Mock Translation Extended

**Affects**: Translation (Step 5)
**Status**: ✅ Implemented (Phase 56, reworked March 2026)

**Purpose**: Extended specification for Mock Translation behaviour, including deliberate flaw testing for recovery validation.

**Implementation**: `functions/mock_translator.py` (standalone module), integrated
via `functions/api_client.py` mock routing (`model == "mock"`).
Tests: `dev/test_mock_translation.py` (70 tests). Fixture: `dev/example/example.txt`.

#### Standard Mock Behaviour

- Always available and the only Model option when no API providers are configured
- Produces deterministic nonsense output (swift random word replacement from a limited list)
- Languages like Japanese have custom replacement settings
- Preserves all `__PROTECTED__`, `__DEDUP__`, `__CUSTOM__` tokens in output
- Preserves speaker:dialogue format and anchor characters
- Does NOT require API key or network connectivity
- No artificial delay — 1000 lines translate in under 100 ms

#### Cancellation

- `MockTranslator` accepts an optional `threading.Event` (`cancel_event`)
- `translate_batch()` checks the event between lines; on cancel it pads remaining output with empty strings and returns immediately
- The GUI translate step creates a shared `_cancel_event` that the Cancel button sets; the mock translator and the chunk-processing loop both observe it
- Cancellation is graceful: no new chunks are submitted, already in-flight work (mock or API) finishes naturally before the background thread exits

#### Speed

- Default `delay_per_chunk=0.0` — no artificial delay
- UI table updates throttled to 150 ms minimum interval (`_schedule_table_update`) to prevent Tkinter event loop flooding during fast mock runs
- Pause loop uses `cancel_event.wait(timeout=0.1)` instead of busy `time.sleep`

#### Deliberate Flaw Testing

Mock Translation intentionally introduces flaws to test the recovery pipeline:

| Flaw Type | Description |
|-----------|-------------|
| **Malformed Placeholders** | Surgically remove and add characters to placeholder tokens (e.g., `__PROTECTED__` → `__PRT__`, or `__PRO T__`) |
| **Anchor Manipulation** | Remove existing anchors and add anchors where they do not belong |
| **Code Intrusion** | No respect for text within code boundaries — random word replacement occurs inside code patterns as well |
| **Character Surgery** | Add and remove characters at random positions to stress-test character-level recovery |

#### Purpose of Flaws

These deliberate flaws validate that the Translation pipeline correctly handles:
- Placeholder recovery (case recovery, mangled recovery, position shift)
- Anchor verification and restoration
- Code spacing rule enforcement
- Quote and bracket balance after distortion

---

## 6. GUI Mode: Step-by-Step Specification

Each step is a tab in the main notebook. Steps can be navigated freely but follow a logical workflow progression.

---

### Step 0: Input

**Purpose**: Load source files and extract translatable text. This is where a project begins. Loading files triggers a configurable automatic pipeline that can run the entire workflow through to mock translation and estimation.

**Implementation Status:** 🔲 Phase 58 PLANNED — Automatic Pipeline on File Load

**Design Goal**: Extract only visible text from any unencrypted text file that a user can theoretically read. Code not part of the text and any other non-translatable content should be excluded. In the final step (Output), translated text is injected into copies of the original files to replace the original text (non-destructive).

**Note**: This step was previously named "Input" — renamed to simply "Input" for clarity.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| **Toolbar** | | |
| Input Button | Button | Unified file/folder selector — opens a single window supporting both file and folder selection |
| Import Translations Button | Button | Import translations from another manifest via selection dialog (choose line fields and settings sections to import) |
| **Options Panel** | LabelFrame | Contains Encoding, Format, and Auto-Pipeline settings |
| Encoding Dropdown | Combobox | Select file encoding (auto, utf-8, shift_jis, etc.). Default: auto |
| Format Dropdown | Combobox | Override format detection (auto, txt, csv, json, rpgmaker, image, etc.). Default: auto |
| Auto-Pipeline Dropdown | Combobox | Pipeline automation level (see Automatic Pipeline section). **Currently hidden** pending rework; widget created but not packed |
| **Loaded Files Panel** | LabelFrame | Shows loaded files in a tree structure |
| File Tree | Treeview | Collapsible folder hierarchy with files. Folders always appear above files within the same directory. Loaded files are collapsed (not expanded) by default. Supports multi-select for bulk operations. Clickable column headers (Name, Type, Lines) sort ascending/descending with ▲/▼ indicators |
| File Filter Entry | Entry | Text filter for loaded files — matches against filename, type, or line count. Matching is instant on keystroke. Non-matching rows are hidden |
| File Filter Clear Button | Button | "✕" button to clear the file filter text |
| **Preview Panel** | LabelFrame | Shows content of selected file |
| Preview Tree | Treeview | Columns: Project (1-based global idx), File (1-based per-file #), Content, Tags. Shows all lines from selected file. When search text is entered, searches across ALL loaded files showing global idx. Must properly render newlines (multi-line content) |
| Preview Search Clear Button | Button | "✕" button to clear the preview search text |

**Removed Elements** (from previous design):
- Load Manifest button → Use File → Open Project... menu instead
- Clear All button → Use File → New Project menu instead
- Manifest Label (below Preview) → Removed; manifest status shown in title bar
- "Select File(s)" naming → Renamed to simply "Input"

#### Options Panel Details

**Encoding Dropdown**:
- Values: `auto`, `utf-8`, `utf-8-sig`, `shift_jis`, `cp932`, `latin-1`, `utf-16`
- Default: `auto` (CherryAI detects encoding per file)
- Behavior: When forced, applies encoding to all loaded files. Does NOT refuse to load files on encoding mismatch.

**Format Dropdown**:
- Values: `auto`, `txt`, `csv`, `tsv`, `json`, `xlsx`, `rpgmaker`, `image`
- Default: `auto` (CherryAI detects format from extension and content)
- Behavior: When forced, CherryAI **refuses to load files** that do not match the defined format.
- Game Engine Support: `rpgmaker` parses RPG Maker MV/MZ custom `.json` and `.js` files
- Image Support: `image` triggers OCR pipeline (see image_translation_workflow.md)

#### Input Button Behavior

The Input button opens a **unified file and folder selection window** that combines both file and folder selection into a single interface:

**Window Design**:
- Single modal window with dual-pane or tabbed interface
- Left/top section: Folder tree browser for selecting directories
- Right/bottom section: File list for selecting individual files
- Both sections support multi-select (Ctrl+Click, Shift+Click)
- "Add Selection" button adds current selection to the load queue without closing
- "Load" button finalizes all selections and begins the loading pipeline
- "Clear" button removes all pending selections

**Phase 58.12 Enhancements**:
- **Last Directory Memory**: Dialog opens to last used directory (stored in `[session].last_input_dir`)
- **Project Name Integration**: When creating a new project (no manifest), Options panel includes Project Name field
- Project name field appears left of Format and Encoding dropdowns
- Eliminates separate ProjectNameDialog for streamlined workflow

**Selection Types**:
- **Files**: Select one or more individual files
- **Folders**: Select one or more folders (recursively loads all supported files within)
- **Mixed**: Combine file and folder selections in a single load operation

**Processing**:
1. For files: Load directly
2. For folders: Recursively collect all supported files
3. Respects Format filter (if not `auto`)
4. Shows a **progress window** during loading with:
   - Current file being loaded
   - Progress bar (files loaded / total files)
   - Cancel button to abort

**After Loading**:
- The containing folder *name* is stored in the manifest as `source_root` (display-only, not a full path)
- Source files are copied to the project's `Original/` directory for portability
- All selected files/folders and their lines are saved to manifest
- The Automatic Pipeline begins (based on Auto-Pipeline setting)

**Non-Destructive Addition** (adding files to an existing manifest):
- When files are loaded into an existing project (manifest already has filedir), the Input button
  performs a **non-destructive merge**: existing lines and filedir entries are preserved, and only
  new files are inserted.
- **Source root validation**: new files must originate from the same source directory. If a mismatch
  is detected, loading is blocked with an error message.
- Files already present in the manifest (matched by filename) are silently skipped.
- After merging, all idx values are re-sequenced contiguously and entries are sorted alphabetically
  by ``rel_path``.
- Only the new originals are copied to the project's ``Original/`` directory.
- The Automatic Pipeline is **not** re-run when adding files to an existing project.

---

#### Import Translation Dialog

**Purpose**: Dialog shown when clicking the Import Translations button. Allows the user to
select which data to import from a source manifest.

**Two groups of checkboxes**:

**Line Fields** (matched by exact ``orig`` text):

| Checkbox | Default | Fields Imported |
|----------|---------|----------------|
| Preprocessed | ✅ | ``prepro`` |
| Tags | ✅ | merge into canonical ``tags`` (deduplicated; legacy ``tag`` migrated but never written) |
| Translated | ✅ | ``tl``, ``preedit`` |
| Postprocessed | ✅ | ``postpro`` |
| Wordwrap | ✅ | ``wordwr`` |
| QA (reviewed text, overwrite, TLC, edits) | ✅ | ``qa``, ``qa_overwrite``, ``edit*``, ``tlc*`` |

**Dedup Guard**: If either the current line or the imported source line has ``prepro == "__DEDUP__"``, the dialog must not import `tl`, postprocess, QA, or wordwrap stage text for that row.
| Do not overwrite lines that already have translations | ❌ | Skips lines with existing ``tl`` |

**Settings Sections**:

| Checkbox | Default | Keys Imported |
|----------|---------|---------------|
| Analysis | ❌ | ``step_state.Analysis`` |
| Information (metadata, glossary, code DB) | ✅ | ``step_state.Information.data.metadata`` except current ``project_name``, plus ``glossary``, ``code_patterns``, ``characters`` |
| Preprocessing Settings | ❌ | ``Deduplication``, ``EllipsisCompression``, ``SymbolConversion``, etc. |
| Costs / Request Settings | ❌ | ``RequestOptions`` |
| Translation Step State | ❌ | ``step_state.Translation`` |
| Postprocessing | ❌ | ``PostProcessing`` |
| Wordwrap Settings | ❌ | ``WordwrapSettings`` |
| QA / Validation Rules | ❌ | ``ValidationRules``, ``QAOptions``, ``CharacterWhitelist``, etc. |
| File / Output Settings | ❌ | ``OutputFormat`` |

---

#### Create New Translation Project Dialog

**Purpose**: Dialog shown when loading files into a new project (no existing manifest).

**Size Requirement**: The dialog window must be sized large enough to display all buttons without truncation. Minimum dimensions: 500x300 pixels.

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Project Name | Entry | Yes | User must provide the project name. No auto-suggestion — field starts empty |
| Source Files | Label | Display | Shows the list of files/folders being loaded (read-only) |
| Auto-Pipeline | Combobox | No | Select automation level for this load. **Currently hidden** pending rework |

**Behavior**:
- Dialog blocks file loading until project name is provided
- If Cancel is clicked, the entire load operation is aborted
- If a manifest already exists for these files (`source_root`), this dialog is skipped
- Project name validation: non-empty, valid filename characters only

---

#### Automatic Pipeline on File Load

**Purpose**: When files are loaded and a manifest is created, automatically execute a sequence of processing steps up to a configurable endpoint. This enables a "load and show me results" workflow where the user immediately sees analysis, costs, and can begin translation.

**Pipeline Levels** (Auto-Pipeline Dropdown):

| Level | Name | Description | Stops After |
|-------|------|-------------|-------------|
| 0 | Manual | No automation — only load files | Step 1 (lines loaded) |
| 1 | Analyze | Run analysis only | Step 2 (analysis results) |
| 2 | Estimate Original | Run analysis + estimate original tokens | Step 3 (original estimation) |
| 3 | Preprocess (Default) | Full preprocessing with defaults | Step 4 (preprocessed, estimated) |
| 4 | Mock Translate | Full pipeline with mock translation | Step 5 (mock translated, validated) |

**Default**: Level 3 (Preprocess) — provides full cost estimation before any API calls.

**Pipeline Sequence** (Steps 1-8):

When files are loaded and a project is created, the following steps execute automatically up to the configured level:

| Step | Name | Action | Skipped When |
|------|------|--------|--------------|
| 1 | Create Manifest | Show Project Name dialog. User must provide name. No auto-suggestion. Save manifest file. | Manifest already exists for `source_root` |
| 2 | Load Lines | Extract lines from all loaded files. Store in manifest `lines[].orig`. | Lines already loaded |
| 3 | Load Defaults | Apply default values from embedded `_FACTORY_DEFAULTS_INI_TEXT` constant to manifest fields. | Defaults already applied |
| 4 | Run Analysis | Execute `functions/analysis.py`. Store results in manifest (`Analysis.*` fields). | Auto-Pipeline Level < 1 |
| 5 | Populate Inferences | (Optional) Populate Glossary, Code Database, and Point of View based on analysis inference. See Options below. | `auto_inference` disabled |
| 6 | Run Original Estimation | Calculate input/output tokens for original lines. Record in manifest. Mark Costs Step first tick. | Auto-Pipeline Level < 2 |
| 7 | Run Default Preprocessing | Apply default-enabled preprocessing rules (Deduplication, Ellipsis, Symbol, PROTECTED compression). | Auto-Pipeline Level < 3 |
| 8 | Run Preprocessed Estimation | Calculate input/output tokens for preprocessed lines. Record in manifest. Mark Costs Step second tick. | Auto-Pipeline Level < 3 |

**Mock Translation (Level 4 Extension)**:

When Auto-Pipeline Level is 4, additional steps execute after Step 8:

| Step | Name | Action |
|------|------|--------|
| 9 | Mock Translation | Run translation using Mock Translation engine (no API calls) |
| 10 | Run QA Validation | Execute validation rules on mock-translated output |
| 11 | Run Postprocessing | Apply postprocessing restoration to mock output |
| 12 | Summary | Display pipeline completion summary with timing and statistics |

**Purpose of Mock Level**: Enables full pipeline testing without API costs. Users can verify that preprocessing, postprocessing, and validation work correctly before committing to real translation.

---

#### Inference Population Options (Step 5)

When `auto_inference` is enabled (Global Option), the pipeline offers several inference sub-options:

| Option | Source | Target | Description |
|--------|--------|--------|-------------|
| `infer_speakers_to_glossary` | Analysis speakers | characters[] | Add detected speakers as character glossary entries with empty Translation |
| `infer_codes_to_database` | Analysis code_patterns | CodeGlossary[] | Add detected code patterns to Code Database with default "Preserve" action; prefers `individual_codes` (per-code detail) over grouped `code_patterns` when available |
| `infer_pov` | Analysis non-dialogue | POVResult | Detect Point of View (1st/2nd/3rd person) for prompt context |
| `infer_gender` | Input step text + Analysis speaker counts | characters[].gender | Two modes: "Script only" uses `infer_genders_batch()` for single-pass batch inference across all speakers; "Script + LLM" runs batch script first then `infer_gender_llm()` for unknowns via dialogue excerpts. Both passes run in a background thread with queue-based polling (`after(100)`) and a Cancel button visible from the start to keep the UI responsive. Script pass uses five-phase batch processing (index pass → explicit gender → honorifics from others → self-pronouns → combine signals) optimized for large manifests (845+ speakers, 64K+ lines). Configurable confidence spinboxes: `gender_script_maximum` controls max lines scanned per speaker, `gender_script_minimum` controls minimum evidence required. `ignore_unknown` excludes no-evidence lines from the limit; `do_all` forces full scan even after consensus. Settings read from CherryAI.ini [utility] and API.ini [gender_inference]. |

**Manifest Keys**: Each inference option has a corresponding boolean in `Options.AutoInference.*`.

**Future Enhancement**: Additional inference options may include `infer_style` (detect appropriate style preset from sample text) and `infer_tone` (detect appropriate tone preset).

---

#### Loaded Files Panel Details

**File Tree Structure**:
- Files organized by folder hierarchy
- **Folders always appear above files** within the same directory level
- **Collapsed by default**: When files are loaded, the tree shows folders collapsed, not expanded
- Files show: filename, line count, format icon
- Multi-select enabled for bulk delete operations
- Context menu (right-click): Remove Selected, Select All in Folder, Expand All, Collapse All

**Clickable Column Headers**:
- Columns: Name, Type, Lines — each clickable to sort
- First click sorts ascending (▲ indicator appended to heading text)
- Second click on same column sorts descending (▼ indicator)
- Clicking a different column resets to ascending for that column
- When sorted by Type or Lines, folder hierarchy is flattened to a flat file list
- Default (no sort active) shows the original folder tree structure

**File Filter**:
- Text entry above the file tree for instant filtering
- Matches against display name, file type, or line count (case-insensitive)
- Non-matching files are hidden; matching files are shown in a flat list (no folder hierarchy)
- "✕" clear button resets the filter and restores the full file tree
- Filter is reset on New Project

#### Preview Panel Details

**Preview Tree**:
- Columns: Project (narrow, 1-based global idx), File (narrow, 1-based per-file line number), Content (wide, stretches), Tags (narrow)
- Shows all lines from selected file (single-file mode) or search results across all files (cross-file mode)
- Content column must properly display multi-line text (newlines rendered, not truncated)

**Cross-File Preview Search**:
- When search text is entered, the preview searches ALL loaded files (not just the selected one)
- Results show the 1-based global idx (Project column) for each matching line
- Selecting a search result automatically switches to the file containing that line
- The corresponding file is highlighted in the file tree
- "✕" clear button resets the search and returns to single-file preview mode

**Known Issues**:
- Newlines not displayed properly (second line barely visible, subsequent lines invisible)
- Needs word-wrap or expanded row height for multi-line content

#### Data Flow

**Inputs**:
- User: File/folder paths via Select File(s) dialog
- System: Encoding and format selections from Options panel

**Processing**:
1. Open file dialog (supports file/folder, single/multi selection)
2. If format filter is set and not `auto`, filter files by format
3. Show progress window with current file and progress bar
4. For each file:
   a. Detect format from extension (or use forced format)
   b. Detect encoding (or use forced encoding)
   c. Read file content using appropriate format handler (`formats/`)
   d. Extract lines array (text only, no code for game engines)
5. Build folder hierarchy for Loaded Files tree
6. Create LoadedFile objects with path, format, lines, encoding
7. Auto-create project if no manifest exists (prompt for project name)

**Outputs**:
- `total_lines: int` - Total extracted line count (all files)
- `encoding: str` - Default encoding override if user-supplied
- *(TASK 71)* `all_lines` no longer stored — access via `mgr.get_all_orig_lines()` or `lines[].orig`
- `loaded_files: List[LoadedFile]` - File metadata objects
- `file_dir: List[FileDirEntry]` - Index ranges per file (for output injection). Each entry includes a `type` field (``dialogue``, ``menu?``, ``menu``, or ``""``).

**Stored In**:
- Manifest: `source_root` (folder name), `file_dir[]`, `lines[].orig`, `lines[].tag` (optional per-line type tag)
- Manifest step data: `Input.file_count`, `Input.total_lines`, `Input.formats`

#### Step Completion

**Automatic Completion**: Step 0 is marked complete when **any file is successfully loaded**.

**Triggers on Completion** (if enabled in Global Options):
- `auto_analyze_on_load`: Automatically runs Analysis (Step 1)
- `auto_preprocess_on_load`: Automatically runs Preprocessing after Analysis (Step 4)

#### User Actions

| Action | Effect |
|--------|--------|
| Click Select File(s) | Opens unified file/folder picker dialog with Typing Enabled toggle |
| Select item in File Tree | Shows preview of that file's content |
| Right-click File Tree | Context menu: Remove Selected, Select All, Select Type (Dialogue/Menu/Mixed) |
| Multi-select + Delete | Removes all selected files |
| Click column header (Name/Type/Lines) | Sorts file tree ascending/descending with ▲/▼ indicator |
| Type in file filter | Filters loaded files by name, type, or line count (instant, case-insensitive) |
| Right-click Preview line | Context menu: Set Tag (Dialogue/Menu/Choice/Clear) for selected lines |
| Preview search box | Cross-file search: searches ALL loaded files, shows global idx, auto-switches file on selection |
| Click preview search clear (✕) | Clears search and returns to single-file preview |

#### Format Handler Integration

| Format | Handler | Extraction Behavior |
|--------|---------|---------------------|
| txt | `formats/txt.py` | One line per text line |
| csv | `formats/csv_handler.py` | Configurable column extraction |
| tsv | `formats/csv_handler.py` | Tab-delimited, same as CSV |
| json | `formats/json_handler.py` | Extract string values from structure |
| xlsx | `formats/xlsx.py` | Configurable sheet/column extraction |
| rpgmaker | `formats/rpgmaker.py` | Parse MV/MZ JSON, extract dialogue only |
| image | `formats/image.py` | OCR extraction (see image workflow) |

---

### Step 1: Analysis - Phase 59 PLANNED

**Purpose**: Analyze loaded content for translation planning. This step primarily infers information and displays it to users to support decisions about preprocessing, glossary, and translation settings. With the Phase 59 enhancements, Analysis provides actionable contextual controls that allow users to populate glossaries and configure preprocessing directly from the Findings Table via category-aware right-click menus.

**Implementation Status**:
- Core analysis: ✓ Implemented
- Statistics panel: ✓ Implemented, Phase 59 enhances
- Findings table: ✓ Implemented, Phase 59 adds contextual right-click actions
- Language detection: ✓ Implemented, Phase 59 adds project-level Chinese threshold
- Speaker detection: ✓ Implemented
- Code pattern detection: ✓ Implemented

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Run Analysis Button | Button | Executes full analysis |
| Export Button | Button | Exports findings to CSV |
| Statistics Panel | Frame | Shows line counts, percentages, dedup projections |
| View Selector | Combobox | (Optional) Switch between General/Speakers/Code views |
| Findings Table | SharedTable | Lists all findings with category-aware right-click menu |

#### Statistics Panel Details

The Statistics Panel displays a summary of the analyzed content:

| Statistic | Description |
|-----------|-------------|
| Total Lines | Count of all loaded lines |
| Empty Lines | Lines with no content (whitespace only) |
| Unique Lines | Count of distinct line contents |
| Duplicate Lines | Lines that appear more than once |
| **Projected Deduplication** | Lines remaining after aggressive deduplication |
| Language Distribution | Detected languages with percentages |
| **Dominant Language** | Project-level detected language (with threshold indicator) |

**Projected Deduplication** (NEW - Phase 59):
- Shows the projected line count if aggressive deduplication were applied
- Format: "Aggressive Dedup: X lines → Y unique (Z% reduction)"
- This is a **preview** — aggressive deduplication is applied optionally during Preprocessing (Step 4)
- Helps users decide whether to enable aggressive deduplication

---

#### Language Detection Enhancement (Phase 59)

**Project-Level Chinese/Japanese Classification**:

Japanese and Chinese share many characters (kanji/hanzi), but Japanese uniquely has **hiragana** (ひらがな) and **katakana** (カタカナ) — collectively called "kana". Chinese has NO kana characters. Korean uses a distinct script (Hangul) and is handled separately.

**Classification Logic** (Project-Level, NOT Per-Line):

1. **Identify CJK Lines**: Find all lines containing CJK characters (Chinese hanzi, Japanese kanji/kana, or both)
2. **Classify Each CJK Line**:
   - **Japanese Line**: Contains ANY hiragana or katakana characters (regardless of kanji)
   - **Chinese-Only Line**: Contains CJK characters but NO hiragana or katakana
3. **Korean Exclusion**: Lines containing only Korean Hangul are classified separately and excluded from this threshold
4. **Apply Threshold Rule**: If Chinese-only lines are **less than 30%** of total CJK lines:
   - Mark the project's dominant language as "Japanese"
   - Record that threshold reclassification was applied
5. **Rationale**: Japanese text frequently uses kanji (Chinese characters) for vocabulary. A project with mostly Japanese text may have some lines that happen to contain only kanji with no kana — these should not cause the project to be misclassified as Chinese.

**Implementation**:
```python
# In functions/analysis.py
import unicodedata

def is_hiragana_or_katakana(char: str) -> bool:
    """Returns True if character is Japanese hiragana or katakana."""
    name = unicodedata.name(char, '')
    return 'HIRAGANA' in name or 'KATAKANA' in name

def is_cjk_character(char: str) -> bool:
    """Returns True if character is CJK unified ideograph."""
    return '\u4e00' <= char <= '\u9fff'  # CJK Unified Ideographs block

def classify_cjk_line(line: str) -> str | None:
    """Classify a line as 'japanese', 'chinese_only', 'korean', or None."""
    has_cjk = any(is_cjk_character(c) for c in line)
    has_kana = any(is_hiragana_or_katakana(c) for c in line)
    has_hangul = any('\uac00' <= c <= '\ud7af' for c in line)
    
    if has_hangul and not has_cjk and not has_kana:
        return 'korean'
    if has_kana:
        return 'japanese'  # Any kana = definitely Japanese
    if has_cjk:
        return 'chinese_only'  # CJK with no kana = ambiguous, might be Chinese
    return None

def detect_project_language(lines: List[str]) -> Dict[str, Any]:
    """Project-level language detection with Japanese/Chinese threshold."""
    japanese_lines = 0
    chinese_only_lines = 0
    korean_lines = 0
    
    for line in lines:
        classification = classify_cjk_line(line)
        if classification == 'japanese':
            japanese_lines += 1
        elif classification == 'chinese_only':
            chinese_only_lines += 1
        elif classification == 'korean':
            korean_lines += 1
    
    total_cjk_lines = japanese_lines + chinese_only_lines  # Exclude Korean
    
    # Apply threshold: if Chinese-only < 30% of CJK lines, treat as Japanese project
    threshold_applied = False
    dominant_language = "Unknown"
    chinese_percentage = 0.0
    
    if total_cjk_lines > 0:
        chinese_percentage = chinese_only_lines / total_cjk_lines
        if chinese_percentage < 0.30:
            # Project is Japanese (Chinese-only lines are just kanji-heavy Japanese)
            dominant_language = "Japanese"
            threshold_applied = chinese_only_lines > 0  # Only true if we reclassified some
        else:
            dominant_language = "Chinese"
    
    return {
        'dominant_language': dominant_language,
        'threshold_applied': threshold_applied,
        'chinese_percentage': chinese_percentage,
        'japanese_lines': japanese_lines,
        'chinese_only_lines': chinese_only_lines,
        'korean_lines': korean_lines,
        'total_cjk_lines': total_cjk_lines
    }
```

**Key Distinction**:
- This is **project-level** classification, not per-line
- A single line with only kanji and no kana is NOT automatically Chinese — it's "ambiguous"
- The 30% threshold determines the **project's** dominant language
- Once dominant language is determined, the Translation Step respects it for all lines

**Manifest Storage**:
- `Analysis.dominant_language: str` — "Japanese", "Chinese", or "Unknown"
- `Analysis.threshold_applied: bool` — Whether Chinese-only lines were reclassified as Japanese
- `Analysis.chinese_percentage: float` — Percentage of Chinese-only lines (before reclassification)
- `Analysis.japanese_lines: int` — Lines with kana (definitely Japanese)
- `Analysis.chinese_only_lines: int` — Lines with CJK but no kana
- `Analysis.korean_lines: int` — Lines with Korean Hangul only

**Translation Step Integration**:
When `skip_non_source_language` is enabled in Global Options:
- If `dominant_language` is "Japanese" and `threshold_applied` is True:
  - Do NOT skip Chinese-only lines (they are part of the Japanese project)
  - Only skip truly non-source language lines (e.g., English-only lines)
- Korean lines are always handled separately based on source language setting

---

#### Findings Table Design (Phase 59)

**Approach**: Keep the existing Findings Table and enhance it with category-aware contextual right-click functionality. If UI complexity makes this impractical, implement switchable table views.

**Option A: Enhanced Existing Table (Preferred)**

The existing Findings Table is retained with all current columns and functionality, plus:

1. **Category-Aware Right-Click Menu**: When user right-clicks rows, the menu dynamically shows options based on the **Category** column of the selected row(s):
   - If selected rows are **Speakers** → Show speaker-specific options
   - If selected rows are **Code Patterns** → Show code pattern-specific options
   - If selected rows are **Mixed** → Show only generic options (Copy, Select All)

2. **Speaker Truncation**: If more than 20 speakers are detected, only the top 20 by count are shown in the table with a note: "Showing top 20 of N speakers. Switch to Speakers view for full list."

3. **Multi-Select Support**: Ctrl+Click, Shift+Click to select multiple rows. Right-click menu applies to all selected rows of the same category.

**Option B: Switchable Table Views (Fallback)**

If the category-aware context menu proves too complex to implement cleanly, use a **View Selector** dropdown above the table:

| View | Contents | Features |
|------|----------|----------|
| **General Analysis** | All findings (current behavior) | Speaker truncation (top 20), read-only display, no new features |
| **Speakers** | Speaker findings only | Full speaker list, speaker-specific right-click menu |
| **Code Patterns** | Code pattern findings only | Full pattern list, code pattern-specific right-click menu |

**Implementation Recommendation**: Start with Option A. Only fall back to Option B if testing reveals usability issues with mixed-category selection.

---

#### Findings Table Columns (Existing)

| Column | Width | Description |
|--------|-------|-------------|
| Category | 100px | Finding type: Speakers, Code Patterns, Top Duplicates, Language |
| Finding | 200px | The detected item (speaker name, normalized code pattern, etc.) |
| Count | 80px | Number of occurrences |
| Details | stretch | Auto-populated: sample line for speakers, type + examples for code patterns |

**Enhancements (Implemented)**:
- All speakers shown without truncation, ordered by count descending
- Individual code patterns shown (normalized) instead of type summaries
- Details column shows character glossary info (translation + notes) for speakers, and code type/examples for code patterns
- Count Filter field in filter bar: supports `<X`, `>X`, `<=X`, `>=X`, `=X` syntax; toggle button (≥/≤) switches default bare-number comparison mode
- **Collapsible instance rows**: Code patterns with multiple raw-code instances show `[+]` prefix. Double-click to expand/collapse sub-rows showing each instance variant and its per-instance count. Patterns with instances sort above same-count patterns without. Expanded rows show `[-]` prefix; instance children are indented with `  └ ` prefix and tagged with "instance" tag.

---

#### Speaker Right-Click Menu (Phase 59)

When user right-clicks on rows where Category = "Speakers":

| Menu Item | Action | Description |
|-----------|--------|-------------|
| Add to Glossary | `add_speaker_to_glossary(name)` | Creates character glossary entry with speaker as original_name |
| Set Role → | Submenu | Protagonist, Love Interest, Major, Minor — stored in character glossary role field |
| Set Gender → | Submenu | Male, Female, Non-Binary, Transwoman, Transman, Other, Unknown — stored in character glossary gender field |
| Set Translation | `prompt_translation(name)` | Opens dialog to input custom translation, fills character glossary name (translation) field |
| Add to Code Database | `add_speaker_to_code_glossary(name)` | Creates Code Database entry to protect speaker name |
| Copy Name | `copy_to_clipboard(name)` | Copies speaker name to clipboard |
| Select All with Speaker | `filter_preview_by_speaker(name)` | Filters preview panel to show only lines from this speaker |

**Role/Gender Behavior**:
- Role is stored in the character glossary entry’s `role` field
- Gender is stored in the character glossary entry’s `gender` field
- All speaker actions write to **character glossary** (manifest `characters` key) via `_upsert_character_entry()`, not to project glossary entries
- Setting Role overwrites any existing Role; Gender overwrites existing Gender
- Setting Gender overwrites the `gender` field directly with the selected value
- Glossary panel in Information Step (Step 3) displays these entries with Gender/Role merged into Notes column
- Details column in Findings table is refreshed after each action to reflect current glossary state

**Multi-Select Support**:
- Select multiple speaker rows (Ctrl+Click, Shift+Click)
- Menu shows "Add X speakers to Glossary" for bulk operations
- Role/Gender submenu applies to all selected speakers

**Inference Details** (Add to Glossary with Inference — future enhancement):
1. Speaker name is sent to configured LLM with prompt: "Provide a likely English translation for this Japanese name: {name}"
2. Response is parsed and placed in Translation field
3. Entry is marked with `source: "analysis_inference"` for tracking
4. If inference fails, falls back to standard Add to Glossary (empty Translation)

---

#### Code Pattern Right-Click Menu (Phase 59)

When user right-clicks on rows where Category = "Code Patterns":

| Menu Item | Action | Description |
|-----------|--------|-------------|
| Preserve | `set_pattern_action(pattern, 'preserve')` | Pattern kept unchanged. Default. Persisted to Code Database. |
| Remove | `set_pattern_action(pattern, 'remove')` | Pattern removed from output. Persisted to Code Database. |
| Translate | `set_pattern_action(pattern, 'translate')` | Pattern translated as text. Persisted to Code Database. |
| Replace → | Submenu | Generic (placeholder), Custom Input (dialog). Persisted to Code Database. |
| Is a Name | `set_pattern_type(pattern, 'name')` | Identifies pattern as a name. Also adds to glossary with temp replacement. |
| Is Text | `set_pattern_type(pattern, 'text')` | Identifies pattern as text content. |
| Is a Number | `set_pattern_type(pattern, 'number')` | Identifies pattern as numeric. |
| Is Invisible | `set_pattern_type(pattern, 'invisible')` | Pattern is control code, not visible. Default. |
| Nameable... | `_show_nameable_dialog(pattern)` | Opens dialog with Character/Company/Location modes and gender-aware name assignment. |
| Copy Pattern | `copy_to_clipboard(pattern)` | Copies pattern to clipboard |
| Show Lines with Pattern | `filter_findings_by_pattern(pattern)` | Sets findings filter to show pattern |

**Action Behavior** (Preserve/Remove/Translate/Replace):
- Only one action can be active at a time
- Selection persisted to Code Database in manifest via `save_code_glossary()`
- Default action is "Preserve" with "Is Invisible" type
- All actions stored as `code_patterns[]` in manifest data

**Type Behavior** (Is a Name/Text/Number/Invisible):
- Identifies what the code pattern represents
- Informs the LLM about appropriate handling
- "Is Invisible" is the default (most code patterns are control sequences)
- Only one type can be active at a time
- "Is a Name" additionally adds the pattern to the glossary with a temporary replacement name

**Nameable Dialog** (Nameable...):
- For nameable variables (e.g., `{{主人公}}`) — characters, companies, or locations
- Opens a Toplevel dialog with three modes:
  - **Character**: Gender selection (Male/Female/Non-Binary) → John Smith / Jane Smith / Alex Smith
  - **Company**: Assigns generic company name (Acme Corp, Globex Inc, Initech Ltd)
  - **Location**: Assigns generic place name (Millfield, Oakville, Riverside)
- Stores replacement name in **character glossary** (manifest `characters` key) and code pattern in **Custom Placeholders** (manifest `CustomPlaceholders` key, restore_after=True)
- Temporary name used during preprocessing so the LLM handles surrounding text naturally

**Multi-Select Support**:
- Select multiple code pattern rows (Ctrl+Click, Shift+Click)
- Bulk operations: "Set X patterns to Preserve"
- Action and Type changes apply to all selected patterns

**Code Database Population**:
- Selections are stored in `code_patterns[]` manifest section via `save_code_glossary()`
- Automatically populates Code Database in Information Step (Step 3)
- Automatically populates Preprocessing options (Step 4)

---

#### Data Flow

**Inputs**:
- From Step 0: manifest `lines[].orig` via `mgr.get_all_orig_lines()`
- From Session: Previously stored analysis results

**Processing** (via `gui/helpers/analysis_adapter.py` → `functions/analysis.py`):
1. Count total lines, empty lines, unique lines
2. Detect duplicate lines and frequency
3. Calculate aggressive deduplication projection
4. Detect project-level language using Japanese/Chinese threshold logic:
   - Classify each line as Japanese (has kana), Chinese-only (CJK but no kana), or Korean
   - Apply 30% threshold to determine project dominant language
5. Detect speaker patterns (Name: "dialogue")
6. Detect code patterns (variables, tags, escapes)
7. Build unified Findings table rows with category column

**Outputs**:
- `total_lines: int`
- `empty_lines: int`
- `unique_lines: int`
- `duplicate_count: int`
- `aggressive_dedup_projection: int` — Lines after aggressive dedup
- `duplicates: Dict[str, int]` - Line text to count
- `dominant_language: str` - Project-level detected language
- `threshold_applied: bool` - Whether Chinese-only lines were reclassified
- `chinese_percentage: float` - Percentage of Chinese-only lines
- `japanese_lines: int` - Lines with kana (definitely Japanese)
- `chinese_only_lines: int` - Lines with CJK but no kana
- `korean_lines: int` - Lines with Korean Hangul only
- `speakers: Dict[str, int]` - Speaker to occurrence count
- `code_patterns: Dict[str, int]` - Pattern type to count

**Stored In**:
- Manifest step data (step_id=1)
- Fields: `Analysis.total_lines`, `Analysis.unique_lines`, `Analysis.aggressive_dedup_projection`, `Analysis.dominant_language`, `Analysis.threshold_applied`, `Analysis.chinese_percentage`, etc.

#### User Actions

| Action | Effect |
|--------|--------|
| Click Run Analysis | Runs analysis in background thread |
| Click Export | Saves findings to CSV file |
| Switch View (if implemented) | Changes between General/Speakers/Code views |
| Right-click Findings row | Category-aware context menu (different options for Speaker vs Code Pattern) |
| Multi-select + Right-click | Bulk actions on selected items of same category |
| Double-click Speaker finding | Opens Add to Glossary dialog pre-filled |
| Double-click Code Pattern finding | Opens Code Database dialog pre-filled |

#### Current State

The Analysis step is functional and provides valuable information. Phase 59 adds category-aware contextual right-click actions to the Findings Table and enhanced project-level language detection.

#### Phase 59 Implementation Checklist

- [ ] Add Projected Deduplication to Statistics Panel
- [ ] Add Dominant Language to Statistics Panel (with threshold indicator)
- [ ] Implement project-level Japanese/Chinese threshold detection (30% of Chinese-only lines)
- [ ] Add category-aware right-click menu to Findings Table
- [x] Implement Speaker right-click menu (Add to Glossary, Set Role, Set Gender, Set Translation)
- [x] Implement Code Pattern right-click menu (Preserve/Remove/Translate/Replace, Is Name/Text/Number/Invisible)
- [x] Add multi-select support with same-category validation
- [x] Implement speaker truncation in General view (top 20 with note)
- [ ] (Optional) Implement View Selector for switchable views if category-aware menu is too complex
- [x] Ensure Glossary in Information Step gets populated from Speaker actions
- [x] Ensure Code Database in Information/Preprocessing Steps gets populated from Code Pattern actions
- [ ] Add manifest fields for new analysis data
- [ ] Update analysis_adapter.py to route context menu actions
- [ ] Write tests for project-level language threshold logic
- [ ] Write tests for context menu actions

---

### Step 4: Costs

**Purpose**: Calculate and display estimated costs before translation and track actual costs after translation. The Costs step provides visibility into resource consumption and enables informed decisions about model selection and preprocessing optimization.

#### Design Goals

1. **Pre-Translation**: Show estimated costs based on current lines, preprocessing state, and selected model
2. **Post-Translation**: Record actual costs and show the difference from estimates (future)
3. **Cost Types**: Translation, Editing, TLC, Summary generation, Glossary inference, Tone/Style inference (future)

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| **Options Panel** | LabelFrame | Contains model and request settings |
| Primary Model Dropdown | Combobox | Select model for translation. Syncs with Global Options. Auto-estimates on change. |
| Lines/Request Spinbox | Spinbox | Maximum lines per request (5-200). Dynamic adjustment at context markers. |
| Tokens/Request Spinbox | Spinbox | Maximum tokens per request (NEW). Acts as alternative maximum alongside lines. |
| Refresh Button | Button | Fetch latest model data from providers (OpenAI, Gemini, Claude, Mistral, Grok, DeepSeek) |
| **Token Counts Panel** | LabelFrame | Display token breakdown |
| Token Grid | Frame | Shows Original, Preprocessed, and Saved columns for Lines, Input Tokens, Output Tokens |
| Prompt Overhead Label | Label | Shows total and average prompt overhead per request (per-request selective filtering) |
| **Cost Estimate Panel** | LabelFrame | Display cost projection |
| Cost Labels | Labels | Input cost (with Prompt Cost and Cached Input Cost sub-rows when model supports caching), Output cost, Total cost for selected model |
| **Time Estimate Panel** | LabelFrame | Display time projection |
| Time Labels | Labels | Estimated duration accounting for rate limits and concurrent requests |
| **Model Comparison Table** | SharedTable | Compare all available models (includes Cached $/1M column) |
| **Bottom Panel** | Frame | Actions and status (future enhancements) |

#### Options Panel Details

**Primary Model Dropdown**:
- Values: All models from `functions/config.py` MODEL_PRICING
- Syncs with Global Options: Changes here update global model setting and vice versa
- Triggers: Auto-runs estimation when model changes
- Current state: Already implemented and working

**Lines/Request Spinbox**:
- Range: 5-200 lines per request
- Acts as **maximum** - requests may contain fewer lines when cut at context markers (end of file, speaker change)
- Future: Request merging to fill capacity when subsequent chunks have no rolling context

**Tokens/Request Spinbox** (Priority Implementation):
- Range: 500-32000 tokens per request
- Acts as **alternative maximum** alongside Lines/Request
- Behavior: Whichever limit is reached first (lines OR tokens) triggers chunk boundary
- Ensures requests don't exceed model context limits

**Refresh Button**:
- Purpose: Fetch current model pricing and capabilities from API providers
- Updates: Model Comparison table with latest data
- Providers: OpenAI, Gemini, Claude, Mistral, Grok, DeepSeek
- Status: Currently not functional, needs implementation

#### Token Counts Panel Details

Displays token breakdown in a grid format:

| Metric | Original | Preprocessed | Saved |
|--------|----------|--------------|-------|
| Lines | X | Y | Z |
| Input Tokens | X | Y | Z |
| Output Tokens (est) | X | Y | Z |
| Prompt Overhead | - total + avg/request - |

**Current Issues**:
- Only counts original lines, does not include prompt tokens
- Prompt overhead not calculated from actual prompt builder output
- Does not use preprocessed lines even after preprocessing completes

**Required Behavior**:
- Include prompt overhead from `gui/helpers/prompt_adapter.py` build_prompt_preview()
- Add default prompts (summary, tone, style) to per-request estimate
- Add conditional prompts (code glossary, selective, rolling context) based on settings
- Use preprocessed lines after Step 4 completes

#### Cost Estimate Panel Details

**Current Display (Purely Additive)**:
- **Input Cost**: (content_tokens / 1M) × model_input_price — content/line tokens only
- **Prompt Cost**: ((prompt_tokens − cached_tokens) / 1M) × model_input_price — non-cached prompt overhead
- **Cached Cost**: (cached_tokens / 1M) × model_cached_input_price — cached prompt portion
- **Output Cost**: (output_tokens / 1M) × model_output_price
- **Total Cost**: Input + Prompt + Cached + Output (four additive components)

All displayed dollar amounts are rounded up to the next cent via `_ceil_to_cents()`.
All four cost rows are primary non-indented rows (same hierarchy as Input/Output).

**Token Display**:
- Prompt Tokens row shows the non-cached portion: prompt_tokens − cached_tokens
- This ensures Input + Prompt + Cached = Total Input (purely additive)

#### Time Estimate Panel Details

**Current Issues**:
- Only accounts for requests per minute rate limit
- Does not factor in concurrent requests
- Does not account for token generation speed

**Required Calculation**:
```
time = max(
    total_requests / concurrent_requests × time_per_request,
    total_tokens / token_speed,
    total_requests / rate_limit_rpm × 60
)
```

Where:
- `concurrent_requests`: Max parallel API calls allowed
- `token_speed`: Tokens per second (model-specific, tracked from previous translations)
- `rate_limit_rpm`: Requests per minute limit for provider

#### Model Comparison Table Details

**Current Columns**:
- Model Name
- Input Price ($/1M tokens)
- Output Price ($/1M tokens)
- Concurrent Requests

**Required Columns** (Priority):
- Price Original: Calculated from original lines upon Auto-Estimation
- Price Preprocessed: Calculated after preprocessing applied
- Savings: (Price Original - Price Preprocessed) / Price Original × 100%

**Future Columns** (Low Priority):
- Token Speed: Tokens/sec, calculated from previous translation history
- Batch Available: Yes (with discount %) or No
- Image Available: Yes or No

**Data Source**:
- Static data from `functions/config.py` MODEL_PRICING
- Dynamic data from `models.db` file (updated by Refresh button)

#### Estimation Workflow

The Costs step has **two distinct estimation states** tracked separately:

**1. Auto-Estimation (Original)**:
- Trigger: Files loaded in Step 0 (Input), manifest initialized
- Input: Original lines from manifest `lines[].orig`
- Prompt: Default prompts only (no preprocessing-specific prompts)
- Result: Populates "Original" columns
- Progress Tracker: Marks first tick on Costs step

**2. Preprocessed Estimation**:
- Trigger: Preprocessing applied in Step 4
- Input: Preprocessed lines from `prepro[]`
- Prompt: Full prompts including conditional (code glossary, rolling context if enabled)
- Result: Populates "Preprocessed" and "Saved" columns
- Progress Tracker: Marks second tick on Costs step

**3. Manual Estimation**:
- Trigger: User clicks Estimate button
- Behavior: Runs both Original and Preprocessed estimation with current settings
- Updates: All columns with latest data

**Progress Tracker Integration**:
- Two checkmarks for Costs step:
  - ☐ → ☑ Original estimation complete
  - ☐ → ☑ Preprocessed estimation complete
- Checkmarks reset to unchecked when:
  - Settings affecting prompt change (affects both)
  - Preprocessing settings change (affects preprocessed only)
  - Files added/removed (affects both)

#### Data Flow

**Inputs**:
- From Step 0: manifest `lines[].orig` (original lines)
- From Step 3: `prepro[]` (preprocessed lines, if available)
- From Step 2: Summary, tone, style, characters, code glossary (for prompt calculation)
- From Global Options: Model, temperature, chunk size, rate limits

**Processing** (via `gui/helpers/chunker_adapter.py` → `functions/chunker.py`):
1. Count tokens in original lines (tiktoken or heuristic)
2. Count tokens in preprocessed lines (if available)
3. Calculate full prompt tokens including:
   - System prompt (base instructions)
   - Summary prompt (if summary provided)
   - Tone/style prompts (if presets selected)
   - Code glossary prompt (if patterns defined)
   - Rolling context prompt (if enabled)
   - Per-chunk content
4. Calculate savings from preprocessing
5. Estimate output tokens: count tokens of Lines to Translate and apply a language-specific output multiplier (e.g., ×1.2 for JP→EN; every language pair has its custom multiplier based on typical expansion/contraction ratios)
6. Look up model pricing (input/output per 1M tokens)
7. Calculate costs for multiple models
8. Estimate time using concurrent requests, rate limits, and token speed

**Outputs**:
- `input_tokens_original: int` - Input tokens before preprocessing (saved in manifest)
- `input_tokens_preprocessed: int` - Input tokens after preprocessing (saved in manifest)
- `output_tokens_original: int` - Estimated output tokens from original (saved in manifest)
- `output_tokens_preprocessed: int` - Estimated output tokens from preprocessed (saved in manifest)
- `prompt_overhead: int` - Total prompt overhead across all requests (per-request selective filtering)
- `cost_original: float` - Cost before preprocessing (not saved — calculated on display)
- `cost_preprocessed: float` - Cost after preprocessing (not saved — calculated on display)
- `cost_saved: float` - Savings from preprocessing (not saved — calculated on display)
- `savings_percent: float` - Percentage saved (not saved — calculated on display)
- `chunks_required: int` - Number of API requests
- `estimated_time: str` - Formatted duration
- `difference: float` - Token difference between original and preprocessed (displayed, not saved)

**Four Saved Token Counts**: The manifest stores exactly four token values from estimation — input/output for both original and preprocessed states. These are used to calculate costs with available models and their rates for display. Cost estimations and savings are saved for the selected model only when translation actually starts.

**Stored In**:
- Manifest step data (step_id=2)
- Fields: `Costs.input_tokens_original`, `Costs.input_tokens_preprocessed`, `Costs.output_tokens_original`, `Costs.output_tokens_preprocessed`, `Costs.estimation_state`

**Estimation uses the shared Request Builder** (see §5.2): The same `functions/prompt_builder.py` request builder function used by Translation is called during estimation to ensure token counts match actual request composition. Input tokens exclude Meta Settings (they are not counted). Estimation runs:
- Once automatically after files are loaded, defaults are written, and default-enabled preprocessing has been done
- When triggered after preprocessing settings change
- Before translation starts (confirmation window)

#### User Actions

| Action | Effect |
|--------|--------|
| Select model | Updates global model, triggers auto-estimation |
| Change Lines/Request | Recalculates chunk count and time |
| Change Tokens/Request | Recalculates chunk boundaries |
| Click Refresh | Fetches latest model data from providers |
| Click Estimate | Runs full manual estimation (both states) |

#### Costs Rework (API Requests & Costs)

**Cache Cost Calculation**:
- `CACHE_HIT_RATE = 0.80` — 80% of the static prompt prefix is assumed cached after first request
- `_get_static_prompt_tokens()` builds the prompt with `chunk_lines=[]` and `rolling_context_text=""` to isolate static sections (slots 1-7b)
- Cache eligible = static_prompt_tokens × (n_requests − 1)
- Cached tokens = cache_eligible × CACHE_HIT_RATE
- Direct 4-component cost calculation (no `estimate_cost()` + savings subtraction):
  - `content_cost = content_tokens / 1M × input_rate`
  - `prompt_cost  = (prompt_tokens − cached_tokens) / 1M × input_rate`
  - `cached_cost  = cached_tokens / 1M × cached_rate`
  - `output_cost  = output_tokens / 1M × output_rate`
  - `total_cost   = content_cost + prompt_cost + cached_cost + output_cost`
- `EstimationResult.input_cost` stores content-only cost (not the full input bundle)
- Guard: no caching applied when static prefix < 1024 tokens or only 1 request
- Module-level `_ceil_to_cents()` and `_fmt_cost()` helpers ensure all displayed costs are rounded up to the next cent

**Mode Button Labels**:
- Non-normal modes (Batch/Flex/Priority) show "(Available)" or "(Unavailable)" suffix
- Availability determined by model pricing (batch_input/flex_input/priority_input rates)
- Button width increased to 20 to accommodate suffix text

**Instant Mode Cost Recalculation**:
- `_recalculate_costs_for_mode()` updates all cost labels and comparison table from existing token counts without re-estimation
- `_select_request_mode()` calls `_recalculate_costs_for_mode()` instead of `_run_estimation()`

**Model Lock During Estimation**:
- Model combo set to `state="disabled"` when estimation starts
- Restored to `state="readonly"` in `_estimation_complete()`

**Settings Decoupling**:
- `_on_model_changed()` no longer calls `_load_model_settings()`
- `_settings_loaded_once` flag ensures settings loaded from API.ini only on first tab entry
- `on_new_project()` resets the flag so next project loads fresh settings

**Per-Model Settings Priority (Costs)**:
- `_do_estimation()` reads `chunk_size` and `tokens_limit` from `_chunk_var`/`_tokens_var`, which are set by `_load_model_settings()` from per-model API.ini `[model_settings]`
- Global Options values are NOT applied on top — they serve as fallback only within `_load_model_settings()`
- Only `request_slicing` is read from GlobalOptions at estimation time (no per-model override)

**Apply Settings to Model**:
- Button text: "📤 Apply Settings to Model" (one-way write to API.ini)
- Confirmation text: "✓ Applied"
- Model changes do NOT reload settings into the UI

#### Future Enhancements (Low Priority)

- **Request Merging**: Combine small trailing chunks into previous request when no rolling context needed
- **Final Cost Recording**: Track actual tokens/cost after translation completes
- **Cost Comparison**: Show estimated vs actual difference
- **Additional Cost Types**: Editing, TLC, Summary generation, Glossary inference
- **Cost History**: Track costs across multiple translation sessions
- **Budget Warnings**: Alert when estimated cost exceeds configured budget

---

### Step 2: Information

**Purpose**: Configure project metadata and translation context. All fields contribute to building the final translation prompt. Every entry is saved in the manifest for persistence.

**Implementation Status:** ✅ Phase 41 DONE — All 10 tasks implemented (57 tests passing)

#### Design Goals

1. **Prompt Construction**: Every relevant field feeds into the translation prompt sent to the LLM
2. **Project Persistence**: All data saved to manifest for session recovery
3. **Glossary Integration**: Project-specific and global glossaries support selective prompt inclusion. `load_all_glossary_entries()` merges project entries with global glossary entries when enabled; project entries take priority over global duplicates
4. **Code Pattern Management**: Detected patterns from Analysis can be managed with preservation rules

---

#### Widget: Project Details

**Purpose**: Core project identification fields.

| Field | Type | Behavior | Prompt Format |
|-------|------|----------|---------------|
| Project Name | Entry | Auto-populated from manifest `ProjectName` (set during Input step); falls back to folder name suggestion | Not included in prompt |
| Title | Entry | Full name of the work (game, novel, etc.) | `Title: [value]` |
| Genre | Entry + Dialog | Comma-separated genres; `...` button opens multi-select | `Genre: [value]` |

**Genre Dialog Behavior**:
- Opens selection window with genre checkboxes
- Each selection separated by `, ` (comma + space)
- **Required Fix**: Dialog should ADD to existing content, not overwrite
- Expanded genre list: Visual Novel, RPG, Action, Adventure, Simulation, Puzzle, Horror, Romance, Fantasy, Sci-Fi, Historical, Slice of Life, Mystery, Comedy, Drama, Isekai, Martial Arts, Supernatural, Thriller, Mecha

**Manifest Keys**: `ProjectName`, `Title`, `Genre`

---

#### Widget: Languages

**Purpose**: Set source and target languages for translation.

| Field | Type | Options | Prompt Format |
|-------|------|---------|---------------|
| Source | Combobox | Japanese, Chinese (Simplified), Chinese (Traditional), Korean, English, Other | `Translate {Source} into {Target}` |
| Target | Combobox | English, Japanese, Chinese (Simplified), Chinese (Traditional), Korean, Spanish, French, German, Portuguese, Russian, Other | (combined with Source) |

**"Other" Behavior**:
- When "Other" selected, prompt user for custom language input
- Accept any valid text input
- Store custom value in manifest

**Manifest Keys**: `SourceLanguage`, `TargetLanguage`

---

#### Widget: Summary (rename from Summary / Description)

**Purpose**: Provide plot summary for translation context.

| Component | Type | Behavior |
|-----------|------|----------|
| Summary Text | ScrolledText | Multi-line input, 2 rows height |
| Restore Default | Button | "🔄 Restore Default" resets to DEFAULT_SUMMARY_TEXT |

**Default Text**: `DEFAULT_SUMMARY_TEXT` constant — "Write a short summary of the work here. Mentioning protagonist(s) and Point of View is not necessary and will be automatically provided."

**Prompt Format**: `Summary: [contents]`

**Required Behavior**:
- Widget title rename: "Summary / Description" → "Summary"
- Contents included in system prompt when non-empty
- `_ensure_default_texts()` populates with DEFAULT_SUMMARY_TEXT when empty on step entry
- "🔄 Restore Default" button replaces current text with DEFAULT_SUMMARY_TEXT

**Manifest Key**: `Summary`

**Future Enhancement**: Button to generate summary via iterative API inference (costly operation). For fictional text, summary must include protagonist name and point of view.

---

#### Widget: Translation Style and Tone

**Purpose**: Control translation style and emotional tone.

**Style Dropdown**:
| Preset | Full Display Text |
|--------|-------------------|
| literal | Literal - Word-for-word translation preserving original structure |
| natural | Natural - Fluent translation adapted to target language |
| creative | Creative - Liberal adaptation with interpretation |
| formal | Formal - Professional language register |
| casual | Casual - Informal, conversational language |
| technical | Technical - Precise terminology |
| literary | Literary - Artistic prose style |
| custom | Custom - User-defined style |

**Tone Dropdown**:
| Preset | Full Display Text |
|--------|-------------------|
| neutral | Neutral - Balanced, no strong emotion |
| serious | Serious - Grave, solemn atmosphere |
| humorous | Humorous - Expect jokes and jests |
| dramatic | Dramatic - Intense, theatrical |
| lighthearted | Lighthearted - Cheerful, upbeat mood |
| dark | Dark - Grim, ominous atmosphere |
| romantic | Romantic - Warm, emotional context |
| action | Action - Fast-paced, energetic sequences |
| custom | Custom - User-defined tone |

**Custom Override Behavior**:
- Each preset has a Custom Text entry below it (ScrolledText, height=1, Consolas 9pt)
- Text field auto-populates with preset prompt text on step entry via `_ensure_style_tone_text()`
- If Custom Text is filled: Dropdown becomes visually grayed (disabled appearance), only Custom used in prompt
- If Custom Text is empty/deleted: Dropdown becomes active, preset used in prompt
- Delete button width=10 to prevent emoji/text clipping

**Button Alignment**: Save, Delete and Enabled|Disabled buttons are right-aligned (pack side="right") matching the Summary section layout.

**Prompt Format**:
- Style: `Style: [Full Display Text or Custom Value]`
- Tone: `Tone: [Full Display Text or Custom Value]`

**Manifest Keys**: `StylePreset`, `CustomStyle`, `TonePreset`, `CustomTone`

**Data Flow**: translate.py `_build_system_prompt_from_manifest()` reads style and tone from `step_state.Information.data.metadata` (keys: `style`, `tone`). If non-empty, they are appended to the system prompt as `# Translation Style Guidelines\n...` and `# Translation Tone\n...` sections. The method also reads language direction, system instructions, summary, genre, glossary, characters, and rolling context from the same metadata dict. Values are saved/loaded via manifest bindings (`bind_text_to_field` for CustomStyle/CustomTone, `bind_combobox_to_field` for StylePreset/TonePreset).

---

#### Widget: System Instructions (rename from Prompt)

**Purpose**: User-defined additional instructions for the LLM.

| Component | Type | Behavior |
|-----------|------|----------|
| Preset Dropdown | Combobox | Default / Custom / user-saved presets |
| Save Preset | Button | "💾 Save" prompts for name, saves text + name (right-aligned) |
| Delete Preset | Button | "🗑 Delete" removes selected user preset (right-aligned) |
| Enabled/Disabled | Button | Toggle section on/off (right-aligned) |
| Instructions Text | ScrolledText | Multi-line input, 4 rows; greyed out when disabled |

**Button Alignment**: Save, Delete and Enabled|Disabled buttons are right-aligned (pack side="right") matching the Summary section layout.

**Default Text**: `DEFAULT_SYSTEM_INSTRUCTIONS` loaded from `default/example.txt` at import time.

**Preset System** (mirrors Style/Tone preset pattern):
- `_SI_PRESETS_FILE` = `user/presets/system_instructions_presets.json`
- `DEFAULT_SI_PRESETS` dict: `{"Default": DEFAULT_SYSTEM_INSTRUCTIONS}`
- `_load_si_presets()` merges built-in defaults with user-saved presets
- Selecting "Default" populates text from `DEFAULT_SYSTEM_INSTRUCTIONS`
- Selecting "Custom" clears text for free-form input
- Selecting a user preset populates text from saved content
- Save button: uses `simpledialog.askstring()` for name, `_unique_preset_name()` for dedup
- Delete button: removes from presets dict and JSON file; reverts to "Default"
- `_on_si_preset_changed()` populates text when preset selection changes
- `_ensure_default_texts()` populates with DEFAULT_SYSTEM_INSTRUCTIONS when empty on step entry

**Required Rename**: "Prompt" → "System Instructions"

**Prompt Format**: `System Instructions: [contents]`

**Manifest Keys**: `Prompt` (text content), `SIPreset` (selected preset name)

**Data Flow**: translate.py `_build_system_prompt_from_manifest()` reads `Prompt` from manifest and includes it in the system prompt sent to the LLM.

---

#### Widget: Glossary Settings (Selective Glossary) — Merged into Knowledge Base (TASK 76)

> **Note**: This section is historical. In TASK 76, the Glossary Settings widget was merged into the Knowledge Base widget (see below). The project glossary table with selective prompt inclusion remains in the Glossary (Characters) widget. The global glossary toggle and project-to-global export are now in the Knowledge Base widget.

**Selective Prompt Inclusion** (unchanged):
- Glossary entries only included in prompt when their Original term appears in the current chunk
- Reduces token usage by excluding irrelevant entries
- Format in prompt: `Glossary:\n- [Original]: [Translation] ([Notes])`
- Entries with `active=False` are excluded from prompts entirely (TASK 76)

**Manifest Key**: `Glossary.project_entries[]`

---

#### Widget: Code Database (rename from Code Glossary)

**Purpose**: Manage code patterns for preservation, translation, or removal.

| Component | Type | Function |
|-----------|------|----------|
| Pattern Table | Treeview | Columns: Pattern, Category, Action, Code Examples |
| +Add | Button | Open pattern editor dialog |
| Edit | Button | Edit selected pattern |
| Remove | Button | Remove selected pattern(s) |
| Import from Analysis | Button | Import detected patterns (currently not working - needs fix) |

**Pattern Editor Dialog Fields**:
| Field | Type | Description |
|-------|------|-------------|
| Pattern | Entry | RegEx pattern or literal string (RegEx support required) |
| Category | Combobox + Entry | Dropdown with custom input. Categories: RPG Maker Variable, Ruby Code, HTML Tag, Control Code, Placeholder, Custom |
| Action | Combobox | Preserve, Translate, Remove |
| Code | Entry | Actual code examples in JSON array format: `["\\V[1]", "\\V[2]"]` (escape quotes with `\`) |
| Notes | Entry | Usage notes (displayed in prompt for Translate action) |

**Action Behaviors**:

| Action | During Translation | During Postprocessing |
|--------|-------------------|----------------------|
| Preserve | Add to prompt: "Preserve code patterns: [examples]" | Auto-recover or flag for QA if not recoverable |
| Translate | Add to prompt: "[Code] - [Notes]" for contextual translation | No special handling |
| Remove | Not mentioned in prompt | Strip from translation output if found |

**Code Field Format**:
- JSON array format: `["code1", "code2"]`
- Escape literal quotes: `["\"quoted\""]`
- Used to validate pattern matches and generate examples for prompt
- Analysis fills this field automatically

**Pattern Validation**:
- If Pattern is RegEx: Code examples validated against pattern
- If new Code found matching pattern: Auto-add to Code field

**Category Management**:
- Users can type custom categories (instant add to dropdown)
- Categories enable selective import/export from Knowledge Base

**Manifest Key**: `CodeGlossary[]` (array of CodePattern objects)

---

#### Widget: Knowledge Base (TASK 76 — replaces Glossary Settings + Global Glossary/Database)

**Purpose**: Unified widget for managing global glossary and code database resources shared across all projects, with per-entry Active/Inactive toggle and Enabled/Disabled state for prompt inclusion.

**Header Widgets** (in collapsible header row):
| Component | Type | Function |
|-----------|------|----------|
| Enabled/Disabled | Button | Toggle Knowledge Base on/off (controls `use_global_glossary` manifest flag) |
| Copy Project → Global | Button | Export project glossary entries to global glossary file |

**Body Layout**:
| Component | Type | Function |
|-----------|------|----------|
| Mode Switch | Combobox | Toggle between "Glossary" and "Code Database" modes |
| Search | Entry | Filter entries by text match across all visible columns |
| Column Filter | Combobox | Filter by specific column value (e.g., Active=True entries only) |
| Knowledge Base Table | Treeview | Columns vary by mode; includes Active (✓/✗), Original/Pattern, Translation/Action, Notes |
| Entry Count | Label | Shows "X entries" with live count |
| +Add | Button | Add new entry to the active mode's TSV file |
| Edit | Button | Inline edit of selected entry (double-click also supported) |
| Remove | Button | Remove selected entry(s) with multi-select support |
| Activate/Deactivate | Button | Toggle Active state of selected entries; label updates dynamically |

**Mode: Glossary** (reads/writes `user/globalglossary.tsv`):
- Columns: Active, Original, Translation, Notes
- 4-column TSV file (TASK 76: added Active column, defaults "True")
- Single-click toggles Active state; changes saved immediately

**Mode: Code Database** (reads/writes `user/codedatabase.tsv`):
- Columns: Active, Pattern, Type, Action, Notes (subset of 10-column TSV)
- 10-column TSV file (TASK 76: added Active as 10th column, defaults "True")
- Single-click toggles Active state; changes saved immediately

**Mixed-Selection Failsafe**:
- When selected entries have mixed Active states, clicking Activate/Deactivate shows a popup
- Popup offers: "Activate All", "Deactivate All", or "Cancel"
- Prevents accidental bulk state changes on heterogeneous selections

**Enabled/Disabled Behavior**:
- When Enabled: Global glossary entries with `active=True` are included in translation prompts
- When Disabled: No global glossary entries are included (project glossary still used)
- State persisted via `ManifestManager.set_use_global_glossary(bool)`

**File Locations**:
- Global Glossary: `user/globalglossary.tsv` (4 columns: Original, Translation, Notes, Active)
- Global Code Database: `user/codedatabase.tsv` (10 columns: Pattern, Type, RegEx, Notes, Visible, IsInvisible, IsCouple, IsNumber, IsWord, Active)

---

#### Glossary Widget (formerly Character Notes) — Right Column

**Purpose**: Track characters for consistent translation. Analysis speaker actions write to this store.

**Layout**: Right column, grid row 0. Collapsible via Collapse/Display toggle button. Treeview height=8 with sticky="nsew" for vertical expansion.

| Component | Type | Function |
|-----------|------|----------|
| Character Table | Treeview | Columns: Original, Translation, Notes. Default sort: count descending (highest first). Clickable column headers cycle ascending → descending → reset to count. Active sort column shows ▲/▼ arrow. |
| Context Menu | Right-click | Clear Notes, Edit..., Remove |
| Add Character | Button | Add new character entry |
| Edit | Button | Edit selected character via CharacterDialog (Notes field) |
| Remove | Button | Remove selected character(s) |
| Infer Gender | Button | Batch gender inference using `infer_genders_batch()`; both script and LLM passes run in background threads with Cancel button visible from the start |
| Import from Analysis | Button | Import detected speakers using `_get_analysis_step_data()` helper |

**Table Sorting**: Characters display sorted by internal `count` field (highest first) by default. Clicking any column header sorts alphabetically A→Z; clicking the same header again reverses to Z→A; a third click resets to the default count-based order. Sort state tracked via `_char_sort_col`, `_char_sort_reverse`, `_char_sort_clicks`. Row-to-data mapping uses `char_{idx}` tags (via `_get_char_idx()`) so display order is independent of `_metadata.characters` list order.

**Prompt Format**: Character entries included as context:
```
Characters:
- [Original] ([Translation]): [Notes]
```

**Manifest Key**: `characters[]` (via `save_character_notes()` / `load_character_notes()`). Saved in count-descending order for consistent manifest ordering.

**Dual-Storage Sync (Bug Fix):** Characters exist in two manifest locations: the authoritative top-level `characters` key (written by `save_character_notes()` in Analysis step's Term Translation and by `_save_characters_to_manifest()` in Information step) and the nested `step_state.Information.data.metadata.characters` (written by `on_leave()` via `set_step_data()`). To prevent stale step_state from overwriting translations:
1. `on_enter()` loads from step_state first (`_load_metadata()`), then overrides with top-level manifest data (`_load_characters_from_manifest()`) — authoritative source always wins
2. `on_leave()` saves to both step_state and top-level (`_save_characters_to_manifest()`) to keep storage locations in sync
3. `_import_analysis_speakers()` persists auto-imported entries to top-level immediately via `_save_characters_to_manifest()`

Tests: `dev/test_glossary_term_link.py` (19 tests)

---

#### Right Column Layout & Collapsible Widgets

**Purpose**: All table-based widgets (Glossary, Code Database, Knowledge Base) are in the right column with collapsible behavior and taller tables that fill available vertical space.

**Grid Layout** (right column):
| Row | Widget | Default State |
|-----|--------|---------------|
| 0 | Glossary (Characters) | Expanded |
| 1 | Code Database | Expanded |
| 2 | Knowledge Base | Expanded |

**Collapsible Behavior**:
- Each widget uses `_build_collapsible_labelframe()` helper which creates a header row (▾/▸ toggle button + bold label + optional extra widgets + horizontal `ttk.Separator`) and a collapsible body Frame
- Collapse hides body via `grid_remove()`, Display restores via `grid()`
- Button text toggles between "▾" (expanded) and "▸" (collapsed)
- State tracked in `_collapsible_state` dict (bool per widget name)
- `_reconfigure_right_column_weights()` sets row weight=1 for expanded, weight=0 for collapsed
- Collapsed widgets show only their header bar (title + separator), not an empty bordered frame
- Expanded widgets share available vertical space evenly

**Taller Tables**:
- All Treeview widgets use height=8 (previously 4-5)
- Tables use `grid` layout with `sticky="nsew"` for both horizontal and vertical expansion
- Parent frames use `rowconfigure(weight=1)` to allow table growth
- Canvas `<Configure>` binding stretches inner frame to viewport height so tables fill the window when maximized

**Column Sorting** (Glossary + Code Database):
- Both tables default to **count descending** (highest first). Glossary sort key: `(-count, original_name)`. Code Database sort key: `(instances first, -count, pattern)`.
- All column headings are clickable. Click cycle per column: **ascending (A→Z)** → **descending (Z→A)** → **reset to count**. Active sort column shows ▲ (ascending) or ▼ (descending) in heading text.
- Sort state per tree: `_char_sort_col` / `_code_sort_col` (column name or `None`), `_char_sort_reverse` / `_code_sort_reverse`, `_char_sort_clicks` / `_code_sort_clicks`.
- Clicking a different column resets to ascending on that column.
- Glossary uses `char_{idx}` tags for row-to-data mapping; Code Database already uses `pat_{idx}` tags. Both are independent of list order in `_metadata`.
- **Manifest save order**: Both `_save_characters_to_manifest()` and `_save_code_patterns_to_manifest()` sort by count descending before serialization.

---

#### Data Flow

**Inputs**:
- User: Manual entry of all fields
- From Step 1: Detected speakers (populate Characters), detected code patterns (populate Code Database)
- From Global: `user/globalglossary.tsv`, `user/codedatabase.tsv`

**Processing**:
1. Validate field formats on change
2. Build prompt components from each field
3. Auto-save to manifest on field change (via manifest binding)
4. Selective glossary: Filter entries based on chunk content

**Outputs** (to Step 5 Translation):
- `prompt_components{}` - All prompt fragments by category
- `selective_glossary[]` - Glossary entries matching current chunk
- `code_patterns[]` - Patterns with their actions

**Stored In**:
- Manifest: `step_state.Information.data.metadata{}` (source_language, target_language, genre, style, tone, summary, custom_notes, characters, code_patterns, system_instructions, si_preset, io_examples)
- Toggle flags: `step_state.Information.data.metadata{}` (`genre_enabled`, `summary_enabled`, `style_enabled`, `tone_enabled`, `system_instructions_enabled`, `glossary_enabled`, `code_database_enabled`) — written by `_toggle_section_enabled()` via `set_info_metadata_field()`, preserved by `on_leave()` merging BooleanVar values into the metadata dict after `ProjectMetadata.to_dict()`
- Toggle visual state: When disabled, ScrolledText widgets (Summary, Style, Tone, System Instructions) are greyed out with `THEME.bg_disabled` background and `THEME.text_disabled` foreground via `_apply_widget_enabled_state()`. Spinboxes and combos use native `state="disabled"`. When enabled, background/foreground are restored to white/black.
- I/O Examples setting: `metadata.io_examples` — controls example generation mode (`disabled`|`fill`|`1500`|`2500`); stored in manifest, NOT in INI
- Step data: `Information.{fields...}`

---

#### User Actions

| Action | Effect |
|--------|--------|
| Edit any field | Auto-saves to manifest, rebuilds prompt component |
| Click Genre `...` | Opens multi-select genre dialog |
| Select "Other" language | Prompts for custom language input |
| Fill Custom Style/Tone | Grays out preset dropdown, uses custom in prompt |
| Clear Custom Style/Tone | Activates preset dropdown |
| Double-click table cell | Enables inline editing |
| Import from Analysis | Populates Characters or Code Database from Analysis findings |
| Toggle Use Global Glossary | Includes/excludes global entries during translation |
| Click ▾ (right column) | Collapses widget content, button changes to "▸", collapsed row weight=0 |
| Click ▸ (right column) | Expands widget content, button changes to "▾", expanded row weight=1 |

---

#### Known Issues to Fix

1. **Genre Dialog Overwrites**: Currently replaces field content instead of appending
2. ~~**Import from Analysis (Code)**: Button not functional - needs implementation~~ — FIXED: uses `_get_analysis_step_data()` (ManifestManager first, session fallback)
3. ~~**Import from Analysis (Glossary)**: Button not functional - needs implementation~~ — FIXED: uses `_get_analysis_step_data()` (ManifestManager first, session fallback)
4. **"Other" Language**: Does not prompt for custom input
5. ~~**Custom Style/Tone Graying**: Visual feedback not implemented~~ — FIXED: Replaced by full preset system (Phase 60); text fields auto-populate from preset via `_ensure_style_tone_text()`
6. ~~**Section Toggle Persistence**: `on_leave()` called `ProjectMetadata.to_dict()` which does not include `*_enabled` flags, then replaced the entire metadata dict via `set_step_data()`, erasing toggle states written by `_toggle_section_enabled()`~~ — FIXED: `on_leave()` and `_save_metadata()` now merge current toggle BooleanVar values into the metadata dict before saving
7. ~~**Preview Request Ignores Toggles**: `_build_preview_requests()` built labeled sections for all fields regardless of `*_enabled` flags, making disabled sections appear in Preview Request~~ — FIXED: `_build_preview_requests()` now reads enabled flags from metadata and gates sys_instructions, style, tone, summary, genre, glossary, and character sections
8. ~~**Redundant Save Button**: Header contained a Save button that duplicated the auto-save on tab change behavior and showed a misleading confirmation messagebox~~ — FIXED: Save button removed from header; `_save_metadata()` retained as internal helper without messagebox

---

### Step 3: Preprocessing

**Implementation Status:** ✅ Phase 42 DONE — All 12 tasks implemented (80 tests passing, 4679 total suite); TASK 72 optimizations added (tags, pagination, skip unchanged)

**Purpose**: Process text before translation with transformations that will be exactly mirrored and restored in Step 7: Postprocessing. Each process has a priority integer determining execution order. Preprocessing reduces tokens, protects code, and normalizes text while ensuring perfect reversibility.

**Design Goals**:
1. **Mirror Symmetry**: Every Preprocessing transformation has a corresponding Postprocessing restoration
2. **Priority Ordering**: Processes execute in defined order; each `modi/` module has a priority integer
3. **Perfect Reversibility**: All changes must be recoverable to produce accurate final output
4. **Token Efficiency**: Reduce tokens sent to LLM to minimize costs
5. **Code Protection**: Ensure code and placeholders survive translation unchanged
6. **Big Project Efficiency** (TASK 72): Per-line tags for O(1) filter, skip unchanged writes, progress feedback

---

#### Widgets Overview

The Preprocessing tab is organized into three sections:

1. **Standard Rules Panel** - Toggleable checkboxes for common transformations
2. **Pattern Configuration Widgets** - Custom Placeholders, Protect Code Patterns, Anchoring
3. **Preview Widget** - Table view of all lines showing processes applied

---

#### Widget: Standard Rules Panel

**Purpose**: Toggle common preprocessing transformations. All standard rules have Postprocessing counterparts.

| Widget | Type | Default | Function |
|--------|------|---------|----------|
| Deduplication | Checkbox + Spinbox | ✓, Threshold=1 | Replace duplicate lines with tokens |
| Ellipsis Compression | Checkbox | ✓ | Compress ellipsis sequences to save tokens |
| Symbol Conversion | Checkbox | ✓ | Convert JP→EN punctuation before translation |
| Width Conversion | Checkbox | ✓ | Convert fullwidth↔halfwidth characters based on language pair |
| PROTECTED Token Compression | Checkbox | ✓ | Compress adjacent `__PROTECTED__` tokens |
| Speaker Name Replacement | Checkbox | ✗ | Replace speaker names with glossary translations |
| Code Spacing Rules | Checkbox | ✓ | Apply code-aware spacing normalization |
| Quote Stripping | Checkbox | ✗ | Strip quotes at dialogue boundaries to save tokens |
| Aggressive Deduplication | Checkbox | ✗ | Variant-aware deduplication (code→{CODE}, numbers→X) |

**Buttons**:
| Button | Function |
|--------|----------|
| Apply Rules | Execute all enabled preprocessing rules |
| Reset | Clear all preprocessing results and restore original |
| Auto-Suggest | Analyze content and suggest optimal rule settings |

---

#### Process: Deduplication

**Priority**: 10 (First - runs before all other processes; restored last in Postprocessing)

**Purpose**: Temporarily replace duplicate lines to avoid translating the same content multiple times. Restores duplicates to the translation of the unique remaining line.

**Current Behavior**:
- Exact string matching for duplicate detection
- Applies before any other preprocessing
- Configurable threshold: Minimum X occurrences for a line to be deduplicated
- Successive mode: Require X or more identical consecutive lines

**Deduplication Settings**:
| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| Enabled | Boolean | true | Enable deduplication |
| Threshold | Integer (1-10) | 1 | Minimum occurrences to deduplicate |
| Mode | Enum | "Global" | "Global" (anywhere) or "Successive" (consecutive only) |

**Token Format**: `__DEDUP_{idx}__` where `idx` is the index of the first occurrence

**Postprocessing**: All deduplicated lines receive the translation of their unique original

**Manifest Keys**: `Deduplication`, `DeduplicationThreshold`, `DeduplicationMode`

---

#### Process: Ellipsis Compression

**Priority**: 20

**Purpose**: Compress multiple ellipsis characters to a standard form to save tokens and prevent LLM from altering ellipsis length.

**Behavior**:
- Japanese ellipsis `……` (or longer): Compress to `……`
- Western ellipsis `....` (4+ dots): Compress to `...`
- Single ellipsis character `…`: Preserved as-is
- Records original length for restoration

**Postprocessing**: Expand back to original length

**Manifest Key**: `EllipsisCompression`

---

#### Process: Symbol Conversion

**Priority**: 30

**Purpose**: Convert Japanese punctuation to Western equivalents before translation, allowing the LLM to work with familiar characters.

**Conversion Table**:
| Japanese | Western |
|----------|---------|
| `。` | `.` |
| `、` | `,` |
| `！` | `!` |
| `？` | `?` |
| `：` | `:` |
| `；` | `;` |
| `（）` | `()` |
| `「」` | `""` |
| `『』` | `""` |
| Fullwidth `０-９Ａ-Ｚａ-ｚ` | Halfwidth `0-9A-Za-z` |

**Postprocessing**: May optionally convert back based on target language settings

**Manifest Key**: `SymbolConversion`

---

#### Process: PROTECTED Token Compression

**Priority**: 60 (Runs AFTER Protect Code Patterns creates `__PROTECTED__` tokens)

**Purpose**: Compress adjacent `__PROTECTED__` tokens into a single numbered token to reduce token count.

**Behavior**:
- `__PROTECTED____PROTECTED__` → `__PROTECTED_2__`
- `__PROTECTED____PROTECTED____PROTECTED__` → `__PROTECTED_3__`
- Only compresses tokens that are directly adjacent (no whitespace between)
- Records compression mapping for restoration

**Postprocessing**: Decompress `__PROTECTED_N__` back to N individual `__PROTECTED__` tokens BEFORE replacing with originals

**Manifest Key**: `ProtCompression`

---

#### Process: Speaker Name Replacement

**Priority**: 40

**Purpose**: Replace original speaker names in `Speaker: "Dialogue"` format with their translated equivalents from the Glossary.

**Behavior**:
- Matches speaker names against Glossary entries
- If match found, replaces Original with Translation
- Only affects the speaker portion, not the dialogue
- Example: `太郎: "こんにちは"` → `Taro: "こんにちは"` (if glossary has 太郎→Taro)

**Future Improvement**: This feature needs rework to handle edge cases (speakers with colons in name, multiple formats, etc.)

**Manifest Key**: `SpeakerNameReplacement`

---

#### Process: Code Spacing Rules

**Priority**: 50

**Purpose**: Apply intelligent spacing around code elements to prevent spacing issues after translation.

**Behavior**:
- Reads spacing rules from Code Database
- Each code pattern can specify:
  - `visible`: Whether the code renders visibly (affects spacing decisions)
  - `spacing`: How to handle spaces around code (`none`, `preserve`, `normalize`)
- Invisible codes (like color codes) should have no surrounding spaces added
- Variable codes (like `\V[1]`) should preserve existing spacing

**Code Database Integration**: Spacing rules are defined per-pattern in the Code Database (Step 3)

**Future Improvement**: Needs deeper integration with Code Database and expanded rule definitions

**Manifest Key**: `CodeSpacingRules`

---

#### Process: Width Conversion

**Priority**: 35 (After Symbol Conversion, before Speaker Name Replacement)

**Purpose**: Convert character width from source language width to target language width. Most languages use halfwidth characters; East Asian languages (Chinese/Japanese/Korean) use fullwidth.

**Behavior**:
- Converts fullwidth alphanumerics to halfwidth (or vice versa) depending on source→target language direction
- Runs after Symbol Conversion and before Anchoring to ensure anchor equivalents are available
- **Preprocessing only** — no postprocessing reversal needed. The target language width is the desired output width.

**Manifest Key**: `WidthConversion`

---

#### Process: Quote Stripping

**Priority**: 76 (After Anchoring)

**Purpose**: Remove quotes at line/dialogue start and line end to save tokens during translation.

**Behavior**:
- Strips opening and closing quotes from dialogue boundaries
- Records original quote characters and positions for restoration
- Distinct from Quote Balance (which is post-exclusive and fixes LLM-introduced mismatches)

**Postprocessing**: Restored before Anchoring restoration (Priority 9 in Post)

**Manifest Key**: `QuoteStripping`

---

#### Process: Aggressive Deduplication

**Priority**: 90 (Runs last — after all other preprocessing)

**Purpose**: Deduplicate variations of lines that differ only in code or numbers, beyond what standard Deduplication handles.

**Behavior**:
- Replaces all code patterns with a generic `{CODE}` and all numbers with `X`
- Lines that are identical after these substitutions are treated as duplicates
- Runs last in preprocessing because it operates on the fully preprocessed form of each line
- Uses the postprocessed result of the unique original to restore all variant-deduplicated lines

**Postprocessing**: Restored first (Priority 5 in Post), before any other restoration, to ensure the deduplicated variants receive the correct restored translation

**Manifest Key**: `AggressiveDeduplication`

---

#### Widget: Custom Placeholders

**Purpose**: Define custom pattern-to-placeholder mappings for specific strings, primarily for name variables or recurring terms.

**UI Components**:
| Component | Type | Function |
|-----------|------|----------|
| Pattern Table | Treeview | Columns: Pattern, Placeholder, RegEx, Description |
| Add Button | Button | Opens Add dialog |
| Edit Button | Button | Opens Edit dialog for selected row |
| Remove Button | Button | Removes selected rows |
| RegEx Tickbox (in dialog) | Checkbox | Toggle regex interpretation (default: disabled) |

**Priority**: 70 (After standard rules, before Protect Code Patterns)

**Behavior**:
- Replaces Pattern with the configured placeholder token (for example a visible replacement name such as `Jane`)
- If RegEx enabled: Pattern interpreted as regular expression
- If RegEx disabled: Pattern is literal string match
- Stores original text for restoration, including token-aware per-line records so postprocessing can restore the token even if the translated output moved it to another line

**Postprocessing Priority**: 30 (Restored AFTER Anchoring, BEFORE standard restoration)

**Use Cases**:
- Name variables: `{PLAYER_NAME}` → `__CUSTOM_1__`
- Recurring terms that should not be translated
- Company/product names that need consistent handling

**Manifest Key**: `CustomPlaceholders` (list of `{pattern, placeholder, is_regex, description}`)

---

#### Widget: Protect Code Patterns

**Purpose**: Define patterns that should be protected with standard `__PROTECTED__` tokens.

**UI Components**:
| Component | Type | Function |
|-----------|------|----------|
| Pattern Table | Treeview | Columns: Pattern, Replacement, RegEx, Description |
| Add Button | Button | Opens Add dialog |
| Edit Button | Button | Opens Edit dialog for selected row |
| Remove Button | Button | Removes selected rows |
| RegEx Tickbox (in dialog) | Checkbox | Toggle regex interpretation (default: enabled) |

**Priority**: 80 (After Custom Placeholders)

**Behavior**:
- Replaces matched patterns with `__PROTECTED__` token
- Default: RegEx enabled (patterns are regular expressions)
- If RegEx disabled: Pattern is literal string match
- Each match gets same `__PROTECTED__` token (compression handles duplicates)
- Original text stored in `prepro_ops[]` for restoration

**Postprocessing Priority**: 20 (Restored after PROTECTED decompression)

**Validation (QA Step)**:
- Checks that all `__PROTECTED__` tokens exist in translation
- Flags missing/extra tokens for manual review
- Attempts recovery if tokens are mangled

**Manifest Key**: `ProtectCodePatterns` (list of `{pattern, replacement, is_regex, description}`)

---

#### Widget: Anchoring (rename from Anchor Removal)

**Purpose**: Remove patterns from translation entirely and restore them at exact positions afterward using anchor points.

**UI Components**:
| Component | Type | Function |
|-----------|------|----------|
| Pattern Table | Treeview | Columns: Pattern, Action, Anchor Spec, RegEx, Description |
| Add Button | Button | Opens Add dialog |
| Edit Button | Button | Opens Edit dialog for selected row |
| Remove Button | Button | Removes selected rows |
| RegEx Tickbox (in dialog) | Checkbox | Toggle regex interpretation (default: enabled) |

**Note**: Widget renamed from "Anchor Removal" to "Anchoring" for clarity. No single writable field or preset selection buttons - full table-based management with Add/Edit/Remove dialogs.

**Priority**: 75 (After Custom Placeholders, Before Protect Code Patterns)

**Behavior**:
- Removes matched pattern ONLY when adjacent to a valid anchor character (punctuation, bracket, quote) or at line start/end
- Patterns surrounded by normal text on both sides are left in place (not removed)
- Stores anchor-relative removal data: anchor character, side (left/right of anchor), and anchor type (char/line_start/line_end)
- Does NOT use absolute character positions or proportional positioning
- Does NOT leave any placeholder token in text
- Anchor characters: Line start, Line end, Punctuation `.!?;:,`, Brackets `()[]<>{}「」『』【】〔〕《》〈〉（）`, Quotes `"'""''`
- During restoration, finds anchor character (or its symbol-conversion equivalent) via `rfind`, processing records from right to left

**Postprocessing Priority**: 10 (Restored FIRST, before other restorations)

**Anchor Types**:
| Anchor | Description |
|--------|-------------|
| `^` | Start of line |
| `$` | End of line |
| `.!?` | After punctuation |
| `[...]` | Before/after square brackets |
| `<...>` | Before/after angle brackets |
| `{...}` | Before/after curly brackets |

**Validation (QA Step)**:
- Verifies anchor points still exist in translation
- Flags lines where anchors are missing
- Attempts recovery using fuzzy matching
- Does NOT apply restoration in QA - only flags for review

**Manifest Key**: `AnchorRemoval` (list of `{pattern, action, anchor_spec, is_regex, description}`)

---

#### Widget: Preview Table

**Purpose**: Display all lines with preprocessing changes applied, allowing filtering and review.

**Columns**:
| Column | Content |
|--------|---------|
| # | Line index |
| Original | Original text before preprocessing |
| Preprocessed | Text after all preprocessing applied |
| Changes | Comma-separated list of processes applied to this line |
| Status | Processing status (unchanged, modified, deduplicated, error) |

**Filters**:
| Filter | Shows |
|--------|-------|
| All | All lines |
| Changed | Only lines with modifications |
| Deduplicated | Only lines that were deduplicated |
| Protected | Only lines with `__PROTECTED__` tokens |
| Anchored | Only lines with anchor removals |
| Errors | Only lines with processing errors |

**Behavior**:
- Updates in real-time as rules are toggled
- Selecting a line shows detailed breakdown of changes
- Double-click opens line editor for manual override

---

#### Process Execution Order

**Preprocessing** (lowest priority runs first):
| Priority | Process | Description |
|----------|---------|-------------|
| 10 | Deduplication | Remove duplicates before any changes |
| 20 | Ellipsis Compression | Normalize ellipsis |
| 30 | Symbol Conversion | Convert JP→EN symbols |
| 35 | Width Conversion | Convert fullwidth↔halfwidth characters (Pre only) |
| 40 | Speaker Name Replacement | Replace speaker names |
| 50 | Code Spacing Rules | Normalize code spacing |
| 60 | PROTECTED Token Compression | Compress adjacent PROTs (runs after patterns create them) |
| 70 | Custom Placeholders | Apply user-defined patterns |
| 75 | Anchoring | Remove anchored content |
| 76 | Quote Stripping | Strip quotes at dialogue/line boundaries to save tokens |
| 80 | Protect Code Patterns | Protect remaining code |
| 90 | Aggressive Deduplication | Variant-aware dedup with generic substitutions (runs last) |

**Postprocessing** (reverse order - highest priority runs first):
| Priority | Process | Description |
|----------|---------|-------------|
| 5 | Aggressive Deduplication | Restore variant-deduplicated lines FIRST |
| 9 | Quote Stripping | Restore stripped quotes before anchoring restoration |
| 10 | Anchoring | Restore anchored content |
| 20 | Protect Code Patterns | Restore `__PROTECTED__` tokens |
| 30 | Custom Placeholders | Restore custom tokens |
| 40 | PROTECTED Token Decompression | Decompress `__PROTECTED_N__` |
| 50 | Code Spacing Rules | Restore code spacing |
| 60 | Speaker Name Replacement | (No restoration needed) |
| 70 | Symbol Conversion | Optionally restore JP symbols |
| 80 | Ellipsis Expansion | Restore ellipsis length |
| 90 | Deduplication | Apply translation to all duplicates LAST |
| 100 | Quote Balance Recovery | Fix unmatched quotes (Post-exclusive) |
| 110 | Bracket Balance Recovery | Fix unmatched brackets (Post-exclusive) |
| 120 | Whitespace Normalization | Match indentation/spacing to original (Post-exclusive) |
| 130 | Code Spacing Rules (Post) | Specialized whitespace for code patterns (Post-exclusive) |

**Full reference**: See §5.9 Pre/Post Processing Priority System for the complete cross-step priority table.

---

#### Data Flow

**Inputs**:
- From Step 0: manifest `lines[].orig` - Original lines from loaded files
- From Step 3: `code_patterns[]` - Code patterns for protection rules
- From Step 3: `glossary[]` - For Speaker Name Replacement
- From Manifest: Standard rule toggles, pattern lists

**Processing** (via `gui/helpers/mode_adapter.py` → `modi/` modules):
1. Each `modi/` module has a `priority` attribute
2. Modules sorted by priority (ascending for preprocessing)
3. Each module processes all lines and returns modifications
4. Modifications stored in `prepro_ops[]` per line
5. Final preprocessed text stored in `prepro[]`

**Outputs**:
- `prepro: List[str]` - Preprocessed lines ready for translation
- `prepro_ops: List[List[Dict]]` - Restoration metadata per line, per process
- `dedup_map: Dict[str, List[int]]` - (Legacy) Line text → duplicate indices; new dedup stores tags on `lines[].tags` ("dedup,D{source_idx}") for top MAX_DEDUP_GROUPS (10) groups
- `change_count: int` - Total lines modified
- `protected_count: int` - Lines with `__PROTECTED__` tokens
- `anchored_count: int` - Lines with anchor removals

**Stored In**:
- Manifest: `lines[].prepro`, `lines[].prepro_ops`
- Manifest step data: All toggle states and pattern lists

---

#### User Actions

| Action | Effect |
|--------|--------|
| Toggle Standard Rule | Updates Preview immediately (if auto-refresh enabled) |
| Click Apply Rules | Executes all enabled preprocessing |
| Click Reset | Clears preprocessing, reverts to original |
| Click Auto-Suggest | Analyzes content and recommends rule settings |
| Add/Edit/Remove Pattern | Updates pattern list, requires re-processing |
| Filter Preview Table | Shows subset of lines matching filter |
| Double-click Preview Row | Opens manual line editor |

---

#### Validation and Recovery

**QA Step Checks** (Step 6):
- All `__PROTECTED__` tokens present in translation
- All `__CUSTOM__` tokens present in translation
- Anchor points exist for restoration
- No extra/duplicate tokens introduced
- Speaker format preserved

**Recovery Strategies** (applied in Postprocessing):
1. **Exact Match**: Token found at expected position
2. **Case Recovery**: `__PROTECTED__` → `__PROTECTED__` (fix and proceed)
3. **Mangled Recovery**: `__PRO T__` or `__PROTECTED _` (pattern match and fix)
4. **Position Shift**: Token present but at different position (adjust and restore)
5. **Missing Token**: Token not found (flag for manual review, attempt fuzzy match)
6. **Extra Token**: More tokens than expected (flag, may indicate duplicate insertion)

**Retry Strategies** (if recovery fails):
1. **Skip**: Leave line unprocessed, flag for manual fix
2. **Retry Translation**: Re-translate the specific line with different prompt
3. **Isolated Retry**: Re-translate line individually with strict instructions

---

#### Testing Requirements

**Required Test Coverage**:
- Each preprocessing process individually
- Process combinations (all enabled, specific combos)
- Boundary cases (empty lines, lines with only code, etc.)
- Large file handling (100K+ lines performance)
- Roundtrip accuracy (prepro → translate → postpro must match expected)
- Pattern edge cases (overlapping patterns, nested code, etc.)
- Recovery mechanisms (each recovery type)

**Test Files** (to be created/extended):
- `dev/test_preprocessing_dedup.py`
- `dev/test_preprocessing_ellipsis.py`
- `dev/test_preprocessing_symbols.py`
- `dev/test_preprocessing_prot.py`
- `dev/test_preprocessing_placeholders.py`
- `dev/test_preprocessing_anchoring.py`
- `dev/test_preprocessing_integration.py`
- `dev/test_preprocessing_postprocessing_roundtrip.py`

---

### Step 5: Translation

**Purpose**: Execute LLM translation of preprocessed text. The Translation step is the core of the pipeline — it sends text to a configured LLM (or a Mock Translation fallback) and collects translated output line-by-line. Performance, caching, and retry resilience are critical.

**Performance Requirement**: The tab MUST load in under 1 second for 100K lines. Current implementation freezes the application for tens of seconds with several tens of thousands of lines. All tabs must implement a cache strategy: if no changes to project settings or lines have occurred since the last visit, the cached state loads instantly without reprocessing. This cache invalidates when lines, preprocessing results, or relevant settings change.

---

#### Widgets Overview

The Translation tab contains four widget sections:

1. **Translatable Lines Widget** - Table showing all lines with status and translation
2. **Request Options Widget** - Model, temperature, chunking, retry settings
3. **Preview Requests Widget** - Preview Requests button opens RequestPreviewDialog showing actual API requests with Pure/Formatted/Plain views, Jump/Search/Filter toolbar; Ban Tokens separated
4. **API Usage Widget** - Live token usage, cost estimate, rate limit display

---

#### Widget: Translatable Lines

**Purpose**: Display all lines with their translation status and content.

**Columns**:
| Column | Content |
|--------|---------|
| # | Line index (1-based) |
| Status | Translation status icon + text |
| To be Translated | Merged column: shows Preprocessed text if available, otherwise Original |
| Translated | LLM-produced translation |

**Change from Current**: The "Original" and "Preprocessed" columns are **merged** into a single "To be Translated" column. Priority: Preprocessed → Original. This reduces clutter and shows exactly what the LLM will receive.

**Features**:
- Filter dropdown with column-specific filtering (status, content search)
- Buttons: Clear filter, column visibility dropdown to hide/show columns
- **Newline support**: Multi-line content renders with visible line breaks (same approach as Step 0 Input)
- Status icons: ○ Pending, ◐ Translating, ✓ Done, ✗ Failed, ⊘ Skipped
- Double-click a row to view full line content in a popup

**Performance**:
- Table uses virtual/lazy rendering — only visible rows are populated
- Initial load must complete in < 1 second for 100K lines
- Scrolling must remain smooth at all data sizes
- Data is loaded from manifest line entries, not recomputed

**Manifest Key**: Lines read from `lines[].prepro` (preferred) or `lines[].orig`; translations written to `lines[].tl`

---

#### Widget: Request Options

**Purpose**: Configure per-project translation request parameters.

| Widget | Type | Default | Function |
|--------|------|---------|----------|
| Key | Dropdown | (first saved key) | Select API key from saved keys in API.ini |
| Model | Dropdown | (default for key) | Select LLM model, filtered by selected key's provider |
| Request Mode | Combobox | Normal | Normal / Batch / Flex / Priority. Unavailable modes have "(Unavailable)" suffix. Selection stored in TranslationOptions.request_mode, passed to APIConfig.request_mode. |
| Model Settings | Label + Button | — | Opens Global Options at Model Settings section; reuses the existing Global Options dialog if already open |
| Translation Options | Label + Button | — | Opens Global Options at Translation Options section; reuses the existing Global Options dialog if already open |
| Lines/Chunk | Spinbox | 30 | Lines per API request (5-200). Must sync with Estimation step |
| Retry Strategy | Dropdown | Batch | How failures are retried (Batch, Contextual) |
| Max Retries | Spinbox | 3 | Round trips of retries (0 = none) |
| Skip Non-Source Language | Checkbox | ✗ | Skip lines not detected as source language |
| Skip Already Translated | Checkbox | ✗ | Skip lines that already have a translation |
| Ban Tokens | Preset + Entry | — | Configure banned output tokens |

**Model Selection**:
- Models are **not** a hardcoded list. They come from Global Options where the user configures API Providers (Name, URL, Key, Model).
- Without any configured providers, the only available option is **"Mock Translation"**.
- Mock Translation: Initially produces nonsense output (using a script to replace words with others from a limited list randomly, languages like Japanese have custom settings). Future improvement: use NMT (Neural Machine Translation) engine for basic translation.
- The dropdown displays the provider Name field from Global Options.

**Lines/Chunk Sync with Estimation**:
- Lines/Chunk must have parity with the Estimation step (Step 4: Costs).
- Changing Lines/Chunk in Translation updates the value in Estimation and vice versa.
- When Lines/Chunk changes, the user is prompted: "Chunk size changed. Re-run estimation?" with Yes/No.
- Both steps read/write the same manifest key: `RequestOptions.LinesPerChunk`.

**Retry Strategy Details**:

| Strategy | Behavior | Prompt Modification | Rolling Context |
|----------|----------|---------------------|-----------------|
| Batch | Retry failed lines together | Adds instruction: "These lines are unrelated; translate each independently" | Disabled (no rolling context) |
| Contextual | Retry failed lines with surrounding context | Uses different rolling context: lines before AND after the failed segment | Enabled (before + after context) |

**Note**: "Isolated" and "Skip" strategies exist in code but are **hidden** from the UI for now. They will be exposed once further refined. Retries are done after the first round of translation.

**Skip Non-Source Language**:
- NEW option. Uses language detection (`functions/analysis.py`) to identify lines not in the configured source language.
- Lines detected as already in the target language or a third language are marked as Skipped.
- Reduces unnecessary API calls and costs.
- For Japanese / Chinese / Korean projects, placeholder tokens are stripped before detection and any remaining CJK/Hangul content keeps the line eligible; Latin-only remainder is skipped as non-CJK.

**Skip Already Translated**:
- NEW option. When enabled, lines that already have a non-empty `tl` field in the manifest are skipped during translation.
- Useful for **incremental translation**: when new lines are added to a project (e.g., game patch), only untranslated lines are sent to the LLM.
- Also useful after **Import Translations** (Step 0): imported lines already have translations and don't need re-translation.
- Request Preview and Start Translation must both re-evaluate the full loaded line set against this option. When overwrite is enabled, already translated lines re-enter the translatable set immediately; when overwrite is disabled, they count toward the policy-skipped summary.
- Skipped lines are marked as "Skipped (already translated)" in the status column.
- This does NOT skip lines that have `edit{N}` or `tlc{N}` — it only checks the base `tl` field.
- Can be combined with Skip Non-Source Language for maximum efficiency.
- Manifest Key: `RequestOptions.SkipAlreadyTranslated`

**Moved to Global Options**:
- **Enable Request Caching**: Moved from Translation to Global Options. Becomes a dropdown with cache modes. Default mode: "Line" — every individual line with its translation is cached. Cache is applied both during translation (skip already-cached lines) and after (populate cache from results). Other modes (strict, model_only, any) to be implemented later.
- **Extended Thinking**: Moved from Translation to Global Options. Renamed from "Extended Thinking (Claude)" to "Thinking Mode" — it is NOT Claude-exclusive. Implementation must support toggling thinking on/off for any model that supports it (OpenAI reasoning models, Claude, etc.). Default: off. Includes Thinking Budget spinbox (1000-100000 tokens).
- **Rolling Context (Context Lines)**: Moved to Global Options. Determines how many preceding lines are included as context in each request. Range: 0-10. Default: 3. Used by both normal translation and Contextual retry strategy.

**Hidden (Future Improvement)**:
- **Edit Before Translation**: Currently a checkbox; must become a Button that opens a dialog window. The dialog runs a modified system where the LLM is prompted to only fix specific mistakes in the original text (not translate). Hidden from UI until further design.
- **Line-by-Line Mode**: Translates each line individually instead of in chunks. Hidden for now. When exposed, Context Lines (Rolling Context) will control its context window.
- **Translation / Edit / TLC Mode Toggle**: A three-way toggle (Translation, Edit, TLC) that changes the behaviour of the Translation step. Translation mode is the default and current implementation. Edit mode uses a different prompt and request-building script: the LLM is instructed to fix the translated text (grammar, naturalness, formatting) without re-translating. TLC (Translation Check) mode sends the original alongside the translation and asks the LLM to verify accuracy, flagging or correcting mistranslations. Key design question to resolve through testing: line matching strategy — whether to match via line numbers, full original lines, or empty lines, since not every line will be edited/TLC'd and unnecessary output is the most expensive token category. Each mode writes to its own manifest field (`lines[].edit{N}`, `lines[].tlc{N}`) and increments the round counter. Hidden from UI until prompt design and line-matching strategy are validated.

**Buttons**:
| Button | Function |
|--------|----------|
| ▶ Start Translation | Begin translation of all pending lines |
| ⏸ Pause / ▶ Resume | Toggle pause during translation |
| ⏹ Cancel | Abort translation (preserves completed work) |
| ↻ Refresh Lines | Reload lines from previous steps |

---

#### Widget: Preview Requests

**Purpose**: Preview the actual API requests that would be sent during translation. The Preview Requests button builds requests using the same functions and data as the real translation pipeline — reading from the manifest (Summary, Style, Tone, System Instructions, Glossary, Conditional Prompts) and chunking the lines identically. When OpenAI prompt caching applies, the preview must also expose the effective `prompt_cache_key` / `prompt_cache_retention` so users can confirm the request metadata before sending.

**Implementation**: `_build_preview_requests()` gathers options from UI, re-classifies all loaded lines with the same shared skip rules used by Costs and Start Translation, chunks the resulting translatable lines via `_build_chunks()`, reads manifest data (Prompt, Summary, CustomStyle, CustomTone, POV), loads glossary entries via `load_glossary_entries()`, detects conditional prompts via `build_conditional_instructions()`, computes effective prompt cache request params through the shared API-client helper, and produces a list of `PreviewRequest` dataclass instances — one per chunk. `RequestPreviewDialog` displays them.

**UI Components**:
| Component | Type | Function |
|-----------|------|----------|
| 👁 Preview Requests Button | Button | Opens `RequestPreviewDialog` showing all built requests |
| Ban Tokens Entry | Entry | Comma-separated token ban list (em_dash, smart_quotes, etc.) |
| Ban Tokens Preset Dropdown | Combobox | Quick-select common ban presets |

**RequestPreviewDialog** (opened by button):
- **Toolbar row 1**: Jump To (Spinbox 1–N / total count) · View mode (Combobox: Pure / Formatted / Plain) · Search (Entry with ▲ prev / ▼ next buttons and match count label) · Filter (Menubutton with 9 checkbox items)
- **Text area**: read-only `tk.Text` with vertical + horizontal scrollbars, displays current request
- **Footer**: info label (request index, line count, model, temperature)

**View Modes**:
| Mode | Description |
|------|-------------|
| Pure | Raw JSON exactly as sent to the API (`{"messages": [...], "model": ..., "temperature": ...}`) including request metadata such as `prompt_cache_key` when applicable |
| Formatted | Section headers (═══ META ═══, ═══ SYSTEM INSTRUCTIONS ═══, etc.) with content below each |
| Plain | Stripped of JSON syntax, word-wrapped at 100 characters for readability |

**Filter Parts** (13 toggleable checkboxes via `FILTER_PARTS` constant):
| Key | Label |
|-----|-------|
| meta | Meta |
| language | Language |
| system_instructions | System Instructions |
| io_examples | I/O Examples |
| style | Style |
| tone | Tone |
| summary | Summary |
| genre | Genre |
| pov | Point of View |
| conditional_prompts | Conditional Prompts |
| glossary | Glossary |
| rolling_context | Rolling Context |
| input_lines | Input Lines |

Deselecting a filter hides that section from the Formatted/Plain views and omits it from Pure JSON content field.

**Search**: Case-insensitive text search with yellow highlight (`search_hl` tag) for all matches, orange highlight (`search_current` tag) for the active match. Previous/Next buttons cycle through matches with wrap-around. Match count displayed as "N of M".

**Ban Tokens**:
- Separated into its own clearly labeled section
- Entry field for comma-separated token names
- Dropdown with presets: "None", "Clean English" (em_dash, smart_quotes), "Strict" (em_dash, smart_quotes, ellipsis_variants)
- Applied via logit bias in the API request
- Manifest Key: `RequestOptions.BanTokens`, `RequestOptions.BanTokenPreset`

**Character Whitelist**:
- Comma-separated character ranges allowed in translations (e.g. `a-z,A-Z,0-9`)
- Characters not matching any range are stripped from translation output
- Manifest Key: `RequestOptions.CharacterWhitelist`

**Character Blacklist**:
- Comma-separated characters/ranges removed from translations (e.g. `★,☆,♪`)
- Applied after whitelist filtering
- Manifest Key: `RequestOptions.CharacterBlacklist`

---

#### Widget: API Usage

**Purpose**: Display real-time translation metrics.

| Display | Content |
|---------|---------|
| Tokens Used | Running total of input + output tokens |
| Est. Cost | Running cost estimate based on model pricing |
| Rate Limit | Current request rate vs. configured RPM limit |
| Lines Progress | Translated / Total lines with percentage |
| ETA | Estimated time remaining based on current throughput |

**Progress Window** (non-modal, opens during translation):
- Progress bar with percentage
- ETA and token speed (tok/s)
- Lines translated / remaining / failed counts
- Chunk progress (current chunk / total chunks)
- Pause/Resume/Cancel controls
- API Log button that opens or focuses the shared non-blocking API Log window
- Inline scrollable log pane showing per-chunk status messages

---

#### Mock Translation

**Purpose**: Default translation mode when no API providers are configured. Allows full pipeline testing without API costs.

**Behavior**:
- Available as the only Model option when no providers exist in Global Options
- Produces deterministic nonsense output (word reversal, character substitution from NATO phonetic list)
- Preserves all `__PROTECTED__`, `__DEDUP__`, `__CUSTOM__` tokens in output
- No artificial delay — runs at processing speed (1000 lines < 100 ms)
- Supports cancellation via `threading.Event` — Cancel button stops processing immediately
- Tracks mock token counts for cost estimation testing
- Does NOT require API key or network connectivity

**Future Improvement**: Replace nonsense output with NMT (Neural Machine Translation) engine for basic but meaningful translation.

**Manifest Key**: `RequestOptions.Model` = "mock" when Mock Translation is selected

---

#### Data Flow

**Inputs**:
- From Step 3: `prepro[]` (preprocessed lines) — preferred
- From Step 0: `orig[]` (original lines) — fallback if no preprocessing
- From Step 2 (via manifest `step_state.Information.data.metadata`): Summary, Style, Tone, System Instructions, Genre, Characters, Glossary, Code Database
- From Global Options: API Provider config (URL, Key, Model), Caching mode, Rolling Context, Thinking Mode

**Processing** (via `functions/api_client.py` or Mock Translation):
1. Build translation prompt from Information metadata via `_build_system_prompt_from_manifest()` (follows §5.2 10-slot injection order; context_type passed for §5.2 slot 7b)
2. Determine input: use `get_input_for_translation()` per line (edited_prepro → prepro → orig)
3. Set `source_lang`/`target_lang` on API client config from Information metadata
4. Chunk lines by configured Lines/Chunk size
5. Group chunks into request strings via `_group_chunks_into_strings()`, sort by content type priority (dialogue > choice > mixed/unknown > menu) via `sort_requests_by_type()`
6. **First-request validation gate**: send the first chunk of the first string alone. If a fatal API error occurs (classify via `classify_api_error()` → `TranslationAbortError`), abort immediately before spending tokens on the full batch
7. Execute string groups concurrently via `ThreadPoolExecutor(max_workers=max_concurrent)`:
   - Strings execute in **parallel** across threads
   - Chunks within each string execute **sequentially** (preserving rolling context)
   - Falls back to sequential execution when `max_concurrent ≤ 1`
   - For each chunk:
     a. Check line cache for existing translations (if caching enabled)
     b. Apply rate limiting (from Global Options RPM setting)
     c. Build chunk-specific prompt (include rolling context if enabled)
     d. Send to LLM API with JSON response format (or Mock Translation)
     e. Parse response, map translated lines back to source indices
     f. Classify any API errors via `classify_api_error()` — fatal errors raise `TranslationAbortError` (no retry); retryable errors use exponential backoff
     g. Handle failures per retry strategy (Batch or Contextual)
     h. Update progress display and API Usage widget (thread-safe via `threading.Lock`)
     i. Save translations to manifest after each chunk (crash resilience)
     j. Populate line cache with new translations
   - If any thread raises `TranslationAbortError`, set `_cancel_requested` and drain remaining futures
8. Track token usage and costs
9. On completion: update manifest step data with totals

**Outputs**:
- `tl: List[str]` - Translated lines
- `tokens_used: int` - Actual tokens consumed (input + output)
- `cost_actual: float` - Actual cost incurred based on model pricing
- `failed_lines: List[int]` - Indices that failed all retry attempts
- `skipped_lines: List[int]` - Deduped/empty/wrong-language lines skipped

**Stored In**:
- Manifest: `lines[].tl` (translation result per line)
- Manifest: `lines[].tlc{N}`, `lines[].edit{N}` (TLC and Edit rounds)
- Manifest step data: `Translation.tokens_used`, `Translation.cost_actual`, `Translation.model_used`
- Manifest step data: `Translation.completed_count`, `Translation.failed_count`, `Translation.skipped_count`

---

#### Retry Strategies (Detailed)

| Strategy | When Used | Prompt Modification | Rolling Context | Behavior |
|----------|-----------|---------------------|-----------------|----------|
| Batch | Default | Adds: "These lines are not related to each other. Translate each line independently." | Disabled | Re-sends the entire failed chunk as a single request. Simple and fast but doesn't help with context-dependent failures. |
| Contextual | Context-dependent failures | Uses surrounding lines (before + after failed segment) as additional context | Enabled (bidirectional) | Re-sends only failed lines but includes lines before AND after as rolling context. Better for failures caused by missing context. |
| Isolated | Hidden | Sends one line at a time with strict instructions | Configurable | Retries each failed line individually. Slowest but most reliable for stubborn failures. Hidden until further refinement. |
| Skip | Hidden | N/A | N/A | Marks failed lines as Skipped and moves on. Hidden until further refinement. |

**Max Retries**: Determines how many round trips of retries are made for each strategy. 0 means no retries — failures are immediately marked as Failed. Default: 3.

---

#### API Request Format

Cloud providers (OpenAI, Gemini, Anthropic, Mistral):
```json
{
  "model": "gemini-2.0-flash",
  "messages": [
    {"role": "system", "content": "[Full system prompt from _build_system_prompt_from_manifest() + Output Format]"},
    {"role": "user", "content": "[Lines to translate as numbered JSON]"}
  ],
  "response_format": {"type": "json_object"},
  "temperature": 0.2
}
```

Local providers (LM Studio, Ollama, local):
```json
{
  "model": "qwen/qwen3.5-35b-a3b",
  "messages": [
    {"role": "system", "content": "[Full system prompt from _build_system_prompt_from_manifest() + Output Format]"},
    {"role": "user", "content": "[Lines to translate as numbered JSON]"}
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "translation",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "translations": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["translations"],
        "additionalProperties": false
      }
    }
  },
  "temperature": 0.3
}
```

> **Note:** LM Studio does not support `response_format: {"type": "json_object"}`.
> It requires `{"type": "json_schema", ...}` with a full schema definition.
> The `APIClient.is_local_provider()` method detects the provider type and selects
> the appropriate format automatically.
>
> **Provider Handshake:** Since the Provider Handshake migration, the response
> format, temperature handling, and thinking mode parameters are determined by
> each provider's `get_response_format()`, `get_temperature_config()`, and
> `get_thinking_config()` methods.  The `api_client.py` delegates to the resolved
> provider rather than using if/elif branches.  Temperature is omitted for
> GPT-5 family and o-series models.  Thinking parameters are injected only
> for Anthropic's explicit mode.

---

#### Tab Loading Performance

**Problem**: Current implementation freezes the UI for tens of seconds when loading tens of thousands of lines. This is unacceptable.

**Requirements**:
1. Tab switch (`on_enter`) must complete in < 100ms for any data size
2. Table population must be lazy/virtual — only render visible rows
3. Line data reads from manifest, NOT recomputed from previous steps
4. Cache strategy: if no changes detected (manifest hash or dirty flag), reuse last table state
5. Background thread for any heavy computation; UI thread only handles display updates
6. SharedTable must support virtual scrolling for 100K+ rows

**Cache Invalidation**: The tab caches its last displayed state. Cache is invalidated when:
- Preprocessing results change (manifest `lines[].prepro` modified)
- Lines are added/removed (file load in Step 0)
- Translation results are updated (after a translation run)
- User explicitly clicks "Refresh Lines"

**Implementation Status:** ✅ Phase 43 DONE — All 14 tasks implemented (48 tests passing, 4727 total suite)

---

#### Testing Requirements

**Required Test Coverage**:
- Tab load performance (must load 100K lines in < 1s)
- Mock Translation produces valid output preserving tokens
- Retry strategies (Batch, Contextual) behave correctly
- Lines/Chunk sync with Estimation step
- Language detection skip works correctly
- Cache invalidation triggers properly
- Progress window updates correctly
- Manifest persistence after each chunk
- Ban Tokens applied to API request
- Prompt Preview shows correct constructed prompt from manifest

**Test Files**:
- `dev/test_translation_phase43.py` — 48 tests covering all Phase 43 tasks

---

### Step 7: Quality Assurance

**Purpose**: Manual inspection of translation quality for issues that automatic recovery and retries could not resolve. Optimally, this step is never needed — the Translation step (Step 5) and Postprocessing step (Step 7) already employ the same validation scripts to automatically recover or retry failed lines. Only when those automated mechanisms are exhausted and issues remain does the QA step become relevant.

**Philosophy**: QA is a safety net, not a primary mechanism. The same scripts used in QA (`functions/validation.py`) are also called during translation (automatic recovery after each chunk) and postprocessing (restoration validation). The QA step surfaces what those automatic passes could not fix, allowing manual review, acceptance, or rejection.

**Current State (Placeholder)**: The QA step is currently rendered non-functional. A toggle switch (on by default, meaning the placeholder is active) replaces all QA widgets with a single informational label:

> *"Yet to be fully Implemented — Translation Step and Postprocessing Step currently employ all automatic fixes and log failures."*

When the toggle is turned off, the full QA interface loads (once implemented). This provides a clean, non-misleading UI until the step is fully built out.

---

#### Widgets (Current — Placeholder Mode)

| Widget | Type | Function |
|--------|------|----------|
| Placeholder Toggle | Switch/Checkbutton | On (default): show placeholder. Off: load full QA UI (future) |
| Placeholder Label | Label | Informational text explaining the step is not yet active |

---

#### Widgets (Future — Full Implementation)

The following widgets will be activated once the Translation/Edit/TLC mode toggle and full QA pipeline are implemented:

| Widget | Type | Function |
|--------|------|----------|
| Run QA Checks Button | Button | Execute validation |
| Export Report Button | Button | Save QA report to file |
| Refresh Button | Button | Reload translation data |
| Filter Radios | RadioGroup | all/errors/warnings/unfixed/accepted/rejected/edited/tlc'd |
| Lines Table | SharedTable | Lines with issue counts |
| Accept Selected Button | Button | Mark lines as accepted |
| Reject Selected Button | Button | Mark lines for re-translation |
| Auto-fix Selected Button | Button | Apply automatic fixes |
| Rules Panel | Frame | Enable/disable validation rules |
| Issue Details Panel | Frame | Show issues for selected line |
| Fix Suggestions List | Listbox | Suggested fixes for issues |

**Note on Edit/TLC Filtering**: Once Edit and TLC modes are featured in the Translation step, the QA Filter Radios will include "Edited" and "TLC'd" filters. These allow inspecting how much (or little) each inference pass changed, helping measure the value of additional passes.

---

#### Data Flow

**Inputs**:
- From Step 4: `prepro[]`, `prepro_ops[]` (for placeholder checking)
- Working text resolved as `postpro[] → tl[] → prepro[] → orig[]`
- `qa[]` is the reviewed QA text shown in the middle column
- `qa_overwrite[]` is a manual review/output field only and is never used as QA input
- From Step 5: `tl[]` remains the primary translation source when no later stage output exists

**Processing** (via `functions/validation.py`):
1. **Placeholder Check**: Verify all `__PROTECTED__` tokens preserved
2. **Anchor Check**: Verify `<>[]{}` characters preserved
3. **Japanese Check**: Flag remaining Japanese characters
4. **Speaker Format**: Verify `Name: "Dialogue"` preserved
5. **Quote Balance**: Check matching quote pairs
6. **Empty Check**: Flag empty translations
7. **Line Length**: Flag lines exceeding limit

**Note**: Steps 1-7 are the same validation rules already used by both the Translation step (post-chunk automatic recovery) and the Postprocessing step (restoration validation). QA does NOT add new validation logic — it provides a UI for manually reviewing what the automated passes left unresolved.

**Outputs**:
- `issues: List[QAIssue]` - All detected issues
- `lines: List[QALine]` - Lines with issue status
- `error_count: int` - Critical issues
- `warning_count: int` - Non-critical issues
- `accepted: List[int]` - User-accepted lines
- `rejected: List[int]` - Lines marked for retry
- `qa_overwrite[]` - Explicit manual overwrite text only when the user changes it; unchanged values are not auto-persisted

**Stored In**:
- Manifest step data (step_id=6)
- Issue list and acceptance status

---

#### Validation Rules (Reference — same rules as automatic recovery)

| Rule | Severity | Auto-fixable |
|------|----------|--------------|
| Placeholder Missing | ERROR | No |
| Placeholder Extra | ERROR | Yes (remove) |
| Anchor Missing | WARNING | No |
| Japanese Remaining | WARNING | No |
| Speaker Format Lost | ERROR | No |
| Quote Imbalance | WARNING | Yes (balance) |
| Empty Translation | ERROR | No |
| Line Too Long | WARNING | No |

---

### Step 6: Postprocessing

**Purpose**: Reverse all Preprocessing transformations and apply post-exclusive recovery processes to produce final translated text. Step 6 mirrors Step 3 — every Preprocessing transformation has a corresponding Postprocessing restoration that executes in reverse priority order. Additionally, Postprocessing includes exclusive recovery processes (Bracket Balance, Quote Balance, Whitespace Normalization) that only run here.

**Design Goals**:
1. **Mirror Symmetry**: Every Preprocessing transformation (Step 3) is reversed here. Without exception, all lines that were preprocessed are postprocessed.
2. **Reverse Priority Ordering**: Processes execute in descending priority order (highest priority runs first), the inverse of Preprocessing.
3. **Perfect Restoration**: All Preprocessing changes must be undone to produce accurate final output.
4. **Post-Exclusive Recovery**: Bracket Balance, Quote Balance, and Whitespace Normalization are Postprocessing-exclusive — they only appear here and address translation-introduced issues.
5. **Overwrite Semantics**: Postprocessing overwrites any previous postprocessing results. If results already exist, a confirmation warning is shown before overwriting.
6. **Stage-Bounded Input**: Postprocessing reads only `tl → prepro → orig`; it must never consume `postpro`, `wordwr`, `qa_overwrite`, or Edit/TLC rounds as its working input.
7. **Sparse Persistence**: `postpro` is only stored when the recovered output differs from `tl → prepro → orig`; unchanged results are removed from `lines[]` instead of being written redundantly.

**Implementation Status:** ✅ Phase 45 DONE — All 10 tasks implemented (49 tests passing, 4755 total suite)

---

#### Widgets Overview

The Postprocessing tab is organized into four sections:

1. **Header** — Title, status, and the Apply Postprocessing button (only action button)
2. **Left: Processed Lines Table** — Filterable table showing translated vs postprocessed text
3. **Right: Options Panels** — Recovery Options, Postprocess Options, Failure Handling, Diff View, Postprocessing Summary
4. **Bottom: Summary Bar** — Live aggregate statistics

---

#### Widget: Header

**Purpose**: Controls and status for the Postprocessing step.

| Widget | Type | Function |
|--------|------|----------|
| Title Label | Label | "Postprocessing" |
| Status Label | Label | Current status (Ready, Processing, Complete, Error) |
| Apply Postprocessing Button | Button | Execute all postprocessing — the only action trigger |

**Removed from previous spec** (no longer present):
- ~~Refresh Button~~ — Lines load automatically from previous steps on tab entry
- ~~Revert All Button~~ — Overwrite semantics replaces revert; re-running overwrites

**Behavior**:
- Clicking "▶ Apply Postprocessing" runs all enabled processes on all preprocessed lines
- If postprocessing results already exist, a confirmation dialog warns: "Postprocessing results already exist. Overwrite?" (OK / Cancel)
- Button is disabled during processing and re-enabled on completion
- Status label shows real-time progress: "Processing line 42/500…"

---

#### Widget: Processed Lines

**Purpose**: Display all lines with postprocessing results. Renamed from "Postprocessed Lines" to "Processed Lines".

**Columns**:
| Column | Content |
|--------|---------|
| # | Line index (1-based) |
| Status | Processing status icon and label |
| Changes | Count of recovery operations applied |
| Translated | Input text resolved from `tl → prepro → orig` only |
| Postprocessed | Output text after postprocessing |

**Status Values**:
| Status | Icon | Meaning |
|--------|------|---------|
| Changed | ✓ | Line was modified by postprocessing |
| Same | – | No changes needed |
| Written | ✎ | Failure was written as-is (default failure handling) |
| Flagged | ⚑ | Failure flagged for review (Skip policy) |

**Filters**:
| Filter | Shows |
|--------|-------|
| All | All lines |
| Changed | Only lines with modifications |
| Written | Lines where failures were written as-is |
| Flagged | Lines flagged for manual review |
| By Process | Filter by specific process name (e.g., "Bracket Balance", "Deduplication") |

**Behavior**:
- Table populates automatically when entering the tab (reads from previous steps)
- Only populated after "Apply Postprocessing" is clicked — before that, shows translated text in both columns
- Selecting a row updates the Diff View and Recovery Details panels
- Checkboxes allow batch selection for manual operations
- Supports virtual scrolling for large files (100K+ lines)

---

#### Widget: Recovery Options

**Purpose**: Toggle post-exclusive recovery processes. These processes only exist in Postprocessing and address issues introduced by the translation process itself.

| Widget | Type | Default | Function |
|--------|------|---------|----------|
| Bracket Balance Recovery | Checkbox | ✓ | Fix unmatched brackets only when the original bracket structure is balanced |
| Quote Balance Recovery | Checkbox | ✓ | Fix unmatched quotes by comparing with original |
| Whitespace Normalization | Checkbox | ✓ | Restore indentation and spacing to match original |

**Bracket Balance Recovery** (Post-Exclusive):
- Runs only when the original line has balanced recoverable brackets and the latest translated text is unbalanced; rare intentionally unbalanced source lines are left unchanged
- Compares bracket pairs in translated text against the original using ANCHOR_EQUIVS equivalence (fullwidth/halfwidth variants treated as the same bracket), with `【】` canonicalised to the square-bracket family `[]`
- Uses anchor-relative logic (line start `^`, end `$`, adjacent punctuation via `get_equivs()`) to determine insertion points for missing brackets
- Bracket-quote hybrids (e.g. `「」` whose canonical form is `"`) are deferred to Quote Balance Recovery to avoid double-counting
- Supports all bracket types: `[]`, `{}`, `<>`, `()`, `『』`, `【】`, `〔〕`, `《》`, `〈〉`, plus fullwidth variants `［］`, `｛｝`, `＜＞`, `（）`
- Balanced latest text is ignored even if it changed bracket style; missing-bracket repair only starts from an actual imbalance
- Extra unmatched brackets in the translated text are removed when the balanced source proves they are over-insertions (for example an LLM-added third `}` after a `{{...}}` code)
- If a bracket is missing, only insert at the direct position (before/after) from a located anchor — no absolute positional calculations
- If balance cannot be achieved (no anchor found in translated text), flags the line for review (`NEEDS_RETRY`)

**Code Pattern Recovery** (Post-Exclusive):
- For each code pattern with `action='preserve'`, uses `generate_regex_pattern()` to find all occurrences in the original text
- If an original occurrence is missing in the translation, scans for content wrapped in the same delimiters (e.g. `{...}`, `[...]`, `<...>`) that does NOT appear in the original text — these are likely translated substitutes
- Replaces the first unmatched candidate with the original pattern (e.g. `{anchor}` → `{アンカー}`)
- If no candidate is found (pattern completely missing), flags the line as `NEEDS_RETRY` for QA review
- Runs inside `recover_line()` after placeholder recovery and before bracket/quote balance recovery
- Balanced nested substring matches are ignored, so a preserve rule for `{主人公}` does not fire just because `{{主人公}}` was present on the line
- Also validated during translation: `validate_translation_comprehensive()` check #7 detects missing preserve-action patterns and adds `CODE_PATTERN_TRANSLATED` retry reason

**Quote Balance Recovery** (Post-Exclusive):
- **Important**: Quote recovery runs BEFORE bracket balance check. Quotes stripped during Preprocessing Symbol Conversion must be recovered first, then balance is verified.
- Uses ANCHOR_EQUIVS equivalence to recognise bracket-quote conversions (`「」` → `""`, `＂` → `"`, curly `""` → straight `"`) — converted quotes are NOT counted as missing
- Distinct from Preprocessing quote stripping — Symbol Conversion may convert `「」` to `""` during pre; here we ensure the translated text has matching quote pairs
- Supports: `""`, `''`, `""`, `''`, fullwidth `＂＂`, plus bracket-quotes `「」` via equivalence
- Missing closing quotes → inserted at line end (dialogue end)
- Missing opening quotes at line start → inserted at line start (dialogue start)
- Interior missing quotes use anchor-relative logic (`_find_anchor_near` + `get_equivs`) or are flagged `NEEDS_RETRY`
- Handles same-character quote pairs (straight quotes) via open/close alternating state tracking

**Whitespace Normalization** (Post-Exclusive):
- Matches indentation of translated lines to their originals
- Detects speaker indent patterns (e.g., `　太郎：` uses fullwidth space indent)
- Preserves leading whitespace count and type (spaces vs tabs vs fullwidth spaces)
- Normalizes errant spacing around placeholders (`__ PROTECTED __` → `__PROTECTED__`)
- Does NOT alter intentional whitespace within dialogue text

**Removed from GUI** (automatic from manifest — no user toggle):
- ~~Placeholder Recovery~~ — Always runs automatically; recovery of `__PROTECTED__`, `__CUSTOM__`, `__DEDUP__` tokens is mandatory and not optional
- ~~Restore Code Characters~~ — Always runs automatically as part of the Protect Code Patterns restoration
- ~~Restore `<br>` Tags~~ — Always runs automatically as part of line break restoration from manifest `prepro_ops`

**Manifest Keys**: `PostProcessing.BracketBalanceRecovery`, `PostProcessing.QuoteBalanceRecovery`, `PostProcessing.WhitespaceNormalization`

---

#### Widget: Postprocess Options

**Purpose**: Configure symbol conversion direction for postprocessing. Preprocessing converts JP→EN; Postprocessing can optionally convert back.

| Widget | Type | Default | Function |
|--------|------|---------|----------|
| Enable Symbol Conversion | Checkbox | ✓ | Enable/disables other symbol conversion (like quote equivalents) |
| Fullwidth → Halfwidth | Checkbox | ✗ | Convert fullwidth punctuation/alphanumeric to halfwidth |
| Halfwidth → Fullwidth | Checkbox | ✗ | Convert halfwidth punctuation/alphanumeric to fullwidth |

**Behavior**:
- Symbol Conversion is for converting symbols other than punctuation and alphanumeric widths like quotes
- Fullwidth→Halfwidth and Halfwidth→Fullwidth are mutually exclusive (enabling one disables the other)
- Direction depends on target language: JP target typically needs Halfwidth→Fullwidth; EN target typically needs Fullwidth→Halfwidth
- Uses the same conversion table as Preprocessing Step 4 Symbol Conversion, applied in the chosen direction

**Conversion Table** (same as Step 4, bidirectional):
| Fullwidth | Halfwidth |
|-----------|-----------|
| `！` | `!` |
| `？` | `?` |
| `：` | `:` |
| `；` | `;` |
| `，` | `,` |
| `。` | `.` |
| `（` | `(` |
| `）` | `)` |
| `【` | `[` |
| `】` | `]` |
| `｛` | `{` |
| `｝` | `}` |
| `＜` | `<` |
| `＞` | `>` |
| `＂` | `"` |
| `＇` | `'` |
| `～` | `~` |
| `＝` | `=` |
| `＋` | `+` |
| `－` | `-` |
| `＊` | `*` |
| `／` | `/` |
| `＼` | `\` |
| `＠` | `@` |
| `＃` | `#` |
| `＄` | `$` |
| `％` | `%` |
| `＆` | `&` |
| `＿` | `_` |
| `　` | ` ` (space) |
| `０-９` | `0-9` |
| `Ａ-Ｚ` | `A-Z` |
| `ａ-ｚ` | `a-z` |

**Manifest Keys**: `PostProcessing.EnableSymbolConversion`, `PostProcessing.FullwidthToHalfwidth`, `PostProcessing.HalfwidthToFullwidth`

---

#### Widget: Failure Handling

**Purpose**: Configure how postprocessing failures (unrecoverable issues) are handled.

| Option | Label | Default | Behavior |
|--------|-------|---------|----------|
| Write | "Write (keep as-is)" | ✓ (default) | Write the line to output even if recovery failed. The line is included in results with whatever partial recovery was achieved. This is the nominal path. |
| Skip | "Flag for Review" | ✗ | Do NOT write an entry. Flag the line for manual review. Log the failure. The line appears in the Flagged filter with details of what went wrong. |
| ~~Retry~~ | ~~"Queue for Retry"~~ | — | **Hidden (Future Improvement)**: Queue the line for re-translation with stricter instructions. Not yet implemented; will be exposed when retry pipeline is built. |

**Behavior**:
- "Write" is the default because partial recovery is almost always better than no output
- "Flag for Review" (previously "Skip") does not produce an output entry — the line remains untranslated/unprocessed until manually resolved via the Diff View
- Failed lines are always logged regardless of policy
- Failure details include: which recovery type failed, what was attempted, suggestions for manual fix

**Manifest Key**: `PostProcessing.FailureHandling` (values: `write`, `flag`)

---

#### Widget: Diff View

**Purpose**: Show a character-level diff between the translated input and the postprocessed output for the selected line. Supports manual editing and problem resolution.

| Component | Type | Function |
|-----------|------|----------|
| Line Info Label | Label | Shows line number and status |
| Diff Text Display | ScrolledText | Character-level diff with color highlighting |
| Edit Field | Text | Editable text field for manual corrections |
| Mark as Fixed Button | Button | Accept manual edit, update postprocessed result |
| Recovery Details List | Listbox | List of recovery operations applied to this line |

**Diff Highlighting**:
| Tag | Color | Meaning |
|-----|-------|---------|
| Addition | Green (#22c55e) | Text added by postprocessing |
| Deletion | Red (#ef4444) | Text removed by postprocessing |
| Problem | Yellow/Orange (#f59e0b) | Issues that need attention (flagged failures) |
| Header | Blue (accent_info) | Section headers |

**Manual Editing Behavior**:
- The Edit Field is pre-populated with the postprocessed text
- User can modify the text freely
- Clicking "✓ Mark as Fixed" writes the edited text as the postprocessed result for that line
- The line's status changes to "Changed" and the diff updates to reflect the manual edit
- Manual edits are written to the manifest immediately

**Manifest Key**: Manual edits stored in `lines[].postpro` (overwrites automatic result)

---

#### Widget: Postprocessing Summary

**Purpose**: Live aggregate statistics panel showing postprocessing progress and results.

| Metric | Description |
|--------|-------------|
| Total | Total lines processed |
| Changed | Lines with modifications |
| Recovered | Total recovery operations successfully applied |
| Written | Lines written despite failures (Write policy) |
| Flagged | Lines flagged for review (Flag policy) |
| Rate | Recovery success rate (recovered / total issues × 100%) |

**Behavior**:
- Updates in real-time during postprocessing (after each line completes)
- At 100% completion, a popup dialog appears: "Postprocessing Complete — N lines processed, M changes applied, K issues flagged" with OK button
- Summary data persists in manifest for reference in later steps

**Manifest Keys**: `Postprocessing.recovery_rate`, `Postprocessing.total_processed`, `Postprocessing.flagged_count`

---

#### Process Execution Order

Postprocessing reverses the Preprocessing order. Highest priority runs first (opposite of Preprocessing where lowest runs first). Automatic restorations (from manifest `prepro_ops`) execute first, followed by post-exclusive recovery processes.

**Automatic Restorations** (from manifest — no GUI toggle):
| Priority | Process | Description |
|----------|---------|-------------|
| 10 | Anchoring Restoration | Restore anchored content FIRST (matches Anchoring P75 pre) |
| 20 | Protect Code Patterns | Restore `__PROTECTED__` tokens to original code |
| 30 | Custom Placeholders | Restore configured custom tokens to original strings; unresolved values fall back to a batch-wide exact-token scan so misplaced named replacements can still be restored |
| 40 | PROTECTED Token Decompression | Decompress `__PROTECTED_N__` → N individual `__PROTECTED__` tokens |
| 50 | Code Spacing Restoration | Restore original code spacing |
| 60 | Speaker Name Restoration | (No restoration needed — names stay translated) |
| 70 | Symbol Conversion | Optionally restore JP symbols based on Postprocess Options direction |
| 80 | Ellipsis Expansion | Restore ellipsis to original length |
| 90 | Deduplication Restoration | Apply translation to all duplicate lines LAST |

**Post-Exclusive Recovery Processes** (after all automatic restorations, user-toggleable):
| Priority | Process | Description |
|----------|---------|-------------|
| 100 | Quote Balance Recovery | Fix unmatched quotes (runs before bracket balance) |
| 110 | Bracket Balance Recovery | Fix unmatched brackets using anchor logic |
| 120 | Whitespace Normalization | Match indentation/spacing to original |

**Execution Note**: Quote Balance Recovery (P100) runs before Bracket Balance Recovery (P110) because quotes stripped during Preprocessing Symbol Conversion must be recovered before bracket balance is assessed — a quote character adjacent to a bracket affects balance detection.

---

#### Character/Word Validation

**Purpose**: After all postprocessing, validate the result for character-level issues.

| Component | Type | Function |
|-----------|------|----------|
| Run Validation Button | Button | Execute character/word validation scan |
| Status Label | Label | "Not scanned" / "N issues in M lines" / "✓ No issues" |
| Warnings Count | Label | Number of warnings (fixable) |
| Errors Count | Label | Number of errors (manual review) |
| Findings List | Listbox | Individual findings with severity, line, and suggestion |
| Apply Autofix Button | Button | Apply autofix map to all fixable warnings |

**Behavior**:
- Reads whitelist, blacklist, word blacklist, and autofix map from manifest (`CharacterValidation` section)
- Checks the `postprocessed` field of each line
- Autofix applies character replacements from the configured autofix map
- Re-runs validation after autofix to show remaining issues

---

#### Data Flow

**Inputs**:
- From Step 4: `prepro_ops[]` — Restoration metadata per line (what was changed and how to reverse it)
- From Step 5: `tl[]` — Translated lines (or `edit[]`, `tlc[]` if available from future Edit/TLC modes)
- From Step 6: `qa_lines[]` — QA-reviewed lines (if QA modified any)
- From Manifest: Recovery option toggles, symbol conversion settings, failure handling policy

**Processing** (via `functions/postprocess.py` + `modi/` modules):
1. Load lines from best available source: QA → Edit → TLC → Translation → Preprocessed
2. For each line with `prepro_ops`:
   a. Execute automatic restorations in priority order (P10→P90)
   b. Each restoration reads its metadata from `prepro_ops` and reverses the transformation
  c. Custom Placeholder restoration performs a second batch-wide pass for unresolved named tokens so line-shifted replacements can still be restored safely
3. Execute post-exclusive recovery processes (P100→P120) if enabled
4. Apply symbol conversion if enabled (direction per Postprocess Options)
5. Run failure handling policy on any unrecoverable issues
6. Update summary statistics in real-time
7. Store results in manifest

**Outputs**:
- `postpro: List[str]` — Fully restored and recovered lines
- `recovery_stats: RecoveryStats` — Per-type success/failure counts
- `flagged_lines: List[int]` — Lines flagged for manual review (Flag policy)
- `validation_result` — Character/word validation findings (if run)

**Stored In**:
- Manifest: `lines[].postpro`
- Manifest step data: `Postprocessing.recovery_rate`, `Postprocessing.FailureHandling`, all option toggles

---

#### User Actions

| Action | Effect |
|--------|--------|
| Click Apply Postprocessing | Execute all postprocessing (warns if overwriting existing results) |
| Toggle Recovery Option | Enable/disable post-exclusive recovery process |
| Toggle Symbol Conversion | Enable/disable and configure direction |
| Change Failure Handling | Switch between Write and Flag policies |
| Select Line in Table | Show diff and recovery details in right panels |
| Edit in Diff View | Manually correct postprocessed text |
| Click Mark as Fixed | Accept manual edit, update manifest |
| Filter Processed Lines | Show subset matching filter criteria |
| Run Validation | Execute character/word validation scan |
| Apply Autofix | Apply autofix map to fixable warnings |

---

#### Testing Requirements

**Required Test Coverage**:
- Each automatic restoration process individually (Anchoring, PROT, Custom, Dedup, etc.)
- Each post-exclusive recovery process (Bracket Balance, Quote Balance, Whitespace Normalization)
- Symbol conversion in both directions (Fullwidth→Halfwidth, Halfwidth→Fullwidth)
- Failure handling policies (Write vs Flag behavior)
- Overwrite warning when re-running postprocessing
- Manual editing via Diff View
- Summary statistics accuracy and real-time updates
- Roundtrip: Preprocessing → Translation → Postprocessing produces expected output
- Large file performance (100K+ lines)
- Edge cases: empty lines, lines with only code, lines with mixed bracket types

**Test Files** (to be created/extended):
- `dev/test_postprocessing_restoration.py`
- `dev/test_postprocessing_bracket_balance.py`
- `dev/test_postprocessing_quote_balance.py`
- `dev/test_postprocessing_whitespace.py`
- `dev/test_postprocessing_symbol_conversion.py`
- `dev/test_postprocessing_failure_handling.py`
- `dev/test_postprocessing_diff_view.py`
- `dev/test_preprocessing_postprocessing_roundtrip.py`

---

### Step 8: Wordwrap

**Purpose**: Apply wordwrap rules to format text for game engine display requirements. Wordwrap operates in two conceptual modes: **automatic** (parser-detected settings based on the game engine format) or **manual** (user-configured width, break character, and line limits). The core wrapping algorithm is `pretty_wrap` — punctuation-preferred breaks and anti-orphan handling are always active (no user toggle).

#### Philosophy

Wordwrap is the final text-shaping step before output. It must produce lines that fit within the target engine's display constraints while preserving readability. The step runs after QA, consuming QA-reviewed text when present. The table now separates the stage input from the stored Wordwrap result so the Wordwrap column only shows real `wordwr` values.

Persistence rule: preview refresh and tab leave do not write `wordwr`. Only explicit Apply persists wrapped output, and unchanged results are removed instead of stored redundantly.

Key principles:
- **Pretty wrap is standard**: Punctuation-preferred line breaks and orphan prevention are always active — no checkboxes.
- **Parser-driven when possible**: When a parser provides display constraints (width, break character, max lines), settings are auto-populated and displayed (user can override).
- **Code-aware**: Ignore patterns come from the Code Database (Step 3), not from hardcoded checkboxes.
- **Overwrite integrated**: The Overwrite column lives in the same table as Wordwrap, eliminating the need for a separate Overwrite Strategy widget. It can be editted.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Apply Wordwrap Button | Button | Execute wrapping on all lines |
| Refresh Preview Button | Button | Recalculate preview without applying |
| Reset Button | Button | Clear wordwrap results |
| Mode Dropdown | Combobox | Wrapping mode (Manual, parser-specific modes) |
| Width Dropdown | Combobox | Line width — Character count or Pixel-based |
| Tag Sections | Frame per tag | Per-tag Width / BreakChar / MaxLines settings |
| Add Tag Dropdown | Combobox | Add a new tag section from available tags |
| Break Character Entry | Entry | Line break sequence (auto-detected, editable) |
| Max Lines Spinbox | Spinbox | Maximum lines per box (0=unlimited) |
| Speaker Handling Dropdown | Combobox | How to count speaker prefixes: Ignore / Count |
| Ignore Patterns Table | Table (read-only) | Patterns from Code Database used during wrap |
| Lines Table | SharedTable | Source, Wordwrap, Overwrite columns with filters |
| Filter Radios | RadioGroup | All / Changed / Exceeding / Overwrite Differs |

**Removed Widgets** (compared to previous spec):
- ~~Ignore Patterns Checkboxes~~ → Sourced from Code Database (Step 3), shown as read-only table
- ~~Typography Style Dropdown~~ → Removed entirely
- ~~Typography Checkboxes~~ → Removed entirely
- ~~Overwrite Strategy Dropdown~~ → Overwrite is a table column, not a separate mode
- ~~Merge Method Dropdown~~ → Removed with Overwrite Strategy
- ~~Backup Suffix Entry~~ → Removed with Overwrite Strategy
- ~~Format Dropdown~~ → Replaced by parser-aware Mode Dropdown
- ~~Orphan prevention / Punct breaks (global)~~ → Now configurable per-tag

#### Per-Tag Wordwrap Settings

Wordwrap settings are wrapped in tag sections. Each tag (e.g., `dialogue`, `menu`, `variable`) has its own Width, Break Character, Max Lines, Speaker Handling, Prevent Orphans, Prefer Punctuation Breaks, and New Textbox configuration. Standard tags `dialogue` and `menu` are always present; additional tags are discovered from filedir `type` fields and line `tag` fields.

**TagWrapConfig** (dataclass):
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tag` | str | — | Tag name (e.g., "dialogue", "menu") |
| `width` | int | 48 | Characters per line (0=no wrap) |
| `break_char` | str | "\\n" | Line break sequence |
| `max_lines` | int | 4 (dialogue) / 0 (menu) | Max lines per box (0=unlimited) |
| `speaker_handling` | str | "count" | "ignore" or "count" — how speaker prefixes affect wrap width |
| `prevent_orphans` | bool | True | Prevent tiny orphan words on the last line |
| `prefer_punct_breaks` | bool | True | Prefer breaking after punctuation when possible |
| `new_textbox` | bool | False | Create a new textbox when max lines exceeded |
| `new_textbox_injection` | str | "" | Text injected to signal new textbox (e.g., "\\w" for LightVN) |

**Behavior**:
- **Parser-provided defaults**: When the active parser provides `wordwrap_for_tag(tag)` returning a non-None config, the tag section is pre-populated with the parser's values (width, break char, max lines, new textbox injection). All values remain **editable** — the parser only provides sensible defaults.
- **Width=0**: Zero width means no wrapping for that tag.
- **Tag resolution** (per line): Line `tag` field → filedir entry `type` field → `"dialogue"` fallback.
- **Add Tag**: Dropdown shows tags not yet configured. Adding creates a new section with parser-provided defaults (when available).
- **Remove Tag**: Non-standard tags (not dialogue/menu) have a "Remove tag" button.
- **Manifest persistence**: `WordwrapSettings.TagConfigs` stores the list of `TagWrapConfig.to_dict()` entries.

#### Widget Specifications

##### Mode Dropdown

| Property | Value |
|----------|-------|
| Type | Combobox (dropdown, not radio buttons) |
| Default | "Manual" |
| Options | Manual (+ future parser-specific modes) |
| Manifest Key | `WordwrapSettings.Mode` |

**Behavior**:
- **Manual**: User configures all settings (width, break char, max lines) directly.
- Parser-specific modes will be added as parsers are implemented (e.g., when RPG Maker becomes its own parser, it will appear as a mode option that auto-populates width from project analysis).
- RPG Maker is **not** a wordwrap mode — it becomes its own parser (see Future Improvements).
- "Disabled" option is removed — if no wrapping is desired, simply don't click Apply.

##### Width Dropdown

| Property | Value |
|----------|-------|
| Type | Combobox (dropdown) |
| Default | "48 characters" |
| Options | Character-based presets, "Pixel" option |
| Range (character) | 20–200 |
| Manifest Key | `WordwrapSettings.Width`, `WordwrapSettings.WidthMode` |

**Behavior**:
- **Character mode** (default): Width in character count. Simple division of line length.
- **Pixel mode**: Width in pixels. Requires font metrics for accurate calculation. When selected, shows additional fields for font size and pixel width.
- Pixel-accurate calculation is primarily relevant for engines like RPG Maker that have variable-width fonts and known display dimensions.
- Max length per variable: when engine variables are present in text, their maximum rendered length should be accounted for in width calculations.

##### Break Character Entry

| Property | Value |
|----------|-------|
| Type | Entry (combobox with common options) |
| Default | Auto-detected from input format |
| Common Options | `\n`, `[br]`, `[r]`, `<br>` |
| Manifest Key | `WordwrapSettings.BreakChar` |

**Behavior**:
- Auto-detected from the input files during loading (parser identifies the line break convention).
- Linked to **Preprocessing** (Step 3): The break character should be protected during preprocessing so it is not mangled by translation.
- Linked to **Translation Prompt** (Step 5): The prompt should state what the line break character is so the LLM can use it correctly.
- **Cost optimization** (future, belongs to Preprocessing): Line breaks may optionally be removed before translation to reduce token count (fewer characters = fewer costs). If enabled, a warning is displayed that post-editing may be needed since the LLM won't see line structure. Re-wrapping after translation restores line breaks.

##### Max Lines Spinbox

| Property | Value |
|----------|-------|
| Type | Spinbox |
| Default | 0 (unlimited) |
| Range | 0–20 |
| Manifest Key | `WordwrapSettings.MaxLines` |

**Behavior**:
- When wrapping produces more lines than the maximum:
  - **Flag the line**: Mark in the Lines Table as "Exceeding" for manual review.
  - **New box** (future): Split overflow into a new text box entry (requires parser support for text box boundaries — see Future Improvements).
- 0 means unlimited (no max line constraint).

##### Speaker Handling Dropdown

| Property | Value |
|----------|-------|
| Type | Combobox (dropdown) |
| Default | "Ignore" |
| Options | Ignore, Count |
| Manifest Key | `WordwrapSettings.SpeakerMode` |

Speaker format is always `Speaker: Dialogue` or `Speaker: "Dialogue"`.

**Options**:
- **Ignore**: Don't count the speaker prefix toward line width — only measure the dialogue portion. Use when the speaker name is injected into a separate name field during output. The trailing space after `:` belongs to the speaker and is stripped during injection.
- **Count** (renamed from "Sameline"): Speaker prefix (name + `:` + spaces) is counted toward line width. Use when the speaker is part of the displayed line and takes up horizontal space.

**Removed Options**:
- ~~Samelineindent~~ → Redundant. Respecting indentation on continuation lines is inherent behavior of `Count` mode (hanging indent from `pretty_wrap`).
- ~~Newline~~ → Redundant. The choice is binary: either ignore the speaker (separate name field) or count it (inline).

##### Ignore Patterns (Code Database Integration)

Ignore patterns are **no longer configured in Wordwrap settings**. Instead, they are sourced from the **Code Database** (Step 2, Information tab):

- The Code Database defines code patterns with their actions (Preserve, Translate, Remove) and Categories.
- Patterns marked as **Invisible** are automatically treated as invisible during width calculation.
- The Wordwrap step displays a read-only summary table showing which patterns are being ignored.
- No tickboxes — the single source of truth is the Code Database.

| Display Column | Source |
|----------------|--------|
| Pattern | Code Database pattern regex |
| Action | Preserve / Remove |
| Example | Sample match from loaded text |

##### Lines Table

| Column | Source | Description |
|--------|--------|-------------|
| # | Index | Line number |
| Original | `qa_overwrite[] → qa[] → postpro[] → tl[] → prepro[] → orig[]` | Input text for wrapping (stage-bounded) |
| Wordwrap | `wordwr[]` | Wrapped result |
| Overwrite | `overwrite[]` | Final injected text (populated during wrap) |
| Status | Computed | OK / Exceeding / Differs |

**Overwrite Column Behavior**:
- Loaded only from stored `wordwr[]` values; it is not prefilled from the current input chain.
- The Overwrite value represents the text as it will appear in the output file after injection.
- **Standard behavior**: Output (Step 9) prioritizes `overwrite[]` over `wordwr[]`. 
- When Overwrite differs from Wordwrap, the line is flagged as "Differs" and can be filtered for (like to undo edits).
- Can be editted.

**Filters**:
- **All**: Show all lines.
- **Changed**: Lines where Wordwrap differs from the input.
- **Exceeding**: Lines where wrapping produced more lines than Max Lines allows.
- **Overwrite Differs**: Lines where Overwrite ≠ Wordwrap.

#### Data Flow

**Inputs**:
- From Step 7: stage-bounded text resolved as `qa_overwrite[] → qa[] → postpro[] → tl[] → prepro[] → orig[]`
- From Step 3: Code Database patterns (for ignore pattern list)
- From Manifest: `WordwrapSettings.*` (saved settings)

**Processing** (via `functions/wordwrap.py`):
1. Load ignore patterns from Code Database (Preserve + Remove action patterns).
2. Build tag maps: `line_tag_map` (line index → tag from `lines[].tag`) and `filedir_type_map` (file directory → type from `file_dir[].type`).
3. For each line:
   a. Resolve tag: line `tag` → filedir `type` → `"dialogue"` fallback.
   b. Look up `TagWrapConfig` for resolved tag. Width=0 → skip (no wrap).
   c. Detect speaker prefix per Speaker Handling mode.
   d. Calculate visible width (excluding ignored code patterns).
   e. **Parser-managed tag**: Try O6 `parser.wordwrap()` → O9 `parser.pretty_wrap()` → passthrough.
   f. **User-managed tag**: Try O9 `parser.pretty_wrap()` → built-in `pretty_wrap()` with per-tag config.
   g. Insert break characters at calculated positions.
   h. Respect max lines constraint (flag if exceeding).
   i. Populate Overwrite column with injection-ready text.
4. Calculate wrap statistics (lines changed, lines exceeding, total breaks inserted).

**Outputs**:
- `wordwr: List[str]` — Wrapped lines
- `overwrite: List[str]` — Injection-ready output lines
- `wrap_stats: WrapStats` — Lines wrapped, exceeding count, break count

**Stored In**:
- Manifest: `lines[].wordwr`, `lines[].overwrite`
- Manifest step data: `WordwrapSettings.Mode`, `WordwrapSettings.Width`, `WordwrapSettings.WidthMode`, `WordwrapSettings.BreakChar`, `WordwrapSettings.MaxLines`, `WordwrapSettings.SpeakerMode`, `WordwrapSettings.TagConfigs`

#### Standard Wrapping Rules (Always Active)

These behaviors are built into `pretty_wrap()` and are NOT user-configurable:

| Rule | Description |
|------|-------------|
| Punctuation-preferred breaks | When a line exceeds width, backtrack to the last token ending with punctuation (`.`, `,`, `!`, `?`, `;`, `:`, `—`, `…`) if available |
| Anti-orphan | If the last wrapped line contains ≤ 20% of width in characters, rebalance by moving one word from the previous line |
| Hanging indent | Continuation lines for speaker/bullet prefixes maintain the indentation level of the content start |
| Code-aware width | Ignored patterns (from Code Database) do not count toward visible width |

#### Testing Requirements

- Unit tests for all wrapping modes and edge cases
- Speaker Ignore vs Count with various prefix formats
- Code pattern exclusion from width calculation
- Max lines flagging behavior
- Overwrite column population and diff detection
- Break character auto-detection accuracy
- Width calculation in character and pixel modes
- Empty lines, code-only lines, very long words (hard-break fallback)
- Lines with mixed code patterns and visible text

**Test Files** (to be created/extended):
- `dev/test_wordwrap_modes.py`
- `dev/test_wordwrap_speaker.py`
- `dev/test_wordwrap_code_patterns.py`
- `dev/test_wordwrap_overwrite_integration.py`
- `dev/test_wordwrap_pixel_width.py`

**Implementation Status:** ✅ Phase 46 DONE — All 10 tasks implemented (45 tests passing, 4832 total suite)

---

### Step 9: Output

**Purpose**: Generate output files by injecting the best available translation into copies of the original files. The Output step is the final pipeline stage — it resolves which text to inject per line, validates that upstream steps completed cleanly (via dirty flags), and writes non-destructive output. It receives format and structure settings from Input (Step 0) and has its own settings for destination, naming, and backup.

#### Philosophy

Output's job is to produce files that are ready to use. It must:
- **Be non-destructive by default**: Original files are never modified. Default naming strategy is `subfolder` ("put in subfolder").
- **Open with valid defaults**: Output settings must always resolve to a usable manifest-backed state. Destination defaults to `Same as Source`, preserve structure defaults to on, pair mode defaults to `custom`, overwrite defaults to on, backup defaults to `timestamp` with `.bk`, and format/encoding default to the loaded Input metadata when unset.
- **Use the best available text**: The injection priority chain determines which field to use per line.
- **Validate completeness**: Dirty flags from upstream steps must be cleared before export (with warnings if not).
- **Log failures**: Every write failure is logged with the file path and error for review.

#### Injection Priority Chain

For each line, Output resolves the text to inject by walking the following priority chain **from top to bottom**, using the **first non-empty value** found:

| Priority | Manifest Field | Source Step | Description |
|----------|---------------|-------------|-------------|
| 1 (highest) | `lines[].wordwr` | Step 8: Wordwrap | Wordwrapped text |
| 2 | `lines[].qa_overwrite` | Step 7: QA | QA-overwritten text |
| 3 | `lines[].qa` | Step 7: QA | QA-reviewed text |
| 4 | `lines[].overwrite` | Legacy / compatibility | Legacy overwrite text |
| 5 | `lines[].postpro` | Step 6: Postprocessing | Postprocessed text |
| 6 | `lines[].edit{N}` | Step 5: Translation (Edit mode) | Latest Edit round (highest N) |
| 7 | `lines[].tlc{N}` | Step 5: Translation (TLC mode) | Latest TLC round (highest N) |
| 8 | `lines[].tl` | Step 5: Translation | Base translation |
| 9 | `lines[].preedit` | Step 5: Translation (Pre-edit) | Pre-edit result |
| 10 | `lines[].prepro` | Step 3: Preprocessing | Preprocessed text |
| 11 (lowest) | `lines[].orig` | Step 0: Input | Original extracted text |

**Notes**:
- `edit{N}` and `tlc{N}` are round-numbered fields (e.g., `edit1`, `edit2`, `tlc1`). The highest available round number is used.
- When no processing has occurred, the original text is injected (passthrough).
- The function `get_final_output(line_entry)` implements this chain and returns a `(text, source_field)` tuple for logging.

#### Dirty Flags (Pipeline Completeness Check)

Before exporting, Output checks dirty flags to warn the user if upstream steps have unfinished work:

| Flag | Set When | Cleared When | Warning Message |
|------|----------|--------------|-----------------|
| Process Flag | Any preprocessing is applied (Step 3) | Postprocessing reaches 100% completion (Step 6) | "Preprocessing was applied but Postprocessing is not complete. Output may contain unrecovered codes." |
| Wordwrap Flag | Files are loaded or translation changes | Wordwrap is applied (Step 7) | "Wordwrap has not been applied. Output will use unwrapped text." |

**Behavior**:
- Dirty flags are stored in manifest step data: `DirtyFlags.process`, `DirtyFlags.wordwrap`
- On export attempt with dirty flags, a warning dialog is shown listing all dirty flags.
- User can choose to **Export Anyway** or **Cancel** to go fix the issues first.
- The Summary panel shows dirty flag status with visual indicators (⚠ or ✓).

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Export All Button | Button | Write all output files |
| Cancel Button | Button | Stop export |
| Refresh Preview Button | Button | Recalculate output files |
| Filter Radios | RadioGroup | all / pending / written / failed |
| Files Table | SharedTable | Source → output mapping with status |
| Summary Panel | Frame | Export stats, dirty flag status, failure log |
| **Destination Options** | | |
| Destination Entry | Entry | Output directory path |
| Browse Button | Button | Select output directory |
| **Format Options** | | |
| Format Dropdown | Combobox | txt / csv / tsv / json / xlsx / injection (default: same as Input) |
| Encoding Dropdown | Combobox | utf-8 / utf-8-sig / shift_jis / etc. (default: same as Input) |
| Pair Mode Dropdown | Combobox | custom / translated_only / side_by_side / interleaved / separate_files |
| **Naming Options** | | |
| Naming Strategy Dropdown | Combobox | subfolder (default) / suffix / prefix / replace |
| Naming Value Entry | Entry | Subfolder name, suffix, or prefix text |
| **Safety Options** | | |
| Preserve Structure Checkbox | Checkbox | Maintain folder hierarchy in output |
| Overwrite Checkbox | Checkbox | Overwrite existing output files (default: on) |
| Backup Strategy Dropdown | Combobox | timestamp (default) / numbered / extension / none |
| Backup Extension Entry | Entry | Extension for backup files (default: .bk) |
| **Export Extras** | | |
| Export Manifest Checkbox | Checkbox | Include manifest copy in export |
| Export Logs Checkbox | Checkbox | Include processing logs in export |
| Export Glossary Checkbox | Checkbox | Include glossary entries in export |

#### Widget Specifications

##### Destination Options

| Property | Value |
|----------|-------|
| Default Destination | `Same as Source` |
| Browse | Opens folder picker dialog |
| Resolution | Resolved at runtime to the **parent** of the `Original/` directory so that output subfolders (e.g. `translated/`) sit next to `Original/` rather than inside it |
| Auto-populate | When naming strategy is `subfolder`, preview/export paths are built under `{resolved_destination}/{naming_value}/...` |
| Manifest Key | `OutputFormat.Destination` |

##### Files Table

| Column | Content |
|--------|---------|
| # | File index |
| Status | pending / written / failed (with icon) |
| Source | Source file path (relative to source_root) |
| Output | Output file path (relative to destination) |
| Format | File format |
| Lines | Line count |

##### Summary Panel

Displays after export:
- Total files / written / failed / skipped counts
- Duration and lines written
- Dirty flag status indicators (⚠ Process / ⚠ Wordwrap / ✓ Clean)
- **Failure Log**: Scrollable list of failed writes with file path and error message

#### Naming Strategies

| Strategy | Default Value | Example |
|----------|---------------|---------|
| subfolder (default) | "translated" | `input.txt` → `translated/input.txt` |
| suffix | "_translated" | `input.txt` → `input_translated.txt` |
| prefix | "translated_" | `input.txt` → `translated_input.txt` |
| replace | Pattern/replacement | `input.txt` → `output.txt` |

**Default**: `subfolder` with value `"translated"`. This is the safest non-destructive option — originals are untouched.

#### Pair Modes

| Mode | Output Format |
|------|---------------|
| custom | Format-specific paired export behavior when supported by the active writer |
| translated_only | Only the resolved output text (injection chain result) |
| side_by_side | Original\tTranslated columns per line |
| interleaved | Original line, then translated line |
| separate_files | Two files: `_original` and `_translated` |

#### Settings Received from Input (Step 0)

Output inherits these settings from Input to ensure format consistency:
- `source_root` — folder name for display (resolution uses `Original/` directory)
- `file_dir[]` — line-to-file mapping for injection targeting
- Encoding per file (from Input format detection)
- Format per file (for format-aware injection via `formats/` handlers)
- When `OutputFormat.Format` or `OutputFormat.Encoding` is empty, invalid, or still legacy `auto`, Step 0 seeds those settings from the first loaded input file

#### Data Flow

**Inputs**:
- From Manifest: `file_dir[]` (source file mapping from Step 0)
- From Manifest: `lines[]` with all available fields (orig, prepro, tl, edit{N}, tlc{N}, postpro, wordwr, overwrite)
- From Manifest: `DirtyFlags.process`, `DirtyFlags.wordwrap`
- Config: `OutputFormat.*` (destination, format, naming, backup, export options)

**Processing** (via `formats/` handlers + `functions/output.py`):
1. **Check dirty flags** — warn if any are set.
2. **Resolve destination** — `_get_same_as_source_dir()` returns the parent of `Original/` so output subfolders sit next to it.
3. **Map lines to source files** — use `file_dir[]` to group lines by source file.
4. For each source file:
   a. Determine output path based on naming strategy.
   b. **Fresh line reads** — `_get_fresh_lines_for_file()` reads directly from the manifest manager every time (not from cached `step_data["lines"]`), using `resolve_line_field()` per line. This ensures Full Table View edits are immediately reflected without restart.
   c. **INJECTION format** (standardized parser handshake): When format is `injection`, `_write_injection()` executes the 4-step handshake: (0) Load `\Original` via `mgr.resolve_file_path()`, (1) Extract keys via `parser.extract()`, (2) Sequential match — verify each extracted key matches manifest `orig` field; resolve best text via `resolve_line_field()`; mark mismatches as failures preserving original text, (3) Call `parser.inject_to(source, output, translated_lines, orig_lines=orig_lines)`. Reports failures via logger.
   d. **Parser-based surgical injection** (legacy path): Check `filedir[].format` against `ParserRegistry`. When a parser is found, slice per-file lines using `first_idx:last_idx+1` and call `parser.inject_to(source_path, output_path, file_lines)`. Falls back to generic writer on failure.
   e. **Generic format writer (fallback)**: When no parser matches the filedir format, write using format-specific writer (TXT, CSV, TSV, JSON, XLSX) with freshly resolved lines.
   f. Create backup of existing output file if it exists and backup is enabled.
   g. Log success or failure with details.
5. **Export extras** — manifest, logs, glossary if requested.
6. **Update statistics** — files written/failed/skipped, total lines, duration.

**Outputs**:
- Output files with injected translations
- `export_stats: ExportStats` — Files written/failed/skipped, duration
- Failure log entries with file path and error message
- Backup files if enabled
- Manifest/logs/glossary exports if enabled

**Stored In**:
- Manifest step data: `Output.files_written`, `Output.files_failed`, `Output.format`, `Output.destination`
- Manifest step data: `Output.failure_log[]` — Array of `{file, error, timestamp}` entries
- Manifest config: `OutputFormat.Destination`, `OutputFormat.Format`, `OutputFormat.Encoding`, `OutputFormat.PairMode`, `OutputFormat.PreserveFolderStructure`, `OutputFormat.OverwriteExistingFiles`, `OutputFormat.Backup`, `OutputFormat.BackupExtension`

#### Testing Requirements

- Injection priority chain resolution (all levels, with gaps)
- Dirty flag detection and warning display
- Non-destructive default (subfolder naming)
- Input-driven Output defaults and manifest-backed `Same as Source` destination resolution
- Explicit parser selection with auto encoding still honoring parser `detect_encoding()`
- Failure logging with accurate file paths and error messages
- Format-aware injection (TXT, CSV, JSON, RPG Maker, etc.)
- INJECTION format: standardized 4-step parser handshake (load original → extract → sequential match → inject_to)
- Fresh line reads: `_get_fresh_lines_for_file()` always reads from manifest (not stale cache)
- Same as Source resolution: returns parent of `Original/` (translated/ sits next to Original/)
- Standardized `inject_to` handshake with `orig_lines` and failure list return
- Backup strategies (timestamp, numbered, extension)
- Encoding preservation across input → output
- Pair modes (translated_only, side_by_side, interleaved, separate_files)
- Edge cases: empty files, files with no translations, mixed format projects
- Export extras (manifest copy, log export, glossary export)

**Test Files** (to be created/extended):
- `dev/test_output_injection_chain.py`
- `dev/test_output_dirty_flags.py`
- `dev/test_output_naming_strategies.py`
- `dev/test_output_format_handlers.py`
- `dev/test_output_injection.py` ✅ (25 tests — standardized inject_to, LightVN signature, fresh lines, Same as Source, INJECTION format, write injection handshake, build file list, edge cases)

**Implementation Status:** ✅ Phase 47 DONE — All 10 tasks implemented (51 tests passing, 4883 total suite). Phase 79: INJECTION format, stale data fix, Same as Source fix, standardized inject_to handshake (25 additional tests).

---

## 7. CLI Mode: Automatic Pipeline

CLI mode provides fully automated translation without GUI interaction.

### 7.1 Commands

| Command | Purpose |
|---------|---------|
| `translate <path>` | Full pipeline: Pre → Translate → Post |
| `sample <path>` | Quick sample (50 lines) |
| `estimate <path>` | Cost estimation only |
| `config [option] [value]` | View/set configuration |
| `io [option] [value]` | View/set I/O settings |
| `glossary [action]` | Manage translation glossary |
| `local [detect\|check\|setup]` | Local LLM management |
| `languages` | List supported languages |
| `test` | Run diagnostic tests |
| `help` | Show command help |

### 7.2 Translate Command Options

| Option | Short | Description |
|--------|-------|-------------|
| `--source` | `-s` | Source language |
| `--target` | `-t` | Target language |
| `--lines` | `-n` | Limit to first N lines |
| `--yes` | `-y` | Skip confirmation |
| `--interactive` | `-i` | Step-by-step wizard |
| `--model` | | Override model |
| `--temperature` | | Override temperature |
| `--chunk-size` | | Lines per request |
| `--retry-strategy` | | batch/contextual/isolated/skip |
| `--use-cache` | | Enable request caching |
| `--preset` | | Apply API preset |
| `--no-api-key` | | Skip key validation (local LLM) |

### 7.3 Automatic Pipeline Flow

```
python CherryAI.py translate file.txt -s ja -t en
```

1. **Load**: Read input file(s)
2. **Analyze**: Count lines, detect language (silent)
3. **Estimate**: Calculate cost, show to user
4. **Confirm**: Wait for user confirmation (unless -y)
5. **Preprocess**: Apply standard preprocessing
6. **Translate**: Send chunks to API with progress display
7. **Postprocess**: Restore protected content
8. **Output**: Write translated file

### 7.4 Progress Display

```
  [1/1] input.txt
    [████████████████░░░░░░░░░░░░] 53.3% (16/30) Translating: Chunk 16 ETA: 45s
    ✓ Complete in 1m 23s (4,521 tokens)

  ─────────────────────────────────────
  Translation Summary
  ─────────────────────────────────────
  Files:  1/1 successful
  Tokens: 4,521
  Cost:   $0.0045 USD (estimated)
  ─────────────────────────────────────
```

---

## 8. Manifest Structure

The manifest (`.CherryAI.json`) is the single source of truth for project state.

### 8.1 Top-Level Structure

```json
{
  "version": "3.2",
  "glossary": { /* GlossaryConfig */ },
  "source_root": "GameFolder",
  "file_dir": [ /* FileDirEntry[] */ ],
  "lines": [ /* LineEntry[] */ ],
  "operations": [ /* Operation[] */ ],
  "step_state": {
    "Information": {
      "name": "Information",
      "status": "completed",
      "data": {
        "metadata": {
          "project_name": "MyProject",
          "source_language": "Japanese",
          "target_language": "English",
          "genre": "Visual Novel",
          "summary": "...",
          "style_preset": "Natural",
          "custom_style": "",
          "tone_preset": "Neutral",
          "custom_tone": "",
          "custom_notes": ""
        }
      }
    }
  },
  "created_at": "2026-01-31T12:00:00Z",
  "updated_at": "2026-01-31T14:30:00Z"
}
```

**Note:** `project_info` and `project_name` are no longer top-level keys.
All project metadata lives in `step_state.Information.data.metadata`.
The `ManifestManager.get_info_metadata()` / `set_info_metadata_field()` helpers
provide the canonical read/write API.

### 8.2 LineEntry Structure

```json
{
  "idx": 0,
  "orig": "Original Japanese text",
  "prepro": "Preprocessed text with __PROTECTED__",
  "prepro_ops": [{"type": "protect", "original": "\\V[1]", "pos": 15}],
  "tl": "Translated English text",
  "postpro": "Restored translated text with \\V[1]",
  "wordwr": "Word-wrapped\ntext",
  "overwrite": null,
  "qa_overwrite": null
}
```

### 8.3 Field Progression

```
orig → prepro → edited_prepro → tl → tlc1 → edit1 → tlc2 → ... → postpro → wordwr → qa_overwrite
```

Each step writes its output field via `ManifestManager.set_line_field(idx, field, value)`:
- Step 3 `_update_step_data()` writes `prepro`
- Step 5 `update_translation()` writes `tl` (and `edited_prepro`)
- Step 6 `_on_postprocess_complete()` / `_mark_line_as_fixed()` writes `postpro`
- Step 7 `_save_to_session()` writes `wordwr`
- Step 7 `on_leave()` writes `qa` and `qa_overwrite`
- Step 8 `_save_to_session()` writes `wordwr`

**All steps now read from manifest** using `manifest_fields.py` shared resolution functions
instead of session step_data. The priority chain is:
`wordwr → qa_overwrite → qa → postpro → tl → prepro → orig`

Resolution methods:
- `resolve_line_field(line_entry, *fields)`: Returns first non-empty field from ordered priority chain
- `resolve_line_field_from(line_entry, start_field)`: Resolves starting from a specific field in PIPELINE_FIELDS
- `get_latest_line_text(line_entry)`: Returns the most recent non-empty text from the full chain
- `get_all_lines_resolved(mgr, field?)`: Returns list of resolved texts for all lines (optional start field)
- `get_input_for_translation()`: edited_prepro → prepro → orig
- `get_input_for_tlc(N)`: edit{N-1} → tlc{N-1} → ... → tl
- `get_input_for_postprocessing()`: tl → prepro → orig
- `get_final_output()`: wordwr → qa_overwrite → qa → overwrite → postpro

### 8.4 Options Structure (Phase 58/59 Additions)

```json
{
  "Options": {
    "AutoPipeline": {
      "level": 3,
      "level_name": "Preprocess",
      "auto_inference": true,
      "infer_speakers_to_glossary": true,
      "infer_codes_to_database": true,
      "infer_pov": true,
      "infer_gender": false
    },
    "PROT": {
      "enabled": true,
      "patterns": [
        {"pattern": "\\\\V\\[\\d+\\]", "type": "regex", "source": "analysis"},
        {"pattern": "<<n>>", "type": "literal", "source": "user"}
      ]
    }
  }
}
```

**AutoPipeline Fields** (Phase 58):
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | int | 3 | Pipeline automation level (0-4) |
| `level_name` | string | "Preprocess" | Human-readable level name |
| `auto_inference` | bool | true | Master toggle for inference population |
| `infer_speakers_to_glossary` | bool | true | Add detected speakers to Glossary |
| `infer_codes_to_database` | bool | true | Add detected code patterns to Code Database |
| `infer_pov` | bool | true | Detect Point of View for prompt context |
| `infer_gender` | bool | false | Use LLM to infer character gender |

**PROTECTED Patterns Structure**:
| Field | Type | Description |
|-------|------|-------------|
| `pattern` | string | Regex or literal pattern to protect |
| `type` | string | "regex" or "literal" |
| `source` | string | "analysis" (from Step 1) or "user" (manually added) |

### 8.5 Analysis Structure (Phase 59 Additions)

```json
{
  "Analysis": {
    "total_lines": 5000,
    "empty_lines": 150,
    "unique_lines": 4200,
    "duplicate_count": 800,
    "aggressive_dedup_projection": 3800,
    "dominant_language": "Japanese",
    "threshold_applied": true,
    "chinese_percentage": 0.12,
    "japanese_lines": 4200,
    "chinese_only_lines": 550,
    "korean_lines": 0,
    "total_cjk_lines": 4750,
    "speakers": {
      "アリス": 120,
      "ボブ": 85,
      "??": 45
    },
    "code_patterns": {
      "\\\\V[N]": 230,
      "<<n>>": 180,
      "<color>": 95
    }
  }
}
```

**Analysis Fields** (Phase 59 Additions):
| Field | Type | Description |
|-------|------|-------------|
| `aggressive_dedup_projection` | int | Projected line count after aggressive deduplication |
| `dominant_language` | string | Project-level detected language ("Japanese", "Chinese", "Korean", "Unknown") |
| `threshold_applied` | bool | Whether Chinese-only lines were reclassified as Japanese due to threshold |
| `chinese_percentage` | float | Percentage of Chinese-only lines (no kana) among all CJK lines |
| `japanese_lines` | int | Lines containing hiragana or katakana (definitively Japanese) |
| `chinese_only_lines` | int | Lines with CJK characters but no kana (ambiguous, may be Japanese kanji-heavy) |
| `korean_lines` | int | Lines containing only Korean Hangul |
| `total_cjk_lines` | int | Sum of japanese_lines + chinese_only_lines (excludes Korean) |

**Threshold Logic**:
- If `chinese_only_lines / total_cjk_lines < 0.30`, the project is classified as Japanese
- `threshold_applied` is `true` only when there were some `chinese_only_lines` that got reclassified
- Korean lines are not included in the threshold calculation — they are separate

### 8.6 Step State Structure (Input Step)

```json
{
  "step_state": {
    "Input": {
      "file_count": 15,
      "total_lines": 5000,
      "formats": ["json", "txt"],
      "last_import": {
        "source_manifest": "C:/path/to/other.CherryAI.json",
        "lines_matched": 4200,
        "lines_total": 5000,
        "timestamp": "2026-02-15T10:30:00Z"
      },
      "pipeline_executed": {
        "level": 3,
        "steps_completed": [1, 2, 3, 4, 5, 6, 7, 8],
        "steps_skipped": [],
        "execution_time_ms": 12500,
        "timestamp": "2026-02-15T10:30:00Z"
      }
    }
  }
}
```

**Pipeline Execution Record**:
| Field | Type | Description |
|-------|------|-------------|
| `level` | int | AutoPipeline level that was executed |
| `steps_completed` | int[] | Pipeline steps that completed successfully |
| `steps_skipped` | int[] | Pipeline steps that were skipped |
| `execution_time_ms` | int | Total pipeline execution time |
| `timestamp` | string | ISO 8601 timestamp of execution |

### 8.7 CodeGlossary Structure

```json
{
  "CodeGlossary": [
    {
      "pattern": "\\\\V[\\d+]",
      "type": "regex",
      "action": "Preserve",
      "description": "RPG Maker variable",
      "source": "analysis"
    },
    {
      "pattern": "<<n>>",
      "type": "literal",
      "action": "Remove",
      "description": "Newline marker",
      "source": "user"
    }
  ]
}
```

**CodeGlossary Entry Fields**:
| Field | Type | Description |
|-------|------|-------------|
| `pattern` | string | Code pattern to match |
| `type` | string | "regex" or "literal" |
| `action` | string | "Preserve", "Transform", "Remove", or "Replace" |
| `description` | string | User-facing description |
| `source` | string | "analysis" (from Step 1 right-click) or "user" (manually added) |

---

## 9. Processing Modules Reference

### 9.1 functions/ Modules

| Module | Purpose |
|--------|---------|
| `mainhelper.py` | Processor class, LineEntry, Manifest |
| `api_client.py` | LLM API communication |
| `chunker.py` | Text chunking with token awareness |
| `dedup.py` | Duplicate line handling |
| `glossary.py` | Translation glossary management |
| `analysis.py` | Text analysis and statistics |
| `validation.py` | QA validation rules |
| `postprocess.py` | Placeholder restoration |
| `wordwrap.py` | Line wrapping algorithms |
| `CLI.py` | Command-line interface |
| `config.py` | Configuration loading |
| `rate_limiter.py` | API rate limiting (sliding window) |
| `header_rate_limiter.py` | Header-based rate limiting (per-model, response-header driven) |
| `request_cache.py` | Request caching |
| `prompt_builder.py` | Translation prompt construction |
| `manifest_manager.py` | Unified state management |

### 9.2 modi/ Modules (Pre/Post Processing)

| Module | Purpose |
|--------|---------|
| `standard_mode.py` | Ellipsis, symbols, PROTECTED compression |
| `protect_code.py` | Code pattern protection |
| `custom_placeholder.py` | Custom pattern→token replacement |
| `temporary_replacement.py` | Temp replacement with restore |
| `anchor_equivalence.py` | Anchor pattern handling |
| `speaker_replacement.py` | Speaker name handling |

### 9.3 formats/ Modules (File I/O)

| Module | Purpose |
|--------|---------|
| `txt.py` | Plain text files |
| `csv_handler.py` | CSV/TSV files |
| `json_handler.py` | JSON files |
| `xlsx.py` | Excel files |
| `rpgmaker.py` | RPG Maker data (placeholder) |

### 9.4 gui/helpers/ Modules (Adapters)

| Module | Purpose |
|--------|---------|
| `mode_adapter.py` | Bridge GUI → modi/ modules |
| `analysis_adapter.py` | Bridge GUI → analysis functions |
| `chunker_adapter.py` | Bridge GUI → chunker functions |
| `glossary_adapter.py` | Bridge GUI → glossary functions |
| `prompt_adapter.py` | Bridge GUI → prompt builder |
| `manifest_binding.py` | Widget ↔ manifest field binding |

---

## 10. Pipeline Logging System

**Implementation Status:** ✅ Phase 48 DONE — All 9 tasks implemented (52 tests passing, 4890 total suite)

CherryAI maintains per-project, per-step log files that record the outcome of every processing step in the pipeline. Logs are the audit trail: they capture what happened, what went wrong, what was recovered, and how long it took. The manifest remains the single source of truth for data; logs are the single source of truth for *process history*.

For the GUI API Log window, structured API log entries are stored in full and rendered through a viewer-only display limit. The default viewer setting is `All`, with optional per-block limits of `1000`, `2500`, `5000`, or `Nothing` lines.

### 10.1 Design Principles

1. **Manifest is Data, Logs are History**: The manifest stores line fields (`tl`, `postpro`, `wordwr`, `overwrite`) and step data (counts, flags, options). Logs store chronological event records — what was attempted, what succeeded, what failed, and why. Logs never duplicate manifest data; they reference it by line index.
2. **Per-Project, Per-Step**: Each log file is scoped to one project and one pipeline step. Log files live alongside the manifest.
3. **Archival on Re-run**: When a step is re-run, the existing log is archived (renamed with timestamp) and a fresh log is started. This preserves full history without cluttering the active log.
4. **Unified Status Vocabulary**: All logs use the same status vocabulary (see §9.3) so that cross-step analysis is consistent.
5. **Utility Metrics Always Present**: Every log entry and summary includes time taken and token counts where applicable.
6. **Existing Functions First**: The logging system builds on existing infrastructure in `functions/mainhelper.py` (`setup_logger`, `write_failure_report`), `functions/api_client.py` (`write_log_header`, `write_log_footer`, `_log_api_call`, `_update_log_summary`), and `functions/common_errors.py` (`ErrorCollector`). New code extends these — it does not replace them.
7. **Succintness**: Logs must not log every success. Only the translation.log is supposed to log every request with response. Any other optimally only logs 'Success' and any utility information like timestamp and time taken. 

### 10.2 Log File Specifications

All log files are plain UTF-8 text. They follow a common structure: **Header → Per-Line/Per-Chunk Entries → Summary Footer**.

#### 9.2.1 Log File Location & Naming

| Item | Value |
|------|-------|
| Directory | Same directory as the project manifest (`.CherryAI.json`) |
| Naming | `{project_name}.{step}.log` |
| Archive Naming | `{project_name}.{step}.{YYYYMMDD_HHMMSS}.log` |
| Encoding | UTF-8 (no BOM) |

**Examples**:
- `MyGame.translation.log` — active translation log
- `MyGame.postprocess.log` — active postprocessing log
- `MyGame.wordwrap.log` — active wordwrap log
- `MyGame.output.log` — active output log
- `MyGame.translation.20260208_143022.log` — archived translation log from Feb 8, 2026 at 14:30:22

#### 9.2.2 translation.log (Step 5: Translation)

**Purpose**: Record every translation chunk request, its result, any retries, and per-line outcomes.

**Header** (written once at start of translation run):
```
============================================================
 CherryAI Translation Log
 Project: {project_name}
 Started: {ISO 8601 timestamp}
 Model: {model_name}
 Provider: {provider_name}
 Lines/Chunk: {chunk_size}
 Total Lines: {total_lines}
 Retry Strategy: {strategy}
 Max Retries: {max_retries}
============================================================
```

**Per-Chunk Entry**:
```
--- Chunk {N}/{total} | Lines {start_idx}-{end_idx} ---
  Status: {PASS | RECOVERED: {type} | (PARTIAL) RETRIAL {type} | (PARTIAL) FAILURE {type}}
  Input Tokens: {count}
  Output Tokens: {count}
  Time: {seconds}s
  Cache Hits: {count}
  Lines:
    [{idx}] {status} {detail}
    [{idx}] {status} {detail}
    ...
```

**Per-Line Status Values** (within chunk):
| Status | Meaning |
|--------|---------|
| `OK` | Line translated successfully on first attempt |
| `CACHED` | Line served from cache, no API call |
| `SKIPPED` | Line skipped (dedup, empty, wrong language, already translated) |
| `RECOVERED` | Line failed initial validation but was auto-fixed |
| `RETRIED:{strategy}` | Line required retry (strategy: BATCH, CONTEXTUAL, ISOLATED) |
| `FAILED` | Line exhausted all retry attempts |

**Summary Footer** (written once at end of translation run):
```
============================================================
 Translation Summary
 Completed: {ISO 8601 timestamp}
 Duration: {total_time}
 Total Lines: {total} | Translated: {count} | Cached: {count} | Skipped: {count} | Failed: {count}
 Total Tokens: {input + output} (Input: {input}, Output: {output})
 Tokens Saved (Cache): {saved_count}
 Tokens Saved (Dedup): {dedup_saved_count}
 Cost: ${cost} USD
 Retries: {retry_count} (Recovered: {recovered_count})
============================================================
```

**Existing Functions** (to extend, not replace):
| Function | Module | Current Role | Extension |
|----------|--------|-------------|-----------|
| `write_log_header()` | `api_client.py` | Writes API log header | Adapt format to match spec header above |
| `write_log_footer()` | `api_client.py` | Writes API log summary | Add token-saved and retry metrics |
| `_log_api_call()` | `api_client.py` | Logs individual API calls | Add per-line status detail |
| `_update_log_summary()` | `api_client.py` | Updates running totals | Add cache/dedup savings tracking |
| `_format_system_prompt_for_log()` | `api_client.py` | Formats prompt for log | No change needed |
| `_format_lines_for_log()` | `api_client.py` | Formats input lines | No change needed |
| `_format_translations_for_log()` | `api_client.py` | Formats output lines | Add status annotation per line |
| `get_api_log()` | `api_client.py` | Returns log path | Update to return step-specific path |

**Retry Functions** (log their outcomes into translation.log):
| Function | Module | What It Logs |
|----------|--------|-------------|
| `RetryHandler.handle_failed_lines()` | `retry_handler.py` | Entry point — logs which strategy was selected |
| `RetryHandler._retry_batch()` | `retry_handler.py` | Logs batch retry attempt and result |
| `RetryHandler._retry_contextual()` | `retry_handler.py` | Logs contextual retry with context window |
| `RetryHandler._retry_isolated()` | `retry_handler.py` | Logs per-line isolated retry |
| `RetryHandler._retry_skip()` | `retry_handler.py` | Logs skipped lines |
| `RetryHandler.should_continue_retrying()` | `retry_handler.py` | Logs retry exhaustion decision |
| `RetryHandler.get_exhausted_lines()` | `retry_handler.py` | Logs final exhausted line list |

**Validation Functions** (called during translation, log to translation.log):
| Function | Module | What It Logs |
|----------|--------|-------------|
| `validate_line_pre()` | `validation.py` | Pre-translation validation issues |
| `validate_line_post()` | `validation.py` | Post-translation validation issues |
| `validate_batch_post()` | `validation.py` | Batch-level validation summary |
| `validate_batch_comprehensive()` | `validation.py` | Comprehensive validation findings |
| `detect_repetition()` | `validation.py` | Repetition detection flags |
| `apply_autofix()` | `validation.py` | Auto-fix applications |

**Chunk Optimization** (logs adjustment decisions):
| Function | Module | What It Logs |
|----------|--------|-------------|
| `ChunkOptimizer.record_batch()` | `chunk_optimizer.py` | Batch result recording |
| `ChunkOptimizer.record_error()` | `chunk_optimizer.py` | Error type and rate |
| `ChunkOptimizer._check_adjustment()` | `chunk_optimizer.py` | Chunk size adjustment decisions |
| `ChunkOptimizer._reduce_chunk_size()` | `chunk_optimizer.py` | Chunk size reduction events |

#### 9.2.3 postprocess.log (Step 7: Postprocessing)

**Purpose**: Record every postprocessing operation, recovery attempt, and failure for each line.

**Header**:
```
============================================================
 CherryAI Postprocessing Log
 Project: {project_name}
 Started: {ISO 8601 timestamp}
 Total Lines: {total_lines}
 Failure Policy: {write | flag}
 Recovery Options: Bracket={on|off}, Quote={on|off}, Whitespace={on|off}
 Symbol Conversion: {direction | off}
============================================================
```

**Per-Line Entry**:
```
--- Line {idx} ---
  Status: {PASS | RECOVERED: {type} | (PARTIAL) RETRIAL {type} | (PARTIAL) FAILURE {type}}
  Input: "{truncated_input}"
  Output: "{truncated_output}"
  Operations:
    [{priority}] {process_name}: {result}
    [{priority}] {process_name}: {result}
  Recovery: {count} operations applied
  Time: {ms}ms
```

**Per-Operation Result Values**:
| Result | Meaning |
|--------|---------|
| `OK` | Restoration/recovery succeeded without issues |
| `RECOVERED: {RecoveryType}` | Issue found and automatically fixed |
| `SKIPPED` | Process not applicable to this line |
| `FAILED: {reason}` | Process failed, line handled per FailurePolicy |

**RecoveryType Values** (from `postprocess.py` `RecoveryType` enum):
| Type | Description |
|------|-------------|
| `PLACEHOLDER_CASE` | Fixed placeholder case mismatch |
| `MANGLED_PLACEHOLDER` | Recovered mangled/split placeholder token |
| `MISSING_PLACEHOLDER` | Recovered missing placeholder from original |
| `PLACEHOLDER_WHITESPACE` | Normalized placeholder whitespace |
| `BRACKET_BALANCE` | Fixed unmatched brackets |
| `QUOTE_BALANCE` | Fixed unmatched quotes |
| `SPEAKER_FORMAT` | Restored speaker format |
| `BR_TAG` | Recovered `<br>` tags |
| `CODE_PATTERN` | Recovered code pattern via postanalysis |
| `WHITESPACE` | Normalized whitespace/indentation |

**Summary Footer**:
```
============================================================
 Postprocessing Summary
 Completed: {ISO 8601 timestamp}
 Duration: {total_time}
 Total Lines: {total} | Changed: {count} | Unchanged: {count} | Written: {count} | Flagged: {count}
 Recovery Operations: {total_ops} (Success: {success}, Failed: {failed})
 Recovery Rate: {rate}%
 By Type:
   Placeholder Case: {count}
   Mangled Placeholder: {count}
   Missing Placeholder: {count}
   Bracket Balance: {count}
   Quote Balance: {count}
   Speaker Format: {count}
   BR Tag: {count}
   Code Pattern: {count}
   Whitespace: {count}
============================================================
```

**Existing Functions** (to extend):
| Function | Module | Current Role | Extension |
|----------|--------|-------------|-----------|
| `recover_line()` | `postprocess.py` | Master recovery for single line | Add log emission per operation |
| `recover_batch()` | `postprocess.py` | Batch recovery orchestrator | Add header/footer log writes |
| `PostProcessManager.run()` | `postprocess.py` | Full postprocessing pipeline | Wire log file creation and archival |
| `recover_placeholder_case()` | `postprocess.py` | Fix case mismatches | Log recovery type + detail |
| `recover_mangled_placeholders()` | `postprocess.py` | Fix split/mangled tokens | Log recovery type + detail |
| `recover_missing_placeholders()` | `postprocess.py` | Restore missing placeholders | Log recovery type + detail |
| `normalize_placeholder_whitespace()` | `postprocess.py` | Fix placeholder spacing | Log recovery type + detail |
| `check_bracket_balance()` | `postprocess.py` | Detect bracket issues | Log detection result |
| `recover_bracket_balance()` | `postprocess.py` | Fix bracket issues | Log recovery type + detail |
| `check_quote_balance()` | `postprocess.py` | Detect quote issues | Log detection result |
| `recover_quote_balance()` | `postprocess.py` | Fix quote issues | Log recovery type + detail |
| `compare_manifest_and_final()` | `postanalysis.py` | Post-analysis comparison | Log comparison findings |
| `_try_code_recover()` | `postanalysis.py` | Attempt code recovery | Log recovery attempt |
| `_try_speaker_fix()` | `postanalysis.py` | Attempt speaker fix | Log recovery attempt |
| `_try_br_recovery()` | `postanalysis.py` | Attempt BR tag recovery | Log recovery attempt |

**GUI Step Functions** (orchestrate logging):
| Function | Module | Current Role | Extension |
|----------|--------|-------------|-----------|
| `_do_postprocessing()` | `gui/steps/postprocess.py` | Main postprocessing entry | Create log, write header, call processing, write footer |
| `_basic_postprocess()` | `gui/steps/postprocess.py` | Basic postprocess path | Log each line result |
| `_run_character_validation()` | `gui/steps/postprocess.py` | Character validation | Log validation findings |
| `_apply_character_autofix()` | `gui/steps/postprocess.py` | Apply autofix rules | Log autofix applications |
| `FailurePolicy` | `gui/steps/postprocess.py` | Enum for failure handling | Used in log status determination |

#### 9.2.4 wordwrap.log (Step 8: Wordwrap)

**Purpose**: Record wrapping operations, exceeding-line flags, and overwrite generation.

**Header**:
```
============================================================
 CherryAI Wordwrap Log
 Project: {project_name}
 Started: {ISO 8601 timestamp}
 Total Lines: {total_lines}
 Mode: {Manual | parser_name}
 Width: {value} {characters | pixels}
 Break Character: {repr}
 Max Lines: {value | unlimited}
 Speaker Handling: {Ignore | Count}
============================================================
```

**Per-Line Entry** (only for lines with changes or issues):
```
--- Line {idx} ---
  Status: {PASS | RECOVERED: {type} | (PARTIAL) FAILURE {type}}
  Wrapped Lines: {count}
  Exceeding: {yes | no}
  Overwrite Differs: {yes | no}
  Break Positions: [{pos1}, {pos2}, ...]
  Time: {ms}ms
```

**Summary Footer**:
```
============================================================
 Wordwrap Summary
 Completed: {ISO 8601 timestamp}
 Duration: {total_time}
 Total Lines: {total} | Changed: {count} | Unchanged: {count} | Exceeding: {count}
 Overwrite Differs: {count}
 Total Breaks Inserted: {count}
============================================================
```

**Existing Functions** (to extend):
| Function | Module | Current Role | Extension |
|----------|--------|-------------|-----------|
| `pretty_wrap()` | `wordwrap.py` | Core wrapping algorithm | Return metadata for logging |
| `apply_wordwrap()` | `wordwrap.py` | Batch wrapping | Add header/footer log writes |
| `_on_wrap_error()` | `gui/steps/wordwrap_overwrite.py` | Error handler | Log error with line detail |

#### 9.2.5 output.log (Step 9: Output)

**Purpose**: Record every file export attempt, injection source per line, and any write failures.

**Header**:
```
============================================================
 CherryAI Output Log
 Project: {project_name}
 Started: {ISO 8601 timestamp}
 Total Files: {total_files}
 Total Lines: {total_lines}
 Destination: {destination_path}
 Naming Strategy: {subfolder | suffix | prefix | replace}
 Format: {auto | txt | csv | json | xlsx}
 Backup: {timestamp | numbered | extension | none}
 Dirty Flags: Process={✓|⚠}, Wordwrap={✓|⚠}
============================================================
```

**Per-File Entry**:
```
--- File {N}/{total}: {filename} ---
  Status: {PASS | (PARTIAL) FAILURE {type}}
  Source: {source_path}
  Output: {output_path}
  Lines: {count}
  Injection Sources:
    overwrite: {count}
    wordwr: {count}
    postpro: {count}
    edit{N}: {count}
    tlc{N}: {count}
    tl: {count}
    preedit: {count}
    prepro: {count}
    orig: {count}
  Time: {seconds}s
  Errors: {count}
    [{line_idx}] {error_detail}
```

**Summary Footer**:
```
============================================================
 Output Summary
 Completed: {ISO 8601 timestamp}
 Duration: {total_time}
 Files: {total} | Written: {count} | Failed: {count} | Skipped: {count}
 Lines Injected: {count}
 Injection Source Breakdown:
   overwrite: {count} | wordwr: {count} | postpro: {count}
   edit: {count} | tlc: {count} | tl: {count}
   preedit: {count} | prepro: {count} | orig: {count}
 Extras Exported: {manifest: yes|no, logs: yes|no, glossary: yes|no}
============================================================
```

**Existing Functions** (to extend):
| Function | Module | Current Role | Extension |
|----------|--------|-------------|-----------|
| `_export_logs()` | `gui/steps/output_inject.py` | Export log files | Bundle all step logs into export |
| `_on_export_error()` | `gui/steps/output_inject.py` | Export error handler | Log error to output.log |
| `get_final_output()` | `functions/output.py` (new, Task 47.4) | Resolve injection priority | Return source_field for log tracking |
| `write_failure_report()` | `mainhelper.py` | Write failure report | Adapt to output.log format |

### 10.3 Log Status Definitions

All log entries use a unified status vocabulary. Status is determined at two levels: **per-line** (individual line outcome) and **per-step** (aggregate step outcome derived from line statuses).

#### Per-Line Status

| Status | Format | Meaning |
|--------|--------|---------|
| **PASS** | `PASS` | Line processed successfully with no issues |
| **RECOVERED** | `RECOVERED: {RecoveryType}` | Issue detected and automatically resolved. `{RecoveryType}` specifies what was fixed (e.g., `BRACKET_BALANCE`, `MISSING_PLACEHOLDER`, `MANGLED_PLACEHOLDER`) |
| **PARTIAL RETRIAL** | `(PARTIAL) RETRIAL {RetryStrategy}` | Line required retrying with the specified strategy. "(PARTIAL)" indicates the line was not fully resolved on first attempt. Applies only to Translation step |
| **PARTIAL FAILURE** | `(PARTIAL) FAILURE {FailureType}` | Line could not be fully processed. Some operations may have succeeded but the final result is incomplete. `{FailureType}` specifies what failed |
| **FAILURE** | `FAILURE {FailureType}` | Line processing failed entirely. No usable output was produced |

#### Per-Step Status (Summary)

The step-level status is derived from the worst per-line status:

| Step Status | Condition |
|-------------|-----------|
| `PASS` | All lines are PASS |
| `RECOVERED` | Some lines RECOVERED, none worse |
| `PARTIAL` | Some lines had PARTIAL RETRIAL or PARTIAL FAILURE |
| `FAILURE` | Any line has FAILURE status |

#### RecoveryType Reference

| RecoveryType | Applicable Steps | Description |
|-------------|-----------------|-------------|
| `PLACEHOLDER_CASE` | Translation, Postprocessing | Placeholder token case corrected (e.g., `__PROTECTED__` → `__PROTECTED__`) |
| `MANGLED_PLACEHOLDER` | Translation, Postprocessing | Split or corrupted placeholder token reconstructed |
| `MISSING_PLACEHOLDER` | Translation, Postprocessing | Placeholder missing from output, recovered from original |
| `PLACEHOLDER_WHITESPACE` | Postprocessing | Errant spaces in placeholder token normalized |
| `BRACKET_BALANCE` | Postprocessing | Missing/extra brackets fixed using original as reference |
| `QUOTE_BALANCE` | Postprocessing | Missing/extra quotes fixed |
| `SPEAKER_FORMAT` | Postprocessing | Speaker `Name: "Dialogue"` format restored |
| `BR_TAG` | Postprocessing | `<br>` tags recovered |
| `CODE_PATTERN` | Postprocessing | Code pattern recovered via postanalysis comparison |
| `WHITESPACE` | Postprocessing | Indentation/spacing normalized to match original |
| `LINE_COUNT_MISMATCH` | Translation | API returned wrong number of lines, remapped |
| `JSON_PARSE` | Translation | API response JSON repaired |
| `CONTENT_WARNING` | Translation | Content warning detected and handled |

#### RetryStrategy Reference

| Strategy | When Used | Description |
|----------|-----------|-------------|
| `BATCH` | Default | Re-send entire failed chunk |
| `CONTEXTUAL` | Context-dependent failures | Re-send failed lines with surrounding context |
| `ISOLATED` | Stubborn failures (hidden) | Retry each line individually |
| `SKIP` | Give up (hidden) | Mark as Skipped, move on |

#### FailureType Reference

| FailureType | Applicable Steps | Description |
|-------------|-----------------|-------------|
| `TRANSLATION_EXHAUSTED` | Translation | All retry attempts exhausted |
| `API_ERROR` | Translation | API returned error (rate limit, auth, server) |
| `VALIDATION_FAILED` | Translation, QA | Line failed validation after all recovery |
| `RECOVERY_FAILED` | Postprocessing | Recovery operation could not fix the issue |
| `PLACEHOLDER_LOST` | Postprocessing | Placeholder could not be recovered from any source |
| `BRACKET_UNRECOVERABLE` | Postprocessing | Bracket balance could not be restored (no anchor) |
| `QUOTE_UNRECOVERABLE` | Postprocessing | Quote balance could not be restored |
| `WRAP_OVERFLOW` | Wordwrap | Line exceeds Max Lines after wrapping |
| `WRITE_ERROR` | Output | File write failed (permission, disk, path) |
| `FORMAT_ERROR` | Output | Format handler could not inject into target file |
| `INJECTION_MISMATCH` | Output | Line count mismatch between manifest and source file |

### 10.4 Utility Metrics Tracking

Every log captures process-level utility metrics. These are written in both per-entry and summary sections.

| Metric | Steps | Description | Source |
|--------|-------|-------------|--------|
| **Time Taken** | All | Wall-clock duration per entry and total | `time.perf_counter()` delta |
| **Input Tokens** | Translation | Tokens sent to LLM | API response usage field |
| **Output Tokens** | Translation | Tokens received from LLM | API response usage field |
| **Tokens Saved (Cache)** | Translation | Tokens not sent due to cache hits | Cache hit count × avg tokens/line |
| **Tokens Saved (Dedup)** | Translation | Tokens not sent due to deduplication | Dedup skip count × avg tokens/line |
| **Cost** | Translation | Dollar cost of API calls | Model pricing × token counts |
| **Recovery Operations** | Postprocessing | Count of recovery ops applied | RecoveryStats from postprocess.py |
| **Recovery Rate** | Postprocessing | Success rate of recovery attempts | `recovered / (recovered + failed) × 100` |
| **Breaks Inserted** | Wordwrap | Total line break characters inserted | Wrapping metadata |
| **Files Written** | Output | Count of successfully written files | Export loop counter |

**Manifest Storage**: Utility metrics are also persisted in manifest step data for later reference:
- `Translation.tokens_used`, `Translation.tokens_saved_cache`, `Translation.tokens_saved_dedup`, `Translation.cost_actual`, `Translation.duration`
- `Postprocessing.recovery_rate`, `Postprocessing.total_ops`, `Postprocessing.duration`
- `Wordwrap.breaks_inserted`, `Wordwrap.lines_exceeding`, `Wordwrap.duration`
- `Output.files_written`, `Output.files_failed`, `Output.duration`

### 10.5 Log Archival & Lifecycle

| Event | Action |
|-------|--------|
| Step re-run | Active log renamed to `{project}.{step}.{timestamp}.log`, fresh log created |
| Project load | Active logs remain; displayed in Output step's "Export Logs" option |
| Export Logs (Step 9) | All logs (active + archived) in the project directory are bundled into the export |
| Manual cleanup | User may delete archived logs at will; active logs are regenerated on next run |

**Archival Implementation**:
1. Before writing a new log header, check if `{project}.{step}.log` exists
2. If it exists, rename to `{project}.{step}.{YYYYMMDD_HHMMSS}.log` using the log's own creation timestamp
3. Create a fresh `{project}.{step}.log` and write the new header
4. This is handled by a shared `_rotate_log()` utility in `functions/mainhelper.py`

**Existing Function to Extend**:
| Function | Module | Extension |
|----------|--------|-----------|
| `setup_logger()` | `mainhelper.py` | Add `_rotate_log()` call before logger creation |
| `write_failure_report()` | `mainhelper.py` | Route failure reports to the appropriate step log |

### 10.6 Manifest Integration

Logs are about process history; the manifest is about data state. They complement each other:

| Concern | Manifest | Log |
|---------|----------|-----|
| Line text fields | `lines[].tl`, `lines[].postpro`, etc. | Referenced by index, not stored |
| Step data / totals | `Translation.tokens_used`, `Postprocessing.recovery_rate`, etc. | Duplicated in summary footer for standalone readability |
| Per-line status | Not stored (derived from field presence) | Explicitly recorded per entry |
| Failure details | `Output.failure_log[]` (file-level only) | Full detail per line per step |
| Options / settings | All step options in manifest | Echoed in log header for context |
| Recovery type breakdown | `Postprocessing.recovery_stats` (summary only) | Per-line per-operation detail |

**Key Rule**: The manifest is always written first (crash resilience). Log writes are best-effort — a log write failure must never block or interrupt processing. Logs are wrapped in `try/except` at every write point.

### 10.7 Recovery & Failure Functions Catalog

This catalog lists every existing function that participates in recovery, validation, retry, or failure handling, organized by pipeline step. These functions produce the log entries described above and are the implementation backbone of the logging system.

#### 9.7.1 Translation Step Functions

**API Client** (`functions/api_client.py`):
| Function | Purpose |
|----------|---------|
| `_translate_chunk_with_retry()` | Orchestrates chunk translation with retry loop |
| `check_content_warning()` | Detects and handles API content warnings |
| `write_log_header()` | Writes session log header |
| `write_log_footer()` | Writes session log summary |
| `_log_api_call()` | Logs individual API request/response |
| `_update_log_summary()` | Updates running summary statistics |
| `_format_system_prompt_for_log()` | Formats system prompt for readable log output |
| `_format_lines_for_log()` | Formats input lines for log |
| `_format_translations_for_log()` | Formats translation output for log |
| `get_api_log()` | Returns path to current API log file |

**Retry Handler** (`functions/retry_handler.py`):
| Function / Class | Purpose |
|------------------|---------|
| `RetryStrategy` (enum) | BATCH, CONTEXTUAL, ISOLATED, SKIP |
| `RetryConfig` | Max retries, delay, strategy configuration |
| `RetryResult` | Per-line retry outcome |
| `BatchRetryResult` | Aggregate retry outcome for a batch |
| `RetryHandler.handle_failed_lines()` | Entry point for retry logic |
| `RetryHandler._retry_batch()` | Batch retry implementation |
| `RetryHandler._retry_contextual()` | Contextual retry with surrounding lines |
| `RetryHandler._retry_isolated()` | Per-line isolated retry |
| `RetryHandler._retry_skip()` | Skip strategy (mark as skipped) |
| `RetryHandler.should_continue_retrying()` | Decides if more retries are warranted |
| `RetryHandler.get_exhausted_lines()` | Returns lines that exhausted all retries |

**Chunk Optimizer** (`functions/chunk_optimizer.py`):
| Function / Class | Purpose |
|------------------|---------|
| `ErrorType` (enum) | Categorizes chunk errors |
| `ChunkOptimizer.record_batch()` | Records batch outcome |
| `ChunkOptimizer.record_success()` | Records successful chunk |
| `ChunkOptimizer.record_error()` | Records chunk error with type |
| `ChunkOptimizer._check_adjustment()` | Evaluates whether chunk size should change |
| `ChunkOptimizer._reduce_chunk_size()` | Reduces chunk size after errors |
| `ChunkOptimizer.get_error_rate()` | Returns current error rate |
| `ChunkOptimizer.get_success_rate()` | Returns current success rate |

**Rate Limiter** (`functions/rate_limiter.py`):
| Function | Purpose |
|----------|---------|
| `RateLimiter.wait_if_needed()` | Enforces RPM limits, logs wait events |
| `RateLimiter.record_request()` | Tracks request timing |

**Header-Based Rate Limiter** (`functions/header_rate_limiter.py`):
| Function / Class | Purpose |
|------------------|---------|
| `ProviderRateLimitConfig` | Configurable header names per provider |
| `ModelWindowState` | Per-model runtime counters and reset timers |
| `HeaderBasedRateLimiter` | Thread-safe, per-model enforcement using monotonic timer |
| `HeaderBasedRateLimiter.pre_request()` | Block until capacity available; increments counters |
| `HeaderBasedRateLimiter.update_from_headers()` | Read reset timing from response headers |
| `HeaderBasedRateLimiter.set_model_limits()` | Set RPM/TPM limits for a model |
| `HeaderBasedRateLimiter.get_stats()` | Return current counters and limits |
| `parse_reset_duration()` | Parse OpenAI duration strings ("6m0s", "1s", "200ms") |
| `OPENAI_RATE_LIMIT_CONFIG` | Pre-built config for OpenAI headers |

#### 9.7.2 Validation Functions

**Validation** (`functions/validation.py`):
| Function / Class | Purpose |
|------------------|---------|
| `SkipReason` (enum) | Why a line was skipped (EMPTY, COMMENT, TAG, DEDUP_ONLY, PROT_ONLY, CODE_ONLY, NO_JAPANESE, ALREADY_TRANSLATED, SYMBOL_ONLY) |
| `ValidationResult` | Single validation finding |
| `BatchValidationResult` | Aggregate validation for a batch |
| `PlaceholderValidationResult` | Placeholder-specific validation |
| `SpeakerFormatInfo` | Speaker format detection result |
| `RetryReason` (enum) | Why a line needs retry |
| `TranslationValidationResult` | Full translation validation |
| `BatchTranslationValidationResult` | Batch translation validation |
| `ValidationSeverity` (enum) | ERROR, WARNING, INFO |
| `CharacterWordFinding` | Character/word validation issue |
| `CharacterWordValidationResult` | Character validation result set |
| `RepetitionDetectionResult` | Repetition detection outcome |
| `extract_placeholders()` | Finds all placeholder tokens in text |
| `validate_placeholder_preserved()` | Checks placeholder integrity |
| `detect_speaker_dialogue_format()` | Detects speaker format in text |
| `validate_line_pre()` | Pre-translation line validation |
| `validate_line_post()` | Post-translation line validation |
| `validate_batch_pre()` | Pre-translation batch validation |
| `validate_batch_post()` | Post-translation batch validation |
| `validate_batch_comprehensive()` | Full batch validation with all rules |
| `detect_repetition()` | Detects repetitive patterns |
| `validate_character_word()` | Character/word blacklist/whitelist check |
| `apply_autofix()` | Applies automatic fixes from autofix map |

#### 9.7.3 Postprocessing Functions

**Postprocess** (`functions/postprocess.py`):
| Function / Class | Purpose |
|------------------|---------|
| `RecoveryType` (enum) | 10 recovery types (see §9.3) |
| `RecoveryAction` (enum) | RECOVERED, NEEDS_RETRY, SKIPPED, NO_ACTION |
| `RecoveryIssue` | Single recovery finding |
| `RecoveryResult` | Recovery outcome for one line |
| `BatchRecoveryResult` | Aggregate recovery for a batch |
| `RecoveryStats` | Per-type success/failure counts |
| `recover_placeholder_case()` | Fix `__PROTECTED__` → `__PROTECTED__` |
| `recover_mangled_placeholders()` | Reconstruct split/corrupted tokens |
| `recover_missing_placeholders()` | Restore missing placeholders from original |
| `normalize_placeholder_whitespace()` | Fix `__ PROTECTED __` → `__PROTECTED__` |
| `check_bracket_balance()` | Detect unmatched brackets |
| `recover_bracket_balance()` | Fix brackets using original as reference |
| `check_quote_balance()` | Detect unmatched quotes |
| `recover_quote_balance()` | Fix quotes |
| `recover_line()` | Master recovery — runs all applicable recoveries |
| `recover_batch()` | Batch recovery — processes all lines |
| `PostProcessManager` | Orchestrates full postprocessing pipeline |

**Post-Analysis** (`functions/postanalysis.py`):
| Function | Purpose |
|----------|---------|
| `compare_manifest_and_final()` | Compares manifest data with final output |
| `_try_code_recover()` | Attempts code pattern recovery |
| `_try_speaker_fix()` | Attempts speaker format restoration |
| `_try_br_recovery()` | Attempts `<br>` tag recovery |

**GUI Postprocessing** (`gui/steps/postprocess.py`):
| Function / Class | Purpose |
|------------------|---------|
| `FailurePolicy` (enum) | WRITE, FLAG (controls failure handling) |
| `_do_postprocessing()` | Main postprocessing entry point |
| `_basic_postprocess()` | Basic postprocessing path |
| `_run_character_validation()` | Character/word validation scan |
| `_apply_character_autofix()` | Applies autofix map |

#### 9.7.4 Wordwrap Functions

**Wordwrap** (`functions/wordwrap.py`):
| Function | Purpose |
|----------|---------|
| `pretty_wrap()` | Core wrapping algorithm with anti-orphan and punct-preferred breaks |
| `apply_wordwrap()` | Batch wrapping orchestrator |

**GUI Wordwrap** (`gui/steps/wordwrap_overwrite.py`):
| Function | Purpose |
|----------|---------|
| `_on_wrap_error()` | Handles wrapping errors per line |

#### 9.7.5 Output Functions

**GUI Output** (`gui/steps/output_inject.py`):
| Function | Purpose |
|----------|---------|
| `_export_logs()` | Bundles and exports all log files |
| `_on_export_error()` | Handles file write errors during export |

**Output** (`functions/output.py` — new, from Task 47.4):
| Function | Purpose |
|----------|---------|
| `get_final_output()` | Resolves injection priority chain, returns `(text, source_field)` |

#### 9.7.6 General / Cross-Pipeline Functions

**Error Handling** (`functions/common_errors.py`):
| Function / Class | Purpose |
|------------------|---------|
| `ErrorCode` (enum) | Standardized error codes |
| `CherryError` | Base exception with error code |
| `ErrorCollector` | Accumulates errors across operations |
| `validate_config_for_api()` | Validates API configuration before requests |
| `validate_file_readable()` | Validates file accessibility |
| `check_dependencies()` | Validates required package availability |

**Main Helper** (`functions/mainhelper.py`):
| Function | Purpose |
|----------|---------|
| `setup_logger()` | Creates and configures log handlers |
| `log_summary()` | Writes summary to log |
| `log_warning()` | Writes warning to log |
| `log_error()` | Writes error to log |
| `write_failure_report()` | Writes detailed failure report |

**Local LLM** (`functions/local_llm.py`):
| Function | Purpose |
|----------|---------|
| `check_port_open()` | Validates local LLM server port |
| `check_server_health()` | Health check for local LLM server |
| `discover_models()` | Query `/v1/models` endpoint for available models |
| `is_local_url()` | Check if URL points to localhost/LAN |
| `get_local_error_help()` | Returns human-readable error guidance |
| `get_provider_setup_instructions()` | Returns setup guide for a provider |
| `format_server_status()` | Formats server list for display |
| `detect_local_servers()` | Scan common ports for running LLM servers |

Local provider integration points:
- `APIClient.LOCAL_PROVIDERS = ("local", "lmstudio", "ollama")`
- `APIClient.is_local_provider()` — provider name + URL detection
- `_translate_chunk()` — `json_schema` format for local, `json_object` for cloud
- `test_model_translation()` in `api_config.py` — same `json_schema` adaptation
- `_filter_models_by_provider()` in `translate.py` — queries live server for models
- `_do_translation()` in `translate.py` — placeholder key + `no_api_key` for local providers
- `PROVIDER_PRESETS` — dedicated "LM Studio" entry (`provider_type="lmstudio"`)

**Batch Tracker** (`functions/batch_tracker.py`):
| Function | Purpose |
|----------|---------|
| `build_batch_jsonl()` | Builds JSONL payload for OpenAI Batch API |
| `parse_batch_results()` | Parses JSONL response into custom_id→content map |
| `submit_batch()` | Uploads JSONL and creates batch job |
| `poll_batch_status()` | Checks current status of a batch job |
| `retrieve_batch_results()` | Downloads and parses completed batch output |
| `cancel_batch()` | Cancels an in-progress batch job |
| `save_batch_job()` | Persists batch job metadata to JSON |
| `load_batch_jobs()` | Loads all persisted batch jobs |

**Key Manager** (`functions/key_manager.py`):
| Function/Class | Purpose |
|----------|---------|
| `APIKey` | Dataclass for key metadata, status, and rate-limit tracking |
| `KeyPool` | Manages pool of keys with rotation strategies |
| `PoolMode` | Enum: SEQUENTIAL, EVEN, PRIORITY |
| `KeyPool.next_key()` | Returns next available key per rotation strategy |
| `KeyPool.save()` / `load()` | JSON persistence for key pool state |

**Usage Tracker** (`functions/usage_tracker.py`):
| Function | Purpose |
|----------|---------|
| `record_usage()` | Inserts usage record into SQLite DB |
| `query_usage()` | Queries records by date, task_type, model |
| `usage_summary()` | Aggregated totals by model and task_type |
| `total_cost()` | Sum of costs in date range |
| `total_tokens()` | Sum of input/output tokens in date range |
| `export_csv()` | Exports usage records to CSV file |
| `purge_before()` | Deletes records older than cutoff date |

**Agent Modes** (`functions/agent_modes.py`):
| Function | Purpose |
|----------|---------|
| `register_mode()` | Registers a new agent mode |
| `unregister_mode()` | Removes a registered mode |
| `get_mode()` / `list_modes()` | Mode lookup and listing |
| `agent_call()` | Executes an agent request against an LLM |
| `gather_context()` | Assembles context string for a mode/request |
| `write_to_sandbox()` | Writes content to sandboxed dev/sandbox/ directory |
| `log_audit_entry()` | Appends audit entry to JSONL log |

**Estimation Engine** (`functions/estimation.py`):
| Function | Purpose |
|----------|---------|
| `estimate_tokens_for_lines()` | Estimates token count from line list |
| `estimate_chunks()` | Calculates chunk count from tokens and chunk_size |
| `compute_cost()` | Builds CostEstimate with itemized line items |
| `build_estimate()` | Full estimation pipeline from lines + options |
| `compare_models()` | Side-by-side cost comparison across models |
| `save_options()` / `load_options()` | InferenceOptions JSON persistence |

**Internationalization** (`functions/i18n.py`):
| Function | Purpose |
|----------|---------|
| `init()` | Loads language JSON strings from user/lang/ |
| `t()` | Translates key to localized string with format args |
| `set_language()` / `get_language()` | Active language management |
| `get_available_languages()` | Lists available language files |
| `has_key()` / `missing_keys()` | Key validation and coverage checking |

**Tooltip Helper** (`gui/helpers/tooltip.py`):
| Function | Purpose |
|----------|---------|
| `attach_tooltip()` | Binds tooltip to a Tk widget, returns tooltip_id |
| `detach_tooltip()` | Removes tooltip binding by id |
| `set_tooltips_enabled()` | Global enable/disable toggle |
| `set_tooltip_delay()` | Configures hover delay before showing |

=============================================================================

## Dynamic Model Registry Specification

**Requirement:** CherryAI must fetch, store, and serve model capabilities and pricing
without any hardcoded cloud provider data.

**Providers in scope:** OpenAI, Google Gemini, Mistral
(Anthropic/local/ollama/lmstudio providers remain static — not in scope)

**Data captured per model (`ModelInfo` fields):**

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | str | Provider canonical ID |
| `display_name` | str | Human-readable label |
| `provider` | str | `openai` / `google` / `mistral` |
| `url` | str | Pricing/info URL |
| `input_price` | float | USD per 1M input tokens |
| `cached_input_price` | float | USD per 1M cached input tokens |
| `output_price` | float | USD per 1M output tokens |
| `batch_input_price` | float | USD per 1M input tokens (batch mode) |
| `batch_output_price` | float | USD per 1M output tokens (batch mode) |
| `batch_mode` | bool | Batch API supported |
| `rpm_free` | int | Requests/min (free tier) |
| `rpm_tier1` | int | Requests/min (paid tier 1) |
| `rpd_free` | int | Requests/day (free tier) |
| `rpd_tier1` | int | Requests/day (paid tier 1) |
| `tpm_free` | int | Tokens/min (free tier) |
| `tpm_tier1` | int | Tokens/min (paid tier 1) |
| `max_concurrent` | int | Max concurrent requests |
| `structured_output` | bool | JSON/structured output supported |
| `thinking` | bool | Extended thinking/reasoning supported |
| `logit_bias` | bool | Logit bias supported |
| `temperature_min` | float | Minimum temperature value |
| `temperature_max` | float | Maximum temperature value |
| `context_window` | int | Max context tokens |
| `token_speed` | int | Approx tokens/second |
| `fetched_at` | str | ISO-8601 timestamp of last fetch |
| `flex_input_price` | float | Flex processing input (USD/1M tokens) |
| `flex_output_price` | float | Flex processing output (USD/1M tokens) |
| `priority_input_price` | float | Priority processing input (USD/1M tokens) |
| `priority_output_price` | float | Priority processing output (USD/1M tokens) |
| `thinking_mode` | str | Reasoning classification: "optional"/"mandatory"/"builtin"/"explicit"/"" |

**Pricing Tier Availability per Model Family:**
- GPT 4.1 family (`gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`): Standard + Batch only. No Flex or Priority tiers (`flex_*` and `priority_*` fields are `None`).
- GPT 5 family (`gpt-5`, `gpt-5-mini`, `gpt-5.1`, `gpt-5.2`, `gpt-5-nano`): Standard + Batch + Flex + Priority.
- O-series (`o3`, `o4-mini`): Standard + Batch + Flex + Priority.
- GPT 4o family (`gpt-4o`, `gpt-4o-mini`): Standard + Batch + Flex + Priority.
- Google/Mistral: Standard + Batch only (where `batch_mode=True`).

**Thinking/Reasoning Mode per Model Family:**
- GPT 4.1 family: `thinking_mode="optional"` — on/off toggle, `reasoning_effort` (low/medium/high)
- GPT 5 family: `thinking_mode="mandatory"` — always on, `reasoning_effort` configurable
- O-series (o3, o4-mini): `thinking_mode="builtin"` — always on, no extra params
- Claude (sonnet-4, opus-4): `thinking_mode="explicit"` — toggle + budget (tokens)
- Gemini/Magistral thinking: `thinking_mode="explicit"` — toggle + budget
- Non-thinking models: `thinking_mode=""` — unavailable

**reasoning_effort settings:**
- Stored per model in `[model_settings]` section of `user/API.ini` as `<model>.reasoning_effort`
- Valid values: `low`, `medium`, `high` (default: `medium`)
- Passed as top-level `reasoning_effort` in Chat Completions API for OpenAI models
- Part of `RequestSettings`, `APIConfig`, and `TranslationOptions` dataclasses
- UI: Combobox shown for optional/mandatory modes in Global Options Thinking frame

**Storage:** `user/API.ini`
- `[model_registry]` — `version`, `last_refreshed`
- `[model_registry_openai]` — `last_updated` (ISO-8601), `model.<id>` per model (JSON per line)
- `[model_registry_google]` — same structure
- `[model_registry_mistral]` — same structure
- `[security]` — `password_hash` (bcrypt WF-10, empty when password disabled), `key_salt` (hex, 32 bytes for PBKDF2)
- `[api_keys]` — Named API keys: `provider, name = <Fernet-encrypted value>` or plaintext when password disabled
  - Multiple keys per provider supported (e.g. `openai, work-key`, `openai, personal`)
  - Encrypted with AES-256 via Fernet, derived from master password + PBKDF2-HMAC-SHA256 (390k iterations)

**API Key Management functions** (`functions/api_config.py`):
- `set_api_key(provider, key, password, name="default")` — encrypt and store
- `get_api_key(provider, password, name="default")` — decrypt and return
- `set_api_key_plain(provider, key, name="default")` — store key as plaintext (no password required)
- `get_api_key_plain(provider, name="default")` — retrieve plaintext key
- `list_api_keys()` → `[(provider, name), …]` — metadata without decryption
- `delete_api_key(provider, name)` — remove a saved key
- `disable_password(current_password)` — decrypt all keys, clear hash/salt, store as plaintext
- `reset_password()` — clear hash/salt and remove all stored keys
- `test_api_connection(api_key, provider, base_url, timeout)` → `(bool, str, list)` — validates via `models.list()`, returns model ID list
- `test_model_translation(api_key, model_id, provider, base_url, timeout)` → `dict` — 6-check translation test (structured output, line count, code preservation, glossary adherence, translation completeness, output length)
- `PROVIDER_BASE_URLS` — default base URLs for all known providers

**Freshness policy:** Default 24 hours; stale data transparently falls back to built-in curated list.

**Fetch methods:**
- OpenAI: `GET https://api.openai.com/v1/models` (Bearer API key required), pricing from HTML page
- Google: `GET https://generativelanguage.googleapis.com/v1beta/models?key={key}`, pricing from HTML page
- Mistral: `GET https://api.mistral.ai/v1/models` (Bearer API key required), pricing embedded (JS-rendered page)

**Backward compatibility requirements:**
- `from functions.config import MODEL_PRICING` — must remain importable as a dict
- `MODEL_PRICING[model_id]` — must return pricing dict with same keys as before
- `from functions.options import API_PROVIDERS` — must remain importable as a dict
- `API_PROVIDERS["openai"]["models"]` — must return list of model ID strings

**GUI integration:**
- Global Options dialog: "⟳ Refresh Models" button triggers background refresh
- All three cloud providers (Global Options, Analysis, Translation) must use identical model lists
- No GUI code should call `get_api_key()` with password parameter — GUI refresh uses fallback only

=============================================================================

## Request Preview & Formation Integration Specification (Task 74)

### Section Headers with Descriptions

`SECTION_DESCRIPTIONS` dict maps 12 keys to informative text:
- meta: "Section headers (===) are for display only and not sent to the API"
- language: "Source/target language pair for translation"
- system_instructions: "Custom instructions provided in the Information step"
- summary: "Game context summary from the Information step"
- style: "Translation style guidelines"
- tone: "Translation tone"
- genre: "Genre of the source material"
- pov: "Narrative perspective (1st/2nd/3rd person)"
- conditional_prompts: "Auto-detected structural patterns in this chunk"
- glossary: "Only terms present in this chunk are included"
- rolling_context: "Last N translated lines from the previous chunk"
- input_lines: "Lines to translate in this chunk (JSON array)"

`build_full_request_text()` renders: `=== Label (description) ===`

### Formation-Based Chunking

`_build_chunks()` uses the 4-step pipeline from `prompt_builder.py`:
1. `TranslatableLine` → `LineInfo` conversion (index, text, is_invalid for __DEDUP__/__PROTECTED__/__CUSTOM__)
2. `file_end` markers injected from `mgr.get_filedir()` FileDirEntry.last_idx
3. `build_requests(line_infos, RequestFormationConfig(max_lines=chunk_size, min_lines=max(2, chunk_size//5), max_tokens=max_input_tokens))` called
4. `TranslationRequest.line_indices` mapped back to `List[List[TranslatableLine]]`

Each chunk's first line gets `_formation_ctx` dict: `{receives_context, provides_context, context_type}`.
Falls back to fixed-size splitting on ImportError or pipeline failure.

### Rolling Context

The `_do_translation()` loop maintains:
- `rolling_ctx_max`: from `global_options.request.rolling_context_lines` (default 3)
- `rolling_ctx_buffer: list[str]`: all translations from chunks with `provides_context=True`
- For chunks with `receives_context=True`: last N translations formatted as `rolling_context_text`
- Passed through: `_translate_chunk(rolling_context_text=...)` → `_build_system_prompt_from_manifest(rolling_context_text=...)` → `build_full_system_prompt(rolling_context_text=...)`

Preview shows placeholder: `[Rolling context: last N translated lines will be inserted here]`

### Per-Chunk Selective Filtering

`build_full_system_prompt(chunk_lines=...)` activates selective mode:
- Conditional prompts: detect against chunk_lines (not sample_lines)
- Glossary: include only entries where `entry["source"]` appears in chunk text
- Characters: include only where `ch["original_name"]` appears in chunk text

`_translate_chunk()` filters `__DEDUP__` lines before API call.

### Cross-Request Search

`RequestPreviewDialog` search state:
- `_cross_counts: list[int]` — match count per request
- `_cross_total: int` — sum of all matches
- `_cross_global_idx: int` — current position in global match sequence

Navigation: `_resolve_global_index(idx)` → `(request_idx, local_match_idx)`.
`_navigate_to_global_match()` switches request and highlights locally.
Match label: "N of M (across K requests)" when multiple requests have matches.

### Request Logging

`LoggingSettings.log_requests: bool = False` in `global_options.py`.
When enabled, `_log_request_json()` writes to `logs/requests/request_{YYYYMMDD_HHMMSS}_chunk{N}.json`:
```json
{
  "timestamp": "20260302_143022",
  "chunk_index": 1,
  "model": "gpt-4o",
  "temperature": 0.3,
  "system_prompt": "...",
  "input_lines": ["line1", "line2"],
  "line_count": 2
}
```

=============================================================================

## Phase 78 — Estimation, Validation & Formation Fixes

### Character Validation Spec (Task 5)

**Entry Syntax:** Comma-separated tokens.  `\,` for literal comma.
`re=<pattern>` for regex.  Plain text for literal matching.

**Strategies** (Global Options → Translation → Character Validation):

| Setting | Default | Behaviour |
|---------|---------|-----------|
| Exchange Forbidden Characters | On | Replace via Autofix Map |
| Flag for QA Review | On | Set line status to `NEEDS_REVIEW` |
| Retry Lines with Forbidden Characters | Off | Blank translation, reset to `PENDING` |

Strategies are applied in order: exchange first, then retry, then flag.
If exchange resolves all violations the line is accepted normally.

### Prompt Overhead Spec (Task 4, updated Task 42)

Per-request prompt overhead: Each request's prompt is built individually
using `build_full_system_prompt(chunk_lines=request.lines)` so that
selective glossary/conditional filtering applies per chunk.  Token counts
are summed across all requests for the total overhead; the average is
`total // num_requests`.

Display format: `~Z total (Y Requests, ~X avg/request)`.
Token counts use `count_tokens()` (tiktoken-based) not `len // 4`.

### Formation Receives-Context Spec (Task 7)

First request of each file section: `receives_context = False`.
`rolling_ctx_buffer.clear()` at every file boundary.

### Estimation Skip Spec (Task 3)

`_get_skip_indices()` returns indices to exclude from preprocessed estimation:
skip non-source, skip already translated (when overwrite off), skip
symbol-only dialogue, skip generic placeholders.

## Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 3.7 | 2026-03-07 | Bug Fix — Glossary ↔ Term Translation Dual-Storage Desync: Fixed `on_enter()` in information.py loading characters from top-level manifest BEFORE `_load_metadata()` replaced `self._metadata` with stale step_state (reordered to load after). Fixed `on_leave()` not syncing characters/code_patterns to top-level manifest (added `_save_characters_to_manifest()` and `_save_code_patterns_to_manifest()` calls). Fixed `_import_analysis_speakers()` not persisting auto-imported entries to top-level key. 19 new tests (test_glossary_term_link.py). |
| 3.6 | 2026-03-06 | Bug Fix — Section Toggle Persistence & Preview Gating: Fixed `on_leave()` in information.py erasing `*_enabled` flags (root cause: `ProjectMetadata.to_dict()` excludes them, then `set_step_data()` replaced entire metadata dict). Fixed `_build_preview_requests()` in translate.py ignoring enabled flags (now gates sys_instructions, style, tone, summary, genre, glossary, character sections). Removed redundant Save button from Information step header (auto-save on tab change is sufficient). 35 new tests (test_section_toggles.py). |
| 3.5 | 2026-03-05 | Task 42 — Per-Request Prompt Overhead: `_estimate_via_formation()` returns `FormationResult` dataclass (num_requests + request_line_lists). New `_compute_per_request_prompt_overhead()` builds each request's prompt individually via `build_full_system_prompt(chunk_lines=...)` for selective glossary/conditional filtering, sums token counts. Display format changed from `~Z total (Y Requests, ~X per)` to `~Z total (Y Requests, ~X avg/request)`. 29 new tests (test_prompt_overhead_fix.py). |
| 3.4 | 2026-03-04 | Task 41 — Max Input Tokens: Added `max_input_tokens` field to RequestSettings (0 = no limit, input lines only), Global Options spinbox (0–128000, increment 500), INI persistence (`[api].max_input_tokens`), wired into translate.py `_build_chunks()` and costs.py `_estimate_via_formation()` via `RequestFormationConfig.max_tokens`. 34 new tests (test_max_input_tokens.py). |
| 3.3 | 2026-03-03 | Phase 78 — 10 tasks: manifest sample removal, speaker replacement fix, estimation skip logic, prompt overhead display, blacklist/whitelist validation rewrite (parse_filter_entries, check_filter_violations, 3-strategy _apply_char_filters, NEEDS_REVIEW status, 3 new TranslationSettings fields + UI checkboxes), romanization + Code DB Translation column, rolling context file-boundary fix, slicing efficient mode fix, global options scrolling fix, model settings lines/request decoupling. New test files: test_estimation_skip.py (41), test_costs_step_phase40.py (57), test_rolling_context_phase78.py (10), test_slicing_phase78.py (11), test_char_filter_phase78.py (32). |
| 3.2 | 2026-03-02 | Task 76 — Knowledge Base Widget: Merged Glossary Settings and Global Glossary/Database into unified Knowledge Base widget with Enabled/Disabled toggle, mode switch (Glossary/Code Database), per-entry Active column (✓/✗ toggle), mixed-selection Activate/Deactivate failsafe popup, search/column filter. Updated collapsible widgets from LabelFrame to header+separator design (no empty borders when collapsed). Right column reduced from 4 to 3 rows. TSV schemas updated: globalglossary.tsv 3→4 columns (added Active), codedatabase.tsv 9→10 columns (added Active). Button text standardized to +Add/Edit/Remove. 56 tests. |
| 3.1 | 2026-03-02 | Task 74 — Request Preview Overhaul: Informative section headers (SECTION_DESCRIPTIONS dict, 12 keys), renamed custom_notes → system_instructions across 6 files, formation-based chunking (4-step build_requests pipeline integrated into _build_chunks), rolling context in translation loop (receives_context/provides_context flags, rolling_ctx_buffer), per-chunk selective glossary/conditional/character filtering (chunk_lines parameter), cross-request search (global match index navigation across all requests), request logging toggle (log_requests in LoggingSettings, JSON to logs/requests/). Fixed step index bugs (3→2) in metadata lookup. 110 tests passing (20 prompt_builder_shared + 42 request_preview + 50 request_formation). |
| 3.0 | 2026-02-10 | Phase 17 Infrastructure: Added Batch API support (batch_tracker.py — JSONL builder, job persistence, submit/poll/cancel), Multi-Key Management (key_manager.py — key pools with sequential/even/priority rotation), Named API Profiles (project_config.py — display_name, system_prompt_tweak, rename/duplicate), Additional File Formats (markdown.py, json_lenient.py, translator_plus.py), Usage Analytics (usage_tracker.py — SQLite-backed token/cost tracking with CSV export), Agent-Assisted Modes (agent_modes.py — mode registry, sandboxed writes, audit logging), Estimation Engine (estimation.py — itemized billing, model comparison, persistence), i18n & Tooltips (i18n.py — JSON language files with fallback, tooltip.py — configurable Tk tooltips). Session persistence (app.py saves/restores last step). Bug fixes: estimate_rate_limit_time() missing params; SharedTable batch insertion duplicate item IDs (added _batch_insert_version counter). Added 339 new tests (5619 total). |
| 2.8 | 2026-02-08 | Comprehensive rewrite of Step 9 (Output): Defined injection priority chain (9-level: overwrite → wordwrap → postprocessed → edit{N} → tlc{N} → translation → preedit → preprocessed → original). Added Dirty Flags system (Process flag set by preprocessing/cleared by postprocessing 100%, Wordwrap flag cleared when applied) with pre-export validation dialog. Non-destructive default (subfolder naming, no overwrite). Failure logging with per-file error tracking. Complete widget specifications with destination, format, naming, safety, and export extras sections. Settings received from Input (source_root, file_dir, encoding, format). Step 0 (Input): Added Import Translations button — imports translations from another manifest via exact `orig` line matching (sequential search, file/line-number agnostic, copies all processing fields). Step 5 (Translation): Added Skip Already Translated checkbox — skips lines with existing `tl` field for incremental translation workflows. Bug fixes: QA mousewheel TclError (try/except wrapper for race condition), output_inject `get_section` → `get_output_options()`, preprocess warning demoted to debug. |
| 2.7 | 2026-02-08 | Comprehensive rewrite of Step 8 (Wordwrap): Redefined purpose (auto from parser or manual settings). Pretty wrap is now standard — removed Prevent Orphans and Prefer Punctuation Breaks checkboxes (always active). Mode changed from radio buttons to dropdown, removed RPG Maker (→ its own parser) and Disabled options. Width changed from Spinbox to Dropdown with Character/Pixel modes. Break Character linked to Preprocessing and Translation Prompt with cost-optimization note. Speaker Handling reduced to Ignore + Count (renamed from Sameline), removed Samelineindent and Newline. Ignore Patterns replaced with read-only Code Database table (no checkboxes). Removed Typography widget entirely. Removed Overwrite Strategy widget — Overwrite becomes a column in the Lines Table with diff filtering. Added table filters (All/Changed/Exceeding/Overwrite Differs). Added Standard Wrapping Rules table documenting always-active `pretty_wrap()` behavior. Added comprehensive Future Improvements for parser-driven wrap, font commands, pixel-accurate width, New Textboxes, and break char removal before translation. |
| 2.6 | 2026-02-08 | Comprehensive rewrite of Step 7 (Postprocessing): Complete mirror-symmetry spec with Step 4 Preprocessing — reverse priority ordering, automatic restorations (Placeholder/Code/BR always-on, no GUI toggle), post-exclusive recovery processes (Bracket Balance, Quote Balance, Whitespace Normalization with toggles). Renamed "Postprocessed Lines" to "Processed Lines" with new filters (Changed/Written/Flagged/By Process). Removed Refresh and Revert All buttons (overwrite semantics with confirmation dialog). Added Postprocess Options widget (bidirectional Symbol Conversion: Fullwidth↔Halfwidth). Redesigned Failure Handling (Write=default, Flag for Review=no-write, Queue for Retry=hidden/future). Added Diff View manual editing with Mark-as-Fixed. Added Postprocessing Summary with live updates and 100% completion popup. Fixed MouseWheel `bind_all` bug across all step files (qa.py, postprocess.py, translate.py, wordwrap_overwrite.py, output_inject.py). |
| 2.5 | 2026-02-07 | Step 5 (Translation): Added Translation/Edit/TLC Mode Toggle to Hidden (Future Improvement) — three-way toggle with line-matching strategy design challenge. Step 6 (Quality Assurance): Complete rewrite — defined purpose as safety net for issues automatic recovery couldn't fix, added philosophy section, specified placeholder toggle mode (current state), preserved full widget spec and validation rules as future reference, added Edit/TLC filtering note. |
| 2.4 | 2026-02-07 | Comprehensive update to Step 5 (Translation): Complete widget specifications for Translatable Lines (merged Original/Preprocessed into "To be Translated"), Request Options (Model from Global Options providers, Mock Translation default, Lines/Chunk sync with Estimation, Retry Strategy details for Batch/Contextual, Skip Non-Source Language), Preview Requests (RequestPreviewDialog with Pure/Formatted/Plain views, Jump/Search/Filter toolbar, Ban Tokens separated), API Usage (live metrics). Added performance requirements (< 1s load for 100K lines, virtual scrolling, tab caching). Moved Request Caching, Extended Thinking, and Rolling Context to Global Options. Hidden Edit Before Translation and Line-by-Line Mode as Future Improvements. Added Mock Translation specification. |
| 2.3 | 2026-02-03 | Comprehensive update to Step 4 (Preprocessing): Complete widget specifications for Standard Rules Panel, Custom Placeholders, Protect Code Patterns, and Anchoring (renamed from Anchor Removal). Added detailed process specifications with priority ordering, execution order documentation, Preprocessing↔Postprocessing mirror symmetry, validation and recovery strategies, RegEx toggle support for all pattern widgets, Preview Table with filtering, and comprehensive testing requirements. |
| 2.2 | 2026-02-01 | Updated Step 3 (Information) with comprehensive widget specifications: Project Details (Name, Title, Genre with ADD behavior), Languages (Source/Target with "Other" custom input), Summary (renamed), Translation Style and Tone (dropdown graying with custom override), System Instructions (renamed from Prompt), Glossary Settings (3-column editable table, selective glossary), Code Database (renamed from Code Glossary, Preserve/Translate/Remove actions), and NEW Global Glossary and Database widget. Added prompt formats and manifest keys for all widgets. |
| 2.1 | 2026-02-01 | Updated Step 1 (Analysis) with QoL future improvements. Renamed Step 2 from Estimation to Costs with comprehensive spec including: dual estimation workflow (Original + Preprocessed), Tokens/Request limit, prompt overhead calculation, model comparison expanded fields, time estimation with concurrent requests. Updated data flow and automation triggers. |
| 2.0 | 2026-02-01 | Major revision: Updated Step 0 (Input) spec with unified file selector, collapsible folder tree, format filtering, progress window, removed redundant buttons. Updated step names (Wordwrap, Output). Added automation triggers and pipeline overview. |
| 1.0 | 2026-01-31 | Initial comprehensive specification |
