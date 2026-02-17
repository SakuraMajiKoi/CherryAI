# Changelog

All notable changes to CherryAI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Manifest v2.1 with extended property tags and auto-tagging system
- Post-processing framework with comprehensive text restoration
- Auto-tagger with 24 extraction categories (names, code, tags, etc.)
- Rate limiting with adaptive backoff
- Request caching for API calls
- Retry handler with configurable strategies
- Rolling context for translation continuity
- Comprehensive test suite (1495+ tests)
- CI/CD with GitHub Actions
- Type hints throughout codebase

### Changed
- Modernized packaging with pyproject.toml
- Improved error handling and validation
- Enhanced placeholder system
- Input button now directly opens Unified Selection dialog (no dropdown menu)
- Estimation step renamed to Costs step (Phase 40)

### Fixed
- Manifest v3.2 filedir loading: lines now properly restored when reopening projects
- File tree ordering: folders now appear above files and are collapsed by default
- Test imports updated from `estimate` to `costs` module
- Various edge cases in text processing
- Unicode handling improvements

## [1.0.0] - 2024-12-01

### Added
- Initial release
- Multi-format support (TXT, CSV, JSON, Excel, HTML)
- LLM-powered translation via OpenAI API
- Batch processing with configurable chunk sizes
- Deduplication system for efficiency
- Glossary support for consistency
- Multiple translation modes (standard, aggressive, line-by-line)
- GUI interface with configuration management
- Manifest system for tracking translation progress
