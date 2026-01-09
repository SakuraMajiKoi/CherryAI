📚 DOCUMENTATION STRUCTURE - READ THIS FIRST

=============================================================================

CONSOLIDATED DOCUMENTATION (READ THESE)

Three main documents contain all information:

1. **features.doc**
   For: End users, project managers, anyone who wants to know what the tool does
   Contains: Workflow, capabilities, file formats, FAQs, step-by-step guides
   Time to read: 30 minutes
   
2. **technical.doc**
   For: Developers, AI agents, those who need to modify or extend the tool
   Contains: Module overview, API reference, architecture, data formats, development guidelines
   Time to read: 45 minutes
   
3. **todo.doc**
   For: Project managers, developers planning future work
   Contains: Outstanding tasks, roadmap, known issues, effort estimates
   Time to read: 20 minutes

=============================================================================

REFERENCE DOCUMENTS (KEEP FOR DEEP DIVES)

Architecture Reference:
- filetreedoc.md - Complete module dependency tree (50+ modules documented)

Domain-Specific Features:
- GLOSSARY_*.md - Glossary system architecture and usage
- ANCHOR_*.md - Anchor equivalence system
- CODE_*.md - Code analysis features
- UNIQUE_PLACEHOLDER_*.md - Placeholder system design
- REGEX_PATTERNS_REFERENCE.md - Regex patterns and examples
- ROMANIZATION_REFERENCE.md - Romanization system

Status & History:
- TASK_COMPLETION_CHECKLIST.md - Detailed metrics and completion status

=============================================================================

ARCHIVED DOCUMENTS (CONSOLIDATED INTO THREE MAIN FILES)

These files have been consolidated and are kept for historical reference only:

- doc.md (archived - marked as deprecated)
- SESSION_4_COMPLETION.md (archived - content in features/technical/todo)
- COMPLETION_SUMMARY.md (archived)
- FINAL_STATUS_REPORT.md (archived)
- GLOSSARY_README.md (archived - glossary info in features.doc)
- DEPENDENCY_MANAGEMENT.md (archived - info in features.doc)
- QUICK_REFERENCE.md (archived - info in features.doc)
- CONFIG_OPTIONS_INTEGRATION.md (archived - info in technical.doc)
- SPLIT_SUMMARY.md (archived - info in technical.doc)
- UI_UX_IMPROVEMENTS_REPORT.md (archived)
- README_SUMMARY.md (archived)
- DOCUMENTATION_INDEX.md (archived - use this index instead)
- DOCUMENTATION_INDEX_SESSION4.md (archived)
- WORK_COMPLETION_SUMMARY.txt (archived)
- EXECUTIVE_SUMMARY.md (archived)

=============================================================================

HOW TO USE THIS DOCUMENTATION

START HERE (You are here!):
→ Read the three main documents above

UNDERSTAND THE WORKFLOW:
→ features.doc "The Basic Workflow" section

LEARN TO USE THE TOOL:
→ features.doc "How to Use - Step by Step" section

LEARN THE ARCHITECTURE:
→ technical.doc "Architecture Diagram" section

BUILD A NEW FEATURE:
→ technical.doc "Development Guidelines" section
→ todo.doc "How to Contribute" section

PLAN FUTURE WORK:
→ todo.doc "Roadmap" section

INVESTIGATE A BUG:
→ technical.doc "Entry Points" section
→ Start with the entry point, follow the code flow

=============================================================================

QUICK REFERENCE

File Locations:
- Main code: CherryAI/
- Core processing: CherryAI/functions/
- Modes (plugins): CherryAI/modi/
- User data: CherryAI/user/
- Manifests: CherryAI/manifests/
- Logs: CherryAI/logs/
- Documentation: CherryAI/doc/

Entry Points:
- GUI: python -m CherryAI.CherryAI
- CLI Analysis: python -m CherryAI.CherryAI --analyze FILE
- Check deps: python CherryAI/functions/dependencies.py --verbose

Key APIs:
- Processor: functions/mainhelper.py
- Glossary: functions/glossary.py
- Analysis: functions/analysis.py
- Dedup: functions/dedup.py
- Modes: modi/*.py

File Formats:
- Manifest (rules saved): JSON
- Glossary: CSV
- Config: INI
- Supported input: TXT, CSV, TSV, JSON, XLSX

=============================================================================

WHAT'S NEW (Session 4)

✅ features.doc - NEW consolidated user guide
✅ technical.doc - NEW consolidated developer reference
✅ todo.doc - NEW consolidated roadmap
✅ Dependency management system (auto-install on changes)
✅ Config and Options modules (Session 4)

=============================================================================

QUESTIONS?

Q: Where do I find documentation about feature X?
A: Check features.doc table of contents for X. If not there, check technical.doc.

Q: How do I add a new mode?
A: See technical.doc "Development Guidelines" → "Adding a New Mode"

Q: What needs to be done next?
A: See todo.doc for roadmap and outstanding work

Q: What's the overall architecture?
A: See technical.doc "Architecture Diagram"

Q: How do I use the GUI?
A: See features.doc "How to Use - Step by Step"

=============================================================================

VERSION INFO

Documentation created: 2025-11-13
Format: Three consolidated .doc files (plain text) + reference .md files
Status: Current and maintained

=============================================================================
