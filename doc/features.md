CHERRYAI - USER GUIDE

A Tool to Prepare Text for AI Translation

=============================================================================

AI AGENT INSTRUCTIONS
---------------------
This document describes CherryAI's USER-FACING FEATURES and CAPABILITIES.
When implementing or modifying features:
- ALL processing logic belongs in `functions/` (36 modules) or `modi/` (12 modes)
- GUI code (gui/) should ONLY handle display and user interaction
- CLI code shares the same `functions/` modules as GUI
- Check the TABLE OF CONTENTS below to find relevant feature documentation
- Cross-reference with `technical.md` for implementation details

VERIFIED MODULE COUNTS (January 2026):
- functions/: 40 modules (+ glossaries/ subfolder with 6 files)
- modi/: 12 processing modes
- formats/: 5 format handlers
- gui/steps/: 10 workflow tabs
- gui/helpers/: 6 adapter modules
- gui/dialogs/: 5 dialog modules (global_options, project_dialog, loading_progress, input_dialog, password_dialog)
- gui/widgets/: 1 widget module (password_strength)

For module-level documentation, see: doc/technical.md
For test documentation, see: doc/tests.md
For outstanding work, see: doc/todo.md

=============================================================================

TABLE OF CONTENTS
-----------------

1. OVERVIEW
   - What is CherryAI?
   - The Basic Workflow (Batch Processing)
   - What Can the Tool Protect?

2. KEY FEATURES
   - Integrated AI Translation
   - Command Line Interface (CLI)
   - File Format System
   - Conditional Prompt Instructions
   - API Response Validation
   - Analysis Tool
   - Templates & Manifests
   - Glossary & Automatic Detection
   - Game Summary & Project Context
   - Translation Style Guide
   - Rolling Context
   - Model Presets
   - Local LLM Support
   - Partial Translation Mode
   - Speaker Format Preservation
   - Extended Line Tags & Auto-Tagging

3. GUI v2 ARCHITECTURE (10-Step Workflow)
   - Step 1: Input & Extraction
   - Step 2: Analysis
   - Step 3: Information (Metadata & Inference)
   - Step 4: Preprocessing
   - Step 5: Costs
   - Step 6: Translation
   - Step 7: Postprocessing
   - Step 8: Wordwrap & Overwrite
   - Step 9: Quality Assurance
   - Step 10: Output & Injection
   - Global Options Dialog
   - Theme & Icons System

4. ADVANCED FEATURES
   - Request Caching System
   - Prompt Caching (OpenAI)
   - Progress Indicators
   - Rate Limit Management
   - Adaptive Chunk Sizing
   - Speaker Quote Stripping
   - Token-Based Chunking
   - Persistent API Logging
   - Automatic Line Recovery
   - Retry Strategy Options
   - Line-by-Line Translation Mode
   - Translation Style Presets
   - Context Markers
   - Parser Scripts
   - Width Conversion
   - Aggressive Deduplication
   - Point of View Inference
   - Consistency System
   - Mock Translation (Flaw Testing)

5. MANIFEST v3.1 - PROFESSIONAL TRANSLATION WORKFLOW
   - How It Works
   - PREPRO_OPS: Per-Line Operation Metadata
   - The Workflow Stages
   - Quality Check Cycles
   - GUI Project Integration (v3.1)
   - Project File Staging (v3.1)

6. UPDATING TRANSLATIONS FOR PATCHED GAMES

7. FILE FORMATS SUPPORTED

8. SAVING YOUR WORK
   - Manifests & Templates
   - Config File & API Configuration
   - Options Dialog

9. HOW TO USE - STEP BY STEP
   - First Time Setup
   - Setting Up Protection Rules
   - Before Sending to AI
   - After AI Translation

10. ANALYSIS - UNDERSTANDING YOUR FILE

11. GLOSSARY - AUTOMATED LEARNING
    - Automatic Detection
    - Building Your Glossary
    - Enhanced Gender Inference
    - Optional LLM Enhancement

12. COMMON SCENARIOS & TIPS

13. FAQ

14. COMMAND LINE INTERFACE (CLI)
    - Estimate Cost
    - 1-Click Translate
    - Diagnostic Test

15. TESTING
    - Run from `utility` root: `python -m pytest CherryAI/dev/ -v --timeout=10`
    - See `doc/tests.md` for details.

=============================================================================

WHAT IS CHERRYAI?

CherryAI is a sophisticated framework that helps you prepare text before sending it to an AI language model for translation. It uses scripts and optionally AI to help with the translation work before, during and afterward.

Think of it like this:
- BEFORE: You have text with code, proper names, formatting
- WITH THE FRAMEWORK: Prepare the text and sent it to the AI with detailed and customized instructions to then also process it afterwards.
- AFTER: Get back the translated text in the very same format you put it in 

The framework removes or protects things the AI shouldn't touch (like code), 
then adds them back correctly after translation. During translation it provides critical context and instructions to ensure a high-quality translation. Optionally this includes Translation Checks and Editing.

=============================================================================

THE BASIC WORKFLOW (Batch Processing)

CherryAI is built on **batch processing**: you can load one or multiple files and apply the same rules to all of them at once.

1. Load Files (Single, Multiple, or Folder)
   - Click "Input" button to open unified file/folder selection dialog
   - Select one or more files: .txt, .csv, .tsv, .json, .xlsx, .rpgmaker, or image files
   - Folder loading shows collapsible folder hierarchy in a Treeview (folders above files, collapsed by default)
   - Auto-encoding detection (BOM → utf-8 → shift_jis → fallback)
   - Format filtering: when format is forced, non-matching files are refused
   - Progress dialog shown when loading >3 files
   - Shows "N files selected" if you picked multiple files
   - Single file is treated as a batch of 1

2. Set Up Protection Rules
   - Tell the tool what to protect (code, names, special patterns)
   - Choose how to handle different content
   - Rules apply to all loaded files

3. Prepare Text (Pre-Translation) - Batch Process
   - Click "Process Pre-TL"
   - Tool processes ALL loaded files:
     * Removes/replaces protected content with placeholders
     * Generates one output file per input file
     * Uses progress bar to show status across files
     * Creates single manifest for the entire batch
   - All cleaned files are ready for the AI

4. Send to AI (Auto-Translate)
   - Click "Auto-Translate" to send files directly to the AI
   - **User Control**: You can choose to run the full pipeline or just the translation step.
   - The tool handles:
     * Connecting to the API (OpenAI, Gemini, etc.)
     * Splitting text into chunks
     * Sending instructions and glossary terms
     * Handling errors and retries
   - Or, do it manually: Take prepared files and send them yourself

5. Restore Text (Post-Translation) - Batch Process
   - Load the translated files (same ones you sent to AI)
   - Load the saved manifest from step 3
   - Click "Process Post-TL"
   - Tool processes ALL files and restores everything:
     * Replaces placeholders with original content
     * Generates one output file per input file
     * Shows progress for all files
   - You get all translated files with formatting restored

=============================================================================

WHAT CAN THE TOOL PROTECT?

The tool has several ways to protect content:

1. CUSTOM PLACEHOLDERS
   You can tell the tool: "Whenever you see [pattern], replace it with [name]"
   Examples:
   - Replace all phone numbers with __PHONE__
   - Replace email addresses with __EMAIL__
   - Replace Japanese names with __NAME__
   After translation, the tool puts them back exactly as they were

2. CODE PROTECTION
   Tell the tool what looks like code (using patterns)
   Examples:
   - Regex patterns: <tag.*?> (HTML tags)
   - Code snippets: `const x = 10;`
   The tool replaces these with __PROTECTED__ during translation
   After translation, they're restored unchanged

3. TEMPORARY REPLACEMENT
   Replace patterns with specific text that the AI will see
   Example: "[player_name]" → "Steve"
   - The AI sees "Steve" in the dialogue (a real name it understands)
   - The AI must preserve "Steve" exactly in the translation
   - After translation, "Steve" is replaced back with "[player_name]"
   This is useful for game variables that would confuse the AI.
   Note: If no replacement value is given, a placeholder like __TEMPREPL_0_1__
   is used instead.

4. SPECIAL FORMATTING
   Handles special text automatically:
   - Ellipses (...) 
   - Empty lines
   - Common punctuation

5. DUPLICATE LINES
   If your file has repeated lines, you can:
   - Send only unique lines to the AI (saves money)
   - The tool automatically fills in the duplicates from the translation

=============================================================================

KEY FEATURES

FULL TABLE VIEW
- **Menu Bar Access**: Direct access via "Full Table View" entry in the menu bar (not a dropdown)
- **Menu Bar Layout**: File (dropdown), Full Table View (direct), API Log (direct), Options (direct), Help (dropdown)
- **Spreadsheet View**: Displays all manifest line entries with named columns (Line #, Tags, Original, Preprocessed, Translated, Postprocessed, Wrapped, Overwrite, Quality Assurance, Log, Tags (Internal))
- **Column Display Names**: All columns use human-readable display names (e.g., idx→Line #, orig→Original, tl→Translated)
- **Column Auto-Hide**: Empty columns hidden by default; Tags (context_marker) hidden by default
- **Column Filter Dropdown**: Slim tk.Menu dropdown with presets — Show All, Show Visible, Show Latest (furthest non-empty right column per line) plus individual column toggles
- **All Columns Hideable**: Every column including Line # can be hidden via the column filter
- **Column Selection Bar**: Each column has a "Select / Selected" bar above the header for search/replace scoping; same visual style as column headers
- **Sort Indicators**: Column headers display ▲/▼ arrows showing current sort direction; click toggles ascending/descending
- **Cell Editing**: Double-click to edit any cell (except Line # and Original); multiline support via Shift+Enter
- **Read-Only Original**: Double-click Original opens a read-only text widget for copying content
- **Non-Editable Fields**: Line # and Original cannot be edited or replaced
- **Deletion**: Del key clears selected cells; entire columns can be cleared
- **File Filter**: Hierarchical dropdown with folder navigation (click folders, Back button, scrollable); larger font for readability
- **RegEx Search & Replace**: Two-row toolbar layout — search row on top, replace row below; search across visible or selected columns; toggle RegEx mode; Results Only mode with Prev (◀) / Next (▶) navigation
- **Results Only**: Inverted "Show Misses" — when checked, only matching rows are displayed
- **Searchable Tags & Line #**: Tags (context_marker) and Line # (idx) are searchable (not limited to metadata)
- **Row Selection**: Click-based selection with Ctrl+click and Shift+click; highlighted rows
- **Pagination**: Show All / Show X with configurable page size (default 100); "Showing X / Y Lines" status
- **Save/Reset/Diff**: Save changes to manifest (all or selected); Reset from manifest data; Diff mode shows only changed rows
- **Close Prompt**: Asks to save or discard unsaved changes on close

API LOG
- **Menu Bar Access**: Direct access via "API Log" entry in the menu bar (direct button, no dropdown)
- **Non-Blocking Window**: Opens as a separate Toplevel window; does not lock the main application
- **Live Updates**: Subscribes to the API log store for real-time display of new entries as API calls complete
- **Category Filter**: Dropdown to filter by Main Translation, Term Translation, Gender Inference, or Other (probing/testing)
- **View Mode Switch**: Radio buttons to toggle between Sent, Received, or Both views
- **Search Bar**: Case-insensitive text search across all entry fields with yellow highlights
- **Color-Coded Headers**: Green (✔ success), Yellow (⚠ recovered), Red (✘ failed) status indicators
- **Sent Block**: Displays model, provider, temperature, chunk info, system prompt, and user content
- **Received Block**: Displays token statistics (prompt/completion/total/cached/reasoning), duration, finish reason, error messages, and response content
- **Status Bar**: Shows entry count (filtered vs. total) and aggregated token totals
- **Per-Project Persistence**: Log stored as `.api_log.jsonl` alongside the manifest file; referenced by manifest "log" key
- **Infinite Scroll**: Text widget with word wrap supports unlimited entries
- **Clear Log**: Button to clear all entries from memory
- **Chronological Order**: Entries displayed in order of occurrence; sent/received always coupled together

INTEGRATED AI TRANSLATION
- **1-Click Flow**: Use the "1-Click" button to run the entire pipeline (Load -> Pre -> Translate -> Post) automatically.
- **Manual Control**: Use the "Translate" button to run translation on already pre-processed files (using the loaded manifest).
- **Cost Estimation**: Both methods provide a cost estimate and token count before proceeding.
- **Selective Execution**: You have full control to pause after preparation, review the protected text, and then trigger the translation manually.
- Connects directly to LLM APIs (OpenAI, Gemini)
- Automatically chunks large files to fit context limits
- Enforces structured output (JSON) to prevent line mismatches
- Uses your glossary and analysis data to guide the AI
- Handles rate limits and retries automatically

COMMAND LINE INTERFACE (CLI) ✓ (Enhanced)
- **Interactive Mode**: `python CherryAI.py translate --interactive`
  - Step-by-step wizard guides through file selection and language choice
  - Cost estimation before proceeding
  - Clear progress indicators
- **Direct Mode**: `python CherryAI.py translate file.txt -s ja -t en`
  - One-liner for automation and scripting
  - Language arguments override config
- **Sample Mode**: `python CherryAI.py sample file.txt -n 50`
  - Quick sample translation for testing quality
  - Configurable number of lines (default 50)
- **Configuration via CLI**: `python CherryAI.py config <option> <value>`
  - View all options: `config`
  - Show option details: `config api_url`
  - Set by selection: `config api_url 2` (select Gemini)
  - Set directly: `config api_key YOUR_KEY`
  - Known providers: OpenAI, Gemini, Anthropic, Local, Ollama, LM Studio
  - Known models per provider shown when running `config model`
  - Validation for URLs, temperatures, chunk sizes
  - Apply presets: `config preset gemini_free`
- **CLI Override Options** ✓ (NEW - Session 14):
  - Override API settings directly in translate/sample commands
  - `--model MODEL` - Override model (e.g., gpt-4o, gemini-2.0-flash)
  - `--temperature TEMP` - Override temperature (0.0-2.0)
  - `--timeout SECS` - Override API timeout in seconds
  - `--chunk-size N` - Override lines per API request (10-200)
  - `--preset NAME` - Apply an API preset before translation
  - Overrides are validated and applied before translation starts
  - Example: `translate file.txt -s ja -t en --model gpt-4o --temperature 0.5`
- **Glossary Management**: `python CherryAI.py glossary`
  - Summary: `glossary` (show stats)
  - List entries: `glossary list [names|terms]`
  - Search: `glossary search <query>`
  - Add entries: `glossary add <original> <translation>`
  - Export: `glossary export <path.csv>`
  - Show path: `glossary path`
- **Language Selection**:
  - 14 supported languages: Japanese, English, Chinese (Simplified/Traditional),
    Korean, Spanish, French, German, Portuguese, Russian, Italian, Arabic, Thai, Vietnamese
  - Multiple aliases per language (e.g., `ja`, `jp`, `jpn`, `japanese`)
  - Persisted to config file
- **Utility Commands**:
  - `languages` - List all supported languages with codes
  - `config` - View/set configuration (API URL, key, model, etc.)
  - `io` - Configure input/output file formats
  - `glossary` - Manage translation glossary
  - `sample` - Quick sample translation
  - `estimate` - Estimate translation cost without translating
  - `test` - Run diagnostic tests
  - `help` - Show help and usage information
  - `help <command>` - Detailed help for specific command

FILE FORMAT SYSTEM ✓ (New)
- Pluggable file format handlers with separate extract/inject operations
- **Simple Formats** (fully supported):
  - `txt` - Plain text (one line per line)
  - `csv` - Comma-separated values
  - `tsv` - Tab-separated values
  - `json` - JSON with multiple structure support:
    - Array of strings: `["line1", "line2", ...]`
    - Array of pairs: `[["original", "translated"], ...]`
    - Array of objects: `[{"original": "...", "translated": "..."}, ...]`
    - **Dictionary format**: `{"original_text": "translation", ...}` (keys=source, values=translation)
  - `xlsx` - Excel spreadsheets
- **Pair Support**: CSV, TSV, JSON, XLSX can store original + translated pairs
- **IO Configuration via CLI**: `python CherryAI.py io`
  - View settings: `io` (show current extract/inject formats)
  - List formats: `io formats` (show all available formats)
  - Set formats: `io standard txt json` (read txt, output json)
  - Set extract: `io extract csv` (set input format)
  - Set inject: `io inject xlsx` (set output format)
  - Preserve original: `io preserve_original true`
- **Planned Formats**:
  - HTML files (robust nested parsing) - See todo.md
  - RPG Maker MV/MZ data files (JSON parsing)
  - RPG Maker plugin files (JavaScript)
  - PDF documents (text extraction)
  - EPUB e-books (chapter-based)
- Auto-enables preserve_original when using pair format for output

CONDITIONAL PROMPT INSTRUCTIONS ✓ (Enhanced - Session 14+)
- Pattern-triggered instructions sent to the AI alongside your text
- Similar to glossary but for behavioral rules, not translations
- **Dynamic Instructions** (NEW - TASK 5):
  - Instructions generated based on patterns actually present in batch
  - Only shows relevant examples (reduces token usage)
  - Separate handling for related patterns (e.g., delimiter types, linebreak kinds)
- Built-in conditions (9 total, all configurable in Global Options → Prompts):
  - **Temporary Replacement**: Preserves __TEMPREPL_X_Y__ and __CUST__ placeholder tokens
  - **Delimiter Protection**: Preserves [square], {curly}, <angle>, __dunder__ delimiters (dynamic — lists only matched types)
  - **Linebreaks**: Preserves <br> tags, \\n escape sequences, literal newlines (dynamic — lists only detected kinds)
  - **Color codes**: Preserves \\c[N] formatting
  - **Media commands**: Preserves \\se[], \\pic[], \\wait[], \\fadein[]
  - **Text formatting**: Preserves \\fb, \\fr, \\i[], \\b codes
  - **Ruby text**: Preserves \\rb[text,reading] furigana
  - **Ellipsis**: Maintains …/... dramatic pauses
  - **Speaker dialogue format**: Preserves Speaker: "Dialogue" format (Analysis-style detection)
- All pattern-triggered prompts configurable: enabled/disabled + instruction text editable in Global Options → Prompts → Conditional Prompts (Pattern Triggered)
- Settings stored in CherryAI.ini [pattern_prompts] section
- Custom patterns: Define your own via user/conditional_prompts.json
- Priority-based ordering (higher priority = earlier in prompt)
- Instructions only injected when relevant patterns detected in batch
- **Pattern-Specific Examples**:
  - Each pattern has its own human-readable example
  - Examples only shown when that specific pattern matches
  - e.g., "[square]" shown only when square brackets detected
  - e.g., "<br> tags" shown only when <br> detected in input
- Reduces placeholder corruption from ~5% to <0.1%

API RESPONSE VALIDATION ✓ (Enhanced - Session 14+)
- Multi-layer validation of AI translation responses
- **Pre-Translation Validation**:
  - Skip empty lines, __COMMENT__-prefixed lines
  - Skip context markers (__DIALOGUE__, __MENU__, __CHOICE__, __FILE__)
  - Skip __DEDUP__ and __PROTECTED__ only lines
  - Skip lines without Japanese characters
  - Skip already translated lines
  - Auto-translate symbol-only lines (…→..., 。→., etc.)
  - Note: # and = lines are treated as normal text (not skipped)
- **Post-Translation Validation**:
  - Japanese character count check (max 4 allowed in output)
  - Anchor character preservation verification
  - Uses ANCHOR_EQUIVS for fullwidth/halfwidth equivalence
- **Placeholder Preservation** ✓ (NEW - TASK 4):
  - Validates __PROTECTED__, __PROTECTED_1__, custom placeholders preserved
  - Detects missing, mangled, and extra placeholders
  - Per-line validation with targeted retry recommendations
  - Supports indexed placeholders: __PROTECTED_1__, __NAME_2__, etc.
- **Comprehensive Validation** ✓ (NEW - TASK 4):
  - Combines all checks: empty, placeholder, speaker, Japanese, anchors
  - Per-line retry reasons: EMPTY_TRANSLATION, PLACEHOLDER_MISSING,
    SPEAKER_FORMAT_LOST, TOO_MANY_JAPANESE, LINE_COUNT_MISMATCH
  - Batch validation with lines_to_retry list for targeted retries
  - Success rate calculation for batch quality assessment
- **Symbol Conversion** (Standard Mode):
  - Enabled by default via `symbol_conversion_enabled` config
  - Fullwidth digits → ASCII: ０１２３４５６７８９ → 0123456789
  - Fullwidth letters → ASCII: Ａ-Ｚ, ａ-ｚ → A-Z, a-z
  - Japanese quotes → English: 「」→"", 『』→''
  - Special brackets: 【】→[], 《》→<>
  - Punctuation: 、→,, 。→., ：→:, ；→;, ！→!, ？→?
  - Operators: ＝→=, ＋→+, －→-, ＊→*, ／→/, ～→~
  - Misc: ％→%, ＆→&, ＠→@
  - Ellipsis: …→... (language-specific)
  - Configurable per-language (jpn→eng, eng→jpn, etc.)
- Batch processing with proper line reassembly
- 108 unit tests for validation logic (56 core + 52 API validation)

ANALYSIS TOOL
- Look at your file before translating
- See statistics: How many lines? Duplicates? Empty lines?
- Detect code patterns automatically
- Estimate AI translation costs
- See language detected
- Get glossary suggestions

TEMPLATES
- Save your protection rules as a template
- Reuse the same rules on different files
- Share templates with team members
- Load templates to start with pre-made rules

MANIFESTS
- Automatically saves all your rules for each file
- Stored in the "Projects/" folder with .CherryAI.json extension
- When translating the same file later, load the manifest to use the same rules
- Tracks what was protected in each file
- Helps with consistency

PROJECT FILE STAGING (v3.1)
- Input/output decoupling via `filedir` field maps line index ranges to files
- Source files are copied to `Projects/{project_name}/Original/` on load
- Translated files are written to `Projects/{project_name}/Patch/`
- `source_root` stores only the folder name (privacy-safe, portable)
- File resolution uses the local `Original/` directory, not original user paths
- Projects remain functional even if original source files are moved/deleted
- Folder structure is preserved for multi-file projects
- Supports per-file encoding (utf-8, shift_jis, etc.)

DRY RUN / TEST MODE
- Try your rules without actually translating
- The tool runs the prepare and restore steps
- Shows you if something might go wrong
- No need to send to AI - just test locally

GLOSSARY & AUTOMATIC DETECTION
- Unified glossary system that automatically learns from your files
- The tool automatically detects and catalogs:
  - Speaker names from dialogue (with gender and honorific patterns)
  - Code patterns and technical markers
  - Terms and terminology
- Track context for proper names (female/male, pronouns, honorifics)
- Optional LLM-based enhancement: Get AI-suggested translations and gender for names
- Helps AI translator maintain consistency across files
- **Table Sorting**: Glossary and Code Database tables sort by count (highest first) by default. All column headers are clickable — ascending (A→Z), descending (Z→A), third click resets to count. Active sort column shows ▲/▼ arrow. Manifest saves entries in count-descending order.

GAME SUMMARY & PROJECT CONTEXT
- Provide story context to help the AI understand your game/story
- Summary widget in Information Step (Step 3), height=2, with "🔄 Restore Default" button
- Default text: "Write a short summary of the work here. Mentioning protagonist(s) and Point of View is not necessary and will be automatically provided."
- Summary stored in manifest key `Summary`, auto-saved/loaded via manifest binding
- Summary is automatically injected into the system prompt by translate.py `_build_system_prompt_from_manifest()` as `# Game Context\n...`, reading from `step_state.Information.data.metadata.summary`
- Helps AI maintain consistent characterization and tone
- Project configuration stored per-project in manifest:
  - Project name (from Input step, not folder name), genre, tone
  - Custom style instructions
  - API profile selection (different models for different purposes)
- Multiple API profiles supported:
  - Use fast/cheap models for glossary enrichment
  - Use powerful models for actual translation
  - Keep API keys secure (never stored in manifest)

TRANSLATION STYLE GUIDE
- Customize translation style and tone via Information Step preset system
- Style and Tone each have:
  - Dropdown with built-in presets (Natural, Formal, Casual, etc.) and user-saved presets
  - Custom text field (ScrolledText, height=1) for free-form override
  - Save/Delete buttons for managing user presets
  - All presets (built-in and user) stored in `user/CherryAI.ini` under `[style]` and `[tone]` sections
  - Built-in presets are seeded automatically on first run and are never overwritten
- Style/Tone values stored in `step_state.Information.data.metadata` under keys `style`, `tone`, `style_preset`, `tone_preset`
- translate.py `_build_system_prompt_from_manifest()` reads from `step_state.Information.data.metadata` and appends to system prompt as `# Translation Style Guidelines\n...` and `# Translation Tone\n...` sections
- Helps maintain consistent translation style across the project

SYSTEM INSTRUCTIONS
- Provide custom LLM instructions via Information Step preset system
- Preset dropdown: Default (built-in full text seeded in `[system_instructions]`), Custom (free-form), or user-saved presets
- Save/Delete buttons for managing user presets; all presets stored in `user/CherryAI.ini` under `[system_instructions]`
- Default text (including Output Examples section) automatically populated from INI when empty on step entry
- Instructions stored in manifest key `Prompt`, preset name in `SIPreset`
- translate.py `_build_system_prompt_from_manifest()` reads `custom_notes` from `step_state.Information.data.metadata` and includes in system prompt
- Global Options → Restore Defaults → System Instructions resets `[system_instructions]` section and re-seeds Default preset

I/O EXAMPLES GENERATION (NEW)
- Generate I/O (input/output) example blocks for the system prompt to improve translation quality
- Dropdown in Information Step (System Instructions section): disabled | fill | 1500 | 2500
  - **disabled**: No separate examples generated
  - **fill**: Cache-aligned budget — calculates remaining token space to fill the optimal cache boundary (default 1536 tokens for OpenAI). Uses `get_optimal_cache_size()` from api_config.py. Fill target = `optimal_cache_size - all_static_section_tokens` (pre-computes tokens for ALL static sections including Style, Tone, Summary, Genre, Protagonist, POV, Context-Type before generating examples)
  - **1500**: Fixed budget of ~1500 tokens of I/O examples
  - **2500**: Fixed budget of ~2500 tokens of I/O examples
- Examples generated at request build time by `functions/io_examples.py`, NOT stored in manifest
- **Never modifies System Instructions** — examples are a separate slot (2b) and do not strip or alter SI content
- Examples injected at prompt slot 2b (between System Instructions and Style) in the static/cacheable prefix
- **Preview Requests**: IO Examples section visible in Preview Request dialog via `io_examples` filter part (positioned after System Instructions, before Style/Tone)
- Example bank uses `_Example` dataclass with language-keyed fields (`jp`, `en`); source/target language from manifest determines which field is used for input vs output
- Language key resolution: maps language names to keys (Japanese→jp, English→en); unknown languages fall back to `en` unless English is already source or target (then `jp`); source/target always resolve to distinct keys
- Example bank covers ~35 translation patterns: PLACEHOLDER, VARIABLE, COLOR, LINEBREAK, MEDIA, ICON, FONT, SPEAKER, PRESERVE, RUBY, SPAN, COMPLEX, PLAIN
- Code pattern priority boosting: project's detected `code_patterns` boost matching examples in the bank (e.g., a project with COLOR codes gets more color-related examples)
- Line numbering: each line key ("Line1", "Line7", etc.) is globally unique across all blocks and matched between Input/Output pairs
- Token counting via tiktoken (cl100k_base) with heuristic fallback for environments without tiktoken
- Setting stored in manifest `metadata.io_examples`; seeded as "disabled" at manifest creation

ROLLING CONTEXT (NEW - TASK 7, extended TASK 78)
- Provides surrounding lines as context for each translation batch
- Helps AI maintain continuity and context awareness
- Configuration in `CherryAI.ini` under `[rolling_context]`:
  - `enabled`: true/false to enable/disable
  - `lines_before`: number of preceding lines to include (default: 3)
  - `lines_between`: number of skipped/interspersed lines within chunk range (default: 0)
  - `lines_after`: number of following already-translated lines (default: 0)
  - `scene_markers`: comma-separated patterns that indicate scene breaks (e.g., "=====,-----,***")
  - `use_translated`: true to prefer translated text, false for source text (default: true)
- Three rolling context types:
  - **Lines (Before)**: Classic preceding-lines context from prior request
  - **Lines (Between)**: Skipped lines within the chunk's index range (already translated / non-source)
  - **Lines (After)**: Already-translated lines following the chunk (forward context)
- All three context types block Efficient-mode cross-file merging
- Scene markers reset context (new scene = fresh start)
- Context is prefixed to user message with clear "do not re-translate" warning
- Dynamic updates: context can be replaced with actual translated lines after each batch
- Global Options UI: separate "Lines (Before)", "Lines (Between)", "Lines (After)" spinboxes + "Prefer translated lines" checkbox

MODEL PRESETS (NEW - TASK 8)
- Quick-switch between different AI model configurations
- Presets defined in `CherryAI.ini` under `[api_presets]`:
  - Format: `preset_name = base_url|model|temperature|timeout|rate_limit`
- Default presets included:
  - `gemini_free`: Gemini 2.0 Flash Lite (free tier, 15 req/min)
  - `gemini_pro`: Gemini 2.0 Flash (paid, 60 req/min)
  - `gpt4`: GPT-4o-mini (OpenAI, 60 req/min)
  - `gpt4_turbo`: GPT-4 Turbo Preview (OpenAI, 60 req/min)
  - `local`: Localhost for local models (LM Studio, Ollama, etc.)
- API Client method: `client.apply_preset("gemini_free")` to switch models
- Static method: `APIClient.get_available_presets()` to list available presets
- Keeps API key separate (presets only change model settings)
- Use different presets for different tasks:
  - Fast/cheap preset for glossary enrichment
  - Powerful preset for actual translation
  - Local preset for testing without API costs

LOCAL LLM SUPPORT (Current + Planned Enhancement)
- **Current Support:**
  - Works with any OpenAI-compatible local server
  - Built-in presets: `local` (port 1234), `ollama` (port 11434), `lmstudio` (port 1234)
  - Dedicated **LM Studio** preset in Global Options → API Provider (alongside OpenAI, Gemini, Anthropic, etc.)
  - CLI usage: `python CherryAI.py translate --preset local input.txt`
  - No API key required for local endpoints — placeholder `lm-studio` key used automatically
  - LM Studio keys can be saved in Global Options → Saved API Keys and selected in the Translation Step
  - Uses `json_schema` response format for structured output (LM Studio does not support `json_object`)
  - Automatic model discovery from running LM Studio server via `/v1/models` endpoint
  - Translation Step model dropdown auto-populates with models loaded in LM Studio
- **Compatible Software:**
  - **LM Studio**: OpenAI-compatible server, easy model management, tested with Qwen 3.5 35B A3B (~2-4 tok/s)
  - **Ollama**: Fast local inference, many model options
  - **text-generation-webui**: Advanced interface with extensions
  - **LocalAI**: Drop-in OpenAI replacement
  - **llama.cpp server**: Lightweight, direct GGUF support
- **Quick Start (GUI):**
  1. Start LM Studio and load a model (enable the local server)
  2. Open CherryAI → Global Options → API Provider → select **LM Studio**
  3. Base URL auto-fills to `http://localhost:1234/v1`
  4. Enter `lm-studio` as the API key and click Save
  5. Go to Translation Step → select the saved LM Studio key
  6. The Model dropdown auto-populates with models from the server
  7. Translate — no cloud API key or costs required
- **Quick Start (CLI):**
  1. Start your local LLM server (e.g., LM Studio → Start Server)
  2. Run: `python CherryAI.py translate --preset local myfile.txt`
  3. No API key needed - uses localhost:1234 by default
- **Implementation Details:**
  - Provider detection: `APIClient.is_local_provider()` checks provider name and URL
  - `LOCAL_PROVIDERS = ("local", "lmstudio", "ollama")` in `api_client.py`
  - Response format: `json_schema` (with strict schema enforcing `{"translations": [...]}`) for local providers, `json_object` for cloud providers
  - `test_model_translation()` in `api_config.py` also uses `json_schema` for local providers
  - `_filter_models_by_provider()` in `translate.py` queries the live server for model lists
  - `functions/local_llm.py`: `LocalLLMProvider` enum, `discover_models()`, `check_server_health()`, `is_local_url()`

PARTIAL TRANSLATION MODE (NEW - TASK 9)
- Translate only the first N lines of a file, leaving the rest unchanged
- Useful for:
  - Testing translation quality on a subset before full processing
  - Budget-conscious partial translation
  - Quick preview of translation results
- CLI argument: `--translate-lines N` or `-n N`
  - Example: `cherryai translate -n 50 myfile.txt` (translate first 50 lines)
- Configuration in `CherryAI.ini` under `[partial_translation]`:
  - `enabled`: true/false to enable partial mode by default
  - `max_lines`: default line limit (default: 100)
  - `skip_marker`: marker appended to skipped lines (default: "[UNTRANSLATED]")
- CLI argument overrides config setting
- Skipped lines retain their original text with an optional marker
- Empty/whitespace lines do not receive skip markers
- Output clearly indicates how many lines were translated vs skipped

SPEAKER FORMAT PRESERVATION (NEW - TASK 10)
- Validates that Speaker: "Dialogue" format is preserved after translation
- **Two-Tier Validation System:**
  - **Tier 1**: Automatic retranslation when format is broken
    - Detects when speaker dialogue format is lost during translation
    - Triggers automatic retry with emphasis on format preservation
  - **Tier 2**: Flagging when retries exhausted
    - Tags line with `needs_review` and `speaker_format_error`
    - Logs the issue for manual review
- **Comprehensive Quote Detection:**
  - Standard quotes: "..." and '...'
  - Japanese brackets: 「...」 and 『...』
  - Curly/smart quotes: "..." and '...'
  - Thought/parenthetical: (...) and （...）
- **Format Requirements:**
  - Colon (: or fullwidth ：) followed by quote character
  - Balanced opening/closing quotes at end of line
  - Exception: space and simple commands (e.g., \b) allowed between colon and quote
- **Conditional Prompt Integration:**
  - Pattern: `.+[:：]\s*[""「『\'\(（].+[\"\"」』\'\)）]\s*$`
  - Priority 82: Ensures AI is instructed about format preservation
  - Instruction: Lines contain Speaker: "Dialogue" format - preserve exactly
- **SpeakerFormatInfo dataclass fields:**
  - `has_speaker_format`: Whether format was detected
  - `speaker_name`: Text before the colon
  - `opening_quote` / `closing_quote`: Quote characters used
  - `is_balanced`: Whether quotes are properly paired
  - `dialogue_content`: Text between quotes
- **Files Affected:**
  - `functions/validation.py`: Core detection and validation logic
  - `functions/postanalysis.py`: Enhanced speaker validation
  - `functions/conditional_prompts.py`: CONDITION_SPEAKER_DIALOGUE
- **Tests:** 45 tests in `dev/test_speaker_format.py`

EXTENDED LINE TAGS & AUTO-TAGGING (Implemented)
- Every line can now have multiple status tags with severity levels
- **Tag Categories:**
  - Processing: needs_review, code_mismatch, placeholder_error, dedup_source
  - Content: has_speaker, has_code, long_line, short_line, empty_translation
  - Quality: low_confidence, glossary_mismatch, style_issue, grammar_flag
  - Workflow: manual_edit, api_translated, needs_tlc, approved, rejected
- **Severity Levels with Colors:**
  - INFO (Green): Informational, no action needed
  - WARNING (Yellow): Attention recommended
  - ERROR (Orange): Problem logged, action required
  - CRITICAL (Red): Severe error, must fix
- **Auto-Tagging:** Tags are automatically assigned based on events:
  - placeholder_error added when restoration fails
  - code_mismatch added when code count differs
  - api_translated added after successful translation
  - manual_edit added when user modifies content
- Filter and sort lines by tags to focus on problems

GUI v2 ARCHITECTURE (In Progress - Phase 8 Complete)
- Complete GUI rewrite with 10-step workflow tabs
- **Design Philosophy:**
  - Pastel blue color theme (no grey/white monotony, no yellow/red)
  - Each step is a separate tab for focused work
  - Progress tracker shows completion status
  - Undo/redo support for all operations
- **10 Workflow Steps:**
  1. **Input** - Load files, select formats ✅ Implemented
  2. **Analysis** - Analyze content, detect patterns ✅ Implemented
  3. **Information** - Configure context, glossary, summary
  4. **Preprocessing** - Apply protection rules, dedupe ✅ Implemented
  5. **Costs** - Token counts, cost estimates, time projection ✅ Implemented
  6. **Translation** - API configuration, batch translation ✅ Implemented
  7. **Postprocessing** - Restore placeholders, apply fixes ✅ Implemented
  8. **Wordwrap** - Line breaking, width limits ✅ Implemented
  9. **QA** - Quality checks, auto-tagging ✅ Implemented
  10. **Output** - Export formats, save results
- **Input Tab (Phase 1, updated Phase 39, 58, 60):**
  - **Unified Input Button (Phase 58.1):** Single "Input" button opens UnifiedInputDialog
    - Dual-pane interface: File browser (left) and Folder browser (right)
    - Multi-select support with path list display
    - Combined file and folder loading in single operation
  - **Auto-Pipeline Dropdown (Phase 58.2):** Select automation level before loading
    - Manual (0): No automation - user controls each step
    - Analyze (1): Creates manifest, loads lines, runs analysis
    - Estimate Original (2): Level 1 + original cost estimation
    - Preprocess (3, default): Level 2 + preprocessing pipeline
    - Mock Translate (4): Level 3 + mock translation for testing
  - **File Tree Improvements (Phase 58.7):**
    - Folders collapsed by default for cleaner initial view
    - Folders sorted above files in tree
    - New context menu items: Select All, Expand All, Collapse All
  - **Clickable Column Headers (Phase 60):**
    - Name, Type, Lines columns clickable to sort ascending/descending
    - ▲/▼ indicators show current sort column and direction
    - Folder hierarchy flattened when sorting by Type or Lines
    - Replaces previous Sort Combobox
  - **File List Filter (Phase 60):**
    - Text entry for instant filtering by filename, type, or line count
    - Non-matching files hidden; ✕ clear button restores full list
    - Filter resets on New Project
  - **Type Column Refresh Fix (Phase 60):**
    - File types (dialogue, menu, etc.) now display immediately after loading
    - Previously required a sort action to populate the Type column
  - **Cross-File Preview Search (Phase 60):**
    - Preview search now searches ALL loaded files, not just the selected one
    - Results show global idx column for cross-file identification
    - Selecting a result auto-switches to the containing file in the file tree
    - ✕ clear button restores single-file preview mode
  - **Non-Destructive File Addition:**
    - Adding files to an existing manifest preserves all existing line data (tl, prepro, etc.)
    - Source root validation blocks loading files from a different source directory
    - New files are merged into sorted filedir with contiguous idx rewrite
    - Only new originals are copied to project; Automatic Pipeline is not re-run
  - **Preview Column Rename:**
    - "Idx" column renamed to "Project" (1-based global index)
    - "#" column renamed to "File" (1-based per-file line number)
  - **Import Translation Selection Dialog:**
    - Import Translations button now opens a selection dialog before importing
    - Line Fields group: Preprocessed, Tags, Translated, Postprocessed, Wordwrap, QA
    - Settings Sections group: Analysis, Information, Preprocessing, Costs, Translation,
      Postprocessing, Wordwrap, QA/Validation, File/Output Settings
    - "Do not overwrite lines that already have translations" option
  - **OutputFormat Safe Parsing:**
    - ``_safe_output_format()`` prevents ValueError crash when Output tab is opened
      with empty or invalid format string (defaults to TXT)
  - **Input Dialog UX Improvements (Phase 58.12):**
    - UnifiedInputDialog remembers last used directory across sessions
    - Project Name field integrated into Options panel (avoids separate dialog)
    - Directory persisted in `[session].last_input_dir` in CherryAI.ini
  - Unified "Input" button opens UnifiedInputDialog directly (no dropdown)
  - **Collapsible folder hierarchy:** Treeview with parent folder nodes and leaf file nodes
    - Multi-select support for bulk deletion
    - Context menu: Remove Selected, Select All in Folder
  - Supported formats: txt, csv, tsv, json, xlsx, rpgmaker, image
  - Auto-encoding detection (BOM → utf-8 → shift_jis → latin-1 fallback)
  - Format filtering: refuses non-matching files when format is forced
  - Preview with newline → ↵ marker replacement for multi-line content
  - Progress dialog for loading operations (>3 files)
  - Batch summary (file count, total lines, format breakdown)
  - Removed: Load Manifest button, Clear All button, manifest status label
  - **Source File Recovery Status (color-coded):**
    - Green: Original file found at expected path
    - Yellow: File missing but recoverable format (txt, csv, tsv, json)
    - Red: File missing with non-recoverable format (rpgm, xlsx, epub, pdf)
- **Shared Table Component (Phase 2):**
  - SharedTable class with ttk.Treeview widget
  - TableRow dataclass for row data representation
  - ColumnDef dataclass for column configuration
  - Virtual scrolling (tested with 4947 lines)
  - Filter/search with Enter key binding
  - Sort by column header click
  - Multi-select with Ctrl/Shift click
  - Column resize support
  - CSV export functionality
- **Analysis Tab (Phase 3, updated Phase 59):**
  - Static analysis on loaded files
  - Stats display: line counts, duplicates, empties
  - **Aggressive Dedup Projection (Phase 59.2):** Shows projected unique lines after normalization
  - **Project-Level Language Detection (Phase 59.1):**
    - CJK language classifier (Japanese, Chinese, Korean)
    - Japanese identified by kana (hiragana/katakana)
    - Chinese-only: CJK without kana, 30% threshold rule
    - Korean: Hangul detection, excluded from JP/CN threshold
  - Language detection (Japanese, Chinese, etc.)
  - Code/pattern detection: individual normalized patterns with count, type, and concrete instances (raw variants that normalize to the same pattern)
  - Speaker detection: ALL speakers listed with frequency counts (no truncation); enhanced validation rejects false positives via balanced bracket checks, no-newline rule, and script-aware length limits (≤30 Latin / ≤20 CJK)
  - **Findings Table Enhancements:**
    - Individual code patterns shown with normalized form, occurrence count, type, and examples in Details
    - Patterns with instances (aggregated) display **[+]/[-] collapsible** sub-rows showing each concrete variant and its per-instance count; double-click to toggle expansion
    - Patterns with instances sort above same-count patterns without instances
    - Speaker rows show character glossary info (translation, notes) in Details column
    - **Count Filter:** Filter bar includes Count field supporting `<X`, `>X`, `<=X`, `>=X`, `=X` syntax; toggle button (≥/≤) switches default bare-number comparison mode
  - **Findings Table Context Menu (Phase 59.3-59.5):**
    - Category-aware right-click menu (categories: "Speakers", "Code Patterns")
    - **Speaker actions:** Add to Glossary, Set Role (Protagonist/Love Interest/Major/Minor), Set Gender (Male/Female/Non-Binary/Transwoman/Transman/Other/Unknown), Set Translation, Add to Code Glossary, Copy Name, Select All with Speaker (filter); all actions write to **character glossary** (manifest `characters` key) not project glossary entries
    - **Code Pattern actions:** Preserve/Provides Context/Custom Placeholder/Protect (Generic Placeholder)/Strip with Anchor/Part of a Span (persisted to Code Database); action sync auto-populates Preprocessing sections (Protect → ProtectCodePatterns, Custom Placeholder → CustomPlaceholders, Strip with Anchor → AnchorRemoval). Type classification (Name/Text/Number/Invisible), Nameable... (assigns temp replacement name for Character/Company/Location), Copy Pattern, Show Lines with Pattern (filter)
    - **Nameable Dialog:** Code patterns marked "Is a Name" get the replacement name added to character glossary and the code pattern to Custom Placeholders in Preprocessing; "Nameable..." opens a dialog with Character (John/Jane/Alex Smith), Company (Acme/Globex/Initech Corp), and Location (Millfield/Oakville/Riverside) modes with gender-aware name selection
    - Generic menu for mixed selection (Copy, Select All)
  - **Ignored Patterns (Phase 59.7):** Filter patterns from code detection results
  - Export findings to CSV
  - Options panel: detector toggles
  - Threaded analysis for large files
- **Progress Tracker Panel (Phase 4):**
  - Right-side collapsible panel (StepRow, ProgressPanel, ProgressTracker classes)
  - Step rows with completion status icons (✓ done, – skipped, pending)
  - Skip and rollback per step with undoable actions
  - **Workflow Presets:**
    - Sample: Quick test with minimal steps (Input + Analysis only)
    - Dirty & Cheap: Fast translation with minimal processing
    - Automatic Luxury: Full pipeline with all automation
    - Everything Custom: Manual control at every step
  - Preset selector dropdown with auto-skip and auto-complete
  - Completion percentage display
- **Undo/Redo System (Phase 4):**
  - Full undo/redo stack with 50-action limit
  - UndoAction dataclass stores before/after state snapshots
  - All step changes are undoable (status, skip, rollback, presets)
  - get_undo_description() / get_redo_description() for UI hints
- **Project Persistence (Phase 4, Enhanced with Manifest v3.0):**
  - **Manifest-first architecture**: All state saved to manifest file
  - **File menu**: New Project, Open Project, Exit
  - **Auto-save on step change**: Manifest saved when navigating between steps
  - **Atomic saves**: Manifest written to `.tmp` file, fsynced, then atomically renamed via `os.replace()` to prevent corruption on crash
  - **Deep-copy safety**: `get_step_data()` callers that mutate data use `deepcopy()` to prevent shared-reference contamination; `_SafeManifestEncoder` handles non-serializable objects as a safety net
  - **Robust on-close**: `_on_close()` retries save up to 3 times with exponential backoff; on persistent failure, user is prompted to force-quit or retry; structured sequence: save manifest → save INI → stop autosave → destroy
  - **Manifest v3.0 format** stores all project data:
    - step_state: Completion status, skipped flags, metadata per step
    - project_info: **Removed as top-level key.** Now lives in `step_state.Information.data.metadata` (single source of truth). Access via `get_info_metadata()` / `set_info_metadata_field()`.
    - glossary: Project-specific glossary entries (optional, can use global)
    - characters: Speaker database with gender and context
    - code_patterns: Protected code and custom placeholders
    - lines: Source and translated line content
    - **Line field persistence (Task 3):** Each processing step writes its per-line output directly to manifest `lines[]` via `set_line_field()` — `prepro` (preprocessing), `tl` (translation), `postpro` (postprocessing), `wordwr` (wordwrap). Fields accumulate through the pipeline and survive session restore.
  - **Settings Flow to Processing Functions (Task 21.3):**
    - Grouped settings access via ManifestManager helper methods
    - `get_request_options()` - API settings (Model, Temperature, LinesPerChunk)
    - `get_preprocessing_options()` - Deduplication, SymbolConversion, etc.
    - `get_validation_rules()` - PlaceholderPreservation, QuoteBalance, etc.
    - `get_qa_options()` - RerunPolicy, MaxJapaneseChars, MaxLineLength
    - `get_postprocessing_options()` - Recovery and restoration settings
    - `get_wordwrap_options()` - Width, BreakChar, Typography, etc.
    - `get_output_options()` - Format, Encoding, FileNaming, etc.
    - `get_estimation_data()` - InputLines, InputTokens, OutputTokens
    - `get_all_settings()` - Returns all settings grouped by category
    - All getters return deep copies (mutation-safe)
    - All setters mark manifest dirty for auto-save
  - **Manifest Field Type Helpers (Task 22.1):**
    - Reusable save/load functions in `functions/manifest_fields.py`
    - Text fields: `save_text_field()`, `load_text_field()` + nested variants
    - Boolean fields: Handles "true"/"false"/"1"/"0" string normalization
    - Integer fields: Bounds clamping (min/max), truncation from float
    - Float fields: Bounds, precision rounding, validation
    - Enum fields: Validates against option list, falls back to default
    - List fields: Parses comma-separated strings, handles empty defaults
    - Dict fields: Deep copy semantics for mutation safety
    - All helpers mark manifest dirty on save, return defaults on missing
  - **Special Format Helpers (Task 22.2):**
    - Complex data structure helpers in `functions/manifest_fields.py`
    - Glossary (Characters): `save_character_notes()` / `load_character_notes()`
      - Fields: name, original_name, gender, role, notes, speaking_style
      - Supports CharacterInfo dataclass or plain dicts
      - Gender/Role merged into Notes column in UI for parity with Glossary Settings
    - Code Glossary: `save_code_glossary()` / `load_code_glossary()`
      - Fields: pattern, category, action (preserve/provides_context/custom_placeholder/protect/strip_with_anchor/part_of_span), example, notes
      - Supports CodePattern dataclass or plain dicts
    - Protect Code Patterns: `save_protect_code_patterns()` / `load_protect_code_patterns()`
      - Fields: pattern, replacement, is_regex, description
    - Custom Placeholders: `save_custom_placeholders()` / `load_custom_placeholders()`
      - Fields: pattern, placeholder, is_regex, restore_after
    - Anchor Removal: `save_anchor_removal()` / `load_anchor_removal()`
      - Fields: pattern, action (remove/preserve/replace), replacement, is_regex
    - Glossary Entries: `save_glossary_entries()` / `load_glossary_entries()`
      - Fields: source, target, category, context, notes
      - Stored under glossary.project_entries in manifest
  - **Widget-to-Manifest Binding (Phase 22-23):**
    - Automatic two-way binding between GUI widgets and manifest fields
    - `gui/helpers/manifest_binding.py` provides binding functions:
      - `bind_entry_to_field()` - Text entries (auto-save on change via trace)
      - `bind_checkbox_to_field()` - Boolean checkboxes
      - `bind_combobox_to_field()` - Dropdown selections with validation
      - `bind_spinbox_to_field()` - Integer values with min/max clamping
      - `bind_text_to_field()` - Multiline Text widgets (saves on FocusOut)
      - `bind_radio_group_to_field()` - Radio button groups
      - `bind_float_spinbox_to_field()` - Float values with precision
    - Each binding returns `BindingInfo` for tracking/testing
    - `load_all_bindings()` for batch loading from manifest
  - **Information Tab Manifest Integration (Phase 23):**
    - All Information tab fields bound to manifest for persistence:
      - **Basic Metadata (Task 23.1):** ProjectName, Title, Genre, SourceLanguage, TargetLanguage, Summary
      - **Style and Tone (Task 23.2, updated Phase 60):** StylePreset (combobox → manifest), CustomStyle (ScrolledText → manifest), TonePreset, CustomTone
      - **Glossary / Characters (Task 23.3):** Save/load via special format helpers
      - **Code Database (Task 23.3):** Save/load via special format helpers
      - **Prompt (Task 23.4):** Renamed from "Additional Notes", moved to left column
    - Changes auto-save to manifest on widget interaction
    - Values auto-load on step entry via `_load_from_manifest_bindings()`
  - **Application Startup (Task 21.4, Phase 58.11):**
    - On launch, reads last manifest path from INI [session] section
    - Auto-loads last project if load_last enabled (default)
    - Shows WelcomeDialog if no last manifest or file missing:
      - Resume: Load last project
      - New Project: Start fresh with file loading
      - Load Existing: Open project browser (sorted by date, latest first)
      - Start Fresh: Begin without loading project
      - **Auto-load checkbox:** "Automatically load last project on startup" (Phase 58.11, updated Phase 60)
        - Always visible regardless of whether Resume option is available
        - Loads current INI setting on display; saves immediately on toggle
        - Persists via ini_manager.set_load_last()
        - GlobalOptions syncs with this setting in [session] section
    - Saves last manifest path on app close for next launch
    - Recent manifests list maintained (up to 10)
  - **Global vs Project Glossary**: Toggle in Information step to use global glossary.json or project-specific glossary stored in manifest
  - **Section Enable/Disable Toggles:**
    - Each Information step section has an Enabled/Disabled toggle button:
      - **Genre** (default: Disabled) — button in Project Details row
      - **Summary** (default: Disabled) — button right of Restore Default
      - **Translation Style** (default: Disabled) — button right of Delete
      - **Translation Tone** (default: Disabled) — button right of Delete
      - **System Instructions** (default: Enabled) — button right of Delete
      - **Glossary** (default: Enabled) — button in collapsible header
      - **Code Database** (default: Enabled) — button in collapsible header
      - **Knowledge Base** (default: Enabled) — existing button, enhanced
    - Disabled text fields (Summary, Style, Tone, System Instructions) are visually greyed out with `THEME.bg_disabled` / `THEME.text_disabled` colours
    - Save, Delete, and Toggle buttons for Style, Tone, and System Instructions are right-aligned (matching Summary)
    - Toggle state persists to manifest via `*_enabled` metadata keys
    - Disabled sections are excluded from prompt assembly in `build_full_system_prompt()`
    - Collapsible sections collapse and disable their collapse button when toggled off
    - Toggles are respected by Preview Request, Estimate, and Start Translation
    - `on_leave()` merges toggle states into metadata dict (survives `ProjectMetadata.to_dict()` which excludes `*_enabled` keys)
    - Preview Request: `_build_preview_requests()` gates each labeled section by its enabled flag
    - No manual Save button — toggles and metadata auto-save on tab change via `on_leave()`
- **Theme System (Phase 14):**
  - **Pastel Blue Theme (default):**
    - Light/pastel blue base color (#B8D4E8)
    - Modern, clean, non-white/grey monotony
    - No yellow/red colors (accessibility)
  - **High-Contrast Theme (accessibility):**
    - Dark navy background (#1A1A2E)
    - Pure white text (#FFFFFF)
    - WCAG AAA compliant contrast ratios
    - Bright accent colors (Spring Green, Deep Sky Blue)
  - **Theme Switching:**
    - ThemeMode enum: PASTEL_BLUE, HIGH_CONTRAST
    - set_theme(mode) to switch at runtime
    - get_theme() / get_theme_mode() accessors
    - apply_theme(root, theme) for custom themes
- **Icons System (Phase 14):**
  - Icons dataclass with Unicode symbols
  - Cross-platform compatibility (Windows, macOS, Linux)
  - **Status Icons:** ✓ Done, ◐ Partial, ○ Pending, ✗ Failed, ⊘ Skipped
  - **Step Icons:** 📁 Input, 🔍 Analysis, ℹ Info, ⚙ Preprocess, etc.
  - **Action Icons:** + Add, − Remove, ↻ Refresh, ↶ Undo, ↷ Redo
  - Helper functions: get_step_icon(), get_status_icon(), get_log_level_icon()
- **Implementation Status:**
  - Phase 0: Foundation skeleton ✅ Complete
  - Phase 1: Input ✅ Complete (with session serialization fix)
  - Phase 2: Shared Table Component ✅ Complete (with TableRow serialization)
  - Phase 3: Analysis Tab ✅ Complete (with data flow fix)
  - Phase 4: Progress Tracker & State ✅ Complete (with recursive serialization)
  - Phase 5: Preprocessing Tab ✅ Complete
  - Phase 6: Estimation Tab ✅ Complete (renamed to Costs in Phase 40)
  - Phase 7: Translation Tab ✅ Complete
  - Phase 8: Quality Assurance Tab ✅ Complete
  - Phase 9: Postprocessing Tab ✅ Complete
  - Phase 10: Wordwrap & Overwrite Tab ✅ Complete
  - Phase 11: Output & Injection Tab ✅ Complete
  - Phase 12: Information Tab ✅ Complete
  - Phase 13: Global Options Dialog ✅ Complete
  - Phase 14: Polish & Integration ✅ Complete
  - **🎉 GUI v2 COMPLETE! All 15 phases implemented.**
- **Preprocessing Tab (Phase 5):**
  - Standard rules with toggles: Deduplication, Ellipsis, Symbol Conversion, PROTECTED Compression
  - Deduplication threshold control (0=off, 1=all repeats, N=N+ consecutive)
  - Custom Placeholder section with add/edit/remove and pattern→token mapping
  - Protect Code Patterns section with regex patterns
  - Common patterns reference (HTML, RPG Maker, variables, etc.)
  - Preview table showing original vs processed with diff column
  - Apply Rules button with threaded background processing
  - Auto-Suggest button leveraging analysis results
  - Tooltips explaining each rule's behavior
  - **Manifest Integration (Phase 24):**
    - All toggles persist to manifest: Deduplication, DeduplicationThreshold, EllipsisCompression,
      SymbolConversion, ProtCompression, SpeakerNameReplacement, CodeSpacingRules
    - Protect Code Patterns saved/loaded from manifest in ProtectCodePatterns format
    - Custom Placeholders saved/loaded from manifest in CustomPlaceholders format
    - Anchor Removal settings saved/loaded from manifest in AnchorRemoval format
  - **Big Project Optimizations (TASK 72):**
    - Per-line tags (`lines[].tags`): mode_adapter writes tag names during processing
      (e.g. "symbol_conversion", "ellipsis", "protect_code", "placeholder", "prot_compression")
    - Tag-based filter dropdown with 12 entries: All, Changed, Unchanged, Deduplicated,
      Aggressive Deduplicated, Ellipsis Compression, Symbol Conversion, Protected Compression,
      Custom Placeholder, Protected, Anchored, Speaker Name Replacement
    - Progress bar (hidden by default) shown during Apply Rules processing
    - Skip writing `prepro` when `processed == orig` — PIPELINE_FIELDS fallback chain handles reads
    - O(1) `idx_map` lookup replaces N×`set_line_field` calls; single `_mark_dirty()` at end
    - Filter label renamed from "Filter:" to "Search:"
- **Costs Tab (Phase 6, updated Phase 40+):**
  - **Renamed from Estimation to Costs** (class CostsStep, step_name "Costs")
  - Token counting with tiktoken (cl100k_base) or heuristic fallback
  - Model selection dropdown with dynamic registry models and "(No Model)" option
  - **Per-model settings** (Task 4): Save Settings button persists chunk_size,
    chunk_max_tokens, thinking_enabled, use_translated_context, rolling_context
    Before/Between/After, and request_mode per model to API.ini.  Model change
    loads saved settings without auto-saving.
  - **Translation Options row** (Task 4): Thinking checkbox, Translated Context
    checkbox, Rolling Context Before/Between/After spinboxes (0–20)
  - **Request Mode widget** (Task 5): 2×2 grid (Normal / Batch / Flex / Priority)
    with Available (green), Unavailable (red), Selected (blue) states.  Mode
    drives comparison table pricing and persists per-model.
  - **Tokens/Request spinbox** (500-32000): alternative maximum alongside Lines/Request
    - Hybrid chunking mode: whichever limit is reached first triggers chunk boundary
  - **Revised token breakdown** (Task 6): Token Counts panel shows:
    - Input Tokens — content/line tokens only
    - Prompt Tokens — overhead across all requests
    - Cached Tokens — prompt portion cached after first request
    - Total Input (bold) — content + prompt (what gets billed)
    - Output Tokens (est)
  - **Formation-based request counting**: Uses the same 4-step formation pipeline (prompt_builder.py) as Translation step for accurate request counting via `_estimate_via_formation()`
  - **GlobalOptions sync**: Chunk size, max input tokens, and request slicing mode read from Global Options at estimation time
  - Lines/Request spinbox range expanded to 1–99999 to match Model Settings
  - Cost estimate panel with input/output/total breakdown
  - **Prompt Cost** and **Cached Input Cost** sub-rows shown when model supports prompt caching (≥1024 token static prefix). Estimates first-request uncached cost plus remaining-requests cached cost.
  - **Model comparison table** with Cached $/1M column, mode-specific pricing (Normal/Batch/Flex/Priority rates)
  - **Dual estimation workflow** (Task 40.4):
    - Tracks original_complete and preprocessed_complete states separately
    - Auto-estimation on enter when files loaded
    - reset_estimation() method for state management
  - **Progress tracker dual ticks** (Task 40.5):
    - ☐☐ → ☑☐ (original done) → ☑☑ (preprocessed done)
    - Reports dual state via set_dual_ticks() API
  - **Time estimation with concurrent requests** (Task 40.7):
    - Formula: max(requests/concurrent × time_per_request, tokens/speed, requests/rpm × 60)
    - MODEL_PRICING includes concurrent_requests and token_speed per model
  - **Preprocessed lines from manifest** (Task 40.9):
    - Checks Step 4 session data, then manifest prepro[] as fallback
  - Auto-refresh when switching from preprocessing step
  - Output token estimation using language-specific multiplier (1.2x for JP→EN)
  - **Manifest estimation persistence** (Task 7):
    - Saves 10 fields: InputLines, InputTokens, OutputTokens, ContentTokens,
      PromptTokens, CachedTokens, NumRequests, InputCost, OutputCost, TotalCost
    - on_enter restores all breakdown rows, request count, and cost
  - **Estimate/Update Counts** button (Task 8): Shows "▶ Estimate" initially,
    changes to "↻ Update Counts" after first estimation or manifest restore
  - **Backward compatibility**: EstimationStep alias, estimate.py re-exports
- **Translation Tab (Phase 7):**
  - TranslationStep class (step_id=5) with ~900 lines
  - Lines table with per-line status tracking:
    - PENDING, TRANSLATING, COMPLETED, FAILED, SKIPPED states
    - Status icons: ○ Pending, ◐ Translating, ✓ Done, ✗ Failed, ⊘ Skipped
  - **Prompt Editor Panel:**
    - Style preset entry for translation style configuration
    - Game summary scrollable text area (configured via [project].summary_file in CherryAI.ini)
    - Glossary entries scrollable text area
    - Conditional prompts scrollable text area
    - Ban tokens entry (comma-separated: em_dash, smart_quotes, etc.)
  - **Request Options Panel:**
    - API Key selection from saved keys (populated from API.ini)
    - Model selection filtered by selected key's provider
    - Model Settings "Change…" button → opens Global Options at Model Settings panel
    - Translation Options "Change…" button → opens Global Options at Translation Options panel
    - Character Whitelist: comma-separated ranges of allowed characters (manifest-bound to `RequestOptions.CharacterWhitelist`)
    - Character Blacklist: comma-separated characters stripped from translations (manifest-bound to `RequestOptions.CharacterBlacklist`)
    - Ban Tokens entry with preset dropdown
    - `_apply_char_filters()` post-processes each chunk's translations
    - Hidden backward-compat variables for: chunk_size, retry, retries, cache, edit_before, skip_translated, skip_non_source, line_by_line, context_lines (no UI, synced from GlobalOptions)
    - `_sync_from_global_options()` applies GlobalOptions overrides including TranslationSettings (overwrite_translation, skip_non_source_language, retry_strategy, request_slicing)
    - **Edit Before Translation (Task 33.1):**
      - Toggle to enable pre-translation editing
      - Shows EditPreviewDialog modal when enabled
      - Allows editing of preprocessed text before API call
      - Stores edits in manifest `lines[].edited_prepro`
      - Uses edited text in translation if available
  - **Configurable Edit/TLC Prompts (Task 33.2):**
    - Custom prompts accessible via Global Options dialog
    - **Edit Step Prompt:** Configurable instructions for Edit passes
    - **TLC Step Prompt:** Configurable instructions for TLC passes
    - Placeholder support: {source_lang}, {target_lang}
    - Reset to Default buttons for each prompt
    - Stored in [prompts] section of CherryAI.ini (user preference)
    - Factory defaults embedded in `_FACTORY_DEFAULTS_INI_TEXT` (ini_manager.py)
    - Default prompts provided out of the box
  - **Translation Progress Window (Modal):**
    - Progress bar with percentage display
    - ETA calculation based on translation rate
    - Token speed display (tokens/second)
    - Statistics: lines translated/failed, chunks processed, tokens used
    - Pause/Resume/Cancel controls
    - State indicators: ● Running, ● Paused, ✓ Completed, ✗ Failed, ⊘ Cancelled
    - Inline log pane with scrollable history
  - **API Usage Panel (Always Visible):**
    - Tokens used counter
    - Estimated cost display
    - Rate limit status (RPM usage)
  - **Integration Features:**
    - Threaded background translation
    - Automatic line refresh from preprocessing step
    - Session state persistence
    - Simulation mode when API unavailable
  - **Manifest Integration (Phase 26):**
    - RequestOptions nested structure with all request settings:
      - ApiKeyProvider, ApiKeyName, Model, Temperature, LinesPerChunk, RetryStrategy
      - MaxRetries, EnableRequestCaching, LineByLineMode
      - ContextLines, Thinking, ThinkingBudget
    - All options persist to manifest and load on step enter
- **Quality Assurance Tab (Phase 8):**
  - QAStep class (step_id=8) with ~1100 lines
  - Lines table with QA status tracking:
    - Filter modes: All, Errors Only, Warnings Only, Unfixed, Accepted, Rejected
    - Status icons: ✓ Accepted, ✗ Rejected, ⚠ Error, ○ Warning, ✓ OK
    - Issue count display per line
  - **Validation Rules Panel:**
    - 6 default rules with enable/disable toggles:
      1. Placeholder Preservation (ERROR) - Check __PROTECTED__ preserved
      2. Anchor Preservation (WARNING) - Check < > [ ] { } chars
      3. Japanese Character Detection (WARNING) - Flag remaining Japanese
      4. Speaker Format (ERROR) - Check Name: "Dialogue" preserved
      5. Quote Balance (WARNING) - Check quote pairs balanced
      6. Empty Translation (ERROR) - Flag empty translations
    - Severity indicators: [ERROR], [WARNING], [INFO]
  - **Manifest Integration (Phase 25-26):**
    - ValidationRules nested: PlaceholderPreservation, AnchorPreservation,
      JapaneseCharacterDetection, SpeakerFormat, QuoteBalance, EmptyTranslation
    - QAOptions nested: RerunPolicy, MaxJapaneseChars, MaxLineLength
    - All toggles persist to manifest and load on step enter
    - **Session 26:** QA step now persists `qa_overwrite` field to manifest on leave
    - Column "Translated" renamed to "Overwrite" to reflect qa_overwrite field
  - **Issue Types (IssueType enum):**
    - PLACEHOLDER_MISSING, PLACEHOLDER_EXTRA, PLACEHOLDER_MANGLED
    - ANCHOR_MISSING, ANCHOR_EXTRA
    - JAPANESE_REMAINING
    - SPEAKER_FORMAT_LOST, QUOTE_IMBALANCE
    - LINE_TOO_LONG, EMPTY_TRANSLATION, CUSTOM
  - **Issue Details Panel:**
    - Original and translated text display (ScrolledText)
    - Issues listbox with severity indicators
    - Suggestion display for auto-fixable issues
    - Apply Fix button for automatic corrections
  - **QA Options Panel:**
    - Max Japanese characters threshold (default 4)
    - Max line length limit (0 = no limit)
    - Re-run policy: Failed only, All lines, None (skip checked)
  - **Batch Operations:**
    - Accept Selected - Mark lines as reviewed/approved
    - Reject Selected - Flag lines for re-translation
    - Auto-fix Selected - Apply automatic fixes where possible
    - Reset Selected - Clear QA status and issues
  - **Export QA Report:**
    - JSON format with full issue details
    - Text format with summary and detailed breakdown
    - Report includes: summary stats, issues by type, detailed line issues
  - **Integration with functions/validation.py:**
    - validate_placeholder_preserved() for placeholder checks
    - detect_speaker_dialogue_format() for speaker format detection
    - has_japanese() / count_japanese() for Japanese detection
    - extract_anchors() for anchor preservation checks
  - **Summary Panel (Always Visible):**
    - Total lines count
    - Lines with issues count (red)
    - Accepted count (green)
    - Rejected count (orange)
- **Postprocessing Tab (Phase 9):**
  - PostprocessingStep class (step_id=6) with ~1100 lines
  - Lines table with postprocessing status tracking:
    - Filter modes: All, Changed, Needs Retry, Skipped
    - Status icons: ✓ Changed, ⚠ Retry, ○ Skipped, – Same
    - Changes count display per line
  - **Recovery Options Panel:**
    - Placeholder Recovery toggle
    - Bracket Balance Recovery toggle
    - Quote Balance Recovery toggle
    - Whitespace Normalization toggle
    - Restore Code Characters toggle
    - Restore <br> Tags toggle
  - **Symbol Conversion Options:**
    - Enable Symbol Conversion toggle
    - Fullwidth → Halfwidth conversion toggle
    - FULLWIDTH_TO_HALFWIDTH map (25+ character mappings):
      - Punctuation: ！→!, ？→?, ：→:, ；→;, ，→,, 。→.
      - Brackets: （→(, ）→), 【→[, 】→], ｛→{, ｝→}
      - Quotes: ＂→", ＇→'
      - Operators: ＝→=, ＋→+, ～→~, ＊→*
  - **Failure Handling Options (FailurePolicy enum):**
    - Skip (keep original) - Unrecoverable issues preserved as-is
    - Flag for review - Issues marked for manual inspection
    - Queue for retry - Failed lines added to retry queue
  - **Recovery Types (RecoveryType enum - 10 types):**
    - PLACEHOLDER_CASE - Fix __PROTECTED__ → __PROTECTED__
    - PLACEHOLDER_MANGLED - Fix __PR OT__ → __PROTECTED__
    - PLACEHOLDER_MISSING - Restore missing placeholders
    - BRACKET_BALANCE - Fix unbalanced brackets
    - QUOTE_BALANCE - Fix unbalanced quotes
    - WHITESPACE - Normalize whitespace issues
    - CODE_CHARACTER - Restore code characters (<{[]}>)
    - BR_TAG - Restore missing <br> tags
    - SPEAKER_FORMAT - Fix Speaker: "Dialogue" format
    - SYMBOL_CONVERSION - Apply fullwidth→halfwidth
  - **Recovery Actions (RecoveryAction enum):**
    - RECOVERED - Issue fixed automatically
    - NEEDS_RETRY - Cannot fix, needs re-translation
    - SKIPPED - Kept original, no fix attempted
    - FAILED - Fix attempted but failed
  - **Diff View Panel:**
    - Unified diff format display
    - Syntax highlighting:
      - Green for additions
      - Red for deletions
      - Blue for diff headers
    - Line-by-line comparison
  - **Issues Panel:**
    - Recovery action list with symbols:
      - ✓ Recovered, ⚠ Needs Retry, ○ Skipped, ✗ Failed
    - Recovery type and description display
  - **Batch Operations:**
    - Accept Selected - Mark lines as finalized
    - Revert Selected - Restore to translated state
    - Retry Selected - Queue for re-processing
    - Revert All - Restore all lines (with confirmation)
  - **Summary Panel (Always Visible):**
    - Total lines count
    - Changed lines count (blue)
    - Recovered issues count (green)
    - Needs Retry count (orange)
    - Recovery rate percentage
  - **Integration with functions/postprocess.py:**
    - recover_line() for single-line recovery
    - RecoveryResult with issues and recovered text
    - PostProcessManager for batch operations
  - **Data Classes:**
    - RecoveryIssue: line_idx, recovery_type, action, description, position
    - PostprocessLine: idx, original, translated, postprocessed, issues
    - PostprocessOptions: all recovery toggles and failure policy
    - RecoveryStats: lines processed, issues recovered, recovery rate
  - **Manifest Integration (Phase 27):**
    - PostProcessing nested structure with all recovery settings:
      - 8 boolean toggles: PlaceholderRecovery, BracketBalanceRecovery,
        QuoteBalanceRecovery, WhitespaceNormalization, RestoreCodeCharacters,
        RestoreLinebreaks, EnableSymbolConversion, FullwidthToHalfwidth
      - FailureHandling enum: "skip", "flag", "retry"
      - Legacy enum mapping via `_FAILURE_POLICY_MAP` (e.g., "FlagForReview" → "flag")
    - All options persist to manifest and load on step enter
    - 35 tests in dev/test_postprocess_manifest.py
- **Wordwrap & Overwrite Tab (Phase 10):**
  - WordwrapOverwriteStep class (step_id=7, ~950 lines)
  - Preview table with line length indicators:
    - Columns: #, Status, Chars, Lines, Latest, Wrapped Preview
    - Status icons: ✓ Wrapped, ⚠ Exceeds, — No change
    - Filter and checkbox selection support
  - **Format Selector:**
    - RPG Maker MV (48 chars, \n break, 4 max lines)
    - RPG Maker MZ (55 chars, \n break, 4 max lines)
    - Ren'Py (60 chars, \n break, unlimited lines)
    - TyranoScript (45 chars, [r] break, unlimited)
    - Custom (user-defined settings)
  - **Wordwrap Settings Panel:**
    - Mode selection (WrapMode enum):
      - Manual: Simple character-based wrapping
      - RPGMaker: Pretty wrap with punctuation preference
      - Disabled: No wrapping applied
    - Width spinbox (20-200 characters)
    - Break character combo (\\n, \n, <br>, [r], \\r\\n)
    - Max lines spinbox (0=unlimited, 1-20)
    - Prevent orphans checkbox
    - Prefer punctuation breaks checkbox
  - **Per-Tag Wordwrap Settings (TagWrapConfig):**
    - Per-tag sections for dialogue, menu, and custom tags
    - Each tag section has Width / Break Char / Max Lines controls
    - Parser-managed tags shown as read-only ("Wordwrap mandated by Parser Format")
    - "Add Tag" dropdown to add sections for additional tags from filedir/line tags
    - "Remove tag" button on non-standard tags (dialogue/menu always present)
    - Tag resolution: line tag → filedir type → "dialogue" fallback
    - Default configs: dialogue (width=48, max_lines=4), menu (width=48, max_lines=0)
    - Persisted via `WordwrapSettings.TagConfigs` in manifest
  - **Speaker Handling Panel (SpeakerMode enum):**
    - IGNORE: Remove speaker prefix before wrapping
    - SAMELINE: Keep prefix on first line only
    - SAMELINEINDENT: Prefix on first line, indent continuation
    - NEWLINE: Speaker prefix on its own line
    - Descriptions shown for each mode
  - **Ignore Patterns Panel (IgnorePattern enum):**
    - ANGLE: Ignore <tags> (HTML/XML)
    - SQUARE: Ignore [codes] (RPG Maker)
    - CURLY: Ignore {vars} (template)
    - EN: Ignore en() escapes
    - Checkbox toggles with descriptions
  - **Typography Panel:**
    - Style selection (TypographyStyle enum):
      - Western, Japanese, Chinese, Korean, Mixed
    - Use fullwidth punctuation checkbox
    - Use ideographic spaces checkbox
    - Convert quotation marks checkbox
  - **Overwrite Strategy Panel (OverwriteStrategy enum):**
    - OVERWRITE: Replace existing files
    - BACKUP: Create backup before overwrite (default)
    - MERGE: Merge with existing content
    - SKIP: Skip if file exists
    - Merge method selector (MergeMethod enum):
      - Replace All, Replace Changed, Append, Interleave
    - Backup suffix entry (.bak default)
  - **Line Length Ruler:**
    - Visual canvas showing line length vs limit
    - Color-coded bar (green under limit, red over)
    - Limit marker line with dashed style
    - Character count display (current/limit)
  - **Batch Operations:**
    - Accept Selected: Mark wrapped lines as final
    - Revert Selected: Restore to original text
  - **Summary Panel:**
    - Total lines count
    - Wrapped lines count
    - Exceeding lines count (over limit)
    - Average line length
  - **Integration with functions/wordwrap.py:**
    - WordwrapConfig with mode, in1, in2, in3, ignore_codes
    - apply_wordwrap() for batch processing
    - get_wordwrap_modes() for UI metadata
    - smart_wrap() and pretty_wrap() core functions
  - **Data Classes:**
    - WrapLine: idx, original, wrapped, char_count, line_count, exceeds_limit
    - FormatConfig: format_name, wrap_width, break_char, max_lines, enabled
    - WrapOptions: mode, speaker_mode, ignore_patterns, width, break_char
    - OverwriteOptions: strategy, merge_method, backup_suffix
    - TypographyOptions: style, fullwidth/ideographic/quote settings
    - WrapStats: total_lines, lines_wrapped, lines_exceeding, avg_line_length
  - **Manifest Integration (Phase 28):**
    - WordwrapSettings nested structure with all wrap settings:
      - Mode, Width, BreakChar, MaxLines
      - PreventOrphans, PreferPunctuationBreaks
      - SpeakerHandling, Typography
      - TagConfigs (list of per-tag config dicts)
    - All options persist to manifest and load on step enter
    - 40 tests in dev/test_wordwrap_manifest.py
- **Output & Injection Tab (Phase 11):**
  - OutputInjectStep class (step_id=9, ~1324 lines)
  - Preview table showing source→destination mapping:
    - Columns: #, Source, Destination, Format, Lines, Status
    - Status icons: Pending, Success, Failed, Skipped
  - **Output Format Selection (OutputFormat enum):**
    - TXT: Plain text (one line per line)
    - CSV: Comma-separated values
    - TSV: Tab-separated values
    - JSON: JSON array of lines
    - XLSX: Excel spreadsheet
    - Format descriptions and file extension mapping
  - **Naming Strategy Panel (NamingStrategy enum):**
    - SUFFIX: file_translated.txt (default)
    - PREFIX: translated_file.txt
    - REPLACE: Custom pattern replacement
    - SUBFOLDER: output/file.txt
    - Examples shown for each strategy
  - **Backup Strategy Panel (BackupStrategy enum):**
    - NONE: No backup, overwrite directly
    - TIMESTAMP: file.txt.20241201_120000.bak
    - NUMBERED: file.txt.1.bak, file.txt.2.bak
    - EXTENSION: file.txt.bak
  - **Pair Mode Panel (PairMode enum):**
    - TRANSLATED_ONLY: Output translated text only
    - SIDE_BY_SIDE: Original and translated in columns
    - INTERLEAVED: Alternating original/translated lines
    - SEPARATE_FILES: Separate files for each
  - **Destination Browser:**
    - Path entry with browse button
    - Preserve structure option
    - Overwrite existing files toggle
  - **Export Options Panel:**
    - Export manifest checkbox
    - Export logs checkbox
    - Export glossary checkbox (if available)
    - Custom manifest/log paths
  - **Summary Panel (ExportStats):**
    - Total files to process
    - Files written successfully
    - Files failed
    - Files skipped
    - Duration (start_time to end_time)
    - Success rate percentage
  - **Data Classes:**
    - OutputFile: idx, source_path, output_path, format, line_count, status
    - NamingOptions: strategy, suffix, prefix, replace_pattern, subfolder
    - BackupOptions: strategy, extension, timestamp_format
    - OutputOptions: format, destination, naming, backup, pair_mode, encoding
    - ExportStats: total_files, files_written, files_failed, duration, success_rate
    - ManifestExportOptions: export_manifest, export_logs, export_glossary, paths
  - **Helper Constants:**
    - FORMAT_DESCRIPTIONS: User-friendly format descriptions
    - FORMAT_EXTENSIONS: File extension mapping (.txt, .csv, etc.)
    - PAIR_MODE_DESCRIPTIONS: Explanations for each pair mode
    - NAMING_EXAMPLES: Visual examples (input.txt → output.txt)
  - **Manifest Integration (Phase 28):**
    - OutputFormat nested structure with all output settings:
      - PreserveFolderStructure (bool), Format (text), PairMode (text)
      - Encoding (text), FileNaming (text), TextOption (text)
      - OverwriteExistingFiles (bool), Backup (text), BackupExtension (text)
      - ExportManifestFile (bool), ExportProcessingLogs (bool), ExportGlossaryEntries (bool)
    - All 12 options persist to manifest and load on step enter
    - 45 tests in dev/test_output_manifest.py
- **Autosave System (Phase 29, Task 29.1):**
  - ManifestManager autosave with configurable interval
  - **Configuration (from INI [autosave] section):**
    - `enabled` (bool, default true) - Enable/disable autosave
    - `interval_seconds` (int, default 15) - Autosave interval (clamped 5-300s)
    - `save_on_close` (bool, default true) - Save when closing manifest
  - **Autosave Thread:**
    - Background daemon thread monitors dirty flag
    - Only saves when manifest has unsaved changes
    - Auto-starts on create_new() and load()
    - Auto-stops on close()
  - **Properties:**
    - `autosave` - Enable/disable via property
    - `interval` - Interval in seconds
    - `save_on_close` - Save on close behavior
  - **Methods:**
    - `start_autosave()` - Start background thread
    - `stop_autosave()` - Stop background thread
  - 24 tests in dev/test_autosave.py
- **Save Triggers (Phase 29, Task 29.2):**
  - Ensure manifest saved at critical points
  - **Save Trigger Locations:**
    - **On close:** App._on_close() calls ManifestManager.close()
    - **After file load:** InputExtractionStep._save_manifest_after_file_load()
    - **Before translation:** TranslationStep._save_manifest_before_translation()
  - **Implementation Details:**
    - All save methods check is_loaded before saving
    - All save methods have try/except for error handling
    - Logs debug on success, warning on failure
    - Docstrings reference TASK 29.2 for traceability
  - 17 tests in dev/test_save_triggers.py
- **Preset System (Phase 30, Task 30.1):**
  - Save/load/delete operations for named presets
  - **Supported Preset Types:**
    - `style` - Translation style presets (Natural, Literal, etc.)
    - `tone` - Writing tone presets (Neutral, Casual, Formal, etc.)
    - `prompt` - System prompt presets
  - **Storage:**
    - Presets stored in `user/presets/` folder as JSON files
    - `style_presets.json`, `tone_presets.json`, `prompt_presets.json`
  - **PresetManager Class:**
    - Singleton pattern with `get_instance()`
    - `save_preset(type, name, content)` - Add/update preset
    - `load_preset(type, name)` - Get preset content
    - `delete_preset(type, name)` - Remove preset
    - `get_presets(type)` - Get all presets
    - `get_preset_names(type)` - Get preset names
    - `preset_exists(type, name)` - Check existence
  - **Features:**
    - Default presets provided for each type
    - Unicode and special character support
    - Corrupted file recovery (returns defaults)
    - File caching for performance
  - 42 tests in dev/test_preset_manager.py
- **GUI Preset Integration (Phase 30, Task 30.2):**
  - PresetManager accessible from GUI components
  - Preset types available: style, tone, prompt
  - **GUI Methods:**
    - `get_preset_names(type)` - Strings for Combobox values
    - `load_preset(type, name)` - Populate text field content
    - `save_preset(type, name, content)` - Save field content
    - `delete_preset(type, name)` - Remove from list
  - **Integration Points:**
    - PresetManager singleton accessible from any step
    - Default presets auto-loaded on first access
    - Custom presets persisted to user/presets/ folder
  - 21 tests in dev/test_preset_gui.py
- **User Defaults Configuration (Phase 31, Task 31.2):**
  - Allow users to customize defaults and reset to initial values
  - **Storage:**
    - Initial defaults: embedded in `_FACTORY_DEFAULTS_INI_TEXT` constant (ini_manager.py, Session 25)
    - User defaults: `[user_defaults]` section in CherryAI.ini
  - **ini_manager.py Functions:**
    - `get_initial_default()` - Load from embedded `_FACTORY_DEFAULTS_INI_TEXT` constant
    - `get_user_default()` / `set_user_default()` / `has_user_default()` - User defaults
    - `get_effective_default()` - Resolves user > initial > fallback chain
    - `save_as_user_defaults()` - Save multiple values for a section
    - `get_all_user_defaults()` / `get_all_initial_defaults()` - Get all for section
    - `clear_user_defaults()` / `restore_initial_defaults()` - Reset to factory
    - `reload_defaults_cache()` - Clear defaults.ini cache
  - **Global Options Dialog Buttons:**
    - "Save as Default" - Saves current settings as user defaults
    - "Restore Initial Defaults" - Clears user defaults, reverts to factory
  - **Override Chain:** User defaults > Initial defaults > Fallback value
  - 45 tests in dev/test_defaults.py
- **Path Handling (Phase 32, Task 32.1):**
  - All file paths stored as absolute paths
  - **Manifest Storage:**
    - `create_new()` uses `resolve()` for source_files
    - `set_source_files()` uses `resolve()` for absolute storage
    - Paths remain absolute through save/load cycle
  - **INI Storage:**
    - `set_last_manifest()` uses `resolve()` for absolute path
    - `add_to_recent_manifests()` stores absolute paths
  - **Missing File Handling:**
    - Files status: found, recoverable, missing
    - File relocation dialog for missing files
    - User can browse and select new location
    - Relocated files tracked and used for loading
  - **Display:**
    - Paths stored absolute but displayed relative when appropriate
    - Filename extraction for UI display
  - 18 tests in dev/test_paths.py
- **Information Tab (Phase 12):****
  - InformationStep class (step_id=2, ~1150 lines)
  - Project metadata management with LLM inference support
  - **Enums:**
    - InferenceStatus: IDLE, RUNNING, SUCCESS, FAILED
    - MetadataField: PROJECT_NAME, SUMMARY, GENRE, STYLE, TONE, NOTES, SOURCE_LANG, TARGET_LANG
  - **Style/Tone Preset System (Phase 60, updated Session 28-29):**
    - Built-in presets stored in `CherryAI.ini` via `_seed_builtin_sections()`:
      - `[style]`: Natural, Literal, Creative, Formal, Casual, Technical, Literary (7 presets)
      - `[tone]`: Neutral, Serious, Humorous, Dramatic, Lighthearted, Dark, Romantic, Action (8 presets)
    - Each preset is seeded **per-key** so user-added presets are preserved when built-in keys are missing
    - `_migrate_preset_values()` corrects mis-assigned built-in values (e.g. Dramatic having Neutral's text)
    - CUSTOM_PRESET_NAME: "Custom" sentinel — cannot be overwritten or deleted; clears the text field on selection
    - User presets also stored in `CherryAI.ini` `[style]`/`[tone]` sections via `set_preset_text()`
    - `get_all_presets("style"/"tone")` returns merged dict: builtins + user INI entries (INI overrides builtins)
    - `_unique_preset_name()` auto-appends numbers for duplicate names (e.g. "My Style", "My Style 2")
    - Dropdown `<<ComboboxSelected>>` handlers always read **fresh from INI** (not a stale build-time dict)
    - `on_enter()` refreshes preset dicts and combobox `values` from INI before loading manifest bindings
    - `_ensure_style_tone_text()` **always** overwrites text fields for named presets from INI on step enter
      (removed "only if empty" guard — ensures stale manifest CustomStyle content is replaced by preset text)
  - **System Instructions Preset System (Session 28-29):**
    - `[system_instructions]` section in `CherryAI.ini`; built-in "Default" preset seeded from `_BUILTIN_SYSTEM_INSTRUCTION`
    - `[defaults].SystemInstruction` stores the **preset name** (e.g. `Default`) not the full text —
      consistent with `default_style = Natural` and `default_tone = Neutral`
    - `get_default_text("SystemInstruction")` resolves the stored preset name via `get_si_preset()`;
      legacy full-text values (multi-line) are returned as-is for backward compatibility
    - Migration: if `[defaults].SystemInstruction` contains newlines (legacy full text from prior sessions),
      `_seed_builtin_sections()` replaces it with `"Default"` on next load
    - `_on_si_preset_changed()` reads via `ini_manager.get_si_preset(name)` directly (always fresh from INI)
  - **Data Classes:**
    - CharacterInfo: original_name, translation, notes (with to_dict/from_dict; legacy `name`/`gender`/`role`/`speaking_style` auto-migrated on load)
    - ProjectMetadata: project_name, summary, genre, style_preset (str), tone_preset (str), notes, source_lang, target_lang, characters list
    - InferenceOptions: infer_summary, infer_characters, infer_style, sample_size, api_profile
    - InferenceResult: success, metadata, error, duration
  - **Helper Constants:**
    - COMMON_GENRES: List of common translation project genres
    - SOURCE_LANGUAGES: Japanese, Chinese, Korean, etc.
    - TARGET_LANGUAGES: English, Spanish, German, French, etc.
  - **Metadata Panel:**
    - Project name entry field
    - Summary multi-line text area
    - Genre dropdown with common options
    - Custom notes field
    - Source/target language dropdowns
  - **Glossary Panel (formerly Character Notes) — right column:**
    - Moved from left column to right column for grouping with other glossary/database widgets
    - Table with columns: Original, Translation, Notes (Gender/Role merged into Notes for parity with Glossary Settings)
    - Treeview height=8 for taller tables; grid layout with sticky="nsew" for viewport filling
    - Collapsible via compact ▾/▸ button in LabelFrame header (see UI Enhancements below)
    - CharacterDialog with Notes field combining gender, role, other info
    - **Right-click context menu**: Clear Notes (resets notes to empty), Edit..., Remove
    - Add/Edit/Remove character buttons with multi-select support (selectmode="extended")
    - Confirmation dialog with "Don't ask again" option for removal
    - Import from glossary functionality
    - Export character list support
    - Gender inference progress dialog: shows "Checking 'name'" label, progress bar, and count (X / Y); LLM pass runs in background thread to keep UI responsive; Cancel button aborts inference early
  - **Style & Tone Panel (Phase 60):**
    - Style preset dropdown (combobox) with full list of built-in + user presets
    - Editable ScrolledText field (height=1) showing the preset's LLM prompt text
    - On step entry, text fields auto-populate from preset if empty (`_ensure_style_tone_text()`)
    - Save button: saves current text as a new or updated user preset (auto-numbers duplicates)
    - Delete button (width=10): removes user presets (built-in presets cannot be deleted)
    - Tone preset dropdown + ScrolledText (height=1) + Save/Delete buttons (same pattern as Style)
    - "Custom" preset always available, cannot be overwritten or deleted
    - Confirmation dialog with "Don't ask again" for preset deletion
    - Presets reset button in Global Options → Session section
  - **JSON View Panel:**
    - Collapsible raw JSON editor
    - Syntax highlighting (optional)
    - Validate JSON button
    - Import/Export JSON functionality
  - **LLM Inference Panel:**
    - Inference toggle (enable/disable)
    - Sample size slider (lines to analyze)
    - API profile selection
    - Infer button with progress indicator
    - Status display: idle, running, success, failed
    - Auto-populate metadata from sample analysis
  - **Workflow Integration:**
    - Loads metadata from manifest if available
    - Saves metadata to manifest on step complete
    - Provides metadata to Translation step for prompt building
    - Character names integrate with glossary system
  - **UI Enhancements (Phase 41):**
    - Widget renames: "Summary / Description" → "Summary", "Prompt" → "System Instructions", "Code Glossary" → "Code Database"
    - Genre dialog ADD behavior: appends to existing genres instead of replacing
    - "Other" language custom input via simpledialog when "Other" selected in Source/Target Language
    - Style/Tone preset system (Phase 60): replaced graying with full preset management (see Style & Tone Panel above)
    - Glossary table inline editing: 4-column Treeview (Active, Original, Translation, Notes) with double-click editing
    - Import from Analysis: choice dialog (Top N with spinbox / All) for each import; code patterns import as "Detected" category; speakers import as character entries; non-destructive merge (skips duplicates); reads data from manifest via `_get_analysis_step_data()` helper
    - Code Database actions: Preserve ("Do not translate"), Provides Context ("Translate as" hint), Custom Placeholder/Protect/Strip with Anchor/Part of a Span (default "Do not translate"); legacy migration: translate→provides_context, remove→preserve
    - Code Database mass removal: multi-select (selectmode="extended") with batch reverse-index deletion
    - Code Database auto-populate: reads from unified `code_patterns` list with per-pattern count, raw_type, instances, and instance_counts
    - **Code Database collapsible instances**: Patterns with instances display [+]/[-] prefix; double-click on pattern column toggles expansion to show indented instance sub-rows with per-instance counts; patterns with instances sort before those without; instance sub-rows use tag-based index lookup (`pat_{idx}` tags) for correct edit/remove operations
    - Knowledge Base widget: unified mode switch (Glossary / Code Database), search/filter, inline Active column toggle, stored in `user/` directory; Knowledge Base reads only patterns (no instances) from `codedatabase.tsv`
    - Selective glossary: Active column with ✓/✗ toggle per entry, only active entries included in prompt; mixed-selection failsafe popup for Activate/Deactivate
    - **Collapsible right-column widgets**: All three right-column sections (Glossary, Code Database, Knowledge Base) use `_build_collapsible_labelframe()` helper — a header row with ▾/▸ toggle button + bold label + optional extra widgets + horizontal `ttk.Separator`; collapsed widgets hide body via `grid_remove()`, expanded widgets share space via row weight=1; `_reconfigure_right_column_weights()` dynamically adjusts grid weights; `_toggle_collapsible()` swaps button text between "▾" (expanded) and "▸" (collapsed)
    - **Taller tables**: All right-column Treeview widgets use height=8 (up from 4-5) with `sticky="nsew"` and parent `rowconfigure(weight=1)` for vertical expansion; canvas `<Configure>` binding stretches inner frame to viewport height so tables fill available space when window is maximized
    - **Glossary moved to right column**: Glossary (formerly Character Notes) relocated from left column to right column row 0, grouped with Code Database (row 1) and Knowledge Base (row 2)
    - **Style/Tone text display fix**: `_ensure_style_tone_text()` populates text fields from preset when empty on step entry; `_populate_form()` also falls back to preset text
    - **Style/Tone single-line height**: ScrolledText height reduced from 3 to 1 for compact display
    - **Delete button width**: Style/Tone Delete buttons widened from width=8 to width=10 to prevent text clipping
  - **Confirmation Opt-Out System (Phase 60):**
    - `gui/helpers/confirmations.py`: reusable confirmation dialog with "Don't ask again" checkbox
    - `confirm_action(parent, key, title, message)`: custom Toplevel dialog returning True/False
    - Suppressed confirmations stored in INI `[confirmations]` section via `is_suppressed()` / `suppress()`
    - `reset_all_suppressions()`: clears all suppression keys (removes `[confirmations]` section)
    - Used for: character removal, code pattern removal, preset deletion
    - Recovery: Global Options → Session → "Reset All Confirmation Dialogs" button
    - Also in Global Options → Session: "Reset Style & Tone Presets" button (removes user preset keys from ``[style]``/``[tone]`` INI sections; old JSON files are gone)
  - **Preprocessing & Postprocessing (Phase 42):**
    - Anchoring Widget Redesign: 5-column Treeview (Pattern, Action, Anchor Spec, RegEx, Description) replacing old simple fields
    - Custom Placeholders RegEx: _RuleDialog `show_regex` parameter, `regex_result` attribute, regex checkbox UI
    - Protect Code Patterns: Treeview widget with RegEx and Description columns, dict-based pattern storage
    - Aggressive Deduplication UI: checkbox toggle wired to `set_aggressive_dedup()` runtime flag via store config
    - Code Database Integration: `visible` and `spacing` fields in code_glossary manifest, manifest overrides TSV spacing
    - Preview Widget Filtering: dropdown filter (All/Changed/Custom/Deduplicated/Protected/Anchored/Errors) with count label
    - Validation Enhancement: `PLACEHOLDER_POSITION_SHIFT` and `PLACEHOLDER_EXTRA` recovery types, `save_to_manifest()` persistence
    - Process Priority: `functions/process_order.py` with `PRE_PRIORITIES`/`POST_PRIORITIES` dicts, `get_pre_order()`/`get_post_order()`
  - **Translation Tab Overhaul (Phase 43):**
    - Merged Column: "Original" + "Preprocessed" replaced with "To be Translated" column (resolution: edited_prepro → preprocessed → original)
    - Newline Rendering: newlines displayed as ↵ symbol in table cells, 200-char truncation limit
    - Mock Translation: "Mock Translation" as first MODEL_OPTIONS entry, routes to `MockTranslator` in `functions/mock_translator.py`
    - API Provider Management: `APIProviderEntry` dataclass, `PROVIDER_PRESETS` (6 presets: OpenAI GPT-4o-mini, GPT-4o, Gemini Flash, Claude Sonnet, Local LLM, LM Studio), `_PresetPickerDialog` helper dialog
    - API Key Management: "Saved API Keys" Treeview (Name, Provider columns) with Save Key/Load Key/Remove buttons; encrypted storage via `api_config.set_api_key(provider, key, password, name)` in `[api_keys]` as `provider, name = encrypted_value`; master password prompt with first-time setup flow
    - Connection Test: Real `test_api_connection()` using OpenAI-compatible `models.list()` endpoint; returns `(bool, str, list)` with model IDs; threaded execution with specific error messages (auth failure, timeout, connection refused); on success, opens API Test Results dialog with filterable model table and per-model translation testing via `test_model_translation()`
    - Settings Migration: caching.mode in CachingSettings, thinking_enabled/thinking_budget in RequestSettings, rolling_context_lines in RequestSettings; `_sync_from_global_options()` applies overrides on tab enter
    - Retry Refinement: UI shows only Batch + Contextual (`RETRY_STRATEGIES`); `ALL_RETRY_STRATEGIES` kept for CLI with all 4; max retries minimum changed from 1 to 0
    - Prompt Editor Redesign: removed Style Preset and Game Summary textarea; "Preview Requests" button opens `RequestPreviewDialog` showing actual API requests built with the same functions as translation; three view modes (Pure JSON / Formatted with section headers / Plain readable text); toolbar with Jump To (request number), Search with previous/next and match count, and Filter dropdown with checkboxes for 13 prompt parts (Meta, Language, System Instructions, I/O Examples, Style, Tone, Summary, Genre, POV, Conditional Prompts, Glossary, Rolling Context, Input Lines); Ban Tokens LabelFrame with preset dropdown (None/Clean English/Strict)
    - Chunk Sync: LinesPerChunk synced between Costs step and manifest; `_on_chunk_changed()` write-back
    - Language Skip: `detect_line_script()` in `functions/analysis.py` (CJK/kana/hangul/latin detection); `_LANG_SCRIPT_MAP` and `_apply_language_skip()` filter non-source lines; placeholder tokens stripped before detection to prevent skewing ratios
    - Tab Caching: `BaseStep` infrastructure (`_compute_cache_hash`, `_is_cache_valid`, `_update_cache`, `_invalidate_cache`, `_force_refresh`); TranslationStep early-returns on cache hit
    - Performance: SharedTable batch insertion (2000-row batches via `after(1, ...)`); bulk `*children` delete; page-based display (5000 rows/page with Prev/Next navigation, TASK 72); `_refresh_lines()` optimized with batch manifest dict read
  - **QA Step & Validation (Phase 44):**
    - QA Step Placeholder Mode: toggle switch defaults to placeholder, preserves full QA UI behind toggle
    - Shared Validation: Translation uses prompt_adapter retry/recovery, Postprocessing uses recover_line + validate_character_word
    - Validation consistency: validate_placeholder_preserved, validate_line_post, extract_placeholders all verified
  - **Postprocessing Tab Overhaul (Phase 45):**
    - Auto Recovery: Placeholder Recovery, Restore Code Characters, Restore BR Tags always enabled (no toggles); "always on" label in Options panel
    - Bidirectional Symbol Conversion: HALFWIDTH_TO_FULLWIDTH reverse map; "Halfwidth → Fullwidth" checkbox with mutual exclusion trace callbacks against Fullwidth → Halfwidth
    - Failure Handling Redesign: FailurePolicy enum SKIP→WRITE, default WRITE; radio buttons Write (keep as-is) / Flag for Review; Retry hidden
    - Diff View Manual Editing: editable ScrolledText below diff display; "✓ Mark as Fixed" button updates PostprocessLine, writes to manifest
    - Summary Live Updates: ttk.Progressbar during processing; Written/Flagged counters; completion popup (messagebox.showinfo)
    - Filter Options: All/Changed/Written/Flagged filters; PostprocessLine.written and .flagged bool fields; status icons ⚠ Flagged, ✓ Written
    - Overwrite Warning: messagebox.askokcancel before re-running when results already exist
    - UI Cleanup: renamed "Postprocessed Lines" → "Processed Lines"; removed Refresh and Revert All buttons
- **Wordwrap Tab Overhaul (Phase 46):**
    - Mode Dropdown: replaced WrapMode radio buttons with ttk.Combobox; removed RPGMAKER and DISABLED options (MANUAL only)
    - Orphan/Punct Always On: removed checkboxes; hardcoded prevent_orphan=True and prefer_punct_breaks=True; "always on" label
    - Speaker Handling: reduced SpeakerMode to IGNORE and COUNT; replaced radio buttons with ttk.Combobox with dynamic description label
    - Ignore Patterns from Code Database: removed IgnorePattern enum and checkboxes; read-only Treeview table sourced from manifest CodeDatabase entries (pattern/action/example columns)
    - Typography Widget Removed: removed TypographyStyle enum, TypographyOptions dataclass, and entire _build_typography_panel()
    - Overwrite Strategy Widget Removed: removed OverwriteStrategy/MergeMethod enums, OverwriteOptions dataclass, and entire _build_overwrite_panel()
    - Width Dropdown with Pixel: replaced Spinbox with Character/Pixel mode Combobox; Character mode (20-200 chars), Pixel mode (100-2000px + font size 8-72)
    - Overwrite Column in Table: added overwrite field and overwrite_differs property to WrapLine; "↔ Differs" status; Overwrite column in table
    - Table Filter Radios: All/Changed/Exceeding/Overwrite Differs filter radio buttons above Lines Table
    - Max Lines Flag: _simple_wrap() detects exceeds_limit based on max_lines; "⚠ Exceeds" status indicator
- **Output + Pipeline Completeness + Import (Phase 47):**
    - Injection Priority Chain: functions/output.py with get_final_output() 9-level priority (overwrite → wordwr → postpro → edit{N} → tlc{N} → tl → preedit → prepro → orig); resolve_all_lines() batch; get_source_breakdown() stats
    - Dirty Flags: ManifestManager.get_dirty_flags()/set_dirty_flag() storing {process, wordwrap} booleans; pre-export warning dialog listing dirty stages
    - Non-Destructive Default: NamingOptions.strategy default changed from SUFFIX to SUBFOLDER; "translated" subfolder name
    - Failure Logging: ExportStats.failure_log list of {file, error, timestamp} dicts; appended on write failure in _process_export()
    - Import Translations: "📥 Import Translations" button in Input step toolbar; loads .CherryAI.json manifest; matches by orig field; copies prepro/tl/edit{N}/tlc{N}/preedit/postpro/wordwr/overwrite fields; summary dialog
    - Skip Already Translated: TranslationOptions.skip_already_translated bool; checkbox in Request Options; skips lines with non-empty tl field; marks as LineStatus.SKIPPED
    - Output Summary Panel: dirty flag indicators (⚠/✓ labels for process and wordwrap); _update_dirty_flags() refreshes on _update_summary()
- **Pipeline Logging System (Phase 48):**
    - Log Rotation: _rotate_log() archives existing {project}.{step}.log with YYYYMMDD_HHMMSS timestamp; get_step_log_path() canonical path helper
    - Status Vocabulary: LogStatus class (PASS, recovered(), partial_retrial(), partial_failure(), failure()); FailureType class with 11 constants; format_log_status(); derive_step_status() worst-of aggregation
    - Step Log I/O: write_step_log_header()/write_step_log_footer()/append_step_log_entry() with try/except never-block-processing guarantee; UTF-8 encoding
    - translation.log: APIClient._step_log_path attribute; write_log_header/footer/call emit to step log alongside session log
    - postprocess.log: _do_postprocessing() writes header at start, footer with duration/lines/issues/recovered stats at completion
    - wordwrap.log: _apply_wordwrap() run_wrap() writes header with mode/width, footer with duration/total/changed/exceeding stats
    - output.log: _run_export() run_export() writes header with total files/naming strategy, footer with duration/written/failed stats
    - Manifest Metrics: set_step_metrics()/get_step_metrics() on ManifestManager for per-step metric storage with merge-update and deepcopy retrieval
    - Log Export: _export_logs() discovers {pname}.*.log step logs via glob pattern; copies to logs/ subfolder in export destination
- **Request Formation 4-Step Process (Phase 49):**
    - Data Model: LineInfo (index, text, is_invalid, context_marker), RequestFormationConfig (max_lines, min_lines, max_tokens, model), TranslationRequest (lines, line_indices, context_type, is_split, provides_context, receives_context)
    - build_requests(): Shared builder for Estimation and Translation ensuring cost estimates match actual usage
    - Step 1 — Menu/Choice Splitting: _step1_split_menu_choice() groups consecutive menu/choice-marked lines into dedicated requests with no rolling context
    - Step 2 — File Boundary Split: _step2_split_at_file_boundaries() splits at file_end markers; drops marker lines
    - Step 3 — Size Splitting & Balancing: _step3_split_and_balance() splits oversized groups; balances sub-groups evenly; respects both max_lines and max_tokens limits
    - Step 4 — Short Request Merging: _step4_merge_short_requests() merges below-minimum same-type requests up to max_lines; menu/choice never merged
    - Invalid Line Exclusion: _extract_valid_lines() filters placeholders, dedup, context markers before formation
    - Document Order: Final requests sorted by first line index
- **Context Markers Full Implementation (Phase 50):**
    - Data Model: LineEntry.context_marker field (Optional[str]: None, "file_end", "dialogue", "menu", "choice")
    - Helper methods: is_context_marker(), get_marker_type(), VALID_MARKERS constant
    - Serialization: to_dict/from_dict round-trip preserves context_marker
    - Detection: _is_choice_item() (numbered/bulleted patterns), _is_menu_item() (short non-speaker items), _is_dialogue_line() (speaker:dialogue pattern)
    - detect_context_markers() scans contiguous runs of similar-pattern lines with min_run threshold
    - get_active_context_type() scans backwards from any position to find active marker
    - Integration: build_line_infos() converts LineEntry to LineInfo with context propagation
    - File-section tracking: _file_section field prevents Step 4 from merging across file boundaries
    - Conditional Prompts: CONTEXT_PROMPT_DIALOGUE, CONTEXT_PROMPT_MENU, CONTEXT_PROMPT_CHOICE, CONTEXT_PROMPT_UNKNOWN
    - get_context_prompt() reads INI first (get_conditional_prompt()), falls back to hardcoded constants; user-configurable via Global Options → Prompts
    - _construct_system_prompt() accepts optional context_type parameter (Phase 50 slot 2 of 9)
    - Mock translation: context_type extracted from system_prompt header and forwarded to MockTranslator
- **API Error Classification System (Phase 78.2):**
    - 20-category error taxonomy: APIErrorCategory enum covering auth, rate-limit, quota, model, content-filter, billing, timeout, server, connection, and translation-specific errors
    - ClassifiedAPIError dataclass: user_message, remediation steps, is_retryable, is_fatal flags
    - classify_api_error() inspects exception type name and message text patterns to categorise any API error
    - TranslationAbortError exception: wraps ClassifiedAPIError with format_for_display() for user-facing dialogs
    - _API_ERROR_INFO lookup: maps each category to a human-readable message and list of actionable remediation steps
- **First-Request Validation Gate (Phase 78.2):**
    - First chunk of first string sent alone before batch execution begins
    - Fatal errors (auth, model-not-found, quota, content-filter) abort immediately — no retries, no wasted tokens
    - Retryable errors (rate-limit, timeout, server) use standard exponential backoff
    - User sees instant feedback: "First request validated — API configuration OK" or detailed error dialog
- **Request String Sorting by Type (Phase 78.2):**
    - sort_requests_by_type() groups requests into rolling-context chains, sorts by type priority
    - Priority order: Dialogue (0) > Choice (1) > Mixed/Unknown (2) > Menu (3)
    - RC chains before standalone requests; longer strings before shorter at same priority
    - RequestString dataclass: requests, context_type, has_rolling_context, priority, line_count
- **Concurrent Request Execution (Phase 78.2):**
    - _group_chunks_into_strings() maps formation chunks to sorted request strings
    - _process_single_chunk() handles one chunk with thread-safe progress locking
    - _execute_string_sequential() processes all chunks of one string in order (designed for ThreadPoolExecutor threads)
    - _do_translation() uses ThreadPoolExecutor(max_workers=max_concurrent) for parallel string execution
    - Sequential within a string (rolling context preserved), parallel across independent strings
    - Thread-safe progress updates via threading.Lock on translated_lines / failed_lines
    - Abort in any thread sets _cancel_requested and cancels remaining futures
    - Falls back to sequential execution when max_concurrent ≤ 1
- **Context-Type Conditional Prompt Fix (Phase 78.2):**
    - _translate_chunk() now extracts context_type from _formation_ctx and passes it to _build_system_prompt_from_manifest()
    - Enables §5.2 item 7b injection: context-type prompt (Dialogue/Menu/Choice/Mixed) appears in system prompt
    - Previously context_type parameter was accepted but never supplied — prompts were always empty
- **Speaker Duplicate Removal (Phase 51):**
    - Detection: detect_consecutive_speakers() identifies lines with same speaker as previous
    - Regex: _SPEAKER_PREFIX_RE handles half-width `:` and fullwidth `：` colons
    - SpeakerDedupOp dataclass: stores speaker name and colon_char for prepro_ops
    - Preprocessing: remove_duplicate_speakers() strips speaker prefix from duplicate lines
    - Postprocessing: restore_duplicate_speakers() re-adds speaker prefix after translation
    - Round-trip fidelity: remove → translate → restore preserves original speaker format
    - Global Option: RequestSettings.remove_duplicate_speakers (bool, default False)
    - UI: "Speaker Deduplication" checkbox in Request Settings panel
    - Serialization: to_dict/from_dict includes remove_duplicate_speakers key
- **Selective Glossary Per Chunk (Phase 52):**
    - Filter function: filter_glossary_for_chunk(entries, chunk_lines, mode) in glossary.py
    - Mode "all": unfiltered, all entries included (default)
    - Mode "original_only": match Original column against chunk text
    - Mode "original_or_translation": match both Original and Translation columns
    - Entries with empty Translation still included when Original matches (context for LLM)
    - Integration: PromptBuilder uses filter via glossary_filter_mode attribute
    - _construct_system_prompt() calls filter_glossary_for_chunk() instead of inline loop
    - Global Option: RequestSettings.glossary_filter_mode dropdown (all/original_only/original_or_translation)
    - UI: "Glossary Inclusion" combo in Request Settings panel
    - Constants: GLOSSARY_FILTER_ALL, GLOSSARY_FILTER_ORIGINAL, GLOSSARY_FILTER_BOTH, GLOSSARY_FILTER_MODES
- **Global Options Dialog (Phase 13):**
  - GlobalOptionsDialog class (~1100 lines)
  - Centralized options accessible from Tools → Options menu
  - Modal dialog with navigation tree on left, content panels on right
  - **Enums:**
    - OptionSection: API, REQUEST, TRANSLATION, CACHING, LOGGING, SESSION, LIMIT, FILE_IO, PROMPTS, SECURITY (10 sections)
    - OptionCategory: CONNECTION, PROCESSING, APPLICATION (3 categories)
    - LogLevel: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - ThemeMode: LIGHT, DARK, SYSTEM
    - LineEnding: LF, CRLF, CR, AUTO
    - EncodingOption: UTF8, UTF8_BOM, UTF16, SHIFT_JIS, EUC_JP, AUTO
  - **Security Section (added 2026):**
    - Set/change master password via SetPasswordDialog / ChangePasswordDialog
    - Disable password: `disable_password()` decrypts all keys and stores them as plaintext
    - Reset password: `reset_password()` clears password hash/salt and removes all stored keys
    - Plaintext key storage: `set_api_key_plain()` / `get_api_key_plain()` for no-password mode
    - Real-time password strength meter (PasswordStrengthWidget)
    - HiveSystems 2025 tier legend (Instantly/Weak/Good/Great/Safe)
    - bcrypt WF-10 hashing + AES-256 Fernet encryption for API keys (user/API.ini)
    - See doc/passwords.md for full details
  - **Settings Dataclasses (with to_dict/from_dict):**
    - APISettings: provider, api_key, base_url, model, temperature
    - RequestSettings: timeout, retries, rate_limit, chunk_size, max_input_tokens, thinking_enabled, thinking_budget, rolling_context_lines
    - TranslationSettings (NEW): overwrite_translation, skip_non_source_language, retry_strategy, request_slicing
    - CachingSettings: enabled, dir, age (days; 0=unlimited), size (MB; 0=unlimited), mode (strict/line/any/model_only/disabled)
    - LoggingSettings: level, location, debug, api_log
    - SessionSettings: autosave, interval, theme, load_last
    - LimitSettings: banned (comma-sep chars), output (tokens), warnings, safe; SafetySettings = alias
    - FileIOSettings: encoding, lines, preservebom, backup
    - PromptsSettings: edit, tlc, glossary, summary, code, input, tlc_include_* booleans,
      dialogue, menu, choice, unknown (conditional context-type prompts — Session 24+)
    - GlobalOptions: Container for all settings sections, providers list; `safety` property is alias for `limit`
    - APIProviderEntry: name, provider_type, url, api_key, model (to_dict/from_dict) — Task 43.6
    - PROVIDER_PRESETS: 6 presets (OpenAI GPT-4o-mini, GPT-4o, Gemini Flash, Claude Sonnet, Local LLM, LM Studio) — Task 43.6
    - API Key Pipeline: `_save_api_key()`, `_load_api_key()`, `_remove_api_key()`, `_ensure_password_set()`, `_prompt_password()` — GUI ↔ api_config integration
  - **Helper Constants:**
    - SECTION_DESCRIPTIONS: User-friendly descriptions for each section
    - CATEGORY_ORDER: Category → sections mapping for navigation
    - CATEGORY_NAMES: Display names for categories
    - SECTION_NAMES: Display names for sections
    - API_PROVIDERS: Imported from options.py (7 providers: openai, gemini, anthropic, mistral, local, ollama, lmstudio)
    - COMMON_BAN_TOKENS: em_dash, smart_quotes, ellipsis, etc.
  - **API Section:**
    - Provider dropdown (OpenAI, Gemini, Anthropic, Mistral, Local, Ollama, LM Studio)
    - "Details" button inline with provider dropdown; opens Available Models window from registry cache
    - Available Models window: filterable model table (Structured/Batch/No-Optional-Thinking/Cached-Input filters), "Update" button for live API fetch, "Set as Default" button for per-key default model, "Save" button to persist filtered model list
    - Gemini model IDs normalized (strips "models/" prefix) for consistent display
    - Filter checkbox states saved to API.ini (filter_structured, filter_batch, filter_thinking, filter_cached); Structured Output defaults to checked
    - "No / Optional Thinking" filter excludes models that require extended thinking (inverted logic)
    - "Cached Input" filter keeps only models with cached input pricing
    - API key entry with inline Save button and show/hide toggle
    - Base URL entry (auto-filled from provider)
    - Default model per key: `get_default_model()` / `set_default_model()` in api_config.py (stored as `default_model_{provider}_{name}` in [api] section)
  - **Model Settings Section (renamed from Request Section):**
    - Lines per request (chunk size, 1–99999)
    - Max Input Tokens (0–128000, increment 500; 0 = no limit, input lines only)
    - Timeout in seconds
    - Max retries
    - Rate limit (requests per minute)
    - Temperature slider (0.0-2.0, moved from API section)
  - **Translation Section (restructured):**
    - OptionSection.TRANSLATION in CONNECTION category
    - Overwrite Translation checkbox (replaces Edit Before + Skip Translated)
    - Skip Non-Source Language checkbox (default ON)
    - Rolling Context (moved from Model Settings)
    - Speaker Dedup (moved from Model Settings)
    - Retry Strategy dropdown (batch/contextual/isolated/skip)
    - Request Slicing dropdown (Conservative / Efficient)
    - Consistency System dropdown
  - **Caching Section:**
    - Enable/disable caching toggle
    - Cache directory with browse button
    - Max cache age in hours
    - Max cache size in MB
    - Clear cache button
  - **Logging Section:**
    - Log level dropdown
    - Log file path with browse button
    - Debug mode toggle
    - Log API calls toggle
    - Open log file button
  - **Session Section:**
    - Autosave toggle and interval
    - Theme dropdown (light, dark, system)
    - Restore on launch toggle
    - Confirm on exit toggle
    - Confirmation Dialogs: "Reset All Confirmation Dialogs" button (Phase 60)
    - Translation Presets: "Reset Style & Tone Presets" button (Phase 60)
  - **Safety Section:**
    - Ban tokens entry (comma-separated)
    - Common tokens quick-add buttons
    - Max output tokens limit
    - Content warning toggle
  - **File I/O Section:**
    - Default encoding dropdown
    - Line ending style dropdown
    - Preserve BOM toggle
    - Backup originals toggle
  - **Prompts Section (Task 33.2 + Session 24+):**
    - OptionSection.PROMPTS in Processing category
    - PromptsSettings dataclass with edit, tlc, and 4 conditional prompt fields
    - Edit Step Prompt: Multi-line text area for Edit pass instructions
    - TLC Step Prompt: Multi-line text area for TLC pass instructions
    - Placeholder support: {source_lang}, {target_lang} for language substitution
    - Reset to Default button for each prompt
    - **Conditional Prompts Table (Session 24+):** 4-row LabelFrame table configuring context-type prompts:
      - Dialogue: Character voice & emotional nuance; stored as `dialogue` in [prompts]
      - Menu: Concise action-oriented UI text; stored as `menu` in [prompts]
      - Choices: Distinct option formatting; stored as `choice` in [prompts]
      - Unknown/Mixed: Adaptive mixed-content; stored as `unknown` in [prompts]
      - Each row: 3-line Text widget + scrollbar + Reset to Default button
      - Persisted to CherryAI.ini on Apply/OK via set_conditional_prompt()
      - Used by get_context_prompt() in prompt_builder.py for live translation and mock translation
    - **Conditional Prompts (Pattern Triggered):** 11-prompt LabelFrame configuring pattern-triggered prompts:
      - Each prompt: Enabled checkbox + 2-line instruction Text widget + Reset to Default button
      - temp_replacement, delimiter_protection, linebreaks, color_codes, media_commands, text_formatting, ruby_text, ellipsis, speaker_dialogue_format
      - Stored in CherryAI.ini [pattern_prompts] section (enabled + text per prompt)
      - Merged Request Instructions subsection: all_unrelated + block_unrelated texts
      - Loaded from INI by ConditionalPromptManager via _apply_ini_overrides()
    - Prompts stored in [prompts] and [pattern_prompts] sections of CherryAI.ini (auto-seeded from defaults)
    - User customizations saved via Save as Default
    - Factory defaults restorable via Restore Initial Defaults
  - **Dialog Features:**
    - Navigation tree with expandable categories
    - OK/Apply/Cancel buttons
    - Reset to Defaults button
    - Settings persist via callback to session
- **Bug Fixes Applied:**
  - TableRow JSON serialization: to_dict/from_dict for session save/load
  - StepState recursive serialization: _serialize_value handles nested objects
  - Analysis header deduplication: Removed redundant "Step 2:" prefix
  - Analysis data flow: Fixed to access input step's loaded files directly
  - Input step data sharing: Orig lines accessed via manifest `lines[].orig` (TASK 71)
- **Known Issues (Follow-up Phase):**
  - Autosave JSON parse error on corrupt files
  - Manifest not created automatically on file load
  - Session not loading automatically on launch
  - Analysis tab duplicate feature sections
- **Architecture:**
  - gui/app.py - Main application window
  - gui/theme/colors.py - Pastel blue color palette
  - gui/state/store.py - Session state management
  - gui/dialogs/global_options.py - Global options dialog
  - gui/steps/base.py - Abstract step base class
  - gui/steps/input_extract.py - Input tab
  - gui/steps/analysis.py - Analysis tab
  - gui/steps/information.py - Information tab (metadata & inference)
  - gui/steps/preprocess.py - Preprocessing tab
  - gui/steps/costs.py - Costs tab (renamed from estimate.py in Phase 40)
  - gui/steps/estimate.py - Backward-compat redirect to costs.py
  - gui/steps/translate.py - Translation tab
  - gui/steps/qa.py - Quality Assurance tab
  - gui/steps/postprocess.py - Postprocessing tab
  - gui/steps/wordwrap_overwrite.py - Wordwrap & Overwrite tab
  - gui/steps/output_inject.py - Output & Injection tab
  - gui/components/table.py - Shared table component (pagination, ~950 lines)
  - gui/components/ - Reusable UI components
- Legacy GUI preserved at functions/gui_legacy.py

GUI TABLE VIEW & EDITOR (Implemented)
- Professional spreadsheet-like interface for manifest editing (gui/components/table.py)
- **Standard Table Features (Implemented):**
  - Sortable columns (click header to sort)
  - Column visibility toggle (Columns menu)
  - Filter by any field (search bar, renamed from "Filter" to "Search" — TASK 72)
  - Search within table
  - Virtualized scrolling for large files (10k+ lines)
  - Page-based display (5000 rows/page) with Prev/Next page navigation (TASK 72)
  - Count filter shown only where needed (`show_count_filter` parameter — TASK 72)
- **Editing (Implemented):**
  - In-place cell editing (double-click to edit)
  - Multi-select with checkboxes (optional)
  - CSV export functionality
- **Tag Management (Implemented):**
  - Add/remove tags from rows via API
  - Tag-based row styling (error, success, warning)
  - Color-coded rows based on tag severity
- **Advanced Features (Planned):**
  - Undo/Redo stack (Ctrl+Z, Ctrl+Y)
  - Bulk operations on selected rows
  - Search and Replace across fields
  - Translate selected lines only
- **Export (Implemented):**
  - Export visible/filtered rows to CSV
  - Copy selection via system clipboard

REQUEST CACHING SYSTEM (Implemented)
- Cache API responses to avoid resending identical requests
- Significant cost savings for repeat translations or testing
- **Cache Matching Modes:**
  - **strict**: Prompt settings AND model settings must all match
  - **model_only**: Only model name must match (different temperature OK)
  - **any**: Use cached response regardless of model/settings
- **Separate Settings Categories:**
  - Prompt settings: system prompt, glossary, game summary
  - LLM settings: model, temperature, max_tokens, etc.
- **CLI Options:**
  - `--use-cache`: Enable cache lookup
  - `--cache-mode strict|model_only|any`: Set matching mode
  - `--clear-cache`: Clear all cached responses
- **Cache Structure:**
  - Stored at: cache/request_cache.json
  - Indexed by: model → settings_hash → source_lines_hash
  - Per-project or global cache (configurable)
  - TTL expiration (default: 30 days)
  - LRU eviction when size limit reached

PROMPT CACHING — OpenAI (Implemented)
- Leverages OpenAI's automatic prompt caching for gpt-4o and newer models
- **How It Works:**
  - OpenAI caches identical prompt prefixes (≥1024 tokens) across API requests
  - Static prompt sections (language, instructions, style, tone, summary, genre, POV) are assembled first as a stable prefix
  - Dynamic sections (conditional prompts, glossary, rolling context) follow the static prefix
  - Repeated requests with the same static prefix reuse cached tokens automatically
- **Benefits:**
  - Up to 50% reduction in input token cost for cached tokens
  - Up to 80% reduction in latency for cache hits
  - No code changes required for basic caching (automatic)
- **Extended Retention (24h):**
  - Supported models: gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5.x
  - Extends cache lifetime from 5-10 minutes to 24 hours
  - Configured via `prompt_cache_retention` in APIConfig
- **Supported Models:**
  - gpt-4o, gpt-4o-mini, chatgpt-4o
  - gpt-4.1, gpt-4.1-mini, gpt-4.1-nano
  - gpt-5, gpt-5.x
  - o1, o1-mini, o1-preview, o3, o3-mini
- **Statistics Tracking:**
  - Cached token count per chunk in API log
  - Cache hit rate (%) in log footer
  - Estimated cache savings ($) in log footer and step log
  - Cached tokens column in CSV summary
- **Configuration:**
  - `prompt_cache_enabled`: Enable/disable (default: true)
  - `prompt_cache_retention`: "" (default), "in_memory", or "24h"
  - `prompt_cache_key`: Routing hint for cache slot affinity (auto-generated from manifest)
- **Static Prompt Size Check:**
  - Evaluates static prefix (slots 1-7b) estimated token count
  - ≥1280 tokens: "ok" — caching active (80%+)
  - 1024-1279 tokens: "suggest" — borderline, may benefit from more instructions for more hits
  - <1024 tokens: "warn" — below minimum, caching will NEVER activate

PROGRESS INDICATORS (Implemented)
- **CLI Progress:**
  - Progress bar: `[████████░░░░░░░░] 45% (225/500 lines)`
  - Current batch: "Translating lines 201-250..."
  - Multi-file: "File 3/10: dialogue.txt"
  - ETA based on average batch time
  - Rate limit status when throttled
  - Token usage summary per file
- **GUI Progress:**
  - Visual progress bar in status area
  - Batch counter: "Batch 5/20 (lines 201-250)"
  - File counter for multi-file operations
  - Running token usage total
  - Cancel button for mid-translation abort
  - Partial results saved on cancel

RATE LIMIT MANAGEMENT (Implemented)
- Comprehensive tracking for free and paid tiers
- **Request Limits:**
  - Requests per minute (RPM) tracking
  - Daily request limit tracking
  - Per-model limit configurations
- **Daily Limit Features:**
  - Track requests sent today per model
  - Auto-calculate lines to stay under limit (with margin)
  - Split large translations across multiple days
  - Clock-based limit refresh detection (midnight UTC)
  - Pre-request warning: "Will exceed daily limit"
- **Concurrent Requests:**
  - Parallel API requests within RPM limits
  - Configurable: max_concurrent_requests (default: 3)
  - Smart batch queue with priority ordering
  - Automatic throttling on 429 errors
- **Persistent Storage:**
  - user/rate_limits.json tracks usage
  - Survives application restarts

ADAPTIVE CHUNK SIZING (Implemented)
- Automatically adjust chunk size based on error rates
- Improves reliability for problematic content
- **Trigger Conditions:**
  - Error rate >= 20% (configurable)
  - Minimum 7 requests sent before adjustment
- **Errors Tracked:**
  - Empty line responses
  - Complete batch retries needed
  - Timeout errors
- **Adjustment Strategy:**
  - Reduce chunk_size by 25% on trigger
  - Minimum floor: 10 lines per chunk
  - Reset to original after 10 consecutive successes
- **Per-Model Learning:**
  - Track optimal chunk size per model
  - Some models handle larger chunks better
  - Persist learned values across sessions

SPEAKER QUOTE STRIPPING (Implemented)
- Strip quotes from speaker dialogue lines to save tokens
- **How It Works:**
  - Before: `Speaker: "Hello, how are you?"`
  - Sent to LLM: `Speaker: Hello, how are you?`
  - After: `Speaker: "Hello, how are you?"` (restored)
- **Cost Savings:**
  - Saves 2 tokens per speaker line (opening + closing quote)
  - For 50,000 speaker lines: ~100,000 tokens saved
  - Estimated savings: ~$0.80 at typical rates
- **Configuration:**
  - Enabled by default (cost optimization)
  - CLI: `--no-strip-quotes` to disable
  - Config: `strip_speaker_quotes = false`
- **Behavior:**
  - Only applies to `Speaker: "..."` format lines
  - Preserves inner quotes and escaped quotes
  - Tracks stripped lines for accurate restoration
  - Works with speaker format preservation

TOKEN-BASED CHUNKING (Implemented)
- Chunk by token count instead of (or in addition to) line count
- **Chunking Modes:**
  - **Lines Mode** (current): Fixed number of lines per chunk
  - **Tokens Mode**: Fixed token budget per chunk
  - **Hybrid Mode**: Whichever limit reached first (safer)
- **Use Cases:**
  - Files with highly variable line lengths
  - Preventing context window overflow
  - More predictable API costs per batch
- **Configuration:**
  - CLI: `--chunk-mode hybrid`, `--chunk-tokens 4000`
  - Config: `chunk_mode = hybrid`, `chunk_size_tokens = 4000`
- **Token Counting:**
  - Uses tiktoken for accurate counting
  - Caches token counts per line (no recounting)
  - Accounts for system prompt overhead
  - Reserves tokens for output (1.5x input estimate)
- **Benefits:**
  - Better handling of mixed-length content
  - Prevents truncation from context overflow
  - Hybrid mode: line consistency + token safety

PERSISTENT API LOGGING (Implemented)
- API logs persist across sessions (no overwrite)
- **Log File Naming:**
  - Timestamped: api_log_YYYYMMDD_HHMMSS.txt
  - Or append mode with session markers
- **Log Rotation:**
  - Auto-archive logs older than N days
  - Compress old logs automatically
- **Summary File:**
  - api_log_summary.csv for quick overview
  - Fields: date, requests, tokens, cost, model

AUTOMATIC LINE RECOVERY (Planned)
- Fix malformed translations without retrying when possible
- **Recovery Strategies (No LLM Required):**
  - **Placeholder Case Fix**: `__PROTECTED__` → `__PROTECTED__`
  - **Placeholder Whitespace Fix**: `__ PROTECTED __` → `__PROTECTED__`
  - **Quote Balancing**: Add missing closing quotes
  - **Bracket Matching**: Restore missing [], {}, <> pairs
  - **Speaker Format Fix**: Add missing colon or quotes
  - **Code Character Recovery**: Insert missing CODE_CHARS in order
  - **<br> Tag Recovery**: Insert missing line break tags
- **Recovery vs Retry Decision:**
  - If local recovery possible: Apply fix, log warning, continue
  - If recovery impossible: Queue for LLM retry
- **Benefits:**
  - Faster than LLM retries
  - Lower cost (no API calls)
  - Higher throughput
  - Recovery rate tracking per session

RETRY STRATEGY OPTIONS (Implemented)
- Multiple strategies for handling failed line translations
- **Available Strategies:**
  - **Batch Retry** (current default): Failed lines in smaller batch
  - **Contextual Retry**: Include surrounding translated lines as context
  - **Isolated Retry**: Single line with minimal prompt (faster)
  - **Skip and Log**: Mark as failed, continue, report at end
- **Strategy Selection:**
  - CLI: `--retry-strategy contextual`
  - Config: `retry_strategy = contextual`
- **Contextual Retry Benefits:**
  - Better quality for context-dependent lines
  - Uses already-translated neighbors as reference
  - May improve consistency
- **Isolated Retry Benefits:**
  - Faster, cheaper
  - Eliminates cross-line interference
  - Good for independent lines

LINE-BY-LINE TRANSLATION MODE (Implemented)
- Translate one line at a time with minimal prompt
- **Use Cases:**
  - Debugging translation issues on specific lines
  - Files with highly varied content
  - Testing different models with identical inputs
  - Maximum control over individual translations
- **Configuration:**
  - CLI: `--line-by-line` or `--single-line`
  - Very simple prompt: "Translate to {language}. Preserve placeholders."
- **Optional Context:**
  - Include 1-2 adjacent lines as read-only reference
  - `--line-context 2`: Show 2 lines before/after (not translated)
- **Trade-offs:**
  - Higher API call count
  - Less batching efficiency
  - But more reliable for problematic content

TRANSLATION STYLE PRESETS (Implemented — INI-based since 2026)
- Pre-built and user-defined style guides for translation tone and approach
- Built-in presets: Literal, Natural, Creative, Formal, Casual, Technical, Literary
- User presets are saved in ``user/CherryAI.ini`` under the ``[style]`` section
- Tone presets (Neutral, Serious, Humorous, Dramatic, etc.) saved under ``[tone]``
- Saved/deleted via the Information step (Step 3) of the GUI workflow
- Old JSON files (``user/presets/style_presets.json``, ``tone_presets.json``) have been removed
- CLI style: `--style-preset fantasy_medieval`
- Combine presets: `--style-preset fantasy_medieval,archaic_english`
- **Time Period Presets:**
  - `archaic_english`: Thou/thee, -eth/-est verbs, formal address
  - `victorian`: Formal, verbose, British conventions
  - `modern_casual`: Contemporary slang, contractions
  - `futuristic_scifi`: Technical jargon, neologisms
- **Cultural/Regional Presets:**
  - `british_english`: UK spellings, idioms
  - `american_english`: US spellings, idioms
  - `australian_english`: Australian slang
  - `formal_japanese`: Keep honorifics, formal speech
  - `casual_japanese`: Remove honorifics, casual speech
- **Genre Presets:**
  - `fantasy_medieval`: Medieval vocabulary, formal address
  - `fantasy_eastern`: Wuxia/xianxia terminology
  - `noir_detective`: Hardboiled prose, period slang
  - `romance_flowery`: Emotional, poetic
  - `horror_gothic`: Atmospheric, archaic, foreboding
  - `comedy_witty`: Puns, wordplay, comedic timing
- **Character Speech Patterns:**
  - `noble_aristocrat`: Refined, formal, condescending
  - `street_slang`: Urban vernacular, colloquialisms
  - `child_innocent`: Simple words, curious tone
  - `elderly_wise`: Proverbs, measured speech
  - `military_formal`: Orders, ranks, protocol
  - `pirate_nautical`: Nautical terms, "arr" patterns
  - `robot_mechanical`: Precise, clinical, technical
- **Dialect Presets:**
  - `scottish_dialect`: Scottish English patterns
  - `irish_dialect`: Irish English expressions
  - `southern_us`: American Southern dialect
  - `cockney`: London working-class speech

CONTEXT MARKERS (Planned)
- Metadata lines injected by Parser Scripts or detected during Analysis
- Inform how lines are grouped into API requests and which prompt is selected
- **Marker Types:**
  - `File End` — Marks boundaries between files; requests do not cross file boundaries
  - `Dialogue` — Marks dialogue sections; enables Rolling Context and Dialogue prompt
  - `Menu` — Marks menu sections; uses Menu prompt, aims for maximum request size
  - `Choice` — Marks choice sections; uses Choice prompt, aims for maximum request size
- Context Markers are never translated or sent to the LLM
- When no markers are present, lines are treated as "Unknown" (mixed content)
- Quality improvement: Appropriate prompt selection per content type

TYPING (Implemented)
- Classifies source files and individual lines by content type (dialogue, menu, choice)
- Enables per-request prompt selection based on content type
- **File-level classification** (`functions/analysis.py: classify_file_type()`):
  - Uses `detect_speaker()` with 10% threshold
  - >10% speakers → "dialogue"; ≤10% ≥2 → "menu?"; 0 → "menu"
  - Runs during `_sync_lines_to_manifest()` when typing is enabled
  - Result stored in `FileDirEntry.type` field
- **Line-level tagging** (Preview context menu):
  - Users can tag individual lines as Dialogue, Menu, or Choice via right-click
  - Tags stored in `LineEntry.tags` field; displayed in Preview tags column
- **Type resolution** (`functions/analysis.py: resolve_chunk_type()`):
  - Priority chain: per-line tags > filedir type > "unknown"
  - Resolves per API request chunk at translation time
- **Prompt injection** (slot 7b in `build_full_system_prompt()`):
  - Context-type prompt injected as static cacheable content before the cache boundary
  - Pattern-triggered prompts remain dynamic in slot 8
- **GUI controls:**
  - Typing Enabled toggle in UnifiedInputDialog options panel
  - Sort combobox (Filetree / Count / Type) above Loaded Files tree
  - Type column in file tree; Select Type cascade in file context menu
  - Search bar and Tags column in Preview tree
- **INI setting:** `[session] typing_enabled` (bool, default True)

PARSER SCRIPTS (Implemented)
- Game-engine-specific scripts that extend the format system with engine-aware logic
- **Base interface** (`formats/parser_base.py`): `ParserScript` ABC with mandatory `name`, `extract`, `inject` methods
- **Configuration dataclasses:** `WordwrapConfig`, `ForbiddenChars`, `ContextMarkerRules`
- **RPG Maker MV/MZ** (`formats/parser_rpgmaker.py`): Full implementations with wordwrap defaults, forbidden chars, context markers
- **Parser Registry** (`formats/__init__.py`): `ParserRegistry` with register, get, detect, list_parsers
- Auto-detection via `can_handle()` probes file structure (e.g. www/data/*.json, null-first arrays)
- **Wordwrap Integration** (`gui/steps/wordwrap_overwrite.py`): Parser wordwrap configs auto-populate format dropdown
- **Forbidden Characters:** Merged into logit bias via `merge_parser_forbidden_chars()`; auto-replaced or flagged via `replace_forbidden_chars()`
- **API Integration** (`functions/api_client.py`): `apply_parser_forbidden_chars()` method on ApiClient

PARSER HANDSHAKE — UNIFIED I/O PARSER INTERFACE (Implemented)
- Formal contract that every parser must satisfy: Mandatory (M1-M3) and Optional (O1-O8) components
- **Handshake module** (`formats/handshake.py`): `SpeakerInfo`, `ExtractedLine`, `ParserError`, `validate_parser()`
- **Mandatory contract:** M1=Extract, M2=Inject, M3=Identity (format_id+extensions or can_handle)
- **Optional components:** O1=Decrypt, O2=Encrypt, O3=Encoding, O4=Speaker Detection, O5=Wordwrap Config, O6=Custom Wordwrap, O7=Forbidden Chars, O8=Context Markers, O9=Pretty Wrap Hook
- **Handler retrofit (P4):** All registered FormatHandlers and ParserScripts verified against M1-M3 via `validate_parser()`. RPG Maker handler stubs raise `ParserError` with metadata instead of silent no-ops.
- **Tagged extraction** (`parser_base.py`): `extract_tagged()` returns `List[ExtractedLine]` with per-line tag, speaker, context
- **Tag-specific wordwrap** (`parser_base.py`): `wordwrap_for_tag(tag)` returns different `WordwrapConfig` per extraction tag
- **Speaker detection** (`parser_base.py`): `detect_speakers(lines)` returns `List[SpeakerInfo]`
- **Validation:** `validate_parser(parser)` checks M1-M3 compliance, returns list of errors
- **Dynamic format spinbox:** Parser names dynamically appear in format dropdown via `list_parser_names()`
- **Parser-aware extraction:** `_extract_lines()` routes to parser.extract() when format is a parser name
- **Auto-detection:** `_load_file()` tries `detect_parser()` for auto format, falls back to FORMAT_MAP
- **Selection-time validation:** `_validate_parser_selection()` runs `validate_parser()` on parser/format selection; missing mandatory → error popup, blocks load
- **Token validation:** `_validate_extracted_lines()` checks per-line token count; >2048 → error popup + abort, >1024 → warning
- **Token estimation:** `_estimate_tokens()` uses tiktoken when available, else `len(text) * 0.3` heuristic
- **Encoding heuristic:** `_detect_encoding()` 8 KB probe with fallback chain: BOM → parser `detect_encoding()` → utf-8 → shift_jis → cp932 → latin-1

PIPELINE WIRING OF OPTIONAL COMPONENTS (Implemented — P3)
- **`_wire_parser_optionals(format_id)`** in `gui/steps/input_extract.py`: Runs after extraction/manifest creation, writes all parser optional data to manifest fields
- **O4 Speaker Detection:** Calls `parser.detect_speakers()`, writes `SpeakerInfo` list to manifest `characters[]`, sets `Options.ParserHandlesSpeakers = True`; analysis step always runs speaker detection but uses parser-detected names as an allowlist to filter false positives from regex-based detection
- **O6 Custom Wordwrap:** Sets `Options.ParserHandlesWordwrap = True`; wordwrap step delegates to `parser.wordwrap(line)` per line instead of built-in `apply_wordwrap`
- **O9 Pretty Wrap Hook:** `parser.pretty_wrap(text, width, break_char, max_lines)` replaces built-in `pretty_wrap` core algorithm while keeping speaker handling and pipeline logic intact; lighter alternative to O6, used for user-managed tags or as fallback
- **O7 Forbidden Chars:** Serialises `forbidden_chars.to_dict()` to `Options.ParserForbiddenChars`; translation step calls `api_client.apply_parser_forbidden_chars()` to merge into logit bias
- **O8 Context Markers:** Compiles `context_marker_rules`, applies regex patterns to extracted lines, writes `context_marker` tags; `detect_context_markers()` accepts optional `parser_rules` parameter to override built-in heuristics
- **Output Injection:** Output step reads `Options.ParserName`, routes through `parser.inject()` instead of standard format-based writers
- **Manifest Options written:** `ParserName`, `ParserHandlesSpeakers`, `ParserHandlesWordwrap`, `ParserForbiddenChars` (dict), `ParserHandlesContextMarkers`

LIGHT VN PARSER (Implemented)
- Full parser for Light VN visual novel engine scripts (`formats/LightVN.py`)
- Extracts dialogue, menu text (`~文字`/`~ボタン文字`), and variable assignments in document order
- **No deduplication:** Every occurrence is returned including duplicates; deduplication is handled downstream by the Preprocessing step if enabled
- **Extraction tags:** `dialogue` (with speaker info), `menu`, `variable`
- **Speaker format:** `Speaker: text` — speaker tags detected from `~【SpeakerName】` notation
- **Conditional dialogue:** `~もし (condition)` prefix stripped from keys, preserved during injection
- **Code handling:** Balanced bracket matching for `[] {} <> ［］ ｛｝ ＜＞ ⟨⟩ ⟪⟫ 〈〉 《》`
- **Code recovery:** Restores accidentally translated code during injection
- **Angle bracket safety:** Converts non-code `<>` to fullwidth `＜＞` during injection
- **Custom wordwrap:** Balanced line wrapping with orphan avoidance, textbox splitting (O6)
- **Pretty wrap hook:** O9 `pretty_wrap()` — lighter core-wrap replacement used by Step 7 for user-managed tags
- **Tag-specific wrapping:** Dialogue=wrap (60 chars, 3 lines), menu/variable=no wrap
- **Encoding detection:** Priority chain: utf-8, utf-8-sig, shift_jis, cp932, euc-jp, utf-16
- **Auto-detection:** `can_handle()` scans first 200 lines for `~【` or `~文字` patterns
- **Corpus verified:** 55604 total lines, 50212 unique across 1056 .txt files, 843 speakers

WIDTH CONVERSION (Implemented)
- Converts character width from source language to target language encoding
- East Asian languages (Chinese/Japanese/Korean) use fullwidth characters
- Most other languages use halfwidth characters
- Runs during Preprocessing after Symbol Conversion
- No postprocessing reversal needed — the target width is the desired output
- Implemented in `modi/standard_mode.py`

AGGRESSIVE DEDUPLICATION (Implemented)
- Goes beyond standard deduplication by detecting line variants
- Replaces all code with generic `{CODE}` and all numbers with `X`
- Lines identical after substitution are treated as duplicates
- Runs last in preprocessing (after all normalization is complete)
- Variant-deduplicated lines receive the postprocessed result of their unique original
- Implemented in `functions/dedup.py`
- **Per-line tags replace dedup_map:** Dedup state is now stored directly on `LineEntry.tags` as comma-separated strings (`"dedup,D{source_idx}"`) instead of a separate `dedup_by_doc` mapping dict. Only the top `MAX_DEDUP_GROUPS` (10) duplicate groups are processed — the rest are left as-is to bound manifest size. Tag-based restoration in `deduplicate_post()` with legacy `dedup_by_doc` fallback for backward compatibility.
- **Instance tracking:** `detect_individual_codes_batch()` tracks concrete raw code instances per normalized pattern (e.g. `\V[1]`, `\V[2]` under `\V[<NUM>]`) with per-instance occurrence counts. Patterns store `instances: List[str]` and serialized count `[total, inst1_count, inst2_count, ...]` in manifest.
- **GUI Pipeline Integration (TASK 73):**
  - Standard Dedup (`apply_dedup_batch`) at P10 (first in pre) and Aggressive Dedup
    (`apply_aggressive_dedup_batch`) at P90 (last in pre) in `gui/helpers/mode_adapter.py`
  - Per-line tags: display tags ("dedup", "aggressive_dedup") + lookup tags ("D{src_idx}",
    "AD{src_idx}") stored in `lines[].tags` for postprocessing restoration
  - `DEDUP_PLACEHOLDER = "__DEDUP__"` sentinel replaces duplicate content
  - Preprocessing step persists `dedup_map`, `aggr_dedup_map`, `aggr_numbers` in step data
  - Postprocessing (`_restore_dedup_lines`) reads maps from step 3 data, resolves best text
    from in-RAM source lines (postprocessed → translated → original), and restores aggressive
    dedup lines with number substitution via `aggressive_restore_line()`
  - Test suite: `dev/test_dedup_pipeline.py` (26 tests)

SHARED PROMPT BUILDER (Implemented)
- Single source of truth for system prompt assembly: `build_full_system_prompt()` in
  `gui/helpers/prompt_adapter.py`
- Implements all §5.2 slots: Language → System Instructions → Style → Tone → Summary →
  Genre → POV → Conditional → Glossary+Characters → Rolling Context
- **POV slot**: Maps "1st"→"first", "2nd"→"second", "3rd"→"third"; included only when
  `pov_data.confidence == "high"`
- **Costs (Step 4)**: `_get_prompt_tokens()` now calls shared builder with full metadata,
  glossary, characters, POV, and sample lines for accurate prompt overhead estimation
- **Translation (Step 5)**: `_build_system_prompt_from_manifest()` and
  `_build_preview_requests()` both delegate to shared builder so Request Preview matches
  actual translation requests exactly
- Returns `(assembled_prompt, token_breakdown)` where breakdown maps slot names to word counts
- Test suite: `dev/test_prompt_builder_shared.py` (20 tests)

POINT OF VIEW INFERENCE (Implemented)
- Infers narrative perspective (1st/2nd/3rd person) from non-dialogue text
- **Pronoun Pattern Database** (`functions/analysis.py`): `_RAW_POV_PATTERNS` for Japanese, English, Chinese, Korean with compiled caching via `_get_pov_patterns()`
- **Detection Algorithm** (`detect_pov()`): Filters out dialogue (speaker prefix) and menu/choice lines, counts pronoun occurrences, infers 3rd person via protagonist name frequency
- **Confidence Scoring:** High when dominant POV >60%, low otherwise; mixed when secondary ≥20%
- **POVResult Dataclass:** `pov`, `confidence`, `counts`, `total_narrative_lines` with `to_dict`/`from_dict`
- **Prompt Integration** (`functions/prompt_builder.py`): `pov_result` attribute; "Narrative Perspective" section added to system prompt when confidence is "high"
- English patterns compiled with `re.IGNORECASE` for proper case handling

PROTAGONIST DETECTION + POV RE-RUN (Implemented — Task 75)
- Identifies protagonist characters from character glossary and code database
- **Protagonist Functions** (`functions/analysis.py`):
  - `get_protagonists_from_characters(characters)` — scans notes field for "Protagonist" tag (case-insensitive)
  - `get_protagonists_from_code_database(code_patterns)` — finds nameable variables marked as protagonist
  - `run_pov_with_protagonists(lines, language, characters, code_patterns, context_markers)` — merged POV detection across all protagonist names; deduplicates 1st/2nd person counts when multiple protagonists
  - `format_protagonist_prompt(characters, code_patterns, pov_result)` — builds prompt section with format: `Protagonist: {Original} - {Translation} ({Details})\nNarration: {1st/2nd/3rd/Mixed} View`
- **POV Re-run on Protagonist Selection** (`gui/steps/analysis.py`): `_set_speaker_role("Protagonist")` automatically triggers `_rerun_pov_with_protagonists()` which reads all lines, gathers protagonist names, runs merged detection, and stores result in manifest `["POV"]`
- **Prompt slot 4b** (`gui/helpers/prompt_adapter.py`, `functions/prompt_builder.py`): Protagonist+Narration section injected between Tone and Summary; legacy POV slot 7 skipped when protagonist section already includes narration
- No protagonist: when POV confidence is low, shows "Narration: ? - Likely 3rd Person"
- Multiple protagonists: comma-separated in prompt line
- Test suite: `dev/test_protagonist_romanization.py` (18 protagonist tests)

JAPANESE ROMANIZATION — MODIFIED HEPBURN (Implemented — Task 75)
- Converts Japanese hiragana and katakana to Latin-letter rōmaji
- **Module:** `functions/romanization.py` (250+ lines, dependency-free)
- **Mapping Tables:**
  - 46 hiragana base characters + dakuten + handakuten
  - 46 katakana base characters + dakuten + handakuten
  - 15 hiragana digraphs (yōon: きゃ→kya, しゃ→sha, etc.)
  - 15+ katakana digraphs (yōon + extended foreign loan-words: ファ→fa, ティ→ti, etc.)
- **Special Handling:**
  - Small tsu (っ/ッ): doubles the following consonant (かった→katta)
  - Long vowel mark (ー): extends previous vowel (カー→kaa)
  - Non-kana characters (kanji, Latin, digits, punctuation): passed through unchanged
- **Public API:**
  - `romanize(text)` — converts kana to rōmaji
  - `contains_kana(text)` — returns True if text has any kana
  - `romanize_if_japanese(text)` — romanize only if kana detected and no kanji present, otherwise pass through
  - `capitalize_name(text)` — capitalize only the first letter of the text (e.g. "ko-no-ha" → "Ko-no-ha")
  - `contains_kanji(text)` — returns True if text contains CJK ideographs (skips mixed kanji+kana terms to avoid garbled romanization)
- **Glossary Integration:** `name_glossary_functions.py` auto-fills Translation field with romanization when no translation exists and name contains kana
- **Code DB Integration:** `code_glossary_functions.py` auto-fills Notes field with romanization for kana code patterns (NEW, ADD, OVERWRITE modes)
- Test suite: `dev/test_protagonist_romanization.py` (22 romanization tests)

TERM TRANSLATION — MULTI-MODE DISPATCHER (Implemented)
- Unified term translation system replacing the standalone "Romanize" button with "Translate Terms"
- **Module:** `functions/term_translation.py` — dispatches to Romaji or LLM mode
- **Two modes** (configurable in Global Options → Utility → Term Translation Mode):
  - `Romaji` (default) — Uses the built-in Modified Hepburn romanization engine, then capitalizes the first letter. Skips terms containing kanji. Zero dependencies.
  - `LLM` — Uses the API key and model configured in the Utility section. Reads provider/key_name/model from API.ini `[term_translation]` profile.
- **Structured Output**: LLM mode uses strict JSON-schema (`response_format=json_schema`) enforcing `{"translations": [...]}`. Output capped with `max_tokens` and `store=False` to minimise token waste.
- **Two prompt types**: `prompt_type="glossary"` for character name/glossary terms (succinct translation) and `prompt_type="code"` for code pattern labels (succinct explanation). Analysis step routes each type automatically.
- **Configurable prompts**: Global Options → Prompts shows "Translate Terms — Glossary" and "Translate Terms — Code" sections. Templates use `{source_lang}`, `{target_lang}`, and `{count}` placeholders. Stored in CherryAI.ini `[prompts]` section with compiled-in defaults as fallback.
- **API key/model selection**: Global Options → Utility provides dropdowns to select any API key saved in API.ini and a **model Combobox** that auto-populates from `get_provider_models()` when the API key changes. Settings are persisted to API.ini `[term_translation]` section. Gender Inference has its own model Combobox that updates independently.
- **Batch size**: Configurable spinbox (1–100, default 10) controls how many terms are sent per LLM request. The `_worker` calls `translate_terms()` which internally splits the term list by `_get_utility_batch_size()`. Large term lists are processed in batches with per-batch progress updates.
- **Code validation**: `extract_code_segments()` detects bracket-delimited code (balanced matching for `[]`, `{}`, `<>` and fullwidth variants). `validate_translation_code()` checks that all code segments in the original term survive in the translation. Terms with missing code segments are **skipped** (not retried) and reported in the summary.
- **Skip empty results**: Translations that return empty, whitespace-only, or identical-to-original strings are silently skipped — the existing value is left unchanged.
- **Partial save on error**: LLM mode raises `RuntimeError` on API failure. The Analysis step saves any terms successfully translated before the error via `_save_results()`, then shows a messagebox reporting both the error and the count of saved translations. Previously, all progress was lost on error.
- **Error abort**: LLM mode raises `RuntimeError` on API failure instead of silently returning untranslated terms.
- **Public API:**
  - `translate_term(term, source_lang, target_lang, *, mode, context, prompt_type)` — translate one term
  - `translate_terms(terms, source_lang, target_lang, *, mode, context, prompt_type)` — batch-translate (LLM mode respects batch_size)
  - `get_current_mode()` — read configured mode from INI
- **Progress Dialog:** Clicking "Translate Terms" opens a modal progress dialog showing mode, a determinate progress bar, and per-term status (e.g. "5 / 42 — 店員"). Translation runs in a background thread so the GUI stays responsive. A Cancel button lets the user stop early; already-translated terms are saved.
- **GUI Integration:** Analysis step "Translate Terms" button reads source/target language from manifest metadata, calls `translate_terms()` in batches with correct language pair and `prompt_type`. After translation, the findings table Details column updates immediately. Code pattern translations are saved to the project manifest only (not the global TSV).
- **Immediate Persistence:** Translation results are written to disk immediately after each chunk completes via `manifest_manager.save()`, not deferred to the 60-second autosave timer.
- **Code Patterns in Prompt (§5.7):** Code patterns with action "Translate" are included in the glossary section (slot 9) of the system prompt, with per-chunk selective filtering like glossary entries and characters.
- Test suite: `dev/test_term_translation.py` (100 tests), `dev/test_utility_settings.py` (57 tests), `dev/test_utility_integration.py` (7 live API tests)

CONSISTENCY SYSTEM (Implemented)
- Ensures consistent translation of recurring terms across all requests
- **Module:** `functions/consistency.py` — `ConsistencyTerm` dataclass, `ConsistencyStore` collection, type detection, three operating modes
- **Three modes** (Global Option in Request Settings, default: "disabled"):
  - `Preliminary` — Pre-translation LLM passes via `run_preliminary()` to establish canonical translations with multi-pass confidence scoring
  - `During` — `during_scan_output()` captures first translated occurrence as canonical; `during_replace_in_requests()` propagates to subsequent chunks
  - `Check` — `check_consistency()` post-translation verification returning `InconsistencyFlag` instances for manual review
- **Three term types** detected automatically:
  - `Code (Translate)` — `detect_code_terms()` scans Code Database for action='translate' entries
  - `Glossary` — `detect_glossary_terms()` finds entries with empty translation or empty notes
  - `Spans` — `detect_span_terms()` discovers paired tags (RPG Maker color/bold, HTML tags) via regex
- `build_consistency_store()` combines all detection methods into a single `ConsistencyStore`
- Store supports case-insensitive lookup, serialisation via `to_dict`/`from_dict`
- GUI: "Consistency System" dropdown in Request Settings section of Global Options

MOCK TRANSLATION — FLAW TESTING (Implemented)
- Default translation mode when no API providers are configured
- Produces random word replacements for pipeline testing
- Standalone module: `functions/mock_translator.py`
- Integrated via mock routing in `functions/api_client.py` (model == "mock")
- **Deliberate flaw injection** to validate recovery (Phase 56):
  - Malformed placeholders (missing/added characters in `__PROTECTED__` tokens)
  - Anchor manipulation (removed/added at wrong positions)
  - Code intrusion (replacements inside code boundaries)
  - Character surgery (random character insertion/deletion)
- Configurable flaw intensity: mild (10%), moderate (30%), severe (60%)
- `FlawConfig` dataclass controls which flaw types are active
- `FlawReport` tracks every injected flaw for test assertions
- Deterministic via seed-based `random.Random` for reproducible tests
- Tests that Postprocessing recovery handles all failure modes correctly
- No API key or network required
- Test suite: `dev/test_mock_translation.py` (59 tests)

=============================================================================

MANIFEST v3.0 - PROFESSIONAL TRANSLATION WORKFLOW (Implemented)

**Status:** All Phases Complete (3177 tests passing)

CherryAI v3.0 introduces a unified manifest-first architecture that tracks
every stage of your translation project with seamless GUI integration.

HOW IT WORKS

The manifest stores the complete history of each line:

```
Original → Pre-processed → Translated → TLC Checked → Edited → Post-processed → Word-wrapped → Final
```

Each step is saved, so you can:
- See what happened to any line at any stage
- Go back to previous versions if needed
- Continue where you left off
- Run multiple quality check passes

PREPRO_OPS: Per-Line Operation Metadata

Each line now stores its preprocessing operations in `prepro_ops`:
- What patterns were protected and where they were
- What placeholders were inserted
- What ellipsis characters were normalized

This means restoration is now per-line, not global. Each line knows exactly
how to restore itself, even if the translation changed the text significantly.

**Example prepro_ops entry:**
```json
{
  "mode": "Protect Code",
  "pattern": "\\[/?font\\]",
  "items": [
    {"value": "[font]", "context_before": "Hello ", "context_after": "World"}
  ]
}
```

THE WORKFLOW STAGES

1. ORIGINAL (orig)
   - Your source text, exactly as loaded
   - Never changed, always preserved

2. PRE-PROCESSING (prepro)
   - Text after protection rules are applied
   - Code replaced with placeholders like __PROTECTED_0__
   - Special characters normalized

3. TRANSLATION (tl)
   - Result from the AI translation
   - Uses pre-processed text (or original if no pre-processing)

4. TLC PASSES (tlc1, tlc2, ...)
   - Translation Check: AI reviews for accuracy
   - Each pass checks against the original meaning
   - Unlimited passes allowed (tlc1, tlc2, tlc3, ...)

5. EDIT PASSES (edit1, edit2, ...)
   - Quality editing: AI improves style/flow
   - Each pass builds on the previous
   - Alternate with TLC passes as needed

6. POST-PROCESSING (postpro)
   - Placeholders restored to original code
   - Protected content put back in place

7. WORD WRAP (wordwr)
   - Text formatted for display
   - Line length limits applied

8. USER OVERRIDE (overwrite)
   - Your manual edits, always takes priority
   - Saved separately so you can revert if needed

IMPORTANT: Each stage knows where to get its input:
- Translation uses pre-processed text
- TLC checks the translation (or previous edit)
- Post-processing uses the latest TLC/Edit result
- Export uses your override (or word-wrap, or post-processed)

QUALITY CHECK CYCLES

You can run as many TLC and Edit passes as you want:

Default workflow:
```
Translate → TLC1 → Edit1 → TLC2 (done)
```

Extended workflow:
```
Translate → TLC1 → Edit1 → TLC2 → Edit2 → TLC3 → Edit3 (and so on...)
```

Each pass improves the quality:
- TLC catches meaning errors
- Edit improves style
- Repeat until satisfied

GUI PROJECT INTEGRATION (v3.0)

The v3.0 manifest format extends v2.0 with GUI state management:

**New Manifest Sections:**
- `step_state`: Completion status, skipped flags, metadata per GUI step (includes project metadata in `Information.data.metadata`)
- `project_info`: **Removed** — now lives in `step_state.Information.data.metadata`
- `glossary`: Project-specific glossary entries (alternative to global glossary.json)
- `characters`: Speaker database with gender, context, aliases, and occurrence count
- `code_patterns`: Unified code pattern list with count (int or `[total, inst1_ct, ...]`), raw_type, instances, and instance_counts; replaces the former separate `individual_codes` and `findings` dicts

**File Menu Operations:**
- **New Project**: Creates fresh manifest via `reset_manifest_manager()`, then calls `on_new_project()` on ALL 10 step tabs to flush cached instance state (loaded files, analysis results, lines, estimation data, etc.). Prevents old project data from leaking into a new session. Resets to Input tab via `on_enter()`.
- **Open Project**: Checks for unsaved changes ("Save?"/"Don't Save"/"Cancel" dialog) before loading a different manifest; restores all step states (Phase 60)
- **Open Files**: Load source files into current project
- **Save (Ctrl+S)**: Manually save current manifest state

**Automatic State Persistence:**
- Manifest auto-saves when navigating between steps
- Manifest auto-saves when closing the application
- No background autosave thread (reduces complexity)

**Glossary Options (Information Step):**
- **Knowledge Base Enabled/Disabled**: Toggle button enables or disables the Knowledge Base; when enabled, global `globalglossary.tsv` entries are included in translation prompts
- **Copy Project → Global**: Export project glossary entries to global glossary file
- **Project-specific glossary**: Stored in manifest, travels with project
- **Selective Glossary (Phase 41)**: Active/inactive toggle per entry; only active entries sent to prompt
- **Knowledge Base Widget (Phase 41 / Phase 62 / TASK 76)**: Unified widget replacing separate Glossary Settings and Global Glossary/Database widgets; manages cross-project glossary (`user/globalglossary.tsv`, 4-column TSV) and code patterns (`user/codedatabase.tsv`, 10-column TSV) with mode switch, search/filter, column filter, inline Active toggle, and mixed-selection Activate/Deactivate failsafe
  - ✅ **Phase 62 complete**: Widget reads/writes same TSV files; auto-migrates from legacy JSON/CSV/SQLite on first access
  - ✅ **TASK 76 complete**: Added Active column to both TSV files; unified into single Knowledge Base widget with Enabled/Disabled toggle
- **Glossary Entries include `active` field** (Phase 41 / TASK 76): Persisted in TSV and manifest, defaults to True for backward compatibility

**Project Creation Flow:**
1. Load source files (Input step)
2. If no manifest exists, one is created automatically
3. Project metadata set in Information step
4. All state saved to manifest throughout workflow

=============================================================================

UPDATING TRANSLATIONS FOR PATCHED GAMES (NEW)

When a game gets patched and the original text changes, CherryAI can help
you update only what's needed - without re-translating everything.

HOW GAME UPDATE DETECTION WORKS

1. Load Your Existing Manifest
   - Contains all your previous translation work
   - Includes original text, translation, edits, etc.

2. Select the Updated Source Files
   - The new/patched versions of the game text

3. Click Compare
   - Tool automatically detects:
     * UNCHANGED lines (no work needed)
     * MODIFIED lines (need re-translation)
     * NEW lines (added by the patch)
     * DELETED lines (removed by the patch)

4. Export Only What Changed
   - Get a file with just the new/modified lines
   - Send only those to the AI
   - Save time and money

5. Merge Back
   - Updated translations integrate with your existing work
   - Your manual edits are preserved
   - Version history maintained

EXAMPLE

Your game has 10,000 lines. A patch updates 200 lines and adds 50 new ones.

Without CherryAI:
- Re-translate all 10,000 lines
- Cost: ~$15
- Time: Hours of work

With CherryAI:
- Tool detects 9,750 unchanged lines (skip these)
- Extract 250 lines that need translation
- Cost: ~$0.40
- Time: Minutes of work

Your previous work is preserved, and you only pay for what's new.

=============================================================================

FILE FORMATS SUPPORTED

The tool works with:

- TEXT FILES (.txt)
  Plain text, one piece of content per line

- CSV/TSV FILES (.csv, .tsv)
  Spreadsheet data, like comma or tab separated values
  Tool usually translates the first column

- EXCEL FILES (.xlsx)
  Spreadsheet data in Excel format
  Works like CSV but from Excel files

- JSON FILES (.json)
  Structured data with key-value pairs
  Tool translates the text values

- MARKDOWN FILES (.md)
  Preserves code blocks, inline code, and frontmatter (YAML headers).
  Only translates text content while maintaining heading structure.

- LENIENT JSON FILES (.json5, .jsonc)
  Handles JSON with trailing commas, single quotes, unquoted keys,
  and comments (// and /* */). Auto-sanitizes before parsing.

- TRANSLATOR++ FILES (.trans)
  SQLite-based translation databases from Translator++.
  Reads/writes translation pairs directly from the database tables.

- MULTIPLE FILE FORMATS
  You can load a file, prepare it, send to AI, get back result
  then restore it - all in the same format

=============================================================================

BATCH API SUPPORT (Phase 17)

CherryAI supports provider Batch APIs for cost savings of up to 50%.
Batch mode queues requests for asynchronous processing (up to 24h turnaround)
instead of real-time translation.

Features:
- Batch mode toggle in Translation step
- JSONL-based request building and result parsing
- Persistent job tracking (user/batch_jobs.json)
- Submit, poll, retrieve, and cancel batch jobs
- Automatic fallback to real-time if batch is unavailable

Limitations:
- Rolling context is source-language only (no translated context mid-batch)
- Results may arrive hours later
- Not all providers support batch mode

=============================================================================

MULTI-KEY MANAGEMENT (Phase 17)

Manage multiple API keys per provider with automatic rotation on rate limits.

Features:
- Store and label multiple keys ("Personal", "Work", "Free Tier")
- Mark keys as active/inactive/exhausted
- Auto-rotate on rate limit errors or daily exhaustion
- Pool modes: Sequential, Even Distribution, Priority-Based
- Usage tracking per key (requests today, tokens used)
- Persistent storage in user/api_keys.json

=============================================================================

NAMED API PROFILES (Phase 17)

Organize API configurations with names and quick-switching.

Features:
- Name profiles (e.g., "Fast Translation", "Quality Check", "Cheap Bulk")
- Profile-specific display names and system prompt tweaks
- Rename, duplicate, and delete profiles
- Profile display map for UI selection

=============================================================================

USAGE ANALYTICS (Phase 17)

Comprehensive tracking of API usage with SQLite-backed analytics.

Features:
- Records every request: timestamp, model, key, profile, task type, tokens, cost
- Task types: API Tests, Glossary, Game Summary, Translation, TLC, Editing
- Query and filter by any criteria
- Usage summaries with GROUP BY aggregation
- Export to CSV for external analysis
- Data maintenance (purge old records)

=============================================================================

AGENT-ASSISTED MODES (Phase 17)

Optional AI agent modes for interactive help, language assistance, script
authoring, and translation checking.

Modes:
- Interactive Help: Contextual Q&A about CherryAI usage and configuration
- Language Assistant: Language analysis and translation quality review
- Script Author: Generate format handlers and mode plugins (sandboxed)
- Translation Check: Targeted translation review and validation

Safety:
- All write operations sandboxed in dev/sandbox/
- Audit trail in logs/agent/audit.jsonl
- Configurable read/write scopes per mode
- Degrades gracefully without API credentials

=============================================================================

ESTIMATION ENGINE (Phase 17)

Advanced cost estimation with configurable inference options and live pricing.

Features:
- Itemized cost breakdown: translation, summary, glossary, editing, TLC
- Configurable pipeline toggles: batch mode, dedup, rolling context
- Model comparison across all known providers
- Batch API discount calculation (50% savings)
- Persistent inference options for session reuse
- Token estimation from line counts

=============================================================================

MULTI-LANGUAGE UI & TOOLTIPS (Phase 17)

Internationalization support and restored tooltips.

Features:
- Translation system with t(key) function and JSON language files
- Nested key support with dot separation (e.g., "step.input.title")
- Format interpolation with placeholders
- Language auto-detection from user/lang/ directory
- Fallback to English for missing translations
- Tooltip helper with global enable/disable toggle
- Configurable tooltip delay and wrap length
- Currently ships with English (en.json); template for adding more

=============================================================================

SAVING YOUR WORK

The tool automatically creates a MANIFEST for each file you work with.
A manifest is like a "recipe" that contains:
- All your protection rules
- What the tool protected in that file
- How to restore it

Later, when you work with the same file again:
- Load the manifest
- Your rules are automatically applied
- Much faster than setting up everything again

TEMPLATES are similar but for reuse:
- Save useful rule sets as templates
- Use them on new files
- Share with team members

CONFIG FILE (CherryAI.ini)
- The tool remembers your settings:
  - Last folder you opened
  - Window size
  - Default options
  - File history
  - API configuration (see below)

API CONFIGURATION
- To use the built-in AI translation feature, configure the [api] section:
  
  [api]
  provider = openai       # API provider (openai, gemini, anthropic, local)
  api_key = your_key_here # Your API key (required for translation)
  model = gpt-4o-mini     # Model to use for translation
  temperature = 0.3       # Creativity (0.0-2.0, lower = more consistent)
  source_lang = Japanese  # Source language
  target_lang = English   # Target language
  
- Run `py CherryAI.py test` to verify your configuration
- The config file is auto-created with defaults on first run

OPTIONS DIALOG (GUI)
- Access via the "Options" button in the main window
- Provides a tabbed interface for all configuration:

  **General Tab:**
  - Enable debug logging
  - Auto-save state on exit

  **API Tab:**
  - Provider selection (OpenAI, Gemini, Anthropic, Local/Custom)
  - API Key entry (with show/hide toggle)
  - Base URL (auto-populated for known providers)
  - Model selection (filtered by provider)
  - Temperature slider (0.0-2.0 with live display)
  - Test API Connection button

  **Translation Tab:**
  - Source/Target language selection (14 languages supported)
  - Lines per request (chunk size): 10-200
  - Timeout (seconds): 10-600
  - Max retries: 0-10
  - Rate limit (requests/minute): 1-1000

- Changes are validated before saving
- "Reset to Defaults" restores all settings (except API key)

SUPPORTED PROVIDERS
| Provider | Base URL | Models |
|----------|----------|--------|
| OpenAI | (default SDK) | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo |
| Gemini | generativelanguage.googleapis.com | gemini-2.0-flash-lite, gemini-2.0-flash, etc. |
| Anthropic | api.anthropic.com | claude-3-opus, claude-3-sonnet, claude-3-haiku |
| Local | localhost:11434 | custom (for Ollama, etc.) |

=============================================================================

HOW TO USE - STEP BY STEP

FIRST TIME SETUP

1. Start the program
2. Click "Load Translation File"
3. Pick your text file
4. The file appears in the main area

SETTING UP PROTECTION RULES

The main area has sections:

"Custom Placeholder" row:
- Pattern: What to look for (can be regex)
- Replacement: What to put in its place
- Example: Pattern = "\\d{3}-\\d{4}" (phone pattern), Replacement = "__PHONE__"

"Protect Code" row:
- Pattern: Regex to match code
- Example: "<.*?>" for HTML tags

"Standard Helpers" row:
- Checkboxes for built-in rules (ellipses, empty lines, etc.)
- "Enable Deduplication" checkbox to find and skip duplicate lines

Other rows:
- "Remove and Restore" - Remove content during AI translation
- "Temporary Replacement" - Replace text just during translation
- "Free" - Other custom operations

BEFORE SENDING TO AI

Click "Process Pre-TL" button:
- The tool prepares ALL selected files
- Progress bar shows which file is being processed (e.g., "File 1/3")
- Protected content is replaced with placeholders
- One output file generated per input file
- All files are ready to send to AI

Optionally click "Analysis" first:
- Analyzes ALL selected files
- Shows statistics for each file
- Helps you decide which protection rules to use

AFTER AI TRANSLATION

Batch Post-Translation Workflow:
1. Get your translated files from the AI
2. Load the translated files (can select multiple again)
   - Click "Load Translation File" and select all translated files
3. Load your MANIFEST (the tool remembers your rules for the batch)
4. Click "Process Post-TL" button:
   - Tool processes ALL selected translated files
   - Progress bar shows status (e.g., "File 2/3")
   - Placeholders are replaced with original content in each file
   - One output file generated per input file
   - All translations are complete

Testing without AI:

Click "Dry Run" to test:
- Runs prepare and restore locally on ALL selected files
- Shows progress across all files
- Shows if your rules work correctly
- No need to send to AI
- Helps you fix rules before using the real translator

=============================================================================

ANALYSIS - UNDERSTANDING YOUR FILE

Click the "Analysis" button to see:

Basic Stats:
- Total lines in file
- Empty or whitespace lines
- Unique lines (how many different lines)
- Duplicate lines (how many are repeated)
- Average line length
- Longest line

Content Detection:
- Detected code lines (HTML, escape sequences, brackets)
- Individual code patterns with occurrence count, type classification, and examples
- Detected speaker names (ALL speakers listed, ordered by frequency)
- Character glossary info (translation, notes) for each speaker in the Details column

Findings Table:
- All detected speakers, code patterns, languages, and duplicates in one table
- Right-click speakers: Add to Glossary, Set Role/Gender (expanded: Non-Binary/Transwoman/Transman), Set Translation — writes to character glossary (manifest `characters` key)
- Right-click code patterns: Preserve/Remove/Translate, Set Type, Nameable... (Character/Company/Location)
- Count Filter: type `>10` or `<5` in the Count field, or use ≥/≤ toggle button for bare numbers
- Text Filter: search across all columns with substring matching

Nameable Dialog:
- Code patterns like `{{主人公}}` can be marked "Is a Name" or opened via "Nameable..." dialog
- Three modes: Character (John/Jane/Alex Smith), Company (Acme/Globex/Initech Corp), Location (Millfield/Oakville/Riverside)
- Gender-aware name selection for Character mode (Male/Female/Non-Binary)
- Replacement name is stored in character glossary; code pattern is written to Custom Placeholders in Preprocessing for pattern protection and replacement

Automatic Glossary Suggestions:
- Speaker names with detected gender and pronouns
- Code patterns with classification (HTML, variables, colors, etc.)
- Common terms that appear multiple times
- Recommended entries to add to glossary

Language:
- Detected language (e.g., Japanese, English)

Duplication Savings:
- Tokens saved by deduplication
- How many requests needed after dedup

Costs:
- Estimated input tokens
- Estimated output tokens (with JP→EN multiplier if set)
- Estimated USD cost for AI translation

Glossary Match Results:
- How many glossary entries matched in file
- Which glossary terms appeared and where
- Helps verify consistency with previous translations

=============================================================================

GLOSSARY - AUTOMATED LEARNING & CONSISTENT TRANSLATIONS

CherryAI has a powerful built-in glossary that automatically learns from your files.

Automatic Detection:

When you analyze a file, the tool automatically detects:

1. SPEAKERS (from dialogue)
   - Extracts character names from lines like "Character: dialogue"
   - Identifies gender cues from speech patterns (pronouns: 私, 僕, etc.)
   - Detects honorifics (さん, ちゃん, etc.)
   - Learns how each character refers to themselves
   - Learns how others address them

2. CODE PATTERNS
   - Detects technical markers: <tags>, [brackets], {braces}, escape sequences
   - Classifies them: HTML, colors, fonts, variables, line breaks, ruby annotations
   - Creates glossary entries so you remember what each code means

3. TERMS & TERMINOLOGY
   - Identifies recurring technical terms
   - Tracks common game/story terminology
   - Helps you maintain consistent translation

Building Your Glossary:

The glossary starts empty and grows over time:

1. Run Analysis on your first file
   - Tool detects speakers, code, and terms
   - These are automatically suggested for glossary

2. Review suggestions and add entries you want to track:
   - Original: The text as it appears in source
   - Translation: Your preferred translation
   - Notes: Context or special meaning
   - Type: Name, Location, Term, Code
   - Gender: For names (Male, Female, Neutral)
   - How they refer to themselves: Japanese pronoun (私, 俺, etc.)
   - How others refer to them: Honorific (さん, ちゃん, etc.)

3. Use glossary entries:
   - When sending to AI, reference the glossary
   - AI uses your glossary to be consistent
   - After translation, you can verify consistency

4. Next file: Glossary entries from previous files automatically apply
   - New speakers and code are added to glossary
   - You keep building a project-wide translation reference

Enhanced Gender Inference (NEW):

CherryAI uses a multi-signal approach to accurately infer character gender.
This system is fully integrated into the analysis workflow - when you analyze
a file, speakers are automatically processed through comprehensive gender
inference before being added to the glossary.

**Two modes** (configurable in Global Options → Utility → Gender Inference):

- **Script only** (default) — Built-in script analysis using pronouns, honorifics, and explicit markers. No API required.
- **Script + LLM** — Runs script first, then uses the configured LLM API to resolve remaining unknowns via dialogue excerpt analysis. LLM pass executes in a background thread with queue-based polling (`after(100)`) to keep the UI responsive; a Cancel button allows aborting early.

**Structured Output**: LLM mode uses strict JSON-schema (`response_format=json_schema`) with a gender enum of `[Female, Male, Non-Binary, Unsure]`. Output capped with `max_tokens=150` and `store=False` to minimise token waste. "Unsure" maps to "Unknown" internally.

**Configurable prompt**: Global Options → Prompts shows a "Gender Inference" section. The template uses `{name}` and `{excerpt}` placeholders. Stored in CherryAI.ini `[prompts] gender_inference` with a compiled-in default as fallback.

**API key/model selection**: Like Term Translation, the Gender Inference section in Global Options → Utility provides dropdowns for API key and model. Settings are persisted to API.ini `[gender_inference]` section.

**Confidence controls**:
- **Script Confidence**: Two spinboxes (minimum / maximum) control how many script checks run and how many must agree. "Ignore Unknown" excludes no-result checks from the count. "Do all Requests" forces all maximum checks to run (vs. early stop on consensus).
- **LLM Confidence**: Same spinbox pair for LLM checks. Defaults: minimum=3, maximum=5, Ignore Unknown=True, Do all Requests=False (early stop on consensus).

**Error abort**: LLM mode raises `RuntimeError` on API failure (missing key, network error) and shows a messagebox instead of silently skipping.

1. **Explicit Gender Detection** (highest priority)
   - Detects status cards: "名前：リリィ、性別：女性" (Name: Lily, Gender: Female)
   - Recognizes transformation narrative: "リリィは女性になった" (Lily became female)
   - Returns 100% confidence when explicit markers are found

2. **Honorifics from Others** (high priority, 3x weight)
   - When OTHER characters call someone "リリィちゃん" (Lily-chan), the ちゃん strongly suggests female
   - More reliable than self-pronouns for characters with unusual speech patterns
   - Handles transformed characters correctly (e.g., former male now female)

3. **Self-Pronouns** (fallback)
   - Analyzes pronouns used: 俺/僕 (male), あたし/わたくし (female), 私 (neutral/female)
   - Weighted by occurrence count
   - 75% confidence threshold for automatic assignment

4. **LLM excerpt analysis** (Script + LLM mode only)
   - Constructs dialogue excerpts where the character appears as speaker
   - Sends each excerpt to the configured LLM with a structured JSON prompt
   - Runs up to maximum checks, needs minimum agreements for consensus
   - Returns gender and confidence percentage

Edge Case Example (リリィ / Lily):
- Uses 俺様 (arrogant male pronoun) → would suggest Male
- But status card shows 性別：女性 → explicit Female
- Others call her リリィちゃん → confirms Female
- **Result**: Correctly identified as Female despite male pronouns

Workflow Integration:
- `update_glossaries_from_analysis()` passes full file content for comprehensive inference
- Speakers are analyzed with all three detection methods before glossary update
- API-based gender enrichment (Gemini/OpenAI) is now configurable via Global Options → Utility
- No translation should proceed without assured gender for all speakers

Optional LLM Enhancement:

For speaker names specifically, CherryAI can use an AI model to suggest:

- **Name translation**: Convert Japanese name to target language (e.g., イオリ → Iori)
- **Gender inference**: Determine likely gender from speech patterns (Female/Male/Non-Binary/Unsure → maps internally to Unknown)
- **Context notes**: Infer role or relationship from dialogue context

How it works:

1. Configure in Global Options → Utility: Select API key and model for Gender Inference
2. Set mode to "Script + LLM"
3. During analysis: Script runs first, LLM resolves unknowns via dialogue excerpts
4. You review suggestions: Accept, edit, or reject
5. Glossary entries are updated with inferred values

Example:

File has a character "イオリ" who uses feminine pronouns (私). Analysis with AI:
- Suggests translation: "Iori"
- Infers gender: "Female" (based on pronouns and speech patterns)
- Glossary automatically updated
- Next file: Tool knows this character is female and uses correct pronouns

Benefits:

- **Speed**: No manual research needed for name translation
- **Consistency**: AI suggestions help maintain character consistency
- **Learning**: Each file teaches the glossary more about your characters
- **Flexibility**: You can always edit suggestions or turn off AI enhancement

SPEAKER THRESHOLD (Global Options → Utility → Misc)
- **Speaker Threshold** (default 10): Minimum occurrence count for speakers to appear in findings
- Speakers below threshold are collapsed into a single "[+] N Speakers" row in the Analysis findings table
- Below-threshold speakers are excluded from Glossary import and Term Translation
- Manual right-click "Add to Glossary" still works for any individual speaker
- Stored in CherryAI.ini `[utility]` section as `speaker_threshold`

=============================================================================

HOW THE GLOSSARY HELPS

Before AI Translation:
- Share glossary with translator or in prompt
- "Please use these terms and names consistently"
- Translator refers to glossary during translation

After AI Translation:
- Tool can verify glossary term consistency
- Helps spot where AI deviated from glossary
- Points to manual correction spots

Long-term:
- Build a complete project glossary
- Use for multiple files/scripts/games
- Share with team members
- Reduces rework and inconsistencies

=============================================================================

COMMON SCENARIOS

SCENARIO 1: Translate multiple Japanese game scripts at once

1. Load 5 script files (Ctrl+Click to select multiple)
   - Shows "5 files selected"
2. Set up rules:
   - Protect Code: "<.*?>" (for dialogue tags)
   - Custom Placeholder: "\\[.*?\\]" → __BRACKET__ (for command brackets)
3. Analysis: Check statistics across all 5 files
4. Process Pre-TL: All 5 files are prepared in parallel with progress
5. Send all 5 output files to AI translator
6. Get back 5 translated files
7. Load all 5 translated files (Ctrl+Click multiple again)
8. Load manifest
9. Process Post-TL: All 5 files restored automatically with progress
10. Done! All 5 scripts are translated and ready

SCENARIO 2: Batch translate CSV files with duplicates

1. Load 10 CSV files (monthly data, same format)
2. Set up deduplication in "Standard Helpers"
3. Process Pre-TL:
   - Each file: 1000 lines → 300 unique lines (70% savings!)
   - Total: 10,000 lines → 3,000 lines to send to AI
4. Send 3,000 lines to AI (much cheaper!)
5. Receive back translated 3,000 lines
6. Load all 10 translated CSV files
7. Load manifest
8. Process Post-TL: All files automatically restored with duplicates
9. All 10,000 lines translated! (Cost reduced 70%)

SCENARIO 3: Monthly batch using template manifest

1. First month: Set up all rules for the batch
   - Load 5 files
   - Set all protection rules
   - Save manifest (auto-saved)
2. Every month: 
   - Load new 5 files (same names, new content)
   - Load last month's manifest
   - All rules already configured
   - Process Pre-TL and Post-TL automatically
   - Files are ready
3. Much faster - no need to reconfigure each month!

=============================================================================

TIPS & BEST PRACTICES

1. START WITH ANALYSIS
   Always run Analysis first to understand your file
   Helps you decide what to protect

2. TEST WITH DRY RUN
   Before sending to AI, click Dry Run
   Tests if your rules work
   Saves time finding problems

3. SAVE YOUR MANIFESTS
   Each file gets a manifest
   Saves you time on future files
   Track what you've done

4. USE TEMPLATES FOR REPETITIVE WORK
   Set up rules once, save as template
   Reuse for similar files
   Share with team

5. BUILD GLOSSARY GRADUALLY
   Start with common patterns
   Add more entries as you translate
   Your glossary becomes more useful over time

6. KEEP PROTECTION PATTERNS SIMPLE
   Complex regex can slow things down
   Test patterns before using on real files

7. CHECK AFTER TRANSLATION
   After Process Post-TL, quickly scan the result
   Look for anything that doesn't look right
   Most translations are perfect, but worth a quick check

=============================================================================

FREQUENTLY ASKED QUESTIONS

Q: What if I make a mistake in my protection rules?

A: Use Dry Run to test before sending to AI. If you find a mistake:
   1. Fix the rule
   2. Run Dry Run again to verify
   3. Then send to AI
   
   Or, just run Process Post-TL again with fixed rules.

Q: Can I use this with different AI translation services?

A: Yes! The tool prepares text for any AI translator:
   - OpenAI (ChatGPT)
   - Google Translate API
   - DeepL
   - Any other service
   
   Just prepare the text with Process Pre-TL, send it to the service,
   then restore with Process Post-TL.

Q: How much money do deduplication and glossaries save?

A: Deduplication: If 50% of your lines are duplicates, send only 50% to AI
   Glossary: Helps avoid mistakes, but doesn't directly save money
   Together: Can reduce AI costs by 30-50% depending on your files

Q: Can I undo a Process operation?

A: The tool keeps the original file. You can:
   1. Reload the original file
   2. Load a different manifest (if you saved one)
   3. Try again with different rules

Q: What languages does this work with?

A: The tool itself is language-agnostic. It works with any text.
   You can protect any content, translate any language.
   Language detection in Analysis is best for Japanese/English currently.

Q: Can I translate multiple files at once?

A: Yes! That's the default behavior:
   1. Click "Load Translation File"
   2. Select one or more files (Ctrl+Click or Shift+Click for multiple)
   3. Shows "N files selected" if multiple
   4. Click "Process Pre-TL" to process all files
   5. Files are output with "_pre" suffix
   6. Send all outputs to AI translator
   7. Load all translated files back
   8. Load manifest and click "Process Post-TL"
   9. All files are automatically post-processed
   
   This saves time compared to processing one file at a time!

Q: How accurate is the cost estimation?

A: The tool estimates based on:
   - Character count heuristics
   - OpenAI token patterns
   - Language-specific multipliers (JP typically needs more tokens)
   
   Estimates are usually within 10-20% of actual costs.
   Use for budgeting, not exact pricing.

=============================================================================

COMMAND LINE INTERFACE (CLI)

CherryAI can be run from the command line for automation or headless operation.

1. Estimate Cost
   Check token counts and estimated cost for a file or entire folder.
   
   Usage:
   `py CherryAI.py estimate <path>`
   
   Examples:
   `py CherryAI.py estimate "C:\Games\MyGame\Data"` (Scans all supported files recursively)
   `py CherryAI.py estimate "C:\Games\MyGame\Data\Map001.json"` (Single file)

2. 1-Click Translate
   Run the full "1-Click" pipeline (Pre -> Translate -> Post) from the command line.
   Includes a confirmation step before starting the API calls.
   
   Usage:
   `py CherryAI.py translate <path> [options]`
   
   Options:
   - `-s, --source`: Source language (default: from config)
   - `-t, --target`: Target language (default: from config)
   - `-n, --lines`: Translate only first N lines (partial mode, default: 200)
   - `-y, --yes`: Skip confirmation prompt
   
   Examples:
   `py CherryAI.py translate "C:\Games\MyGame\Data"`
   `py CherryAI.py translate "file.txt" -s ja -t en -n 100` (First 100 lines)
   
   Note:
   - Uses default settings and standard helpers.
   - Requires API key to be configured in CherryAI.ini.
   - Automatically saves output files with `_translated` suffix.
   - **API Logging**: Automatically creates an API log in `logs/api_log.txt`
     capturing all request-response pairs. API keys are automatically redacted.
     Logs use human-readable formatting with numbered lines and section headers.
     
   API Log Format:
   The log file is formatted for human readability, NOT as raw API data:
   - **Header**: File name, timestamp, total lines/chunks, model info
   - **Statistics**: Cost per 1M tokens (FREE noted for Gemini), structured output mode
   - **Skipped Lines**: DEDUP markers, symbol-only lines, no-source-lang lines
   - **Missing Sections**: Lists components not included (Glossary, Rolling Context)
   - **Content Warnings**: Explicit content detection results (if any)
   - **Chunk Format**: `CHUNK #N - TIMESTAMP | Tokens: X in / Y out | Running Total: Z`
   - **Section Headers**: `[SYSTEM PROMPT]`, `[USER MESSAGE]` (LOG-ONLY, not sent to API)
   - **Line Numbers**: Each input/output line numbered (`[  1]`, `[  2]`)
   - **Footer**: Final chunk count, total tokens, estimated cost
   
   Content Warning System:
   The tool detects potentially explicit content that may trigger API refusals:
   - Terms like "erotic", "explicit", "sexual", "violent" are detected
   - A warning is logged to both console and api_log.txt
   - Recommendations provided (use Gemini, local models, etc.)
   - Disable with `content_warning_enabled = false` in CherryAI.ini [api] section
   
   Prompt Optimization:
   System prompts are automatically optimized to reduce token usage:
   - Empty sections (game summary, glossary, etc.) are skipped
   - Conditional instructions are concise (1-2 lines each)
   - Protected code uses short `__PROTECTED__` placeholder
   - Modular prompt structure: base_instructions.txt, output_examples.txt

3. Diagnostic Test
   Run a comprehensive test of the entire pipeline to verify your setup.
   Tests dependencies, configuration, file I/O, pre-processing, API connection,
   translation (live), and post-processing.
   
   Usage:
   `py CherryAI.py test`
   `py CherryAI.py test --skip-api` (Offline mode, skips API tests)
   
   What It Tests:
   - Dependencies: Checks required and optional packages (openpyxl, openai, tiktoken)
   - Configuration: Validates CherryAI.ini, especially the [api] section
   - File I/O: Writes and reads a test file to verify file operations
   - Pre-Processing: Runs sample Japanese text through the pre-processing pipeline
   - API Connection: Connects to your configured API provider and fetches models
   - Translation: Sends a minimal test (2 lines) to verify translation works
   - Post-Processing: Validates placeholder restoration logic
   
   Output:
   - Each stage shows PASS/FAIL with timing
   - Detailed error messages for any failures
   - Summary report at the end
   
   Use Cases:
   - First-time setup: Verify everything is configured correctly
   - Troubleshooting: Identify which component is failing
   - After updates: Ensure the pipeline still works
   - Before large batches: Confirm API is responding

=============================================================================

GETTING HELP

If something doesn't work:

1. Check the Analysis output
   - Shows what the tool detected in your file
   - Often shows what went wrong

2. Check the Logs folder
   - Each operation creates a log
   - Shows details of what the tool did

3. Use Dry Run
   - Tests rules without committing
   - Shows what would happen

4. Check your manifest file
   - It's a text file (JSON format)
   - Shows exactly what rules were saved

5. Reload and try different rules
   - Most issues are wrong patterns
   - Simplify your rules and try again

=============================================================================

TECHNICAL NOTES (For Advanced Users)

Manifest File Format:
The manifest is JSON:
- "operations": Array of your rules
- "mappings": What was protected in each file
- "metadata": File info, timestamp, language detected

Pattern Types:
- Regular text: Matches exactly
- Regex: If checkbox is marked, uses regex patterns
- Can test patterns in Analysis

File Support:
- Large files: Can handle files with 100,000+ lines
- Encoding: Works with UTF-8, UTF-16, other common encodings
- Delimiters in CSV/TSV are auto-detected

Performance:
- Most files process in < 1 second
- Large analysis runs in 5-10 seconds
- Pre/Post processing is nearly instant

=============================================================================

TESTING

CherryAI uses a two-tier testing strategy:

1. SCRIPT TEST (Fast, No LLM)
   - 1497 unit tests in `dev/test_*.py`
   - Run with: `pytest dev/ -v`
   - Tests manifest, modi integration, functions, replication, validation, config

2. API TEST (Full Pipeline with LLM)
   - 7-stage integration test in `functions/One_Click_Test.py`
   - Run with: `python CherryAI.py test`
   - Tests dependencies, config, I/O, pre/post processing, API

For detailed test documentation, see `doc/tests.md`

=============================================================================

## Dynamic Model Registry

CherryAI automatically discovers and prices available models from OpenAI, Google Gemini,
and Mistral. Model information (pricing, rate limits, capabilities) is:
- Fetched from provider APIs when API keys are available
- Cached locally in `user/API.ini` for offline use
- Updated via the "⟳ Refresh Models" button in Global Options
- Automatically up-to-date via curated built-in fallback data (Feb 2026)

**Models included** (27 built-in, more fetched live with keys):
- OpenAI: GPT-5.2/5.1/5/5-mini/5-nano, GPT-4.1 family, GPT-4o family, o3/o4-mini reasoning
- Google: Gemini 3.x/2.5/2.0 Flash and Pro variants
- Mistral: Mistral Large/Medium/Small 3.x, Magistral reasoning, Codestral, Ministral

**Per-model information stored**: input/output/cached/batch/flex/priority pricing (USD/1M tokens),
RPM/RPD rate limits per tier, context window, structured output, thinking mode,
logit_bias support, temperature range.

**API Key Management**: Encrypted or plaintext API key storage in `user/API.ini` with
multiple named keys per provider (format: `[api_keys]` → `provider, name = encrypted_value`).
Keys encrypted with AES-256 via Fernet, keyed from a master password (bcrypt WF-10).
Password can be disabled (stores keys as plaintext) or reset (clears all keys).
Connection testing via `test_api_connection()` validates keys against provider endpoints
using the OpenAI-compatible `models.list()` call, returns model ID list for the
API Test Results dialog with filterable model table and per-model translation testing.

=============================================================================

## Request Preview Overhaul (Task 74)

**Informative Section Headers**: Preview Requests now renders each section with a
descriptive label: `=== Meta (Section headers are for display only) ===`,
`=== Glossary (Only terms present in this chunk are included) ===`, etc. 12 sections
have descriptions via the `SECTION_DESCRIPTIONS` dict.

**Renamed custom_notes → system_instructions**: The `custom_notes` metadata field has
been renamed to `system_instructions` across all files (information.py, manifest_manager.py,
prompt_adapter.py, translate.py). Manifest migration reads both keys for backward compat.

**Formation-Based Chunking**: Translation now uses the 4-step `build_requests()` pipeline
from `prompt_builder.py` instead of simple fixed-size splitting:
1. Split at menu/choice context markers
2. Split at file boundaries (from manifest `filedir`)
3. Balance sub-groups to stay within `max_lines`
4. Merge short requests within file boundaries

Falls back to simple chunking when the formation pipeline is unavailable.

**Rolling Context**: Each chunk receives context from prior translations when:
- The formation pipeline marks it with `receives_context=True`
- The Global Options `rolling_context_lines` setting is > 0
- Previous chunks produced translations (stored in `rolling_ctx_buffer`)

Preview Requests shows a descriptive placeholder for chunks that will receive rolling context.

**Selective Glossary/Conditional Per-Chunk**: `build_full_system_prompt()` accepts
`chunk_lines` parameter. When provided, only glossary entries whose source term appears
in the chunk's lines are included; characters are filtered by `original_name`; conditional
prompts are detected against chunk lines instead of sample lines.

**Cross-Request Search**: The Preview Requests dialog now searches across all requests.
Match counter shows "N of M (across K requests)". Next/Prev navigation automatically
switches between requests when matches span boundaries.

**Request Logging**: Global Options → Application → Logging includes a new
"Log outgoing requests as JSON" checkbox. When enabled, each API request writes a
timestamped JSON file to `logs/requests/` containing model, temperature, system prompt,
and input lines — useful for comparing Preview Requests against actual requests.

## Phase 78 Improvements

**Manifest Sample Removal (Task 1)**: Manifests no longer store redundant
`SampleText` / `SampleTranslation` fields.  Existing manifests are migrated
transparently on load; the fields are dropped from the data dictionary and
never written back.

**Speaker Replacement Fix (Task 2)**: Speaker name replacement now operates
on the resolved dialogue portion only, preventing false matches inside stage
directions or narration blocks.

**Improved Estimation Skip Logic (Task 3)**: The preprocessed estimation
shares the formation pipeline with the actual translation but applies
additional skip rules: lines matching "Skip Non-Source Language Lines",
"Overwrite Translation", symbol-only dialogue (e.g. `Rin: "..."`), and
generic placeholders (`__PLACEHOLDER__`, `__DEDUP__`) are excluded via the
`_get_skip_indices()` helper.

**Prompt Overhead Display (Task 4)**: The costs step now shows
`~Z total (Y Requests, ~X per)` instead of the old
`~X tokens/request × Y requests = ~Z total` format.  Request Preview
computes separate prompt-token and input-token counts using `count_tokens()`
instead of the `len // 4` heuristic.

**Blacklist / Whitelist Validation (Task 5)**: Filters no longer strip
offending characters.  Instead the translation is validated and three
configurable strategies determine the response:

* **Exchange Forbidden Characters** (default on) — replaces violations via
  the manifest's Autofix Map.
* **Flag for QA Review** (default on) — marks lines that still have
  violations with status `NEEDS_REVIEW` so later steps can surface them.
* **Retry Lines with Forbidden Characters** (default off) — blanks the
  translation and resets the line to `PENDING` for another API attempt.

Entries now support `re=<pattern>` for regex matching, `\,` for literal
commas, and plain words — all comma-separated.  Three new checkboxes appear
in Global Options → Translation → Character Validation.

**Term Translation + Code DB (Task 6)**: The Analysis step exposes a
"Translate Terms" button that fills the `translation` column for characters,
speakers, and glossary entries using the configured term translation mode
(Romaji/LLM, set in Global Options → Utility).  The
Code Database TSV has a `Translation` column (between Pattern and the
former Type column, now renamed `Category`).  Code pattern translations
are synced to the manifest `code_patterns` for cross-tab persistence.

**Rolling Context Fix (Task 7)**: The first request of each file section
now receives `receives_context=False`, preventing stale context from a
prior file from bleeding into the next.  The rolling-context buffer is
cleared at file boundaries.  Preview Requests shows actual original lines
instead of placeholder text.

**Slicing Efficient Mode Fix (Task 8)**: Efficient-mode slicing uses
`min_lines = max(5, chunk_size // 2)` vs conservative's
`max(2, chunk_size // 5)`.  With the rolling-context fix (Task 7) ensuring
correct file-boundary detection, efficient mode now merges aggressively
within file sections while respecting section boundaries.

**Global Options Scrolling (Task 9)**: The Global Options dialog sections
now scroll correctly when content overflows the visible area.

**Model Settings Lines/Request (Task 10)**: The `_chunk_var` used by the
costs step and the translation step are fully decoupled, so changing the
lines-per-request slider in Model Settings no longer affects translation
chunk sizes and vice-versa.

## Provider Handshake — Unified LLM Provider Interface

A pluggable provider abstraction layer that moves all provider-specific
logic out of scattered if/elif branches into self-contained provider
classes registered in a global registry.

### Architecture

- **`providers/`** — new top-level package alongside `functions/`, `modi/`, `formats/`
- **`ProviderBase`** — abstract base class with 7 mandatory + 8 optional methods
- **`ProviderRegistry`** — global registry mapping provider slugs to instances
- **`validate_provider()`** — verifies ABC compliance at registration time

### Registered Providers (7)

| Provider | Class | Key Features |
|----------|-------|-------------|
| OpenAI | `OpenAIProvider` | Reference implementation. GPT-5 family (no temperature, builtin reasoning), o-series reasoning, prompt caching, batch mode |
| Google/Gemini | `GoogleProvider` | OpenAI-compatible. Thinking via FALLBACK_MODELS lookup |
| Mistral | `MistralProvider` | OpenAI-compatible. Temperature max 1.0, Magistral thinking |
| Anthropic | `AnthropicProvider` | OpenAI-compatible. Explicit thinking mode (extra_body.thinking), budget 10K default |
| Local | `LocalProvider` | Direct ProviderBase. json_schema format, $0 pricing, no API key |
| LM Studio | `LMStudioProvider` | Inherits Local. Port 1234 |
| Ollama | `OllamaProvider` | Inherits Local. Port 11434 |

### Shared Types

- `TokenUsage` — 7-field token accounting (prompt, completion, cached, reasoning, etc.)
- `ProviderResponse` — content + usage + finish_reason + raw
- `ThinkingConfig` — available/mode/budget with `build_params()` helper
- `TemperatureConfig` — supported/min/max/default
- `CachedInputConfig` — factory methods for OpenAI standard and extended 24h
- `BatchConfig` — batch/flex/priority ratios
- Error hierarchy: `ProviderError` → Auth, ModelNotFound, RateLimited, Quota, ContentFiltered, Connection, Timeout

### Integration Points

- **`api_client.py`** — resolves `self._provider` from ProviderRegistry; delegates `requires_api_key`, `get_response_format()`, `get_temperature_config()`, `classify_error()` to provider
- **`options.py`** — `_build_api_providers()` and `get_provider_display_name()` check ProviderRegistry first, then fall back to legacy dict
- **Global Options UI** — provider constraints applied dynamically:
  - Temperature slider hidden when `get_temperature_config().supported` is False (e.g. GPT-5 family)
  - Thinking frame hidden when `get_thinking_config().available` is False
  - Warning for models without structured output support
  - Per-model settings (temperature, thinking) saved/loaded from INI
  - Model selection combo in Request Settings section

### Adding a New Provider

See `providers/provider_template.py` (documented skeleton) and `doc/adding_a_provider.md` (step-by-step guide).

=============================================================================

END OF USER GUIDE

For technical details about the tool, see technical.md
For developer information, see technical.md  
For test documentation, see tests.md
For features being worked on, see todo.md
