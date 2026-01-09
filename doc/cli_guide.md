# CherryAI Command Line Guide

Quick reference for CLI commands with copy-paste examples.

---

## Quick Start

```bash
# Navigate to CherryAI directory
cd CherryAI

# 1. Configure API (first time only)
python CherryAI.py config api_key YOUR_API_KEY
python CherryAI.py config api_url 2    # Select Gemini

# 2. Translate a file (Japanese → English)
python CherryAI.py translate config/sample.txt -s ja -t en -n 50
```

---

## Available Commands

| Command | Description |
|---------|-------------|
| `translate` | Translate files (1-Click pipeline) |
| `sample` | Quick sample translation (default 50 lines) |
| `estimate` | Estimate translation cost without translating |
| `test` | Run diagnostic tests |
| `config` | View/set API configuration (URL, key, model) |
| `io` | Configure input/output file formats |
| `glossary` | Manage translation glossary |
| `local` | Detect and check local LLM servers |
| `languages` | List supported languages |
| `help` | Show help and usage information |

---

## 1. Config Command

View and modify CherryAI configuration settings including API URL, key, and model.

### Usage Patterns

```bash
# Show all configurable options
python CherryAI.py config

# Show details for a specific option
python CherryAI.py config <option>

# Set option by selecting from numbered list
python CherryAI.py config <option> <number>

# Set option with custom value
python CherryAI.py config <option> <value>
```

### Configuration Options

| Option | Description |
|--------|-------------|
| `api_url` | API endpoint URL (OpenAI, Gemini, local, etc.) |
| `api_key` | API authentication key |
| `model` | LLM model name |
| `temperature` | Generation temperature (0.0-2.0) |
| `chunk_size` | Lines per translation chunk (10-200) |
| `timeout` | API timeout in seconds (10-600) |
| `source_lang` | Default source language |
| `target_lang` | Default target language |
| `preset` | Apply a saved configuration preset |

### Examples

```bash
# Show all options with current values
python CherryAI.py config

# Show known API URLs with selection numbers
python CherryAI.py config api_url

# Select OpenAI (option 1)
python CherryAI.py config api_url 1

# Select Gemini (option 2)
python CherryAI.py config api_url 2

# Set custom API URL
python CherryAI.py config api_url https://my.api.com/v1

# Set API key
python CherryAI.py config api_key sk-abc123...
python CherryAI.py config api_key AIzaSyB...

# Show available models for current provider
python CherryAI.py config model

# Select model by number
python CherryAI.py config model 1

# Set model directly
python CherryAI.py config model gpt-4o
python CherryAI.py config model gemini-2.0-flash

# Apply a preset (combines URL + model + settings)
python CherryAI.py config preset gemini_free
python CherryAI.py config preset gpt4

# Set other options
python CherryAI.py config temperature 0.5
python CherryAI.py config chunk_size 100
python CherryAI.py config source_lang ja
python CherryAI.py config target_lang en
```

### Known API Providers

| # | Provider | URL |
|---|----------|-----|
| 1 | OpenAI | https://api.openai.com/v1 |
| 2 | Gemini | https://generativelanguage.googleapis.com/v1beta/openai/ |
| 3 | Anthropic | https://api.anthropic.com/v1 |
| 4 | Local | http://localhost:1234/v1 |
| 5 | Ollama | http://localhost:11434/v1 |
| 6 | LM Studio | http://localhost:1234/v1 |

### Available Presets

| Preset | Model | Rate Limit |
|--------|-------|------------|
| `gemini_free` | gemini-2.0-flash-lite | 15 req/min |
| `gemini_pro` | gemini-2.0-flash | 60 req/min |
| `gpt4` | gpt-4o-mini | 60 req/min |
| `gpt4_turbo` | gpt-4-turbo-preview | 60 req/min |
| `local` | local-model | 999 req/min |

---

## 2. Translate Command

Runs the full pipeline: Pre-process → Translate → Post-process

### Basic Usage

```bash
python CherryAI.py translate <path> [options]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--source` | `-s` | Source language | From config |
| `--target` | `-t` | Target language | From config |
| `--lines` | `-n` | Translate only first N lines | All |
| `--yes` | `-y` | Skip confirmation prompt | False |
| `--interactive` | `-i` | Step-by-step wizard | False |
| `--partial` | | Enable partial mode (default 100 lines) | False |
| `--model` | | Override model (e.g., gpt-4o, gemini-2.0-flash) | From config |
| `--temperature` | | Override temperature (0.0-2.0) | From config |
| `--timeout` | | Override API timeout in seconds (10-600) | From config |
| `--chunk-size` | | Override lines per API request (10-200) | From config |
| `--preset` | | Apply an API preset before translation | None |
| `--ban-tokens` | | Comma-separated tokens to ban (e.g., `em_dash`) | None |
| `--logit-bias-preset` | | Token banning preset (see Token Banning section) | None |
| `--retry-strategy` | | Retry strategy: `batch`, `contextual`, `isolated`, `skip` | batch |
| `--use-cache` | | Enable request caching to avoid duplicate API calls | False |
| `--cache-mode` | | Cache matching: `strict`, `model_only`, `any` | model_only |
| `--clear-cache` | | Clear cache before starting | False |
| `--style-preset` | | Style preset(s) to apply (comma-separated) | None |
| `--rate-limit` | | Enable advanced rate limiting (see Rate Limiting section) | False |
| `--max-concurrent` | | Maximum concurrent API requests (1-10) | 1 |
| `--daily-limit-check` | | Check and warn before exceeding daily API limits | False |

### Planned Options (Coming Soon)

| Option | Description |
|--------|-------------|
| `--progress` | Show detailed progress bar (default: true) |
| `--line-by-line` | Translate one line at a time with minimal prompt |
| `--line-context` | Lines of context for line-by-line mode (0-3) |
| `--auto-recover` | Enable automatic line recovery without retries (default: true) |
| `--strip-quotes` | Strip speaker quotes to save tokens (default: true) |
| `--no-strip-quotes` | Disable speaker quote stripping |
| `--chunk-mode` | Chunking mode: `lines`, `tokens`, or `hybrid` |
| `--chunk-tokens` | Max tokens per chunk in tokens/hybrid mode (100-8000) |

### Examples

```bash
# Translate sample.txt (first 50 lines, Japanese → English)
python CherryAI.py translate config/sample.txt -s ja -t en -n 50

# Translate all supported files in a folder
python CherryAI.py translate temp/ -s japanese -t english

# Translate entire file (no line limit)
python CherryAI.py translate config/sample.txt -s ja -t en -n 5000

# Skip confirmation prompt
python CherryAI.py translate config/sample.txt -s ja -t en -n 100 -y

# Translate to German
python CherryAI.py translate config/sample.txt -s ja -t de -n 50

# Translate to French
python CherryAI.py translate config/sample.txt -s jp -t french -n 50

# Interactive mode (step-by-step wizard)
python CherryAI.py translate --interactive

# Override model for this translation only
python CherryAI.py translate file.txt -s ja -t en --model gpt-4o

# Use lower temperature for more consistent output
python CherryAI.py translate file.txt -s ja -t en --temperature 0.2

# Apply a preset and override specific settings
python CherryAI.py translate file.txt -s ja -t en --preset gemini_pro --timeout 120

# Use larger chunks for faster processing
python CherryAI.py translate file.txt -s ja -t en --chunk-size 100

# Ban em-dashes and smart quotes from output
python CherryAI.py translate file.txt -s ja -t en --ban-tokens em_dash,smart_quotes

# Use a preset for common punctuation banning
python CherryAI.py translate file.txt -s ja -t en --logit-bias-preset no_fancy_punctuation
```

### Token Banning (Logit Bias)

Control which characters appear in the translation output by banning or discouraging specific tokens.

**Available Presets:**

| Preset | Description | Banned Characters |
|--------|-------------|-------------------|
| `no_fancy_punctuation` | Bans em-dash, en-dash, smart quotes, ellipsis | —, –, ", ", ', ', … |
| `no_em_dash` | Bans only em-dash | — |
| `no_smart_quotes` | Bans smart/curly quotes | ", ", ', ' |
| `ascii_only_punctuation` | Bans non-ASCII punctuation | —, –, ", ", ', ', …, · |
| `japanese_ellipsis_safe` | Bans standard ellipsis (preserves Japanese) | … |

**Token Aliases (for `--ban-tokens`):**

| Alias | Character | Unicode |
|-------|-----------|---------|
| `em_dash` | — | U+2014 |
| `en_dash` | – | U+2013 |
| `smart_quote_open` | " | U+201C |
| `smart_quote_close` | " | U+201D |
| `smart_quotes` | " and " | Both |
| `smart_single_open` | ' | U+2018 |
| `smart_single_close` | ' | U+2019 |
| `ellipsis` | … | U+2026 |
| `middot` | · | U+00B7 |

**Examples:**

```bash
# Ban specific characters by alias
python CherryAI.py translate file.txt --ban-tokens em_dash,ellipsis

# Mix aliases and literal characters
python CherryAI.py translate file.txt --ban-tokens "em_dash,×,÷"

# Use a preset
python CherryAI.py translate file.txt --logit-bias-preset no_fancy_punctuation
```

### Retry Strategies

Control how failed translations are retried with `--retry-strategy`:

| Strategy | Description | Best For |
|----------|-------------|----------|
| `batch` | Retry in smaller batches with emphasis prompt (default) | General use, balanced quality/cost |
| `contextual` | Include surrounding translated lines as context | Context-dependent text, dialogue |
| `isolated` | Single line with minimal prompt | Fast retries, simple content |
| `skip` | Skip failed lines, preserve original | Non-critical translations |

**Examples:**

```bash
# Use contextual retry (includes surrounding translations as context)
python CherryAI.py translate file.txt --retry-strategy contextual

# Skip failed lines instead of retrying (fastest)
python CherryAI.py translate file.txt --retry-strategy skip

# Isolated retry for simple content
python CherryAI.py translate file.txt --retry-strategy isolated
```

### Request Caching

Enable caching to avoid resending identical API requests, saving costs and reducing latency:

| Option | Description | Default |
|--------|-------------|---------|
| `--use-cache` | Enable request caching | Disabled |
| `--cache-mode` | Cache matching mode (strict, model_only, any) | model_only |
| `--clear-cache` | Clear cache before starting | Don't clear |

**Cache Modes:**

| Mode | Description | Best For |
|------|-------------|----------|
| `strict` | All settings must match (model, temp, prompt) | Exact reproducibility |
| `model_only` | Only model name must match | General use (default) |
| `any` | Use any cached response for same source | Maximum cache hits |

**Examples:**

```bash
# Enable caching (default model_only mode)
python CherryAI.py translate file.txt --use-cache

# Strict mode - only use cache when all settings match
python CherryAI.py translate file.txt --use-cache --cache-mode strict

# Clear cache before starting
python CherryAI.py translate file.txt --use-cache --clear-cache

# Any mode - maximize cache hits regardless of settings
python CherryAI.py translate file.txt --use-cache --cache-mode any
```

### Output

- Translated files saved with `_translated` suffix
- API log created at `logs/api_log.txt`
- Shows progress and cost estimation

---

### Style Presets

Apply pre-built or custom translation style presets with `--style-preset`.

| Usage | Description |
|-------|-------------|
| `--style-preset fantasy_medieval` | Apply a single built-in preset |
| `--style-preset fantasy_medieval,archaic_english` | Combine multiple presets (later presets override earlier ones) |

Notes:
- Presets control tone, formality, vocabulary, and honorific handling.
- Built-in presets include `fantasy_medieval`, `archaic_english`, `victorian`, `modern_casual`, `british_english`, `american_english`, `formal_japanese`, `casual_japanese`, `noir_detective`, `romance_flowery`, and more.
- Custom presets can be created in `config/style_presets/` as `.txt` files.

Examples:

```bash
# Apply a single preset
python CherryAI.py translate file.txt --style-preset fantasy_medieval

# Combine two presets (archaic guidance applied after fantasy)
python CherryAI.py translate file.txt --style-preset fantasy_medieval,archaic_english

# Use a custom preset placed in config/style_presets/custom_casual.txt
python CherryAI.py translate file.txt --style-preset custom_casual
```


## 3. Sample Command

Quick sample translation for testing quality before full translation.

### Basic Usage

```bash
python CherryAI.py sample <path> [options]
```

### Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--lines` | `-n` | Number of lines to translate | 50 |
| `--source` | `-s` | Source language | From config |
| `--target` | `-t` | Target language | From config |
| `--model` | | Override model | From config |
| `--temperature` | | Override temperature (0.0-2.0) | From config |
| `--preset` | | Apply an API preset | None |

### Examples

```bash
# Translate first 50 lines (default)
python CherryAI.py sample config/sample.txt

# Translate first 100 lines
python CherryAI.py sample config/sample.txt -n 100

# Specify languages
python CherryAI.py sample config/sample.txt -s ja -t en -n 100

# Test with a specific model
python CherryAI.py sample config/sample.txt --model gpt-4o -n 20

# Use a preset for testing
python CherryAI.py sample config/sample.txt --preset gemini_free
```

**Note:** Ensure the first N lines of your file are representative of the content you want to translate.

---

## 4. Glossary Command

Manage the translation glossary for consistent term translations.

### Usage Patterns

```bash
# Show glossary summary
python CherryAI.py glossary

# List all entries
python CherryAI.py glossary list

# List only names or terms
python CherryAI.py glossary list names
python CherryAI.py glossary list terms

# Search for entries
python CherryAI.py glossary search <query>

# Add a new entry
python CherryAI.py glossary add <original> <translation> [notes]

# Show glossary file location
python CherryAI.py glossary path

# Export glossary
python CherryAI.py glossary export <path>
```

### Examples

```bash
# Show glossary statistics
python CherryAI.py glossary

# List all character names
python CherryAI.py glossary list names

# Search for entries containing "hero"
python CherryAI.py glossary search hero

# Add a character name
python CherryAI.py glossary add "リオス" "Rios"
python CherryAI.py glossary add "勇者" "Hero" "Main character"

# Export to CSV
python CherryAI.py glossary export glossary_backup.csv

# Export to text file
python CherryAI.py glossary export terms.txt
```

### Glossary File

- Location: `user/glossary.csv`
- Format: Original, Translation, Notes, Source, Type, Gender, etc.
- Automatically used during translation

---

## 5. Estimate Command

Check token counts and estimated cost without translating.

### Basic Usage

```bash
python CherryAI.py estimate <path>
```

### Examples

```bash
# Estimate cost for sample.txt
python CherryAI.py estimate config/sample.txt

# Estimate cost for all files in a folder
python CherryAI.py estimate temp/

# Estimate cost for specific file type
python CherryAI.py estimate "temp/message (58).txt"
```

### Output

```
Found 1 files to estimate.
[1/1] Analyzing sample.txt...
  Tokens: 12500 -> 15000 | Cost: $0.0000

=== Total Estimation ===
Files: 1
Total Input Tokens: 12,500
Total Output Tokens: 15,000
Total Estimated Cost: $0.0000
```

---

## 6. Test Command

Run diagnostic tests to verify setup.

### Basic Usage

```bash
python CherryAI.py test [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--skip-api` | Skip API tests (offline mode) |

### Examples

```bash
# Run full diagnostic test (includes API test)
python CherryAI.py test

# Run offline tests only (no API calls)
python CherryAI.py test --skip-api
```

### What It Tests

1. **Dependencies**: openpyxl, openai, tiktoken
2. **Configuration**: CherryAI.ini validation
3. **File I/O**: Read/write operations
4. **Pre-Processing**: Placeholder protection
5. **API Connection**: Model listing
6. **Translation**: 2-line test translation
7. **Post-Processing**: Placeholder restoration

---

## 7. Languages Command

List all supported languages with codes and aliases.

### Usage

```bash
python CherryAI.py languages
```

### Supported Languages

| Code | Language | Aliases |
|------|----------|---------|
| `ja` | Japanese | jp, jpn, japanese |
| `en` | English | eng, english |
| `zh-CN` | Chinese (Simplified) | chinese, simplified |
| `zh-TW` | Chinese (Traditional) | traditional |
| `ko` | Korean | kor, korean |
| `de` | German | deu, ger, german, deutsch |
| `fr` | French | fra, fre, french, français |
| `es` | Spanish | spa, spanish, español |

---

## 8. Help Command

Show help and usage information.

### Usage

```bash
# Show general help
python CherryAI.py help

# Show detailed help for a command
python CherryAI.py help <command>
```

### Examples

```bash
python CherryAI.py help
python CherryAI.py help translate
python CherryAI.py help config
python CherryAI.py help glossary
python CherryAI.py help io
```

---

## 9. IO Command

Configure input/output file formats for translation.

### Basic Usage

```bash
# Show current IO settings
python CherryAI.py io

# List all available formats
python CherryAI.py io formats
```

### Commands

| Command | Description |
|---------|-------------|
| `io` | Show current IO configuration |
| `io formats` | List all available formats |
| `io extract <format>` | Set input (extract) format |
| `io inject <format>` | Set output (inject) format |
| `io standard <ext> <inj>` | Set both formats at once |
| `io preserve_original true` | Include original lines in output |

### Supported Formats

| Format | Description | Supports Pairs |
|--------|-------------|----------------|
| `txt` | Plain text (one line per line) | No |
| `csv` | Comma-separated values | Yes |
| `tsv` | Tab-separated values | Yes |
| `json` | JSON (strings or objects) | Yes |
| `xlsx` | Excel spreadsheet | Yes |

### Planned Formats

| Format | Description | Status |
|--------|-------------|--------|
| `rpgmaker_mv` | RPG Maker MV data files | Planned |
| `rpgmaker_mz` | RPG Maker MZ data files | Planned |
| `pdf` | PDF documents | Planned |
| `epub` | EPUB e-books | Planned |

### Examples

```bash
# View current settings
python CherryAI.py io

# Set up txt input with json output (includes original lines)
python CherryAI.py io standard txt json

# Set up csv input with plain txt output
python CherryAI.py io standard csv txt

# Change only the output format
python CherryAI.py io inject xlsx

# Enable original line preservation
python CherryAI.py io preserve_original true
```

### Format Pair Support

When using pair-supporting formats (csv, tsv, json, xlsx) for output, you can include the original lines alongside translations:

**JSON Output Example:**
```json
[
  {"original": "こんにちは", "translated": "Hello"},
  {"original": "ありがとう", "translated": "Thank you"}
]
```

**CSV Output Example:**
```
Hello,こんにちは
Thank you,ありがとう
```

---

## 10. Interactive Mode

Step-by-step wizard for guided translation.

### Usage

```bash
python CherryAI.py translate --interactive
```

### Steps

1. **File Selection**: Enter path or drag-drop file
2. **Language Selection**: Choose source and target languages
3. **Cost Estimation**: Review token counts and costs
4. **Confirmation**: Approve or cancel
5. **Translation**: Watch progress
6. **Complete**: View output summary

---

## Sample File for Testing

The file `config/sample.txt` is provided for testing. It contains:

- **4,947 lines** of Japanese game dialogue
- **Speaker format**: `Speaker: 「Dialogue」`
- **Code patterns**: `<br>` line breaks
- **Fullwidth characters**: `６２７`, `＝`, `「」`
- **Multiple speakers**: リオス, エマ, 勇者, リオスの部下

### Quick Test Commands

```bash
# Quick sample (10 lines)
python CherryAI.py sample config/sample.txt -n 10

# Standard sample (50 lines)
python CherryAI.py sample config/sample.txt

# Larger sample (100 lines)
python CherryAI.py sample config/sample.txt -n 100

# Estimate full file cost
python CherryAI.py estimate config/sample.txt
```

---

## Common Workflows

### Workflow 1: First-Time Setup

```bash
# 1. Set API key
python CherryAI.py config api_key AIzaSyB...

# 2. Choose provider (Gemini recommended for free tier)
python CherryAI.py config api_url 2

# 3. Verify setup
python CherryAI.py test --skip-api
python CherryAI.py test

# 4. Try small translation
python CherryAI.py sample config/sample.txt -n 10
```

### Workflow 2: Production Translation

```bash
# 1. Estimate costs
python CherryAI.py estimate my_game_data/

# 2. Test on sample
python CherryAI.py sample my_game_data/map001.txt -n 50

# 3. Review output quality

# 4. Full translation
python CherryAI.py translate my_game_data/ -s ja -t en -y
```

### Workflow 3: Glossary Setup

```bash
# 1. Check current glossary
python CherryAI.py glossary

# 2. Add character names
python CherryAI.py glossary add "リオス" "Rios"
python CherryAI.py glossary add "エマ" "Emma"
python CherryAI.py glossary add "勇者" "Hero"

# 3. Export for backup
python CherryAI.py glossary export backup.csv

# 4. Translate with glossary
python CherryAI.py translate story.txt -s ja -t en
```

### Workflow 4: Multi-Language

```bash
# Translate to multiple languages
python CherryAI.py translate story.txt -s ja -t en -n 100
python CherryAI.py translate story.txt -s ja -t de -n 100
python CherryAI.py translate story.txt -s ja -t fr -n 100
```

---

## Troubleshooting

### "No supported files found"

- Check file extension (.txt, .csv, .tsv, .json, .xlsx)
- Verify path exists and is accessible

### "Unknown language"

- Use `python CherryAI.py languages` to see valid codes
- Try aliases: `jp`, `jpn`, `japanese` all work for Japanese

### "API Error"

- Check API key: `python CherryAI.py config api_key`
- Verify URL: `python CherryAI.py config api_url`
- Run `python CherryAI.py test` to diagnose
- Check `logs/api_log.txt` for details

### Translation Quality Issues

- Add glossary entries: `python CherryAI.py glossary add ...`
- Edit `config/game_summary.txt` for context
- Edit `config/translation_style.txt` for style preferences

---

## Planned Commands (Coming Soon)

### Cache Command

Manage the request cache for API responses.

```bash
# Show cache statistics
python CherryAI.py cache

# Clear all cache entries
python CherryAI.py cache clear

# Clear cache entries older than 30 days
python CherryAI.py cache clear --older-than 30

# Show cache entries for a specific model
python CherryAI.py cache list --model gemini-2.0-flash
```

### Rate Limit Command

View and manage API rate limits. The rate limiter tracks requests per minute (RPM), tokens per minute (TPM), and daily limits for each model.

```bash
# Show current usage and limits
python CherryAI.py ratelimit

# Show usage for specific model
python CherryAI.py ratelimit gemini-2.0-flash-lite

# Reset daily counter (for testing)
python CherryAI.py ratelimit reset
```

### Rate Limiting

CherryAI includes an advanced rate limiting system that prevents API rate limit errors and tracks usage:

**Features:**
- Per-model rate limits (RPM, TPM, daily quotas)
- Automatic waiting when limits are reached
- Daily usage persistence across sessions
- Capacity estimation for large translations
- Support for concurrent request limiting

**Default Rate Limits (Free Tier):**

| Model | RPM | TPM | Daily Requests |
|-------|-----|-----|----------------|
| gemini-2.0-flash | 15 | 1M | 1500 |
| gemini-2.5-pro | 5 | 250K | 50 |
| gemini-2.5-flash | 10 | 250K | 500 |
| gpt-4o | 500 | 30K | 10000 |
| gpt-4o-mini | 500 | 200K | 10000 |
| claude-* | 50 | 40K | 1000 |
| local models | Unlimited | Unlimited | Unlimited |

**Usage Examples:**

```bash
# Enable rate limiting for a translation
python CherryAI.py translate file.txt -s ja -t en --rate-limit

# Enable with daily limit checking (warns before exceeding)
python CherryAI.py translate file.txt -s ja -t en --rate-limit --daily-limit-check

# Set maximum concurrent requests
python CherryAI.py translate file.txt -s ja -t en --rate-limit --max-concurrent 3
```

**Rate Limit Files:**
- `user/rate_limits.json` - Persistent daily usage tracking

### Local Command

Detect and check local LLM servers (LM Studio, Ollama, text-generation-webui).

```bash
# Scan for running local servers
python CherryAI.py local detect

# Check a specific URL
python CherryAI.py local check --url http://localhost:1234/v1

# Get setup instructions for a provider
python CherryAI.py local setup --provider lmstudio
python CherryAI.py local setup --provider ollama
python CherryAI.py local setup --provider text-gen-webui
```

**Local LLM Translation:**

```bash
# Translate with local LLM (no API key needed)
python CherryAI.py translate file.txt -s ja -t en --no-api-key

# Check server health before translating
python CherryAI.py translate file.txt -s ja -t en --no-api-key --check-local

# Use a local preset
python CherryAI.py translate file.txt -s ja -t en --preset local
python CherryAI.py translate file.txt -s ja -t en --preset ollama
```

**See Also:** [Local LLM Guide](local_llm_guide.md) for detailed setup instructions.

### Style Command

Manage translation style presets.

```bash
# List available style presets
python CherryAI.py style list

# Show details of a preset
python CherryAI.py style show fantasy_medieval

# List all presets by category
python CherryAI.py style list --category genre

# Create custom preset from current style
python CherryAI.py style create my_preset

# Use preset in translation
python CherryAI.py translate file.txt --style-preset fantasy_medieval,archaic_english
```

### Available Style Presets

| Category | Presets |
|----------|---------|
| Time Period | `archaic_english`, `victorian`, `modern_casual`, `futuristic_scifi` |
| Regional | `british_english`, `american_english`, `australian_english` |
| Japanese | `formal_japanese`, `casual_japanese` |
| Genre | `fantasy_medieval`, `fantasy_eastern`, `noir_detective`, `romance_flowery`, `horror_gothic`, `comedy_witty` |
| Character | `noble_aristocrat`, `street_slang`, `child_innocent`, `elderly_wise`, `military_formal`, `pirate_nautical`, `robot_mechanical` |
| Dialect | `scottish_dialect`, `irish_dialect`, `southern_us`, `cockney` |

---

## File Locations

| File | Purpose |
|------|---------|
| `CherryAI.ini` | Main configuration (API keys, settings) |
| `config/sample.txt` | Test file for verification |
| `user/glossary.csv` | Character/term translations |
| `user/rate_limits.json` | Rate limit usage tracking |
| `cache/request_cache.json` | Cached API responses (planned) |
| `config/game_summary.txt` | Story context for AI |
| `config/translation_style.txt` | Style preferences |
| `config/style_presets/` | Built-in style presets (planned) |
| `user/style_presets/` | Custom style presets (planned) |
| `config/prompt.txt` | Base translation prompt |
| `logs/api_log.txt` | API request/response log |
| `logs/api_log_YYYYMMDD_HHMMSS.txt` | Timestamped logs (planned) |
| `logs/api_log_summary.csv` | Log summary file (planned) |
| `output/` | Translated output files |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error or user abort |
