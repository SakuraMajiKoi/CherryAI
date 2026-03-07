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
- Request building unification: Preview, Estimate, and Translate now use identical line filtering via shared `is_placeholder_only()` — mixed `__PROTECTED__` lines with CJK content are no longer wrongly excluded
- Language skip now uses original text for script detection instead of preprocessed text where CJK was replaced with `__PROTECTED__`
- Request Preview applies language skip before chunking (matching Start Translation behaviour)
- Estimation uses formation pipeline for both Original and Preprocessed columns with per-request JSON token counting
- `PROT_PATTERN` in validation.py now matches actual `__PROTECTED__` tokens (previously only matched `__PROT__`)
- Language detection reverted to operate on prioritized text (what the LLM receives) — a line like `__PROTECTED__ ON` is now correctly skipped as non-source
- `_PLACEHOLDER_TOKEN_RE` broadened to match all tool placeholder types (`__COLOR__`, `__FONT__`, `__TEMPREPL__`, `__NAME__`, etc.), not just `__PROTECTED__`/`__DEDUP__`/`__CUSTOM__`
- Removed unnecessary `detection_text` parameter from `validate_line_pre()` — caller provides the correct text directly
- Fixed `_apply_language_skip()` placeholder stripping: placeholder token names (PROTECTED, COLOR, etc.) are Latin letters that skewed ratio-based script detection — CJK lines with placeholders were wrongly classified as "latin" and skipped; tokens are now stripped before detection
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
