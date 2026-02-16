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
- functions/: 36 modules (+ glossaries/ subfolder with 5 files)
- modi/: 12 processing modes
- formats/: 5 format handlers
- gui/steps/: 10 workflow tabs
- gui/helpers/: 6 adapter modules
- gui/dialogs/: 3 dialog modules

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
   - Step 7: Quality Assurance
   - Step 8: Postprocessing
   - Step 9: Wordwrap & Overwrite
   - Step 10: Output & Injection
   - Global Options Dialog
   - Theme & Icons System

4. ADVANCED FEATURES
   - Request Caching System
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
   - Click "Select File(s) ▾" dropdown for unified file/folder selection
   - Select one or more files: .txt, .csv, .tsv, .json, .xlsx, .rpgmaker, or image files
   - Folder loading shows collapsible folder hierarchy in a Treeview
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
   The tool replaces these with __PROT__ during translation
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
  - Separate handling for related patterns (e.g., <br> vs \n)
- Built-in conditions (15 total):
  - **__PROT__/__COLOR__/__FONT__**: Protected placeholders with indexed variants
  - **__DEDUP__**: AI instructed to output unchanged
  - **__TEMPREPL_X_Y__**: AI instructed to preserve format
  - **Brackets**: Preserves [name], {variable}, <tag> structures (shows only used types)
  - **Japanese brackets**: Converts 「」『』【】《》 appropriately
  - **<br> Tags**: Protects HTML line break tags in game text
  - **\n Newlines**: Preserves escaped newline sequences
  - **Color codes**: Preserves \\c[N] formatting
  - **Variables**: Preserves \\v[N], \\n[N] references
  - **Media commands**: Preserves \\se[], \\pic[], \\wait[]
  - **Text formatting**: Preserves \\fb, \\fr, \\i[], etc.
  - **Ruby text**: Preserves \\rb[text,reading] furigana
  - **Ellipsis**: Maintains ... dramatic pauses
  - **Speaker tags**: Handles Name: format structure
  - **Speaker dialogue format**: Preserves Speaker: "Dialogue" format
- Custom patterns: Define your own via config/conditional_prompts.json
- Priority-based ordering (higher priority = earlier in prompt)
- Instructions only injected when relevant patterns detected in batch
- **Pattern-Specific Examples**:
  - Each pattern has its own human-readable example
  - Examples only shown when that specific pattern matches
  - e.g., "[name]" shown only when square brackets detected
  - e.g., "__PROT_1__" shown only when indexed PROT detected
- Reduces placeholder corruption from ~5% to <0.1%

API RESPONSE VALIDATION ✓ (Enhanced - Session 14+)
- Multi-layer validation of AI translation responses
- **Pre-Translation Validation**:
  - Skip empty lines, comments (#), section markers (=)
  - Skip __DEDUP__ and __PROT__ only lines
  - Skip lines without Japanese characters
  - Skip already translated lines
  - Auto-translate symbol-only lines (…→..., 。→., etc.)
- **Post-Translation Validation**:
  - Japanese character count check (max 4 allowed in output)
  - Anchor character preservation verification
  - Uses ANCHOR_EQUIVS for fullwidth/halfwidth equivalence
- **Placeholder Preservation** ✓ (NEW - TASK 4):
  - Validates __PROT__, __PROT_1__, custom placeholders preserved
  - Detects missing, mangled, and extra placeholders
  - Per-line validation with targeted retry recommendations
  - Supports indexed placeholders: __PROT_1__, __NAME_2__, etc.
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

GAME SUMMARY & PROJECT CONTEXT (NEW)
- Provide story context to help the AI understand your game/story
- Edit `config/game_summary.txt` with:
  - Title and setting information
  - Main character descriptions and relationships
  - Plot summary (avoid spoilers for later sections)
  - Tone and style notes (comedic, dramatic, formal, etc.)
- Summary is automatically injected into the system prompt
- Helps AI maintain consistent characterization and tone
- Project configuration stored per-project in manifest:
  - Project name, genre, tone
  - Custom style instructions
  - API profile selection (different models for different purposes)
- Multiple API profiles supported:
  - Use fast/cheap models for glossary enrichment
  - Use powerful models for actual translation
  - Keep API keys secure (never stored in manifest)

TRANSLATION STYLE GUIDE (NEW - TASK 6)
- Customize translation style preferences via `config/translation_style.txt`
- Style sections include:
  - **Formality Level**: formal, casual, or mixed (match source)
  - **Honorifics Handling**: keep (-san, -chan), remove, or localize (Mr., Ms.)
  - **Cultural References**: preserve, localize, or explain inline
  - **Dialogue Style**: maintain distinct speech patterns, preserve verbal tics
  - **Specific Rules**: project-specific terminology choices
  - **Things to Avoid**: what the translator should NOT do
- Comment lines (starting with #) are ignored
- Automatically injected into system prompt after game summary
- Truncated at 2000 characters with warning if too long
- Helps maintain consistent translation style across the project

ROLLING CONTEXT (NEW - TASK 7)
- Provides previous lines as context for each translation batch
- Helps AI maintain continuity and context awareness
- Configuration in `CherryAI.ini` under `[rolling_context]`:
  - `enabled`: true/false to enable/disable
  - `lines_before`: number of lines to include (default: 3)
  - `scene_markers`: comma-separated patterns that indicate scene breaks (e.g., "=====,-----,***")
  - `use_translated`: true to use translated text, false for source text
- Scene markers reset context (new scene = fresh start)
- Context is prefixed to user message with clear "do not re-translate" warning
- Dynamic updates: context can be replaced with actual translated lines after each batch

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
  - CLI usage: `python CherryAI.py translate --preset local input.txt`
  - No API key required for local endpoints
- **Compatible Software:**
  - **LM Studio**: OpenAI-compatible server, easy model management
  - **Ollama**: Fast local inference, many model options
  - **text-generation-webui**: Advanced interface with extensions
  - **LocalAI**: Drop-in OpenAI replacement
  - **llama.cpp server**: Lightweight, direct GGUF support
- **Quick Start:**
  1. Start your local LLM server (e.g., LM Studio → Start Server)
  2. Run: `python CherryAI.py translate --preset local myfile.txt`
  3. No API key needed - uses localhost:1234 by default
- **Planned Enhancements** (see todo.md):
  - Auto-detection of running local servers
  - Model discovery from /v1/models endpoint
  - Health check before translation
  - Better error messages for connection issues

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
  7. **QA** - Quality checks, auto-tagging ✅ Implemented
  8. **Postprocessing** - Restore placeholders, apply fixes
  9. **Wordwrap** - Line breaking, width limits
  10. **Output** - Export formats, save results
- **Input and Extraction Tab (Phase 1, updated Phase 39, 58):**
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
  - Unified "Select File(s) ▾" dropdown button for file and folder selection
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
  - Code/pattern detection (HTML/XML, line breaks)
  - Speaker detection with frequency counts
  - **Findings Table Context Menu (Phase 59.3-59.5):**
    - Category-aware right-click menu
    - **Speaker actions:** Add to Glossary, Set Role (Protagonist/Love Interest/Major/Minor), Set Gender (Male/Female), Set Translation, Add to Code Glossary, Copy Name
    - **Code Pattern actions:** Preserve/Remove/Translate toggles, Replace options, Type classification (Name/Text/Number/Invisible), Copy Pattern, Show Lines
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
  - Keyboard shortcuts: Ctrl+Z (undo), Ctrl+Y (redo)
  - get_undo_description() / get_redo_description() for UI hints
- **Project Persistence (Phase 4, Enhanced with Manifest v3.0):**
  - **Manifest-first architecture**: All state saved to manifest file
  - **File menu**: New Project, Open Project, Open Files, Exit
  - **Manual save**: Ctrl+S saves current manifest state
  - **Auto-save on step change**: Manifest saved when navigating between steps
  - **Manifest v3.0 format** stores all project data:
    - step_state: Completion status, skipped flags, metadata per step
    - project_info: Name, source/target language, genre, tone
    - glossary: Project-specific glossary entries (optional, can use global)
    - characters: Speaker database with gender and context
    - code_patterns: Protected code and custom placeholders
    - lines: Source and translated line content
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
    - Character Notes: `save_character_notes()` / `load_character_notes()`
      - Fields: name, original_name, gender, role, notes, speaking_style
      - Supports CharacterInfo dataclass or plain dicts
    - Code Glossary: `save_code_glossary()` / `load_code_glossary()`
      - Fields: pattern, category, action (preserve/translate/remove), example, notes
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
      - **Style and Tone (Task 23.2):** StylePreset, CustomStyle, TonePreset, CustomTone
      - **Character Notes (Task 23.3):** Save/load via special format helpers
      - **Code Glossary (Task 23.3):** Save/load via special format helpers
      - **Prompt (Task 23.4):** Renamed from "Additional Notes", moved to left column
    - Changes auto-save to manifest on widget interaction
    - Values auto-load on step entry via `_load_from_manifest_bindings()`
  - **Application Startup (Task 21.4):**
    - On launch, reads last manifest path from INI [recent] section
    - Auto-loads last project if restore_on_launch enabled (default)
    - Shows WelcomeDialog if no last manifest or file missing:
      - Resume: Load last project
      - New Project: Start fresh with file loading
      - Load Existing: Open project browser
      - Start Fresh: Begin without loading project
    - Saves last manifest path on app close for next launch
    - Recent manifests list maintained (up to 10)
  - **Global vs Project Glossary**: Toggle in Information step to use global glossary.json or project-specific glossary stored in manifest
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
  - Phase 1: Input and Extraction ✅ Complete (with session serialization fix)
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
  - Standard rules with toggles: Deduplication, Ellipsis, Symbol Conversion, PROT Compression
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
- **Costs Tab (Phase 6, updated Phase 40):**
  - **Renamed from Estimation to Costs** (class CostsStep, step_name "Costs")
  - Token counting with tiktoken (cl100k_base) or heuristic fallback
  - Model selection dropdown with 11 supported models:
    - GPT-4.1, GPT-4o, GPT-4o Mini, GPT-4 Turbo
    - Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku
    - Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini 2.0 Flash, Gemini 2.0 Flash Lite
  - **Tokens/Request spinbox** (500-32000): alternative maximum alongside Lines/Request
    - Hybrid chunking mode: whichever limit is reached first triggers chunk boundary
  - **Prompt overhead calculation**: includes system prompt, summary, glossary, style tokens per request
  - Token counts panel: original vs preprocessed with savings
  - Cost estimate panel with input/output/total breakdown
  - **Model comparison table** with Price Original, Price Preprocessed, Savings columns
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
  - **Manifest Integration (Phase 25):**
    - Analysis results saved: InputLines, InputTokens, OutputTokens
    - Results loaded on step enter for session restoration
  - **Backward compatibility**: EstimationStep alias, estimate.py re-exports
- **Translation Tab (Phase 7):**
  - TranslationStep class (step_id=5) with ~900 lines
  - Lines table with per-line status tracking:
    - PENDING, TRANSLATING, COMPLETED, FAILED, SKIPPED states
    - Status icons: ○ Pending, ◐ Translating, ✓ Done, ✗ Failed, ⊘ Skipped
  - **Prompt Editor Panel:**
    - Style preset entry for translation style configuration
    - Game summary scrollable text area (loads from config/game_summary.txt)
    - Glossary entries scrollable text area
    - Conditional prompts scrollable text area
    - Ban tokens entry (comma-separated: em_dash, smart_quotes, etc.)
  - **Request Options Panel:**
    - Model selection with 9 models (GPT, Claude, Gemini families)
    - Temperature control (0.0-2.0, default 0.3)
    - Chunk size (5-100 lines per request, default 30)
    - Retry strategy: batch, contextual, isolated, skip
    - Max retries (1-10, default 3)
    - Request caching toggle
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
    - Stored in [prompts] section of config/defaults.ini (user preference)
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
      - Model, Temperature, LinesPerChunk, RetryStrategy
      - MaxRetries, EnableRequestCaching, LineByLineMode
      - ContextLines, Thinking, ThinkingBudget
    - All options persist to manifest and load on step enter
- **Quality Assurance Tab (Phase 8):**
  - QAStep class (step_id=6) with ~1100 lines
  - Lines table with QA status tracking:
    - Filter modes: All, Errors Only, Warnings Only, Unfixed, Accepted, Rejected
    - Status icons: ✓ Accepted, ✗ Rejected, ⚠ Error, ○ Warning, ✓ OK
    - Issue count display per line
  - **Validation Rules Panel:**
    - 6 default rules with enable/disable toggles:
      1. Placeholder Preservation (ERROR) - Check __PROT__ preserved
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
  - PostprocessingStep class (step_id=7) with ~1100 lines
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
    - PLACEHOLDER_CASE - Fix __prot__ → __PROT__
    - PLACEHOLDER_MANGLED - Fix __PR OT__ → __PROT__
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
    - All options persist to manifest and load on step enter
    - 35 tests in dev/test_postprocess_manifest.py
- **Wordwrap & Overwrite Tab (Phase 10):**
  - WordwrapOverwriteStep class (step_id=8, ~950 lines)
  - Preview table with line length indicators:
    - Columns: #, Status, Chars, Lines, Original, Wrapped Preview
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
    - `autosave_enabled` - Enable/disable via property
    - `autosave_interval` - Interval in seconds
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
    - Initial defaults: `config/defaults.ini` (factory, read-only reference)
    - User defaults: `[user_defaults]` section in CherryAI.ini
  - **ini_manager.py Functions:**
    - `get_initial_default()` - Load from config/defaults.ini
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
    - StylePreset: NATURAL, LITERAL, LOCALIZING, FORMAL, CASUAL, TECHNICAL, POETIC, CUSTOM
    - TonePreset: NEUTRAL, CASUAL, FORMAL, DRAMATIC, COMEDIC, SERIOUS, WHIMSICAL, DARK, CUSTOM
  - **Data Classes:**
    - CharacterInfo: name, gender, role, notes (with to_dict/from_dict)
    - ProjectMetadata: project_name, summary, genre, style, tone, notes, source_lang, target_lang, characters list
    - InferenceOptions: infer_summary, infer_characters, infer_style, sample_size, api_profile
    - InferenceResult: success, metadata, error, duration
  - **Helper Constants:**
    - STYLE_DESCRIPTIONS: Detailed descriptions for each StylePreset
    - TONE_DESCRIPTIONS: Detailed descriptions for each TonePreset
    - COMMON_GENRES: List of common translation project genres
    - SOURCE_LANGUAGES: Japanese, Chinese, Korean, etc.
    - TARGET_LANGUAGES: English, Spanish, German, French, etc.
  - **Metadata Panel:**
    - Project name entry field
    - Summary multi-line text area
    - Genre dropdown with common options
    - Custom notes field
    - Source/target language dropdowns
  - **Character Notes Panel:**
    - Table with columns: Name, Gender, Role, Notes
    - Add/Edit/Remove character buttons
    - Import from glossary functionality
    - Export character list support
  - **Style & Tone Panel:**
    - Style preset dropdown with descriptions
    - Tone preset dropdown with descriptions
    - Custom style/tone text areas when "Custom" selected
    - Live preview of combined style prompt
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
    - Style/Tone dropdown graying: preset dropdown disabled when custom field has content
    - Glossary table inline editing: 4-column Treeview (Active, Original, Translation, Notes) with double-click editing
    - Import from Analysis: code patterns import as "Detected" category; speakers import as glossary entries
    - Code Database actions: Preserve ("Do not translate"), Translate ("Translate as"), Remove (filtered from prompt)
    - Global Glossary and Database widget: mode switch, search/filter, import/export JSON/CSV, stored in user/ directory
    - Selective glossary: Active column with ✓/✗ toggle, only active entries included in prompt
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
    - API Provider Management: `APIProviderEntry` dataclass, `PROVIDER_PRESETS` (5 presets: OpenAI GPT-4o-mini, GPT-4o, Gemini Flash, Claude Sonnet, Local LLM), providers Treeview in Global Options, `_ProviderEditDialog` and `_PresetPickerDialog` helper dialogs
    - Settings Migration: cache_mode in CachingSettings, thinking_enabled/thinking_budget in RequestSettings, rolling_context_lines in RequestSettings; `_sync_from_global_options()` applies overrides on tab enter
    - Retry Refinement: UI shows only Batch + Contextual (`RETRY_STRATEGIES`); `ALL_RETRY_STRATEGIES` kept for CLI with all 4; max retries minimum changed from 1 to 0
    - Prompt Editor Redesign: removed Style Preset and Game Summary textarea; "Preview Prompt" read-only button; Ban Tokens LabelFrame with preset dropdown (None/Clean English/Strict)
    - Chunk Sync: LinesPerChunk synced between Costs step and manifest; `_on_chunk_changed()` write-back
    - Language Skip: `detect_line_script()` in `functions/analysis.py` (CJK/kana/hangul/latin detection); `_LANG_SCRIPT_MAP` and `_apply_language_skip()` filter non-source lines
    - Tab Caching: `BaseStep` infrastructure (`_compute_cache_hash`, `_is_cache_valid`, `_update_cache`, `_invalidate_cache`, `_force_refresh`); TranslationStep early-returns on cache hit
    - Performance: SharedTable batch insertion (500-row batches via `after(1, ...)`); `_refresh_lines()` optimized with batch manifest dict read
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
    - get_context_prompt() returns type-specific instruction snippet for system prompt injection
    - _construct_system_prompt() accepts optional context_type parameter (Phase 50 slot 2 of 9)
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
    - OptionSection: API, REQUEST, CACHING, LOGGING, SESSION, SAFETY, FILE_IO, PROMPTS (8 sections)
    - OptionCategory: CONNECTION, PROCESSING, APPLICATION (3 categories)
    - LogLevel: DEBUG, INFO, WARNING, ERROR, CRITICAL
    - ThemeMode: LIGHT, DARK, SYSTEM
    - LineEnding: LF, CRLF, CR, AUTO
    - EncodingOption: UTF8, UTF8_BOM, UTF16, SHIFT_JIS, EUC_JP, AUTO
  - **Settings Dataclasses (with to_dict/from_dict):**
    - APISettings: provider, api_key, base_url, model, temperature
    - RequestSettings: timeout, retries, rate_limit, chunk_size, thinking_enabled, thinking_budget, rolling_context_lines
    - CachingSettings: enabled, cache_dir, max_age_hours, max_size_mb, cache_mode
    - LoggingSettings: level, log_file, debug_mode, log_api_calls
    - SessionSettings: autosave_enabled, autosave_interval, theme, restore_on_launch, confirm_on_exit
    - SafetySettings: ban_tokens, content_warning_enabled, max_output_tokens
    - FileIOSettings: default_encoding, line_ending, preserve_bom, backup_originals
    - PromptsSettings: edit_prompt, tlc_prompt (Task 33.2)
    - GlobalOptions: Container for all settings sections, providers list, get_model_list(), get_provider_for_model()
    - APIProviderEntry: name, provider_type, url, api_key, model (to_dict/from_dict) — Task 43.6
    - PROVIDER_PRESETS: 5 presets (OpenAI GPT-4o-mini, GPT-4o, Gemini Flash, Claude Sonnet, Local LLM) — Task 43.6
  - **Helper Constants:**
    - SECTION_DESCRIPTIONS: User-friendly descriptions for each section
    - CATEGORY_ORDER: Category → sections mapping for navigation
    - CATEGORY_NAMES: Display names for categories
    - SECTION_NAMES: Display names for sections
    - API_PROVIDERS: Imported from options.py (6 providers: openai, gemini, anthropic, local, ollama, lmstudio)
    - COMMON_BAN_TOKENS: em_dash, smart_quotes, ellipsis, etc.
  - **API Section:**
    - Provider dropdown (OpenAI, Gemini, Anthropic, Local, Ollama, LM Studio)
    - API key entry with show/hide toggle
    - Base URL entry (auto-filled from provider)
    - Model dropdown (updates based on provider)
    - Temperature slider (0.0-2.0)
    - Test API Connection button
  - **Request Section:**
    - Lines per request (chunk size)
    - Timeout in seconds
    - Max retries
    - Rate limit (requests per minute)
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
  - **Prompts Section (Task 33.2):**
    - OptionSection.PROMPTS in Processing category
    - PromptsSettings dataclass with edit_prompt and tlc_prompt
    - Edit Step Prompt: Multi-line text area for Edit pass instructions
    - TLC Step Prompt: Multi-line text area for TLC pass instructions
    - Placeholder support: {source_lang}, {target_lang} for language substitution
    - Reset to Default button for each prompt
    - Prompts stored in [prompts] section of config/defaults.ini
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
  - Input step data sharing: Stores all_lines for cross-step access
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
  - gui/steps/input_extract.py - Input and Extraction tab
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
  - gui/components/table.py - Shared table component (708 lines)
  - gui/components/ - Reusable UI components
- Legacy GUI preserved at functions/gui_legacy.py

GUI TABLE VIEW & EDITOR (Implemented)
- Professional spreadsheet-like interface for manifest editing (gui/components/table.py)
- **Standard Table Features (Implemented):**
  - Sortable columns (click header to sort)
  - Column visibility toggle (Columns menu)
  - Filter by any field (search bar)
  - Search within table
  - Virtualized scrolling for large files (10k+ lines)
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
  - **Placeholder Case Fix**: `__prot__` → `__PROT__`
  - **Placeholder Whitespace Fix**: `__ PROT __` → `__PROT__`
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

TRANSLATION STYLE PRESETS (Implemented)
- Pre-built style guides for common translation scenarios
- Load by name: `--style-preset fantasy_medieval`
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

POINT OF VIEW INFERENCE (Implemented)
- Infers narrative perspective (1st/2nd/3rd person) from non-dialogue text
- **Pronoun Pattern Database** (`functions/analysis.py`): `_RAW_POV_PATTERNS` for Japanese, English, Chinese, Korean with compiled caching via `_get_pov_patterns()`
- **Detection Algorithm** (`detect_pov()`): Filters out dialogue (speaker prefix) and menu/choice lines, counts pronoun occurrences, infers 3rd person via protagonist name frequency
- **Confidence Scoring:** High when dominant POV >60%, low otherwise; mixed when secondary ≥20%
- **POVResult Dataclass:** `pov`, `confidence`, `counts`, `total_narrative_lines` with `to_dict`/`from_dict`
- **Prompt Integration** (`functions/prompt_builder.py`): `pov_result` attribute; "Narrative Perspective" section added to system prompt when confidence is "high"
- English patterns compiled with `re.IGNORECASE` for proper case handling

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
  - Malformed placeholders (missing/added characters in `__PROT__` tokens)
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
   - Code replaced with placeholders like __PROT_0__
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
- `step_state`: Completion status, skipped flags, metadata per GUI step
- `project_info`: Project name, source/target language, genre, tone, style notes
- `glossary`: Project-specific glossary entries (alternative to global glossary.json)
- `characters`: Speaker database with gender, context, and aliases
- `code_patterns`: Protected regex patterns and custom placeholders

**File Menu Operations:**
- **New Project**: Creates fresh manifest, clears all state
- **Open Project**: Loads existing manifest.json, restores all step states
- **Open Files**: Load source files into current project
- **Save (Ctrl+S)**: Manually save current manifest state

**Automatic State Persistence:**
- Manifest auto-saves when navigating between steps
- Manifest auto-saves when closing the application
- No background autosave thread (reduces complexity)

**Glossary Options (Information Step):**
- **Use Global Glossary**: Toggle between global `glossary.json` and project manifest
- **Copy from Global**: Import entries from global glossary into project
- **Project-specific glossary**: Stored in manifest, travels with project
- **Selective Glossary (Phase 41)**: Active/inactive toggle per entry; only active entries sent to prompt
- **Global Glossary and Database Widget (Phase 41)**: Manage cross-project glossary (`user/global_glossary.json`) and code patterns (`user/global_codes.json`) with search, import/export (JSON/CSV)
- **Glossary Entries include `active` field** (Phase 41): Persisted in manifest, defaults to True for backward compatibility

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
- Code segment count and classification
- Detected speaker names (if dialogue file)
- How many times each speaker appears

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

Edge Case Example (リリィ / Lily):
- Uses 俺様 (arrogant male pronoun) → would suggest Male
- But status card shows 性別：女性 → explicit Female
- Others call her リリィちゃん → confirms Female
- **Result**: Correctly identified as Female despite male pronouns

Workflow Integration:
- `update_glossaries_from_analysis()` passes full file content for comprehensive inference
- Speakers are analyzed with all three detection methods before glossary update
- API-based gender enrichment (Gemini/OpenAI) remains as optional fallback
- No translation should proceed without assured gender for all speakers

Optional LLM Enhancement:

For speaker names specifically, CherryAI can use an AI model to suggest:

- **Name romanization**: Convert Japanese name to romaji (e.g., イオリ → Iori)
- **Gender inference**: Determine likely gender from speech patterns (Male/Female/Neutral/Unknown)
- **Context notes**: Infer role or relationship from dialogue context

How it works:

1. Enable in options: "Use AI to enhance glossary" (optional, off by default)
2. Provide API key: OpenAI, Gemini, or compatible endpoint
3. During analysis: AI examines dialogue to suggest translations and gender
4. You review suggestions: Accept, edit, or reject
5. Glossary entries are updated with AI-suggested values

Example:

File has a character "イオリ" who uses feminine pronouns (私). Analysis with AI:
- Suggests romanization: "Iori"
- Infers gender: "Female" (based on pronouns and speech patterns)
- Glossary automatically updated
- Next file: Tool knows this character is female and uses correct pronouns

Benefits:

- **Speed**: No manual research needed for name romanization
- **Consistency**: AI suggestions help maintain character consistency
- **Learning**: Each file teaches the glossary more about your characters
- **Flexibility**: You can always edit suggestions or turn off AI enhancement

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
   - Protected code uses short `__PROT__` placeholder
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

END OF USER GUIDE

For technical details about the tool, see technical.md
For developer information, see technical.md  
For test documentation, see tests.md
For features being worked on, see todo.md
