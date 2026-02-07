# CherryAI Specification Document

Version 2.0 | February 2026

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

**Design Goal**: Extract only visible text from any unencrypted text file that a user can theoretically read. Code not part of the text and any other non-translatable content should be excluded. In the final step (Output), translated text is injected into copies of the original files to replace the original text (non-destructive).

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

**Purpose**: Configure project metadata and translation context. All fields contribute to building the final translation prompt. Every entry is saved in the manifest for persistence.

#### Design Goals

1. **Prompt Construction**: Every relevant field feeds into the translation prompt sent to the LLM
2. **Project Persistence**: All data saved to manifest for session recovery
3. **Glossary Integration**: Project-specific and global glossaries support selective prompt inclusion
4. **Code Pattern Management**: Detected patterns from Analysis can be managed with preservation rules

---

#### Widget: Project Details

**Purpose**: Core project identification fields.

| Field | Type | Behavior | Prompt Format |
|-------|------|----------|---------------|
| Project Name | Entry | Auto-populated from first file load; user-editable | Not included in prompt |
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
| Summary Text | ScrolledText | Multi-line input, 5 rows default height |
| Description | Label | "Provide a brief summary for translation context" |

**Prompt Format**: `Summary: [contents]`

**Required Behavior**:
- Widget title rename: "Summary / Description" → "Summary"
- Contents included in system prompt when non-empty

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
- Each preset has a Custom Text entry below it
- If Custom Text is filled: Dropdown becomes visually grayed (disabled appearance), only Custom used in prompt
- If Custom Text is empty/deleted: Dropdown becomes active, preset used in prompt

**Prompt Format**:
- Style: `Style: [Full Display Text or Custom Value]`
- Tone: `Tone: [Full Display Text or Custom Value]`

**Manifest Keys**: `StylePreset`, `CustomStyle`, `TonePreset`, `CustomTone`

---

#### Widget: System Instructions (rename from Prompt)

**Purpose**: User-defined additional instructions for the LLM.

| Component | Type | Behavior |
|-----------|------|----------|
| Instructions Text | ScrolledText | Multi-line input, 6 rows default |
| Description | Label | "Additional instructions for the translation AI" |

**Required Rename**: "Prompt" → "System Instructions"

**Prompt Format**: `System Instructions: [contents]`

**Manifest Key**: `SystemInstructions` (rename from `Prompt`)

**Future Enhancement**: Save/Load buttons for instruction templates

---

#### Widget: Glossary Settings (Selective Glossary)

**Purpose**: Manage translation glossary with selective prompt inclusion.

| Component | Type | Function |
|-----------|------|----------|
| Glossary Table | Treeview | 3 columns: Original, Translation, Notes |
| Import from Analysis | Button | Import detected terms from Analysis step |
| Add Entry | Button | Add new glossary entry |
| Edit Entry | Button | Edit selected entry |
| Remove Entry | Button | Remove selected entry(s) |

**Table Behavior**:
- Inline editing: Double-click any cell to edit directly (no separate dialog)
- Multi-select support for bulk delete
- Columns: Original (source term), Translation (target term), Notes (context/usage)

**Selective Prompt Inclusion**:
- Glossary entries only included in prompt when their Original term appears in the current chunk
- Reduces token usage by excluding irrelevant entries
- Format in prompt: `Glossary:\n- [Original]: [Translation] ([Notes])`

**Project vs Global Glossary**:
- Project glossary: Stored in manifest, project-specific
- Global glossary: Stored in `user/glossary.csv`, shared across projects
- Analysis creates project-specific glossary entries

**Manifest Key**: `Glossary.project_entries[]`

---

#### Widget: Code Database (rename from Code Glossary)

**Purpose**: Manage code patterns for preservation, translation, or removal.

| Component | Type | Function |
|-----------|------|----------|
| Pattern Table | Treeview | Columns: Pattern, Category, Action, Code Examples |
| Add Pattern | Button | Open pattern editor dialog |
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
- Categories enable selective import/export from Global Database

**Manifest Key**: `CodeGlossary[]` (array of CodePattern objects)

---

#### Widget: Global Glossary and Database (NEW)

**Purpose**: Manage global resources shared across all projects.

**Mode Switch**: Toggle between Glossary Mode and Code Mode

**Glossary Mode**:
| Component | Type | Function |
|-----------|------|----------|
| Use Global Glossary | Checkbox | Include global glossary during translation |
| Export to Global | Button | Export selected project entries (or all if none selected) to global |
| Display Global | Button | Open window with interactive global glossary table |

**Code Mode**:
| Component | Type | Function |
|-----------|------|----------|
| Category Filter | Combobox | Filter by category for selective import |
| Import from Global | Button | Import filtered patterns to project |
| Export to Global | Button | Export project patterns to global database |
| Display Global | Button | Open searchable global code database window |

**Uniqueness Rules**:
- Project Code Database: Same Code+Pattern can only exist once
- Global Code Database: Same Code+Pattern can exist multiple times under different Categories
- Global Database is searchable by pattern, code, category, notes

**File Locations**:
- Global Glossary: `user/glossary.csv`
- Global Code Database: `user/code_patterns.db` (SQLite) or `user/code_patterns.json`

---

#### Character Notes Widget

**Purpose**: Track characters for consistent translation.

| Component | Type | Function |
|-----------|------|----------|
| Character Table | Treeview | Columns: Original, Translation, Gender, Role |
| Add Character | Button | Add new character entry |
| Edit | Button | Edit selected character |
| Remove | Button | Remove selected character(s) |
| Infer Gender | Button | LLM-based gender inference |
| Import from Analysis | Button | Import detected speakers |

**Prompt Format**: Character entries included as context:
```
Characters:
- [Original] ([Translation]): [Gender], [Role]
```

**Manifest Key**: `CharacterNotes[]`

---

#### Data Flow

**Inputs**:
- User: Manual entry of all fields
- From Step 1: Detected speakers (populate Characters), detected code patterns (populate Code Database)
- From Global: `user/glossary.csv`, `user/code_patterns.db`

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
- Manifest: `project_info{}`, `Glossary{}`, `CodeGlossary[]`, `CharacterNotes[]`
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

---

#### Known Issues to Fix

1. **Genre Dialog Overwrites**: Currently replaces field content instead of appending
2. **Import from Analysis (Code)**: Button not functional - needs implementation
3. **Import from Analysis (Glossary)**: Button not functional - needs implementation
4. **"Other" Language**: Does not prompt for custom input
5. **Custom Style/Tone Graying**: Visual feedback not implemented

---

### Step 4: Preprocessing

**Purpose**: Process text before translation with transformations that will be exactly mirrored and restored in Step 7: Postprocessing. Each process has a priority integer determining execution order. Preprocessing reduces tokens, protects code, and normalizes text while ensuring perfect reversibility.

**Design Goals**:
1. **Mirror Symmetry**: Every Preprocessing transformation has a corresponding Postprocessing restoration
2. **Priority Ordering**: Processes execute in defined order; each `modi/` module has a priority integer
3. **Perfect Reversibility**: All changes must be recoverable to produce accurate final output
4. **Token Efficiency**: Reduce tokens sent to LLM to minimize costs
5. **Code Protection**: Ensure code and placeholders survive translation unchanged

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
| PROT Token Compression | Checkbox | ✓ | Compress adjacent `__PROT__` tokens |
| Speaker Name Replacement | Checkbox | ✗ | Replace speaker names with glossary translations |
| Code Spacing Rules | Checkbox | ✓ | Apply code-aware spacing normalization |

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

#### Process: PROT Token Compression

**Priority**: 60 (Runs AFTER Protect Code Patterns creates `__PROT__` tokens)

**Purpose**: Compress adjacent `__PROT__` tokens into a single numbered token to reduce token count.

**Behavior**:
- `__PROT____PROT__` → `__PROT_2__`
- `__PROT____PROT____PROT__` → `__PROT_3__`
- Only compresses tokens that are directly adjacent (no whitespace between)
- Records compression mapping for restoration

**Postprocessing**: Decompress `__PROT_N__` back to N individual `__PROT__` tokens BEFORE replacing with originals

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
- Replaces Pattern with a unique `__CUSTOM_{idx}__` token
- If RegEx enabled: Pattern interpreted as regular expression
- If RegEx disabled: Pattern is literal string match
- Stores original text for restoration

**Postprocessing Priority**: 30 (Restored AFTER Anchoring, BEFORE standard restoration)

**Use Cases**:
- Name variables: `{PLAYER_NAME}` → `__CUSTOM_1__`
- Recurring terms that should not be translated
- Company/product names that need consistent handling

**Manifest Key**: `CustomPlaceholders` (list of `{pattern, placeholder, is_regex, description}`)

---

#### Widget: Protect Code Patterns

**Purpose**: Define patterns that should be protected with standard `__PROT__` tokens.

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
- Replaces matched patterns with `__PROT__` token
- Default: RegEx enabled (patterns are regular expressions)
- If RegEx disabled: Pattern is literal string match
- Each match gets same `__PROT__` token (compression handles duplicates)
- Original text stored in `prepro_ops[]` for restoration

**Postprocessing Priority**: 20 (Restored after PROT decompression)

**Validation (QA Step)**:
- Checks that all `__PROT__` tokens exist in translation
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
- Removes matched pattern completely from the line
- Stores removal position relative to anchors (start, end, punctuation, brackets)
- Does NOT leave any placeholder token in text
- Anchor characters: Line start `^`, Line end `$`, Punctuation `.!?`, Brackets `[]<>{}`

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
| Protected | Only lines with `__PROT__` tokens |
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
| 40 | Speaker Name Replacement | Replace speaker names |
| 50 | Code Spacing Rules | Normalize code spacing |
| 60 | PROT Token Compression | Compress adjacent PROTs (runs after patterns create them) |
| 70 | Custom Placeholders | Apply user-defined patterns |
| 75 | Anchoring | Remove anchored content |
| 80 | Protect Code Patterns | Protect remaining code |

**Postprocessing** (reverse order - highest priority runs first):
| Priority | Process | Description |
|----------|---------|-------------|
| 10 | Anchoring | Restore anchored content FIRST |
| 20 | Protect Code Patterns | Restore `__PROT__` tokens |
| 30 | Custom Placeholders | Restore custom tokens |
| 40 | PROT Token Decompression | Decompress `__PROT_N__` |
| 50 | Code Spacing Rules | Restore code spacing |
| 60 | Speaker Name Replacement | (No restoration needed) |
| 70 | Symbol Conversion | Optionally restore JP symbols |
| 80 | Ellipsis Expansion | Restore ellipsis length |
| 90 | Deduplication | Apply translation to all duplicates LAST |

---

#### Data Flow

**Inputs**:
- From Step 0: `all_lines[]` - Original lines from loaded files
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
- `dedup_map: Dict[str, List[int]]` - Line text → list of duplicate indices
- `change_count: int` - Total lines modified
- `protected_count: int` - Lines with `__PROT__` tokens
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
- All `__PROT__` tokens present in translation
- All `__CUSTOM__` tokens present in translation
- Anchor points exist for restoration
- No extra/duplicate tokens introduced
- Speaker format preserved

**Recovery Strategies** (applied in Postprocessing):
1. **Exact Match**: Token found at expected position
2. **Case Recovery**: `__prot__` → `__PROT__` (fix and proceed)
3. **Mangled Recovery**: `__PRO T__` or `__PROT _` (pattern match and fix)
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
3. **Prompt Editor Widget** - Preview button for constructed prompt; Ban Tokens separated
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
| Model | Dropdown | Mock Translation | Select LLM model from configured providers |
| Temperature | Spinbox | 0.2 | Set generation temperature (0.0-2.0) when model supports it |
| Lines/Chunk | Spinbox | 30 | Lines per API request (5-200). Must sync with Estimation step |
| Retry Strategy | Dropdown | Batch | How failures are retried (Batch, Contextual) |
| Max Retries | Spinbox | 3 | Round trips of retries (0 = none) |
| Skip Non-Source Language | Checkbox | ✗ | Skip lines not detected as source language |

**Model Selection**:
- Models are **not** a hardcoded list. They come from Global Options where the user configures API Providers (Name, URL, Key, Model).
- Without any configured providers, the only available option is **"Mock Translation"**.
- Mock Translation: Initially produces nonsense output (using a script to replace words with others from a limited list randomly, languages like Japanese have custom settings). Future improvement: use NMT (Neural Machine Translation) engine for basic translation.
- The dropdown displays the provider Name field from Global Options.

**Lines/Chunk Sync with Estimation**:
- Lines/Chunk must have parity with the Estimation step (Step 2: Costs).
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

#### Widget: Prompt Editor

**Purpose**: Preview the constructed translation prompt. The Prompt Editor does NOT build its own prompt — it reads all relevant data from the manifest (Summary, Style, Tone, System Instructions, Glossary, Code Database, Conditional Prompts) and constructs a preview.

**Change from Current**: The Prompt Editor is reduced to a **single Preview button** and Renamed to **Prompt Preview** plus a separated Ban Tokens field. It must NOT contain its own Summary, Style, or Glossary inputs — those are managed in Step 3: Information and stored in the manifest. The Prompt Editor reads from the manifest to show the complete prompt but formatted for readability (##NAMEINCAPS shows Source but are not sent in the request).

**UI Components**:
| Component | Type | Function |
|-----------|------|----------|
| Preview Prompt Button | Button | Opens a read-only dialog showing the full constructed prompt |
| Ban Tokens Entry | Entry | Comma-separated token ban list (em_dash, smart_quotes, etc.) |
| Ban Tokens Preset Dropdown | Combobox | Quick-select common ban presets |

**Preview Dialog** (opened by button):
- Shows the complete system prompt as it would be sent to the LLM
- Read-only text area with syntax highlighting for different prompt sections
- Token count estimate for the prompt (header showing total tokens and breakdown)
- Sections: System Instructions, Game Summary, Translation Style, Glossary (selective), Code Database (selective), Conditional Prompts (if triggered), Rolling Context sample

**Ban Tokens**:
- Separated from the Prompt Editor into its own clearly labeled section
- Entry field for comma-separated token names
- Dropdown with presets: "None", "Clean English" (em_dash, smart_quotes), "Strict" (em_dash, smart_quotes, ellipsis_variants)
- Applied via logit bias in the API request
- Manifest Key: `RequestOptions.BanTokens`, `RequestOptions.BanTokenPreset`

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

**Progress Window** (modal, opens during translation):
- Progress bar with percentage
- ETA and token speed (tok/s)
- Lines translated / remaining / failed counts
- Chunk progress (current chunk / total chunks)
- Pause/Resume/Cancel controls
- Inline scrollable log pane showing per-chunk status messages

---

#### Mock Translation

**Purpose**: Default translation mode when no API providers are configured. Allows full pipeline testing without API costs.

**Behavior**:
- Available as the only Model option when no providers exist in Global Options
- Produces deterministic nonsense output (word reversal, character substitution, or lorem ipsum insertion)
- Preserves all `__PROT__`, `__DEDUP__`, `__CUSTOM__` tokens in output
- Simulates realistic timing (configurable delay per chunk / total time)
- Tracks mock token counts for cost estimation testing
- Does NOT require API key or network connectivity

**Future Improvement**: Replace nonsense output with NMT (Neural Machine Translation) engine for basic but meaningful translation.

**Manifest Key**: `RequestOptions.Model` = "mock" when Mock Translation is selected

---

#### Data Flow

**Inputs**:
- From Step 4: `prepro[]` (preprocessed lines) — preferred
- From Step 0: `orig[]` (original lines) — fallback if no preprocessing
- From Step 3 (via manifest): Summary, Style, Tone, System Instructions, Glossary, Code Database
- From Global Options: API Provider config (URL, Key, Model), Caching mode, Rolling Context, Thinking Mode

**Processing** (via `functions/api_client.py` or Mock Translation):
1. Build translation prompt from manifest data via `functions/prompt_builder.py`
2. Determine input: use `get_input_for_translation()` per line (edited_prepro → prepro → orig)
3. Optionally skip lines not in source language (language detection)
4. Chunk lines by configured Lines/Chunk size
5. For each chunk:
   a. Check line cache for existing translations (if caching enabled)
   b. Apply rate limiting (from Global Options RPM setting)
   c. Build chunk-specific prompt (include rolling context if enabled)
   d. Send to LLM API with JSON response format (or Mock Translation)
   e. Parse response, map translated lines back to source indices
   f. Handle failures per retry strategy (Batch or Contextual)
   g. Update progress display and API Usage widget
   h. Save translations to manifest after each chunk (crash resilience)
   i. Populate line cache with new translations
6. Track token usage and costs
7. On completion: update manifest step data with totals

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

```json
{
  "model": "gemini-2.0-flash",
  "messages": [
    {"role": "system", "content": "[Full system prompt from prompt_builder]"},
    {"role": "user", "content": "[Lines to translate as numbered JSON]"}
  ],
  "response_format": {"type": "json_object"},
  "temperature": 0.2
}
```

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

**Test Files** (to be created/extended):
- `dev/test_translation_performance.py`
- `dev/test_mock_translation.py`
- `dev/test_translation_retry.py`
- `dev/test_translation_cache.py`
- `dev/test_translation_prompt.py`

---

### Step 6: Quality Assurance

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
- From Step 5: `tl[]` (translation results), `edit{N}[]`, `tlc{N}[]` (when Edit/TLC modes exist)

**Processing** (via `functions/validation.py`):
1. **Placeholder Check**: Verify all `__PROT__` tokens preserved
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
| 2.5 | 2026-02-07 | Step 5 (Translation): Added Translation/Edit/TLC Mode Toggle to Hidden (Future Improvement) — three-way toggle with line-matching strategy design challenge. Step 6 (Quality Assurance): Complete rewrite — defined purpose as safety net for issues automatic recovery couldn't fix, added philosophy section, specified placeholder toggle mode (current state), preserved full widget spec and validation rules as future reference, added Edit/TLC filtering note. |
| 2.4 | 2026-02-07 | Comprehensive update to Step 5 (Translation): Complete widget specifications for Translatable Lines (merged Original/Preprocessed into "To be Translated"), Request Options (Model from Global Options providers, Mock Translation default, Lines/Chunk sync with Estimation, Retry Strategy details for Batch/Contextual, Skip Non-Source Language), Prompt Editor (preview-only button, Ban Tokens separated), API Usage (live metrics). Added performance requirements (< 1s load for 100K lines, virtual scrolling, tab caching). Moved Request Caching, Extended Thinking, and Rolling Context to Global Options. Hidden Edit Before Translation and Line-by-Line Mode as Future Improvements. Added Mock Translation specification. |
| 2.3 | 2026-02-03 | Comprehensive update to Step 4 (Preprocessing): Complete widget specifications for Standard Rules Panel, Custom Placeholders, Protect Code Patterns, and Anchoring (renamed from Anchor Removal). Added detailed process specifications with priority ordering, execution order documentation, Preprocessing↔Postprocessing mirror symmetry, validation and recovery strategies, RegEx toggle support for all pattern widgets, Preview Table with filtering, and comprehensive testing requirements. |
| 2.2 | 2026-02-01 | Updated Step 3 (Information) with comprehensive widget specifications: Project Details (Name, Title, Genre with ADD behavior), Languages (Source/Target with "Other" custom input), Summary (renamed), Translation Style and Tone (dropdown graying with custom override), System Instructions (renamed from Prompt), Glossary Settings (3-column editable table, selective glossary), Code Database (renamed from Code Glossary, Preserve/Translate/Remove actions), and NEW Global Glossary and Database widget. Added prompt formats and manifest keys for all widgets. |
| 2.1 | 2026-02-01 | Updated Step 1 (Analysis) with QoL future improvements. Renamed Step 2 from Estimation to Costs with comprehensive spec including: dual estimation workflow (Original + Preprocessed), Tokens/Request limit, prompt overhead calculation, model comparison expanded fields, time estimation with concurrent requests. Updated data flow and automation triggers. |
| 2.0 | 2026-02-01 | Major revision: Updated Step 0 (Input) spec with unified file selector, collapsible folder tree, format filtering, progress window, removed redundant buttons. Updated step names (Wordwrap, Output). Added automation triggers and pipeline overview. |
| 1.0 | 2026-01-31 | Initial comprehensive specification |
