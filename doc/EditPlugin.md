# Edit Plugin Specification

## Purpose

The Edit Plugin is a developer-facing direct edit mode for translated games. Its goal is to let a translator open an editor at the currently visible dialogue, adjust the source script line, save it, and continue testing with minimal context switching.

The design must be portable across engines. The current KiriKiri2 implementation is the reference implementation, but the same concepts should apply to engines such as RPG Maker MV/MZ, Ren'Py, Unity VN frameworks, or custom script runners.

The plugin is not a translation UI. It is a runtime patching aid for already unpacked or override-backed scripts.

## Required User Experience

1. A configurable hotkey opens the edit UI while the game has focus.
2. Opening the editor with no current dialogue must not crash. It should show a clear unavailable state or do nothing with a log entry.
3. The editor should open near or inside the game window. If an in-engine overlay is practical, prefer that. If not, use an always-on-top tool window positioned over the game client area.
4. The editor should remember its last screen position and reopen there. The saved position should be clamped to a visible monitor work area so an old off-screen coordinate cannot hide the editor.
5. The editor must show:
   - The editable script path, relative to the patch or game root when possible.
   - The resolved line number or line range.
   - The current rendered or advanced text.
   - The original editable script text.
   - Whether the target file can be written.
6. The editable control must support multiline text and wrap naturally at the text box width. It should not require horizontal scrolling for normal dialogue prose.
7. If the editor window is resizable, keep the dialogue text box width fixed unless the engine UI explicitly supports responsive width. Vertical resizing should grow and shrink the text box while keeping the history and command buttons in stable positions.
8. The editor must provide:
   - `Edit` or `Save`.
   - `Cancel`.
   - Previous and next history buttons, shown as `<` and `>`.
9. The history buttons must browse recently available dialogue lines, not only lines that were previously opened with the hotkey.
10. Saving must support multiple edits during one session.
11. Saving must update the in-memory history entry and invalidate any file cache.
12. Save failures must not crash the game. They should show a failure status and log enough detail to diagnose the cause.

## Configuration

Every implementation should support an engine-local config block:

```ini
[editmode]
enabled = true
key = e
```

Rules:

- `enabled` accepts at least `true` and `false`. Implementations may also accept `1`, `yes`, or `on`.
- `key` is a single activation key by default.
- Default key is `e`.
- The hotkey must only fire while the game process or game canvas has focus.
- The hotkey must be edge-triggered and debounced. Holding the key should not open repeated dialogs.
- The hotkey must not be globally consumed while the editor text box is focused. In browser engines, install the listener on the game canvas or scene layer and ignore events from input or textarea elements.

## Core Data Model

Each engine adapter should maintain a current edit state:

```text
requestedName       Engine-level script or resource name.
placedPath          Engine-resolved source location, archive path, or URL.
editableFilePath    Loose filesystem path if available.
renderedText        Text currently visible or recently advanced.
matchedFilePath     Loose filesystem path containing the matched text.
matchedLineText     Original editable source text.
matchedLineIndex    Zero-based line index or equivalent source index.
matchedLineCount    Number of physical source lines or event records covered.
hasMatchedLine      True after a successful source match.
history             Ordered list of editable dialogue entries.
```

History entries should contain:

```text
filePath            Absolute writable path or virtual source identifier.
displayPath         Short path relative to patch root or game root.
renderedText        Visible or advanced text used for matching.
lineText            Editable source text.
lineIndex           Source line index, event command index, or JSON path index.
lineCount           Number of source lines or commands covered.
canEdit             Current write capability.
```

## Text Tracking Strategy

There are two valid tracking strategies. Prefer the first whenever the engine allows it.

### Script Advancement Mirroring

Open engines should mirror dialogue advancement at the script interpreter level.

Examples:

- RPG Maker MV/MZ: hook `Game_Interpreter.prototype.command101` and the following `401` continuation commands, or hook the point where `Game_Message` receives text.
- Ren'Py-like engines: hook statement execution or dialogue display callbacks.
- Engines with JSON/event commands: track map ID, event ID, page index, command index, and text command span.

Advantages:

- The source location is known without fuzzy search.
- Formatting tokens are still available.
- Wrapped text split across multiple records can be reconstructed precisely.
- History can be recorded when text advances, before any hotkey is pressed.

### Rendered Text Matching

Closed or binary engines may only expose rendered text or debug output. In that case:

- Track the currently loaded script file through file or stream open hooks.
- Track text drawn on message layers, debug text, or script globals.
- Search the currently loaded source file for the rendered text.
- Use normalization and wildcard matching to handle placeholders and invisible characters.

The current KiriKiri2 implementation uses both approaches where possible:

- File hooks identify the current `.ks`.
- `MessageLayer.tjs` mirrors current message text into script globals.
- Native edit mode queries these globals when the hotkey opens.
- Native matching searches the loose `.ks` file.
- Nearby previous editable `.ks` lines are backfilled into history as a practical fallback.

## Matching Rules

Matching must be strict enough to avoid false positives but flexible enough to handle runtime substitutions.

Normalize both candidate source text and rendered text:

- Trim leading and trailing whitespace.
- Collapse all whitespace runs to a single space.
- Remove zero-width and control characters.
- Normalize curly apostrophes to ASCII apostrophe.
- Ignore decorative double quotes where appropriate.
- Compare case-insensitively unless the engine requires case-sensitive text.

For source patterns:

- Treat recognized placeholders as wildcards. In KiriKiri2, bracket tokens such as `[HF]`, `[SF]`, and `[NAME_1]` are wildcard placeholders when they contain uppercase letters, digits, or underscores.
- Do not use loose substring matching for normal lines. A rendered text `Uh...` must not match source text `Huh...?`.
- Wildcard matching must still be anchored:
  - Text before the first wildcard must match from the beginning.
  - Text after the last wildcard must reach the end.
  - Literal parts between wildcards must appear in order.

Example:

```text
Source:   [HF]'s face, lit by the setting sun, looked as lonely as her words.
Rendered: Sakura's face, lit by the setting sun, looked as lonely as her words.
Result:   match
```

Multiline source lines:

- Manual line breaks may be meaningful in scenario files.
- Matching must support joining consecutive editable source lines.
- The reference KiriKiri2 implementation checks up to 8 consecutive editable lines.
- Save must replace the same number of physical lines unless the edit text itself introduces a new line count.

## History Requirements

History exists to edit recent lines after later context makes a problem visible.

Required behavior:

- Keep at least the latest 64 dialogue entries.
- Current entry is the newest entry.
- `<` moves to older entries.
- `>` moves to newer entries.
- Duplicate entries for the same source location should be replaced, not appended repeatedly.
- Saving an older history entry must update that entry and the shared history state.
- History must be populated before the user presses the hotkey when the engine supports script advancement hooks.

Fallback behavior for engines without reliable advancement hooks:

- After matching the current source location, backfill nearby previous editable source lines from the same file.
- Backfilled entries are less precise than true render history, but they make previous-line editing viable.
- Mark or log backfilled history so debugging can distinguish it from actual advanced text history.

## Save Semantics

When saving:

1. Read the current file from disk at save time.
2. Preserve the original encoding when possible.
3. Verify the target line or command index is still valid.
4. Replace the matched span only.
5. Preserve the final newline behavior of the replaced span.
6. Write atomically where practical.
7. Clear or invalidate caches for that file.
8. Update the active editor state and history entry.
9. Log file, location, and saved text.

Encoding:

- KiriKiri2 reference supports UTF-8, UTF-8 BOM, UTF-16LE, and CP932.
- RPG Maker MV/MZ JSON files are normally UTF-8 JSON and should be parsed and serialized as JSON, not edited with raw string replacement.

Write-protected or locked files:

- Detect writability before enabling save.
- If the engine locks the source file, use a safe overwrite strategy:
  - Write to a sidecar override file if the engine supports loose-file priority.
  - Write to a temporary file and schedule replacement after process exit.
  - Offer a manual export path.
- Never corrupt packed archive files in place.
- Archive-backed resources are editable only when a loose override path is available or can be generated.

## RPG Maker MV/MZ Notes

RPG Maker MV/MZ should not rely on rendered canvas text for matching. It is an open JavaScript engine with accessible interpreter state, so the plugin should mirror script advancement.

Relevant data shape:

- Event commands live in JSON arrays, usually under map event pages or common events.
- `101` starts a Show Text command.
- One or more following `401` commands contain the text lines.
- Choices, scrolling text, and plugin commands have other command codes and should be handled separately.

Recommended tracking record:

```text
mapId
eventId
pageIndex
listIndexStart
listIndexEnd
jsonPath
speaker/options from 101
textLines from 401 commands
joinedText
sourceFile
```

On `command101`:

1. Record the interpreter context.
2. Read the current command at `_index`.
3. Collect following `401` commands until the command sequence ends.
4. Store the joined text as the current entry.
5. Push the entry into history immediately.
6. Continue normal engine behavior.

On save:

1. Load the owning JSON file, for example `data/Map001.json` or `data/CommonEvents.json`.
2. Navigate to the recorded event/common-event command list.
3. Replace the captured `401` command span.
4. If the edited text has a different number of lines, insert or remove `401` commands.
5. Preserve the `101` command unless the UI explicitly edits speaker/window options.
6. Serialize JSON with the repository or plugin-selected formatting policy.

JSON formatting:

- MV/MZ projects vary in formatting. Some are compact, some are pretty-printed.
- Prefer parse-modify-serialize with a stable formatter over regex edits.
- Keep a backup before first write.
- If exact formatting preservation is required, use a JSON AST or patcher that preserves token spans.

File locking:

- Browser runtime deployments may not allow direct disk writes.
- NW.js desktop builds can write through Node `fs` when allowed.
- Web exports may require download/export instead of direct save.
- Packaged games may require writing an override file or patch project copy rather than the packaged asset.

## UI Placement

Preferred order:

1. Native/in-engine overlay inside the game viewport.
2. Tool window owned by the game window and positioned inside the client rectangle.
3. External always-on-top editor window.

The editor must not steal the hotkey from its own text box. Once open, keyboard input belongs to the editor controls.

Position and size:

- Persist the editor's screen position when the window closes through Cancel, the close button, or equivalent dismissal.
- Store coordinates in engine-local config when possible. The KiriKiri2 reference uses optional `[editmode]` keys `window_x` and `window_y`.
- Reopen at the saved coordinates on the next edit session, including after restarting the game if config persistence is available.
- Clamp restored coordinates to a visible monitor work area.
- Keep the editor width stable for engines where layout and text wrapping depend on a known textbox width.
- Allow vertical resizing when practical. The multiline text box should grow and shrink with the window; the current-line label and `<`, `Edit`, `>`, `Cancel` buttons should remain anchored below it.
- The text box should wrap words or engine text units according to its visible width. Horizontal scrolling should be avoided for normal dialogue text.

For browser engines:

- Use a DOM overlay above the canvas.
- Stop propagation only inside the editor.
- Ignore the edit hotkey while focus is in `input`, `textarea`, `select`, or contenteditable elements.

For native engines:

- Marshal UI creation to the game owner thread if the engine is not thread-safe.
- Do not call script VM APIs directly from a polling thread.
- Use an owner-window message or equivalent queue to open the dialog safely.

## Logging

Log at least:

- Config load result.
- Hotkey press.
- Current script/resource path.
- Current line match result.
- History import/backfill counts.
- Dialog open and close.
- Save success or failure.
- Writability or lock status.
- Any exception while querying script state.

Suggested KiriKiri2-style log lines:

```text
EditMode config enabled=true key=e vk=69
EditMode scenario request=A_A1a01200.ks placed=... editable=...
EditMode current line file=... line=269 rendered=... text=...
EditMode imported script history entries=4 matched=4 total=4
EditMode backfilled nearby history entries=24 total=25
EditMode matched file=... line=269 writable=true text=...
EditMode saved file=... line=269 text=...
```

## KiriKiri2 Reference Behavior

Current reference implementation:

- Source code: `libraries/KiriKiriInjection/KirikiriUnencryptedArchive/EditMode.cpp`.
- Config: `kirikiri-patched.ini` and `patch/kirikiri-patched.ini`.
- Script bridge: `libraries/KiriKiriInjection/SystemPatchTemplates/MessageLayer.tjs`.
- Live test target: `dev/kanotsuku2`.

Behavior summary:

- Ensures `[editmode]` exists in old and patch INI files.
- Polls the configured key on a background thread.
- Ignores hotkey presses when the game window is not foreground.
- Posts an owner-window message before opening the editor to avoid script VM calls from the hotkey thread.
- Tracks current `.ks` file from text stream hooks.
- Stores current and historical message text in TJS globals.
- Queries current/history globals when the dialog opens.
- Matches rendered text against the current loose `.ks` file.
- Uses placeholder-aware anchored matching.
- Backfills nearby previous editable lines when true render history is incomplete.
- Shows a native Win32 multiline edit dialog with `<`, `Edit`, `>`, and `Cancel`.
- Persists the native dialog screen position as `[editmode] window_x` and `window_y`.
- Keeps the dialog width fixed while allowing vertical resize.
- Uses word-wrapped multiline editing and grows the text box vertically as the window height changes.
- Saves back to the loose `.ks` file with encoding preservation.

Known limitations:

- The KiriKiri2 implementation edits only loose override files, not packed archive members.
- True history depends on script bridge coverage; backfill is used when runtime history is incomplete.
- The current native UI is a topmost tool window, not an in-engine overlay.

## Acceptance Checklist

An engine adapter is viable when:

- Hotkey opens the editor without crashing on title screens or non-dialogue scenes.
- Current dialogue resolves to the exact editable source span.
- Placeholder substitutions do not prevent matching.
- Loose false positives such as `Uh...` matching `Huh...?` are rejected.
- Previous lines are available without previously opening them.
- Multiline edits save correctly.
- Multiple saves in one session are reflected in history.
- Read-only or locked targets disable save or use a documented override strategy.
- Paths shown to users are relative and readable.
- Logs provide enough data to diagnose source tracking and save failures.
