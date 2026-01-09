# CherryAI

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-1495%2B%20passing-brightgreen.svg)](#testing)

**LLM-Powered Translation Tool for Games and Software Localization**

CherryAI is a powerful batch translation tool that prepares text for AI translation, sends it to LLMs (OpenAI, Gemini, local models), and restores protected content afterward. It's designed for game localization, handling code, variables, and special formatting automatically.

## Features

- **Multi-Format Support**: TXT, CSV, TSV, JSON, Excel (.xlsx), HTML
- **LLM Integration**: OpenAI API, Google Gemini, local LLM servers
- **Smart Protection**: Automatically protects code, variables, and patterns
- **Batch Processing**: Process multiple files with consistent rules
- **Deduplication**: Avoid re-translating duplicate lines
- **Glossary Support**: Maintain consistent translations
- **GUI & CLI**: Both graphical and command-line interfaces
- **Manifest System**: Track progress and resume translations

## Installation

### From PyPI (Recommended)

```bash
pip install cherryai
```

### From Source

```bash
git clone https://github.com/cherryai/cherryai.git
cd cherryai
pip install -e .
```

### Optional Dependencies

```bash
# Full functionality
pip install cherryai[full]

# Individual features
pip install cherryai[api]    # OpenAI API support
pip install cherryai[excel]  # Excel file support
pip install cherryai[html]   # HTML file support
```

## Quick Start

### GUI Mode

```bash
python CherryAI.py
```

### CLI Mode

```bash
# Basic translation
python -m functions.CLI --input files/ --output translated/ --mode standard

# With glossary
python -m functions.CLI --input files/ --glossary glossary.csv --mode aggressive
```

## How It Works

1. **Load Files**: Select one or more files for translation
2. **Configure Protection**: Set up rules for code, names, patterns
3. **Pre-Process**: Tool removes/replaces protected content
4. **Translate**: Send to AI (auto or manual)
5. **Post-Process**: Restore protected content in translated text

## Configuration

CherryAI uses `CherryAI.ini` for settings:

```ini
[API]
api_key = your-openai-api-key
model = gpt-4

[Processing]
chunk_size = 50
batch_delay = 1.0
```

See `doc/features.md` for full configuration options.

## Documentation

- [User Guide](doc/features.md) - Complete feature documentation
- [CLI Guide](doc/cli_guide.md) - Command-line interface reference
- [Technical Docs](doc/technical.md) - Architecture and internals
- [Local LLM Guide](doc/local_llm_guide.md) - Using local models

## Testing

```bash
# Run all tests
pytest dev/ -v

# Run with coverage
pytest dev/ --cov=functions --cov=formats --cov=modi
```

Currently passing **1495+ tests**.

## Type Checking

CherryAI now has comprehensive type hints across core modules and validates with `mypy`.

- Run type checks:

```
# Full project coverage (functions, formats, modi)
python -m mypy -p CherryAI.functions -p CherryAI.formats -p CherryAI.modi

# Or by paths
python -m mypy CherryAI/functions CherryAI/formats CherryAI/modi
```

- Notes:
	- Central mypy settings live in `pyproject.toml` (`follow_imports = "skip"`, `explicit_package_bases = true`).
	- Optional third-party stubs may be missing (e.g., `openpyxl`); these are silenced with targeted ignores for imports.
	- Pillow text measurement uses `ImageDraw.textlength` with a `textbbox` fallback to avoid deprecated/attr-defined issues.
	- The OpenAI SDK call sites are typed via localized `Any` casts for overload compatibility.
	- Optional `tiktoken` usage is guarded and typed as `Any` when unavailable.
	- The CLI uses `TypedDict` and `Literal` types to model task structures precisely.

## Project Structure

```
CherryAI/
├── CherryAI.py          # Main entry point
├── functions/           # Core functionality
│   ├── api_client.py    # LLM API integration
│   ├── dedup.py         # Deduplication system
│   ├── glossary.py      # Glossary management
│   └── ...
├── formats/             # File format handlers
├── modi/                # Processing modes
├── config/              # Default configuration
├── templates/           # Mode templates
└── doc/                 # Documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest dev/ -v`
5. Submit a pull request

## License

GPLv3 License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with support from the translation community hosted by Dazed.
