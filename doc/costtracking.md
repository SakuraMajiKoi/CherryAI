# Ledger Window Redesign

## Goal

Replace the old lifetime-cost draft with a dedicated non-modal `Ledger` window and a
TSV-backed usage ledger.

This redesign keeps Step 4 Costs as the estimator and keeps API Log as the
request-level inspector, but it fully deprecates `user/usage.db` as the persistent
aggregate store.

## New Direction

- The user-facing entry point is `Ledger`, not `Lifetime Cost Tracking`.
- The window stays non-modal and reusable, like API Log and the planned Editor window.
- `user/ledger.tsv` becomes the only primary aggregate store.
- `functions/usage_tracker.py` should be recycled where practical, but its storage backend
	must move from SQLite to TSV.
- `functions/api_log.py` remains the detail source for drill-down and validation.

## Deprecation Rules

### `usage.db`

`user/usage.db` must be treated as legacy input only.

Required behavior for the redesign phase:

1. If `user/usage.db` exists, a one-time migration writes its rows into
	 `user/ledger.tsv`.
2. After migration, new writes must go only to `user/ledger.tsv`.
3. The codebase should stop treating SQLite as the live source of truth.
4. Documentation and tests should describe `usage.db` only as deprecated legacy data.

### `ledger.tsv`

`user/ledger.tsv` becomes the canonical aggregate ledger.

It should be:

- append-friendly
- human-readable
- easy to diff and export
- stable enough for long-lived historical accounting

## Data Sources

Use two layers together:

1. `user/ledger.tsv` as the aggregate ledger.
2. Per-project `.api_log.jsonl` files as the detailed request record.

The Ledger window should aggregate from TSV and use API Log for per-request drill-down.

## Required Columns

The TSV schema should be explicit and versioned in documentation before implementation.

Minimum fields:

- timestamp
- project_name
- provider
- model
- task_type
- status
- input_tokens
- prompt_tokens
- cached_input_tokens
- reasoning_tokens
- output_tokens
- total_tokens
- input_cost
- cached_cost
- output_cost
- total_cost
- estimate_total_cost
- estimate_delta_cost
- request_id or log reference

If a field is not available for a provider, store an empty value rather than inventing one.

## GUI Entry Points

The redesign should add both of these entry points:

- a direct `Ledger` menu-bar button
- a `Ledger` button inside Step 4 Costs

The button text should stay exactly `Ledger`.

## Required Window Behavior

The Ledger window is a historical analytics surface.

It is not:

- a replacement for Step 4 Costs
- a replacement for API Log
- a provider billing dashboard

It is:

- a lifetime ledger across projects and task types
- a sortable analytics table
- a summary of actual spend and token mix
- a bridge between estimate and actual spend

## Required Layout

### Summary Band

Show compact totals for:

- Total Cost
- Total Requests
- Total Tokens
- Cached Tokens
- Reasoning Tokens
- Success Rate
- Date Range

### Main Table

Minimum columns:

- Date
- Project
- Task
- Provider
- Model
- Requests
- Input
- Cached
- Reasoning
- Output
- Total Tokens
- Total Cost

### Filters

Required filters:

- Project
- Task Type
- Provider
- Model
- Status
- Date Preset
- Custom Date Range

Date presets:

- Today
- 7 Days
- 30 Days
- This Month
- All Time

### Drill-Down

Selecting a row should show either:

- aggregate details for a grouped row
- matching request entries from API Log for a request-backed row

The preferred deep-dive action is `Show matching requests`, which should reuse the
existing API Log viewer where possible.

## Grouping Modes

The Ledger window should support:

- By Day
- By Project
- By Task
- By Provider
- By Model
- By Project then Day
- Ungrouped Requests

Each grouping must still expose sortable numeric totals.

## Phase Plan

### Phase 1: Storage Redesign Review

Review and approve before implementation:

1. Final TSV schema and column order.
2. Migration behavior from `usage.db`.
3. Policy for legacy-file handling after migration.
4. How request references map from TSV rows to API Log entries.

Implementation tasks for this phase:

1. Port `usage_tracker.py` persistence from SQLite to TSV.
2. Add one-time DB-to-TSV migration.
3. Add TSV read, append, query, and grouping helpers in shared `functions/` code.

### Phase 2: Aggregation Layer Review

Review and approve before implementation:

1. Grouping API shape for GUI and CLI reuse.
2. Estimate-vs-actual comparison semantics.
3. Status normalization across providers.

Implementation tasks for this phase:

1. Add shared aggregation helpers.
2. Merge aggregate TSV rows with API-log detail references.
3. Expose stable filters and summary totals for the GUI.

### Phase 3: Ledger Window Review

Review and approve before implementation:

1. Toolbar layout and filter order.
2. Summary cards and main-table columns.
3. Drill-down actions and API Log handoff.
4. Placement of the `Ledger` button in Step 4 and the menu bar.

Implementation tasks for this phase:

1. Add the non-modal Ledger dialog.
2. Wire the menu-bar and Step 4 `Ledger` entry points.
3. Add refresh, grouping, and request drill-down behavior.

## Test Plan

The redesign should add focused script coverage for:

1. TSV round-trip read/write behavior.
2. One-time migration from `usage.db` to `ledger.tsv`.
3. Aggregation by day, project, task, provider, and model.
4. Cached and reasoning token accounting.
5. Estimate-vs-actual summaries.
6. Menu-bar and Step 4 `Ledger` button wiring.
7. API Log drill-down from selected ledger rows.

## Out Of Scope For First Version

- per-user budgets or alerts
- external billing sync
- multi-user accounting
- manual editing of historical entries

## Documentation Rule

Once implementation starts, all docs should refer to:

- `Ledger` as the window/button name
- `user/ledger.tsv` as the primary aggregate store
- `usage.db` only as deprecated legacy data