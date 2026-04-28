# RegEx Help Window Design

## Goal

Design a light, non-blocking `RegEx Maker` help window that lets users provide one or more example input lines, optional replacement targets, and selection-driven guidance so CherryAI can suggest several ranked regex search and replace candidates in real time.

The design must stay aligned with CherryAI's existing behavior instead of inventing a separate regex system.

The primary interaction should shift away from freeform command typing wherever possible: users should select text spans inside the examples, right-click to declare intent such as constants, variables, or capture groups, and only fall back to a structured options popup when the choice cannot be expressed from a direct selection.

## Existing CherryAI Constraints To Reuse

### Window model

- Use the same non-modal `tk.Toplevel` pattern already used by CherryAI dialogs.
- Prefer a shared `open_or_focus()` entry point so reopening `RegEx Maker` focuses the existing window instead of creating duplicates.
- The window must be resizable and should persist geometry through the same window-preference path used by other dialogs.
- Entry point belongs under the existing `Help` dropdown, alongside `Documentation` and `About`.

### Regex compatibility

- Candidate validation must default to the same Python regex engine CherryAI already uses: stdlib `re`.
- Search preview must follow CherryAI's current search behavior: compile with `re.IGNORECASE` and fail safely on invalid patterns.
- Replace preview must follow the same replacement semantics used by CherryAI search/replace: `Pattern.sub()` or `subn()` style replacement with capture-group support.
- Invalid regex must never crash the help window. Invalid candidates are discarded or demoted and shown with an explanation.

### Clipboard and text widgets

- Clipboard operations should use Tk methods already available on widgets and toplevels.
- No external clipboard library is required for copy/paste.
- Multiline input/output should use `Text` widgets or `ScrolledText` when vertical growth becomes awkward.

## User-Facing Scope

### Primary use cases

1. A user pastes several example lines and wants one regex that matches all of them.
2. A user provides matching replacement targets and wants CherryAI to infer capture groups and a regex replacement string.
3. A user does not know regex syntax and instead gives commands such as `whole line`, `ignore spaces`, or `capture number`.
4. A user wants several alternatives, not one opaque guess.

### Non-goals for the first implementation

- It does not need to edit project files directly.
- It does not need to execute replacements across the project.
- It does not need to support multiple regex engines in the first release.
- It should not depend on network access or AI inference.

## Window Layout

### High-level structure

Use a three-band layout:

1. `Top controls`
2. `Example editors`
3. `Candidate output and explanations`

### Top controls

Include:

- `Mode` selector: `Search only`, `Search + Replace`
- `Compatibility` selector: default `CherryAI (re, ignore-case search)`
- `Options` button that opens a structured popup for global constraints
- lightweight `Commands` or `Notes` input only as an advanced fallback, not the primary path
- `Realtime` checkbox, enabled by default
- `Refresh` button for manual rebuild
- `Status` label for validation warnings, debounce state, and candidate counts

### Example editors

Two vertical groups:

#### `Line to find`

- One multiline textbox by default
- `Paste` button beside each textbox
- `Add Line` button below the group
- `Remove` button on rows after the first
- Optional enable/disable checkbox per row for quick experiments
- Text selection inside each row must support right-click actions for marking constants, variable spans, capture groups, ignored spans, and related intent

#### `Replace Target`

- One multiline textbox per active `Line to find` row when replace mode is enabled
- `Paste` button beside each textbox
- Same add/remove pairing behavior as the `Line to find` list
- Hidden or disabled in `Search only` mode
- Replace rows should support the same selection and inspection behavior when replacement mapping needs to be clarified

### Output area

Four panes or stacked sections:

1. `RegEx Search`
2. `RegEx Replace`
3. `RegEx Candidates`
4. `Why this is ranked here`

Behavior:

- `RegEx Search` is read-only and has a `Copy` button.
- `RegEx Replace` is read-only and has a `Copy` button.
- `RegEx Candidates` shows ranked candidates in a selectable list.
- Selecting a candidate updates the `RegEx Search`, `RegEx Replace`, stats, and rationale panes.
- Double-clicking a candidate should copy the search regex, not execute anything.

### Selection-first interaction model

The help window should prefer direct manipulation over typed instructions.

Primary flow:

1. User pastes example lines.
2. User highlights a span in one or more example boxes.
3. User right-clicks to open a context menu.
4. User chooses an intent such as `Mark as constant`, `Mark as variable`, or `Capture this span`.
5. The span remains visually marked and influences candidate generation immediately.

Fallback flow:

1. User clicks `Options`.
2. A small popup window exposes tickboxes, dropdowns, and short help text for constraints that cannot be attached to one specific selected span.
3. The chosen option is reflected back into the example views, candidate scoring, and hover summaries.

### Persistent visual annotations

Any span the user marks must remain visibly determined until the user changes or clears it.

Required behavior:

- Determined spans remain highlighted after the selection is cleared.
- Different intent types use different colors.
- Hovering a highlighted span shows the active meaning and any related scope, for example `Constant across all examples` or `Capture group candidate`.
- Recomputing candidates must not discard the user-marked state.
- Candidate changes may refine interpretation, but must not silently erase explicit user markings.

## Functional Requirements

### Task 1. Window shell

- Non-locking `RegEx Maker` window
- Resizable
- Single-instance reuse via `open_or_focus()` style behavior
- Theme application through the existing CherryAI theme/window helpers

### Task 2. Help menu integration

- Add `RegEx Maker` entry under `Help`
- Reopen focuses existing window if already open

### Task 3. `Line to find`

- Flexible multiline textbox
- `Paste` button per row
- Add/remove rows dynamically
- Right-click context menu on selected text
- Persistent visual overlays for marked spans

### Task 4. `Replace Target`

- Flexible multiline textbox
- `Paste` button per row
- Add/remove rows in sync with search rows when replace mode is active
- Right-click context menu on selected text when replacement structure needs to be clarified

### Task 5. `RegEx Search`

- Read-only multiline output
- `Copy` button
- Always reflects the currently selected candidate

### Task 6. `RegEx Replace`

- Read-only multiline output
- `Copy` button
- Empty when the selected candidate has no confident replace mapping

### Task 7. Dynamic row management

- `Add Line` creates a new example row
- `Remove` deletes only that row
- At least one search row must remain
- Replace rows remain index-aligned with search rows

### Task 8. Shared search inference

- Infer one regex that matches every enabled `Line to find`
- Show multiple candidates, not a single result
- Rank candidates using deterministic scoring
- Print the selected candidate into `RegEx Search`

### Task 9. Replace inference

- Infer a replacement string when `Replace Target` rows are supplied
- Use capture groups when possible
- Print the selected replacement pattern into `RegEx Replace`
- Explain when no reliable replacement can be inferred

### Task 10. User guidance

- Replace most typed commands with selection-based context actions
- Provide a structured popup for non-selection constraints
- Keep any remaining typed commands as an advanced fallback only
- Validate all user guidance early and display unsupported actions inline
- User guidance must bias the generator without silently changing compatibility mode

### Task 11. Context menu actions

- Right-clicking a non-empty selection opens a context menu tailored to the current mode
- Menu actions should cover the most common span-level intents without requiring regex knowledge
- Applying an action must immediately create a persistent colored annotation
- The same intent should be reversible through either the same menu or a `Clear annotation` action

### Task 12. Options popup

- `Options` button opens a small non-modal popup or lightweight dialog
- Popup uses tickboxes, dropdowns, and brief tooltips instead of freeform text where practical
- Popup covers global rules that do not attach cleanly to one selected span
- Closing and reopening the popup should preserve current state

### Task 13. Hover and color semantics

- Every determined span must expose its current setting through hover text
- Colors must remain stable by annotation type so users learn the visual language quickly
- Highlight state must survive candidate refreshes, selection changes, and mode switches

## Suggestion Engine Design

### Core principle

The help window should not generate regex from scratch in one pass. It should build a small set of candidate families, validate them against all examples, score them, then present the best-ranked survivors.

### Suggested backend stages

#### Stage 1. Collect active examples

- Read enabled `Line to find` rows
- Trim trailing newline artifacts from `Text` widgets
- Keep internal raw values exactly as entered otherwise
- Drop completely empty rows from inference, but keep them visible in the UI

#### Stage 2. Parse user guidance

- Normalize user guidance from three sources:
	- span annotations created from the context menu
	- global options selected in the popup
	- optional advanced typed commands
- Build a `RestrictionProfile`
- Reject contradictory guidance with a visible warning

#### Stage 3. Derive shared structure

For each example set, detect:

- common prefixes
- common suffixes
- varying spans
- repeated delimiters
- whitespace variance
- digit variance
- word variance
- bracket or quote symmetry
- full-line similarity versus substring similarity
- explicit user-marked constants
- explicit user-marked variable spans
- explicit user-marked capture spans

#### Stage 4. Generate candidate families

Minimum families for the first design:

1. `Escaped literal`
2. `Anchored escaped literal`
3. `Whitespace-flex literal`
4. `Digit wildcard`
5. `Word wildcard`
6. `Delimited capture`
7. `Prefix + capture + suffix`
8. `Repeated token capture`
9. `Whole line strict`
10. `Search-only fallback generalization`

Examples:

- `Hero_01`, `Hero_02`, `Hero_15` -> `Hero_\d+`
- `Name: Alice`, `Name: Bob` -> `^Name:\s*(.+)$`
- `【町】`, `【城】` -> `^【(.+?)】$`
- `HP 100`, `HP 150`, `HP 999` -> `^HP\s+(\d+)$`

#### Stage 5. Validate candidates

For each generated candidate:

- compile with stdlib `re`
- apply CherryAI-compatible search flags
- ensure every example matches
- collect captures and spans
- ensure the candidate honors explicit span annotations before ranking it highly
- reject unstable candidates

#### Stage 6. Infer replacement candidates

When replace targets exist:

- align each search example with its replace target
- determine which parts are constant and which map to captured spans
- emit replacement strings such as `\g<1>` or `prefix\g<1>suffix`
- reject any replace candidate that depends on ambiguous or inconsistent capture mapping

#### Stage 7. Score and rank

Each candidate receives a score such as:

$$
score = coverage + replace\_confidence + simplicity + readability + annotation\_fit + command\_fit - overmatch\_risk - complexity\_penalty
$$

Recommended scoring priorities:

- `coverage`: must match all enabled examples
- `replace_confidence`: required for strong replace ranking
- `simplicity`: prefer escaped literals and small capture sets over noisy patterns
- `readability`: prefer output a human can reuse in CherryAI settings
- `annotation_fit`: strongly boost candidates that obey explicit user-marked span intent
- `command_fit`: boost candidates that obey explicit user commands
- `overmatch_risk`: penalize `.*`-heavy patterns without anchors or delimiters
- `complexity_penalty`: penalize lookarounds, nested alternation, or too many groups in early candidates

#### Stage 8. Explain ranking

Every candidate should surface one short reason block, for example:

- `Rank 1 because it matches all examples, captures only the varying number, and stays anchored to the full line.`
- `Rank 2 because it also matches all examples, but it is broader and may overmatch unrelated lines.`
- `Rank 3 because it requires a greedy wildcard and has lower replace confidence.`

## Replace Inference Rules

### Replace candidate requirements

A replace suggestion should only be shown when all of the following are true:

- every search example has a paired replace example
- the paired rows can be explained by one shared capture layout
- the replacement can be expressed with CherryAI-compatible replacement syntax

### Replace patterns to support first

1. `Pure passthrough capture`
2. `Prefix/suffix wrap around capture`
3. `Reordered fixed capture groups`
4. `Delimiter-preserving replacement`

Examples:

- Search lines: `Name: Alice`, `Name: Bob`
- Replace lines: `Character: Alice`, `Character: Bob`
- Search regex: `^Name:\s*(.+)$`
- Replace regex: `Character: \g<1>`

Examples:

- Search lines: `【Alice】`, `【Bob】`
- Replace lines: `<Alice>`, `<Bob>`
- Search regex: `^【(.+?)】$`
- Replace regex: `<\g<1>>`

### When not to infer replace

Do not emit a confident replace candidate when:

- replacement requires semantic rewriting instead of structural mapping
- one search row maps to multiple different structural transforms
- alignment only works with a broad wildcard and no stable boundaries

In that case, show:

- search candidates normally
- blank replace field
- explanation such as `No stable shared replacement pattern could be inferred from the supplied pairs.`

## Context Actions And Options Design

### Purpose

Selection actions and structured options give non-regex users a way to shape the candidate list without typing regex syntax.

### Recommended context menu actions

Use selection-based actions first whenever the user can highlight a relevant span.

Recommended actions:

- `Mark as constant`
- `Mark as variable` -> `Word` | `Number` | `Any` | `Japanese`
- `Capture this span`npx skills add JuliusBrussee/caveman -a github-copilot
- `Use as capture group 1`
- `Use as capture group 2`
- `Ignore this span`
- `Treat as optional`
- `Must match literally`
- `Prefer digits`
- `Prefer word characters`
- `Preserve punctuation here`
- `Clear annotation`

### Recommended options popup controls

Use tickboxes, dropdowns, and short labels for global settings such as:

- `Match whole line`
- `Ignore spaces`
- `Ignore leading spaces`
- `Ignore trailing spaces`
- `Case sensitive`
- `Prefer simple regex`
- `Prefer strict regex`
- `Allow wildcard fallback`
- `Disallow lookaround`
- `Disallow backreferences`
- `Require replace suggestion`
- `Maximum candidate count`

### Advanced fallback command style

If a typed command area remains, keep it secondary and limited to advanced fallback input using short phrases such as:

- `whole line`
- `literal`
- `ignore spaces`
- `ignore leading spaces`
- `ignore trailing spaces`
- `capture number`
- `capture word`
- `capture inside quotes`
- `capture inside brackets`
- `preserve punctuation`
- `prefer simple`
- `prefer strict`
- `must start`
- `must end`
- `case sensitive`
- `allow wildcard`
- `no wildcard`
- `no lookaround`
- `no backreference`
- `search only`
- `replace required`
- `max candidates 5`

### Internal command categories

- `Anchoring`
- `Whitespace policy`
- `Capture policy`
- `Complexity limits`
- `Matching strictness`
- `Output count`
- `Replace requirements`

These categories should now primarily be driven by:

- context-menu annotations for span-local intent
- popup options for global intent
- typed fallback commands only when neither of the above fits

### Interaction behavior rules

- Context-menu annotations constrain ranking first and generation second.
- Popup selections constrain ranking first and generation second.
- Typed fallback commands must never override explicit annotations silently.
- User guidance must never silently output a regex incompatible with CherryAI's default search behavior.
- Unsupported typed commands or impossible annotation combinations remain visible as warnings so users understand why a request was ignored.

### Tooltip and hover rules

- Every context-menu action and popup control should expose a short tooltip.
- Hover text over a highlighted span should state:
	- the current setting
	- whether it is local or global
	- whether it affects search, replace, or both
- Tooltip phrasing should stay novice-readable and avoid raw regex jargon unless necessary.

## Real-Time Update Design

### Responsiveness target

- Updates should feel immediate for normal usage.
- A practical target is one recalculation after a short debounce instead of recalculating on every keystroke.

### Recommended strategy

- Use `after_cancel()` and `after()` debounce on text edits.
- Debounce interval: about `120-200 ms`.
- Reuse compiled or normalized candidate fragments where possible.
- Recompute only from active rows, current commands, and current mode.

### Threading policy

- Do not use background threads for the first version if candidate generation remains lightweight.
- Tk event handlers must stay fast; if later pattern generation becomes expensive, move only backend computation off the UI thread and marshal results back via `after()`.

### Cache opportunities

Cache by a hash of:

- active `Line to find` values
- active `Replace Target` values
- normalized annotation state
- normalized popup option state
- normalized fallback command profile
- compatibility mode

## Extensibility Requirements

### Keep GUI and inference separate

The window should remain a thin Tk layer over a reusable backend. The backend should own:

- annotation normalization
- candidate generation
- validation
- scoring
- explanation text
- replace inference
- command parsing

### Suggested internal data model

#### `RegexExampleSet`

- search rows
- replace rows
- mode
- span annotations
- popup option state
- command profile
- compatibility profile

#### `RegexCandidate`

- search pattern
- replace pattern
- score
- family
- explanation
- warnings
- flags used for validation
- capture summary
- sample spans

#### `RestrictionProfile`

- anchoring rules
- capture rules
- wildcard rules
- whitespace policy
- complexity limits
- replace requirements

#### `SpanAnnotation`

- row id
- text range
- annotation type
- color key
- scope
- hover label
- optional capture group index

### Extension points that should remain open

- future parser-specific compatibility profiles
- future import from selected CherryAI text rows
- future advanced candidate families
- future fuzzy or approximate matching modes
- future export into preprocessing widgets or search/replace dialogs

## Required Compatibility With Existing CherryAI Functions

The help window must document and implement the following compatibility rule:

`RegEx Maker` is a helper that proposes patterns, but the final candidate validation must match the regex rules already used in CherryAI's current Python implementation.

That means:

- stdlib `re` is the default engine
- invalid patterns are handled safely
- search candidates are tested with CherryAI-compatible search flags
- replacement strings use Python replacement semantics compatible with `re.sub()` / `Pattern.sub()`

This is important because users will expect a regex copied from the help window to behave the same way inside existing CherryAI functionality.

The same rule applies to user guidance: a context-menu action such as `Capture this span` or `Mark as constant` must only steer candidates toward regex that still behaves correctly under CherryAI's actual runtime semantics.

## Non-Standard Library Assessment

### No non-standard library required for core scope

The following features can and should be implemented with stdlib plus existing Tk:

- non-modal help window
- menu integration
- copy/paste
- multiline textboxes
- add/remove example rows
- real-time debounced updates
- regex compilation and validation
- search candidate inference from deterministic heuristics
- replacement inference for stable capture mappings
- candidate ranking with custom scoring

Required built-in modules are sufficient:

- `tkinter`
- `tkinter.ttk`
- `tkinter.scrolledtext` if desired
- `re`
- `dataclasses`
- `enum`
- `functools`
- `collections`
- `typing`

### Optional library: `regex`

The third-party `regex` package is only needed if CherryAI later decides to support advanced features that stdlib `re` does not provide well enough, such as:

- fuzzy matching for approximate example alignment
- partial matching for live pattern construction
- operation timeouts on dangerous patterns
- richer Unicode properties and grapheme-aware matching
- overlapped matches
- variable-length lookbehind beyond stdlib restrictions

Important constraint:

- `regex` should not replace stdlib `re` for default CherryAI-compatible output unless CherryAI explicitly introduces a new compatibility mode.
- It is acceptable only as an optional advanced engine or an internal research/ranking tool.

### Optional library: `RapidFuzz`

`RapidFuzz` is not required for the first implementation.

It becomes useful only if later ranking needs fast approximate string scoring for:

- clustering similar examples
- choosing the best wildcard boundary
- ranking candidates by closeness to user intent when exact heuristics tie

Current recommendation:

- do not depend on `RapidFuzz` initially
- add it only if candidate ranking becomes noticeably weak or slow with pure-Python heuristics

### Libraries that are not needed

- `pyperclip` is not needed because Tk already exposes clipboard access.
- Any AI or network library is not needed for deterministic suggestion generation.
- Parser-specific regex helpers are not needed in the first release.

## Recommended Implementation Order

- [ ] Build the shared non-modal `RegEx Maker` window shell.
- [ ] Add `Help -> RegEx Maker` menu entry.
- [ ] Implement dynamic `Line to find` and `Replace Target` row editors.
- [ ] Implement copy/paste actions for all text areas.
- [ ] Implement backend command parsing and example normalization.
- [ ] Implement selection annotations, context menu actions, and persistent highlight rendering.
- [ ] Implement the structured Options popup with tickboxes and tooltips.
- [ ] Implement search candidate generation and validation.
- [ ] Implement replace candidate inference.
- [ ] Implement scoring, ranking, and rationale messages.
- [ ] Add debounce and lightweight caching.
- [ ] Add focused tests for invalid regex, ranking stability, and replace-group inference.

## Minimum Test Requirements

- invalid regex never crashes the window
- copied search regex equals the selected candidate
- copied replace regex equals the selected candidate
- add/remove rows preserves row alignment
- highlighted span annotations persist after refresh
- hover text reports the correct setting for a highlighted span
- context menu actions change candidate ranking as expected
- popup tickboxes change candidate ranking as expected
- all enabled examples must match the selected search regex
- replace candidate reproduces all supplied replace targets when confidence is marked high
- command restrictions measurably affect candidate ranking
- reopening the window focuses the existing instance

## Summary Decision

For the first robust implementation, CherryAI does not need any new non-standard dependency.

Use stdlib `tkinter` + `re` for the real product path, keep the backend extensible, and treat third-party packages as optional later enhancements only:

- `regex`: optional for advanced matching and safety features
- `RapidFuzz`: optional for future ranking improvements