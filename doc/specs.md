# CherryAI Specification Document

Version 2.0 | February 2026

This document provides a complete functional specification of CherryAI, an LLM-based translation application designed to achieve high-quality translations using Large Language Models. The application requires substantial input and processing which can optimally be performed automatically once an input is selected.

CherryAI describes every component, data flow, user interaction, and file dependency in detail suitable for both human users and AI assistants.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Data Flow Summary](#2-data-flow-summary)
3. [External Files and Storage](#3-external-files-and-storage)
4. [Global Options](#4-global-options)
5. [GUI Mode: Step-by-Step Specification](#5-gui-mode-step-by-step-specification)
   - [Step 0: Input](#step-0-input)
   - [Step 1: Analysis](#step-1-analysis)
   - [Step 2: Costs](#step-2-costs)
   - [Step 3: Information](#step-3-information)
   - [Step 4: Preprocessing](#step-4-preprocessing)
   - [Step 5: Translation](#step-5-translation)
   - [Step 6: Quality Assurance](#step-6-quality-assurance)
   - [Step 7: Postprocessing](#step-7-postprocessing)
   - [Step 8: Wordwrap](#step-8-wordwrap)
   - [Step 9: Output](#step-9-output)
6. [CLI Mode: Automatic Pipeline](#6-cli-mode-automatic-pipeline)
7. [Manifest Structure](#7-manifest-structure)
8. [Processing Modules Reference](#8-processing-modules-reference)

---

## 1. Architecture Overview

CherryAI is designed to achieve high-quality translation using LLMs through extensive input processing and automation. The application separates concerns into four layers:

| Layer | Location | Responsibility |
|-------|----------|----------------|
| GUI | `gui/` | Display, user interaction, widget binding (10 workflow steps/tabs) |
| Processing | `functions/` | Core logic, translation, validation |
| Modes | `modi/` | Pre/post-processing transformations |
| Formats | `formats/` | File I/O for TXT, CSV, JSON, XLSX, RPG Maker, Images |

**Critical Rule:** GUI code contains NO processing logic. All text manipulation occurs in `functions/` or `modi/`. Both GUI and CLI share identical processing paths.

### GUI Structure

The GUI is organized as:
- **Menu Bar**: File, Edit, Tools, Help dropdowns (File contains New Project, Open Project)
- **Step Tabs**: 10 workflow tabs (Steps 0-9) progressing from Input to Output
- **Global Options**: Application-wide settings accessed via Tools → Options
- **Progress Tracker**: Visual indicator showing completion status of each step

### Module Counts

- `functions/`: 36 modules (core processing)
- `modi/`: 12 pre/post-processing modes
- `formats/`: 5+ file format handlers (expanding to support images and game engines)
- `gui/steps/`: 10 workflow tabs
- `gui/helpers/`: 6 adapter modules
- `gui/dialogs/`: 2 dialog modules

### State Management

All application state is stored in the Manifest (`.CherryAI.json`), not in GUI memory. For every translation project, a manifest file is created which loads all project data and saves all process steps. The ManifestManager handles:
- Auto-save on step change, close, and periodic interval (15s default)
- Per-step data storage with automatic serialization
- Line-by-line translation state tracking
- Project recovery and session restoration

---

## 2. Data Flow Summary

CherryAI processes text through a 10-step pipeline. Each step produces outputs that feed into subsequent steps. Once an input is selected, the entire pipeline can run automatically based on configured settings.

```
User Files (TXT/CSV/JSON/XLSX/RPG Maker/Images)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 0: Input          │ Load files, detect format         │
│  Produces: all_lines[]  │ Store in manifest file_dir        │
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
│  Step 2: Costs          │ Token count, cost projection      │
│  Produces: token_count, │ cost_original, cost_preprocessed  │
│  time_estimate          │ (Two-state: Original + Prepro)    │
│  Auto-Trigger: On load  │ Auto-Trigger: After Preprocessing │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: Information    │ Project metadata, style, tone     │
│  Produces: metadata{},  │ characters[], code_glossary[]     │
│  prompt_context         │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: Preprocessing  │ Dedup, placeholders, protect code │
│  Produces: prepro[],    │ prepro_ops[], dedup_map           │
│  protected_patterns     │ (Runs automatically if enabled)   │
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
│  Step 6: QA             │ Validate placeholders, anchors    │
│  Produces: issues[],    │ accepted[], rejected[]            │
│  suggestions            │                                   │
└─────────────────────────┴───────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 7: Postprocessing │ Restore placeholders, symbols     │
│  Produces: postpro[],   │ recovery_stats, retry_list        │
│  validation_result      │                                   │
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

---

## 3. External Files and Storage

### 3.1 Configuration Files

| File | Location | Purpose | Format |
|------|----------|---------|--------|
| `CherryAI.ini` | Project root | API keys, presets, defaults | INI |
| `api_profiles.ini` | Project root | API provider profiles | INI |
| `config/defaults.ini` | `config/` | Default settings | INI |
| `.vscode/settings.json` | `.vscode/` | VS Code analysis paths | JSON | Dev only
| `pyrightconfig.json` | Project root | Type checking config | JSON | Dev only

### 3.2 Project Files

| File | Location | Purpose | Format |
|------|----------|---------|--------|
| `*.CherryAI.json` | `Projects/` | Project manifest (all state) | JSON |
| `glossary.csv` | `user/` | Global translation glossary | CSV |
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
| Provider | enum | openai | API provider (openai, gemini, anthropic, local) |
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
| Chunk Size | int | 50 | Lines per API request |

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

---

## 5. GUI Mode: Step-by-Step Specification

Each step is a tab in the main notebook. Steps can be navigated freely but follow a logical workflow progression.

---

### Step 0: Input

**Purpose**: Load source files and extract translatable text. This is where a project begins. Loading files can trigger the entire pipeline automatically based on configured settings.

**Design Goal**: Extract only visible text from any unencrypted text file that a user can theoretically read. Code and non-translatable content should be excluded. In the final step (Output), translated text is injected into copies of the original files to replace the original text (non-destructive).

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| **Toolbar** | | |
| Select File(s) Button | Button | Unified file/folder selector (replaces Load Files and Load Folder) |
| **Options Panel** | LabelFrame | Contains Encoding and Format dropdowns |
| Encoding Dropdown | Combobox | Select file encoding (auto, utf-8, shift_jis, etc.). Default: auto |
| Format Dropdown | Combobox | Override format detection (auto, txt, csv, json, rpgmaker, image, etc.). Default: auto |
| **Loaded Files Panel** | LabelFrame | Shows loaded files in a tree structure |
| File Tree | Treeview | Collapsible folder hierarchy with files. Supports multi-select for bulk operations |
| **Preview Panel** | LabelFrame | Shows content of selected file |
| Preview Tree | Treeview | Line numbers and content. Must properly render newlines (multi-line content) |

**Removed Elements** (from previous design):
- Load Manifest button → Use File → Open Project... menu instead
- Clear All button → Use File → New Project menu instead
- Manifest Label (below Preview) → Removed; manifest status shown in title bar

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

#### Select File(s) Button Behavior

The unified selector replaces separate Load Files and Load Folder buttons:

1. Opens a file dialog that accepts:
   - Single file selection
   - Multi-file selection (Ctrl+Click)
   - Single folder selection
   - Multi-folder selection

2. Processing:
   - For files: Load directly
   - For folders: Recursively collect all supported files
   - Respects Format filter (if not `auto`)
   
3. Displays a **progress window** during loading to show:
   - Current file being loaded
   - Progress bar (files loaded / total files)
   - Cancel button to abort

4. After loading:
   - The containing folder is stored in the manifest as `source_root`
   - All selected files/folders and their lines are saved to manifest

#### Loaded Files Panel Details

**File Tree Structure**:
- Files organized by folder hierarchy
- Folders are collapsible nodes
- Files show: filename, line count, format icon
- Multi-select enabled for bulk delete operations
- Context menu (right-click): Remove Selected, Select All in Folder

**Missing Features to Implement**:
- Collapsible folder groups
- Multi-select support (currently single-select only)
- Folder-level delete (delete all files in a folder at once)

#### Preview Panel Details

**Preview Tree**:
- Columns: Line # (narrow), Content (wide, stretches)
- Shows all lines from selected file
- Content column must properly display multi-line text (newlines rendered, not truncated)

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
- `all_lines: List[str]` - All extracted text lines from all files
- `loaded_files: List[LoadedFile]` - File metadata objects
- `file_dir: List[FileDirEntry]` - Index ranges per file (for output injection)

**Stored In**:
- Manifest: `source_root`, `source_files[]`, `file_dir[]`, `lines[].orig`
- Manifest step data: `Input.file_count`, `Input.total_lines`, `Input.formats`

#### Step Completion

**Automatic Completion**: Step 0 is marked complete when **any file is successfully loaded**.

**Triggers on Completion** (if enabled in Global Options):
- `auto_analyze_on_load`: Automatically runs Analysis (Step 1)
- `auto_preprocess_on_load`: Automatically runs Preprocessing after Analysis (Step 4)

#### User Actions

| Action | Effect |
|--------|--------|
| Click Select File(s) | Opens unified file/folder picker dialog |
| Select item in File Tree | Shows preview of that file's content |
| Right-click File Tree | Context menu: Remove Selected, Select All |
| Multi-select + Delete | Removes all selected files |
| Collapse/Expand folder | Toggles folder visibility in tree |

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

### Step 1: Analysis

**Purpose**: Analyze loaded content for translation planning. This step primarily infers information and displays it to users to support decisions about preprocessing, glossary, and translation settings.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Run Analysis Button | Button | Executes full analysis |
| Export Button | Button | Exports findings to CSV |
| Statistics Panel | Frame | Shows line counts, percentages |
| Findings Table | SharedTable | Lists categorized findings |

#### Data Flow

**Inputs**:
- From Step 0: `all_lines[]` from loaded files
- From Session: Previously stored analysis results

**Processing** (via `gui/helpers/analysis_adapter.py` → `functions/analysis.py`):
1. Count total lines, empty lines, unique lines
2. Detect duplicate lines and frequency
3. Detect language distribution per line
4. Detect speaker patterns (Name: "dialogue")
5. Detect code patterns (variables, tags, escapes)
6. Build findings table rows

**Outputs**:
- `total_lines: int`
- `empty_lines: int`
- `unique_lines: int`
- `duplicate_count: int`
- `duplicates: Dict[str, int]` - Line text to count
- `languages: Dict[str, int]` - Language to line count
- `speakers: Dict[str, int]` - Speaker to occurrence count
- `code_patterns: Dict[str, int]` - Pattern type to count
- `findings: List[TableRow]` - UI display rows

**Stored In**:
- Manifest step data (step_id=1)
- Fields: `Analysis.total_lines`, `Analysis.unique_lines`, etc.

#### User Actions

| Action | Effect |
|--------|--------|
| Click Run Analysis | Runs analysis in background thread |
| Click Export | Saves findings to CSV file |
| Filter findings table | Filters by category column |
| Select finding row | No additional action (display only) |

#### Current State

The Analysis step is functional and provides valuable information. No immediate priority improvements are planned for the Statistics and Findings widgets.

#### Future Quality of Life Improvements (Low Priority)

- **Auto-populate glossary**: Use detected speakers and code patterns to pre-fill glossary entries
- **Pattern suggestions**: Recommend protection rules based on detected code patterns
- **Export formats**: Support additional export formats (JSON, XLSX)
- **Visual improvements**: Charts/graphs for language distribution
- **Diff analysis**: Compare against previous analysis when files change

---

### Step 2: Costs

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
| Prompt Overhead Label | Label | Shows token cost of system prompt per request |
| **Cost Estimate Panel** | LabelFrame | Display cost projection |
| Cost Labels | Labels | Input cost, Output cost, Total cost for selected model |
| **Time Estimate Panel** | LabelFrame | Display time projection |
| Time Labels | Labels | Estimated duration accounting for rate limits and concurrent requests |
| **Model Comparison Table** | SharedTable | Compare all available models |
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
| Prompt Overhead | - per request - |

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

**Current Display**:
- Input cost: (input_tokens / 1M) × model_input_price
- Output cost: (output_tokens / 1M) × model_output_price
- Total cost: Input + Output

**Required Behavior**:
- Pull calculated costs from Model Comparison table for consistency
- Show both Original estimate and Preprocessed estimate
- Show Savings percentage

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
- Input: Original lines from `all_lines[]`
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
- From Step 0: `all_lines[]` (original lines)
- From Step 4: `prepro[]` (preprocessed lines, if available)
- From Step 3: Summary, tone, style, characters, code glossary (for prompt calculation)
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
5. Estimate output tokens (input × 1.2 multiplier)
6. Look up model pricing (input/output per 1M tokens)
7. Calculate costs for multiple models
8. Estimate time using concurrent requests, rate limits, and token speed

**Outputs**:
- `input_tokens_original: int` - Input tokens before preprocessing
- `input_tokens_preprocessed: int` - Input tokens after preprocessing
- `output_tokens: int` - Estimated output tokens
- `prompt_overhead: int` - Tokens per request from system prompt
- `cost_original: float` - Cost before preprocessing
- `cost_preprocessed: float` - Cost after preprocessing
- `cost_saved: float` - Savings from preprocessing
- `savings_percent: float` - Percentage saved
- `chunks_required: int` - Number of API requests
- `estimated_time: str` - Formatted duration

**Stored In**:
- Manifest step data (step_id=2)
- Fields: `Costs.input_tokens`, `Costs.output_tokens`, `Costs.total_cost`, `Costs.cost_original`, `Costs.cost_preprocessed`, `Costs.savings_percent`, `Costs.estimation_state`

#### User Actions

| Action | Effect |
|--------|--------|
| Select model | Updates global model, triggers auto-estimation |
| Change Lines/Request | Recalculates chunk count and time |
| Change Tokens/Request | Recalculates chunk boundaries |
| Click Refresh | Fetches latest model data from providers |
| Click Estimate | Runs full manual estimation (both states) |

#### Future Enhancements (Low Priority)

- **Request Merging**: Combine small trailing chunks into previous request when no rolling context needed
- **Final Cost Recording**: Track actual tokens/cost after translation completes
- **Cost Comparison**: Show estimated vs actual difference
- **Additional Cost Types**: Editing, TLC, Summary generation, Glossary inference
- **Cost History**: Track costs across multiple translation sessions
- **Budget Warnings**: Alert when estimated cost exceeds configured budget

---

### Step 3: Information

**Purpose**: Configure project metadata and translation context.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Project Name Entry | Entry | Project identifier |
| Game Title Entry | Entry | Source game/work title |
| Source Language Dropdown | Combobox | Source language (Japanese, etc.) |
| Target Language Dropdown | Combobox | Target language (English, etc.) |
| Genre Dropdown | Combobox | Content genre (RPG, Visual Novel, etc.) |
| Summary Text | ScrolledText | Content summary for context |
| Style Preset Dropdown | Combobox | Translation style (literal, natural, etc.) |
| Custom Style Text | ScrolledText | Custom style instructions |
| Tone Preset Dropdown | Combobox | Translation tone (neutral, dramatic, etc.) |
| Custom Tone Text | ScrolledText | Custom tone instructions |
| Character Notes Table | Table | Character name, gender, notes |
| Code Glossary Table | Table | Code patterns to preserve |
| Prompt Text | ScrolledText | Additional translation instructions |
| JSON View Button | Button | Toggle raw JSON view |
| Save Button | Button | Force save to manifest |

#### Data Flow

**Inputs**:
- User: Manual entry of all fields
- From Step 1: Detected speakers (can populate characters)
- From Step 1: Detected code patterns (can populate glossary)

**Processing**:
1. Validate field formats
2. Build ProjectMetadata dataclass
3. Build CharacterInfo list from table
4. Build CodePattern list from table
5. Serialize to manifest on change

**Outputs**:
- `project_name: str`
- `game_title: str`
- `source_language: str`
- `target_language: str`
- `genre: str`
- `summary: str`
- `style_preset: str` + `custom_style: str`
- `tone_preset: str` + `custom_tone: str`
- `characters: List[CharacterInfo]`
- `code_patterns: List[CodePattern]`
- `custom_notes: str` (prompt)

**Used By**:
- Step 5 (Translation): Prompt construction uses summary, style, tone, characters
- Step 7 (Postprocessing): Code glossary patterns for restoration

**Stored In**:
- Manifest: `project_info{}`, `glossary.project_entries[]`
- Auto-saved on field change via manifest binding

#### Style Presets

| Preset | Description |
|--------|-------------|
| literal | Word-for-word, preserving structure |
| natural | Fluent, adapted to target language |
| creative | Liberal adaptation with interpretation |
| formal | Professional language register |
| casual | Informal, conversational |
| technical | Precise technical terminology |
| literary | Artistic prose style |

#### Tone Presets

| Preset | Description |
|--------|-------------|
| neutral | Balanced, no strong emotion |
| serious | Grave, solemn atmosphere |
| humorous | Light-hearted, comedic |
| dramatic | Intense, theatrical |
| dark | Grim, ominous |
| romantic | Warm, emotional |

---

### Step 4: Preprocessing

**Purpose**: Apply text transformations before translation.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Apply Rules Button | Button | Execute preprocessing |
| Reset Button | Button | Clear preprocessing results |
| Auto-Suggest Button | Button | Suggest rules from analysis |
| Deduplication Checkbox | Checkbox | Enable duplicate removal |
| Dedup Threshold Spinbox | Spinbox | Minimum occurrences (0-10) |
| Ellipsis Checkbox | Checkbox | Compress ellipsis sequences |
| Symbol Conversion Checkbox | Checkbox | Convert JP→EN punctuation |
| PROT Compression Checkbox | Checkbox | Compress adjacent __PROT__ |
| Speaker Replacement Checkbox | Checkbox | Replace speaker names |
| Code Spacing Checkbox | Checkbox | Apply code spacing rules |
| Placeholder Rules List | Listbox | Custom pattern→token rules |
| Protect Code List | Listbox | Patterns to protect with __PROT__ |
| Anchor Removal List | Listbox | Anchors to remove/restore |
| Preview Table | SharedTable | Original vs Processed comparison |

#### Data Flow

**Inputs**:
- From Step 0: `all_lines[]`
- From Step 3: `code_patterns[]` for protect rules
- Config: Standard rule toggles

**Processing** (via `gui/helpers/mode_adapter.py` → `modi/` modules):
1. **Deduplication**: Replace repeated lines with `__DEDUP_N__` tokens
2. **Ellipsis**: Compress `……` / `...` sequences
3. **Symbol Conversion**: `。→.` `、→,` `！→!` etc.
4. **PROT Compression**: `__PROT____PROT__` → `__PROT_2__`
5. **Custom Placeholders**: Pattern → `__TOKEN__`
6. **Protect Code**: Pattern → `__PROT__` with stored original
7. **Anchor Removal**: Remove and store for later restoration

**Outputs**:
- `prepro: List[str]` - Preprocessed lines
- `prepro_ops: List[Dict]` - Restoration metadata per line
- `dedup_map: Dict[str, List[int]]` - Original indices for deduped lines
- `change_count: int` - Lines modified
- `protected_count: int` - Code patterns protected

**Stored In**:
- Manifest: `lines[].prepro`, `lines[].prepro_ops`
- Manifest step data: `Preprocessing.{Deduplication, EllipsisCompression, ...}`

#### Preprocessing Rules Detail

| Rule | Pattern | Result |
|------|---------|--------|
| Ellipsis | `……+` or `\.{4,}` | `……` or `...` |
| Symbol JP→EN | `。、！？` | `.,!?` |
| Fullwidth | `０-９Ａ-Ｚ` | `0-9A-Z` |
| PROT Compress | `__PROT____PROT__` | `__PROT_2__` |

---

### Step 5: Translation

**Purpose**: Execute LLM translation of preprocessed text.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Start Translation Button | Button | Begin translation process |
| Pause/Resume Button | Button | Control translation flow |
| Cancel Button | Button | Abort translation |
| Model Override Entry | Entry | Override model from options |
| Temperature Spinbox | Spinbox | Override temperature (0.0-2.0) |
| Chunk Size Spinbox | Spinbox | Lines per request |
| Retry Strategy Dropdown | Combobox | batch/contextual/isolated/skip |
| Max Retries Spinbox | Spinbox | Retry attempts (1-10) |
| Cache Enabled Checkbox | Checkbox | Enable request caching |
| Line-by-Line Checkbox | Checkbox | Translate lines individually |
| Edit Before Translation Checkbox | Checkbox | Show edit dialog before API |
| Prompt Preview Pane | Text | Shows constructed prompt |
| Lines Table | SharedTable | Source and translated lines |
| Progress Window | Toplevel | Modal progress display |

#### Data Flow

**Inputs**:
- From Step 4: `prepro[]` (or `orig[]` if no preprocessing)
- From Step 3: Summary, style, tone, characters (for prompt)
- From Global Options: API config, model, temperature

**Processing** (via `functions/api_client.py`):
1. Build translation prompt from templates and metadata
2. Chunk lines by configured size
3. For each chunk:
   a. Check cache for existing translation
   b. Apply rate limiting
   c. Send to LLM API with JSON response format
   d. Parse response, map to source lines
   e. Handle failures per retry strategy
   f. Update progress display
   g. Save to manifest after each chunk
4. Track token usage and costs

**Outputs**:
- `tl: List[str]` - Translated lines
- `tokens_used: int` - Actual tokens consumed
- `cost_actual: float` - Actual cost incurred
- `failed_lines: List[int]` - Indices that failed
- `skipped_lines: int` - Deduped/empty lines skipped

**Stored In**:
- Manifest: `lines[].tl`, `lines[].tlc{N}`, `lines[].edit{N}`
- Manifest step data: `Translation.tokens_used`, `Translation.cost`

#### Retry Strategies

| Strategy | Behavior |
|----------|----------|
| batch | Retry entire chunk on failure |
| contextual | Retry failed lines with surrounding context |
| isolated | Retry each failed line individually |
| skip | Skip failed lines, continue processing |

#### API Request Format

```json
{
  "model": "gpt-4o-mini",
  "messages": [
    {"role": "system", "content": "[Translation instructions]"},
    {"role": "user", "content": "[Lines to translate]"}
  ],
  "response_format": {"type": "json_object"},
  "temperature": 0.3
}
```

---

### Step 6: Quality Assurance

**Purpose**: Validate translation quality and flag issues.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Run QA Checks Button | Button | Execute validation |
| Export Report Button | Button | Save QA report to file |
| Refresh Button | Button | Reload translation data |
| Filter Radios | RadioGroup | all/errors/warnings/unfixed/accepted/rejected |
| Lines Table | SharedTable | Lines with issue counts |
| Accept Selected Button | Button | Mark lines as accepted |
| Reject Selected Button | Button | Mark lines for re-translation |
| Auto-fix Selected Button | Button | Apply automatic fixes |
| Rules Panel | Frame | Enable/disable validation rules |
| Issue Details Panel | Frame | Show issues for selected line |
| Fix Suggestions List | Listbox | Suggested fixes for issues |

#### Data Flow

**Inputs**:
- From Step 4: `prepro[]`, `prepro_ops[]` (for placeholder checking)
- From Step 5: `tl[]` (translation results)

**Processing** (via `functions/validation.py`):
1. **Placeholder Check**: Verify all `__PROT__` tokens preserved
2. **Anchor Check**: Verify `<>[]{}` characters preserved
3. **Japanese Check**: Flag remaining Japanese characters
4. **Speaker Format**: Verify `Name: "Dialogue"` preserved
5. **Quote Balance**: Check matching quote pairs
6. **Empty Check**: Flag empty translations
7. **Line Length**: Flag lines exceeding limit

**Outputs**:
- `issues: List[QAIssue]` - All detected issues
- `lines: List[QALine]` - Lines with issue status
- `error_count: int` - Critical issues
- `warning_count: int` - Non-critical issues
- `accepted: List[int]` - User-accepted lines
- `rejected: List[int]` - Lines marked for retry

**Stored In**:
- Manifest step data (step_id=6)
- Issue list and acceptance status

#### Validation Rules

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

### Step 7: Postprocessing

**Purpose**: Restore protected content and apply final transformations.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Apply Postprocessing Button | Button | Execute restoration |
| Refresh Button | Button | Reload translation data |
| Revert All Button | Button | Undo postprocessing |
| Filter Radios | RadioGroup | all/changed/retry/skipped |
| Lines Table | SharedTable | Translated vs postprocessed |
| Placeholder Recovery Checkbox | Checkbox | Restore __PROT__ tokens |
| Bracket Recovery Checkbox | Checkbox | Fix bracket balance |
| Quote Recovery Checkbox | Checkbox | Fix quote balance |
| Whitespace Normalization Checkbox | Checkbox | Clean whitespace |
| Symbol Conversion Checkbox | Checkbox | Convert symbols |
| Fullwidth→Halfwidth Checkbox | Checkbox | Convert fullwidth chars |
| BR Tag Restoration Checkbox | Checkbox | Restore line break tags |
| Failure Policy Dropdown | Combobox | skip/flag/retry |
| Diff View Pane | Text | Show changes between translated and postprocessed |
| Character Validation Panel | Frame | Validate character/word issues |

#### Data Flow

**Inputs**:
- From Step 4: `prepro_ops[]` (restoration metadata)
- From Step 5: `tl[]` (or `tlc[]`, `edit[]` if available)

**Processing** (via `functions/postprocess.py`):
1. For each line with `prepro_ops`:
   a. Find `__PROT__` tokens in translation
   b. Match to original protected content
   c. Replace token with original
2. Apply bracket/quote recovery if enabled
3. Apply symbol conversion if enabled
4. Validate character/word consistency
5. Track recovery success/failure

**Outputs**:
- `postpro: List[str]` - Restored lines
- `recovery_stats: RecoveryStats` - Success/failure counts
- `retry_list: List[int]` - Lines needing re-translation
- `validation_result` - Character/word validation

**Stored In**:
- Manifest: `lines[].postpro`
- Manifest step data: `Postprocessing.recovery_rate`

#### Recovery Types

| Type | Description |
|------|-------------|
| PLACEHOLDER_CASE | Fix __prot__ → __PROT__ |
| PLACEHOLDER_MANGLED | Fix __PRO_T__ etc. |
| PLACEHOLDER_MISSING | Flag for manual fix |
| BRACKET_BALANCE | Fix unmatched brackets |
| QUOTE_BALANCE | Fix unmatched quotes |
| BR_TAG | Restore [br] or \n tags |
| SPEAKER_FORMAT | Restore Name: prefix |

---

### Step 8: Wordwrap

**Purpose**: Format text for game engine requirements.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Apply Wordwrap Button | Button | Execute wrapping |
| Preview Button | Button | Show wrap preview |
| Mode Dropdown | Combobox | manual/rpgmaker/disabled |
| Format Dropdown | Combobox | RPG Maker MV/MZ, Ren'Py, etc. |
| Width Spinbox | Spinbox | Characters per line |
| Max Lines Spinbox | Spinbox | Maximum lines (0=unlimited) |
| Break Character Entry | Entry | Line break sequence (\n, [br]) |
| Speaker Mode Dropdown | Combobox | ignore/sameline/indent/newline |
| Prevent Orphan Checkbox | Checkbox | Avoid single-word final lines |
| Prefer Punct Breaks Checkbox | Checkbox | Break at punctuation |
| Ignore Patterns Checkboxes | Checkboxes | Ignore <>, [], {}, en() |
| Lines Table | SharedTable | Original vs wrapped |
| Overwrite Strategy Dropdown | Combobox | overwrite/backup/merge/skip |
| Merge Method Dropdown | Combobox | replace_all/replace_changed/append |
| Typography Style Dropdown | Combobox | western/japanese/chinese |

#### Data Flow

**Inputs**:
- From Step 7: `postpro[]` (or best available from chain)

**Processing** (via `functions/wordwrap.py`):
1. For each line:
   a. Measure character width (considering fullwidth)
   b. Find optimal break points
   c. Insert break characters
   d. Handle speaker prefix per mode
   e. Apply typography rules
2. Calculate wrap statistics

**Outputs**:
- `wordwr: List[str]` - Wrapped lines
- `wrap_stats: WrapStats` - Lines wrapped, exceeding
- `break_positions: List[List[int]]` - Break points per line

**Stored In**:
- Manifest: `lines[].wordwr`
- Manifest step data: `Wordwrap.width`, `Wordwrap.format`

#### Format Presets

| Format | Width | Break | Max Lines |
|--------|-------|-------|-----------|
| RPG Maker MV | 48 | \n | 4 |
| RPG Maker MZ | 55 | \n | 4 |
| Ren'Py | 60 | \n | 0 |
| TyranoScript | 45 | [r] | 0 |

---

### Step 9: Output

**Purpose**: Generate output files and inject translations into copies of originals.

#### Widgets

| Widget | Type | Function |
|--------|------|----------|
| Export All Button | Button | Write all output files |
| Cancel Button | Button | Stop export |
| Refresh Preview Button | Button | Recalculate output files |
| Filter Radios | RadioGroup | all/pending/written/failed |
| Files Table | SharedTable | Source → output mapping |
| Format Dropdown | Combobox | txt/csv/tsv/json/xlsx |
| Destination Entry | Entry | Output directory path |
| Browse Button | Button | Select output directory |
| Naming Strategy Dropdown | Combobox | suffix/prefix/replace/subfolder |
| Suffix/Prefix Entry | Entry | Text to add to filename |
| Pair Mode Dropdown | Combobox | translated_only/side_by_side/interleaved |
| Backup Strategy Dropdown | Combobox | none/timestamp/numbered |
| Preserve Structure Checkbox | Checkbox | Maintain folder hierarchy |
| Overwrite Checkbox | Checkbox | Overwrite existing files |
| Export Manifest Checkbox | Checkbox | Include manifest in export |
| Export Logs Checkbox | Checkbox | Include logs in export |

#### Injection Mode (Primary Use Case)

The primary purpose of Output is to **inject** translated text back into copies of the original files:

1. Original files are copied to the output directory (non-destructive)
2. Translated text replaces original text at the corresponding positions
3. File structure, formatting, and non-text content are preserved
4. Uses `file_dir[]` from Input step to map lines back to source files

#### Data Flow

**Inputs**:
- From Manifest: `file_dir[]` (source file mapping)
- From Lines: `overwrite[]` or `wordwr[]` or `postpro[]` (final output)
- Config: Format, naming, destination options

**Processing** (via `formats/` handlers):
1. Resolve final output text per line (`get_final_output()`)
2. Map lines back to source files via `file_dir`
3. Copy original file to output location
4. Inject translations at correct positions
5. Create backup if enabled
6. Update export statistics

**Outputs**:
- Output files with injected translations
- `export_stats: ExportStats` - Files written/failed/skipped
- Backup files if enabled
- Manifest export if enabled

**Stored In**:
- Manifest step data: `Output.files_written`, `Output.format`

#### Naming Strategies

| Strategy | Example |
|----------|---------|
| suffix | input.txt → input_translated.txt |
| prefix | input.txt → translated_input.txt |
| replace | input.txt → output.txt |
| subfolder | input.txt → translated/input.txt |

#### Pair Modes

| Mode | Output Format |
|------|---------------|
| translated_only | Only translated text |
| side_by_side | Original\tTranslated columns |
| interleaved | Original line, then translated line |
| separate_files | Two files: original and translated |

---

## 6. CLI Mode: Automatic Pipeline

CLI mode provides fully automated translation without GUI interaction.

### 6.1 Commands

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

### 6.2 Translate Command Options

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

### 6.3 Automatic Pipeline Flow

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

### 6.4 Progress Display

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

## 7. Manifest Structure

The manifest (`.CherryAI.json`) is the single source of truth for project state.

### 7.1 Top-Level Structure

```json
{
  "version": "3.2",
  "project_info": { /* ProjectInfo */ },
  "glossary": { /* GlossaryConfig */ },
  "source_root": "C:/path/to/source",
  "file_dir": [ /* FileDirEntry[] */ ],
  "lines": [ /* LineEntry[] */ ],
  "operations": [ /* Operation[] */ ],
  "steps": [ /* StepState[] */ ],
  "created_at": "2026-01-31T12:00:00Z",
  "updated_at": "2026-01-31T14:30:00Z"
}
```

### 7.2 LineEntry Structure

```json
{
  "idx": 0,
  "orig": "Original Japanese text",
  "prepro": "Preprocessed text with __PROT__",
  "prepro_ops": [{"type": "protect", "original": "\\V[1]", "pos": 15}],
  "tl": "Translated English text",
  "postpro": "Restored translated text with \\V[1]",
  "wordwr": "Word-wrapped\ntext",
  "overwrite": null
}
```

### 7.3 Field Progression

```
orig → prepro → edited_prepro → tl → tlc1 → edit1 → tlc2 → ... → postpro → wordwr → overwrite
```

Resolution methods:
- `get_input_for_translation()`: edited_prepro → prepro → orig
- `get_input_for_tlc(N)`: edit{N-1} → tlc{N-1} → ... → tl
- `get_input_for_postprocessing()`: Latest in TLC/Edit chain → tl → prepro → orig
- `get_final_output()`: overwrite → wordwr → postpro

---

## 8. Processing Modules Reference

### 8.1 functions/ Modules

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
| `rate_limiter.py` | API rate limiting |
| `request_cache.py` | Request caching |
| `prompt_builder.py` | Translation prompt construction |
| `manifest_manager.py` | Unified state management |

### 8.2 modi/ Modules (Pre/Post Processing)

| Module | Purpose |
|--------|---------|
| `standard_mode.py` | Ellipsis, symbols, PROT compression |
| `protect_code.py` | Code pattern protection |
| `custom_placeholder.py` | Custom pattern→token replacement |
| `temporary_replacement.py` | Temp replacement with restore |
| `anchor_equivalence.py` | Anchor pattern handling |
| `speaker_replacement.py` | Speaker name handling |

### 8.3 formats/ Modules (File I/O)

| Module | Purpose |
|--------|---------|
| `txt.py` | Plain text files |
| `csv_handler.py` | CSV/TSV files |
| `json_handler.py` | JSON files |
| `xlsx.py` | Excel files |
| `rpgmaker.py` | RPG Maker data (placeholder) |

### 8.4 gui/helpers/ Modules (Adapters)

| Module | Purpose |
|--------|---------|
| `mode_adapter.py` | Bridge GUI → modi/ modules |
| `analysis_adapter.py` | Bridge GUI → analysis functions |
| `chunker_adapter.py` | Bridge GUI → chunker functions |
| `glossary_adapter.py` | Bridge GUI → glossary functions |
| `prompt_adapter.py` | Bridge GUI → prompt builder |
| `manifest_binding.py` | Widget ↔ manifest field binding |

---

## Document Revision History

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-02-01 | Updated Step 1 (Analysis) with QoL future improvements. Renamed Step 2 from Estimation to Costs with comprehensive spec including: dual estimation workflow (Original + Preprocessed), Tokens/Request limit, prompt overhead calculation, model comparison expanded fields, time estimation with concurrent requests. Updated data flow and automation triggers. |
| 2.0 | 2026-02-01 | Major revision: Updated Step 0 (Input) spec with unified file selector, collapsible folder tree, format filtering, progress window, removed redundant buttons. Updated step names (Wordwrap, Output). Added automation triggers and pipeline overview. |
| 1.0 | 2026-01-31 | Initial comprehensive specification |
