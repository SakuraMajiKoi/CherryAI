# Editor PySide6 Refactor Plan

## Scope

This plan covers the CherryAI Editor opened from the main window `Editor` button/menu entry only.

The goal is to move the Editor to PySide6 as the primary UI library while keeping current CherryAI Editor behavior intact:

- single-instance non-modal Editor window
- `Full Files` and `Lines Only` modes
- manifest-backed persistence through `EditorState.files`
- parser-backed line history and locator mapping
- unified diff views against staged `Original/` and prior patch state
- save-to-Step-9 continuity for parser-backed output
- shared project/file context across mode switches

The migration should stay Editor-only at first. Do not widen the Qt rollout to the rest of the Tk application until the Editor is stable and verified.

## Current Baseline To Preserve

Current shipped behavior is defined by the existing Tk Editor host plus shared backend helpers:

- `gui/dialogs/patch_editor_view.py`
- `gui/dialogs/table_view.py`
- `functions/manifest_manager.py`
- `gui/app.py` Editor entry point

The PySide6 work must preserve backend semantics and move UI concerns only.

## PySide6 Direction

Use standard Qt widgets where they naturally replace current custom Tk behavior:

- `QMainWindow` for the Editor shell
- `QDockWidget` for file tree, diff panes, history panes, and optional inspector panes
- `QPlainTextEdit` for large full-file editing
- `QTreeView` with a model-backed file browser for staged file navigation
- `QSyntaxHighlighter` plus editor selections for locator and parser-match highlighting
- `QSplitter` for resizable panes where docking is too heavy
- `QSettings` plus `saveGeometry()` / `saveState()` / splitter `saveState()` for Editor-only layout persistence
- Qt actions/shortcuts for save, reload, search, replace, diff visibility, and mode switching

Qt quality-of-life features are welcome when they are effectively free because the framework already provides them, but feature parity comes first.

## Phase 0: Preparation And Boundaries

1. Add `PySide6` as a project dependency.
2. Keep all Editor processing in shared backend modules; do not move logic from `functions/manifest_manager.py` into the Qt widgets.
3. Write a thin Editor-facing adapter layer for Qt so backend payloads stay UI-agnostic.
4. Freeze the shipped Tk Editor contract in tests before the first Qt implementation lands.

Exit criteria:

- dependency present
- backend/UI boundary documented
- focused regression tests green

## Phase 1: Qt Editor Shell

1. Create a new PySide6 Editor window module without removing the existing Tk host.
2. Build a `QMainWindow` shell with unique window identity and single-instance reuse.
3. Add central mode switching for `Full Files` and `Lines Only`.
4. Persist geometry and shell layout with `QSettings`.
5. Keep the Tk app as the launcher; only the Editor window changes.

Exit criteria:

- Editor opens once and focuses on reuse
- geometry and dock/splitter state restore across reopen
- no manifest writes occur from shell setup alone

## Phase 2: Full Files Mode Parity

1. Port the left file browser to a model-backed Qt tree.
2. Port the central text editor to `QPlainTextEdit`.
3. Recreate save, reload, undo/redo, and dirty-state behavior.
4. Port search/replace with next/previous, replace current, replace all, and regex support.
5. Port diff panes against `diff_to_original` and `diff_to_patch`.
6. Port locator highlighting and cursor-driven history targeting.

Qt-native improvements allowed in this phase:

- standard shortcuts and action enable/disable state
- dockable diff/history panes
- persistent splitter sizing
- better text navigation and selection handling

Exit criteria:

- `save_editor_patch()` integration unchanged
- diff panes match backend payloads
- locator highlighting and file selection remain stable on large files

## Phase 3: Lines Only Mode Integration

1. Decide whether `Lines Only` is embedded directly as a Qt surface or hosted through an adapter over existing table behavior first.
2. Preserve current line-level editing semantics, column/stage awareness, and search/replace behavior.
3. Keep mode switching inside one Editor window with shared file/locator context.
4. Ensure switching from `Full Files` to `Lines Only` carries the closest file and locator target forward.
5. Ensure `Lines Only` saves do not regress sparse manifest semantics.

Exit criteria:

- mode switch is instant and single-window
- file context and locator context survive the switch
- line saves still align with manifest and staged files

## Phase 4: Shared Polish And Stability

1. Add status bar summaries for file, dirty state, locator, and mode.
2. Add action/menu definitions for common Editor commands.
3. Add optional dock visibility toggles.
4. Audit keyboard navigation and focus behavior.
5. Check large-file responsiveness on real projects, especially `Projects/OmegaKano.CherryAI.json`.

Exit criteria:

- layout remains usable after repeated reopen/switch/save cycles
- no focus loops or recursive selection loops
- acceptable open and interaction time on OmegaKano-scale projects

## Phase 5: Cutover

1. Make the PySide6 Editor the default path behind the main app Editor entry point.
2. Keep the Tk host available behind a temporary fallback switch until parity is proven.
3. Retire Patch Editor naming from user-facing UI.
4. Remove the fallback only after focused Editor regression and real-project validation pass.

Exit criteria:

- PySide6 Editor is default
- fallback no longer needed
- docs/specs/tests updated to describe the new shipped surface

## Required Regression Coverage

Before cutover, keep or add focused tests for:

- single-instance Editor reuse
- geometry/dock/splitter persistence
- `Full Files` search/replace and save behavior
- diff regeneration from shared backend payloads
- parser-backed line history and locator sync
- `Lines Only` mode switch context carry-over
- save-to-Step-9 continuity for parser-backed files
- coexistence of Qt Editor with the Tk main application shell

## Real-Project Validation

Use `Projects/OmegaKano.CherryAI.json` as a standing validation manifest when a real project is required.

Minimum validation checks during implementation:

1. Open project in the main app and launch the Editor.
2. Open a large file in `Full Files` mode.
3. Search, edit, save, reopen, and verify diff/history consistency.
4. Switch to `Lines Only` and confirm file-context carry-over.
5. Run Step 9 export validation for an Editor-modified parser-backed file.

## Non-Goals For This Plan

- migrating the full CherryAI app from Tk to Qt
- changing manifest storage contracts for non-Editor systems
- replacing shared backend diff/parser/history logic with Qt-specific logic
- broad visual redesign unrelated to Editor usability and parity