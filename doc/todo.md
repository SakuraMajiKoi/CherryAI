CHERRYAI - OUTSTANDING WORK & ROADMAP

Features, Improvements, and Known Tasks

=============================================================================

AI AGENT INSTRUCTIONS
---------------------

CRITICAL ARCHITECTURE PRINCIPLE:
The GUI must NOT contain processing logic. All processing functions belong 
in shared modules (functions/, modi/, formats/) that both CLI and GUI use.

WHEN IMPLEMENTING NEW FEATURES:
- ALL text manipulation → functions/ modules
- ALL pre/post-processing → modi/ plugins  
- ALL file I/O → formats/ handlers
- GUI code → display and user interaction ONLY

DOCUMENTATION CROSS-REFERENCE:
- User features: doc/features.md
- Technical API: doc/technical.md
- Test coverage: doc/tests.md

=============================================================================

TESTING REFERENCE

For comprehensive test documentation, see `doc/tests.md`

**Current Status:** 6329 tests passing (verified Q2 2026 via pytest)

Two test types:
- **Script Test**: pytest unit tests (fast, no LLM)
- **API Test**: 7-stage One_Click_Test (full pipeline with LLM)

Run Script Tests: `python -m pytest CherryAI/dev/ -v --timeout=10`
Run API Test: `python CherryAI.py test`

**Note:** Always use `--timeout` to prevent infinite loops. See `doc/tests.md`.

=============================================================================

MODULE COUNTS (Verified January 2026)

- functions/: 39 modules (+ glossaries/ subfolder with 5 files, + romanization.py, + term_translation.py)
- modi/: 12 processing modes
- formats/: 5 format handlers
- gui/steps/: 10 workflow tabs
- gui/helpers/: 6 adapter modules (mode, analysis, glossary, chunker, prompt, manifest_binding)
- gui/dialogs/: 8 dialog modules (global_options, project_dialog, input_dialog, loading_progress, password_dialog, table_view, patch_editor_view, api_log_view)

=============================================================================

### PERFORMANCE AUDIT: Large WOLF RPG Project Responsiveness
**Priority:** HIGH | **Status:** PARTIALLY COMPLETE | **Effort:** Multi-phase

Goal: Keep the GUI responsive on very large projects while preserving output parity. The current benchmark corpus used the WOLF RPG text folders in `dev/data/` with Shift-JIS input and produced `187200` extracted rows (`last idx = 187199`) across `Evtext`, `Evtext_2`, `Evtext_b`, and `Evtext_kh`. This differs from the earlier `176818` expectation and should be reconciled before future benchmark comparisons rely on one fixed baseline.

**Measured runtime on the current implementation:**
1. Step 0 Input load: `1085.199s` with one progress dialog covering `Loading selected files` -> `Staging Original tree` -> `Saving project`.
2. Historical Open Project manifest load before the manifest-load fast path: `38.649s` with one progress dialog covering `Loading manifest` -> `Applying project` -> `Restoring active step` -> `Finalizing`.
3. Historical tab-enter timings after reopen: Analysis and Information were effectively light; Preprocessing `0.861s` enter / `0.459s` leave; Costs light after removing auto-estimate; Translation previously measured `908.716s`; Postprocessing `1.598s`; QA `1.077s`; Wordwrap `1.781s`; Output remained light.
4. Current verified heavy-tab restore results after the shared lazy-row materialization pass:
  - `Projects/Kano.CherryAI.json`: Step 3 `0.847s`, Step 5 `0.496s`, Step 6 `0.852s`, Step 7 `0.674s`, Step 8 `1.109s`
  - `Projects/wolf_perf_probe.CherryAI.json` (`187200` lines): Step 3 `0.905s`, Step 5 `0.553s`, Step 6 `0.925s`, Step 7 `0.873s`, Step 8 `1.171s`
5. Current verified Open Project timings after the canonical-load fast path and final benchmark fix:
  - `Projects/Kano.CherryAI.json`: current Open Project benchmark reports `2.289s` total with phase breakdown `Loading manifest 1.362s`, `Restoring active step 0.586s`, `Finalizing 0.263s`
  - Saved-step restore benchmark semantics now disable benchmark-only autosave noise, snapshot readiness once after restore, and exit without lingering Python processes
  - Benchmark operating rule: every local benchmark run must go through the hard 60-second external wrapper that captures stdout/stderr and force-kills overruns; raw Python benchmark commands are argument reference only

**Implemented in this pass:**
1. **`gui/steps/input_extract.py` / `gui/dialogs/loading_progress.py`** — One Step 0 progress dialog now spans extraction, staging, and manifest save with safe cancel checks between phases.
2. **`gui/app.py` / `gui/dialogs/loading_progress.py`** — Open Project now uses the same style of responsive progress dialog for manifest load and delays activation until the worker completes successfully.
3. **`gui/steps/input_extract.py`** — Manifest-backed Step 0 restore now keeps file content lazy through `LoadedFile.content_loader` instead of eagerly duplicating all extracted lines into memory on reopen.
4. **`gui/steps/costs.py`** — Entering Costs no longer auto-runs estimation.
5. **`functions/prompt_builder.py` / `gui/steps/costs.py`** — Fixed the shared Costs "Preparing lines" hotspot by caching one combined preserve-pattern CODE_ONLY matcher per pattern tuple and by short-circuiting already-skipped rows before extra placeholder/code-only checks in request formation.
6. **`gui/app.py` / `gui/steps/translate.py`** — Saved-step manifest restore now suppresses app-driven notebook tab-change side effects while the target tab is selected and entered, preventing duplicate `on_enter()` work and mid-restore saves on expensive tabs.
7. **`gui/steps/translate.py`** — Fixed the remaining Step 5 restore hotspot by caching manifest `tl` values once during `_refresh_lines()` and by deferring the grouped status-summary rebuild until Tk is idle instead of blocking passive tab entry on a second whole-project validation sweep.
8. **`gui/components/table.py` + heavy tabs** — Added shared lazy row materialization (`set_lazy_data`) so Preprocessing, Translation, Postprocessing, QA, and Wordwrap keep full backing line state but only build visible filtered `TableRow` objects on passive entry.
9. **Tests / scripts** — Added focused regressions for the matcher cache, Costs skip short-circuit, deferred Translation status summary, shared table batching/versioning after the lazy-row path, plus a synthetic benchmark with verbal timeout behavior, a real-manifest Translation tab-entry benchmark, a real-manifest saved-step restore benchmark, and richer KiriKiri2 CSV custom-column analysis scripts.
10. **`functions/manifest_manager.py`** — Added a canonical v3.2 load fast path so already-normalized large manifests skip redundant locator backfill, sorting, and deep-copy canonicalization during `load()`.

**Verified in this pass:**
1. Focused pytest: `python -m pytest dev/test_request_slicing_fix.py dev/test_estimation_skip.py -q --timeout=20` — `93 passed`
2. Synthetic Costs benchmark: `python dev/benchmark_costs_prepare_lines.py --lines 12000 --patterns 300 --timeout 2.0` — improved from `10.613s` before the fix to `0.075s` after the fix
3. Focused Translation pytest: `python -m pytest dev/test_translation_status_cache.py -q --timeout=20` — `1 passed`
4. Updated Translation pytest: `python -m pytest dev/test_translation_status_cache.py -q --timeout=20` — `3 passed`
5. Real Translation benchmark: `python dev/benchmark_translation_tab_entry.py --manifest Projects/wolf_perf_probe.CherryAI.json --timeout 15` — `2.267s` total after the restore-path fix, within the `15.0s` timeout
6. Focused lazy-row pytest: `python -m pytest dev/test_table_batch_insert.py dev/test_translation_status_cache.py dev/test_app_startup.py -q --timeout=20` — `47 passed`
7. Real saved-step restore benchmarks: `python dev/benchmark_manifest_restore.py --manifest Projects/Kano.CherryAI.json --step {3,5,6,7,8} --timeout 20` and the same for `Projects/wolf_perf_probe.CherryAI.json` — all heavy tabs completed within `1.171s`, with Step 5 on `wolf_perf_probe` now at `0.553s`
8. Manifest-load microbenchmark: `Projects/Kano.CherryAI.json` JSON parse `0.632s`, canonicalization `0.597s` after the canonical fast path (down from `5.941s` before the change)
9. Final usable-idle benchmark semantics: `dev/benchmark_manifest_restore.py` now disables benchmark-only autosave/save-on-close noise on temporary managers, snapshots local restore blockers once after activation, skips in-script Tk teardown, and force-exits after printing results so benchmark runs terminate promptly inside the guarded wrapper
10. CSV analysis artifacts: `temp/kirikiri2_csv_analysis.json` and `temp/kirikiri2_csv_headers.json` generated from `dev/ws/data/csv`; current review found `32` schema groups, `719` custom headers, and notable custom Japanese-content columns such as repeated `.` columns in `edit_randomcomment_2.csv`

**Per-tab current behavior and follow-up tasks:**
1. **Step 0 Input** — Current owner: `gui/steps/input_extract.py` (`_load_selected_paths()`, `_restore_files_from_session()`, `_populate_from_manifest()`). Current behavior: extraction and staging are now covered by one progress dialog; manifest reopen is lazy for Step 0 files. Follow-up: keep file-tree restore count-only by default, stream tree inserts for very large file sets, and avoid preview-wide text materialization until the user selects a file or searches.
2. **Step 1 Analysis** — Current owner: `gui/steps/analysis.py`. Current behavior: tab entry is already light and should stay summary-first. Follow-up: keep analysis results manifest-backed, and if new previews are added, they must not force a full `lines[]` load on passive tab entry.
3. **Step 2 Information** — Current owner: `gui/steps/information.py`. Current behavior: metadata, characters, and code patterns should load without needing line text. Follow-up: preserve this rule explicitly; imports from Analysis should stay summary/data driven instead of touching the full line corpus on tab entry.
4. **Step 3 Preprocessing** — Current owner: `gui/steps/preprocess.py`. Current behavior: passive entry now restores preview state through the shared lazy-row path, so only the visible filtered preview slice is materialized as table rows. Follow-up: keep explicit Apply/Refresh work on the full backing preview state and avoid adding new passive full-corpus summary passes.
5. **Step 4 Costs** — Current owner: `gui/steps/costs.py`. Current behavior: passive entry is now light because estimation is manual, the explicit "Preparing lines" phase is no longer the bottleneck after the shared matcher-cache fix, and model changes now fast-reprice existing counts unless the change crosses the OpenAI tokenizer boundary (OpenAI ↔ Google/Mistral), which correctly triggers a fresh count run. Follow-up: restore saved counts and last estimation summary first, and only gather all source text during explicit Update Counts / Estimate runs.
6. **Step 5 Translation** — Current owner: `gui/steps/translate.py` (`on_enter()`, `_refresh_lines()`, `_get_lines_from_previous_steps()`, `_update_lines_table()`). Current behavior: the catastrophic tab-entry stall is fixed, passive status-summary work is deferred, and the shared lazy-row path means passive entry only materializes the visible page. Current saved-step restore timings: `0.496s` on `Kano` and `0.553s` on `wolf_perf_probe`. Follow-up: keep new restore work off the passive path unless it is strictly visible-page scoped.
  - Open Project teardown rule: once the replacement manifest is active, the previous manager is closed with `save_on_close` disabled so the prior save/discard decision is not overridden during activation cleanup.
  - Live translation persistence rule: completed chunks now queue manifest writes for a translation-scoped `15s` batch flush plus one forced final flush on completion; crash salvage relies on the append-first API log rather than per-chunk full-manifest rewrites.
7. **Step 6 Postprocessing** — Current owner: `gui/steps/postprocess.py`. Current behavior: Processed Lines now uses the shared lazy row path, so passive entry keeps filtered ids but only materializes the visible page. Current saved-step restore timings: `0.852s` on `Kano`, `0.925s` on `wolf_perf_probe`. Follow-up: keep summary/filter work cheap and action-scoped.
8. **Step 7 QA** — Current owner: `gui/steps/qa.py`. Current behavior: QA now restores backing state plus the visible page through the shared lazy row path instead of building a full table-model list up front. Current saved-step restore timings: `0.674s` on `Kano`, `0.873s` on `wolf_perf_probe`. Follow-up: keep future review enrichments action-scoped.
9. **Step 8 Wordwrap** — Current owner: `gui/steps/wordwrap_overwrite.py`. Current behavior: Wordwrap preview now restores through the shared lazy row path, so passive entry keeps filtered row ids and materializes only the visible page until explicit wrap work begins. Current saved-step restore timings: `1.109s` on `Kano`, `1.171s` on `wolf_perf_probe`. Follow-up: keep file/tag filter expansion page-scoped.
10. **Step 9 Output** — Current owner: `gui/steps/output_inject.py`. Current behavior: light on entry. Follow-up: keep it manifest-backed and stream verification/write work during export rather than building whole-project preview caches just to enter the tab.

**Benchmark follow-up tasks:**
1. Reconcile the benchmark corpus so the documented expected final idx matches the actual selected WOLF folders and parser output.
2. Add a repeatable timing script under `dev/` that records Step 0 load, Open Project load, and tab enter/leave timings in one run.
3. Add one repeatable benchmark wrapper that runs the full heavy-tab set (Steps 3/5/6/7/8) in a single invocation and stores comparable timing snapshots without leaving stale redirected child-process handles behind.

=============================================================================

### PERFORMANCE: KiriKiri2 Step 0 Sampled Load Path
**Priority:** HIGH | **Status:** COMPLETE | **Effort:** Multi-phase

Goal: Reduce live Step 0 load overhead on the large `dev/ws` KiriKiri2 corpus without losing manifest parity, while switching day-to-day benchmark iteration to a representative one-file-per-folder sample instead of the full 5,572-file tree.

**Representative benchmark mode:**
1. `dev/benchmark_kirikiri2_input_load.py --sample one-per-folder` now selects one parser-accepted file per folder under `dev/ws`; the current representative set is `321` files with `22,876` extracted lines.
2. The mojibake sentinel still exists in the full corpus at `dev/ws/patch_edp/A_B1h12800+.ks:119`, but the representative sample is not guaranteed to include that exact file.

**Measured sampled benchmark progression (real GUI, `dev/ws`, `KiriKiri2`, one file per folder):**
1. Baseline sampled profile before this pass: `117.730s` total, `progress_update 96.924s`, `_sync_lines_to_manifest 9.350s`, `save 6.786s`.
2. After dialog-side batching only: `99.099s` total, `progress_update 84.320s`, `_sync_lines_to_manifest 7.369s`, `save 4.146s`.
3. After Step 0 driver-side progress batching + staged-refresh gating + deferred initial save: profiled run `93.685s` total, `progress_update 0.000s`, `_sync_lines_to_manifest 6.328s`, `save 0.868s`.
4. Official harness verification: first sampled run `102.096s` total, second sampled run `93.035s` total; both completed within the `180s` timeout.
5. Before the final bulk-load/session slice, the representative hotspot profile still measured `60.114s` total with `_update_step_data 0.042s`, `_build_manifest_line_entries 4.625s`, `_sync_lines_to_manifest 6.298s`, and the Progress sidebar still rebuilding throughout the load.
6. After deferring per-file Step 0 state writes, coalescing session notifications, and priming a rel-path source-text cache for manifest sync: final sampled profile `6.165s` total, `_update_step_data 0.001s`, `progress_panel_refresh 0.178s` across `1` refresh, `_build_manifest_line_entries 0.254s`, `_sync_lines_to_manifest 1.788s`, `save 1.017s`.
7. Final official harness benchmark with parity-safe caching: `6.931s` total (`6.181s` load + `0.750s` settle) within the `180s` timeout.
8. After the parser/staging/save slice, the official sampled benchmark dropped again to `4.905s` total (`4.155s` load + `0.750s` settle) while still matching the earlier sampled baseline manifest.

**Measured full-corpus benchmark progression (real GUI, `dev/ws`, `KiriKiri2`):**
1. Before all changes, the live Step 0 load took `1085.199s` with one progress dialog covering `Loading selected files` -> `Staging Original tree` -> `Saving project`.
2. After the full optimization series through the parser/staging/save slice, the same full-corpus real-GUI run completed in `31.213s` (`30.463s` load + `0.750s` settle) while loading `3,716` files and `154,565` extracted lines.

**Implemented in this pass:**
1. **`gui/dialogs/loading_progress.py`** — Progress dialog refreshes now coalesce visible label/count updates and only force full event processing at coarse checkpoints or forced states instead of repainting for every file.
2. **`gui/steps/input_extract.py`** — Step 0 now batches live file-progress publications through `_maybe_update_load_progress()` so the hot loop no longer calls dialog `update()` for every path.
3. **`formats/parser_base.py` / `formats/LightVN.py` / `gui/steps/input_extract.py`** — Added `ParserScript.requires_staged_refresh`; LightVN opts in because its extraction depends on staged `Original/` context, while KiriKiri2 skips the redundant staged re-extraction pass.
4. **`functions/manifest_manager.py` / `gui/app.py` / `gui/steps/input_extract.py`** — Added `create_new(save_immediately=False)` so Step 0 can keep a live manifest manager and autosave state without writing a throwaway pre-sync manifest; the first real disk write now happens after manifest sync.
5. **`dev/benchmark_kirikiri2_input_load.py`** — Added `--sample one-per-folder` so performance iteration stays representative without needing a full-corpus run for each slice.
6. **`gui/state/store.py` / `gui/steps/input_extract.py`** — Added deferred session notifications plus Step 0 bulk-load state batching so per-file `_update_step_data()` calls no longer fan out into hundreds of Progress sidebar rebuilds while the modal loading dialog is active.
7. **`gui/steps/input_extract.py`** — Step 0 now flushes one final Input step-data update after the batch ends instead of writing session fallback state on every file load.
8. **`gui/steps/input_extract.py` / `functions/manifest_manager.py`** — Manifest sync now fills the temporary rel-path source-text cache directly from staged copy bytes, removing the old extra pre-read before staging while still reusing cached text during `_build_manifest_line_entries()` for parity-safe locator capture.
9. **`gui/steps/input_extract.py`** — `_load_file()` now routes through `_extract_file_content()` so parsers with `extract_tagged()` can return text, tags, and locator metadata in one pass instead of making a separate tag-extraction call after line extraction.
10. **`functions/manifest_manager.py`** — The compact manifest writer now formats already-normalized subtrees without renormalizing every nested dict/list on the way down, trimming redundant serializer work in large saves while preserving manifest output shape.
11. **`functions/manifest_manager.py` / `gui/steps/input_extract.py`** — Step 0 now keeps valid zero-line files in both staged `Original/` and manifest `filedir` as `misc` entries with `line_count: 0` and no bounds, and manifest reopen restores those empty-span files instead of silently dropping them.
12. **`dev/compare_manifest_filedir.py`** — Added a reusable Step 0 coverage script that compares manifest `filedir` against a source tree, summarizes included/excluded/zero-line files by extension, and can diff the generated set against a reference manifest.

**Verified in this pass:**
1. Focused pytest: `python -m pytest dev/test_input_step_improvements.py::TestLoadProgressBatching dev/test_autosave.py::TestAutosaveProjectLifecycle::test_create_new_can_defer_initial_save dev/test_lightvn_fixes.py::TestStagedRefreshCapability -q --timeout=10` — `5 passed`.
2. Official sampled parity check: `python dev/validate_manifest_parity.py --baseline temp/kirikiri2_sample_probe_a.json --candidate temp/kirikiri2_sample_probe_b.json` — manifests matched after normalizing volatile fields.
3. Final targeted Step 0 regressions: `python -m pytest dev/test_input_step_improvements.py -q --timeout=20 -k "BulkLoadStateBatching or ManifestEntryBuildCaching or SessionNotificationDeferral or LoadProgressBatching"` — `7 passed`.
4. Final official sampled benchmark: `python dev/benchmark_kirikiri2_input_load.py --source dev/ws --format KiriKiri2 --sample one-per-folder --project-name kirikiri2_sample_probe --launch-gui --save-manifest temp/kirikiri2_sample_after_bulk_state_final.json --timeout 180` — `6.931s` total.
5. Final sampled parity check: `python dev/validate_manifest_parity.py --baseline temp/kirikiri2_sample_probe_a.json --candidate temp/kirikiri2_sample_after_bulk_state_final.json` — manifests matched after normalizing volatile fields.
6. Final parser/staging/save regressions: `python -m pytest dev/test_input_step_improvements.py dev/test_manifest_filedir.py -q --timeout=20 -k "extract_file_content_uses_tagged_extraction_as_single_pass or copy_can_capture_source_text_cache or ManifestEntryBuildCaching or BulkLoadStateBatching or SessionNotificationDeferral"` — `7 passed`.
7. Final sampled benchmark for this slice: `python dev/benchmark_kirikiri2_input_load.py --source dev/ws --format KiriKiri2 --sample one-per-folder --project-name kirikiri2_sample_probe --launch-gui --save-manifest temp/kirikiri2_sample_after_slice_same_name.json --timeout 180` — `4.905s` total.
8. Final sampled parity for this slice: `python dev/validate_manifest_parity.py --baseline temp/kirikiri2_sample_probe_a.json --candidate temp/kirikiri2_sample_after_slice_same_name.json` — manifests matched after normalizing volatile fields.
9. Sentinel verification on the full corpus: `dev/ws/patch_edp/A_B1h12800+.ks:119` still contains `ま、確かにこれから景色でも眺めながら、しみじみと話したかった気もする。`.
10. Real Omega Kano Step 0 benchmark: `python dev/benchmark_kirikiri2_input_load.py --source dev/kanotsuku2/ws2 --format KiriKiri2 --project-name omega_input_probe --save-manifest temp/omega_input_probe.CherryAI.json --timeout 1200` — `3603` loaded files, `147348` extracted lines, sentinel found, `153.728s` total.
11. Real Omega Kano coverage compare: `python dev/compare_manifest_filedir.py --manifest temp/omega_input_probe.CherryAI.json --root dev/kanotsuku2/ws2 --format KiriKiri2 --reference Projects/OmegaKano.CherryAI.json` — `0` missing Step 0 candidates, `425` retained zero-line entries (`357 .ks`, `46 .tjs`, `22 .csv`), and `426` generated-only files relative to the older reference manifest.
10. Final full-corpus benchmark: `python dev/benchmark_kirikiri2_input_load.py --source dev/ws --format KiriKiri2 --project-name kirikiri2_full_probe --launch-gui --save-manifest temp/kirikiri2_full_after_slice.json --timeout 1800` — `31.213s` total.
11. Final full-corpus parity check: `python dev/validate_manifest_parity.py --baseline temp/kirikiri2_full_after_slice.json --candidate temp/kirikiri2_full_after_slice_b.json` — manifests matched after normalizing volatile fields.

**Remaining follow-up:**
1. Any further Step 0 gains will likely need deeper parser-specific extraction work or a manifest-save format change; the major GUI/state/staging overheads are no longer the controlling cost on the current KiriKiri2 path.

=============================================================================

### BUG FIX: KiriKiri2 MainWindow Wordwrap Patch For Stock KAG Variant
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Make `formats/KiriKiri2.py` patch real stock `MainWindow.tjs` files so Kirikiri/KAG message wrapping switches from per-character behavior to per-word behavior, including the verified Shift-JIS `MainWindow.tjs` fixture in `dev/data/system/`.

**Root Causes:**
1. `_patch_add_wrap_block()` only looked for the simplified `if(current.processCh(text))` form, so it missed stock KAG handlers that use `repage = current.processCh(text, chUserMode ? acs : 0);`.
2. The live `_WRAP_BLOCK_SNIPPET` only inserted a stub marker/reset block and never injected the actual tokenization, quote-attachment, width-check, and `processReturn()` logic needed for word-based wrapping.
3. `_patch_add_wrap_vars()` anchored too narrowly, which was brittle outside minimal fixtures.
4. A later broken injection could leave literal `\t` escape text at the start of the inserted TJS block, producing a `文法エラーです(syntax error)` launch failure instead of valid script indentation.
5. Regex-based block replacement originally passed `_WRAP_BLOCK_SNIPPET` directly to `re.sub(...)`, so backslashes in TJS string literals were interpreted as replacement escapes and collapsed `\\`, `\t`, `\n`, and `\r` into malformed source text such as `if(ch != '\')`.

**Changes:**
1. **`formats/KiriKiri2.py`** — Replaced the stub `MainWindow.tjs` wrap block with the full word-tokenizing logic already documented in the repo reference, updated `_patch_add_wrap_block()` to target the real `ch : function(elm)` layouts used by stock KAG `MainWindow.tjs`, and made `_patch_add_wrap_vars()` prefer class-scope insertion with a fallback for minimal fixtures.
2. **`formats/KiriKiri2.py`** — Fixed the generated block so it writes real indentation into `MainWindow.tjs` instead of literal `\t` escape text, replaces stale or malformed existing wrap blocks in-place, and uses function-based regex replacement so literal TJS escape source (`\\`, `\t`, `\n`, `\r`) survives patching unchanged.
3. **`dev/test_parser_scripts.py`** — Added regressions that read the real `dev/data/system/MainWindow.tjs` fixture via `_read_text_with_bom()`, verify the word-based wrap logic, verify the repaired literal backslash/control-character lines, confirm cp932 round-trip, and verify that malformed escaped or malformed in-place legacy blocks are rewritten into one valid block.
4. **Quick verification** — Applied `KiriKiri2Parser.post_inject_project(Path("dev"))` to the real fixture and confirmed `encoding cp932`, no literal `\t` escape marker, canonical backslash/control-character literals present, inserted wrap vars, inserted `splitLine[wrapNum]` logic, inserted `processReturn()` overflow handling, and preserved Japanese text such as `KAG のウィンドウ クラス`.

**Tests:**
- `python -m pytest dev/test_parser_scripts.py dev/test_source_root.py -k "mainwindow or kirikiri_hook_patches_mainwindow" -q --timeout=20` — 4 passed

### BUG FIX: KiriKiri2 Choice + SaveLocation + System Menu Literal Extraction
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Extend `formats/KiriKiri2.py` so Taisho/KAG scenario choices, chapter/save-location titles, and hardcoded system-menu captions can be extracted, translated, and injected safely while preserving Shift-JIS source files.

**Root Causes:**
1. The `.ks` parser only emitted dialogue/narration blocks, so visible `[seladd text="..."]` choices and `*label|title` chapter/save-location titles never reached the translation pipeline.
2. The `.tjs` parser only handled `Menus.tjs` `MenuItem` literals, so real system-menu captions stored as `caption:"..."` in files such as `data/sysscn/Override.tjs` were invisible to extraction and injection.
3. The first literal extractor draft filtered choice/title/caption rows to Japanese-only text, which would have hidden already translated English payloads on later parser passes.

**Changes:**
1. **`formats/KiriKiri2.py`** — Added source-ordered `.ks` literal extraction/injection for `[seladd text="..."]` (`choice`) and `*label|title` (`SaveLocation`) alongside the existing dialogue/narration block path.
2. **`formats/KiriKiri2.py`** — Added generic `.tjs` `caption:"..."` extraction/injection for visible menu captions in files such as `Override.tjs`, while preserving the dedicated `Menus.tjs` path.
3. **`formats/KiriKiri2.py`** — Relaxed the new literal extractors so non-empty translated English payloads still round-trip on re-extraction instead of being dropped by a Japanese-only gate.
4. **`dev/test_parser_scripts.py`** — Added focused regressions for `.ks` choice/save-location extraction and injection, generic `caption:"..."` injection, and real `Override.tjs` menu caption extraction.
5. **Local verification artifact** — Generated a reproducible local patch mirror under `temp/taisho_patch/patch/` with translated `dev/update/scenario` choice/save-location rows, translated `dev/data/sysscn/Override.tjs` menu captions, and a patched `system/MainWindow.tjs` for manual external staging.

**Tests:**
- `python -m pytest dev/test_parser_scripts.py -k "KiriKiri2Parser and (choice or save_location or Override or caption)" -q --timeout=20` — 4 passed
- `python -m pytest dev/test_parser_scripts.py -k "KiriKiri2Parser" -q --timeout=20` — 23 passed

### BUG FIX: KiriKiri2 Kano2 Speaker Variables + Dialog Calls + CSV Extraction
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Extend `formats/KiriKiri2.py` so the Kano2 sample in `dev/ws/` parses real `@talk name=[SF]` speakers, code-heavy dialog-manager `.tjs` literals, and KiriKiri-style `.csv` sheets without loading the whole project into memory.

**Root Causes:**
1. The `.ks` parser only treated `【speaker】` rows as speakers, so real Kano2 `@talk name=[SF]` blocks were downgraded to narration and no valid speaker tokens were extracted.
2. Generic `.tjs` parsing only handled menu captions, so dialog-manager strings embedded in calls such as `SetYesNo("...")` and `SetOK("...")` were invisible when surrounded by code.
3. KiriKiri2 had no parser-owned `.csv` path, so Kano2 data sheets stayed outside the engine-aware parser surface and there was no header-level whitelist to protect IDs, file references, jumps, flags, and numeric-only columns.

**Changes:**
1. **`formats/KiriKiri2.py`** — Added `@talk` command parsing so `name=[SF]` keeps the bracketed variable token as the speaker, while bare `@talk` still opens the following text block without inventing a fake speaker.
2. **`formats/KiriKiri2.py`** — Added dialog-call `.tjs` extraction/injection for `SetYesNo("...")`, `SetOK("...")`, `SetMessage("...")`, and `SetError("...")` special cases, preserving the surrounding function-call code.
3. **`formats/KiriKiri2.py`** — Added schema-based `.csv` support with header-level whitelist rules, column-by-column extraction order, UTF-8/Shift-JIS detection, and surgical cell injection that leaves excluded control columns untouched.
4. **`dev/test_parser_scripts.py`** — Added focused regressions for `@talk name=[SF]` extraction/injection, dialog-manager `.tjs` literals, CSV auto-detection, column-order extraction, and whitelisted-cell-only injection.
5. **`dev/analyze_kirikiri2_csv.py` / `dev/group_kirikiri2_csv_headers.py`** — Added repeatable CSV analysis scripts for per-column profiling and header-signature grouping across `dev/ws/data/csv`.
6. **Local verification artifacts** — Wrote analyzer outputs to `temp/kirikiri2_csv_analysis.json` and `temp/kirikiri2_csv_headers.json` for the Kano2 sample set.

**Tests:**
- `python -m pytest dev/test_parser_scripts.py -k "parses_talk_name_variable_speakers or preserves_talk_name_variable_speaker_lines or detect_parser_for_tjs_dialog_calls or extract_and_inject_tjs_dialog_literals or detect_parser_for_kirikiri_csv or reads_whitelisted_csv_columns_in_column_order or updates_whitelisted_csv_cells_only" -q --timeout=20` — 7 passed
- `python dev/analyze_kirikiri2_csv.py dev/ws/data/csv > temp/kirikiri2_csv_analysis.json` — completed
- `python dev/group_kirikiri2_csv_headers.py dev/ws/data/csv > temp/kirikiri2_csv_headers.json` — completed

### FEATURE: KiriKiri2 DialogMGR `.ks` Literals + `.mdat` Key Whitelist
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Extend `formats/KiriKiri2.py` so code-heavy `.ks` `window.DialogMGR` calls expose visible quoted UI text, including concatenated `SetYesNo(...)` suffixes, and so `.mdat` files can extract/inject only parser-whitelisted quoted keys such as `マップ名` and `グレード名`.

**Root Causes:**
1. The existing dialog-manager literal path only covered `.tjs` calls whose first argument started with a string literal, so code-heavy `.ks` lines such as `window.DialogMGR.SetOK("名前が空欄です",false)` and concatenated payloads such as `tmp_str+"||この名前でよろしいですか？"` stayed invisible.
2. KiriKiri2 had no parser-owned `.mdat` path, so quoted map metadata like `"マップ名"=>"歓楽街"` and `"グレード名"=>"歓楽街"` could not be extracted or injected selectively.
3. The new `.mdat` slice needed the same explicit whitelist model as `CSV_ALLOWED_HEADER_TAGS`, because non-text keys vastly outnumber the visible ones.

**Changes:**
1. **`formats/KiriKiri2.py`** — Added a parser-owned `DialogMGR` literal regex that now covers code-heavy `.ks` lines plus `.tjs` calls when the visible payload is a quoted suffix after concatenation, while still skipping non-literal calls such as `SetOK(res.msg, ...)`.
2. **`formats/KiriKiri2.py`** — Routed those `.ks` dialog-manager payloads through the existing `dialog_call` injection path so replacements preserve the original surrounding KAG/TJS code.
3. **`formats/KiriKiri2.py`** — Added `.mdat` detection, encoding support, whitelist-based extraction/injection, and the new `MDAT_ALLOWED_KEYS` mapping so approved keys are easy to expand without broad parser guessing.
4. **`dev/test_parser_scripts.py`** — Added focused regressions for `.ks` dialog-manager payload extraction/injection and `.mdat` whitelist detection, extraction, source-order preservation, and injection.
5. **Real sample probe** — Verified the live Kano2 files with the parser bootstrap: `WF_S_EditMain.ks` now surfaces the expected empty-name dialog rows and `map_init_data1.mdat` extracts four whitelisted values.

**Tests:**
- `python -m pytest dev/test_parser_scripts.py -k "detect_parser_for_tjs_dialog_calls or extract_and_inject_tjs_dialog_literals or detect_parser_for_kirikiri_csv or extract_tagged_reads_whitelisted_csv_columns_in_column_order or inject_to_updates_whitelisted_csv_cells_only or extract_tagged_parses_talk_name_variable_speakers or inject_to_preserves_talk_name_variable_speaker_lines or extract_tagged_reads_only_ui_literals_from_code_heavy_ks_lines or extract_and_inject_dialog_manager_literals_from_code_heavy_ks_lines or detect_extract_and_inject_whitelisted_mdat_keys" -q --timeout=20` — 10 passed
- Real-file parser probe against `dev/kanotsuku2/ws2/data/scene/WF_S_EditMain.ks` and `dev/kanotsuku2/ws2/data/mapd/map_init_data1.mdat` — extracted the expected dialog-name warnings plus 4 whitelisted `.mdat` values

### BUG FIX: KiriKiri2 SelectLayer Choice Overflow Patch
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Make `formats/KiriKiri2.py` patch real stock `SelectLayer.tjs` files so translated KAG choices wrap by word, grow the button height for multiline text, and default to a smaller hidden choice font size while preserving Shift-JIS source files.

**Root Causes:**
1. `KiriKiri2Parser.post_inject_project()` only patched `MainWindow.tjs`, so output staging never touched the real choice-layout script.
2. Stock `SelectLayer.tjs` rendered choice captions as one line with a fixed `selectHeight = 50`, which caused long translated choices to overflow.
3. The stock vertical layout evenly divided the available height by choice count, so variable-height wrapped buttons would overlap without a second layout patch.

**Changes:**
1. **`formats/KiriKiri2.py`** — Added `_patch_select_layer()` plus shared project-script staging helpers so post-inject patching now targets both `MainWindow.tjs` and `SelectLayer.tjs` under either `data/system/` or `system/`.
2. **`formats/KiriKiri2.py`** — Patched `SelectButtonLayer.redraw()` to wrap choice captions by word, measure multiline height from the wrapped caption, and keep the hidden default choice font size at `18` unless the script explicitly sets `elm.size`.
3. **`formats/KiriKiri2.py`** — Patched `SelectLayer.getSelectPositions()` so stacked choice buttons are spaced from their actual heights plus a fixed gap instead of the old equal-slot count layout.
4. **`dev/test_parser_scripts.py`** — Added focused regressions for the real Shift-JIS `SelectLayer.tjs` fixture and for staged output + `.bak` creation through `post_inject_project()`.
5. **Local verification artifact** — Generated patched manual-inspection copies under `dev/tomove/data/system/`, including `MainWindow.tjs`, `MainWindow.tjs.bak`, `SelectLayer.tjs`, and `SelectLayer.tjs.bak`.

**Tests:**
- `python -m pytest dev/test_parser_scripts.py -k "selectlayer_patch_handles_real_shift_jis_variant or post_inject_project_patches_selectlayer_and_creates_backup or mainwindow_patch" -q --timeout=20` — 5 passed

### FEATURE: Step 9 Manual Parser Apply Patches Window
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Surface parser-owned project patch actions from Step 9 through a dedicated `Apply Patches` window instead of relying only on parser-specific hidden hooks, while keeping patch target resolution manifest-backed and reusable across sessions.

**Root Causes:**
1. Step 9 had no manual surface for parser-specific staged-file patches, so users could not selectively apply or reapply parser-owned fixes such as `MainWindow.tjs` or `SelectLayer.tjs` patches.
2. Parser patch metadata (name, description, target file candidates) was not part of the shared parser handshake, so GUI code had nothing canonical to list.
3. Missing staged files had no reusable search flow: if a required file was absent from `Translated/` and `Original/`, CherryAI could not prompt for an external lookup root and remember it.
4. HyperKano-style `MainWindow.tjs` files use `function SetMesText(text) { MesLayer.DrawText(text); }` instead of the stock `processCh` handler, so the earlier KiriKiri2 wordwrap patch could leave those projects unchanged even after the correct file was found.

**Changes:**
1. **`functions/apply_patches.py`** — Added shared Step 9 parser-patch discovery, file search/copy helpers, manifest-backed lookup-folder persistence, per-patch/logged execution, and the modal `Apply Patches` window with `Cancel`, per-patch Apply buttons, and `Apply All Patches` for checked rows.
2. **`formats/parser_base.py` / `formats/handshake.py`** — Extended the parser handshake with manual `project_patches` actions so parsers can advertise name, description, candidate paths, and apply callbacks to Step 9.
3. **`gui/steps/output_inject.py`** — Added the `Apply Patches` button beside `Refresh Preview` and delegated the window launch to the shared Step 9 helper instead of embedding parser-patch logic in the GUI step.
4. **`formats/KiriKiri2.py`** — Advertised `MainWindow Wordwrap Patch` and `SelectLayer Choice Wrap Patch` as parser-owned Step 9 actions, and extended the MainWindow patch with a HyperKano `SetMesText` fallback that injects `__CherryAIWrapMessageText(text)` and rewrites `MesLayer.DrawText(text);` when no stock `processCh` anchor exists.
5. **`dev/test_apply_patches.py` / `dev/test_output_injection.py`** — Added focused regressions for manifest-driven patch discovery, saved lookup-folder reuse, cancel semantics, and the Step 9 launcher entry point.
6. **Live verification** — Applied the KiriKiri2 MainWindow patch against `Projects/HyperKano.CherryAI.json`, confirmed the first pass fails cleanly when the file is absent from staged roots, confirmed the lookup search resolves `dev/ws2`, copied the file into `Projects/HyperKano/Translated/data/system/MainWindow.tjs`, created `.bak`, rewrote the HyperKano `SetMesText` call, and persisted the lookup folder in the manifest.

**Tests:**
- `python -m pytest dev/test_output_injection.py dev/test_apply_patches.py dev/test_source_root.py -k "open_apply_patches_dialog_calls_shared_launcher or discovers_kirikiri_project_patches or copies_from_original_into_translated_before_patching or uses_saved_lookup_folder_before_prompt or cancelled_folder_selection_cancels_one_patch or kirikiri_hook_patches_mainwindow" -q --timeout=20` — 6 passed

### FEATURE: KiriKiri2 Step 9 Font Patch Workflow
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 session

Goal: Add a parser-owned Step 9 `Font Patch` for KiriKiri2 that stages a reusable `version.dll` runtime, bundled redistributable fonts, and a shared configuration dialog instead of relying on title-specific manual DLL work.

**Root Causes:**
1. The original `Apply Patches` seam only knew how to resolve one staged target file and call `apply_to_target(...)`, so a dialog-driven font/runtime workflow had nowhere canonical to attach.
2. The reusable proxy DLL source existed in the workspace (`KiriKiriTools/KirikiriUnencryptedArchive`) but was not packaged into CherryAI's own `libraries/` tree.
3. Step 9 had no shared way to choose a bundled font family, preview it, write a config, and place the resulting `fonts/` folder next to the patch folder.
4. The sample KiriKiri2 game requested `Segoe UI` at runtime, so the default face aliases had to include that real request before the developer log could prove a concrete substitution.

**Changes:**
1. **`functions/apply_patches.py`** — Extended parser project patches with an optional custom `apply_with_context(...)` runner so dialog-driven workflows can live beside file-target patches.
2. **`functions/kirikiri_font_patch.py`** — Added shared bundled-font discovery, staged layout/config generation, existing-config reload, and the KiriKiri2 Font Patch runner used by Step 9.
3. **`gui/dialogs/kirikiri_font_patch_dialog.py`** — Added the shared modal font patch dialog with family selection, preview labels, height/charset/quality controls, and developer logging toggle.
4. **`formats/KiriKiri2.py`** — Advertised the new parser-owned `Font Patch` action alongside the existing MainWindow and SelectLayer script patches.
5. **`libraries/KiriKiriInjection/`** — Packaged the reusable proxy DLL source tree plus a Python `build_version_dll.py` helper that finds the Visual Studio C++ environment and rebuilds `Release/version.dll` locally.
6. **`libraries/KiriKiriInjection/KirikiriUnencryptedArchive/FontPatch.cpp` / `.h`** — Added a config-driven private font loader + `CreateFontA/W` / `CreateFontIndirectA/W` import hook that logs developer-only runtime diagnostics and rewrites matching requests to the staged replacement face.
7. **`libraries/Fonts/`** — Added recommended redistributable bundles for Inter, Noto Sans, Liberation Sans, and Open Sans with the regular/bold-or-semibold files used by the shared dialog plus the upstream OFL license text.
8. **Live verification** — Built the packaged `version.dll`, staged the Font Patch into `dev/kanotsuku2`, launched `dev/kanotsuku2/xx2.exe`, and confirmed runtime log entries for private font registration and concrete `Segoe UI -> Inter` substitutions.

**Tests:**
- `python -m pytest dev/test_apply_patches.py dev/test_kirikiri_font_patch.py -q --timeout=20` — 7 focused Step 9 / font patch tests passed after parser wiring
- `python libraries/KiriKiriInjection/build_version_dll.py` — packaged `version.dll` build succeeded under Visual Studio 2022

### FEATURE: KiriKiri2 Step 9 Standard UI Translation Patch
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 session

Goal: Add a shared Step 9 patch for KiriKiri2 that stages translated stock menu/help/folder/cache/version UI overlays from real game system files, without bloating the parser surface or requiring a title-specific module.

**Root Causes:**
1. The existing KiriKiri2 parser patches only handled wordwrap/layout/runtime fixes, so stock menu and utility UI strings remained outside the reusable Step 9 patch surface.
2. These strings live in system scripts such as `MenuItemManager.tjs`, `CacheWindow.tjs`, and `VersionWindow.tjs`, often in UTF-16, so naive text rewriting risked mojibake or BOM loss.
3. Standard KiriKiri UI labels include dynamic captions such as `自動選択 [4スレッド]`, so a literal-only replacement table would miss part of the menu tree.
4. The repo instructions for this slice explicitly required keeping parser glue small and reusing `libraries/` rather than introducing a new helper module.

**Changes:**
1. **`functions/kirikiri_font_patch.py`** — Added the shared `stage_kirikiri_standard_ui_translation_patch(...)` workflow plus BOM-preserving read/write helpers, staged-root/external-lookup source resolution, and literal+regex replacement support.
2. **`libraries/KiriKiriInjection/StandardUiTranslations/CherryAI.KiriKiriStandardUiPatch.json`** — Added the library-owned replacement spec for `data/system/MenuItemManager.tjs`, `data/program/CacheWindow.tjs`, and `data/system/VersionWindow.tjs`.
3. **`formats/KiriKiri2.py`** — Advertised `Standard UI Translation Patch` as a parser-owned Step 9 shared workflow through `project_patches`.
4. **`dev/test_kirikiri_font_patch.py` / `dev/test_apply_patches.py`** — Added focused regressions for UTF-16-preserving staged overlays and parser patch discovery including the new patch id.
5. **Local verification artifact** — Ran the shared staging helper against `dev/kanotsuku2/ws2`, producing `dev/kanotsuku2/patch/data/system/MenuItemManager.tjs`, `dev/kanotsuku2/patch/data/program/CacheWindow.tjs`, and `dev/kanotsuku2/patch/data/system/VersionWindow.tjs` for manual game testing.

**Tests:**
- `python -m pytest dev/test_kirikiri_font_patch.py dev/test_apply_patches.py -q --timeout=20` — 12 passed
- Spot check: `Get-Content -Encoding Unicode` confirmed translated `System(&S)`, `View(&V)`, `Image Cache Settings`, `Select Font`, and `Version Info` strings in the staged Kanotsuku2 patch outputs
- Live cleanup follow-up: flattened the accidental active `dev/kanotsuku2/patch/patch/...` mirror into `dev/kanotsuku2/patch/`, archived same-hash/conflicting leftovers plus probe files under `dev/kanotsuku2/_inactive_patch_backups/failed_request_cleanup_20260519/`, staged `map_base_lv1.mdatb` and `map_base_lv2.mdatb` from `dev/kanotsuku2/ws2/patch/`, and confirmed `dev/kanotsuku2/xx2.exe` still stayed up after startup.

### BUG FIX: Editor Theme Refresh `_root()` Collision
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Stop the live Editor window from crashing immediately on open when theme refresh walks the classic-widget tree.

**Root Cause:**
1. `gui/dialogs/patch_editor_view.py` stored the owner toplevel on `self._root`, which shadowed Tkinter's internal `_root()` widget helper.
2. `gui/theme/colors.py::apply_theme()` calls `winfo_children()` while traversing classic widgets, and Tkinter's child/widget resolution path calls `_root()` / `nametowidget()` internally.
3. Once `_root` had been replaced with the `App` instance, opening Editor raised `TypeError: 'App' object is not callable` during theme refresh and later during event substitution/error reporting.

**Changes:**
1. **`gui/dialogs/patch_editor_view.py`** — Renamed the stored owner reference to `_window_root` and kept close-time window deregistration on that safe attribute instead of shadowing Tkinter internals.
2. **`dev/test_patch_editor_view.py`** — Added a regression proving the dialog keeps Tkinter's `_root()` helper callable.
3. **Validation** — Re-ran the focused Editor/App pytest slice and a real dialog smoke test using the repo bootstrap to confirm the Editor window now constructs cleanly.

**Tests:**
- `python -m pytest dev/test_patch_editor_view.py dev/test_app_startup.py -k "PatchEditorDialog or EditorHostOpenOrFocus" -q --timeout=20` — 5 passed
- Smoke test: real `PatchEditorViewDialog(root, mgr)` construction succeeded after bootstrapping `conftest._setup_cherryai_package()`.

### BUG FIX: CherryAI.ini Preset Alias Cleanup + API.ini Key Bridge + Step 6 Crash
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Remove duplicate built-in style/tone preset entries that made strict CherryAI.ini reads fail, stop runtime API warnings from checking stale CherryAI.ini key paths during translation, and fix the Step 6 aggressive-number helper crash on Apply Postprocessing.

**Root Causes:**
1. CherryAI.ini still contained lowercase aliases such as `literal` / `neutral` alongside canonical `Literal` / `Neutral`, and any strict default-`optionxform` reader treated them as duplicate options.
2. Runtime API helper paths still modeled `api_key` as if it lived in CherryAI.ini, while the actual saved-key source of truth had already moved to `user/API.ini`.
3. Step 5 created `APIClient()` before injecting the selected saved key, so the client logged a false "No API key found in configuration" warning even when translation then proceeded normally.
4. `gui/steps/postprocess.py::_reverse_aggr_numbers()` was left as a staticmethod even though it dereferenced `self._lines`, causing the Apply Postprocessing button to fail with `name 'self' is not defined`.

**Changes:**
1. **`functions/ini_manager.py`** — Extended legacy-key normalization to built-in `[style]` / `[tone]` preset aliases so lowercase duplicates are migrated to canonical mixed-case keys and removed on load.
2. **`functions/config.py`** — Switched the canonical runtime config path to `user/CherryAI.ini`, preserved INI key case during reads, and repointed runtime `get_api_config()` / `set_api_config()` to `user/API.ini` while keeping explicit test-file overrides working.
3. **`functions/api_client.py` / `gui/steps/translate.py`** — Added `APIClient(initial_config=...)` and changed Step 5 to construct the client with the already resolved saved key/provider/base URL, eliminating the false missing-key warning.
4. **`functions/common_errors.py`** — API-key validation now checks the canonical runtime API config bridge instead of the old CherryAI.ini secret path.
5. **`gui/steps/postprocess.py`** — `_reverse_aggr_numbers()` is now an instance helper so indexed aggressive-number restoration can read the loaded line set safely during Step 6.
6. **Tests** — Added focused regressions in `dev/test_ini_manager.py`, `dev/test_config.py`, `dev/test_common_errors.py`, `dev/test_api_client.py`, and updated `dev/test_postprocess_phase45.py` for the instance-method helper contract.

**Tests:**
- `python -m pytest CherryAI/dev/test_api_client.py CherryAI/dev/test_ini_manager.py CherryAI/dev/test_config.py CherryAI/dev/test_common_errors.py CherryAI/dev/test_postprocess_phase45.py -k "initial_config_skips_legacy_load_and_missing_key_warning or lowercase_style_and_tone_aliases_migrate_to_canonical_keys or runtime_reads_default_key_from_api_ini or runtime_writes_default_key_to_api_ini or uses_api_ini_default_key_when_validating or AggressiveDedupIndexedRestore" -q --timeout=20` — 6 passed

### BUG FIX: Translation Preview Reopens Finished Projects As Full Runs
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: When loading a nearly finished manifest such as `Projects/TML.CherryAI.json`, make the Translation tab and Preview Requests respect the persisted overwrite-off policy immediately so only the remaining untranslated work is requested.

**Root Causes:**
1. `gui/app.py` created and reset `SessionState` objects without seeding `session.global_options`, so Step 5 had no persisted TranslationSettings until the Global Options dialog was opened manually.
2. `gui/steps/translate.py` used `TranslationOptions.skip_already_translated = False` as its local fallback, which inverted the documented default `overwrite_translation = false` during those startup/load windows.

**Changes:**
1. **`gui/app.py`** — App startup now loads `GlobalOptions` from INI into the session immediately, and `_reset_runtime_state()` preserves that object across project activation so loaded manifests keep the same translation-policy defaults.
2. **`gui/steps/translate.py`** — `TranslationOptions.skip_already_translated` now defaults to `True`, matching the documented overwrite-off behavior when Global Options have not been attached yet.
3. **Tests** — Added regressions in `dev/test_app_startup.py` for Global Options carry-over during project activation and in `dev/test_request_preview.py` for the Step 5 overwrite-off fallback default.

**Tests:**
- `python -m pytest dev/test_request_preview.py dev/test_app_startup.py -q --timeout=20` — 80 passed, 2 skipped

### BUG FIX: Translation Tab Live GUI Restore Loop + Visible Benchmark Coverage
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Reproduce the Translation tab restore bug through the real visible GUI using `Projects/Kano.CherryAI.json`, stop Step 5 from getting trapped in a deferred status-summary rebuild after the window appears, and make the benchmark detect the live GUI path instead of only timing withdrawn widgets.

**Root Causes:**
1. The existing real-manifest restore benchmarks timed withdrawn or activation-only paths, so they missed the live Tk event-cycle where the Translation header's deferred summary actually runs.
2. `gui/steps/translate.py::_get_existing_translation_text()` still re-entered manifest lookup logic on cache misses; when the deferred status summary classified every line after the visible window appeared, untranslated rows could trigger repeated manifest rescans.
3. Live GUI project loading needed its own non-blocking callback path so the benchmark and menu-driven loads could exercise the running Tk event loop without relying on a nested synchronous restore helper.

**Changes:**
1. **`dev/benchmark_manifest_restore.py`** — Added `--launch-gui` mode that starts the real `App` mainloop first, loads a manifest from inside that running event loop, and polls until the restored tab is actually usable instead of only timing a withdrawn restore snapshot.
2. **`gui/steps/translate.py`** — Added a one-time `tl` cache hydration guard so deferred status-summary rebuilds never fall back to per-row manifest lookups after cache misses; the Translation table also restores a smaller first visible page (`500` rows) for the live GUI path.
3. **`gui/app.py`** — Added `_load_manifest_from_path_async()` and routed live GUI manifest loads through it so the running application uses an `after()`-polled worker path while the older synchronous helper remains available for non-mainloop tooling and withdrawn benchmarks.
4. **Tests** — Expanded `dev/test_translation_status_cache.py` for empty-cache and one-time hydration coverage, and `dev/test_app_startup.py` for the new async live GUI loader contract.

**Tests:**
- `python -m pytest dev/test_translation_status_cache.py dev/test_app_startup.py -q --timeout=20` — `35 passed`
- Guarded visible GUI benchmark: `python dev/benchmark_manifest_restore.py --manifest Projects/Kano.CherryAI.json --step 5 --launch-gui --timeout 8 --trace` — reached usable Translation idle in `2.109s`
- Guarded withdrawn benchmark: `python dev/benchmark_manifest_restore.py --manifest Projects/Kano.CherryAI.json --step 5 --timeout 8 --trace` — reached idle in `1.080s`

=============================================================================

### PHASE PLAN: Ledger TSV Migration
**Priority:** HIGH | **Status:** REVIEW FIRST | **Effort:** LARGE

Goal: Replace the old usage database plan with a TSV-backed `Ledger` system.

**Review checklist before implementation:**
1. Approve `user/ledger.tsv` as the only primary aggregate store.
2. Approve one-time migration behavior from legacy `user/usage.db`.
3. Approve the final TSV schema and column order.
4. Approve the `Ledger` entry points: direct menu button plus Step 4 Costs button.

**Implementation tasks after review:**
1. Port or recycle `functions/usage_tracker.py` logic so reads and writes target TSV instead of SQLite.
2. Add one-time migration from `usage.db` into `ledger.tsv` and mark `usage.db` deprecated everywhere.
3. Add shared grouping and filtering helpers in `functions/`.
4. Add the non-modal `Ledger` window and wire both `Ledger` buttons.
5. Keep API Log as the drill-down detail surface.

**Required tests for this phase:**
1. TSV round-trip read/write.
2. One-time DB-to-TSV migration.
3. Grouping by day, project, task, provider, and model.
4. Cached/reasoning-token accounting.
5. Menu-bar and Step 4 `Ledger` button wiring.

### PHASE PLAN: Unified Editor Window
**Priority:** HIGH | **Status:** REVIEW FIRST | **Effort:** LARGE

Goal: Merge Full Table View, Patch Editor, and the workbench draft into one separate non-modal `Editor` window.

Planning note: the active implementation plan for this phase now lives in `doc/editor_pyside6_refactor_plan.md`. The merged Editor should use PySide6 as its primary UI library while preserving the shipped Tk Editor behavior until parity is reached.

**Review checklist before implementation:**
1. Approve the final naming: `Editor`, `Full Files`, and `Lines Only`.
2. Approve the visible switch layout: `Full Files [Switch] Lines Only`.
3. Approve that Patch Editor disappears as a standalone name after migration.
4. Approve that `Lines Only` is the renamed successor to Full Table View.
5. Approve that API Log and Ledger remain separate windows.

**Implementation tasks after review:**
1. Reuse Patch Editor behavior for the `Full Files` mode.
2. Reuse Full Table View behavior for the `Lines Only` mode.
3. Build one single-instance non-modal PySide6 Editor window with shared project/file context.
4. Preserve manifest-aware diffing, parser-backed line history, and search/replace in both modes.
5. Retire menu naming that exposes Patch Editor as a separate destination.
6. Keep the Qt migration Editor-only at first; do not widen the PySide6 rollout to unrelated windows before the Editor is stable.

**Required tests for this phase:**
1. Single-instance Editor reuse.
2. Mode switching between `Full Files` and `Lines Only`.
3. Shared file-selection carry-over across the switch.
4. Search/replace behavior in both modes.
5. Manifest sync and EditorState continuity after the rename.

Current shipped fix before the larger merge: the retained Editor host now guards programmatic file-tree and history-row selection updates so opening the live window cannot spin inside recursive `TreeviewSelect` callbacks. Keep this behavior intact during the unified-window migration.

### PHASE PLAN: Staged Folder And Patch Redesign
**Priority:** HIGH | **Status:** REVIEW FIRST | **Effort:** LARGE

Goal: Redesign staged storage so originals, latest translated files, and patch history are separated cleanly.

**Target directory model:**
1. `Original/` keeps the very first staged source snapshot.
2. `Translated/` keeps the latest translated output.
3. `Patch/Original/` stores forward patches from `Original/`.
4. `Patch/Translated/` stores reverse patches and rollback history for `Translated/`.

**Review checklist before implementation:**
1. Approve that Step 0 copies the entire loaded folder tree into `Original/`, not only files with parseable content.
2. Approve hash-first behavior for patch generation.
3. Approve `same hash = skip`, `different hash = diff or full copy`, `new file = add`.
4. Approve that Editor save and Output both overwrite `Translated/` and first record rollback data in `Patch/Translated/`.

**Implementation tasks after review:**
1. Change staging helpers so the first load mirrors the complete source tree into `Original/`.
2. Route latest full translated files into `Translated/`.
3. Add forward patch generation into `Patch/Original/`.
4. Add reverse patch capture into `Patch/Translated/`.
5. Update `EditorState.files` metadata so it remains aligned with the new directory model.

**Required tests for this phase:**
1. Full-folder copy into `Original/`, including files without parseable lines.
2. Hash-first skip/diff/copy behavior.
3. Editor-save overwrite into `Translated/` plus reverse-patch capture.
4. Output overwrite into `Translated/` plus reverse-patch capture.
5. Manifest and filedir continuity after the new staging layout.

**Follow-on note:**
The old multi-version patch-update workflow should be re-reviewed only after these three phases land, because its conflict model depends on the new Editor naming and the new staged folder layout.

=============================================================================

### BUG FIX: Manifest Bloat From EditorState + Output Lines
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Shrink `.CherryAI.json` manifests by removing redundant persisted caches from `EditorState.files[...]` and `step_state.Output.data.lines`.

**Changes:**
1. **`functions/manifest_manager.py`** — `_stage_translated_bytes()` now persists only the compact `EditorState.files[rel_path]` contract: `saved_at`, staged artifact references, bounded history, and a per-file `changed` flag while Step 9 export is still owed. It no longer serializes `diff_to_patch`, `edited_text`, `diff_to_original`, `line_history`, `locator_metadata`, or `latest_saved_row_state`, and empty-history file records are pruned on load/export.
2. **`functions/manifest_manager.py`** — `get_editor_file_view()` now rebuilds `diff_to_patch` from staged artifacts on demand, including reconstructing the forward-facing editor diff from the Editor-owned reverse patch artifact when necessary.
3. **`functions/manifest_manager.py`** — Added translated-branch backup helpers: `backup_active_translated_branch()`, `discard_active_translated_branch()`, and `restore_translated_branch_backup()`. Backups store artifact-only metadata in `EditorState.backups`, and `backup_active_translated_branch(preserve_active=True)` can snapshot `Translated/` plus `Patch/Translated/` into `Backups/` without removing the live staged files that Step 9 still needs as export input.
4. **`functions/manifest_manager.py`** — `_migrate_manifest()` now strips legacy `step_state.Output.data.lines` plus the removed heavyweight `EditorState.files[...]` keys on load so the next save rewrites compact manifests.
5. **`gui/steps/output_inject.py`** — `_load_from_session()` and `_save_to_session()` now remove the redundant manifest-backed Step 9 `lines` cache instead of persisting it.
6. **`gui/steps/output_inject.py`** — Step 9 now prompts when an active translated branch already exists: export over it in place, snapshot it first without removing the live branch, or cancel the export.
7. **`functions/manifest_manager.py` / pipeline write paths / `gui/steps/output_inject.py`** — Reverse diff artifacts are now Editor-owned only. Successful Step 9 staging writes directly into `Translated/` and clears active `Patch/Translated/` artifacts instead of generating new ones; parser-backed export now re-renders from the manifest pipeline, replays saved editor history onto that fresh render before injection, skips unchanged same-target translated files, and clears the pending `changed` marker on successful export.
The pending `changed` marker is now written only by one shared compare helper, not by generic `set_line_field()` / `set_lines()` calls. The helper is invoked from Input `Load Selected Items` (`orig`), Preprocessing `Apply Rules` (`prepro`), Translation `Start Translation` (`tl`), Postprocessing write actions (`postpro`), QA write actions (`qa_overwrite`), Wordwrap `Apply Wordwrap` (`wordwr`), and Full Table View / Editor saves.
8. **`gui/components/table.py` / `gui/steps/output_inject.py`** — Output export selection now follows checkbox state first, adds a `Select Visible` bulk action for filtered rows, hides the generic table CSV button in Step 9, and supports Shift-range checkbox toggling across the visible rows.
9. **Tests** — Updated the manifest-state assertions to the artifact-only EditorState contract and added regressions for migration cleanup, empty-history pruning, generic-setter non-marking, compare-helper marking for translated files only, input reload `orig` comparison by `rel_path`, first-save replay seeding, Step 9 patch clearing, replay-before-inject export, unchanged-export skip gating, and the new Output-step selection workflow.

**Tests:**
- `python -m pytest dev/test_output_injection.py -q --timeout=20` — 62 passed
- `python -m pytest dev/test_manifest_state.py -k "set_line_field_does_not_mark_changed_without_explicit_tracking or track_output_change_for_field_marks_changed_when_translated_exists or track_output_change_for_replaced_lines_compares_orig_by_rel_path or should_skip_step9_export_uses_translated_presence_and_changed_mark or save_editor_patch_writes_patch_and_updates_editor_state or save_lines_only_changes_synthesizes_patch_when_translated_missing or save_lines_only_changes_promotes_saved_stage_and_updates_translated or save_editor_patch_without_translated_seeds_replay_history or stage_translated_output_file_step9_clears_patch_artifacts or load_prunes_editor_state_files_with_empty_history" -q --timeout=20` — 10 passed

=============================================================================
[Archived: Sessions 43–24 + Phase 62 → see doc/archived.md]

### BUG FIX: LightVN Backlog + Popup Extraction And No Parser Recovery
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Extend the LightVN parser so it can extract/inject backlog choice suffixes and popup-facing `追加項目` text, preserve split dialogue that resumes with bare `-"...` after `~画像` / `~ボイス`, support targeted quoted assignments that span physical lines, and remove parser-side code recovery during injection.

**Root Causes:**
1. LightVN had no dedicated extraction path for `バックログ続く文章追加 "\n\n選択肢 >..."`, so only the whole raw command remained visible to downstream steps instead of the actual translatable suffix.
2. Popup-facing `変数 追加項目 = "..."` payloads were outside the existing variable classifiers and never reached translation.
3. Bare `-"...` lines only worked as continuations of an already-open dialogue block, so command-delimited half-lines after `~画像` / `~ボイス` were skipped.
4. Targeted quoted assignments that spanned multiple physical lines were processed one line at a time and could not round-trip as one payload.
5. LightVN still contained parser-side injection recovery for bracket/code-looking text, which violates the parser contract and could rewrite valid translated payloads such as `[3 items 60G]`.

**Changes:**
1. **`formats/LightVN.py`** — Added dedicated `backlog` and `screenpopup` extraction/injection paths, plus segment-aware menu handling so mixed command lines ignore quoted condition literals but still extract/translate visible `文字*` and `ボタン*` payloads.
2. **`formats/LightVN.py`** — Expanded the targeted-variable family to cover additional requested UI/item fields such as `道具_馬名前`, `料理名`, `料理効果内容`, `釣り結果`, `消費素材*`, and `必要素材名*` while keeping those names out of the generic project-scoped path on the real Uni16 originals.
3. **`formats/LightVN.py`** — Added multiline assignment consumption during extraction, whole-content targeted replacement during injection, and fresh dialogue-start handling for bare `-"...` rows after intervening commands.
4. **`formats/LightVN.py`** — Removed parser-side code/bracket recovery and angle-bracket safety rewrites from injection. The parser now writes translated payloads verbatim and leaves code protection/recovery to preprocessing/postprocessing.
5. **`dev/test_lightvn_parser.py` / `dev/test_lightvn_fixes.py`** — Added and verified regressions for backlog extraction/injection, popup extraction/injection, command-separated `-"` dialogue halves, multiline targeted assignments, no parser-side bracket recovery, menu-segment filtering, and the hardcoded-equipment rewrite path after direct menu translation.
6. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the new LightVN parser behavior and the verified test command.

**Tests:** Focused pytest run passed:
- `python -m pytest dev/test_lightvn_parser.py dev/test_lightvn_fixes.py -q --timeout=20` — 131 passed, 2 skipped

### BUG FIX: LightVN Hardcoded Tag Persistence + Output Newline Guard
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Preserve LightVN parser tags across manifest reloads, mark visible hardcoded machine-value rows for special care, keep `items` as a canonical content tag, and stop trailing manifest newlines from being written or logged during Step 9 output.

**Changes:**
1. **`formats/LightVN.py`** — Added composite `hardcoded` tagging for visible machine-value rows so targeted literals such as `防具_選択中部位 == "頭"` emit `variable,hardcoded` and UI label duplicates emit `menu,hardcoded` while keeping their primary content type.
2. **`functions/manifest_manager.py`** — Promoted `items` into the canonical content-tag set so manifest normalization and reload logic continue to treat item rows as first-class content.
3. **`gui/steps/input_extract.py`** — Restored `LoadedFile.tags` from manifest `lines[].tags` when reopening projects, so parser-provided tags survive Step 0 rehydration.
4. **`gui/steps/preprocess.py`** — Step 3 now preserves parser/content tags already stored in `lines[].tags` and merges preprocessing-owned markers such as `symbol_conversion`, `dedup`, and `AD{idx}` on top instead of overwriting rows down to preprocessing-only tags.
5. **`functions/output.py` / `gui/steps/output_inject.py`** — Added shared trailing-newline stripping for manifest-resolved output/orig text before Step 9 verification, logging, generic writes, and parser injection routing.
6. **`formats/LightVN.py`** — Excluded `〈...〉` from the generic code-recovery bracket path so stylized suffixes such as `〈Limit per battle: 2〉` remain translated while the separate hardcoded-equipment rewrite logic still protects machine-key usages.
7. **Tests** — Added focused regressions for hardcoded composite tags, canonical `items` handling, manifest tag restoration, preprocessing tag merge, translated `〈...〉` suffix preservation, and the Step 9 trailing-newline guard.

**Tests:** Focused pytest run passed:
- `python -m pytest CherryAI/dev/test_lightvn_parser.py::TestRichMenuMarkup::test_menu_extraction_reads_button_labels_without_condition_literals CherryAI/dev/test_lightvn_parser.py::TestHardcodedMachineExtraction::test_conditional_button_line_keeps_machine_value_duplicate CherryAI/dev/test_lightvn_parser.py::TestHardcodedMachineExtraction::test_hardcoded_equipment_tags_include_special_care_marker CherryAI/dev/test_lightvn_parser.py::TestTargetedVariableExtraction::test_targeted_helper_marks_hardcoded_machine_literals CherryAI/dev/test_lightvn_parser.py::TestTargetedVariableOriginalCoverage::test_targeted_helper_covers_all_targeted_assignments_the_generic_path_would_get CherryAI/dev/test_lightvn_parser.py::TestMultilineInlineQuotedAssignments::test_limit_suffix_round_trips_for_skill_effect_assignment CherryAI/dev/test_lightvn_fixes.py::TestTagPropagation::test_items_tag_is_primary_content_tag CherryAI/dev/test_lightvn_fixes.py::TestTagPropagation::test_populate_from_manifest_restores_loaded_file_tags CherryAI/dev/test_lightvn_fixes.py::TestHardcodedEquipmentMachineKeys::test_injection_preserves_hardcoded_equipment_machine_values CherryAI/dev/test_output_injection.py::TestFreshLineReads::test_get_fresh_lines_strips_trailing_newlines CherryAI/dev/test_output_injection.py::TestWriteInjection::test_injection_strips_manifest_trailing_newlines_before_match -q --timeout=20` — 11 passed
- `python -m pytest dev/test_lightvn_fixes.py::TestTagPropagation::test_items_tag_is_primary_content_tag dev/test_lightvn_fixes.py::TestTagPropagation::test_populate_from_manifest_restores_loaded_file_tags dev/test_lightvn_fixes.py::TestTagPropagation::test_preprocessing_merges_tags_without_clobbering_parser_tags dev/test_lightvn_parser.py::TestHardcodedMachineExtraction::test_hardcoded_equipment_tags_include_special_care_marker dev/test_lightvn_parser.py::TestTargetedVariableExtraction::test_targeted_helper_marks_hardcoded_machine_literals dev/test_lightvn_parser.py::TestMultilineInlineQuotedAssignments::test_limit_suffix_round_trips_for_skill_effect_assignment dev/test_output_injection.py::TestFreshLineReads::test_get_fresh_lines_strips_trailing_newlines dev/test_output_injection.py::TestWriteInjection::test_injection_strips_manifest_trailing_newlines_before_match` — 8 passed

### BUG FIX: Dark GUI Designs + Window Persistence Options
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Add real dark-mode GUI designs, move GUI design selection into a new Application → GUI section in Global Options, persist the design in `CherryAI.ini`, and add options to save window sizes or launch windows maximized.

**Changes:**
1. **`functions/ini_manager.py`** — Added `[ui]` defaults and helpers for `design`, `save_window_dimensions`, `launch_maximized`, `window_geometries`, and `window_states`.
2. **`gui/theme/colors.py`** — Expanded the palette system to `Pale Blue`, `Slate Graphite`, `Midnight Teal`, `Carbon Amber`, and `High Contrast`; added a live `THEME` proxy, recursive Tk/ttk recoloring, alternating dark table rows, and shared `apply_window_preferences()` helpers.
3. **`gui/dialogs/global_options.py`** — Added `GUISettings`, a new Application → GUI section, the GUI Design dropdown, and the two new window-behavior toggles while keeping legacy session-theme compatibility.
4. **`gui/app.py`**, **`gui/dialogs/project_dialog.py`**, **`gui/dialogs/input_dialog.py`**, **`gui/dialogs/password_dialog.py`**, **`gui/dialogs/loading_progress.py`**, **`gui/dialogs/api_log_view.py`**, and **`gui/dialogs/table_view.py`** — Applied shared window preference handling and runtime theme refresh, including explicit recoloring for API Log and Full Table View custom surfaces.
5. **Tests** — Updated focused GUI regressions and verified the targeted pytest slice for theme compatibility, options dataclasses, section ordering, and startup/theme loading.

**Tests:** Focused pytest run passed:
- `python -m pytest CherryAI/dev/test_gui_dialogs.py CherryAI/dev/test_ini_persistence.py CherryAI/dev/test_ini_sections.py CherryAI/dev/test_app_startup.py CherryAI/dev/test_gui_v2.py -k "Theme or SessionSettingsDataclass or GlobalOptionsDataclass or SectionDescriptions or CategoryOrder or GlobalOptionsDialogIntegration" -q --timeout=20` — 64 passed

### BUG FIX: LightVN Hardcoded Equipment Display Rewrite Hook
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Let LightVN extract hardcoded armor-part terms as normal translation rows while keeping the actual machine keys intact during injection, and extend the parser handshake with an optional post-injection rewrite hook for this class of parser-safe code edits.

**Root Causes:**
1. The equipment UI in `e_armor.txt` reused `防具_選択中部位` both as visible text and as a machine key for jumps, dynamic variable names, and asset paths.
2. Normal menu and targeted-variable injection would translate quoted part literals in-place, which corrupted control flow and asset lookup.
3. The parser handshake had no optional post-injection hook for parsers that need structural rewrites after normal text replacement.

**Changes:**
1. **`formats/parser_base.py` / `formats/handshake.py`** — Added an optional `rewrite_injected_content(...)` hook and surfaced parser capability metadata for that rewrite path.
2. **`formats/LightVN.py`** — LightVN now extracts hardcoded equipment-part literals as normal rows, skips direct in-place replacement of those machine keys, and uses the rewrite hook to insert a translated display surrogate variable (`防具_選択中部位表示`) plus visible-text placeholder rewrites.
3. **`dev/test_lightvn_fixes.py`** — Added regressions for the base rewrite hook wiring and real-file `dev/scripts/PYUpgrade/scripts/e_armor.txt` extraction/injection behavior.
4. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the new handshake capability and the LightVN hardcoded-equipment strategy.

**Tests:** Focused pytest runs passed:
- `python -m pytest CherryAI/dev/test_lightvn_fixes.py -q --timeout=20` — 45 passed
- `python -m pytest CherryAI/dev/test_lightvn_fixes.py CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_table_view.py -q --timeout=20` — 250 passed

### BUG FIX: Wordwrap Simple Mode + File Navigation Rework
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Replace the redundant single-mode Step 8 selector with `Custom` and `Simple`, add a compact file selector in Wordwrap using the Full Table View file-filter structure, and add `View in File` next to `Accept Selected` so users can jump from a wrapped line to its source-file scope.

**Root Causes:**
1. Step 8 exposed only the legacy advanced wrapping workflow even though the mode selector implied multiple options.
2. There was no quick way to scope preview rows to one source file or to jump from a selected row back to its containing file.
3. Existing Wordwrap code and tests still depended on legacy `manual` naming in shared logic and older manifests.

**Changes:**
1. **`gui/steps/wordwrap_overwrite.py`** — Added `Custom` and `Simple` GUI modes, a compact `Select File:` control reusing `gui/dialogs/table_view.py::_FileFilterDropdown`, a `↗ View in File` action, and Simple-mode file-scoped processing that preserves untouched rows outside the selected file.
2. **`functions/wordwrap.py`** — Kept shared wrap compatibility for `manual`, `custom`, and `simple` mode values and restored the legacy `manual` alias/default expected by older tests.
3. **`functions/manifest_manager.py`** — Updated Wordwrap defaults/persistence to store current mode wording while remaining backward-compatible with loaded manifests.
4. **Tests** — Expanded `dev/test_wordwrap_phase46.py`, `dev/test_gui_v2.py`, and the broader Wordwrap compatibility batch to cover legacy mode mapping, Simple-mode file scoping, and `View in File` behavior.
5. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the new Step 8 behavior and verification coverage.

**Tests:** Focused and broader pytest runs passed:
- `python -m pytest CherryAI/dev/test_wordwrap_phase46.py -q --timeout=10`
- `python -m pytest CherryAI/dev/test_wordwrap.py CherryAI/dev/test_wordwrap_manifest.py CherryAI/dev/test_tag_wordwrap.py CherryAI/dev/test_wordwrap_overhaul.py CherryAI/dev/test_gui_v2.py -k "wordwrap or WrapMode or WrapOptionsDataclass or WordwrapStepIntegration" -q --timeout=20` — 204 passed, 2 skipped

### BUG FIX: LightVN Tagged Variable Wrapping + Table Selection Wrap
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Fix the LightVN `ev_メイン内容`-style missing-tag regression that let Step 8 treat variable text as dialogue, add explicit wrap-target selection in Step 8, remove the obsolete Step 8 Overwrite preview column, stop Simple mode from auto-wrapping on mode change, and add `Wrap Selection` to Full Table View.

**Root Causes:**
1. Some LightVN targeted variable rows could reach later parser branches without preserving the intended explicit `variable` tag.
2. Step 8 resolved wrap targets as `tags -> filedir type -> dialogue`, so an untagged line could still be wrapped as dialogue.
3. The Step 8 preview still documented and exposed an obsolete Overwrite-centric workflow.
4. Full Table View had no direct way to run the shared Step 8 wrapper on selected rows.

**Changes:**
1. **`formats/LightVN.py`** — Added tag-safe append handling for parser output and short-circuited targeted exact-variable extraction so rows such as `ev_メイン内容` keep their explicit `variable` tag.
2. **`gui/steps/wordwrap_overwrite.py`** — Added `Target:` strategies (`Tags first`, `Tags only`, `File first`, `File only`), removed the obsolete Step 8 Overwrite preview column, preserved unresolved rows unchanged instead of forcing a dialogue fallback, and kept Simple mode from auto-refreshing when selected.
3. **`gui/dialogs/table_view.py`** — Added `Wrap Selection` with a Step 8-style dialog (`Max Char`, `Max Line`, `Break Char`, `Pretty Wrap`), persisted those values into `WordwrapSettings`, and reused the shared `wordwrap` stage source chain for selected rows.
4. **Tests** — Expanded `dev/test_lightvn_fixes.py`, `dev/test_wordwrap_phase46.py`, and `dev/test_table_view.py` to cover the missing-tag regression, target-strategy behavior, Step 8 UI removal, and table-view wrap-selection persistence.
5. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the new Wordwrap target policy, LightVN tag contract, and Full Table View wrap-selection flow.

**Tests:** Focused pytest run passed:
- `python -m pytest CherryAI/dev/test_lightvn_fixes.py CherryAI/dev/test_wordwrap_phase46.py CherryAI/dev/test_table_view.py -q --timeout=10` — 244 passed

### BUG FIX: Indexed Aggressive Dedup Number Restore + Uni16 Salvage
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Stop aggressive dedup from restoring multiple numeric placeholders in the wrong order after translation reorders them, and salvage the existing `Projects/Uni16.CherryAI.json` data so rerunning Postprocessing and Wordwrap is sufficient.

**Root Causes:**
1. Shared aggressive dedup masking collapsed every numeric slot to the same `<NUM>` token, so translations such as `Deals <NUM>% damage to <NUM> enemy targets.` could only be restored left-to-right.
2. Step 6 postprocessing had its own `_reverse_aggr_numbers()` implementation that also performed blind left-to-right `<NUM>` substitution instead of using the shared dedup restore semantics.
3. Existing Uni16 step-3 `aggr_numbers` data was stored as positional lists, so saved manifests could not express reordered placeholder intent for multi-number lines.

**Changes:**
1. **`functions/dedup.py`** — Added indexed aggressive placeholders for multi-number rows (`<NUM1>`, `<NUM2>`, ...), kept legacy `<NUM>` behavior for single-number rows, and made restoration/token detection backward-compatible with both list and dict lookup forms.
2. **`gui/helpers/mode_adapter.py`** — Updated aggressive dedup fallbacks and batch return typing so GUI preprocessing stores indexed token maps for multi-number rows.
3. **`gui/steps/postprocess.py`** — Switched aggressive number restoration to the shared `aggressive_restore_line()` helper and taught step-data loading to accept both legacy lists and indexed token maps.
4. **`functions/analysis.py`** — Aligned the aggressive dedup projection fallback normalizer with the indexed placeholder behavior.
5. **`Projects/Uni16.CherryAI.json`** — Converted all saved multi-number aggressive lookups in `step_state.Preprocessing.data.aggr_numbers` to indexed token maps, updated affected `prepro`/`tl` source templates to indexed placeholders, and manually fixed the reordered English patterns such as `Deals <NUM2>% damage to <NUM1> enemy targets.`.
6. **Tests** — Added focused regressions for indexed masking/restoration in `dev/test_dedup.py` and the live postprocess restore path in `dev/test_postprocess_phase45.py`.

**Tests:** Relevant focused pytest runs passed:
- `python -m pytest CherryAI/dev/test_dedup.py -q --timeout=10 -k "aggressive or dedup"`
- `python -m pytest CherryAI/dev/test_postprocess_phase45.py -q --timeout=10 -k "AggressiveDedupIndexedRestore"`

**Note:** The broader `dev/test_postprocess_phase45.py` file still contains unrelated pre-existing symbol-conversion failures outside this fix.

### BUG FIX: LightVN Staged Input Sync Prevents Injection Drift
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Stop freshly loaded LightVN projects from producing Output-step verification warnings like `orig mismatch` and cascading `index out of range` failures before any translation work was done.

**Root Causes:**
1. Step 0 built manifest `lines[]` and `filedir[]` from the pre-copy source paths and only copied files into `Projects/{project}/Original/` afterward.
2. LightVN's project-scoped quoted-variable safety intentionally changes extraction based on the active `Original/` tree, so the same file could yield fewer keys during initial load than during later Output injection.
3. The non-destructive add-files path had the same staging-order problem for newly added parser-backed files.

**Changes:**
1. **`gui/steps/input_extract.py`** — Step 0 now stages parser-backed files into `Original/` before the final manifest sync and re-extracts them from that staged tree so `LoadedFile.lines`, parser tags, `lines[]`, and `filedir[]` all reflect the same parser view later used by Output injection.
2. **`functions/manifest_manager.py`** — `copy_originals_to_project()` now accepts explicit rel-path mappings even before `filedir` is rebuilt, which lets newly added parser-backed files use the same staged refresh path.
3. **`dev/test_lightvn_fixes.py`** — Added focused regressions covering staged LightVN re-extraction during `_sync_lines_to_manifest()` and explicit rel-path staging outside the current `filedir` set.
4. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the staged extraction contract and the new regression coverage.

**Tests:** Focused pytest run passed: `dev/test_lightvn_fixes.py`, `dev/test_lightvn_parser.py`, `dev/test_output_injection.py` — 119 passed.

### BUG FIX: Create Patch Workflow For Input Manifest Updates
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Add a Step 0 `Create Patch` button next to Import Translations so update projects can import prior manifest data, remove unchanged files, and keep only patch-relevant files in the current manifest.

**Changes:**
1. **`functions/manifest_manager.py`** — Added shared manifest-to-manifest import helpers, SHA-256 identical-`Original/` comparison, full-`orig` fallback pruning, and batch `remove_files()` reindexing that removes `filedir` entries, rewrites surviving line indices contiguously, and deletes copied `Original/` files for removed entries.
2. **`gui/steps/input_extract.py`** — Added the `Create Patch` toolbar button and kept the GUI layer to manifest selection, summary dialogs, and tree refresh while delegating all processing to `ManifestManager` per the Step 0 architecture rule.
3. **`dev/test_input_import_fixes.py`** — Added focused regressions for both fast-path identical-file pruning and fail-safe line-match pruning when source `Original/` files are missing.
4. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the new workflow, shared implementation, and validation coverage.

**Tests:** Focused pytest run passed: `python -m pytest CherryAI/dev/test_input_import_fixes.py -q --timeout=20` — 31 passed.

### BUG FIX: Final Output Layer + Full Table View Final Column
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Add a sparse per-line `final` field that sits after `wordwr`, make Output prefer it, expose it only through Full Table View for now, support Import Translation for it, and remove the reported `functions/wordwrap.py` invalid-escape warning.

**Changes:**
1. **`functions/manifest_fields.py`** — Added `final` to the shared latest/output pipeline (`final → wordwr → qa → postpro → tl → prepro → orig`), added source-aware helpers for Full Table View prefill, and removed `qa_overwrite` from Wordwrap input resolution.
2. **`functions/manifest_manager.py`** — Added canonical sparse manifest support for `final` immediately after `wordwr`.
3. **`gui/dialogs/table_view.py`** — Added the `Final` column to the spreadsheet, Show/Hide Columns, Show Latest, and Clear Columns. Empty `Final` cells now prefill from the latest non-final stage on double-click, stay table-local until Save, and auto-clear back to sparse-empty when edited back to their source value.
4. **`gui/steps/input_extract.py`** — Import Translation selection dialog now supports `final`.
5. **`functions/output.py` / `gui/steps/output_inject.py`** — Output resolution now prefers the shared canonical `final` stage over lower pipeline stages.
6. **`functions/wordwrap.py`** — Converted the RPG-code docstring to a raw string so `\V[#]` and related examples no longer trigger Python 3.12+ `SyntaxWarning` invalid-escape diagnostics.
7. **Tests** — Added focused regressions for shared pipeline order, Full Table View `Final` behavior, Import Translation `final` support, and output preference for `final`.

**Tests:** Focused pytest run passed: `dev/test_manifest_fields.py`, `dev/test_table_view.py`, `dev/test_input_import_fixes.py`, `dev/test_output_injection.py` — 399 passed. Additional verification passed: `python -W error::SyntaxWarning -c "import functions.wordwrap"`.

### BUG FIX: Preprocessing Tab Freeze Regression
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 45 minutes

Goal: Restore the responsive Preprocessing behavior that was still present in commit `9721cba` by reverting only the later persistence-path changes that froze tab load and could also stall Apply Rules on large manifests.

**Root Causes:**
1. `gui/steps/preprocess.py::_update_step_data()` stopped using its single-pass manifest update path and started calling `ManifestManager.get_line()` plus `set_line_field()` / `clear_line_field()` for every row.
2. The same helper-based path was triggered both after Apply Rules and during `_load_preview_from_manifest()`, so large projects paid the per-row manifest-helper cost on tab entry as well as on explicit preprocessing runs.

**Changes:**
1. **`gui/steps/preprocess.py`** — Reverted the helper-based persistence path and restored the `9721cba` bulk manifest update flow: build one `idx -> line` map from loaded manifest lines, mutate `tags` / `prepro` in place, and call `_mark_dirty()` once only when something changed.
2. **`gui/steps/preprocess.py`** — Removed the `persist_manifest` / `_preview_persist_pending` flow that had been added around preview refresh and tab leave as part of the regressed persistence path.
3. **Docs** — Updated feature, technical, spec, and test notes to describe the restored bulk persistence behavior and the focused rollback validation.

**Tests:** Focused pytest run passed: `dev/test_line_saving.py::TestSetLineField`, `dev/test_line_saving.py::TestRoundTrip`, `dev/test_line_saving.py::TestPreprocessIntegration`, `dev/test_manifest_overwrite.py` — 29 passed.

### BUG FIX: Wordwrap Invisible Width + Textbox Status Split + Responsive Apply
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Make Step 8 use Analysis-backed speaker detection during wrapping, recognize translated speaker aliases and parser fallback detection when manifest speaker data is missing, preserve leading indentation, rebalance PrettyWrap orphan tails more intelligently, count generic code normally unless the Code Database marked it invisible, split overflow results into `Exceeding` versus `New Textbox`, restore LightVN's required final injected `\w`, stop storing duplicate wrapped-line session data, and keep Apply responsive while wrapping and saving.

**Root Causes:**
1. Step 8 still relied on incomplete speaker allowlists instead of the full Analysis/parser data path, so translated prefixes such as `Young Horse Keeper:` could still count toward width and manifests with empty `characters[]` could lose speaker-ignore behavior entirely.
2. Shared wrapping stripped intended leading indentation from lines that fit or were reflowed.
3. PrettyWrap still used a weak greedy orphan heuristic, so balanced two-line splits such as `...,\nand ...` could degrade into one-word tail lines.
4. Step 8 treated every overflow case as a generic exceed condition and kept a redundant Step 8 overwrite-centric filter, even when overflow had already been realized safely as explicit textbox separators.
5. LightVN conditional dialogue injection still had a static-method `self` reference and could fail at export time with `name 'self' is not defined`.
6. Step 8 still wrote a duplicate `wrapped_lines` session cache even though `lines[].wordwr` is the real persisted wrap output.
7. Sparse manifest writes still ran on the Tk main thread after wrapping finished, so the UI progress bar appeared frozen during Apply.

**Changes:**
1. **`gui/steps/wordwrap_overwrite.py`** — `_get_ignore_codes()` now uses only manifest `code_patterns[]` entries marked `IsInvisible`; `_get_detected_speakers()` now accepts both original and translated aliases from manifest `characters[]` and falls back to parser `detect_speakers()` for the loaded preview rows when manifest speaker data is missing; `WrapLine` distinguishes `Exceeding` from `New Textbox`; `wrapped_lines` is no longer written into step session data; and Apply reports determinate progress while both wrapping and sparse `wordwr` persistence stay off the UI thread.
2. **`functions/wordwrap.py`** — shared wrapping now preserves leading indentation, `IGNORE` speaker mode is restricted to detected speaker names passed in through config, PrettyWrap rebalances one-word orphan tails by searching better breakpoints within the same line count, `apply_new_textbox_injection()` inserts textbox separators only between overflow chunks, never after the final chunk, and ignore-pattern compilation accepts raw regex strings from the manifest.
3. **`formats/LightVN.py`** — Explicit `wordwr` textbox separators are preserved between textboxes, parser injection restores exactly one final terminal `\w` when materializing dialogue output, and conditional-dialogue export no longer crashes on a stray `self` reference inside a static helper.
4. **Tests** — Added focused regressions for translated speaker aliases, parser speaker-detection fallback, balanced PrettyWrap orphan handling, visible generic code counting, indentation preservation, non-persisted unsplittable overflow, `wrapped_lines` removal, `New Textbox` status behavior, and terminal-marker LightVN injection.
5. **Docs** — Updated feature, technical, spec, test, and roadmap notes to match the verified Step 8 behavior.

**Tests:** Expanded focused pytest run passed: `dev/test_wordwrap.py`, `dev/test_wordwrap_phase46.py`, `dev/test_lightvn_parser.py`, `dev/test_tag_wordwrap.py`, `dev/test_wordwrap_manifest.py`, `dev/test_output_injection.py` — 310 passed.

### BUG FIX: Wordwrap Speaker Preservation + Explicit LightVN Textbox Separators
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Stop Wordwrap from deleting speaker prefixes when speaker width is ignored, preserve literal non-RPG break commands and escaped backslashes during wrapping, and make LightVN's full textbox separator (`\w` + newline + `"`) visible in parser defaults and stored `wordwr` output.

**Root Causes:**
1. Shared speaker mode `IGNORE` removed the speaker prefix entirely instead of excluding it from width calculations only.
2. Shared wrap preprocessing treated literal backslash commands such as `\n` as RPG-style control codes even for non-RPG formats, which collapsed explicit wrap boundaries and could strip unrelated escaped backslashes.
3. LightVN exposed only `\w` as `NewTextboxInjection`, while the real engine boundary is `\w` followed by newline and the next opening quote.
4. LightVN injection preserved multiline wrapped dialogue, but it did not recognize a preformatted textbox separator string already embedded in `wordwr`.

**Changes:**
1. **`functions/wordwrap.py`** — `IGNORE` speaker mode now keeps the speaker prefix in output while excluding it from width counting; non-RPG literal `\n` / `\r\n` commands are converted into explicit wrap boundaries; `apply_new_textbox_injection()` now writes parser separator strings directly into wrapped output when a tag supports new-textbox overflow.
2. **`gui/steps/wordwrap_overwrite.py`** — Step 8 now uses the shared textbox-injection helper after wrapping and documents speaker-ignore behavior as width-only.
3. **`formats/LightVN.py`** — Dialogue defaults now expose `NewTextboxInjection = "\\w\n\""`; injection preserves that explicit separator string when it already exists in `wordwr`.
4. **Tests** — Added focused regressions for speaker preservation, literal linebreak preservation, non-RPG backslash preservation, explicit separator emission, and LightVN preformatted separator injection.
5. **Docs** — Updated feature, technical, spec, test, and roadmap notes to match the verified behavior.

**Tests:** Focused pytest run passed: `dev/test_wordwrap_phase46.py`, `dev/test_lightvn_parser.py`, `dev/test_tag_wordwrap.py`, `dev/test_wordwrap_manifest.py` — 186 passed.

### BUG FIX: Manifest-Driven Wordwrap Formats + PrettyWrap Simplification
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Make the Wordwrap tab consume manifest formats directly so LightVN and future parser formats appear in Preview, keep wrapping scoped to each file format for safety, simplify wrap toggles to one PrettyWrap control, and document Wordwrap consistently as the ninth user-facing tab while keeping internal `step_id = 8`.

**Root Causes:**
1. The Preview `Format:` dropdown was still effectively static, so manifest formats such as `lightvn` did not reliably populate the selector.
2. Wordwrap settings were still centered on one global tag-config list, which was unsafe once a project contained more than one parser format.
3. Per-tag wrap behavior still exposed separate orphan/punctuation concepts instead of the intended single PrettyWrap toggle.
4. Documentation and a subset of regressions still used the older "Wordwrap & Overwrite" naming or the pre-QA ordering.

**Changes:**
1. **`gui/steps/wordwrap_overwrite.py`** — Added manifest-driven per-format `FormatConfig` handling, per-line source format/path metadata, preview filtering by selected format, per-format enabled/disabled state, and per-tag enabled/default behavior. Apply now processes enabled formats sequentially but only wraps rows that belong to each row's own `filedir[].format`.
2. **`functions/manifest_manager.py`** — Added `WordwrapSettings.PrettyWrap` and `WordwrapSettings.FormatConfigs` support plus format-config accessor helpers.
3. **`functions/wordwrap.py`** — Added a single `pretty_wrap` config flag with compatibility fallback for legacy orphan/punctuation settings.
4. **LightVN defaults** — Menu remains prefilled in Wordwrap but disabled by default because the parser exposes no-wrap width for that tag.
5. **Tests** — Updated focused Wordwrap, manifest, and GUI regressions for per-format configs, PrettyWrap, and the QA-before-Wordwrap workflow order.
6. **Docs** — Updated feature, technical, spec, test, and roadmap notes to match the verified behavior and naming.

**Tests:** Focused pytest run passed: `dev/test_wordwrap_phase46.py`, `dev/test_tag_wordwrap.py`, `dev/test_wordwrap_manifest.py`, plus targeted `dev/test_gui_v2.py` assertions for step order and Wordwrap dataclasses — 154 passed.

### BUG FIX: Wordwrap Apply Source + LightVN Textbox Realization
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix the live Step 8 failure where Apply/Refresh appeared to run but produced no visible Wordwrap result, keep Wordwrap aligned with canonical tag resolution, and let LightVN realize explicit multiline wrapped dialogue as multiple textboxes instead of losing overflow.

**Root Causes:**
1. `gui/steps/wordwrap_overwrite.py::_process_wrap()` wrapped `step_data["lines"]` instead of the already loaded preview rows in `self._lines`, so the background run could finish against an empty cache while the visible table stayed unchanged.
2. Step 8 still resolved tags from legacy `tag` in some paths, which drifted from the manifest's canonical `tags` field.
3. Step 8 treated `max_lines` as destructive truncation, which is incompatible with formats such as LightVN where overflow must become additional textboxes during injection.
4. `formats/LightVN.py` did not preserve explicit multiline `wordwr` content as authoritative logical lines before textbox emission.

**Changes:**
1. **`gui/steps/wordwrap_overwrite.py`** — `_process_wrap()` now wraps the loaded preview rows, preserves the table's current Overwrite edits during recalculation, uses canonical tag resolution, and treats `max_lines` as an exceed check rather than truncation.
2. **`formats/LightVN.py`** — Explicit multiline wrapped dialogue is now preserved and chunked into successive 3-line LightVN textboxes with the correct `...\w` + newline + next opening quote ordering during injection.
3. **Tests** — Added focused regressions in `dev/test_wordwrap_phase46.py` and `dev/test_lightvn_parser.py`, plus updated the Wordwrap GUI subset in `dev/test_gui_v2.py`.
4. **Docs** — Updated the Wordwrap rework note plus the feature/spec/technical/test documentation to match the verified runtime behavior.

**Tests:** Focused pytest runs passed: `dev/test_wordwrap_phase46.py`, `dev/test_lightvn_parser.py`, `dev/test_lightvn_fixes.py` — 122 passed. GUI subset `dev/test_gui_v2.py -k wordwrap` — 9 passed.

### BUG FIX: QA Rerun Policy + Multilingual SourceLanguageDetection
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Fix the inert QA tab, keep the Quality Assurance column sparse, and replace Japanese-only QA residue checks with multilingual `SourceLanguageDetection` driven by manifest language metadata.

**Changes:**
1. **`gui/steps/qa.py`** — Fixed rerun policy handling for persisted values (`FailedOnly` / `All` / `None`), stopped the Quality Assurance column from falling back to stage input text, and moved per-line QA checking to shared validation helpers.
2. **`functions/validation.py`** — Added shared QA validation, multilingual source-language residue detection, preserve-action code-pattern stripping, and language-pair-specific behavior such as kana-only Japanese→Chinese detection and marker-only German detection.
3. **`functions/manifest_manager.py`** — Migrates legacy `JapaneseCharacterDetection` → `SourceLanguageDetection` and `MaxJapaneseChars` → `MaxSourceLanguageChars` when older manifests are loaded.
4. **Tests** — Added focused regressions for sparse QA column loading, legacy manifest migration, preserve-pattern exclusion, and multilingual detection paths.

**Tests:** Focused pytest run passed: `dev/test_validation.py`, `dev/test_qa_manifest.py`, `dev/test_api_validation.py`, `dev/test_settings_flow.py`, `dev/test_estimate_manifest.py`, `dev/test_manifest_fields.py`, and targeted QA classes in `dev/test_gui_v2.py` — 490 passed.

### BUG FIX: QA Encoding Safety For Legacy Output Codecs
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Catch `shift_jis` / `cp932` write failures earlier in Step 7 by validating the effective QA review text against a selected output encoding, surfacing the first offending character, and offering a safe overwrite suggestion based on explicit transliteration plus Unicode normalization.

**Changes:**
1. **`functions/validation.py`** — Added `validate_encoding_safety()` and `make_encoding_safe_text()` using explicit transliteration for macron vowels and EM/EN dash variants, followed by `unicodedata.normalize("NFKD", ...)` and combining-mark removal. `validate_qa_line()` now emits `encoding_unsafe` findings with the offending character, position, and an auto-fix replacement when the transformed text encodes cleanly.
2. **`gui/steps/qa.py`** — Added manifest-backed QA options `EncodingSafetyEnabled` and `EncodingCheckEncoding`, surfaced as a checkbox plus encoding spinbox, mapped new `ENCODING_UNSAFE` issues, and changed Apply Fix / Auto-fix to write encoding-safe replacements into `qa_overwrite`.
3. **`functions/manifest_manager.py`** — Extended `QAOptions` defaults and getters with the new encoding-safety fields while keeping older manifests backward-compatible.
4. **Tests** — Added focused regressions for the shared encoding helper, QA options persistence, GUI dataclass defaults, and applying encoding-safe auto-fixes through `qa_overwrite`.

**Tests:**
- `python -m pytest dev/test_validation.py -q --timeout=20` — 95 passed
- `python -m pytest dev/test_validation.py dev/test_qa_manifest.py dev/test_gui_v2.py dev/test_manifest_defaults.py -k "EncodingSafety or encoding_safety or apply_current_fix_writes_encoding_safe_overwrite or on_leave_does_not_auto_write_qa_fields or test_issue_type_enum_values or test_qa_issue_creation or test_qa_options_defaults or test_qa_options_custom or test_manifest_has_qa_options" -q --timeout=20` — 11 passed
- `python -m pytest dev/test_validation.py dev/test_qa_manifest.py dev/test_manifest_defaults.py -q --timeout=20` — `dev/test_validation.py` and `dev/test_qa_manifest.py` passed; `dev/test_manifest_defaults.py` still has unrelated pre-existing failures outside this change slice

### BUG FIX: Safe Open Project Reset + Canonical Tags Import
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Make `File → Open Project...` safe when another project is already active, stop stale `last_manifest` entries from being recreated, and normalize manifest/import tagging so CherryAI writes canonical `tags` without leaking legacy `tag` fields or over-broad dedup import restrictions.

**Root Causes:**
1. `gui/app.py::_load_manifest_from_path()` reused the active runtime state instead of replaying the same cache-flush path as New Project, so step tabs could carry old loaded-file and preview state into the newly opened manifest.
2. `functions/ini_manager.py` cleared `last_manifest` by writing an empty string, while INI startup seeding recreated the placeholder key on later loads.
3. `gui/steps/input_extract.py` still wrote parser content tags into legacy `tag`, imported `tag` directly from other manifests, and replaced tags instead of merging them.
4. Dedup placeholder rows (`prepro == "__DEDUP__"`) needed a narrow Import Translations guard for `tl` only; the previous broader restriction interfered with valid later-stage imports and persistence.

**Changes:**
1. **`gui/app.py`** — Open Project now loads into a fresh `ManifestManager`, swaps it in only after successful load, resets `SessionState`, calls `on_new_project()` on all tabs, and then enters the saved step.
2. **`functions/ini_manager.py`** — `set_last_manifest(None)` now removes `[session].last_manifest`, and startup seeding no longer recreates the key.
3. **`functions/manifest_manager.py`** — Added canonical line normalization on load/save/set: merges legacy `tag` into `tags` and writes line keys in canonical order `idx`, `tags`, `orig`, `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, `wordwr`, then auxiliary fields without stripping valid later-stage fields from dedup placeholder rows.
4. **`gui/steps/input_extract.py`** — Parser tag propagation and manual tag edits now write canonical `tags`; translation import merges tags, removes duplicates, migrates legacy `tag` without writing it back, and blocks only `tl` imports for dedup placeholder rows.
5. **Tests** — Added focused regressions in `dev/test_app_startup.py`, `dev/test_input_import_fixes.py`, and `dev/test_lightvn_fixes.py`.

**Tests:** Focused pytest run passed: `dev/test_app_startup.py`, `dev/test_input_import_fixes.py`, `dev/test_lightvn_fixes.py` — 85 tests passing.

### BUG FIX: LightVN Detection Fallback + Bookmark Placeholder Filtering
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Stop LightVN map/script files from falling back to raw `txt` extraction, remove the unwanted raw-code chunks seen in the provided `Uni105` manifest, and prevent editor placeholder dialogue (`ここにテキストを入力`) from being extracted with leaked speaker names.

**Root Causes:**
1. `formats/LightVN.py::can_handle()` only looked for a narrow signal set (`~【`, `~文字`, `~ボタン`, `~絵`, `~効果音`, `~選択`, `栞 `), so script/config-style LightVN files such as `battle_test.txt`, `bgm.txt`, `event\event_mainstory_final_map_05.txt`, and `event\event_mainstory_final_map_06.txt` fell back to plain `txt` extraction.
2. Because those files bypassed the parser entirely, the manifest stored raw code lines with no parser `tag`, which matched the unwanted chunks beginning at indices like `420` and `9999` in the provided project.
3. Within already-detected LightVN files, `~栞 ...` bookmark lines did not reset `_current_speaker`, so placeholder dialogue under later bookmarks inherited the previous real `~【Speaker】` name.
4. The repeated `ここにテキストを入力` lines are editor scaffolding rather than real game text, but the parser treated them like normal dialogue and sent them into translation/speaker analysis.

**Changes:**
1. **`formats/LightVN.py`** — Expanded LightVN auto-detection to include `~栞`, `~スクリプト`, `~保存変数`, `~臨時全域変数`, plus bare `栞 `, `スクリプト `, `保存変数 `, and `臨時全域変数 ` line prefixes.
2. **`formats/LightVN.py`** — Added bookmark handling so `~栞 ...` clears carried speaker state and no longer leaks the previous `~【Speaker】` into later map/interactable dialogue.
3. **`formats/LightVN.py`** — Filtered editor placeholder dialogue (`ここにテキストを入力`, `Enter your text here.`) out of extraction so it is not translated and does not pollute speaker tagging.
4. **Tests** — Added focused regressions for bookmark reset/placeholder filtering and the new detection variants in `dev/test_lightvn_parser.py` and `dev/test_lightvn_fixes.py`.
5. **Real-file verification** — Confirmed against the supplied `Projects/Uni105/Original` corpus that `battle_test.txt`, `bgm.txt`, `event_mainstory_final_map_04.txt`, `event_mainstory_final_map_05.txt`, and `event_mainstory_final_map_06.txt` are all now detected as LightVN and that the placeholder dialogue no longer appears in extracted output.

**Files Modified:**
- `formats/LightVN.py` — broader detection, bookmark reset, placeholder filtering
- `dev/test_lightvn_parser.py` — bookmark/placeholder regressions
- `dev/test_lightvn_fixes.py` — detection regressions for missed LightVN file variants
- `doc/features.md` — LightVN detection and placeholder behavior
- `doc/technical.md` — LightVN implementation notes
- `doc/specs.md` — LightVN parser specification
- `doc/tests.md` — focused test coverage updates
- `doc/todo.md` — completed fix summary

**Tests:** Focused pytest run passed: `dev/test_lightvn_parser.py`, `dev/test_lightvn_fixes.py` — 69 passed. Real-file verification against the supplied `Uni105` sources confirmed the previously missed files are detected and the placeholder dialogue is no longer extracted.

### BUG FIX: Sparse Manifest Persistence + Safe Import Metadata
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Preserve the active project name during translation-settings import, add a bulk clear workflow to Full Table View, and stop Postprocessing, QA, and Wordwrap from auto-writing unchanged per-line results.

**Root Causes:**
1. Importing Information metadata merged the incoming manifest wholesale, so `project_name` could be replaced by an unrelated project.
2. Full Table View only supported ad hoc cell deletion and had no guided destructive workflow for clearing stage columns across the manifest.
3. Postprocessing, QA, and Wordwrap wrote redundant no-op values back into `lines[]`, which made the manifest denser than the actual user-visible pipeline state.
4. QA and Wordwrap still had automatic persistence paths on tab leave or preview refresh, even when the user had not explicitly accepted any changed output.

**Changes:**
1. **`gui/steps/input_extract.py`** — Importing Information metadata now preserves the current `project_name` while still merging the rest of the selected metadata sections.
2. **`gui/dialogs/table_view.py`** — Added a Clear Columns dialog for `prepro`, `tl`, `postpro`, `qa`, `qa_overwrite`, and `wordwr`; clearing `tl` now requires a second confirmation.
3. **`functions/manifest_manager.py`**, **`gui/steps/postprocess.py`**, **`gui/steps/qa.py`**, **`gui/steps/wordwrap_overwrite.py`** — Added sparse field clearing so unchanged `postpro`, `qa_overwrite`, and `wordwr` are removed instead of persisted, and removed QA/Wordwrap auto-write paths.
4. **Tests** — Added focused regressions for import preservation, Clear Columns behavior, sparse postprocess persistence, QA overwrite persistence, Wordwrap explicit-only persistence, and metadata merge semantics.

**Tests:** Focused pytest run passed: `dev/test_input_import_fixes.py`, `dev/test_table_view.py`, `dev/test_postprocess_phase45.py`, `dev/test_qa_manifest.py`, `dev/test_wordwrap_phase46.py`, `dev/test_manifest_metadata.py` — 292 passed, 5 deselected (unrelated pre-existing symbol-conversion regressions).

### BUG FIX: Translation Skip Policy Parity + Status Summary
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Make Translation Refresh, Preview Requests, Start Translation, and Costs estimation respect the same skip policies, especially already translated lines versus the global overwrite option, and surface policy-skipped counts in the Translation header.

**Root Causes:**
1. `gui/steps/translate.py` used separate ad hoc skip paths for refresh, preview, and execution instead of one shared classifier.
2. Preview Requests filtered from an inconsistent line set, so already translated lines were not governed by the overwrite/skip-translated option the same way as the live run.
3. The Translation header only reported a coarse ready/translated count and did not expose policy skips such as empty, placeholders, code-only, symbol-only, or non-source lines.
4. Shared pre-translation validation was still Japanese-centric for optional language skips and did not treat CJK-family source projects consistently.

**Changes:**
1. **`functions/validation.py`** — Extended `validate_line_pre()` with source-language-aware detection, CJK/Hangul filtering for Japanese/Chinese/Korean projects, and symbol-only classification ahead of placeholder-only handling so auto-normalized symbol lines remain `SYMBOL_ONLY`.
2. **`gui/steps/translate.py`** — Added `_collect_translatable_lines()` and `_build_translation_status_text()` so refresh, Preview Requests, and Start Translation all reuse the same shared validation results. Preview now reclassifies all loaded lines, overwrite-enabled runs re-include already translated lines, and `on_enter()` / Preview / Start Translation all re-sync Global Options before using cached state so stale overwrite settings cannot leak across tab re-entry.
3. **`gui/steps/costs.py`** — `_get_skip_indices()` now passes the manifest source language into `validate_line_pre()` so estimation stays aligned with Translation and Preview for CJK-family projects.
4. **Tests** — Expanded `dev/test_validation.py` and `dev/test_request_preview.py`; focused regression run passed for `dev/test_validation.py`, `dev/test_estimation_skip.py`, and `dev/test_request_preview.py` (176 passed, 1 skipped).

**Follow-up:**
- Add separate Global Options toggles for individual optional skip classes shown in the Translation status summary, especially placeholders, code-only, symbols-only, empty, and non-source lines.

### BUG FIX: Deferred Validation Retries + Speaker Delimiter Discard
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Separate API retry handling from translation-validation failures, enforce speaker-format preservation with a strict per-line colon/fullwidth-colon count check, and move validation retries to a deferred pass after the main translation run.

**Root Causes:**
1. Step 5 accepted successful API responses without running the shared batch validation path, so speaker-format and structural checks were not consistently enforced in the live workflow.
2. Line-count mismatches were raised as normal `TranslationError`s inside `functions/api_client.py`, which caused them to be retried inline as if they were transport/API faults.
3. Speaker-format preservation relied on broader pattern inference instead of the requested concrete `:` / `：` count parity per line.

**Changes:**
1. **`functions/validation.py`** — Added delimiter-count speaker validation for `:` and `：`, plus explicit full-response discard signaling for unsafe structural mismatches.
2. **`functions/api_client.py`** — Added `ResponseValidationError` so line-count mismatches bypass inline API retries and stay in the validation lane.
3. **`gui/steps/translate.py`** — Step 5 now validates successful responses before persisting them, queues validation-only failures into deferred retry jobs, retries them after the main pass with the configured retry strategy, and feeds untranslated source text into rolling context for lines still awaiting validation recovery.
4. **Tests** — Added focused regressions in `dev/test_api_validation.py`, `dev/test_first_request_gate.py`, and `dev/test_translation_phase43.py`.

**Tests:** Focused pytest run passed: `dev/test_api_validation.py`, `dev/test_first_request_gate.py`, `dev/test_translation_phase43.py` — 120 passed, 2 skipped.

### BUG FIX: Exact-Length OpenAI Structured Output + API Log Failure Filter
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Investigate the recurring line-count mismatch on a concrete OpenAI `gpt-4.1` translation request, prevent that failure mode where plausible, and make the API Log able to isolate failed requests directly.

**Root Causes:**
1. The failing request returned valid JSON but merged two adjacent source lines into one translated item, so cardinality drift survived prompt-only instructions.
2. CherryAI still used plain `json_object` for cloud OpenAI translation chunks, which guarantees valid JSON but not schema adherence or exact array length.
3. The API Log store already tracked request status, but the dialog toolbar did not expose a failure-focused filter.
4. `test_model_translation()` logged success immediately after the HTTP response, so invalid structured output could appear as a successful API Log entry.

**Changes:**
1. **`functions/api_client.py`** — OpenAI translation chunks now use strict `json_schema` with exact `minItems` / `maxItems` for the `translations` array when the provider supports structured output.
2. **`gui/dialogs/api_log_view.py`** — Added a status filter so Failed, Recovered, Successful, and Pending requests can be isolated directly in the API Log window.
3. **`functions/api_config.py`** — `test_model_translation()` now logs validation failures as failed inference entries instead of premature success.
4. **Tests** — Added focused regressions for exact-length response-format selection and API Log status-filter mapping, while keeping the existing API Log failure-classification coverage green.

**Tests:** Focused pytest run passed: `dev/test_api_log.py`, `dev/test_api_validation.py`, `dev/test_first_request_gate.py`, `dev/test_translation_phase43.py` — 186 passed, 1 skipped.

### BUG FIX: Relaxed Fatal API Policy + 10-Chunk Validation Gate
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Stop aborting Step 5 on the first retryable API hiccup. Only billing/quota exhaustion and concrete not-found failures should remain immediate hard stops, transient upstream reset/overflow errors should retry, and the validation-failure-rate stop should not arm until at least 10 chunks have been sampled.

**Root Causes:**
1. `functions/common_errors.py` still defaulted most classified API categories to fatal unless a caller opted into `is_retryable=True`, so auth, permission, content-filter, generic bad-request, and unknown failures aborted too aggressively.
2. Proxy/gateway messages such as `upstream connect error or disconnect/reset before headers. reset reason: overflow` did not match any retryable classifier branch and therefore fell through to fatal `UNKNOWN`.
3. `gui/steps/translate.py` armed the validation-failure-rate stop after only 20 lines, which let a single early discarded chunk present as a 100% failure rate and cancel the whole run.

**Changes:**
1. **`functions/common_errors.py`** — Changed the shared default so only quota/billing exhaustion and concrete not-found failures remain fatal by default; auth, permission, content-filter, generic bad-request, and unknown failures now stay on the retry path. Added explicit retryable matching for upstream reset/overflow gateway text.
2. **`providers/__init__.py`** — Aligned provider-level `AuthenticationError` and `ContentFilteredError` defaults with the relaxed shared retry policy.
3. **`gui/steps/translate.py`** — Added chunk counters and changed the validation-failure-rate abort gate so it only activates after 10 sampled chunks, while still using the line-based failure ratio for the actual threshold.
4. **Tests** — Expanded focused regressions in `dev/test_api_error_classification.py`, `dev/test_first_request_gate.py`, `dev/test_translation_phase43.py`, and provider spot-checks in `dev/test_provider_handshake.py`.

**Tests:** Focused pytest slices passed: `dev/test_api_log.py`, `dev/test_api_error_classification.py`, `dev/test_first_request_gate.py`, `dev/test_translation_phase43.py` — 198 passed, 2 skipped. Provider spot-check passed: `dev/test_provider_handshake.py -k "authentication_error or content_filtered_error"` — 2 passed.

### BUG FIX: QA Before Wordwrap + Dedicated QA Field
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Move Quality Assurance ahead of Wordwrap across the GUI, shared stage resolution, import/export behavior, and Full Table View. Split QA-reviewed text from QA overwrite so QA and Wordwrap no longer share the same manifest field.

**Root Causes:**
1. The old pipeline treated QA as a later pass than Wordwrap, so shared "latest" resolution, Full Table View, and Output all preferred the wrong fields.
2. QA only had `qa_overwrite`, forcing reviewed text and manual overwrite text into one field.
3. The Wordwrap preview table restored its Wordwrap column from fallback input text, which made the wrapped column appear prepopulated even when no `wordwr` existed.

**Changes:**
1. **`functions/manifest_fields.py`** — Reordered the shared priority chain to `wordwr → qa_overwrite → qa → postpro → tl → prepro → orig`, changed QA stage input to `postpro → tl → prepro → orig`, and changed Wordwrap stage input to `qa_overwrite → qa → postpro → tl → prepro → orig`.
2. **`gui/steps/qa.py`** — Added a dedicated `qa` column, kept `qa_overwrite` as the editable Overwrite column, and added a `Copy to Overwrite` action.
3. **`gui/steps/wordwrap_overwrite.py`** — Moved Wordwrap after QA and made the Wordwrap column load only stored `wordwr` values.
4. **`gui/dialogs/table_view.py`** and **`gui/steps/input_extract.py`** — Updated Full Table View and Import Translations for `qa`, `qa_overwrite`, `wordwr`, and the unified `tags` column.
5. **Tests** — Updated focused regressions for manifest-field priority, QA manifest integration, Wordwrap input/loading, and Full Table View naming.

**Tests:** Focused pytest run passed: `dev/test_manifest_fields.py`, `dev/test_qa_manifest.py`, `dev/test_wordwrap_phase46.py`, `dev/test_table_view.py` — 385 tests passing.

### BUG FIX: LightVN Item Variable Extraction and Injection Tagging
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Extend the LightVN parser so item-like variable assignments are handled the same way as other translatable assignment lines, but surfaced with a dedicated `items` tag. This specifically covers loot/material values such as `角兎の素材×1` from `臨時全域変数 剥ぎ取り素材1 = "角兎の素材×1"` and conditional item gains such as `食用の肉×3` from `もし (獲得ボーナス >= 2) 臨時全域変数 獲得食材 = "食用の肉×3"`.

**Root Cause:**
1. `formats/LightVN.py` only recognized a small fixed prefix set in `TRANSLATABLE_VARS`, so item-style variable names like `剥ぎ取り素材1` and `獲得食材` never entered extraction.
2. Because those lines were not classified as translatable assignments, the LightVN injection path also skipped them.
3. The parser had no dedicated tag to distinguish regular variable assignments from item/material text even though both need different semantic labeling in the manifest.

**Changes:**
1. **`formats/LightVN.py`** — Added `TAG_ITEMS` and shared variable-name classification so item-like assignment fields are recognized during both extraction and injection.
2. **`formats/LightVN.py`** — Added `ITEM_VARS` coverage for names such as `剥ぎ取り素材` and `獲得食材`, including conditional `もし (...)` forms after prefix stripping.
3. **`dev/test_lightvn_parser.py`** — Added focused regressions for `items` extraction and surgical injection.
4. **`dev/test_wordwrap_overhaul.py`** — Added a no-wrap regression for `wordwrap_for_tag("items")`.

**Files Modified:**
- `formats/LightVN.py` — `TAG_ITEMS`, variable classification, item extraction/injection support
- `dev/test_lightvn_parser.py` — item-variable extraction/injection regressions
- `dev/test_wordwrap_overhaul.py` — items no-wrap regression

**Tests:** Focused pytest run passed: `dev/test_lightvn_parser.py`, `dev/test_wordwrap_overhaul.py` — 59 tests passing.

### BUG FIX: LightVN Project-Scoped Variable Safety
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Expand LightVN variable extraction beyond the old fixed allowlist without breaking engine control flow, asset lookup, or script routing. Quoted `保存変数` / `臨時全域変数` assignments should be translated only when the same variable is used purely as display text across the active project.

**Root Causes:**
1. `formats/LightVN.py` only trusted a small hardcoded prefix list, so display-only variables such as `bt_勝利条件` / `bt_敗北条件` / `bt_エロ条件` were skipped even though they are rendered through `文字窓`.
2. A naive broadening of quoted-variable extraction would have broken mixed-use variables such as `胎児`, whose text value is also interpolated into asset paths like `子宮/子宮_妊娠_{{胎児}}.png`.
3. Control variables such as `付与対象` and pattern variables such as `bat_ボイスパターン` participate in `もし (...)` logic or non-display command construction, so translating their assignments alone would desynchronize runtime comparisons and file lookups.

**Changes:**
1. **`formats/LightVN.py`** — Added project-scoped quoted-variable usage analysis. For files under an `Original/` tree, the parser now scans sibling LightVN scripts, records whether each quoted text variable is used only in display contexts or also in non-display interpolations / `もし (...)` conditions, and only extracts the display-only set.
2. **`formats/LightVN.py`** — Kept standalone-file parsing fast by limiting the broader scan to `Original/` project roots; non-project files continue to use single-file analysis.
3. **`dev/test_lightvn_parser.py`** — Added focused regressions covering display-only extraction/injection (`bt_勝利条件`), mixed asset/display exclusion (`胎児`), and control-flow exclusion (`付与対象`).
4. **Docs** — Updated LightVN feature, technical, spec, and test references to describe the new safety rule and its verified examples.

**Files Modified:**
- `formats/LightVN.py` — project-scoped variable usage index, safe quoted-variable classification
- `dev/test_lightvn_parser.py` — display-only vs. mixed-use variable regressions
- `doc/features.md` — user-facing LightVN variable behavior
- `doc/technical.md` — implementation notes for project-scoped safety analysis
- `doc/specs.md` — LightVN parser specification
- `doc/tests.md` — focused regression coverage and command

**Tests:** Focused pytest runs passed: `dev/test_lightvn_parser.py`, `dev/test_lightvn_fixes.py` — 77 passed. Expanded injection regression passed: `dev/test_output_injection.py`, `dev/test_lightvn_parser.py`, `dev/test_lightvn_fixes.py` — 116 passed.

### BUG FIX: LightVN Exact Variable Comparisons + Menu Parentheses Preservation
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Extend the LightVN parser so specific displayed variables translate not only on assignment but also when compared with `==` / `!=`, while preserving visible ASCII-parenthesized menu labels such as `回復薬(粗悪品)` that were still falling through untranslated.

**Root Causes:**
1. LightVN only extracted quoted text from `保存変数` / `臨時全域変数` assignments or the broader project-scoped display-only path, so exact UI/gameplay variables such as `主人公`, `スキル名`, `敵次スキル名`, `敵発動スキル`, and `設定_出産設定説明文` could miss their visible `==` / `!=` comparison literals or bare `変数` assignments.
2. Some of those exact-name variables also overlapped with the broader project-scoped classifier, which risked duplicate extraction unless the whitelist and generic path were separated.
3. `_remove_parenthetical_content()` stripped ASCII parentheses everywhere on a menu line, including inside the quoted text itself, so `回復薬(粗悪品)` extracted as `回復薬` and then could not be injected back into the original quoted string.

**Changes:**
1. **`formats/LightVN.py`** — Added a dedicated exact-name whitelist for visible LightVN variables including `主人公`, `ev_メイン`, `ev_メイン内容`, `子宮状態`, `開発_初めての相手`, `防具_選択中部位`, `武器1_名前`-`武器3_名前`, `武器1_特性1`-`武器3_特性3`, `設定_出産設定説明文`, `スキル名`, `スキル効果`, `敵次スキル名`, `敵発動スキル`, and `bat_ヒロイン次スキル名`.
2. **`formats/LightVN.py`** — Added one targeted extraction/injection path for those exact names that handles quoted literals from exact `変数` / `保存変数` / `臨時全域変数` assignments plus exact `==` / `!=` comparisons, applies the final `variable` versus `items` tag directly from the targeted helper, keeps parity with the older broad assignment parser on padded placeholder literals such as `"{{道具_馬名前}}  "`, skips file-like literals such as `.txt`, and keeps the same names out of the generic project-scoped classifier to avoid duplicate extraction.
3. **`formats/LightVN.py`** — Updated menu preprocessing so ASCII parentheses are preserved while inside quoted text, which fixes labels such as `回復薬(粗悪品)`.
4. **`dev/test_lightvn_fixes.py`** — Added a focused regression for quoted ASCII-parentheses preservation and updated the LightVN full-file integration expectation to include the now-intended `主人公 = "名前入力"` extraction.
5. **`dev/test_lightvn_parser.py`** — Added focused exact-variable extraction/injection regressions plus real-Uni16 verification that every whitelisted variable is extracted by the new helper, injectable by the same helper, that every targeted assignment the broad helper would have returned is still covered, and that both the targeted-name overlap scan and the remaining broad-helper scan are empty on `Projects/Uni16/Original`.
6. **`formats/LightVN.py`** — Removed dead whitelist entries `剥ぎ取り素材4` and `剥ぎ取り素材5` after the real-Uni16 scan confirmed they do not occur in the current staged originals.
7. **Docs** — Updated LightVN feature, technical, spec, and test references to describe the exact-variable path, the file-literal guard, and the menu-parentheses fix.

**Files Modified:**
- `formats/LightVN.py` — exact-name whitelist, targeted extraction/injection path, quoted-parenthesis preservation
- `dev/test_lightvn_fixes.py` — menu-parentheses regression, updated integration expectation
- `dev/test_lightvn_parser.py` — exact-variable regressions and real-Uni16 verification
- `doc/features.md` — user-facing LightVN behavior
- `doc/technical.md` — implementation notes for targeted exact-variable handling
- `doc/specs.md` — LightVN parser specification
- `doc/tests.md` — focused regression coverage and verified command

**Remaining generic project-scoped variables to review later for whitelist/blacklist placement:**
- `スキル追加`
- `剥ぎ取り素材1`
- `剥ぎ取り素材2`
- `剥ぎ取り素材3`
- `獲得食材`
- `調合素材`
- `道具効果`
- `道具名`

**Tests:** Verified focused pytest run passed: `dev/test_lightvn_fixes.py`, `dev/test_lightvn_parser.py`, `dev/test_output_injection.py` — 128 passed.

### BUG FIX: Line-Agnostic Custom Placeholder Restore + Nested Double-Curly Filtering
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix two related postprocessing edge cases. First, restore custom placeholder replacements such as `Jane` even when the LLM moved the token onto a different line that had no original placeholder. Second, stop preserve-action validation/recovery from flagging both `{{主人公}}` and the inner `{主人公}` when only the doubled form is semantically present on the line.

**Root Causes:**
1. GUI and modi custom placeholder restoration were line-bound: they only consumed captured values from the original source line index, so a named replacement shifted by the LLM could not be restored.
2. GUI preprocessing stored only flat `placeholder_captured` value lists, which was insufficient for safe batch-wide restoration when multiple custom tokens existed.
3. Code pattern validation and recovery used plain regex matches, so a preserve rule for `{主人公}` could match the nested substring inside `{{主人公}}` and produce a false second warning/recovery attempt.

**Changes:**
1. **`functions/modehelper.py`** — Added `restore_custom_placeholders_batch()` with a two-pass restore strategy: local per-line restoration first, then a batch-wide exact-token fallback for unresolved named replacements.
2. **`gui/helpers/mode_adapter.py`**, **`gui/steps/preprocess.py`**, **`gui/steps/postprocess.py`** — Persist token-aware `placeholder_records` alongside legacy `placeholder_captured` and use them for batch-wide postprocessing restoration.
3. **`modi/custom_placeholder.py`** — Switched Post restoration to the shared batch helper so the processor path and GUI path behave the same way.
4. **`functions/validation.py`** and **`functions/postprocess.py`** — Filter nested balanced-code matches so inner `{...}` substrings are ignored when they only exist inside a larger balanced token like `{{...}}`.
5. **Tests** — Added `dev/test_custom_placeholder_recovery.py` and expanded `dev/test_code_pattern_recovery.py` with the doubled-curly overlap regression.

**Files Modified:**
- `functions/modehelper.py` — batch custom placeholder restore helper
- `gui/helpers/mode_adapter.py` — token-aware placeholder capture records
- `gui/steps/preprocess.py` — persist `placeholder_records`
- `gui/steps/postprocess.py` — batch placeholder restore before post-exclusive recovery
- `modi/custom_placeholder.py` — shared batch restoration path
- `functions/validation.py` — nested code-pattern match filtering
- `functions/postprocess.py` — nested code-pattern match filtering
- `dev/test_custom_placeholder_recovery.py` — new regressions
- `dev/test_code_pattern_recovery.py` — nested double-curly regressions

**Tests:** Focused pytest run passed: `dev/test_code_pattern_recovery.py`, `dev/test_custom_placeholder_recovery.py`, `dev/test_recovery_anchor.py` — 112 tests passing.

### BUG FIX: Dedup False Postprocess Flags + Flag-Case Filtering
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Stop deduplicated duplicate rows from being falsely flagged during postprocessing placeholder/code-pattern recovery, and make the Processed Lines widget filter/search those flags by case and by the exact Recovery Details text.

**Root Causes:**
1. Deduplicated rows with `tags: "dedup,..."` could still enter the batch custom-placeholder restore fallback and the per-line `recover_line()` phase when they had real `tl` text, even though their final text is supposed to come from dedup source restoration.
2. That let duplicate rows accumulate transient `placeholder_case` / code-pattern retry flags before `_restore_dedup_lines()` copied the already-correct source output over them.
3. The Processed Lines widget only exposed a coarse `Flagged` filter and the shared table search only indexed visible column values, so users could not narrow flags by case or find rows by copied Recovery Details text.

**Changes:**
1. **`gui/steps/postprocess.py`** — Added manifest tag loading on `PostprocessLine`, skipped dedup-tagged rows during batch placeholder fallback and per-line post-exclusive recovery, cleared duplicate-row issue state during dedup restoration, added a dynamic flagged-case combobox next to `Flagged`, and indexed formatted Recovery Details text into table row metadata.
2. **`gui/components/table.py`** — Extended `SharedTable` text filtering to search row values, tags, and nested metadata so Processed Lines search now matches issue text as well as visible cells.
3. **Tests** — Expanded `dev/test_postprocess_phase45.py` with regressions for empty/populated flag-case dropdown states, dedup-restoration flag clearing, and metadata-backed Recovery Details search.

**Files Modified:**
- `gui/steps/postprocess.py` — dedup-aware postprocessing skip/filter/search behavior
- `gui/components/table.py` — metadata-aware table search
- `dev/test_postprocess_phase45.py` — flag-case, dedup, and Recovery Details search regressions
- `doc/features.md` — Processed Lines filter/search behavior and dedup postprocess notes
- `doc/technical.md` — implementation notes for postprocess and shared-table search
- `doc/specs.md` — custom placeholder postprocessing behavior for dedup-tagged lines
- `doc/tests.md` — updated phase-45 test coverage summary

**Tests:** Focused pytest run passed: `dev/test_postprocess_phase45.py -k "flag_case or dedup or recovery_details or refresh_lines_keeps_postpro_separate_from_translated_input or on_complete_only_persists_changed_postpro_lines"` — 6 passed. Full `dev/test_postprocess_phase45.py` still has 4 unrelated pre-existing failures around legacy symbol-conversion expectations.

### BUG FIX: Stage-Bounded Line Preference Resolution
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Stop workflow steps from reading the generic "latest" line value when they should only consume their own stage input or earlier pipeline fields. Postprocessing must use `tl → prepro → orig`, Wordwrap must use `postpro → tl → prepro → orig`, and QA must use `wordwr → postpro → tl → prepro → orig`.

**Root Causes:**
1. `LineEntry.get_input_for_postprocessing()` still walked the Edit/TLC chain, so postprocessing could restore into newer review passes instead of the base translation.
2. `functions/manifest_fields.py` exposed a full-chain "latest" helper intended for final display/output, and QA was using it directly for stage input.
3. Step-specific loaders documented and implied stage ceilings, but only QA still enforced the wrong one at runtime.

**Changes:**
1. **`functions/mainhelper.py`** — Reworked `get_input_for_postprocessing()` to use `tl → prepro → orig` only. Clarified `get_input_for_wordwrap()` as `postpro → tl → prepro → orig`.
2. **`functions/manifest_fields.py`** — Added stage-specific helpers `resolve_line_field_for_stage()`, `get_line_text_for_stage()`, and `get_all_lines_for_stage()`. Kept `PIPELINE_FIELDS` / `resolve_line_field()` as the full final-display chain for output and "latest" views.
3. **`gui/steps/postprocess.py`**, **`gui/steps/wordwrap_overwrite.py`**, **`gui/steps/qa.py`** — Switched stage loaders to explicit stage helpers. QA now falls back from empty `qa_overwrite` to the QA input chain instead of the generic latest value.
4. **Tests** — Updated `dev/test_manifest_v2.py`, expanded `dev/test_manifest_fields.py`, and added stage-resolution regressions in `dev/test_postprocess_phase45.py`, `dev/test_wordwrap_phase46.py`, and `dev/test_qa_manifest.py`.

**Files Modified:**
- `functions/mainhelper.py` — stage-bounded LineEntry input resolution
- `functions/manifest_fields.py` — stage-specific line-resolution helpers
- `gui/steps/postprocess.py` — explicit postprocessing ceiling
- `gui/steps/wordwrap_overwrite.py` — explicit wordwrap ceiling
- `gui/steps/qa.py` — explicit QA ceiling and qa_overwrite fallback behavior
- `dev/test_manifest_v2.py` — updated LineEntry expectations
- `dev/test_manifest_fields.py` — stage helper regressions
- `dev/test_postprocess_phase45.py` — postprocessing stage-input regressions
- `dev/test_wordwrap_phase46.py` — wordwrap stage-input regressions
- `dev/test_qa_manifest.py` — QA stage-input regressions

**Tests:** Focused regression run passed (15 tests): `dev/test_manifest_v2.py`, `dev/test_manifest_fields.py`, and targeted stage-resolution tests in `dev/test_postprocess_phase45.py`, `dev/test_wordwrap_phase46.py`, `dev/test_qa_manifest.py`.

### BUG FIX: Bracket Recovery Should Only Run For Balanced Source Lines
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Stop Bracket Balance Recovery from triggering just because bracket counts differ from the original. Recovery should only engage when the source line itself has balanced recoverable brackets and the latest translated text is actually unbalanced.

**Root Cause:**
1. `recover_bracket_balance()` used original-vs-translation bracket counts as its trigger, so balanced translations with different bracket styles could still be treated as "missing bracket" cases.
2. Rare intentionally unbalanced source lines were used as recovery templates even though there was no trustworthy bracket structure to restore.
3. Lenticular brackets (`【】`) were counted separately from square brackets (`[]`), so symbol-converted lines could be treated as missing-bracket cases.
4. Extra unmatched translated brackets (especially a third `}` after balanced `{{...}}` code) were only flagged, not repaired.

**Changes:**
1. **`functions/postprocess.py`** — Added `_get_recoverable_bracket_pair_id()`, `_extract_recoverable_brackets()`, `_find_unmatched_brackets()`, and `_has_balanced_brackets()` to evaluate recoverable bracket structure with quote-equivalent bracket pairs excluded.
2. **`functions/postprocess.py`** — Reworked `recover_bracket_balance()` to return immediately when the original line is not bracket-balanced, and to skip balanced latest text even when bracket style drifted away from the source.
3. **`functions/postprocess.py`** — Canonicalised `【】` into the square-bracket family for recovery comparisons, and remove extra unmatched translated brackets before attempting missing-bracket insertion.
4. **`dev/test_recovery_anchor.py`** — Added regression coverage for unbalanced-original skip behavior, lenticular-vs-square bracket equivalence, extra `}` removal, and the intentional triple-`}` exception. Updated the old "both brackets missing" case to reflect the new gating rule.

**Files Modified:**
- `functions/postprocess.py` — balanced-source gate + recoverable-bracket helpers
- `dev/test_recovery_anchor.py` — new gating regressions and updated expectations

**Tests:** `dev/test_recovery_anchor.py` — 79 tests passing.

### BUG FIX: Per-Model API.ini Settings Not Respected by Estimation & Preview
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Fix four interconnected bugs where Estimation (Step 4) and Preview Requests (Step 5) ignored per-model API.ini settings (chunk_size, chunk_max_tokens, rolling_context_before/between/after, temperature) and instead used Global Options defaults, causing request count mismatches between modes. "Efficient" request slicing appeared broken because Global Options unconditionally overrode per-model values, and "conservative" paradoxically produced fewer requests. Preview Requests always showed 2040 requests regardless of slicing mode.

**Root Causes:**
1. `_do_estimation()` in `costs.py` unconditionally overwrote per-model `chunk_size` and `max_input_tokens` with Global Options `go.request.chunk_size` / `go.request.max_input_tokens` on every estimation run, erasing values already loaded by `_load_model_settings()`.
2. `_build_preview_requests()` in `translate.py` called `_build_chunks()` which read from `self._translation_options` — initialized to defaults in `__init__` (chunk_size=30, slicing="conservative") and only updated when `_start_translation()` ran, never during Preview.
3. `_build_chunks()` in `translate.py` read `rolling_context_between`, `rolling_context_after`, and `max_input_tokens` from Global Options (`go.request.*`), ignoring per-model API.ini settings entirely.
4. `TranslationStep` had no `_load_model_settings()` method (unlike `CostsStep`), so per-model API.ini settings (chunk_size, temperature, rolling_context, thinking) were never loaded into the UI on tab entry.

**Changes:**
1. **`gui/steps/costs.py`** — Removed the unconditional Global Options override block in `_do_estimation()` that replaced `chunk_size` and `tokens_limit` with `go.request.*` values. Per-model settings from `_load_model_settings()` (via `_chunk_var`/`_tokens_var`) now flow through correctly. Only `request_slicing` is still read from Global Options (no per-model override exists).
2. **`gui/steps/translate.py`** — Added `_load_model_settings()` method that loads chunk_size, temperature, rolling_context_before/between/after, thinking settings from API.ini per-model `get_model_settings(model_id)` with Global Options fallback. Called from `_load_request_options_from_manifest()` after `_sync_from_global_options()`.
3. **`gui/steps/translate.py`** — Fixed `_build_preview_requests()` to execute `self._translation_options = opts` after `opts = self._get_options_from_ui()`, ensuring `_build_chunks()` uses current UI values instead of stale `__init__` defaults.
4. **`gui/steps/translate.py`** — Fixed `_build_chunks()` to read `rolling_context_between`, `rolling_context_after`, and `chunk_max_tokens` from per-model API.ini via `get_model_settings()`, falling back to Global Options when no per-model setting exists.
5. **`gui/steps/translate.py`** — Fixed `_build_preview_requests()` rolling context "before" to read per-model `rolling_context_before` from API.ini, falling back to Global Options.

**Settings Priority Chain (established):**
Per-model API.ini `[model_settings]` → Global Options CherryAI.ini `[request]`/`[translation]` → dataclass defaults

**Files Modified:**
- `gui/steps/costs.py` — Removed Global Options override in `_do_estimation()`
- `gui/steps/translate.py` — Added `_load_model_settings()`, fixed `_build_preview_requests()` stale options, fixed `_build_chunks()` per-model settings, fixed rolling context per-model

**Tests:** `dev/test_request_slicing_settings.py` — 30 tests (TestEfficientAlwaysFewerRequests: 7, TestMinLinesCalculation: 2, TestStep5EfficientMerge: 5, TestConfigPropagation: 2, TestCostsEstimationNoOverride: 2, TestTranslateLoadModelSettings: 2, TestPreviewUpdatesOptions: 1, TestBuildChunksPerModelSettings: 4, TestPreviewRollingContextPerModel: 1, TestFormationPipelineRealWorld: 3, TestFormationStepsConsistency: 1). All passing, 0 regressions.

---

### BUG FIX: Request Slicing Estimation ↔ Translation Mismatch + CODE_ONLY Skip
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix three issues with Request Slicing: (1) `efficient` mode not respected during Estimation — Step 5 cross-file merge never ran in costs.py because `efficient_merge` was not passed to `RequestFormationConfig`, causing Estimation to produce more requests than Translation; (2) No skip condition for lines consisting entirely of preserved code patterns; (3) Preview Requests did not include the merged-request conditional prompt (slot 8b) for efficiently-merged requests.

**Root Causes:**
1. `_estimate_via_formation()` in `gui/steps/costs.py` created `RequestFormationConfig` without `efficient_merge=(slicing == "efficient")` — the field defaulted to `False`, so Step 5 never ran during estimation even when the user selected "efficient" mode.
2. Lines consisting entirely of preserved code patterns (e.g. `{{主人公}}`, `<文字色 255 50 50>`, `</>`) were sent to the LLM unnecessarily because no skip condition existed for code-pattern-only lines.
3. `_build_preview_requests()` in `gui/steps/translate.py` did not extract `merge_boundaries` from formation context or build/pass `merge_instruction` to the prompt builder.

**Changes:**
1. **`gui/steps/costs.py`** — Added `efficient_merge=(slicing == "efficient")` to `RequestFormationConfig` in `_estimate_via_formation()`. Added preserve-pattern collection from manifest `code_patterns` (action="preserve") and `is_code_pattern_only()` check in LineInfo construction. Added same pattern collection in `_get_skip_indices()` with `preserve_patterns` passed to `validate_line_pre()`.
2. **`functions/prompt_builder.py`** — Added `is_code_pattern_only(text, preserve_patterns)` function: strips each preserve pattern (with `<NUM>` → `\d+` wildcard), placeholder tokens, and non-translatable punctuation; returns True when nothing remains.
3. **`functions/validation.py`** — Added `SkipReason.CODE_ONLY` enum value. Added `preserve_patterns` optional parameter to `validate_line_pre()`. Added step 5c check after placeholder-only (step 5b): if preserve_patterns provided and line is code-pattern-only, return CODE_ONLY skip.
4. **`gui/steps/translate.py`** — Added `is_code_pattern_only` import and preserve-pattern collection in `_build_chunks()`. Added `merge_boundaries` extraction and `build_merged_request_instruction()` call in `_build_preview_requests()` for slot 8b conditional prompt.

**Files Modified:**
- `gui/steps/costs.py` — efficient_merge flag, preserve_patterns collection, code-only skip in both `_get_skip_indices()` and `_estimate_via_formation()`
- `gui/steps/translate.py` — code-only skip in `_build_chunks()`, merge_instruction in `_build_preview_requests()`
- `functions/prompt_builder.py` — `is_code_pattern_only()` function
- `functions/validation.py` — `SkipReason.CODE_ONLY`, `preserve_patterns` parameter in `validate_line_pre()`

**Tests:** `dev/test_request_slicing_fix.py` — 50 tests (TestIsCodePatternOnly: 15, TestCodeOnlySkipReason: 2, TestValidateLinePreCodeOnly: 8, TestEfficientMergeParity: 5, TestMergeBoundaries: 2, TestMergedRequestInstruction: 3, TestCodePatternOnlyManifestPatterns: 8, TestRequestFormationConfigPropagation: 4, TestValidateLinePrePreservePatterns: 3). All passing, 0 regressions.

---

### BUG FIX: INI Persistence — Atomic Saves, GUI Mismatch, User Defaults
**Priority:** CRITICAL | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Fix three interconnected bugs causing CherryAI.ini data loss and GUI settings mismatch: (1) INI file getting wiped to only `[ui] state = {}`, (2) `[user_defaults]` values only saved after clicking Apply in Global Options, (3) GUI showing wrong values despite INI having correct ones (e.g. `request_slicing = efficient` shown as `conservative`).

**Root Causes:**
1. `mainhelper.save_app_state()` created its own `ConfigParser` (without `optionxform = str`) and on read failure caught the exception, created an empty ConfigParser, and wrote only `[ui] state = {}` — wiping all other sections.
2. `[user_defaults]` section was only written when Apply/OK was clicked in Global Options dialog. Before that, settings fell back to dataclass defaults.
3. `GlobalOptions.load_from_ini()` only loaded `UtilitySettings` and `PromptsSettings` from the INI — all other settings sections (API, Request, Translation, Caching, Logging, Session, Limit, FileIO) used hardcoded dataclass defaults, ignoring INI values.

**Changes:**
1. **Atomic save in `_save_ini()`** — Rewritten to write to a `.tmp` file, `fsync`, then `os.replace()` to prevent corruption on interrupted writes.
2. **`set_default()` and `clear_user_defaults()`** — Changed from raw `open()/write()` to route through `_save_ini()` for atomic saves.
3. **Centralized UI state API** — Added `load_ui_state()` and `save_ui_state()` to `ini_manager.py`. These use the shared `_ini_cache` and atomic save, ensuring UI state writes never wipe other sections.
4. **`mainhelper.save_app_state()` / `load_app_state()`** — Rewritten to delegate to `ini_manager.save_ui_state()` / `load_ui_state()` with a legacy fallback path that also preserves `optionxform = str` and aborts on read failure instead of resetting.
5. **`config.py:save_config()`** — Made safe: set `optionxform = str`, abort on read failure instead of starting fresh, atomic write pattern.
6. **Comprehensive `load_from_ini()`** — Rewritten `GlobalOptions.load_from_ini()` to load ALL 10 settings sections (API, Request, Translation, Caching, Logging, Session, Limit, FileIO, Utility, Prompts) using `get_effective_default()` with proper type conversion helpers.

**Files Modified:**
- `functions/ini_manager.py` — `_save_ini()` atomic rewrite, `set_default()` routing, `clear_user_defaults()` routing, new `load_ui_state()` and `save_ui_state()` functions
- `functions/mainhelper.py` — `save_app_state()` and `load_app_state()` delegating to ini_manager
- `functions/config.py` — `save_config()` safety fixes (optionxform, abort on failure, atomic write)
- `gui/dialogs/global_options.py` — `load_from_ini()` comprehensive rewrite loading all settings sections

**Tests:** `dev/test_ini_persistence.py` — 22 tests (TestAtomicSave: 3, TestSaveAppState: 3, TestSaveAppStateDoesNotWipeIni: 1, TestSetDefaultAtomic: 1, TestLoadFromIniComprehensive: 6, TestEffectiveDefaultPrecedence: 3, TestCasePreservation: 1, TestClearUserDefaults: 1, TestConcurrentSafety: 1, TestBooleanHandling: 2). Net result: 78 previously-failing tests fixed, 0 new regressions.

---

### REWORK: Mock Translation Cancellation & Speed
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Make mock translation (and general translation) safely cancellable and remove artificial speed bottlenecks. The Cancel button was unresponsive during mock translation because (a) `MockTranslator` had no cancellation mechanism, (b) a `delay_per_chunk=0.1` added unnecessary latency, and (c) per-chunk UI table updates flooded the Tkinter event loop.

**Changes:**
1. **`functions/mock_translator.py`** — Added optional `cancel_event: threading.Event` parameter to `MockTranslator.__init__()` and `create_mock_translator()`. `translate_batch()` checks the event between lines; on cancellation it pads remaining output with empty strings and returns immediately. Default `delay_per_chunk` remains `0.0`.
2. **`gui/steps/translate.py`** — Added `_cancel_event: threading.Event` to `TranslationStep`. `_on_cancel()` now sets both `_cancel_requested` flag and `_cancel_event`. Mock translator created with `cancel_event=self._cancel_event` and no delay. Concurrent executor checks event before submitting new work. `_process_single_chunk` and `_execute_string_sequential` check the event. Pause loop uses `cancel_event.wait(timeout=0.1)` instead of `time.sleep`. Added `_schedule_table_update()` that throttles UI refreshes to 150 ms intervals.

**Graceful Shutdown Behaviour:**
- Cancel sets event + flag → no new chunks submitted
- In-flight API requests finish naturally (not killed)
- Mock translator stops processing lines immediately
- Background thread exits cleanly, `_on_translation_complete` runs on main thread

**Tests:** `dev/test_mock_translation.py` — 11 new tests (TestCancellation: 8 tests, TestSpeed: 3 tests); total file now 70 tests.

**Files Modified:**
- `functions/mock_translator.py` — `cancel_event` parameter, early-exit in `translate_batch()`
- `gui/steps/translate.py` — `_cancel_event`, `_schedule_table_update()`, cancel wiring
- `dev/test_mock_translation.py` — 11 new tests (TestCancellation, TestSpeed)

---

### REWORK: Speaker:Dialogue-Aware Standard Injection
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Rework the standard `inject_to()` handshake in `parser_base.py` to properly separate Speaker and Dialogue during surgical injection. The original implementation searched for the combined `"Speaker: dialogue"` string literally in the raw file content — but this synthetic key never exists verbatim because speaker and dialogue are separate entities in source files (e.g. `[Speaker]` on its own line, dialogue text on the next). Speaker:Dialogue separation is a core principle (§5.1).

**Rules:**
- The Speaker can have their own line that needs to be recorded.
- The same Speaker line can apply to several Dialogue lines during extraction. For subsequent lines with the same speaker, the speaker replacement is skipped.
- Both Speaker and Dialogue are separated and spaces respected (no leading/trailing spaces unless in the original).
- The Speaker is replaced first (no leading/trailing spaces), the dialogue line after (no leading spaces unless intended).

**Changes:**
1. **`formats/parser_base.py`** — Added `_SPEAKER_DIALOGUE_RE` regex and `_split_speaker_dialogue(text)` module-level helper that splits `"Speaker: dialogue"` (half-width `: ` or fullwidth `：`) into `(speaker, dialogue)` tuple; returns `("", text)` when no separator found. Rewrote `inject_to()`: now uses `extract_tagged()` when available to get per-line speaker metadata via `ExtractedLine.speaker`. Lines with a speaker are split into speaker/dialogue parts and replaced independently. Speaker name replaced only on first occurrence for consecutive same-speaker lines (`last_replaced_speaker` tracking). Lines without a speaker use plain find-and-replace. Falls back to `extract()` with empty speaker list when `extract_tagged()` returns `None`.
2. **`formats/LightVN.py`** — No changes. Override remains necessary because LightVN's raw file format strips `\w` markers, `"` prefixes, joins multi-line dialogue during extraction — cleaned text does not exist literally in the raw file, so standard `content.find()` can never match. LightVN keeps its engine-specific `_extract_all_keys()` / `_inject_all()` pipeline.

**LightVN Universal Handshake Assessment:** LightVN cannot use the standard speaker-aware handshake because extraction fundamentally transforms text: (a) `\w` word-continuation markers removed, (b) `"` dialogue prefixes stripped, (c) multi-line continuations (`-"`) joined into single strings, (d) conditional `~もし` prefixes stripped. The extracted text is a cleaned composite that never appears verbatim in the raw file. For LightVN to use the universal handshake, extraction would need to return raw file text segments — which conflicts with the necessary cleaning that makes keys usable for translation. The current approach (parser-specific override) is the correct architecture.

**Tests:** `dev/test_output_injection.py` — 14 new tests (4 `_split_speaker_dialogue` helper + 10 Speaker:Dialogue injection scenarios); total file now 39 tests.

**Files Modified:**
- `formats/parser_base.py` — `_SPEAKER_DIALOGUE_RE`, `_split_speaker_dialogue()`, `inject_to()` rewrite
- `dev/test_output_injection.py` — 14 new tests (TestSplitSpeakerDialogue, TestSpeakerDialogueInjection)

---

### BUG FIX: Output Step Empty Files — Parser Surgical Injection via inject_to
**Priority:** CRITICAL | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix Output step (Step 9) producing entirely empty files when exporting parser formats like LightVN. The root cause was that `_write_file()` looked up `Options.ParserName` (never set) instead of detecting the parser from `filedir[].format`. When no parser was found, the generic TXT writer dumped flat resolved text — destroying all non-translatable script structure. Added `inject_to(source, output, lines)` to the Parser Handshake for surgical injection that reads source files, replaces only translatable text, and writes complete scripts to the output path.

**Changes:**
1. **`formats/parser_base.py`** — Added `inject_to(source_path, output_path, lines)` to `ParserScript` ABC with a default implementation that calls `inject()` and moves the `_translated` file to the output path.
2. **`formats/LightVN.py`** — Overrode `inject_to()` with surgical injection: reads original from source, re-extracts keys via `_extract_all_keys()`, builds translation dict by zipping with lines, calls `_inject_all()` for surgical replacement, writes complete modified script to output. `inject()` now delegates to `inject_to()`.
3. **`gui/steps/output_inject.py`** — `_write_file()`: Detects parser format from `filedir[].format`, queries `ParserRegistry`, slices per-file lines using `first_idx:last_idx+1`, calls `parser.inject_to()`. Falls back to generic writer on failure. `_build_file_list_from_filedir()`: Preserves original file extension for parser formats instead of forcing format-mapped extension.

**Tests:** `dev/test_parser_injection.py` — 16 tests covering inject_to surgical injection, base class default, Output step parser routing, per-file line slicing, extension preservation, and end-to-end regression (output must never be empty).

**Files Modified:**
- `formats/parser_base.py` — `inject_to()` default method
- `formats/LightVN.py` — `inject_to()` override, `inject()` delegation
- `gui/steps/output_inject.py` — `_write_file()` parser detection, `_build_file_list_from_filedir()` extension handling
- `dev/test_parser_injection.py` — 16 new tests

---

### BUG FIX: Output Defaults Now Track Input + LightVN Auto Encoding Honors Forced Parser
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Ensure Step 9 Output always opens with valid defaults derived from Step 0 Input, make destination/state manifest-backed instead of UI-only, and ensure explicit parser selection such as LightVN still controls encoding when Encoding remains `auto`.

**Root Causes:**
1. Output defaults were split across INI defaults, manifest fallbacks, and widget initialization, so the tab could open with blank or stale settings.
2. `OutputFormat.Destination` was not manifest-backed, so `Same as Source` could not be stored and restored cleanly.
3. Step 0 detected encoding before resolving the effective parser format, so forced parser choices could bypass parser-specific `detect_encoding()`.
4. Legacy defaults still used `translated_only`, overwrite off, and other values that did not match the current Output behavior requirements.

**Changes:**
1. **Manifest-backed Output defaults** — Added `OutputFormat.Destination` support and normalized fallback/default values in `functions/manifest_manager.py` and `functions/ini_manager.py`.
2. **Runtime destination resolution** — `gui/steps/output_inject.py` now stores `Same as Source`, resolves it against the staged source directory at runtime, and uses the same helper for preview, browse, open-folder, and export.
3. **Input-driven Format/Encoding seeding** — `gui/steps/input_extract.py` now seeds missing or invalid Output format/encoding defaults from the first loaded input file.
4. **Forced parser + auto encoding fix** — Step 0 now resolves format before encoding so explicitly selected parsers like LightVN still provide encoding through `detect_encoding()` when Encoding is `auto`.
5. **Regression coverage** — Updated Output/Input regression suites and added focused checks around manifest defaults and parser-driven encoding.

**Files Modified:**
- `functions/ini_manager.py` — normalized Output defaults (`Same as Source`, `custom`, overwrite on, `timestamp`, `.bk`)
- `functions/manifest_manager.py` — added `OutputFormat.Destination` and matching Output fallback defaults
- `gui/steps/output_inject.py` — manifest-backed destination binding, runtime destination resolution, input-aware default application, `custom` pair mode
- `gui/steps/input_extract.py` — output-default sync from input metadata, parser-first auto-encoding flow
- `dev/test_output_manifest.py` — updated/default regression expectations
- `dev/test_output_phase47.py` — updated Output default coverage
- `dev/test_input_step_phase39.py` — added input-to-output default sync coverage

**Tests:** Focused pytest run passed: `dev/test_output_manifest.py`, `dev/test_output_phase47.py`, `dev/test_input_step_phase39.py`, `dev/test_lightvn_fixes.py` — 171 tests passing.

### BUG FIX: API Log Window Full Content Rendering + Display Limit Control
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Restore full API Log Window content display after the failed truncation-removal attempt commented out the renderer loop, and make the viewer configurable without trimming stored log data.

**Root Causes:**
1. `APILogViewDialog._render_wrapped_content()` had its line-rendering loop commented out during a truncation-removal attempt, so prompt and response blocks lost all body text.
2. Several structured log producers still sliced prompt/content fields with `[:2000]` before data reached `APILogStore`, so the viewer could never show the full request/response text even when the UI was fixed.
3. Some failure-path structured log entries omitted prompt/user hand-off details, making the API Log inconsistent between success and failure cases.

**Changes:**
1. **Viewer rendering restored** — `gui/dialogs/api_log_view.py` now renders all stored lines by default again via `_render_wrapped_content()`.
2. **Display-limit spinbox** — Added toolbar control with `All` (default), `1000`, `2500`, `5000`, and `Nothing`. The limit is viewer-only and is persisted in `user/CherryAI.ini` as `[log].api_log_display_limit`.
3. **Full structured-log capture** — Removed structured-log `[:2000]` slicing from `functions/api_client.py`, `functions/api_config.py`, `functions/term_translation.py`, and `functions/API2Glossary.py` so full prompt/user/response bodies reach `APILogStore`.
4. **Failure-path hand-off cleanup** — Line-by-line translation failures and term/model test failures now keep the available prompt/user context in the structured API log instead of logging only minimal metadata.
5. **Regression coverage** — Added display-limit helper/rendering tests and source guards that prevent structured-log prompt/content truncation from being reintroduced.

**Files Modified:**
- `gui/dialogs/api_log_view.py` — restored content rendering, added display-limit spinbox + persisted setting
- `functions/api_client.py` — removed structured-log content truncation, improved line-by-line failure hand-off
- `functions/api_config.py` — removed structured-log prompt/content/error truncation in model + connection tests
- `functions/term_translation.py` — removed structured-log truncation and logged full failure context
- `functions/API2Glossary.py` — removed structured-log content truncation
- `functions/ini_manager.py` — added `[log].api_log_display_limit = All` default
- `dev/test_api_log.py` — +7 structured-log full-content guard tests
- `dev/test_gui_dialogs.py` — +5 API Log display-limit tests

**Tests:** Focused pytest run passed: `dev/test_api_log.py` (51), `dev/test_gui_dialogs.py` (26), `dev/test_bugfix_batch_79.py` (33) — 115 tests passing.

### BUG FIX: Bracket/Quote Balance Recovery Too Aggressive (Anchor-Relative Rewrite)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Rewrite Bracket Balance Recovery and Quote Balance Recovery to use anchor-relative positioning with ANCHOR_EQUIVS equivalence instead of absolute positional data. Both recoveries were inserting brackets/quotes at computed positions using `rel_pos = pos / len(original)` which produced wrong results when translation length differs from original.

**Root Causes:**
1. `recover_bracket_balance()` used `rel_pos = pos / len(original)` then `insert_at = int(rel_pos * len(result))` — absolute positional mapping that fails when translated text has different structure/length.
2. No equivalence awareness — fullwidth/halfwidth bracket/quote conversions (e.g. `（`→`(`, `「`→`"`) counted as "missing" because the recovery compared exact characters, not canonical forms.
3. Bracket-quote hybrids (`「`/`」`, canon=`"`) were counted as brackets AND handled by quote recovery, causing double-insertion.

**Changes:**
1. **Equivalence infrastructure** — Added `BRACKET_EQUIV`, `QUOTE_EQUIV`, `_CANON_MAP` (from ANCHOR_EQUIVS), `_CLOSING_TO_OPENING`, `_RECOVERY_ANCHOR_CHARS`, `_normalize_bracket()` to `functions/postprocess.py`.
2. **`recover_bracket_balance()` rewritten** — Extracts brackets from both texts using canonical forms via `_CANON_MAP`. Counts by `(canonical, role)` pairs. Defers bracket-quote hybrids (`「」` etc. whose canonical is `"`) to quote recovery. Missing brackets use `_try_anchor_bracket_insert()` with line-start/end detection and `_find_anchor_near()` + `get_equivs()` (canonicalised) for character anchors. Flags `NEEDS_RETRY` when no anchor found.
3. **`_find_anchor_near()`** — New helper that finds nearest punctuation anchor from a position. Skips whitespace and specified skip chars. Stops at first non-anchor, non-space character.
4. **`_try_anchor_bracket_insert()`** — New helper that tries line-start/end first, then character-anchor search using `get_equivs(_CANON_MAP.get(anchor_ch, anchor_ch))` for bidirectional equivalence lookup.
5. **`recover_quote_balance()` rewritten** — Extracts quotes including bracket-quote equivalents (`「`→`"` via ANCHOR_EQUIVS). Uses canonical comparison to detect truly missing quotes. Closing quotes → line end. Opening quotes → line start or anchor-relative. Interior quotes → anchor or `NEEDS_RETRY`.
6. **Anchor canonicalization fix** — `get_equivs()` calls in `_try_anchor_bracket_insert()` now canonicalize anchor chars first (`_CANON_MAP.get(anchor_ch, anchor_ch)`) so that `。` correctly resolves to `.` equivalents in translated text.

**Files Modified:**
- `functions/postprocess.py` — `BRACKET_EQUIV`, `QUOTE_EQUIV`, `_CANON_MAP`, `_CLOSING_TO_OPENING`, `_RECOVERY_ANCHOR_CHARS`, `_normalize_bracket()`, `recover_bracket_balance()` (rewritten), `_find_anchor_near()` (new), `_try_anchor_bracket_insert()` (new), `recover_quote_balance()` (rewritten)

**Tests:** `dev/test_recovery_anchor.py` — 73 tests (9 bracket equivalence, 7 bracket anchor insertion, 2 NEEDS_RETRY, 6 quote equivalence, 4 quote anchor insertion, 2 quote NEEDS_RETRY, 10 _find_anchor_near, 6 _try_anchor_bracket_insert, 4 _normalize_bracket, 6 recover_line integration, 5 module constants, 12 edge cases). Plus `dev/test_postprocess_fixes.py` — 9 existing bracket/quote tests all passing.

---

### BUG FIX: Preserve-Action Code Patterns Not Validated or Recovered
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix the pipeline so that code patterns with `action='preserve'` are validated after translation and recovered during postprocessing. The bug manifested as `{アンカー}` at idx 8 being translated as `{anchor}` with no validation, recovery, retry, or QA flagging.

**Root Causes:**
1. `validate_translation_comprehensive()` had no `code_patterns` parameter — preserve-action patterns were never validated during translation.
2. `validate_code_patterns_preserved()` results were treated as warnings-only in `validate_line_post()`, not errors.
3. `recover_line()` had no code pattern recovery mechanism at all.
4. `RetryReason` enum lacked a code pattern entry.
5. GUI translation step applied translations without content validation for code patterns.

**Changes:**
1. **`functions/postprocess.py`** — Added `RecoveryType.CODE_PATTERN` to enum. New `recover_code_patterns(text, original, code_patterns)` function: for each preserve-action pattern, uses `generate_regex_pattern()` to find occurrences in original; if missing in translation, scans for content in same delimiters not present in original (translated substitutes); replaces first match or flags `NEEDS_RETRY`. New `_detect_delimiters(pattern)` helper identifies `{}`, `[]`, `<>`, `()`, fullwidth, CJK delimiter pairs, and doubled delimiters such as `{{...}}` so preserve restores replace the whole token instead of leaving trailing braces. Integrated into `recover_line()` pipeline between placeholder and bracket recovery. Updated `recover_batch()`, `PostProcessManager`, and `create_postprocess_manager()` factory.
2. **`functions/validation.py`** — Added `RetryReason.CODE_PATTERN_TRANSLATED` to enum. Added `code_patterns` parameter to `validate_translation_comprehensive()` and `validate_batch_comprehensive()`. Added check #7 that calls `validate_code_patterns_preserved()` and adds missing patterns as errors + retry reasons. Changed `validate_line_post()` to treat code pattern failures as errors instead of warnings.
3. **`gui/steps/postprocess.py`** — Loads `code_patterns` from `ManifestManager.get_code_patterns()` before the processing loop. Passes `code_patterns` to `recover_line()` calls.
4. **`gui/steps/translate.py`** — After applying translations, validates preserve-action code patterns using `recover_code_patterns()`. If recovery succeeds, updates the translation. If recovery fails, marks line as `NEEDS_REVIEW` for QA.
5. **`dev/test_code_pattern_actions.py`** — Updated `test_validate_line_post_with_code_patterns` to check `result.errors` instead of `result.warnings` to match new severity.

**Tests:** `dev/test_code_pattern_recovery.py` — 29 tests (8 delimiter detection, 9 recovery scenarios, 4 validation, 3 comprehensive validation, 3 recover_line integration including the double-curly regression, 2 end-to-end idx 8 bug scenario). All 75 code pattern tests passing (29 new + 46 existing in test_code_pattern_actions.py).

---

### BUG FIX: Deduplication Reduplication Broken in Postprocessing
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Fix reduplication so that deduplicated lines (`__DEDUP__`) are correctly restored to the source line's translated/postprocessed text after clicking Apply Rules (preprocessing) and Apply Postprocessing.

**Root Causes:**
1. `_restore_dedup_lines()` and the main postprocessing loop read preprocessing step data from `self.session.get_step(3).data` (SessionState), but `_update_step_data()` in the preprocessing step saves data via `self.set_step_data()` which writes to ManifestManager when loaded — NOT to the session. The two stores are not synchronized, so `dedup_map` was never seen by the postprocessing step.
2. `_best_text()` resolution chain was `postprocessed → translated → original`, missing `preprocessed`. The intended priority per spec §5.9 is `postpro → tl → prepro → orig`.
3. `PostprocessLine` dataclass lacked a `preprocessed` field, making it impossible to resolve from prepro when tl is empty (e.g., when running postprocessing before translation).
4. Standard dedup restoration handled only direct sources, so chains such as `1636 -> 626 -> 619` failed when a standard dedup source was itself an aggressive dedup duplicate.

**Changes:**
1. **Data source fix** — Both `_restore_dedup_lines()` and the main postprocessing loop now read step 3 data from ManifestManager first (`mgr.get_step_data(3)`), falling back to session only when ManifestManager is unavailable.
2. **`PostprocessLine.preprocessed` field** — Added `preprocessed: str = ""` field to the dataclass. `_refresh_lines()` now batch-reads `prepro` values from the manifest and populates this field.
3. **`_best_text()` updated** — Resolution chain is now `postprocessed → translated → preprocessed → original`, matching the spec priority and skipping `__DEDUP__` sentinels at each level.
4. **Chained dedup resolution** — `_restore_dedup_lines()` now resolves dedup text recursively across `dedup_map` and `aggr_dedup_map`, so a standard duplicate can inherit text from an aggressive dedup source after number restoration.

**Files Modified:**
- `gui/steps/postprocess.py` — `PostprocessLine` (preprocessed field), `_refresh_lines()` (prepro map), `_best_text()` (4-field priority), `_restore_dedup_lines()` (ManifestManager data source + recursive chain resolution), main loop (ManifestManager data source)

**Tests:** `dev/test_dedup_pipeline.py` — 37 tests with chained dedup/aggressive-dedup restoration coverage

---

### BUG FIX: LightVN Detection, Tag Propagation, Input Step Fixes (4 Fixes)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Fix LightVN parser failing to detect files like `chara_make.txt` (whose characteristic patterns appear after line 200), ensure parser extraction tags propagate to manifest `tag`, fix `messagebox` UnboundLocalError in Input step, and fix source file copy matching wrong files in subdirectories.

**Root Causes:**
1. `can_handle()` only checked for `~【` and `~文字` in first 200 lines — files with `~絵` or `栞` as only early patterns were rejected.
2. `_extract_lines()` discarded `ExtractedLine.tag` values from `extract_tagged()` — tags never reached the manifest.
3. Two `from tkinter import messagebox` local imports inside `_load_selected_paths()` created local variable bindings that shadowed the module-level import, causing `UnboundLocalError` when code paths did not enter those branches.
4. `_copy_originals_to_project()` matched LoadedFile to filedir entries by filename only (`path.name == entry_name`), failing when identically named files exist in different subdirectories.

**Changes:**
1. **LightVN `can_handle()` expanded** — Added `_DETECT_PATTERNS` set (`{"~【", "~文字", "~ボタン", "~絵", "~効果音", "~選択"}`) and `_DETECT_LINE_PREFIXES` tuple (`("栞 ",)`). Detection now matches ANY of these patterns/prefixes in the first 200 lines.
2. **Tag propagation via `LoadedFile.tags`** — Added `tags: Optional[List[str]]` field to `LoadedFile` class. `_load_file()` extracts tags from `extract_tagged()` results. `_sync_lines_to_manifest()` sets `entry["tag"]` from tags. `_add_files_to_existing_manifest()` applies tags after `mgr.add_files()`. `_wire_parser_optionals` O8 skips lines already tagged by parser extraction.
3. **Removed local `messagebox` imports** — Deleted two `from tkinter import messagebox` statements inside `_load_selected_paths()`. The module-level import (line 15) is now the sole binding.
4. **Rel-path matching for source copy** — `_copy_originals_to_project()` now computes `base = mgr._find_common_base(all_abs)` and matches by `entry.rel_path == str(loaded_file.path.relative_to(base))` instead of filename only.

**Files Modified:**
- `formats/LightVN.py` — `_DETECT_PATTERNS`, `_DETECT_LINE_PREFIXES`, `can_handle()` rewritten
- `gui/steps/input_extract.py` — `LoadedFile` (tags field), `_load_file()` (tag extraction), `_sync_lines_to_manifest()` (tag from tags), `_add_files_to_existing_manifest()` (tag propagation), `_wire_parser_optionals` O8 (skip pre-tagged), `_load_selected_paths()` (removed local imports), `_copy_originals_to_project()` (rel_path matching)

**Tests:** `dev/test_lightvn_fixes.py` — 31 tests (11 can_handle expanded, 6 ~文字 menu parsing, 4 tag propagation, 2 messagebox AST check, 3 source copy rel_path, 5 full file integration)

---

### BUG FIX: Costs Additive Display Rework
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Make the Costs step token/cost display purely additive. Prompt Tokens and Cached Tokens were not additive (Cached was a subset of Prompt, so Input + Prompt ≠ Total). Cost sub-rows for Prompt Cost and Cached Input Cost were indented and conditionally hidden. Cost rounding was inconsistent.

**Changes:**
1. **Prompt Tokens display** — Now shows `prompt_tokens − cached_tokens` (non-cached portion) so that Input + Prompt + Cached = Total Input.
2. **Cost display layout** — All four cost rows (Input, Prompt, Cached, Output) are now primary non-indented rows that sum to Total. "Cached Input Cost:" renamed to "Cached Cost:". Rows always shown (no conditional hiding).
3. **input_cost semantics** — `EstimationResult.input_cost` now stores content-only cost (content_tokens × rate), not the combined input+prompt+cached bundle.
4. **Direct 4-component calculation** — `_do_estimation()` no longer uses `estimate_cost()` + cache savings subtraction. Computes content_cost, prompt_cost, cached_cost, output_cost directly.
5. **Ceil-to-cents rounding** — Module-level `_ceil_to_cents()` extracted from `estimate_cost()`. New `_fmt_cost()` helper formats all displayed dollar amounts rounded up to the next cent.
6. **All three recalculation paths updated** — `_do_estimation()`, `_recalculate_costs_for_mode()`, and `_reprice_for_model()` all use the same 4-component pattern and `_fmt_cost()`.

**Mathematical equivalence:** Total cost is unchanged. `content × rate + (prompt − cached) × rate + cached × cached_rate` = `(content + prompt − cached) × rate + cached × cached_rate` (the old formula).

**Files Modified:**
- `gui/steps/costs.py` — All calculation and display changes

**Tests:** `dev/test_costs_additive_display.py` — 30 tests (ceil-to-cents, fmt_cost, EstimationResult semantics, additive calculation, recalculate/reprice structure, prompt token display, label layout, always-shown rows, _do_estimation calculation)

---

### BUG FIX: Glossary ↔ Term Translation Dual-Storage Desync (3 Fixes)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix Term Translation results not showing in the Information step's Glossary widget, and fix editing one glossary entry causing other entries (including translations) to disappear.

**Root Cause:** Characters are stored in TWO manifest locations: top-level `characters` key (written by `save_character_notes()` in Analysis step's Term Translation) and nested `step_state.Information.data.metadata.characters` (written by `on_leave()` in Information step). In `on_enter()`, `_load_characters_from_manifest()` loaded correct data from the authoritative top-level key, but `_load_metadata()` ran AFTER and completely replaced `self._metadata` with stale step_state data — wiping the translations. Additionally, `on_leave()` only saved to step_state (not top-level), so the two storage locations diverged over time. `_import_analysis_speakers()` also did not persist auto-imported speakers to the top-level key.

**Changes:**
1. **`on_enter()` load order** — Moved `_load_characters_from_manifest()` and `_load_code_patterns_from_manifest()` to AFTER `_load_metadata()`, so authoritative top-level manifest data always overrides stale step_state data.
2. **`on_leave()` dual-storage sync** — Added `_save_characters_to_manifest()` and `_save_code_patterns_to_manifest()` calls after `set_step_data()`, keeping top-level manifest keys in sync with step_state on every tab change.
3. **`_import_analysis_speakers()` persistence** — Added `_save_characters_to_manifest()` call after importing speakers, ensuring auto-imported entries are immediately persisted to the authoritative top-level key.

**Files Modified:**
- `gui/steps/information.py` — `on_enter()` reordered, `on_leave()` sync added, `_import_analysis_speakers()` persistence added

**Tests:** `dev/test_glossary_term_link.py` — 19 tests (2 character round-trip, 3 on_enter load order AST, 2 on_leave sync AST, 1 import persistence AST, 4 dual-storage simulation, 3 CharacterInfo preservation, 2 ProjectMetadata preservation, 2 load guard)

---

### BUG FIX: Batch 79 — Translation Pipeline Issues (6 Fixes)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Fix 6 issues found during a sample Japanese→English translation run.

**Changes:**
1. **API Log pushed to background** — `APILogViewDialog.__init__` now calls `self.lift()` at the end to stay visible above other windows. `TranslationProgressWindow` no longer calls `grab_set()` (non-modal) so users can interact with the API Log during translation.
2. **Global glossary missing from prompts** — Created `load_all_glossary_entries()` in `manifest_fields.py` that merges project-specific entries with global glossary entries (respects `use_global` flag, deduplicates by source, skips inactive). Updated all 4 call sites in `translate.py` (×2) and `costs.py` (×2).
3. **Ellipsis-only lines still sent to API** — Enhanced `is_placeholder_only()` in `prompt_builder.py` with `_DOTS_ONLY_RE` regex to detect dot/ellipsis-only lines (`"..."`, `".................."`, `"…"`, `"．．．"`).
4. **Ellipsis compression before symbol conversion** — Changed `ellipsis_compression` priority from P20→P36 in `process_order.py` so it runs after symbol conversion (P30) and width conversion (P35). Reordered `mode_adapter.py` accordingly. Enhanced `ELLIPSIS_PATTERN` and `compress_ellipsis_line()` to handle fullwidth period (`．`) and Unicode ellipsis (`…`).
5. **Dedup/placeholder lines never reach 100% progress** — Added pre-translation scan in `translate.py` that marks placeholder-only and empty lines as `LineStatus.SKIPPED` before progress initialization, with correct `skipped_lines` count.
6. **Cached/reasoning tokens not shown in API Log** — Added `reasoning_tokens` extraction to both `log_pair` calls in `api_client.py` (main translation + line-by-line).

**Files Modified:**
- `gui/dialogs/api_log_view.py` — `self.lift()` in `__init__`
- `gui/steps/translate.py` — removed `grab_set()`, glossary loader swap, pre-scan skip logic
- `gui/steps/costs.py` — glossary loader swap (2 sites)
- `functions/manifest_fields.py` — `load_all_glossary_entries()` function
- `functions/prompt_builder.py` — `_DOTS_ONLY_RE` regex, `is_placeholder_only()` enhanced
- `functions/process_order.py` — `ellipsis_compression` P20→P36
- `gui/helpers/mode_adapter.py` — reordered symbol before ellipsis
- `modi/standard_mode.py` — `ELLIPSIS_PATTERN` + `compress_ellipsis_line()` enhanced
- `functions/api_client.py` — `reasoning_tokens` in both `LogEntryReceived` calls

**Tests:** `dev/test_bugfix_batch_79.py` — 33 tests (2 API Log visibility, 4 global glossary merge, 14 ellipsis detection, 5 compression order, 3 progress tracking, 5 cached tokens)

---

### BUG FIX: Single-Instance API Log and Global Options Windows
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Let the translation progress window open the same non-blocking API Log window as the main window, and prevent duplicate API Log and Global Options windows across the GUI.

**Changes:**
1. **Shared API Log window reuse** — Added `APILogViewDialog.open_or_focus()` keyed on the root window. Reopening API Log now lifts and focuses the existing window instead of creating duplicates.
2. **Translation progress API Log access** — Added an `API Log` button to `TranslationProgressWindow` so users can open or foreground the shared API Log while translation is running.
3. **Shared Global Options reuse** — Added `GlobalOptionsDialog.open_or_focus()` plus deduplicated save listeners so the main menu and Translation step quick-access buttons reuse the same dialog and can still target the correct section.
4. **Root-window helpers** — `gui/app.py` now exposes shared open/focus methods for API Log and Global Options so child UI components route through one registry.

**Files Modified:**
- `gui/dialogs/api_log_view.py` — `open_or_focus()`, root-window registration/cleanup
- `gui/dialogs/global_options.py` — `open_or_focus()`, save-listener dedup, root-window registration/cleanup
- `gui/app.py` — shared `open_api_log_dialog()` / `open_global_options_dialog()` helpers
- `gui/steps/translate.py` — translation progress `API Log` button, quick-access routing through shared dialogs
- `dev/test_gui_dialogs.py` — 5 new dialog reuse tests

**Tests:** `dev/test_gui_dialogs.py` — 21 tests; `dev/test_bugfix_batch_79.py` — 33 tests. Focused pytest run: 54 tests passing.

---

### TASK 80: Unified Request Builder — All Features Use Same Prompts
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Ensure Estimation (Step 4), Request Preview, and Start Translation (Step 5) all use the same request builder so prompts are guaranteed identical. Fix API Log to store full system prompts.

**Problem:** Data gathering for prompts was duplicated 5+ times (costs.py × 3, translate.py × 2), with costs.py missing fallback field merging for source_language/target_language/genre. This caused Estimation to produce different prompts than Translation. API Log truncated system_prompt to 2000 chars, and line-by-line mode omitted system_prompt entirely.

**Changes:**
1. **`gather_prompt_data(mgr)`** — New function in `prompt_adapter.py` centralises ALL data gathering (metadata with fallback field merging, glossary entries, characters, code patterns, POV, sample lines).
2. **`build_request_prompt(prompt_data)`** — New wrapper in `prompt_adapter.py` calls `build_full_system_prompt()` with gathered data. All features call this instead of `build_full_system_prompt()` directly.
3. **costs.py `_get_prompt_tokens()`** — Replaced ~40-line data-gathering block with `gather_prompt_data()` + `build_request_prompt()`.
4. **costs.py `_get_static_prompt_tokens()`** — Replaced ~30-line data-gathering block with `gather_prompt_data()` + `build_request_prompt(chunk_lines=[])`.
5. **costs.py `_compute_per_request_prompt_overhead()`** — Replaced ~45-line data-gathering block with `gather_prompt_data()` once + `build_request_prompt(chunk_lines=...)` per request.
6. **translate.py `_build_system_prompt_from_manifest()`** — Replaced ~40-line data-gathering block with `gather_prompt_data()` + `build_request_prompt()`.
7. **translate.py `_build_preview_requests()`** — Replaced ~70-line data-gathering block with `gather_prompt_data()`. Per-chunk prompt now uses `build_request_prompt()`.
8. **API Log full prompt** — Removed `[:2000]` truncation on `system_prompt` in `api_client.py` main translation log.
9. **Line-by-line log** — Added missing `system_prompt=system_prompt` field to `LogEntrySent` in line-by-line path.

**Files Modified:**
- `gui/helpers/prompt_adapter.py` — `gather_prompt_data()` + `build_request_prompt()` functions
- `gui/steps/costs.py` — 3 methods updated to use unified functions
- `gui/steps/translate.py` — 2 methods updated to use unified functions
- `functions/api_client.py` — removed truncation + added line-by-line system_prompt
- `dev/test_prompt_overhead_fix.py` — 2 tests updated for new code pattern
- `dev/test_unified_request_builder.py` — 28 new tests

**Tests:** `dev/test_unified_request_builder.py` — 28 tests (7 gather_prompt_data, 10 build_request_prompt, 7 unified call sites, 2 API Log, 2 identical output)

---

### BUG FIX: Input Step Non-Destructive Addition, Import Dialog, OutputFormat Crash
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Fix Input button to non-destructively add files to existing manifests, add Import Translation selection dialog, fix OutputFormat ValueError crash, rename preview columns to Project/File with 1-based indexing.

**Changes:**
1. **OutputFormat ValueError** — Added `_safe_output_format()` in `output_inject.py` to prevent crash on empty/invalid format string (defaults to TXT).
2. **Non-Destructive File Addition** — `ManifestManager.add_files()` merges new files into sorted filedir, rewritting all idx values contiguously while preserving existing line data (tl, prepro, tags, etc.). `_load_selected_paths()` now detects add-to-existing mode, validates source root, skips already-loaded files, and calls `_add_files_to_existing_manifest()` for new files only.
3. **Preview Column Rename** — "Idx" → "Project" (1-based global idx), "#" → "File" (1-based per-file line number).
4. **Import Translation Dialog** — `_ImportTranslationDialog` Toplevel with Line Fields group (Preprocessed, Tags, Translated, Postprocessed, Wordwrap, QA, skip option) and Settings Sections group (Analysis, Information, Preprocessing, Costs, Translation, Postprocessing, Wordwrap, QA/Validation, File Settings). Per-section import logic via `_import_line_fields()` and `_import_settings_sections()`.

**Files Modified:**
- `gui/steps/output_inject.py` — `_safe_output_format()`, 7 call sites updated
- `gui/steps/input_extract.py` — `_ImportTranslationDialog` class, `_add_files_to_existing_manifest()`, `_import_line_fields()`, `_import_settings_sections()`, modified `_load_selected_paths()` and `_on_import_translations()`, preview headings
- `functions/manifest_manager.py` — `add_files()` method

**Tests:** `dev/test_input_import_fixes.py` — 23 tests (8 OutputFormat, 8 add_files, 3 import lines, 4 import sections)

---

### BUG FIX: si_preset Lost on Tab Change
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: si_preset value disappears from manifest when switching tabs because `ProjectMetadata.to_dict()` and `from_dict()` did not include `si_preset`.

**Solution:** Added `si_preset` field to `ProjectMetadata` dataclass, `to_dict()`, `from_dict()`, `_collect_metadata()`, and `_populate_form()` in `gui/steps/information.py`.

**Files Modified:** `gui/steps/information.py`
**Tests:** `dev/test_io_examples.py::TestProjectMetadataPersistence` — 7 tests

---

### BUG FIX: System Instructions Reset on Re-enter
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Default system instructions text overwrote user edits every time the Information tab was entered because `_ensure_default_texts()` ran unconditionally and empty manifests had no seeded defaults.

**Solution:** Two-pronged fix:
1. `manifest_manager.py::_create_empty_manifest()` now seeds `info_metadata` defaults (system_instructions, si_preset, io_examples, languages, toggles) via new `_get_info_defaults()` method
2. `_ensure_default_texts()` rewritten as fallback-only — only fills truly empty fields in manifests that somehow have no defaults

**Files Modified:** `functions/manifest_manager.py`, `gui/steps/information.py`
**Tests:** `dev/test_io_examples.py::TestManifestDefaultSeeding` — 4 tests

---

### FEATURE: I/O Examples Generation
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 6 hours

Goal: Generate I/O (input/output) example blocks in the system prompt to improve translation quality. Mode selectable per-project: disabled, fill (cache-aligned), 1500, or 2500 tokens.

**Implementation:**
- New module `functions/io_examples.py` — `_Example` dataclass with language-keyed fields (`jp`, `en`), `_resolve_example_keys()` for language resolution, example bank (~35 pairs), priority scoring, code pattern boosting, sequential LineN renumbering, tiktoken token counting with heuristic fallback
- UI dropdown in Information Step (System Instructions section) with 4 modes
- `build_full_system_prompt()` in `prompt_adapter.py` injects examples at slot 2b (between SI and Style)
- Never modifies System Instructions — examples are a separate prompt slot
- Language key resolution: maps lang names to `jp`/`en` keys; unknown languages fall back to `en` unless English is source or target (then `jp`)
- "fill" mode uses `calculate_fill_target()` + `get_optimal_cache_size()` to fill optimal cache boundary
- `api_config.py` extended with `optimal_cache_size` model setting key, `_CACHE_DEFAULTS`, `get_optimal_cache_size()`
- `api_client.py` extended with `io_examples` in `_STATIC_PROMPT_SECTIONS`
- Manifest seeding: `io_examples` default "disabled" seeded at manifest creation

**Files Modified:**
- `functions/io_examples.py` (NEW)
- `gui/steps/information.py` — ProjectMetadata, UI dropdown, _on_io_examples_changed()
- `gui/helpers/prompt_adapter.py` — slot 2b injection
- `functions/api_config.py` — optimal_cache_size key, get_optimal_cache_size()
- `functions/api_client.py` — _STATIC_PROMPT_SECTIONS
- `functions/manifest_manager.py` — _create_empty_manifest, _get_info_defaults

**Tests:** `dev/test_io_examples.py` — 63 tests across 10 classes (all passing)

---

### IMPROVEMENT: Fill Mode Cache Calculation & Preview Request IO Examples
**Priority:** HIGH | **Status:** ✅ COMPLETE

Goal: Ensure fill mode calculates correctly by subtracting ALL static prompt sections from optimal cache size (not just slots 1-2). Add IO Examples to Preview Requests. Verify static prompt consistency with tests.

**Implementation:**
1. **Fill mode fix** — `build_full_system_prompt()` at slot 2b now pre-computes tokens for ALL later static sections (style, tone, summary, genre, protagonist, POV, context-type prompt) using `estimate_tokens()` before calculating fill target. Replaces the old incomplete calculation that only had access to slots 1-2 in `breakdown`.
2. **Preview Request IO Examples** — Added `io_examples` to `FILTER_PARTS` (after system_instructions, before style), `SECTION_DESCRIPTIONS`, `PreviewRequest` dataclass, and `_build_preview_requests()` generation logic with fill mode support.
3. **Static prompt consistency tests** — `TestStaticPromptConsistency` (8 tests): verifies static prefix identical across chunks, all sections present, IO determinism, LineN key consistency, fill uses full static tokens, fill respects cache boundary, no dynamic content without chunks, breakdown matches _STATIC_PROMPT_SECTIONS. `TestFillModeCalculation` (4 tests): empty prompt fill, at-optimal returns 0, never negative, more static → less IO fill.

**Files Modified:**
- `gui/helpers/prompt_adapter.py` — pre-compute all static section tokens at slot 2b
- `gui/steps/translate.py` — FILTER_PARTS, SECTION_DESCRIPTIONS, PreviewRequest, _build_preview_requests
- `dev/test_io_examples.py` — 12 new tests (TestStaticPromptConsistency, TestFillModeCalculation)

**Tests:** `dev/test_io_examples.py` — 63 tests across 10 classes (all passing)

---


PENDING TASKS - Full Table View

### FEATURE: Full Table View Dialog
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Spreadsheet-like view of all manifest line entries accessible via menu bar.

**Implementation:**
- Added `gui/dialogs/table_view.py` — FullTableViewDialog (Toplevel)
- Menu bar restructured: File (dropdown), Full Table View (direct), Options (direct), Help (dropdown)
- Edit menu removed; Tools menu replaced by direct Options entry
- Toolbar removed from app.py (all access via menu bar)
- 11 columns with display names: Line # (idx), Tags (tag), Original (orig), Preprocessed (prepro), Translated (tl), Postprocessed (postpro), Wrapped (wordwr), Overwrite, Quality Assurance (qa_overwrite), Log, Tags (Internal) (tags)
- Removed deprecated columns: edited_prepro, edit1-3, tlc1-3
- Column filter: slim tk.Menu dropdown with Show All / Show Visible / Show Latest presets + individual toggles
- All columns hideable including Line #; Tags hidden by default (DEFAULT_HIDDEN)
- Column selection bar: "Select / Selected" labels per column for search/replace scoping
- Sort indicators: ▲/▼ in column headers; tracks sort column and direction
- Two-row toolbar layout: search row (top), replace row (bottom)
- Results Only mode (inverted Show Misses) with ◀ / ▶ navigation
- Non-editable: Line # and Original (orig allows read-only copy via double-click)
- Tags and Line # now searchable (removed from METADATA_FIELDS)
- Search/replace scoped to visible or selected columns
- File filter dropdown with larger font (size 11)
- Hierarchical file filter dropdown with folder navigation
- Cell editing (double-click), deletion (Del), multi-select, column clearing
- Pagination: Show All / Show X (default 100), configurable page size
- Save/Reset/Diff operations against manifest with change tracking
- Close prompt for unsaved changes

**Files Modified:**
- `gui/dialogs/table_view.py` — FullTableViewDialog, _FileFilterDropdown (removed _ColumnFilterDropdown)
- `gui/app.py` — Menu bar restructured (removed Edit, Tools, toolbar)

**Tests:** `dev/test_table_view.py` — 124 tests (all passing)

---

PENDING TASKS - Costs TAB

### BUG FIX: Section Toggle Persistence
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Section Enabled/Disabled toggle states must survive tab changes and be respected by Preview Request and Estimation.

**Root Cause:** `on_leave()` called `ProjectMetadata.to_dict()` which does NOT include
`*_enabled` flags, then replaced the entire metadata dict via `set_step_data()`. This
erased toggle states written by `_toggle_section_enabled()` via `set_info_metadata_field()`.

**Solution:** Modified `on_leave()` and `_save_metadata()` to read current BooleanVar values
for all seven toggle flags and merge them into the metadata dict after `to_dict()` but before
`set_step_data()`. This preserves flags across tab changes.

**Files Modified:**
- `gui/steps/information.py` - Fixed on_leave() and _save_metadata() to merge toggle states

**Tests:** `dev/test_section_toggles.py` — 35 tests (all passing)

---

### BUG FIX: Preview Request Ignores Section Toggles
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Preview Request must respect Enabled/Disabled toggles — disabled sections must not
appear in the request preview.

**Root Cause:** `_build_preview_requests()` in translate.py built labeled sections for all
fields regardless of `*_enabled` flags. `build_full_system_prompt()` already gated sections
correctly, but the preview builder did not.

**Solution:** Added enabled flag reads from metadata in `_build_preview_requests()`. Each
labeled section (sys_instructions, style, tone, summary, genre, glossary, characters) is
now gated by its corresponding `*_enabled` flag, matching `build_full_system_prompt()`.

**Files Modified:**
- `gui/steps/translate.py` - Gated preview sections by enabled flags in _build_preview_requests()

**Tests:** `dev/test_section_toggles.py::TestPreviewSectionGating` — 6 tests (all passing)

---

### BUG FIX: Redundant Save Button Removal
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 10 minutes

Goal: Remove redundant Save button from Information step header.

**Root Cause:** The Save button duplicated auto-save behavior (manifest saves on every tab
change via on_leave → set_step_data) and showed a misleading "Saved" messagebox.

**Solution:** Removed Save button from header UI. Retained `_save_metadata()` as internal
helper without messagebox for programmatic use.

**Files Modified:**
- `gui/steps/information.py` - Removed Save button, removed messagebox from _save_metadata()

**Tests:** `dev/test_section_toggles.py::TestSaveButtonRemoved` — 1 test (all passing)

---

### BUG FIX: New Project Manifest Flush
**Priority:** CRITICAL | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: File → New Project must fully flush all cached state from every step tab.

**Root Cause:** `_on_new_session()` reset ManifestManager and SessionState but did NOT
clear instance-level cached state in step tabs (e.g., `_loaded_files`, `_lines`,
`_analysis_results`). Old project data leaked into new sessions.

**Solution:** Added `on_new_project()` lifecycle method to `BaseStep` (invalidates cache)
with overrides in all 10 step tabs clearing their specific cached attributes. Called from
`_on_new_session()` in `gui/app.py` before `on_enter()`.

**Files Modified:**
- `gui/steps/base.py` - Added `on_new_project()` method
- `gui/steps/input_extract.py` through `gui/steps/output_inject.py` - Added overrides
- `gui/app.py` - Updated `_on_new_session()` to call `tab.on_new_project()`

**Tests:** `dev/test_new_project_flush.py` — 45 tests (all passing)

---

### BUG FIX: Up Button Emoji Spacing
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 10 minutes

Goal: Fix excessive spacing between arrow symbol and "Up" text in UnifiedInputDialog.

**Root Cause:** The Up button used emoji `⬆️` (U+2B06 + U+FE0F variation selector) which
renders wider than expected on Windows due to emoji presentation.

**Solution:** Replaced with plain Unicode arrow `↑` (U+2191) in `gui/dialogs/input_dialog.py`.

**Tests:** `dev/test_input_dialog_ui.py::TestUpButtonText` — 2 tests (all passing)

---

### BUG FIX: Hide Auto-Pipeline Option
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 10 minutes

Goal: Auto-Pipeline dropdown must be hidden (not removed) in UnifiedInputDialog pending rework.

**Solution:** In `gui/dialogs/input_dialog.py` `_build_options_panel()`, the pipeline Label
and Combobox are still created (for future rework) but their `.pack()` calls are commented out.
The `_pipeline_var` remains functional so existing code referencing it won't break.

**Tests:** `dev/test_input_dialog_ui.py::TestAutoPipelineHidden` — 3 tests (all passing)

---

### BUG FIX: Debug Print Statements in Global Options
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 15 minutes

Goal: Remove all DEBUG print statements from GlobalOptionsDialog and app.py that polluted
console output every time the Options dialog was opened.

**Root Cause:** 23 debug `print("DEBUG:...")` statements were left in `global_options.py`
and 5 in `app.py` from development/troubleshooting and were never removed.

**Solution:** Removed all `print("DEBUG:...")` statements. Retained existing `logger.debug()`
calls which respect the logging configuration.

**Files Modified:** `gui/dialogs/global_options.py`, `gui/app.py`

---

### BUG FIX: API Log View Crash on entry.status.value
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Fix AttributeError crash in API Log View that caused log entries to show only a
checkmark icon with no other content.

**Root Cause:** `_render_entry()` used `entry.status.value.upper()` but `LogEntry.status`
is typed as `str` (not `LogStatus` enum). The `.value` accessor only works on enum instances
but after deserialization status is a plain string. Same issue in `_entry_to_searchable()`.

**Solution:** Changed `entry.status.value.upper()` → `entry.status.upper()` in
`_render_entry()` and `entry.status.value` → `entry.status` in `_entry_to_searchable()`.
Dict lookups using `LogStatus` enum keys still work because `LogStatus(str, Enum)` compares
equal to its string value.

**Files Modified:** `gui/dialogs/api_log_view.py`
**Tests:** `dev/test_api_log.py::TestStatusStringCompatibility` — 5 tests (all passing)

---

### BUG FIX: GlobalOptions Mousewheel Error After Destroy
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Fix "invalid command name" TclError spam when scrolling after closing Global Options.

**Root Cause:** `_build_utility_section()` used `canvas.bind_all("<MouseWheel>", ...)` which
registers a global binding. When the dialog was destroyed, the binding persisted but the canvas
widget no longer existed, causing "invalid command name" errors on every mouse wheel event.

**Solution:** Two-part fix:
1. Changed `_build_utility_section()` to use `<Enter>`/`<Leave>` binding pattern (matching
   the existing `_build_security_section()` approach): binds mousewheel on canvas enter,
   unbinds on canvas leave.
2. Added `self.unbind_all("<MouseWheel>")` to `destroy()` as safety net to clean up any
   lingering global mousewheel bindings before widget destruction.

**Files Modified:** `gui/dialogs/global_options.py`

---

### BUG FIX: Manifest Save File Locking (WinError 32/5)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 minutes

Goal: Fix concurrent manifest save crashes caused by autosave thread and main thread racing
on `os.replace()`.

**Root Cause:** `save()` did not acquire `_autosave_lock`, so the autosave background thread
and the main thread could both write to the `.tmp` file and call `os.replace()` simultaneously.
On Windows this caused WinError 32 ("file being used by another process") and WinError 5
("Access denied").

**Solution:** Wrapped `save()`'s critical section with `self._autosave_lock`. Added retry
logic (3 attempts with back-off) for `os.replace()` to handle transient Windows file locks
from antivirus scanning or other processes.

**Files Modified:** `functions/manifest_manager.py`
**Tests:** `dev/test_api_log.py::TestManifestSaveThreadSafety` — 2 tests (all passing)

---

### BUG FIX: Gender Inference Freezes Window
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Fix UI freeze during LLM-based gender inference which blocked the main thread for
the duration of all API calls.

**Root Cause:** `_infer_character_genders()` ran LLM API calls (`infer_gender_llm()`)
synchronously on the Tkinter main thread. Each API call (3-30 seconds) blocked the event
loop, making the window completely unresponsive. The progress dialog with
`update_idletasks()` only helped between calls, not during them.

**Solution:** Refactored the LLM pass to use a background thread with queue-based
communication:
1. Script pass (fast, CPU-bound) remains synchronous with `update_idletasks()`
2. LLM pass runs in a `threading.Thread` with a `queue.Queue` for messages
3. Main thread polls the queue via `after(100, _poll_llm)` to update progress
4. Added Cancel button to abort the LLM pass via `threading.Event`
5. Completion callback `_finish_inference()` handles dialog close, refresh, and
   notification on the main thread

**Superseded by:** Gender Inference Batch Optimization (below) — script pass also
moved to background thread with batch processing via `infer_genders_batch()`.

**Files Modified:** `gui/steps/information.py`

---

### FEATURE: Prompt Caching (OpenAI)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement OpenAI prompt caching support for gpt-4o+ models to reduce input token
costs by up to 50% and latency by up to 80%.

**Description:** OpenAI automatically caches identical prompt prefixes (≥1024 tokens)
across API requests. The system prompt assembly order (§5.2) already places static
sections (slots 1-7) before dynamic sections (slots 8-10), which is optimal for
prefix-based caching. Implementation adds model detection, extended 24h retention
support for gpt-4.1/gpt-5 models, cached token tracking in logs/stats, and
configurable APIConfig fields.

**Solution:**
- Confirmed prompt ordering is already cache-optimal (static before dynamic)
- Added `prompt_cache_enabled`, `prompt_cache_retention`, and `prompt_cache_key` to APIConfig
- `supports_prompt_caching()` restricted to `provider == "openai"` (Gemini excluded)
- Added `supports_extended_cache_retention()`, `get_prompt_cache_params()` (returns key + retention)
- Injected cache parameters into `_translate_chunk()` API call
- Tracked cached tokens from `usage.prompt_tokens_details.cached_tokens`
- Tracked reasoning tokens from `usage.completion_tokens_details` (reasoning, accepted/rejected prediction)
- Added cache hit rate, savings, and cached token counts to all log outputs
- `generate_prompt_cache_key(project_name, created_at)` — format `"{alpha5}-{seconds}"`
- Follow-up fix: the auto-generated OpenAI `prompt_cache_key` is now actually resolved from manifest metadata, injected into both chunked and line-by-line requests, and exposed in Preview Requests plus the structured API Log Sent block
- `check_static_prompt_cache_status(token_breakdown)` — ok/suggest/warn classification
- Update button now calls `refresh_models()` + `reload_model_pricing()` to save to API.ini
- Available Models: added Cached Input filter, inverted Thinking filter, Save button, Cached $/1M column
- Costs step: `estimate_cost()` supports `cached_tokens` param, Prompt/Cached Input Cost rows, Cached $/1M in comparison table

**Files Modified:**
- `functions/api_client.py` — APIConfig fields, model lists, helper methods, param injection, token tracking, log updates, generate_prompt_cache_key, check_static_prompt_cache_status
- `functions/config.py` — `estimate_cost()` cached_tokens support
- `gui/dialogs/global_options.py` — Filters, Save button, Update button fix, Cached $/1M column
- `gui/steps/costs.py` — EstimationResult extended, Cached $/1M column, Prompt/Cached Input Cost rows
- `dev/test_prompt_caching.py` — Comprehensive test file (110 tests)

**Tests:** `dev/test_prompt_caching.py` — 110 tests (all passing)

### BUG FIX: OpenAI Prompt Cache Key Visibility + Wiring
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fix the missing OpenAI prompt-cache-key wiring so the auto-generated key is not just documented, but actually visible and used.

**Problem:** `generate_prompt_cache_key(project_name, created_at)` already existed, but the generated key was not flowing into live request metadata. Users therefore could not verify prompt cache routing in Preview Requests or the API Log, and line-by-line requests were at risk of omitting the same metadata as chunked requests.

**Solution:**
- Added shared helpers to resolve the effective prompt cache key and build OpenAI cache params from provider/model/project context
- `TranslationStep` now passes manifest `project_name` + `created_at` into `APIClient` before translation so auto-generated keys match the loaded project
- `_translate_chunk()` and `_translate_single_line()` both send the effective prompt cache metadata with the live OpenAI request
- Preview Requests now shows `prompt_cache_key` / `prompt_cache_retention` in both Meta and Pure JSON views
- Structured API Log sent entries now preserve the same prompt-cache metadata in `LogEntrySent.extra`
- Focused regression coverage added for key resolution, preview visibility, and API log metadata persistence

**Files Modified:**
- `functions/api_client.py` — prompt-cache key resolution, shared param builder, live request wiring, structured log metadata
- `gui/steps/translate.py` — preview request metadata, API-client prompt-cache context, PreviewRequest `request_params`
- `dev/test_prompt_caching.py` — key resolution and support-helper coverage
- `dev/test_request_preview.py` — Preview Requests metadata visibility coverage
- `dev/test_api_log.py` — prompt-cache metadata persistence coverage

**Tests:** `C:/Python314/python.exe -m pytest dev/test_prompt_caching.py dev/test_request_preview.py dev/test_api_log.py`
- Result: 204 passed, 2 skipped

### FEATURE: Mistral Provider Parity
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 session

Goal: Bring the Mistral provider up to parity with the current OpenAI-compatible provider path for model refresh, prompt caching, temperature/thinking controls, rate limits, pricing metadata, and utility LLM features.

**Solution:**
- Moved prompt-cache support in `functions/api_client.py` from OpenAI-only checks to provider-driven capability lookup via `ProviderRegistry.get(...).get_cached_input_config(model)`
- Added live Mistral header-rate-limit config (`x-ratelimit-limit-req-minute`, `x-ratelimit-limit-tokens-minute`, remaining-* headers) and wired `APIClient` to choose rate-limit configs per provider instead of always seeding OpenAI
- Updated `providers/mistral_provider.py` to advertise prompt caching, `reasoning_effort`-based thinking, and provider-clamped effort levels (`none` / `high`)
- Refreshed curated Mistral fallback metadata in `functions/model_registry.py` for current live IDs (`mistral-small-latest`, `mistral-medium-3.5`, Magistral, Codestral, Ministral), including cached-input pricing and Experimental-plan defaults (`50 RPM`, `50000 TPM` observed live)
- Changed `fetch_mistral_models()` to preserve curated pricing for known live IDs while still surfacing unknown live chat-capable models with unknown pricing
- Added Mistral URL detection to `functions/CLI.py`
- Updated utility LLM paths (`functions/term_translation.py`, `functions/API2Glossary.py`) to omit `store=False` for Mistral, because the live API now rejects unsupported extra request fields with HTTP 422
- Live-verified CherryAI-native paths for model refresh/specs, main translation, model probe, term translation, gender inference, and prompt-cache accounting

**Tests:**
- `python -m pytest dev/test_api_client.py dev/test_api_providers.py dev/test_model_registry.py -q --timeout=20`
- `python -m pytest dev/test_term_translation.py -q --timeout=20`
- Live verification via CherryAI package imports against the Mistral Experimental plan key

---

### TASK 25.1: Analysis Results Storage
**Priority:** HIGH | **Status:** 🔲 NOT STARTED | **Effort:** 2 hours

Goal: Store analysis results (line counts, token estimates) in manifest.

**Field Mappings:**
- Input Lines → `InputLines` (int)
- Input Tokens → `InputTokens` (int)
- Output Tokens → `OutputTokens` (int)

**Files to Modify:**
- `gui/steps/estimate.py` - Save analysis results to manifest
- `gui/steps/analysis.py` - Write results to manifest after analysis

**Tests to Add:**
- `dev/test_estimate_manifest.py`:
  - `test_analysis_results_saved`
  - `test_token_counts_loaded`

---

### TASK 40.8: Refresh Button Model Data Fetch
**Priority:** LOW | **Status:** ✅ SUPERSEDED | **Effort:** 3 hours

Superseded by model_registry.py implementation (functions/model_registry.py).
Model data is now fetched from provider APIs and persisted to API.ini.

---

### BUG FIX: Model Registry Save Criteria (structured_output filter)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Only save models with structured_output=True to the model registry INI.
Previously, all API-returned models were saved, including skeleton models that
default to structured_output=False, cluttering the registry with unusable entries.

**Root Cause:** fetch_openai_models(), fetch_google_models(), and fetch_mistral_models()
created skeleton ModelInfo for API models not in FALLBACK_MODELS with all defaults
(structured_output=False). These were saved alongside real models.

**Solution:** Added `result = [m for m in result if m.structured_output]` filter after
building the result list in all three fetch functions. Skeleton models without
structured output are now excluded. All FALLBACK_MODELS have structured_output=True
so they are preserved.

**Files Modified:**
- `functions/model_registry.py` — Added structured_output filter to fetch_openai_models(),
  fetch_google_models(), fetch_mistral_models()

**Tests:** `dev/test_model_registry.py::TestStructuredOutputFilter` — 10 tests (all passing)
  `dev/test_model_registry.py::TestFallbackData::test_all_fallback_models_have_structured_output`

---

### FEATURE: Rate Limit Probing via API Response Headers
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Fetch actual RPM and TPM for each model from OpenAI's rate limit response
headers instead of relying on hardcoded values. Remove hardcoded max_concurrent=5.

**Root Cause:** max_concurrent defaulted to 5 for all models. OpenAI does not
impose a concurrent request limit — only RPM and TPM. The hardcoded 5 was
artificially limiting throughput.

**Solution:**
- Added `_http_post_json()` helper returning (body, headers)
- Added `probe_openai_rate_limits(api_key, model_id)` that makes a minimal
  chat completion request (1 token) and reads `x-ratelimit-limit-requests` (RPM)
  and `x-ratelimit-limit-tokens` (TPM) from response headers
- `fetch_openai_models()` accepts `probe_limits=True` to probe after filtering
- `refresh_models()` passes `probe_limits` through to fetch_openai_models
- `global_options.py` `_update_models()` now calls with `probe_limits=True`
- `max_concurrent` changed from `int = 5` to `Optional[int] = None`
- Added `_derived_concurrent()` method to calculate concurrent from RPM when unset
- `to_pricing_entry()["concurrent"]` uses explicit value or derived value

**Files Modified:**
- `functions/model_registry.py` — Added probing, changed max_concurrent type,
  added _derived_concurrent
- `gui/dialogs/global_options.py` — Pass probe_limits=True in _update_models

**Tests:** `dev/test_model_registry.py::TestRateLimitProbing` — 5 tests (all passing)
  `dev/test_model_registry.py::TestDerivedConcurrent` — 6 tests (all passing)

---

### FEATURE: Header-Based Rate Limiting with Response Headers
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Implement per-model rate limiting driven by API response headers, with
the following behaviours:
1. Fetch model limits from `fine_tuning/model_limits` endpoint during Available Models Update
2. Maintain per-model runtime counters (`requests_in_window`, `tokens_in_window`)
3. Rate limit enforcement waits instead of failing
4. Reset timing from `x-ratelimit-reset-requests` and `x-ratelimit-reset-tokens`
   headers using monotonic timer (60s default)
5. Per-model tracking that never exceeds RPM/TPM limits

Token estimation: `estimated_tokens = sent_request_token_count + (input_line_token_count × 1.5)`

**Solution:**
- Created `functions/header_rate_limiter.py` — `HeaderBasedRateLimiter` class with
  `ProviderRateLimitConfig` for provider-agnostic header names
- `parse_reset_duration()` parses OpenAI duration strings ("6m0s", "1s", "200ms")
- `pre_request()` now uses a rolling 60-second TPM reservation window keyed by request start time, so concurrent sends only proceed when the active token window has room
- `pre_request()` returns a reservation ID and `update_from_headers()` can reconcile that same reservation with response usage after the request completes
- When a request would exceed TPM, the limiter sleeps until the oldest reservation expires, then retries the admission check
- Modified `providers/openai_provider.py` `send_request()` to use
  `client.chat.completions.with_raw_response.create()` — captures HTTP headers
- Added `headers: Dict[str, str]` field to `ProviderResponse` dataclass
- Modified `functions/api_client.py` `_translate_chunk()` to use `with_raw_response`
  and feed response headers into the header-based rate limiter
- `_wait_for_rate_limit()` now uses header-based limiter as primary enforcement
- Added `_init_header_rate_limiter()` to load stored RPM/TPM from API.ini on startup
- Added `fetch_openai_model_limits()` to `model_registry.py` — calls
  `GET /v1/fine_tuning/model_limits` and stores results via `api_config.set_rate_limit()`
- `refresh_models()` now calls `fetch_openai_model_limits()` after saving models

**Files Modified:**
- `functions/header_rate_limiter.py` — NEW: per-model rate limiter module
- `functions/api_client.py` — Integrated header-based limiter, `with_raw_response` API calls
- `functions/model_registry.py` — Added `fetch_openai_model_limits()`, integrated into `refresh_models()`
- `providers/__init__.py` — Added `headers` field to `ProviderResponse`
- `providers/openai_provider.py` — `with_raw_response` in `send_request()`, headers in `parse_response()`

**Tests:** `dev/test_header_rate_limiter.py` — 37 tests (all passing)
  Classes: TestParseResetDuration (9), TestModelWindowState (1),
  TestProviderRateLimitConfig (2), TestHeaderBasedRateLimiter (14),
  TestThreadSafety (2), TestCustomProviderConfig (1), TestMonotonicTimer (1),
  TestParseDurationEdgeCases (4)

**Live Validation:** Cheap `gpt-4.1-nano` smoke run with a temporary local
210-TPM / 5-second window: first tiny request admitted immediately, second tiny
request waited ~3.3 seconds behind the active reservation, and the token window
returned to 0 after expiry.

---

### FEATURE: Current Selection + Per-Model Settings in API.ini
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Track the active model selection across providers and store per-model
settings (temperature, timeout, chunk_size, etc.) in API.ini so that each
model retains its own configuration.

**Root Cause:** Previously, all model settings were global in CherryAI.ini.
Switching models lost per-model tuning. No cross-provider selection tracking.

**Solution:**
- `set_default_model()` now also writes `current_selection = {provider}.{model_id}`
  to API.ini via `set_api_setting()`
- Added `get_current_selection()` to read back `current_selection`
- Added `_MODEL_SETTING_KEYS` tuple (11 allowed keys: temperature, timeout,
  chunk_size, chunk_max_tokens, retries, rate_limit_requests, thinking_enabled,
  thinking_budget, logit_bias_enabled, max_concurrent, request_mode)
- Added `get_model_settings(model_id)` — reads `[model_settings]` section,
  returns dict of `{key: value}` for matching `{model_id}.{key}` entries
- Added `set_model_settings(model_id, settings)` — validates keys against
  `_MODEL_SETTING_KEYS`, writes to `[model_settings]` section
- Added `delete_model_settings(model_id)` — removes all keys for a model

**Files Modified:**
- `functions/api_config.py` — Added current_selection writing, get_current_selection,
  per-model settings CRUD functions

**Tests:** `dev/test_model_registry.py::TestCurrentSelection` — 4 tests (all passing)
  `dev/test_model_registry.py::TestPerModelSettings` — 7 tests (all passing)

---

### FEATURE: Save Settings + Translation Options in Costs Tab (Task 4)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Replace Refresh button with Save Settings, add workflow defaults
(Thinking, Translated Context checkboxes) and Rolling Context spinboxes
(Before, Between, After) to the Costs tab header.  Settings are saved
per-model to API.ini via `set_model_settings()` only when Save Settings
is pressed.  Model change loads saved settings without auto-saving.

**Solution:**
- Removed `↻ Refresh` button from Costs header
- Added `💾 Save Settings` button that persists UI settings per-model
- Added second header row with:
  - Thinking checkbox (`thinking_enabled`)
  - Translated Context checkbox (`use_translated_context`)
  - Rolling Context Before/Between/After spinboxes (0–20)
- `_save_settings()` collects all UI values and calls `set_model_settings()`
- `_load_model_settings()` reads per-model settings from API.ini, falling
  back to Global Options defaults
- `_on_model_changed()` calls `_load_model_settings()` before re-estimating
- `on_enter()` loads model settings on tab activation
- Rolling context values passed to `RequestFormationConfig` for accurate
  request formation during estimation
- Extended `_MODEL_SETTING_KEYS` with `rolling_context_before`,
  `rolling_context_between`, `rolling_context_after`, `use_translated_context`
- Fixed test fixture isolation: patched `_load.__globals__` in addition to
  module attribute to handle conftest module duplication

**Files Modified:**
- `gui/steps/costs.py` — New header layout, Save/Load settings, rolling context
- `functions/api_config.py` — Extended `_MODEL_SETTING_KEYS` (4 new keys)
- `dev/test_model_registry.py` — Fixed 3 fixtures, added TestCostsTabSaveSettings

**Tests:** `dev/test_model_registry.py::TestCostsTabSaveSettings` — 8 tests (all passing)
  All 119 + 4 skipped in test_model_registry.py
  All 56 in test_costs_step_phase40.py

---

### FEATURE: Request Mode Widget in Costs Tab (Task 5)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Goal: Add a 2×2 Request Mode grid (Normal / Batch / Flex / Priority) to
the Costs tab summary panel.  Mode selection drives pricing in the
comparison table and persists per-model via API.ini.

**Description:** OpenAI offers alternative processing tiers:
- **Normal** — standard synchronous, full price
- **Batch** — asynchronous (24 h turnaround), 50 % discount
- **Flex** — synchronous but slower, batch-rate pricing
- **Priority** — guaranteed processing, may cost more

Button states:
- **Selected** (#4a90d9 / white / sunken) — currently active mode
- **Available** (#c8e6c9 / green text / groove) — model has pricing data
- **Unavailable** (#ffcdd2 / gray text / flat) — no mode pricing in registry

**Solution:**
- Added `_REQUEST_MODES` class tuple mapping mode → (key, label, input_key,
  output_key) for all four tiers
- `_build_request_mode_grid()` creates 2×2 tk.Button grid in summary panel
- `_select_request_mode(mode)` validates availability, sets `_mode_var`,
  calls `_refresh_mode_buttons()` and re-estimates
- `_refresh_mode_buttons()` colors buttons per state; guards for
  uninitialized widgets
- `_get_mode_price_keys()` returns `(input_key, output_key)` for the
  active mode, defaulting to `("input", "output")`
- `_update_comparison_table()` now uses mode-specific pricing keys
- `_save_settings()` includes `request_mode` in per-model settings
- `_load_model_settings()` restores `request_mode` from API.ini
- Added "(No Model)" sentinel to Primary Model dropdown

**Files Modified:**
- `gui/steps/costs.py` — Request Mode grid, mode-aware pricing, save/load
- `dev/test_model_registry.py` — Added TestRequestModeSettings (6 tests)

**Tests:** `dev/test_model_registry.py::TestRequestModeSettings` — 6 tests (all passing)
  All 125 + 4 skipped in test_model_registry.py
  All 56 in test_costs_step_phase40.py

---

### FEATURE: Revised Token/Cost Breakdown in Costs Tab (Task 6)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Separate the Token Counts display into distinct rows for
content tokens (line text only), prompt tokens (overhead), cached
tokens (prompt portion from request 2+), and total input (billed).
Previously, Input Tokens showed the combined content+prompt total.

**Solution:**
- Added `content_tokens`, `prompt_tokens`, `cached_tokens` fields to
  `EstimationResult` dataclass (default 0 for backward compatibility)
- Token Counts UI grid now shows 6 rows:
  1. **Lines** — translatable line count
  2. **Input Tokens** — content tokens only (line JSON payloads)
  3. **Prompt Tokens** — total prompt overhead across all requests
  4. **Cached Tokens** — prompt tokens cached after first request
  5. **Total Input** (bold) — content + prompt (what gets billed)
  6. **Output Tokens (est)** — estimated output
- `_do_estimation()` populates new fields: `content_tokens` = line-only,
  `prompt_tokens` = per-request overhead sum, `cached_tokens` = prompt ×
  (num_requests − 1) when prompt ≥ 1024 tokens and model has cached_input pricing
- `_update_ui()` displays all breakdown rows with Original/Preprocessed/Saved
  columns for each
- Updated existing `TestPromptOverheadFormat` tests to verify new grid
  structure instead of old single-label format

**Files Modified:**
- `gui/steps/costs.py` — EstimationResult fields, UI grid layout, estimation logic
- `dev/test_costs_step_phase40.py` — Updated TestPromptOverheadFormat tests
- `dev/test_model_registry.py` — Added TestTokenBreakdown (6 tests)

**Tests:** `dev/test_model_registry.py::TestTokenBreakdown` — 6 tests (all passing)
  `dev/test_costs_step_phase40.py::TestPromptOverheadFormat` — 5 tests (all passing)
  All 131 + 4 skipped in test_model_registry.py
  All 57 in test_costs_step_phase40.py

---

### FEATURE: Manifest Estimation Persistence (Task 7)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 30 min

Goal: Persist full estimation results to the manifest so re-opening the
Costs tab restores previous values without re-estimating.  Previously
only InputLines, InputTokens, OutputTokens were saved (TASK 25.1).

**Solution:**
- Replaced `_save_analysis_results_to_manifest()` /
  `_load_analysis_results_from_manifest()` with expanded
  `_save_estimation_to_manifest()` / `_load_estimation_from_manifest()`
- Saved fields: InputLines, InputTokens, OutputTokens, ContentTokens,
  PromptTokens, CachedTokens, NumRequests, InputCost, OutputCost, TotalCost
- `on_enter()` restores all token breakdown rows (Input, Prompt,
  Cached, Total, Output), request count, and total cost from manifest
- `_load_estimation_from_manifest()` returns `None` when no saved data
- Added `save_float_field` / `load_float_field` imports for cost fields

**Files Modified:**
- `gui/steps/costs.py` — Expanded save/load, on_enter restoration
- `dev/test_model_registry.py` — Added TestManifestEstimationPersistence (6 tests)

**Tests:** `dev/test_model_registry.py::TestManifestEstimationPersistence` — 6 tests (all passing)
  All 137 + 4 skipped in test_model_registry.py
  All 57 in test_costs_step_phase40.py

---

### FEATURE: Estimate/Update Counts Button Rename (Task 8)
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 15 min

Goal: After the first estimation, rename the Estimate button to
"↻ Update Counts" so users know clicking again refreshes (not creates)
the estimation.  Also sets "↻ Update Counts" when restoring saved
estimation from manifest on tab enter.

**Solution:**
- `_estimation_complete()` now checks `self._estimation_result`:
  if present → "↻ Update Counts", else → "▶ Estimate"
- `on_enter()` sets "↻ Update Counts" when manifest data is restored
- Initial text remains "▶ Estimate" in `_build_header()`
- "Estimating..." shown during computation (unchanged)

**Files Modified:**
- `gui/steps/costs.py` — Button text logic in _estimation_complete, on_enter
- `dev/test_model_registry.py` — Added TestEstimateButtonRename (3 tests)

**Tests:** `dev/test_model_registry.py::TestEstimateButtonRename` — 3 tests (all passing)
  All 140 + 4 skipped in test_model_registry.py
  All 57 in test_costs_step_phase40.py

---

### DOCS: Costs Tab Overhaul Documentation (Task 9)
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 15 min

Goal: Update all documentation to reflect changes made in Tasks 1-8.

**Changes:**
- `doc/features.md` — Costs Tab section updated: dynamic registry, per-model
  settings, Translation Options row, Request Mode widget, revised token
  breakdown (6 rows), manifest persistence (10 fields), Estimate/Update
  button rename
- `doc/technical.md` — costs.py entry updated with all new features
- `doc/tests.md` — test_model_registry.py section updated from 83 to 140
  tests with 21 class entries; added to summary table; total updated
  from 3901 to 4041
- `doc/todo.md` — Tasks 1-9 all documented with COMPLETE status

=============================================================================

PENDING TASKS - UI

TASK: Progress Sidebar Rework

   Goal: Rework the Progress Sidebar for automatic completion detection, detailed tasks, and proper collapsing without being blank.
   Files: `gui/app.py`, `gui/tracker.py`
   Priority: HIGH
   Effort: 3-5 hours

   Details:
   - Ensure the Sidebar automatically updates and tracks step completion.
   - Show detailed tasks inside the steps.
   - Properly collapse/hide when not in use, without leaving a blank area.

---

TASK: Single/Double Click Editing for Model Comparison

   Goal: Enable click interactions for model selection and comparison in
   the Estimation step.
   Files: `gui/steps/estimate.py`
   Priority: MEDIUM
   Effort: 2-3 hours

   Details:
   - Single click: Select model for comparison.
   - Double click: Set primary model or select API key if multiple found.
   - Visual feedback for selected/active model.

=============================================================================

PENDING TASKS - ARCHITECTURE

TASK: Refactor Processing, IO, Models, Reporting

   Goal: Processing in each mode, shared reporting in modehelper
   Files: modi/*.py, mainhelper.py
   Priority: MEDIUM
   Effort: 4-8 hours

---

TASK: Establish Proper Pipeline

   Goal: Strict separation: CherryAI → mainhelper → modi
   Priority: MEDIUM
   Effort: 2-4 hours
   Depends On: Refactor Processing

=============================================================================

PENDING TASKS - MAJOR FEATURES

TASK: GUI Table View with Full Editing Capabilities

   Goal: Spreadsheet-like table view with search/replace, undo/redo
   Files: gui_table.py (NEW), gui_dialogs.py (NEW), gui_filters.py (NEW)
   Priority: HIGH
   Effort: 20-25 hours

---

TASK: Advanced API Request System

   Goal: Rolling context, multi-step workflows (TLC, Edit, Rewrite)
   Files: api_request.py (NEW), api_client.py (EXTEND)
   Priority: MEDIUM
   Effort: 26-32 hours

---

TASK: LLM Provider Modules

   Goal: Modular provider system with online capability/pricing updates
   Files: providers/ (NEW folder)
   Priority: MEDIUM
   Effort: 12-16 hours
   
   Requirements:
   - Abstract provider interface (OpenAI-compatible as baseline)
   - Provider-specific modules for: OpenAI, Anthropic, Google, Mistral, local
   - Online fetch of model capabilities (context window, features, etc.)
   - Periodic price updates from official pricing pages or APIs
   - Cache model info locally with TTL (e.g., refresh weekly)
   - Fallback to bundled defaults if fetch fails

---

TASK: Translation Progress Window (Live)

   Goal: Dedicated modal/window during Translation step
   Priority: MEDIUM
   Effort: 8-12 hours
   
   Display:
   - Overall progress % (lines translated / total)
   - Time remaining (ETA) based on moving average throughput
   - Token speed (input + output tokens/sec)
   - Lines translated, remaining, failed
   - Current model/provider and rate-limit status
   
   Controls:
   - Start/Resume, Pause, Cancel
   
   Logging:
   - Inline log pane with collapsible details
   - Export session log to logs/

=============================================================================

UPCOMING FEATURES

See the image translation workflow: [Image Translation Workflow](image_translation_workflow.md)

[Archived: Tasks 17.1–17.10 (Completed Features) → see doc/archived.md]

COMPLETED: API Log Window (2026)
   ✅ Core data module: functions/api_log.py (LogCategory, LogStatus, LogEntrySent, LogEntryReceived, LogEntry, APILogStore)
   ✅ Hook logging into all API call sites: api_client.py, term_translation.py, API2Glossary.py, api_config.py
   ✅ Per-project persistence: .api_log.jsonl alongside manifest, atomic saves, "log" manifest key
   ✅ GUI: gui/dialogs/api_log_view.py (non-blocking Toplevel, search, category filter, view mode, color-coded entries, live updates)
   ✅ Menu bar: "API Log" direct entry between Full Table View and Options
   ✅ Tests: dev/test_api_log.py (37 tests — serialization, CRUD, filtering, subscription, persistence, singleton, enums)

COMPLETED: Pricing & Reasoning Mode Fixes (2026)
   ✅ GPT-4.1 pricing fix: removed flex/priority from FALLBACK_MODELS (standard+batch only)
   ✅ GPT-4.1 thinking flag: set thinking=True, thinking_mode="optional"
   ✅ ThinkingConfig three-state: 5 modes (""/builtin/explicit/optional/mandatory) with effort_levels/effort_default/mandatory fields
   ✅ OpenAI provider: _is_gpt41_family(), _is_gpt5_family() helpers; get_thinking_config() returns correct mode per family
   ✅ ModelInfo: added thinking_mode field, set for all 27+ FALLBACK_MODELS entries
   ✅ Available Models filter: shows "Optional"/"✓"/"—" instead of just "✓"/"—"
   ✅ reasoning_effort: added to RequestSettings, APIConfig, TranslationOptions, _MODEL_SETTING_KEYS
   ✅ Global Options UI: reasoning effort combobox (low/medium/high), budget/effort rows toggle per mode
   ✅ Per-model INI persistence: reasoning_effort saved/loaded per model in [model_settings]
   ✅ Translate step: _reasoning_effort_var, _sync_from_global_options(), on_leave() data
   ✅ API client: provider-based get_thinking_params() using ThinkingConfig.build_params()
   ✅ Chat Completions: reasoning_effort as top-level param (not nested); thinking via extra_body for Claude
   ✅ THINKING_MODELS: added GPT-4.1, GPT-5, o4-mini; is_openai_reasoning_model() includes all families
   ✅ Tests: dev/test_pricing_and_reasoning.py (108 tests — pricing, thinking modes, build_params, persistence, API wiring)

PENDING TASKS - QUALITY

TASK: Performance Optimization

   Goal: Support 1M+ line files efficiently
   Priority: LOW
   Effort: 6-8 hours

=============================================================================

KNOWN ISSUES / BUGS

ISSUE: SharedTable "Item N already exists" TclError ✅ FIXED
   Status: FIXED (Phase 17)
   Description: Batch insertion callbacks continued after _refresh_display() was called again,
                causing duplicate item IDs when loading large files and rapidly switching tabs.
   Solution: Added _batch_insert_version counter. Batch callbacks check if version matches
             current before inserting. If stale, batch is silently cancelled.
   Files: gui/components/table.py, dev/test_table_batch_insert.py (8 tests)

---

ISSUE: Placeholders resolved in wrong order (Pre/Post mismatch)
   Status: OPEN (HIGH PRIORITY)
   Impact: Can corrupt restored text with overlapping placeholders
   Workaround: Reduce overlapping patterns, run Dry Run to inspect

---

ISSUE: Anchors / Remove-Restore reinserts content twice on Post-TL
   Status: OPEN (HIGH PRIORITY)
   Impact: Duplicate insertions corrupt output
   Workaround: Inspect manifest mappings for duplicates before Post-TL

---

ISSUE: GUI v2 Autosave JSON Parse Error
   Status: OPEN
   Description: "Failed to load autosave: Expecting value: line 41 column 13"
   Impact: Session not restored on launch
   Workaround: Delete temp/gui_session_autosave.json

---

ISSUE: GUI v2 Manifest Not Created Automatically
   Status: OPEN
   Description: Loading files does not automatically create a manifest
   Impact: User must manually create manifest for workflow

---

ISSUE: Japanese Ellipsis Restoration (Edge Case)
   Status: LOW PRIORITY
   Description: Japanese ellipsis (……) vs Western (...) mismatch warnings
   Impact: Cosmetic only, translations complete successfully

=============================================================================

ORPHANED MODULES (Exist but Not Fully Integrated)

| Module | Reason | Recommendation |
|--------|--------|----------------|
| formats/document.py | Placeholder (PDF/EPUB) | Keep for future |
| formats/html.py | Under development | Keep for HTML support |
| formats/rpgmaker.py | Placeholder | Keep for RPG Maker support |
| functions/local_llm.py | ✅ Integrated with GUI | LM Studio/Ollama support in Translation Step, Global Options |
| functions/replication.py | CLI only | Consider GUI integration |

=============================================================================

POTENTIAL ENHANCEMENTS

Future considerations (not prioritized):
- Undo/redo history in UI
- Real-time glossary suggestions while typing
- Export statistics to Excel
- Comparison mode (side-by-side before/after)
- Diff view for translations
- Integration with version control (git)
- REST API for headless operation

=============================================================================

EFFORT ESTIMATES

Phase 17 (COMPLETED):
- ✅ Batch API Support: 8-12 hours
- ✅ Multi-Key Management & Auto-Rotation: 10-14 hours
- ✅ Named API Profiles: 4-6 hours
- ✅ Additional File Formats (.trans, .md, lenient JSON): 8-10 hours
- ✅ Advanced Usage Analytics & Rate Limiting: 12-16 hours
- ✅ Automatic API Key Provisioning (Invest.): 4-6 hours (NOT FEASIBLE)
- ✅ Session Persistence & Auto-Load: 4-6 hours
- ✅ Agent-Assisted Modes: 6-8 hours
- ✅ Estimation Step Upgrade: 6-10 hours
- ✅ Tooltips & Multi-Language UI: 6-12 hours

Major Projects (12+ hours):
- LLM Provider Modules: 12-16 hours
- Advanced API Request System: 26-32 hours
- GUI Table View: 20-25 hours
- Translation Progress Window: 8-12 hours

Medium Tasks (2-8 hours):
- Refactor Processing: 4-8 hours
- Establish Proper Pipeline: 2-4 hours
- Performance Optimization: 6-8 hours
- Model Data Fetch (Task 40.8): 3 hours
- Analysis Results Storage (Task 25.1): 2 hours
- Model Comparison Click Editing: 2-3 hours

Total Remaining Effort: ~155-215 hours

=============================================================================

FUTURE IDEAS (No Phase Commitment)
**Priority:** LOW | **Status:** 🔲 PARKED | **Effort:** N/A

### Costs Step Future Enhancements
- **Final Cost Recording**: Track actual tokens and cost after translation completes
- **Cost Comparison**: Display estimated vs actual difference post-translation
- **Additional Cost Types**: Track costs for Editing, TLC, Summary generation, Glossary inference, Tone/Style inference
- **Cost History**: Track and display costs across multiple translation sessions
- **Budget Warnings**: Alert when estimated cost exceeds configured budget threshold
- **Request Merging**: Combine small trailing chunks into previous request when no rolling context needed
- **Token Speed Tracking**: Calculate actual tokens/sec from previous translations for accurate time estimates
- **Batch Mode Pricing**: Show batch API pricing (with discount %) for supported models
- **Image Cost Estimation**: Include image processing costs when image files loaded
- **Expanded Deduplication (also part of Pre- and Post-Processing Steps)**: Current Deduplication may just take the original string before any processing. More aggressive Deduplication can apply its own rules after all preprocessing and before all postprocessing. It can use one {CODE} for all code and X for all numbers.

### Analysis Step Future Enhancements
- **Auto-populate Glossary**: Use detected speakers and code patterns to pre-fill glossary entries
- **Pattern Suggestions**: Recommend protection rules based on detected code patterns
- **Export Formats**: Support additional export formats (JSON, XLSX) for findings
- **Visual Charts**: Charts/graphs for language distribution and pattern frequency
- **Diff Analysis**: Compare against previous analysis when files change
- **Code Patterns Consolidation**: The findings table currently writes to a dedicated code patterns table. Rework so findings write directly to the Code Database and Glossary in the Information step, eliminating the intermediate table. This reduces duplication and keeps a single source of truth for all patterns.

### Information Step Future Enhancements
- **Summary Generation via API**: Button to auto-generate summary using LLM analysis of loaded content
- ~~**Save/Load System Instructions**: Buttons to save current System Instructions to file and load from templates~~ ✅ DONE (preset system with Default/Custom/user presets)
- **Expanded Genre List**: Add more genre options, potentially with subcategories
- **Glossary Inference via API**: Use LLM to suggest glossary entries based on content analysis
- **Style/Tone Inference**: Auto-detect appropriate style/tone from sample text
- **Character Database**: Extended character info with relationships, traits, speaking patterns
- **Glossary Categories**: Group glossary entries by category (names, places, terms, etc.)
- **Glossary Import from File**: Direct import from external glossary files (CSV, JSON, TMX)
- **Code Pattern Templates**: Pre-built code pattern sets for common game engines (RPG Maker, Unity, etc.)
- **Project Templates**: Save/load entire Information step configurations as reusable templates
- ~~**Redesign Glossary Settings Widget**: Fold "Glossary Settings" into the "Global Glossary and Database" widget. Requiring a rework to remove, move and streamline to only ever export from the manifest to the global files.~~ ✅ DONE (TASK 76 — replaced both widgets with unified "Knowledge Base" widget)

### Preprocessing/Postprocessing Future Enhancements
- [x] **Line Field Persistence (Task 3)**: Fixed critical bug where preprocessing, postprocessing, and wordwrap steps stored per-line results only in step_state but never wrote to manifest `lines[].prepro` / `lines[].postpro` / `lines[].wordwr` via `set_line_field()`. Also fixed `_mark_line_as_fixed()` calling nonexistent `update_line_field()` → `set_line_field()`. 39 tests in `dev/test_line_saving.py`.
- [x] **Pipeline Order Fix & Postprocessing Reversal**: Fixed 6 root causes of broken postprocessing. (1) Protect Code (P15) and Custom Placeholders (P17) now run before Symbol Conversion (P30) so fullwidth patterns match original text. (2) Anchoring (P20) added to pipeline before Symbol Conversion. (3) All preprocessing data (protect_code_captured, placeholder_captured, ellipsis_counts, anchor_captured, aggr_numbers) stored in step data for postprocessing. (4) Postprocessing now runs full reversal pipeline first (Phase 1: PROT decompression → Protect Code restoration → Custom Placeholder restoration → Ellipsis expansion → Anchoring restoration → `<NUM>` restoration), then `recover_line()` with `enable_placeholder_recovery=False` as Phase 2 on restored text. (5) Protect code capture order fixed: positions collected across all patterns first, overlaps resolved, captured in left-to-right order. (6) Anchoring rewritten to anchor-relative system: patterns only removed when adjacent to a valid anchor character; restoration uses `rfind` with symbol-conversion equivalents instead of absolute/proportional positioning. Updated process_order.py and specs.md §5.9. 48 tests in `dev/test_postpro_pipeline.py`.
- **Speaker Name Replacement Rework**: Handle edge cases (speakers with colons in name, multiple dialogue formats, speaker extraction from non-standard patterns)
- **Code Spacing Rules Expansion**: Deeper integration with Code Database, expanded rule definitions, per-pattern spacing tags (visible/invisible, variable handling)
- **Advanced Deduplication Rules**: Pattern-based deduplication using Increase/Decrease equivalence, RPG stat names (Strength/Willpower/Dexterity) as equivalent, database of auto-translations for common patterns
- **Pattern Replacement Mode**: Replace patterns permanently before translation (not restored after)
- **Pattern Removal Mode**: Remove patterns permanently before translation (not restored after)
- **Optional Custom Placeholder Mismatch Check**: Add a hidden/default-off postprocessing validation that reports two mismatch classes without changing output: (a) lines tagged with `placeholder` where no custom placeholder was actually restored, and (b) recovered/custom-placeholder tokens found on lines that were never tagged. Wire it to a future manifest/UI toggle later rather than enabling it by default now.
- **Variable Replacement via Preprocessing**: Replace variable codes (\\v[N], \\n[N]) during preprocessing and restore with postprocessing. Needs improved parser to handle replacements and restore positions correctly. Currently handled only via conditional prompt instruction.
- **Functions Not Visible in GUI**: Restore additional processing functions that exist in code but lack GUI exposure
- **Context-Aware Deduplication**: Use semantic similarity rather than exact match for deduplication
- **Deduplication Variants Database**: Create database of pattern variants that should be treated as duplicates
- **Deduplication Tag-Based Rework**: Replace the current dedup_map file with inline tags (e.g. ``dedup,D3516``) embedded in each line. This removes the need for a separate mapping file, simplifies the restore step, and makes dedup state visible during translation and QA. Requires changes to the dedup pipeline, restore logic, and manifest line schema.
- **Queue for Retry (Postprocessing)**: When a postprocessing recovery fails, queue the line for re-translation with stricter one-line instructions. Requires retry pipeline integration with Translation Step (Step 5) and a prompt template designed for recovery-focused re-translation. Currently hidden from Failure Handling widget.

### Translation Step Future Enhancements
- **Edit Before Translation**: Button opens a dialog where the LLM is prompted to fix specific mistakes in the original text (not translate). Requires separate prompt design and dedicated LLM pass. Currently hidden from UI.
- **Line-by-Line Translation Mode**: Translate each line individually with configurable rolling context window. Slower but more precise for difficult content. Currently hidden from UI.
- **Per-Rule Skip Toggles**: Expose the Translation header skip groups as individual Global Options switches so users can independently enable or disable already-translated, empty, placeholder-only, code-only, symbols-only, and non-CJK/non-source skipping.
- **NMT Mock Translation**: Replace nonsense Mock Translation output with Neural Machine Translation (NMT) engine for basic but meaningful offline translation. Potential engines: MarianMT, CTranslate2, or local model integration.
- **Isolated Retry Strategy**: Retry each failed line individually with strict one-line instructions. Needs further refinement before UI exposure.
- **Skip Retry Strategy**: Mark failed lines as Skipped immediately without retrying. Needs UX design for manual review flow.
- **Advanced Cache Modes**: Implement strict (exact prompt match), model_only (same model), and any (any translation) cache modes beyond the default Line cache.
- **Daily Limit Check**: Alert before exceeding configured daily API budget/token limits.
- **Batch API Pricing**: Show batch API pricing with discount percentages for supported models.
- **Translation / Edit / TLC Mode Toggle**: A three-way toggle switching the Translation step between Translation (default), Edit, and TLC modes. Edit mode prompts the LLM to fix grammar, naturalness, and formatting in existing translations. TLC mode sends original + translation for accuracy verification. Key design challenge: line-matching strategy (line numbers, full lines, or empty lines) since not every line will be edited/TLC'd and unnecessary output tokens are the most expensive component. Each mode writes to its own manifest fields (`lines[].edit{N}`, `lines[].tlc{N}`). Requires dedicated prompt design, matching script development, and cost-optimization testing before UI exposure.

### Wordwrap Step Future Enhancements
- ~~**Per-Tag Wordwrap Settings**: Tag-based wordwrap configuration with per-tag Width/BreakChar/MaxLines. TagWrapConfig dataclass, tag resolution (line tag → filedir type → "dialogue" fallback), manifest persistence via TagConfigs.~~ ✅ IMPLEMENTED
- ~~**Parser-Driven Wrap Options**: Parsers auto-populate wordwrap settings (width, break char, max lines) based on the game engine format. `_apply_parser_wordwrap_defaults()` reads `wordwrap_for_tag()` and pre-populates per-tag configs. All settings remain editable.~~ ✅ IMPLEMENTED
- ~~**Manifest-Driven Format Scoping**: Preview format list comes from `filedir[].format`; wrapping is filtered and applied per format, with enable/disable control per format.~~ ✅ IMPLEMENTED
- ~~**Per-Tag Enabled + PrettyWrap**: TagWrapConfig exposes Enabled and a single PrettyWrap toggle instead of separate orphan/punctuation controls.~~ ✅ IMPLEMENTED
- ~~**New Textbox Handling**: Per-tag `new_textbox` and `new_textbox_injection` fields in TagWrapConfig. LightVN uses `\\w` as new textbox injection. UI shows checkbox + injection string entry per tag.~~ ✅ IMPLEMENTED
- ~~**Parser display_name / tooltip**: ParserScript ABC extended with `display_name` and `tooltip` properties. LightVN implements both.~~ ✅ IMPLEMENTED
- ~~**Output Format Restriction**: Output step detects parser format from filedir and defaults to INJECTION mode when a parser format is detected.~~ ✅ IMPLEMENTED
- **RPG Maker as Own Parser**: Move RPG Maker-specific wordwrap logic (pixel-accurate width, `analyze_rpgmaker_project()`, `measure_font_avg_char_px()`) into a dedicated RPG Maker format parser. RPG Maker is no longer a wordwrap mode — it becomes a parser that drives the wordwrap settings automatically.
- **Font Commands**: Parser-level support for font size commands (`size_up`, `size_down`, `size_increments`, `set_size`, `get_size`) that affect rendered width mid-line. Width calculation must account for font size changes within a single line of text.
- **Invisible Code and Variable Code**: Distinguish between code that is invisible (zero rendered width, e.g., color codes) and code that represents a variable (rendered width depends on the variable's runtime value). Variable code should use a max-length estimate for width calculation.
- **Line Break Auto-Detection from Parser**: Parsers identify the engine's native line break character and auto-populate the Break Character field. Currently break char is user-configured with common presets.
- **Pixel-Accurate Width Calculation**: Full pixel-based width using font metrics from `measure_font_avg_char_px()`. Requires Pillow for font measurement and project analysis via `analyze_rpgmaker_project()`. Show pixel ruler in preview.
- **Break Character Removal Before Translation**: Remove line breaks before sending to LLM to save tokens (fewer continuation lines = lower cost). Display warning that post-editing may be needed since LLM won't see original line structure. Re-wrapping after translation restores breaks.

### QA Step Future Enhancements
- **Full QA Implementation**: Activate the complete QA interface with validation rules panel, issue details, batch accept/reject, auto-fix, and export report. Currently behind a placeholder toggle.
- **Edit/TLC Filtering**: Once Edit and TLC modes exist in the Translation step, add "Edited" and "TLC'd" filter options to QA. These allow inspecting how much each inference pass changed and measuring the value of additional passes.
- **Re-run Policy**: Implement configurable re-run policies (FailedOnly, All, None) for selective re-validation after manual fixes.
- **Issue Severity Customization**: Allow users to override default severity levels per rule (e.g., downgrade Japanese Remaining from WARNING to INFO for mixed-language projects).
- **QA Report Templates**: Multiple export formats (JSON, XLSX, HTML) with configurable detail levels.
- **QA History**: Track QA results across translation rounds to show improvement/regression trends.

### Other Future Ideas
- Benchmark Mode (requires synthesized text with multiple passes and comparison)
- ToS/EULA for legal protection
- Agent AI
- Context Menu
- System Tray
- Image to Text Translation through OCR-capable model screenshot capture

---

### Application Rename
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Easily rename application when a name is finally found.

**Implementation:**
- Keep all internal references to CherryAI
- Update window title, about dialog, documentation once decided on
- Keep file naming

**Files to Modify:**
- All files with CherryAI references
- Documentation files

---

### Tooltips and Translation Support
**Priority:** LOW | **Status:** 🔲 NOT STARTED | **Effort:** 4 hours

Goal: Add tooltips with translation support for all GUI fields.

**Implementation:**
- Create tooltip system with concise explanations
- Add toggle to disable tooltips in Options
- Translation files in `user/lang/` for i18n

**Files to Create:**
- `gui/helpers/tooltip.py` - Tooltip system
- `user/lang/en.json` - English tooltip strings

=============================================================================

CRITICAL ARCHITECTURE NOTE: UNIFIED MANIFEST SYSTEM

CherryAI uses ONE manifest file per project that contains ALL data:

**SINGLE MANIFEST FILE (.CherryAI.json) contains:**
1. **Processing Data** (v2.1 fields) - `lines`, `operations`, `mappings`, `summary`, `metadata`
2. **Project Settings** (v3.0 additions) - all GUI field defaults and user choices
3. **Step State** - workflow progress and per-step configuration

**TWO CLASSES access the SAME data:**

**1. `ManifestManager` - FILE AUTHORITY**
   - Location: `functions/manifest_manager.py`
   - Purpose: Single authority for manifest file I/O
   - Manages: `_manifest_data` dict containing ALL fields
   - Used by: GUI App, all gui/steps/, project dialogs
   - Role: Creates, loads, saves, validates manifest files
   - Tests: `test_manifest_state.py` - MUST NOT BREAK

**2. `mainhelper.Manifest` - RUNTIME PROCESSING VIEW**
   - Location: `functions/mainhelper.py`
   - Purpose: Dataclass optimized for Processor operations
   - Contains: `LineEntry` objects, `Operation` list, `mappings` dict
   - Used by: `Processor` class, all modi/ modules, CLI operations
   - Role: Runtime view of processing data (not file I/O)
   - Tests: `test_manifest_v2.py` - MUST NOT BREAK

**DATA FLOW:**
```
Manifest File (.CherryAI.json)
       |
       v
ManifestManager._manifest_data  <-- Single source of truth
       |
       |---> GUI reads/writes project settings directly
       |
       +---> export_to_mainhelper_manifest() --> Processor
                                                    |
       import_from_mainhelper_manifest() <----------+
       (syncs processing results back)
```

**MANIFEST 3.0 IS AN EXTENSION, NOT A REPLACEMENT:**
- v2.1 fields (`lines`, `operations`, `mappings`) remain unchanged
- v3.0 ADDS project settings fields alongside existing ones
- All fields coexist in ONE JSON file
- Processor still works with same LineEntry/Operation structures
- GUI simply has more fields to read/write

**Initialization Order:**
1. ManifestManager creates manifest with ALL defaults from .ini
2. GUI loads and can modify any field
3. Before processing: `export_to_mainhelper_manifest()` creates runtime view
4. Processor runs using mainhelper.Manifest dataclass
5. After processing: `import_from_mainhelper_manifest()` syncs results back
6. ManifestManager saves everything to ONE file

**Core Principles:**
1. ONE manifest file per project containing ALL data
2. ManifestManager is the ONLY class that reads/writes files
3. mainhelper.Manifest is a runtime convenience, not a separate system
4. v3.0 extends v2.1 format - all existing tests continue to pass
5. All defaults initialized BEFORE GUI can access fields
6. Most project settings get passed to functions/API requests

**KEY FILES AND THEIR ROLES:**
```
functions/mainhelper.py       - LineEntry, Manifest dataclass, Processor
                                (runtime processing - DO NOT change format)
functions/manifest_manager.py - ManifestManager (file I/O, v3.0 fields)
functions/ini_manager.py      - INI defaults loading
functions/manifest_fields.py  - Field type helpers for GUI binding + shared priority resolution (PIPELINE_FIELDS, resolve_line_field, get_all_lines_resolved)
functions/options.py          - API providers (global settings, not per-project)
functions/project_config.py   - Project overrides (will merge into ManifestManager)
gui/app.py                    - Uses ManifestManager for all state
gui/steps/*.py                - Read/write via ManifestManager
```

=============================================================================

CRITICAL TEST VERIFICATION REQUIREMENTS

Before ANY phase is marked complete, the following tests MUST pass:

**Existing Tests (MUST NOT BREAK):**
- `dev/test_manifest_v2.py` - 50+ tests for mainhelper.Manifest and LineEntry
- `dev/test_manifest_state.py` - 40+ tests for ManifestManager
- `dev/test_manifest_automation.py` - Automated manifest creation tests
- All other existing tests

**Test Commands:**
```bash
# Run all manifest tests
pytest dev/test_manifest_v2.py dev/test_manifest_state.py -v

# Run full test suite (should be done before each merge)
pytest dev/ -v --tb=short
```

**Regression Prevention:**
1. mainhelper.Manifest.to_dict() output format MUST NOT CHANGE
2. mainhelper.Manifest.from_dict() MUST accept existing v2.1 format
3. LineEntry field names and behavior MUST NOT CHANGE
4. ManifestManager bridge methods MUST preserve all line/operation data
5. Processing pipeline (Processor, modes) MUST continue working unchanged

=============================================================================

MANIFEST 3.0 COMPLETE FIELD REFERENCE

All fields stored in the UNIFIED manifest file (ManifestManager._manifest_data).
v2.1 processing fields (`lines`, `operations`, `mappings`) coexist with v3.0 settings.

**Field Categories:**
- **v2.1 Processing** - Unchanged, used by Processor via export_to_mainhelper_manifest()
- **v3.0 Settings** - Passed to functions during processing

### v2.1 Processing Fields (existing - DO NOT CHANGE FORMAT)

| Manifest Key | Type | Description | Managed By |
|--------------|------|-------------|------------|
| `lines` | array | LineEntry.to_dict() results | Processor → import_from_mainhelper_manifest() |
| `operations` | array | Operation.__dict__ results | Processor → import_from_mainhelper_manifest() |
| `mappings` | object | Mode state mappings | Processor → import_from_mainhelper_manifest() |
| `summary` | text | Processing summary | Processor |
| `metadata` | object | Processing metadata | Processor |

These fields are populated by the processing pipeline. GUI should NOT directly modify them.
Instead, use the bridge methods to sync processing results into ManifestManager.

### v3.0 Settings Fields

| GUI Field | Manifest Key | Type | Default | Passed To |
|-----------|--------------|------|---------|-----------|
| Project Name | `step_state.Information.data.metadata.project_name` | text | "Project1" | - |
| Title | `step_state.Information.data.metadata.game_title` | text | "Title1" | prompt |
| Genre | `step_state.Information.data.metadata.genre` | text | "fictional, nonfictional" | prompt |
| Source Language | `step_state.Information.data.metadata.source_language` | text | "Japanese" | api_client |
| Target Language | `step_state.Information.data.metadata.target_language` | text | "English" | api_client |
| Summary | `step_state.Information.data.metadata.summary` | text | "[DEFAULT_SUMMARY_TEXT]" | prompt |
| Style Preset | `step_state.Information.data.metadata.style_preset` | text | "Natural" | prompt |
| Tone Preset | `step_state.Information.data.metadata.tone_preset` | text | "Neutral" | prompt |
| Glossary (Characters) | `CharacterNotes` | special | [] | prompt |
| Code Database | `CodeGlossary` | special | [] | prompt |
| Prompt | `step_state.Information.data.metadata.custom_notes` | text | "[DEFAULT_SYSTEM_INSTRUCTIONS]" | prompt |
| SI Preset | `step_state.Information.data.metadata.si_preset` | text | "Default" | - |
| Genre Enabled | `step_state.Information.data.metadata.genre_enabled` | boolean | false | prompt toggle |
| Summary Enabled | `step_state.Information.data.metadata.summary_enabled` | boolean | false | prompt toggle |
| Style Enabled | `step_state.Information.data.metadata.style_enabled` | boolean | false | prompt toggle |
| Tone Enabled | `step_state.Information.data.metadata.tone_enabled` | boolean | false | prompt toggle |
| SI Enabled | `step_state.Information.data.metadata.system_instructions_enabled` | boolean | true | prompt toggle |
| Glossary Enabled | `step_state.Information.data.metadata.glossary_enabled` | boolean | true | prompt toggle |
| Code DB Enabled | `step_state.Information.data.metadata.code_database_enabled` | boolean | true | prompt toggle |
| Deduplication | `Deduplication` | boolean | true | dedup mode |
| Dedup Threshold | `DeduplicationThreshold` | int | 1 | dedup mode |
| Ellipsis Compression | `EllipsisCompression` | boolean | true | ellipsis mode |
| Symbol Conversion | `SymbolConversion` | boolean | true | symbol mode |
| Speaker Name Replacement | `SpeakerNameReplacement` | boolean | false | speaker mode |
| Code Spacing Rules | `CodeSpacingRules` | boolean | true | code mode |
| Protect Code Patterns | `ProtectCodePatterns` | special | [] | protect_code mode |
| Custom Placeholders | `CustomPlaceholders` | special | [] | placeholder mode |
| Anchor Removal | `AnchorRemoval` | special | [] | anchor mode |
| Input Lines | `InputLines` | int | 0 | estimation |
| Input Tokens | `InputTokens` | int | 0 | estimation |
| Output Tokens | `OutputTokens` | int | 0 | estimation |
| Placeholder Preservation | `ValidationRules.PlaceholderPreservation` | boolean | true | validation |
| Anchor Preservation | `ValidationRules.AnchorPreservation` | boolean | true | validation |
| Source Language Detection | `ValidationRules.SourceLanguageDetection` | boolean | true | validation |
| Speaker Format | `ValidationRules.SpeakerFormat` | boolean | true | validation |
| Quote Balance | `ValidationRules.QuoteBalance` | boolean | true | validation |
| Empty Translation | `ValidationRules.EmptyTranslation` | boolean | true | validation |
| Re-run Policy | `QAOptions.RerunPolicy` | enum | "FailedOnly" | qa |
| Max Source-Language Chars | `QAOptions.MaxSourceLanguageChars` | int | 4 | qa |
| Max Line Length | `QAOptions.MaxLineLength` | int | 0 | qa |
| Model | `RequestOptions.Model` | text | "" | api_client |
| Temperature | `RequestOptions.Temperature` | float | 0.2 | api_client |
| Lines per Chunk | `RequestOptions.LinesPerChunk` | int | 30 | chunker |
| Retry Strategy | `RequestOptions.RetryStrategy` | enum | "Batch" | api_client |
| Max Retries | `RequestOptions.MaxRetries` | int | 3 | api_client |
| Enable Caching | `RequestOptions.EnableRequestCaching` | boolean | true | api_client |
| Line by Line | `RequestOptions.LineByLineMode` | boolean | false | chunker |
| Thinking | `RequestOptions.Thinking` | boolean | false | api_client |
| Thinking Budget | `RequestOptions.ThinkingBudget` | int | 1000 | api_client |
| Placeholder Recovery | `PostProcessing.PlaceholderRecovery` | boolean | true | postprocess |
| Bracket Balance | `PostProcessing.BracketBalanceRecovery` | boolean | true | postprocess |
| Quote Balance | `PostProcessing.QuoteBalanceRecovery` | boolean | true | postprocess |
| Whitespace Norm | `PostProcessing.WhitespaceNormalization` | boolean | true | postprocess |
| Restore Code Chars | `PostProcessing.RestoreCodeCharacters` | boolean | true | postprocess |
| Restore Linebreaks | `PostProcessing.RestoreLinebreaks` | boolean | true | postprocess |
| Symbol Conversion | `PostProcessing.EnableSymbolConversion` | boolean | true | postprocess |
| Fullwidth→Halfwidth | `PostProcessing.FullwidthToHalfwidth` | boolean | true | postprocess |
| Failure Handling | `PostProcessing.FailureHandling` | enum | "FlagForReview" | postprocess |
| Wordwrap Mode | `WordwrapSettings.Mode` | enum | "Manual" | wordwrap |
| Width | `WordwrapSettings.Width` | int | 48 | wordwrap |
| Break Char | `WordwrapSettings.BreakChar` | text | "" | wordwrap |
| Max Lines | `WordwrapSettings.MaxLines` | int | 4 | wordwrap |
| Pretty Wrap | `WordwrapSettings.PrettyWrap` | boolean | true | wordwrap |
| Speaker Handling | `WordwrapSettings.SpeakerHandling` | enum | "Count" | wordwrap |
| Ignore Patterns | `WordwrapSettings.IgnorePatterns` | list | ["Angle","Square","Curly","En"] | wordwrap |
| Typography | `WordwrapSettings.Typography` | text | "Western" | wordwrap |
| Tag Configs | `WordwrapSettings.TagConfigs` | list | [] | wordwrap (per-tag) |
| Format Configs | `WordwrapSettings.FormatConfigs` | list | [] | wordwrap (per-format) |
| Preserve Folders | `OutputFormat.PreserveFolderStructure` | boolean | true | output |
| Format | `OutputFormat.Format` | text | "" | output |
| Pair Mode | `OutputFormat.PairMode` | text | "translated_only" | output |
| Encoding | `OutputFormat.Encoding` | text | "" | output |
| File Naming | `OutputFormat.FileNaming` | enum | "PutInSubfolder" | output |
| Text Option | `OutputFormat.TextOption` | text | "translated" | output |
| Overwrite Files | `OutputFormat.OverwriteExistingFiles` | boolean | false | output |
| Backup | `OutputFormat.Backup` | text | "Timestamp" | output |
| Backup Extension | `OutputFormat.BackupExtension` | text | ".bk" | output |
| Export Manifest | `OutputFormat.ExportManifestFile` | boolean | false | output |
| Export Logs | `OutputFormat.ExportProcessingLogs` | boolean | false | output |
| Export Glossary | `OutputFormat.ExportGlossaryEntries` | boolean | false | output |

=============================================================================

PHASE 58: INPUT AUTOMATION (Step 0 Enhancement)
-----------------------------------------------

**Status:** 🔲 PLANNED | **Effort:** 16-24 hours | **Priority:** HIGH

Goal: Implement automatic pipeline execution when files are loaded, providing
users with a "load and see results" workflow. When files are loaded into a 
new project, the pipeline automatically runs up to a configurable endpoint.

**Reference:** See `doc/specs.md` Section 2.2 → Step 0: Input for full spec.

### TASK 58.1: Input Button Unified Window
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Replace separate Load Files/Load Folder buttons with a unified Input
button that opens a combined file/folder selection window.

**Requirements:**
- Single button opens a modal window with dual-pane interface
- Left pane: Folder tree browser for directory selection
- Right pane: File list for individual file selection
- Both support multi-select (Ctrl+Click, Shift+Click)
- "Add Selection" button queues items without closing
- "Load" button finalizes and begins pipeline

**Files to Modify:**
- `gui/steps/input.py` - Replace buttons with unified Input button
- `gui/dialogs/` - Create new `input_dialog.py` for combined selection

**Tests to Add:**
- `dev/test_input_dialog.py`:
  - `test_file_selection`
  - `test_folder_selection`
  - `test_mixed_selection`
  - `test_add_selection_queue`

---

### TASK 58.2: Auto-Pipeline Dropdown
**Priority:** HIGH | **Status:** ✅ COMPLETE (hidden pending rework) | **Effort:** 2 hours

Goal: Add dropdown to Options Panel for selecting automation level (0-4).

**Levels:**
- 0: Manual (load only)
- 1: Analyze
- 2: Estimate Original
- 3: Preprocess (Default)
- 4: Mock Translate

**Files to Modify:**
- `gui/steps/input.py` - Add Auto-Pipeline Dropdown to Options Panel
- `config/defaults.ini` - Add `auto_pipeline_level = 3`

**Tests to Add:**
- `dev/test_auto_pipeline.py`:
  - `test_pipeline_level_0_load_only`
  - `test_pipeline_level_3_default`
  - `test_pipeline_level_persistence`

[Archived: Phase 58: Input Automation → see doc/archived.md]


---

### TASK 59.2: Aggressive Deduplication Projection
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Goal: Show projected line count after aggressive deduplication in Statistics.

**Display:**
Format: "Aggressive Dedup: X lines → Y unique (Z% reduction)"

**Files to Modify:**
- `functions/analysis.py` - Calculate aggressive dedup projection
- `gui/steps/analysis.py` - Display projection in Statistics Panel

**Tests to Add:**
- `dev/test_analysis.py`:
  - `test_aggressive_dedup_projection`

---

### TASK 59.3: Category-Aware Findings Table Context Menu
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

---

=============================================================================

## PHASE: Parser Handshake — Unified I/O Parser Interface 

**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 12-16 hours

### Goal

Define a formal "handshake" contract that every file-format parser must satisfy.
The contract has **mandatory** components (must be present and return valid data or
raise an error) and **optional** components (provide additional capabilities when
the format supports them). The handshake standardises how parsers communicate with
the pipeline so that adding a new format is purely additive — implement the ABC,
register, done.

All parsers remain in the `formats/` folder. No new top-level package is created.

### Design Principle

Parsers write their results to well-known manifest fields. The rest of the pipeline
never reads parser internals — it reads the manifest. If a mandatory handshake
function is missing or returns an error/unknwn value, an error popup is shown
immediately (on parser selection for missing functions, or after Input is attempted
for validation failures). Warnings (e.g., lines > 1024 tokens) are displayed but
do not block.

---

### Current Implementation Snapshot

Two parallel hierarchies already exist in `formats/`:

1. **`FormatHandler`** (ABC in `formats/__init__.py`)
   - `format_id: str`, `extensions: list[str]`
   - `extract(path, encoding) → list[str]`
   - `inject(path, lines, encoding)`
   - `supports_original() → bool`, `get_metadata(path) → dict`
   - Registered via `FormatRegistry` with extension-based lookup.
   - Concrete handlers: `TxtHandler`, `CsvHandler`, `TsvHandler`, `JsonHandler`,
     `XlsxHandler`, `HtmlHandler`, `MarkdownHandler`, `JsonLenientHandler`,
     `TranslatorPlusHandler` (all in `formats/`). Stub handlers: `RpgMakerMVHandler`,
     `RpgMakerMZHandler`, `PdfHandler`, `EpubHandler`.

2. **`ParserScript`** (ABC in `formats/parser_base.py`)
   - Wraps a FormatHandler and adds game-engine-specific features.
   - `name: str`, `extract()`, `inject()`, optional `wordwrap_config`,
     `forbidden_chars`, `tag_rules`, `can_handle()`.
   - Dataclasses: `WordwrapConfig`, `ForbiddenChars`, `TagRules`.
   - Registered via `ParserRegistry` with `can_handle()` auto-detection.
   - Concrete parsers: `RpgMakerMVParser`, `RpgMakerMZParser`
     (in `formats/parser_rpgmaker.py`).

**Registration flow:**
- `get_registry()` → `_load_handlers()` (simple, html, markdown, json_lenient,
  translator_plus)
- `get_parser_registry()` → `_load_parsers()` (RPG Maker MV, RPG Maker MZ)

**Step 0 (Input)** currently calls `FormatRegistry.get_for_path()` or
`ParserRegistry.detect()` to find the right handler. Lines are stored in
`manifest.lines[].orig`.

**Step 9 (Output)** calls the handler's `inject()` to write translated lines into
copies of the original files.

---

### Handshake Contract

#### A. MANDATORY Components

Every parser (whether a simple `FormatHandler` or an engine-specific `ParserScript`)
**must** implement the following. Failure to provide one raises an error popup when
the parser is selected.

| # | Component | Signature / Type | Description | Validation |
|---|-----------|-----------------|-------------|------------|
| M1 | **Extract** | `extract(path, encoding=None) → list[str]` | Extract translatable lines from the source file, one element per line. Must not return `None`. | Empty list is valid (file has no translatable text). Raises `ParserError` on read failure. |
| M2 | **Inject** | `inject(path, lines, encoding=None)` | Inject translated lines back into a **copy** of the source. Never modifies the original. | `len(lines)` must match the count produced by `extract()` for the same file. Raises `ParserError` on write failure. |
| M3 | **Format ID / Extensions** | `format_id: str` + `extensions: list[str]` **or** `can_handle(path) → bool` | Determines which file types this parser claims. For `FormatHandler` subclasses this is `format_id` and `extensions`. For `ParserScript` subclasses this is `can_handle()` (probes file structure). At least one mechanism is required. | `format_id` must be non-empty. `extensions` must have ≥1 entry or `can_handle()` must be defined. |

**Validation rules for mandatory outputs:**
- No single extracted line may exceed **2048 tokens** (raises `ParserError` immediately).
- Lines exceeding **1024 tokens** emit a warning popup: "Line {idx} is {N} tokens
  ({N-1024} over recommended limit). Consider splitting."
- Token counting uses `tiktoken` when available, else the `len(text) * 0.3` heuristic
  already in `functions/chunker.py`.

#### B. OPTIONAL Components

Optional components follow an `opt-in` pattern: the parser either provides the
attribute/method or does not. The pipeline checks `hasattr()` / `getattr(..., None)`
before using them. Missing optionals never raise errors.

| # | Component | Signature / Type | Description | Manifest Field(s) |
|---|-----------|-----------------|-------------|-------------------|
| O1 | **Decryption** | `decrypt(path) → path` | Decrypt source file before extraction. **Discouraged** without explicit copyright permission. Situated in pipeline *before* `extract()`. | — (transparent to manifest) |
| O2 | **Encryption** | `encrypt(path) → path` | Re-encrypt output file after injection. Situated *after* `inject()`. Must mirror the original encryption. | — (transparent to manifest) |
| O3 | **Encoding** | `detect_encoding(path) → str` **or** `encoding: str` | Calculate or declare the file encoding. When absent the pipeline uses its own heuristic (`chardet` → UTF-8 fallback from `formats/__init__.py`). | `Options.Encoding` |
| O4 | **Speaker Detection** | `detect_speakers(lines) → list[SpeakerInfo]` | Parse `Speaker: Dialogue` or format-specific speaker notation. Returns list of `SpeakerInfo(name, line_idx)`. When provided: auto-writes speakers to Analysis findings, disables the generic regex-based speaker detector in `functions/analysis.py` for this project. | `Analysis.speakers`, `characters[]` |
| O5 | **Wordwrap Config** | `wordwrap_config: WordwrapConfig` | Engine-specific wrapping settings (`max_line_length`, `max_line_number`, `wordwrap_command`, `new_textbox_injection`). Step 8 loads these as editable defaults and the parser may later realize overflow using engine syntax during output. | `Options.Wordwrap.*` |
| O6 | **Wordwrap Function** | `wordwrap(line, config) → list[str]` | Reserved parser-side custom wrapping hook. CherryAI currently keeps Step 8 on the shared `functions/wordwrap.py` path and uses parser wordwrap data mainly as defaults plus output-format metadata. | `lines[].wordwr` |
| O9 | **Pretty Wrap Hook** | `pretty_wrap(text, width, break_char, max_lines) → Optional[str]` | Optional parser wrap helper. Current Step 8 behavior does not swap the shared wrapper out globally; formats such as LightVN use parser-side textbox realization during injection. | `lines[].wordwr` |
| O7 | **Forbidden/Allowed Chars** | `forbidden_chars: ForbiddenChars` | Characters the engine cannot render. Added to logit bias during Translation (Step 5) and to the Blacklist/Whitelist during Postprocessing (Step 6). | `Options.ForbiddenChars`, `Options.LogitBias` |
| O8 | **Tags** | `tag_rules: TagRules` | Regex patterns for scene, dialogue, menu, and choice boundaries. Injected during Input to tag lines. | `lines[].tag` |

#### C. Dataclass Reference (existing + extensions)

```python
# --- Already defined in formats/parser_base.py ---
@dataclass
class WordwrapConfig:
    max_line_length: int = 0        # 0 = no limit
    max_line_number: int = 0        # 0 = no limit
    wordwrap_command: str = "\n"    # engine linebreak
    new_textbox_injection: str = "" # overflow handler

@dataclass
class ForbiddenChars:
    characters: list[str]           # chars that must not appear
    logit_bias: dict[str, int]      # token→bias mapping
    output_action: str = "replace"  # "replace" | "flag"

@dataclass
class TagRules:
    scene_pattern: str = ""         # regex
    dialogue_pattern: str = ""
    menu_pattern: str = ""
    choice_pattern: str = ""

# --- NEW for Parser Handshake ---
@dataclass
class SpeakerInfo:
    name: str          # speaker name as detected
    line_idx: int      # index into extracted lines where speaker appears
```

---

### Validation Pipeline

Validation is split into **selection-time** and **load-time** checks:

**Selection-time** (when user picks a format/parser in Step 0 dropdown):
- Verify `extract()` exists and is callable → error popup if missing.
- Verify `inject()` exists and is callable → error popup if missing.
- Verify `format_id` is non-empty or `can_handle()` is defined → error popup if
  neither.

**Load-time** (after user clicks Input to load files):
- Run `extract()` → on `ParserError`, show error popup with message.
- For each line: token-count check (>2048 → error, >1024 → warning).
- Encoding heuristic: if `detect_encoding` provided, use it and verify it can
  decode the first 8 KB of the file without errors. If heuristic, fall back
  through `chardet` → UTF-8 → Latin-1 with a warning on each fallback.

This validation must be **fast** — encoding heuristic reads the first 8 KB
only, token counting uses the fast `len(text) * 0.3` estimate for the warning
threshold and only calls `tiktoken` if the estimate exceeds 900 tokens.

---

### Manifest Integration Points

Parsers write to the manifest through the existing `ManifestManager` API.
The handshake standardises which keys are targeted:

| Parser Output | Manifest Key | Written When |
|---------------|-------------|--------------|
| Extracted lines | `lines[].orig` | Step 0 Input load |
| File directory | `file_dir[]` (with `type` field) | Step 0 Input load |
| Encoding | `Options.Encoding` | Step 0 Input load |
| Speaker list | `Analysis.speakers`, `characters[]` | Step 0 via O4 or Step 1 Analysis |
| Speaker-detect disable | `Options.ParserHandlesSpeakers` | Step 0 via O4 |
| Wordwrap config | `Options.Wordwrap.*` | Step 0 load; Step 8 reads |
| Wordwrap function flag | `Options.ParserHandlesWordwrap` | Step 0 load; metadata available to Step 8/output wiring |
| Forbidden chars | `Options.ForbiddenChars` | Step 0 load; Step 5 logit bias |
| Context markers | `lines[].tags` | Step 0 via O8 or Step 1 Analysis |
| Decryption/Encryption | (transparent) | Step 0 before extract / Step 9 after inject |

---

### Implementation Plan

#### TASK P1: Define `ParserHandshake` Protocol
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `formats/handshake.py` with a `ParserHandshake` Protocol class
  documenting all mandatory and optional components.
- Add `SpeakerInfo` dataclass.
- Add `ParserError` exception class for mandatory-component failures.
- Add `validate_parser(parser) → list[str]` that returns error messages for
  missing mandatory components (empty list = valid).

**Files to Create:**
- `formats/handshake.py`

**Files to Modify:**
- `formats/__init__.py` — export `ParserHandshake`, `ParserError`,
  `validate_parser`, `SpeakerInfo`

**Tests to Add:**
- `dev/test_parser_handshake.py`:
  - `test_txt_handler_satisfies_handshake`
  - `test_csv_handler_satisfies_handshake`
  - `test_json_handler_satisfies_handshake`
  - `test_rpgmaker_parser_satisfies_handshake`
  - `test_missing_extract_raises`
  - `test_missing_inject_raises`
  - `test_missing_format_id_raises`
  - `test_optional_components_absent_ok`

---

#### TASK P2: Integrate Validation into Step 0 (Input)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

- On parser/format selection in Step 0, run `validate_parser()`.
  Missing mandatory → error popup, block load.
- After `extract()`, run per-line token validation (>2048 error, >1024 warning).
- Add encoding heuristic (8 KB probe, BOM → parser → utf-8 → shift_jis → cp932 → latin-1 fallback chain).
- Show error popups via `tkinter.messagebox.showerror`.

**Files Modified:**
- `gui/steps/input_extract.py` — `_validate_parser_selection()`, `_validate_extracted_lines()`,
  `_estimate_tokens()` (static method, tiktoken with `len*0.3` fallback),
  `_detect_encoding()` (8 KB probe, BOM → parser `detect_encoding()` → utf-8 → shift_jis → cp932 → latin-1)
- Wired into `_load_file()` (parser validation + token validation before loading)
- Wired into `_load_selected_paths()` (batch parser validation before file loop)

**Tests:** `dev/test_parser_input_routing.py` — 32 tests (all passing):
- TestHandshakeValidation (5): valid parser, missing extract, missing inject, missing identity, all registered parsers pass
- TestTokenValidation (4): short text, empty, long text, normal lines pass
- TestEncodingFallback (6): utf-8 BOM, utf-16 BOM, plain utf-8, shift_jis, latin-1 fallback, parser encoding preferred

---

#### TASK P3: Wire Optional Components into Pipeline
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Wired each optional component to its consuming pipeline step:

- **O3 Encoding**: Parser `detect_encoding()` preferred in 8 KB probe chain (P2).
- **O4 Speaker Detection**: `_wire_parser_optionals()` calls `detect_speakers()`,
  writes `SpeakerInfo` list to `characters[]`, sets `Options.ParserHandlesSpeakers`.
  Analysis step reads flag and skips generic speaker detection.
- **O5 Wordwrap Config**: `_apply_parser_wordwrap_defaults()` auto-populates
  wordwrap fields from `wordwrap_config` on tab entry (already done pre-P3).
- **O6 Wordwrap Function**: `_wire_parser_optionals()` sets
  `Options.ParserHandlesWordwrap`. Current runtime uses this as parser wordwrap metadata
  for Step 8 defaults and output-path behavior rather than replacing the shared
  `apply_wordwrap()` pass.
- **O9 Pretty Wrap Hook**: `parser.pretty_wrap(text, width, break_char, max_lines)`
  remains the lighter parser wrap helper. Current runtime does not globally replace
  the shared Step 8 wrapper with it; LightVN instead preserves explicit wrapped lines
  and realizes textbox overflow during parser injection.
  Detected via `type(parser).pretty_wrap is not ParserScript.pretty_wrap`.
- **O7 Forbidden Chars**: `_wire_parser_optionals()` serialises
  `forbidden_chars.to_dict()` to `Options.ParserForbiddenChars`. Translation
  step calls `api_client.apply_parser_forbidden_chars()` to merge into logit bias.
- **O8 Context Markers**: `_wire_parser_optionals()` compiles
  `tag_rules` and applies regex to extracted lines, writing
  `tag` tags. `detect_tags()` in `functions/analysis.py`
  accepts optional `parser_rules` parameter to override built-in heuristics.
- **O1/O2 Decrypt/Encrypt**: Parser-level hooks now exist in `ParserScript` and can be exposed as explicit no-op pass-throughs for exported/unpacked content. Native encrypted archive handling remains deferred pending permission UX and a defensible format implementation.

### FEATURE: WOLF RPG JSON + Text Parser Formats

Goal: Add CherryAI-compliant parser formats for the two relevant Dazed WOLF parser surfaces: exported/unpacked JSON data (`wolf.py`) and line-based WOLF text scripts (`wolf2.py`), while mirroring Dazed's code/flag naming in extraction tags.

What changed:
1. **`formats/wolf_rpg.py`** — Added `WolfRPGJsonParser` for JSON files containing `events`, `types`, or `commands`, with structural injection and Dazed-mirroring tags: `CODE101`, `CODE102`, `CODE122`, `CODE150`, `CODE210`, `CODE250`, `CODE300`, `SCENARIOFLAG`, `OPTIONSFLAG`, `NPCFLAG`, `DBNAMEFLAG`, `DBVALUEFLAG`, `ITEMFLAG`, `STATEFLAG`, `ENEMYFLAG`, `ARMORFLAG`, `WEAPONFLAG`, `SKILLFLAG`.
2. **`formats/wolf_rpg.py`** — Added `WolfRPGTextParser` for line-based WOLF text scripts with cp932 / Shift-JIS detection, speaker-aware grouped dialogue extraction, `//選択肢` choice extraction, and in-place speaker/dialogue/choice injection.
3. **`formats/parser_base.py`** — Added explicit default `decrypt()` / `encrypt()` hooks plus capability metadata flags so plain exported formats can declare O1/O2 pass-through behavior without pretending to own native binary archive crypto.
4. **`formats/__init__.py`** — Registered both WOLF parsers for auto-detection and direct format selection.
5. **`dev/test_parser_scripts.py`** — Added focused regressions for WOLF JSON auto-detection, full code/flag tag coverage, JSON injection, WOLF text encoding/extraction/injection, and O1/O2 capability reporting.
6. **Documentation** — Updated `doc/features.md`, `doc/technical.md`, `doc/specs.md`, and `doc/tests.md` to describe the new parser formats and their current scope.

Verified command:
- `python -m pytest dev/test_parser_scripts.py -k "WolfRPG" -q --timeout=20` — 8 passed

**Files Modified:**
- `gui/steps/input_extract.py` — `_wire_parser_optionals()` (~100 lines) called
  between `_ensure_project_created` and `_save_manifest_after_file_load`
- `gui/steps/analysis.py` — reads `ParserHandlesSpeakers`, skips generic speakers
- `gui/steps/wordwrap_overwrite.py` — reads `ParserHandlesWordwrap`, delegates
  to `parser.wordwrap()` per line
- `gui/steps/output_inject.py` — detects parser from `filedir[].format`, routes through `parser.inject_to()`
- `gui/steps/translate.py` — reads `ParserName`, calls `apply_parser_forbidden_chars()`
- `functions/analysis.py` — `detect_tags()` accepts `parser_rules` kwarg

**Tests:** `dev/test_parser_optional_wiring.py` — 28 tests (all passing):
- TestO4SpeakerDetection (4): returns list, name+idx, no-override returns None, override check
- TestO6CustomWordwrap (4): has override, short line, long line, no-override returns None
- TestO7ForbiddenChars (4): exists, has characters, serialisable round-trip, RPG Maker check
- TestO8ContextMarkers (7): default heuristics, parser rules override, empty lines, LightVN rules exist, compile, dialogue match, no-rules+no-lines
- TestWireParserOptionals (7): parser name stored, speaker flag, wordwrap flag, forbidden chars dict, context markers flag, all LightVN optionals, info flags match checks
- TestAnalysisSpeakerSkip (2): without speakers, with speakers

---

#### TASK P4: Retrofit Existing Handlers to Handshake
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Verified and annotated all existing handlers:

- `TxtHandler` — M1 ✓, M2 ✓, M3 ✓ (extensions: `.txt`). No optionals.
- `CsvHandler` / `TsvHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `JsonHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `XlsxHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `HtmlHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `MarkdownHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `JsonLenientHandler` — M1 ✓, M2 ✓, M3 ✓. No optionals.
- `TranslatorPlusHandler` — M1 ✓, M2 ✓, M3 ✓. O3 (encoding — SQLite). No others.
- `RpgMakerMVParser` — M3 ✓ (via `can_handle`). O5 ✓, O7 ✓, O8 ✓. M1/M2 stubs raise `ParserError`.
- `RpgMakerMZParser` — same as MV with different constants. M1/M2 stubs raise `ParserError`.

RPG Maker handler stubs (`formats/rpgmaker.py`) now raise `ParserError` with
`parser_name` and `component` metadata instead of silently returning empty
results. All registered FormatHandlers pass `validate_parser()`.

**Files Modified:**
- `formats/rpgmaker.py` — extract/inject raise `ParserError` on all three stubs

**Tests:** `dev/test_parser_handler_retrofit.py` — 28 tests (all passing):
- TestFormatHandlerCompliance (9): all extract, all inject, all identity, txt/csv/tsv/json/xlsx individual, validate_parser on all
- TestParserScriptCompliance (4): all parsers pass, LightVN valid, RPGMakerMV valid, RPGMakerMZ valid
- TestRpgMakerStubs (9): MV extract/inject raise, MZ extract/inject raise, plugin extract/inject raise, MV parser delegates raise, MZ parser delegates raise, error metadata
- TestRpgMakerParserOptionals (6): MV wordwrap, MZ wordwrap, MV forbidden chars, MV context markers, MV can_handle, MZ can_handle

**Tests:**
- Expand `dev/test_parser_handshake.py` with one test per handler.

---

#### TASK P5: New Parser Template & Documentation
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 1 hour

LightVN parser (`formats/LightVN.py`) serves as the reference implementation.
All features documented in `features.md`, `technical.md`, and `tests.md`.

---

=============================================================================

## PHASE: Provider Handshake — Unified LLM Provider Interface

**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 16-20 hours

### Goal

Define a formal "handshake" contract for LLM providers so that each provider
is a self-contained module in a new `providers/` top-level folder. The contract
has **mandatory** provider-level components, **mandatory** model-level components,
and **optional** components for advanced features. The OpenAI provider serves as
the **default reference implementation** — other providers that speak the
OpenAI-compatible format can simply delegate to OpenAI's functions instead of
reimplementing them.

Failure to satisfy a mandatory component or having it return an error/unknown
value raises an error popup immediately (on provider selection for missing
functions, or on first API call attempt for runtime failures).

---

### Current Implementation Snapshot

All provider logic currently lives in scattered locations:

1. **`functions/options.py`** — Provider definitions
   - `_STATIC_PROVIDERS`: anthropic, local, ollama, lmstudio (with URLs)
   - `_CLOUD_PROVIDER_META`: openai, gemini, mistral (with registry IDs + URLs)
   - `_build_api_providers()` merges static + dynamic model lists from registry
   - `API_PROVIDERS` is a lazy proxy dict rebuilt on every access
   - Helper functions: `get_api_urls()`, `get_provider_models()`,
     `get_provider_display_name()`, etc.

2. **`functions/api_client.py`** (~2170 lines) — Monolithic API client
   - `APIConfig` dataclass (50+ fields) — all config for all providers
   - `APIClient` class — a single class handling ALL providers:
     - `_init_client()` — creates `OpenAI(...)` SDK client for ALL providers
       (including Claude and Gemini, which use OpenAI-compatible endpoints)
     - Local providers get placeholder API key `"lm-studio"`
     - Provider-specific branching scattered throughout:
       - `is_local_provider()` — checks `LOCAL_PROVIDERS` tuple
       - `is_openai_reasoning_model()` — checks for "o1", "o3" in model name
       - `is_claude_thinking_model()` — checks for "claude" + versioned names
      - `supports_prompt_caching()` — provider-driven via the registered provider capability (currently OpenAI and Mistral; Gemini excluded)
       - `supports_extended_cache_retention()` — gpt-4.1/gpt-5 only
     - `_translate_chunk()` has the biggest provider branch:
       - Local → `response_format = json_schema` (strict schema)
       - Cloud → `response_format = json_object`
       - Claude → `extra_body = thinking params`, inflated `max_tokens`
     - Token usage parsing assumes OpenAI response format
       (`usage.prompt_tokens_details.cached_tokens`, etc.)

3. **`functions/model_registry.py`** (~1730 lines) — Model data
   - `ModelInfo` dataclass with 30+ fields (pricing, rate limits, capabilities)
   - `FALLBACK_MODELS`: curated built-in data per provider (OpenAI 12, Google 7,
     Mistral 8 models) <- MUST BE REMOVED
   - Provider-specific fetchers: `fetch_openai_models()`, `fetch_google_models()`,
     `fetch_mistral_models()` — each fetches from provider API + parses pricing pages
   - `probe_openai_rate_limits()` — reads `x-ratelimit-*` headers
   - INI persistence: saves/loads model data to `user/API.ini`

4. **`functions/common_errors.py`** — Error classification
   - `classify_api_error()` inspects error type + message for provider-specific patterns
   - Categories: AUTH_INVALID, MODEL_NOT_FOUND, RATE_LIMITED, QUOTA_EXCEEDED,
     CONTENT_FILTERED, THINKING_NOT_AVAILABLE, TEMPERATURE_NOT_AVAILABLE, etc.

5. **`functions/config.py`** — loads API config from `user/API.ini`

6. **Supporting modules:**
   - `functions/local_llm.py` — `is_local_url()` helper
   - `functions/logit_bias.py` — `LogitBiasManager`
   - `functions/rate_limiter.py` — `RateLimiter`
   - `functions/batch_tracker.py` — `BatchJob` (batch API support)
   - `functions/request_cache.py` — `RequestCache`
   - `functions/retry_handler.py` — retry logic

**Key architectural problem:** Everything is routed through a single `OpenAI()`
SDK client. Provider differences are handled by scattered `if`/`elif` branches
inside `APIClient`. Adding a new provider means touching `api_client.py`,
`options.py`, `model_registry.py`, and `common_errors.py` simultaneously.

---

### Handshake Contract

#### A. MANDATORY Provider-Level Components

Every provider module **must** implement the following. Failure raises an error
popup when the provider is selected.

| # | Component | Signature / Type | Description | Validation |
|---|-----------|-----------------|-------------|------------|
| MP1 | **API Key Requirement** | `requires_api_key: bool` | `True` for cloud providers, `False` for local. Determines whether the pipeline validates and requires an API key before proceeding. When `False`, a placeholder key is used automatically. | Must be `bool`. |
| MP2 | **Input Price** | `get_input_price(model_id) → float` | Returns price in USD per 1M input tokens. For local providers returns `0.0` (FREE). Cloud providers must fetch or look up from static data. | Must be ≥ 0.0. Return `0.0` for free/local. |
| MP3 | **Output Price** | `get_output_price(model_id) → float` | Returns price in USD per 1M output tokens. Same rules as Input Price. | Must be ≥ 0.0. Return `0.0` for free/local. |
| MP4 | **Base URL** | `base_url: str` | Provider API endpoint. For OpenAI: `https://api.openai.com/v1`. For local: `http://localhost:{port}/v1`. | Must be non-empty, valid URL format. |
| MP5 | **Send Request** | `send_request(messages, model, temperature, response_format, **kwargs) → ProviderResponse` | Send a chat completion request. Returns a `ProviderResponse` with `content`, `usage`, `finish_reason`. This is the core translation call. Providers that use the OpenAI-compatible format can delegate to the default OpenAI implementation. | Must return `ProviderResponse`. Raises `ProviderError` on failure. | `temperature` may be disabled for some models and relegated to optional model.
| MP6 | **Parse Response** | `parse_response(raw_response) → ProviderResponse` | Extract translated content, token usage metadata, and finish reason from the raw API response. Must handle the provider's specific response format and normalise to `ProviderResponse`. | `ProviderResponse.content` must be non-empty on success. `ProviderResponse.usage` must populate `prompt_tokens` and `completion_tokens` at minimum. |

**`ProviderResponse` dataclass:**
```python
@dataclass
class ProviderResponse:
    content: str                           # The response text (JSON string)
    usage: TokenUsage                      # Token counts
    finish_reason: str = "stop"            # "stop", "length", "content_filter"
    raw: Any = None                        # Original response object for debugging

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # Optional extended fields — populated when provider supports them
    cached_tokens: int = 0                 # OpenAI prompt caching
    reasoning_tokens: int = 0              # o1/o3/Claude thinking
    accepted_prediction_tokens: int = 0
    rejected_prediction_tokens: int = 0
```

**`ProviderError` exception hierarchy:**
```python
class ProviderError(Exception):
    """Base error for all provider failures."""
    def __init__(self, message, is_fatal=False, error_code="UNKNOWN"):
        ...

class AuthenticationError(ProviderError):    # is_fatal=True
class ModelNotFoundError(ProviderError):     # is_fatal=True
class RateLimitedError(ProviderError):       # is_fatal=False (retryable)
class QuotaExceededError(ProviderError):     # is_fatal=True
class ContentFilteredError(ProviderError):   # is_fatal=True
class ProviderConnectionError(ProviderError): # is_fatal=False (retryable)
class ProviderTimeoutError(ProviderError):   # is_fatal=False (retryable)
```

#### B. MANDATORY Model-Level Components

Each provider must be able to report these per-model facts. These determine
whether a model is valid for use in CherryAI.

| # | Component | Signature / Type | Description | Validation |
|---|-----------|-----------------|-------------|------------|
| MM1 | **Structured Output** | `supports_structured_output(model_id) → bool` | Whether the model can return structured JSON. CherryAI requires this for line-by-line translation matching. Models without structured output are **rejected** (not shown in model dropdown). | Must be `bool`. `True` → model included, else discarded. |
| MM2 | **Model Name** | `get_model_name(model_id) → str` | Human-readable display name for the model. | Must be non-empty. |
| MM3 | **Thinking / Reasoning** | `get_thinking_config(model_id) → ThinkingConfig` | Determines if and how thinking/reasoning is implemented for the model. Returns config with `available`, `mode` ("builtin" for o1/o3, "explicit" for Claude), and `param_builder` callable. | `ThinkingConfig.available` must be `bool`. When `True`, `mode` must be "builtin" or "explicit". "builtin" are by default rejected when filtering for No / Optional Thinking which is the default. |

**`ThinkingConfig` dataclass:**
```python
@dataclass
class ThinkingConfig:
    available: bool = False
    mode: str = ""                  # "builtin" | "explicit" | ""
    budget_default: int = 10000     # default thinking token budget
    budget_min: int = 1000
    budget_max: int = 100000

    def build_params(self, budget: int) -> dict:
        """Build provider-specific API params for thinking mode."""
        if not self.available:
            return {}
        if self.mode == "builtin":
            return {}  # OpenAI o1/o3: built-in, no extra params
        if self.mode == "explicit":
            return {    # Claude: explicit thinking param
                "thinking": {"type": "enabled", "budget_tokens": budget}
            }
        return {}
```

#### C. OPTIONAL Provider-Level Components

| # | Component | Signature / Type | Description |
|---|-----------|-----------------|-------------|
| OP1 | **Cached Input** | `get_cached_input_config(model_id) → CachedInputConfig \| None` | Check whether model supports prompt caching, minimum static prompt size to trigger it, and how cached tokens are reported. Currently implemented for OpenAI and Mistral: OpenAI is prefix-based with optional 24h retention; Mistral uses `prompt_cache_key`, in-memory retention, and reports hits via `prompt_tokens_details.cached_tokens`. | Claude is know to be vastly different.
| OP2 | **Batch / Flex / Priority Mode** | `get_batch_config(model_id) → BatchConfig \| None` | Check availability of discount batch modes: Batch (50% off, 24h), Flex (variable discount), Priority (faster, premium). Returns differing input/output prices per mode. Currently only OpenAI has Batch. | Must be looked up for other providers.
| OP3 | **Model List Fetcher** | `fetch_models(api_key) → list[ModelInfo]` | Fetch available models from the provider API. Currently implemented for OpenAI, Google, Mistral. Each has its own endpoint and response format. |
| OP4 | **Rate Limit Probing** | `probe_rate_limits(api_key, model_id) → RateLimitInfo \| None` | Send a minimal request to read rate limit headers. OpenAI has explicit probing; Mistral limits are now consumed from live response headers during normal requests (`x-ratelimit-limit-req-minute`, `x-ratelimit-limit-tokens-minute`, remaining-*). |
| OP5 | **Error Classifier** | `classify_error(error) → ClassifiedError` | Provider-specific error classification. When absent, falls back to the default classifier in `common_errors.py`. |

**`CachedInputConfig` dataclass:**
```python
@dataclass
class CachedInputConfig:
    supported: bool = False
    min_prefix_tokens: int = 1024   # minimum for cache to trigger
    retention: str = ""             # "" | "in_memory" | "24h"
    cached_price_ratio: float = 0.5 # cached tokens cost this fraction of normal
    param_builder: Callable = None  # builds provider-specific params

    @staticmethod
    def openai_default() -> 'CachedInputConfig':
        return CachedInputConfig(
            supported=True,
            min_prefix_tokens=1024,
            retention="in_memory",
            cached_price_ratio=0.5,
        )
```

**`BatchConfig` dataclass:**
```python
@dataclass
class BatchConfig:
    batch_available: bool = False
    batch_input_price_ratio: float = 0.5   # vs normal price
    batch_output_price_ratio: float = 0.5
    flex_available: bool = False
    flex_input_price_ratio: float = 0.0
    flex_output_price_ratio: float = 0.0
    priority_available: bool = False
    priority_input_price_ratio: float = 1.0
    priority_output_price_ratio: float = 1.0
```

#### D. OPTIONAL Model-Level Components

| # | Component | Signature / Type | Description |
|---|-----------|-----------------|-------------|
| OM1 | **Temperature** | `get_temperature_config(model_id) → TemperatureConfig \| None` | Whether the model supports temperature, and its valid range. Some models (o1) do not support temperature at all. Others have restricted ranges. |
| OM2 | **Context Window** | `get_context_window(model_id) → int` | Maximum context window in tokens. Used for chunk size validation. |

**`TemperatureConfig` dataclass:**
```python
@dataclass
class TemperatureConfig:
    supported: bool = True
    min_value: float = 0.0
    max_value: float = 2.0
    default: float = 0.3
```

---

### Provider Module Structure

New `providers/` top-level folder alongside `functions/`, `modi/`, `formats/`:

```
providers/
├── __init__.py          # ProviderBase ABC, ProviderRegistry, ProviderResponse,
│                        #   TokenUsage, ProviderError hierarchy, dataclasses
├── openai_provider.py   # OpenAI reference implementation — delegates to existing
│                        #   functions in api_client.py. Other OpenAI-format providers
│                        #   inherit or call these functions.
├── anthropic_provider.py  # Claude via OpenAI-compat + thinking mode specifics
├── google_provider.py     # Gemini via OpenAI-compat (generativelanguage endpoint)
├── mistral_provider.py    # Mistral via OpenAI-compat
├── local_provider.py      # LM Studio / Ollama / generic local (json_schema format)
└── custom_provider.py     # Template for user-created providers (future)
```

**`ProviderBase` ABC** (in `providers/__init__.py`):
```python
class ProviderBase(ABC):
    """Base class for all LLM providers."""
    name: str                          # e.g., "openai", "anthropic"
    display_name: str                  # e.g., "OpenAI", "Anthropic (Claude)"
    requires_api_key: bool = True      # MP1
    base_url: str = ""                 # MP4

    # --- Mandatory ---
    @abstractmethod
    def send_request(self, messages, model, temperature, response_format, **kw):
        """MP5: Send a chat completion request."""
        ...

    @abstractmethod
    def parse_response(self, raw_response) -> ProviderResponse:
        """MP6: Parse raw response to ProviderResponse."""
        ...

    @abstractmethod
    def get_input_price(self, model_id: str) -> float:
        """MP2: USD per 1M input tokens."""
        ...

    @abstractmethod
    def get_output_price(self, model_id: str) -> float:
        """MP3: USD per 1M output tokens."""
        ...

    @abstractmethod
    def supports_structured_output(self, model_id: str) -> bool:
        """MM1: Can this model return structured JSON?"""
        ...

    @abstractmethod
    def get_model_name(self, model_id: str) -> str:
        """MM2: Human-readable model name."""
        ...

    @abstractmethod
    def get_thinking_config(self, model_id: str) -> ThinkingConfig:
        """MM3: Thinking/reasoning support."""
        ...

    # --- Optional (default no-ops) ---
    def get_cached_input_config(self, model_id: str):
        return None  # OP1

    def get_batch_config(self, model_id: str):
        return None  # OP2

    def fetch_models(self, api_key: str) -> list:
        return []  # OP3

    def probe_rate_limits(self, api_key: str, model_id: str):
        return None  # OP4

    def classify_error(self, error: Exception):
        return None  # OP5 — falls back to common_errors.classify_api_error()

    def get_temperature_config(self, model_id: str):
        return TemperatureConfig()  # OM1

    def get_context_window(self, model_id: str) -> int:
        return 128000  # OM2 default
```

---

### OpenAI as Default Reference

`providers/openai_provider.py` is the reference implementation. It delegates to
the existing proven functions in `functions/api_client.py` rather than rewriting
them. Other providers that speak the OpenAI-compatible format (Gemini, Mistral,
generic locals via `/v1/chat/completions`) can inherit from
`OpenAICompatProvider` and override only what differs.

```python
class OpenAIProvider(ProviderBase):
    """Reference implementation. All existing api_client.py functions stay."""
    name = "openai"
    display_name = "OpenAI"
    requires_api_key = True
    base_url = "https://api.openai.com/v1"
    # Implements all methods by calling the existing api_client.py code

class OpenAICompatProvider(OpenAIProvider):
    """Base for providers using OpenAI-compatible endpoints."""
    # Override: name, display_name, base_url, pricing, model lists
    # Keep: send_request, parse_response (identical format)

class GoogleProvider(OpenAICompatProvider):
    """Gemini via OpenAI-compat endpoint."""
    name = "gemini"
    display_name = "Google (Gemini)"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    # Override: pricing, model list fetcher, prompt caching (not supported)

class MistralProvider(OpenAICompatProvider):
    name = "mistral"
    display_name = "Mistral AI"
    base_url = "https://api.mistral.ai/v1"

class AnthropicProvider(OpenAICompatProvider):
    """Claude via OpenAI-compat proxy + thinking mode."""
    name = "anthropic"
    display_name = "Anthropic (Claude)"
    base_url = "https://api.anthropic.com/v1"
    # Override: thinking config (explicit mode), send_request (extra_body)

class LocalProvider(ProviderBase):
    """LM Studio / Ollama / generic local."""
    name = "local"
    display_name = "Local LLM"
    requires_api_key = False
    base_url = "http://localhost:11434/v1"
    # Override: send_request (json_schema format), pricing (FREE)
```

---

### Migration Path

The Provider Handshake is a **refactor**, not a rewrite. All existing features
must be preserved. The migration moves scattered provider logic from
`api_client.py` into discrete provider modules while keeping `APIClient` as
the orchestrator that delegates to the active provider.

**What moves to providers/:**
- Provider-specific request formatting (response_format branching)
- Provider-specific thinking mode params
- Provider-specific prompt caching params
- Provider-specific error classification
- Provider-specific pricing lookups
- Provider model list fetchers (from model_registry.py)
- Provider-specific rate limit probing

**What stays in api_client.py:**
- `APIClient` class as orchestrator (chunking, retry, caching, logging)
- `APIConfig` dataclass (config remains centralised)
- Translation batch orchestration (`translate_batch`, `_translate_chunk_with_retry`)
- Request caching and rate limiting (shared infrastructure)
- Step-log integration

**What stays in model_registry.py:**
- `ModelInfo` dataclass, `FALLBACK_MODELS` (curated static data)
- INI persistence (save/load to `user/API.ini`)
- Provider-specific fetch functions become thin wrappers calling provider modules

---

### Implementation Plan

#### TASK V1: Define Provider ABC and Shared Types
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `providers/__init__.py` with `ProviderBase` ABC, `ProviderResponse`,
  `TokenUsage`, `ProviderError` hierarchy, `ThinkingConfig`, `CachedInputConfig`,
  `BatchConfig`, `TemperatureConfig`, `ProviderRegistry`.
- `ProviderRegistry.register(provider)`, `get(name)`, `list_providers()`.
- `validate_provider(provider) → list[str]` — checks mandatory components.

**Files to Create:**
- `providers/__init__.py`

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_provider_base_is_abstract`
  - `test_mandatory_methods_enforced`
  - `test_optional_methods_have_defaults`
  - `test_provider_response_dataclass`
  - `test_token_usage_dataclass`
  - `test_provider_error_hierarchy`
  - `test_thinking_config_build_params`
  - `test_cached_input_config_openai_default`

---

#### TASK V2: OpenAI Reference Provider
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

- Create `providers/openai_provider.py` implementing `ProviderBase`.
- `send_request()` uses `OpenAI` SDK `client.chat.completions.create()`.
- `parse_response()` extracts `content`, `usage` (including
  `prompt_tokens_details.cached_tokens`, `completion_tokens_details.*`).
- `get_input_price()` / `get_output_price()` delegate to `model_registry`.
- `supports_structured_output()` checks `ModelInfo.structured_output`.
- `get_thinking_config()` returns builtin config for o1/o3 models.
- `get_cached_input_config()` returns OpenAI config for gpt-4o+ models.
- `fetch_models()` wraps existing `fetch_openai_models()`.
- `probe_rate_limits()` wraps existing `probe_openai_rate_limits()`.

---

### API Requests & Costs Rework (7 Tasks)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 4 hours

Goal: Fix 7 issues in the Costs step and Translation step related to API requests, pricing, and UI behavior.

**Tasks Completed:**
1. **Cache cost calculation** — Added `CACHE_HIT_RATE = 0.80` and `_get_static_prompt_tokens()` to compute static/dynamic prompt split. Cache savings = `cached_tokens / 1M × (input_rate - cached_rate)`.
2. **Mode button labels** — Batch/Flex/Priority buttons show "(Available)" or "(Unavailable)" suffix based on model pricing.
3. **Instant mode cost recalculation** — `_recalculate_costs_for_mode()` updates costs from existing token counts without re-estimation.
4. **Model lock during estimation** — Model combo disabled while estimation runs, re-enabled on complete.
5. **Settings decoupling** — Settings loaded from API.ini only once on first tab entry; model changes do not reload settings.
6. **Apply Settings to Model button** — Renamed from "Save Settings", one-way write to API.ini.
7. **Translation request mode selector** — Request Mode combobox in Translation step with unavailability detection, passed to `APIConfig.request_mode`.

**Files Modified:**
- `gui/steps/costs.py` — Tasks 1-6
- `gui/steps/translate.py` — Task 7
- `functions/api_client.py` — Added `request_mode` field to `APIConfig`

**Tests:** `dev/test_costs_api_rework.py` — 35 tests (all passing)
- `classify_error()` wraps error patterns from `common_errors.py`.

**Files to Create:**
- `providers/openai_provider.py`

**Files to Modify:**
- `providers/__init__.py` — register OpenAI provider

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_openai_satisfies_handshake`
  - `test_openai_send_request_format`
  - `test_openai_parse_response_usage`
  - `test_openai_thinking_config_o1`
  - `test_openai_cached_input_gpt4o`
  - `test_openai_pricing_lookup`
  - `test_openai_structured_output_cloud_format`

---

#### TASK V3: OpenAI-Compatible Base + Google/Mistral Providers
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

- Create `OpenAICompatProvider` class inheriting from `OpenAIProvider`.
  It reuses `send_request()` and `parse_response()` but overrides URL,
  pricing, and model fetching.
- Create `providers/google_provider.py` (`GoogleProvider`):
  - `base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"`
  - `get_cached_input_config()` returns `None` (Gemini caching not supported)
  - `fetch_models()` wraps existing `fetch_google_models()`
- Create `providers/mistral_provider.py` (`MistralProvider`):
  - `base_url = "https://api.mistral.ai/v1"`
  - `fetch_models()` wraps existing `fetch_mistral_models()`

**Files to Create:**
- `providers/google_provider.py`
- `providers/mistral_provider.py`

**Files to Modify:**
- `providers/openai_provider.py` — add `OpenAICompatProvider` base
- `providers/__init__.py` — register Google and Mistral

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_google_satisfies_handshake`
  - `test_google_no_prompt_caching`
  - `test_google_pricing_free_tier`
  - `test_mistral_satisfies_handshake`
  - `test_mistral_pricing_lookup`
  - `test_openai_compat_inherits_send_request`

---

#### TASK V4: Anthropic (Claude) Provider
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `providers/anthropic_provider.py` (`AnthropicProvider`):
  - Inherits `OpenAICompatProvider` (uses OpenAI-compat endpoint)
  - Overrides `send_request()` to inject `extra_body` with thinking params
    and inflate `max_tokens` when thinking is enabled
  - `get_thinking_config()` returns explicit mode for Claude sonnet-4/opus-4/
    haiku-4 models
  - Pricing from model registry FallbackModels or hardcoded
  - Currently no models in `FALLBACK_MODELS` — add Claude models

**Files to Create:**
- `providers/anthropic_provider.py`

**Files to Modify:**
- `providers/__init__.py` — register Anthropic
- `functions/model_registry.py` — add Claude `FALLBACK_MODELS` entries

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_anthropic_satisfies_handshake`
  - `test_anthropic_thinking_config_claude`
  - `test_anthropic_send_request_extra_body`
  - `test_anthropic_max_tokens_inflation`

---

#### TASK V5: Local Provider (LM Studio / Ollama)
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 2 hours

- Create `providers/local_provider.py` (`LocalProvider`):
  - `requires_api_key = False`
  - `send_request()` overrides `response_format` to use full `json_schema`
    with strict schema (the biggest provider-specific branch currently in
    `_translate_chunk()`)
  - All pricing returns `0.0` (FREE)
  - `supports_structured_output()` returns `True` (LM Studio and Ollama
    support JSON schema)
  - `get_thinking_config()` may return default (not available) for non-thinking local models; cloud providers override this per model family
  - `fetch_models()` queries `/v1/models` endpoint on localhost
  - Subclasses `LMStudioProvider` (port 1234) and `OllamaProvider` (port 11434)
    can override `base_url`

**Files to Create:**
- `providers/local_provider.py`

**Files to Modify:**
- `providers/__init__.py` — register Local, LMStudio, Ollama

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_local_satisfies_handshake`
  - `test_local_no_api_key_required`
  - `test_local_json_schema_format`
  - `test_local_pricing_free`
  - `test_lmstudio_port_1234`
  - `test_ollama_port_11434`

---

#### TASK V6: Integrate ProviderRegistry into APIClient
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Refactor `APIClient` to delegate to the active provider instead of using
inline `if`/`elif` branches:

- `__init__` resolves `self.provider = ProviderRegistry.get(config.provider)`
- `_translate_chunk()` replaces all provider branches with:
  - `response_format = self.provider.get_response_format(model)`
  - `thinking_params = self.provider.get_thinking_config(model).build_params(budget)`
  - `cache_params = self.provider.get_cached_input_config(model).build_params()`
  - `raw = self.provider.send_request(messages, model, temp, response_format, **extra)`
  - `result = self.provider.parse_response(raw)`
- Error handling delegates to `self.provider.classify_error(e)` with fallback
  to `common_errors.classify_api_error()`.
- `_init_client()` uses `self.provider.requires_api_key` instead of hardcoded
  `LOCAL_PROVIDERS` check.

**Critical**: This is a refactor — all existing tests must continue passing.
The observable behaviour of `APIClient` must not change.

**Files to Modify:**
- `functions/api_client.py` — refactor to use provider delegation

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_api_client_uses_provider_registry`
  - `test_api_client_local_json_schema`
  - `test_api_client_claude_thinking_delegation`
  - `test_api_client_openai_cache_delegation`
  - `test_api_client_error_classification_delegation`

---

#### TASK V7: Migrate options.py Provider Definitions
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 2 hours

Replace `_STATIC_PROVIDERS`, `_CLOUD_PROVIDER_META`, and `_build_api_providers()`
in `options.py` with lookups against `ProviderRegistry`:

- `API_PROVIDERS` becomes: `{p.name: {"url": p.base_url, "models": p.fetch_models_cached()} for p in ProviderRegistry.all()}`
- Helper functions (`get_api_urls`, `get_provider_models`, etc.) delegate to
  `ProviderRegistry`.
- `model_registry.py` fetch functions become thin redirects:
  `fetch_openai_models()` → `ProviderRegistry.get("openai").fetch_models()`.

**Files to Modify:**
- `functions/options.py` — replace provider dicts with registry lookups
- `functions/model_registry.py` — redirect fetch functions to providers

**Tests:**
- Existing tests in `dev/test_api_providers.py` must continue passing.
- `dev/test_provider_handshake.py`:
  - `test_options_api_providers_from_registry`
  - `test_model_registry_delegates_to_provider`

---

#### TASK V8: Provider Validation in Global Options UI
**Priority:** MEDIUM | **Status:** ✅ COMPLETE | **Effort:** 1 hour

When user selects a provider in Global Options:
- Run `validate_provider()` — error popup for missing mandatory methods.
- Add model selection to Model Settings so every model gets its own settings. Ensure that each writers and loads its own config. Use default values for initial. 
- When user selects a model: check `supports_structured_output()` — warn if False.
- Check if Thinking is available, `get_thinking_config().available` — hide entry if False. When user enables thinking: check `get_thinking_config().available` — warn if False. Warn users that thinking and reasoning are only known to waste money and may even negatively affect translation. Ensure that the request do not contain thinking if not supported.
- When loading temperature: check `get_temperature_config().supported` — hide entry if
  not supported, adjust slider to show valid range if available. Ensure that the request do not contain temperature if not supported.

**Files to Modify:**
- `gui/dialogs/global_options.py` — add provider validation callbacks

**Tests to Add:**
- `dev/test_provider_handshake.py`:
  - `test_provider_selection_validation`
  - `test_model_structured_output_warning`

---

#### TASK V9: New Provider Template & Documentation
**Priority:** LOW | **Status:** ✅ COMPLETE | **Effort:** 1 hour

Create a documented template showing how to add a new provider:

- Copy template, fill in `send_request()`, `parse_response()`, pricing, model list.
- For OpenAI-compatible APIs: inherit `OpenAICompatProvider`, override URL and pricing.
- For truly custom APIs: implement `ProviderBase` directly.
- Register in `providers/__init__.py`'s `_load_providers()`.
- `validate_provider()` confirms compliance.

**Files to Create:**
- `providers/provider_template.py` — documented skeleton
- `doc/adding_a_provider.md` — step-by-step guide

---

### Summary of Provider-Specific Behaviour (Reference for Migration)

This table captures every known provider-specific branch from the current
codebase that must be preserved during migration:

| Concern | OpenAI | Claude (Anthropic) | Gemini (Google) | Mistral | Local (LM Studio/Ollama) |
|---------|--------|-------------------|-----------------|---------|--------------------------|
| **SDK init** | `OpenAI(api_key, base_url)` | Same (compat proxy) | Same (compat endpoint) | Same (compat endpoint) | Same + placeholder key `"lm-studio"` |
| **response_format** | `{"type": "json_object"}` | `{"type": "json_object"}` | `{"type": "json_object"}` | `{"type": "json_object"}` | Full `json_schema` with strict schema |
| **Thinking mode** | Built-in for o1/o3 (no extra params) | `extra_body.thinking` + inflated `max_tokens` | Not supported | Not supported | Not supported |
| **Prompt caching** | Auto for gpt-4o+; 24h retention for gpt-4.1/gpt-5 | No | No | No | No |
| **Batch mode** | Yes (JSONL, 50% off) | No | No | No | No |
| **Pricing** | Per-model (model_registry) | Default $1/$2 per M (no registry models yet) | FREE tier (some paid) | Per-model (model_registry) | FREE ($0.0) |
| **Token usage** | Full details (cached, reasoning, prediction) | Basic (prompt + completion) | Basic (prompt + completion) | Basic (prompt + completion) | Basic (prompt + completion) |
| **Error patterns** | All categories from `classify_api_error()` | Same (via compat) + thinking-specific | Same (via compat) + content filter likelihood | Same (via compat) | Connection errors more common |
| **Rate limit headers** | `x-ratelimit-*` (probeable) | Not available | Not available | `x-ratelimit-limit-req-minute`, `x-ratelimit-limit-tokens-minute`, remaining-* | Not applicable |
| **Model fetcher** | `fetch_openai_models()` — `/v1/models` + pricing page HTML | None (hardcoded) | `fetch_google_models()` — `/v1beta/models` + pricing page | `fetch_mistral_models()` — `/v1/models` | `/v1/models` on localhost |
| **Logit bias** | Supports `logit_bias` param | Not supported (ignored) | Limited support | Not supported | Varies by backend |
| **Temperature** | 0.0-2.0 (some models no temperature: o1) | 0.0-1.0 | 0.0-2.0 | 0.0-1.0 | Varies |

---

=============================================================================

Goal: Add category-aware right-click menu to the existing Findings Table. The
menu dynamically shows options based on the Category of selected row(s).

**Approach:**
- Keep existing Findings Table (do NOT split into separate tables)
- Add right-click context menu that inspects the Category column
- Show Speaker-specific options when Category = "Speakers"
- Show Code Pattern-specific options when Category = "Code Patterns"
- Show only generic options (Copy, Select All) when mixed categories selected

**Speaker Options:**
- Add to Glossary (writes to character glossary in manifest `characters` key)
- Set Role → (Protagonist | Love Interest | Major | Minor)
- Set Gender → (Male | Female | Other → Non-Binary | Transwoman | Transman)
- Set Translation → Custom Input dialog
- Add to Code Database (writes to manifest code database)
- Copy Name
- Select All with Speaker (sets filter)

**Code Pattern Options:**
- Preserve / Provides Context / Custom Placeholder / Protect (Generic Placeholder) / Strip with Anchor / Part of a Span (persisted to Code Database)
- Action sync: Protect → ProtectCodePatterns, Custom Placeholder → CustomPlaceholders, Strip with Anchor → AnchorRemoval (auto-synced via sync_code_pattern_actions in manifest_fields.py)
- Legacy migration: translate→provides_context, remove→preserve, replace→protect
- Is a Name / Is Text / Is a Number / Is Invisible (type classification)
- Nameable... (expanded dialog with Character/Company/Location modes,
  Custom Replacement, Role, Gender, Notes, OK/Cancel/Apply)
- Copy Pattern
- Show Lines with Pattern (sets filter)

**Enhancements Implemented:**
- All speakers shown (no truncation), ordered by count descending
- Individual code patterns shown instead of type summaries
- Details column auto-populated: sample lines for speakers, type + examples for codes
- Count Filter field: supports `<X`, `>X`, `<=X`, `>=X`, `=X` syntax
- Count Filter toggle button: switches between ≥ (default) and ≤ for bare numbers
- All code pattern actions persist to manifest via `save_code_glossary()`
- "Is a Name" adds to glossary with temp replacement
- "Nameable..." opens expanded dialog for character/company/location assignment
- Speaker actions write to character glossary (manifest `characters` key) via `_upsert_character_entry()`
- Gender support expanded: Male, Female, Non-Binary, Transwoman, Transman
- Import from Analysis dialogs offer choice of how many to import (non-destructive)
- Enhanced speaker detection: balanced bracket validation, no-newline rule, script-aware length limits (≤30 Latin / ≤20 CJK)
- Speaker Threshold (Global Options → Utility → Misc, default 10): below-threshold speakers collapsed into "[+] N Speakers" row; excluded from Glossary import and Term Translation

**Files Modified:**
- `gui/steps/analysis.py` - Right-click binding, dynamic menu, pattern actions, Nameable dialog
- `gui/helpers/analysis_adapter.py` - `detect_individual_codes_batch()`, speaker samples
- `gui/components/table.py` - Count filter entry with ≥/≤ toggle, `_parse_count_filter()`, updated `_apply_filter()`
- `functions/glossary.py` - Added GENDER_NONBINARY, GENDER_TRANSWOMAN, GENDER_TRANSMAN
- `gui/helpers/glossary_adapter.py` - New gender constant exports
- `functions/manifest_fields.py` - Added gender field to glossary entry schema

**Tests:**
- `dev/test_analysis_context_menu.py` - Category detection, menu options, no-truncation
- `dev/test_analysis_actions.py` - Glossary integration, role/gender persistence
- `dev/test_analysis_findings.py` - Individual codes, count filter, protagonist, details population

---

### TASK 59.4: Speaker Context Menu Actions
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement the Speaker-specific actions for the Findings Table context menu.
When user right-clicks on rows with Category = "Speaker", these options appear.

**Menu Actions to Implement:**
- Add to Glossary: Creates character glossary entry, original_name = speaker name, Translation empty
- Set Role → Protagonist | Love Interest | Major | Minor
  - Stored in character glossary entry's role field
- Set Gender → Male | Female | Other → (Non-Binary | Transwoman | Transman)
  - Stored in character glossary entry's gender field
- Set Translation → Dialog prompt
  - User enters custom translation
  - Fills character glossary entry's name (translation) field
- Add to Code Database: Creates manifest Code Database entry to protect speaker name
- Copy Name: Copies speaker name to clipboard
- Select All with Speaker: Filters preview panel to show lines from this speaker

**Multi-Select:**
- Support bulk operations: "Add X speakers to Glossary"
- Role/Gender apply to all selected

**Files to Modify:**
- `gui/steps/analysis.py` - Menu handler for speaker actions, character glossary helpers (`_upsert_character_entry`, `_load_characters`, `_save_characters`)
- `functions/manifest_fields.py` - `save_character_notes()`, `load_character_notes()` for character glossary

**Tests to Add:**
- `dev/test_analysis_actions.py`:
  - `test_add_speaker_to_glossary`
  - `test_set_speaker_role`
  - `test_set_speaker_gender`
  - `test_set_speaker_translation`
  - `test_speaker_multi_select_bulk`
  - `test_character_notes_populated`

---

### TASK 59.5: Code Pattern Context Menu Actions
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** 3 hours

Goal: Implement the Code Pattern-specific actions for the Findings Table context 
menu. When user right-clicks on rows with Category = "Code Patterns", these options
appear.

**Action Options (persisted to Code Database via `save_code_glossary()`):**
- Preserve: Keep pattern unchanged in translation (default)
- Remove: Remove pattern from output
- Translate: Translate pattern as regular text
- Replace → Generic (placeholder) | Custom Input (dialog)

**Type Options (stored in notes field):**
- Is a Name: Pattern represents a character name — also adds to glossary with temp replacement
- Is Text: Pattern represents visible text content
- Is a Number: Pattern represents numeric values
- Is Invisible: Pattern is control code (default)

**Protagonist Variable Support → Nameable Dialog:**
- Nameable...: Opens expanded dialog for assigning replacement to code pattern
- Three modes: Character, Company, Location — each pre-fills suitable defaults
- Fields: Custom Replacement, Role dropdown, Gender dropdown, Custom Notes
- OK / Cancel / Apply buttons for persistence control
- Warns if entry already exists (overwrite confirmation)
- Replacement name stored in character glossary (manifest `characters` key) and code pattern stored in Custom Placeholders (manifest `CustomPlaceholders` key, restore_after=True)

**Utility Options:**
- Copy Pattern: Copy to clipboard
- Show Lines with Pattern: Sets findings table filter to show pattern

**Code Database Integration:**
- All actions persisted via `_upsert_code_pattern()` → `save_code_glossary()`
- Stored as `code_patterns[]` in manifest data
- Populates Code Database in Information Step (Step 3)
- Populates Preprocessing options (Step 4)
- LLM prompt includes action/type info for special handling

**Multi-Select:**
- Support bulk operations: "Set X patterns to Preserve"
- Action and Type apply to all selected

**Files Modified:**
- `gui/steps/analysis.py` - Pattern action handlers with persistence, protagonist feature
- `functions/manifest_fields.py` - `save_code_glossary()`, `load_code_glossary()`

**Tests:**
- `dev/test_analysis_actions.py` - Pattern action options, multi-select, code glossary

---

[Archived: Session 33: Manifest Rework → see doc/archived.md]

[Archived: Phase 60: UX Polish & Preset Rework → see doc/archived.md]

[Archived: Information Step UI Improvements → see doc/archived.md]


[Archived: Information Step Functional Enhancements → see doc/archived.md]

[Archived: 2026 User-Folder & Security Overhaul + Sessions 29–30 → see doc/archived.md]

[Archived: Session 30 TASK 74 + Phase 78 + Dynamic Registry + API Keys → see doc/archived.md]

---

### TASK 75+: Utility Section Expansion — Term Translation & Gender Inference
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Expand Global Options → Utility section with per-feature API key/model
selection, batch size control, configurable gender inference modes, and error
abort on API failure.

**Term Translation:**
- Mode dropdown: Romaji / LLM (legacy Simple/MTL migrate to Romaji)
- API key provider + key name dropdowns populated from API.ini [api_keys]
- Model **Combobox** auto-populated via `_update_term_model_list()` → `get_provider_models(provider)` when API key changes
- Batch size spinbox (1–100, default 10); `_worker` calls `translate_terms()` which splits internally
- API.ini [term_translation] profile stores provider/key_name/model
- Code validation: `extract_code_segments()` + `validate_translation_code()` — skip terms with missing code segments
- Skip empty/whitespace-only/identical results silently
- Partial save on error: `_save_results()` persists all successful translations before showing error messagebox
- RuntimeError on missing key or API failure, caught in analysis.py

**Gender Inference:**
- Mode dropdown: Script only / Script + LLM
- "Script only" runs heuristic pass with configurable confidence (min/max)
- "Script + LLM" runs script first, then LLM on remaining unknowns
- Separate API key/model controls (stored in API.ini [gender_inference])
- Model **Combobox** auto-populated via `_update_gender_model_list()` → `get_provider_models(provider)` when API key changes
- LLM confidence spinboxes (min/max, default 3/5)
- ignore_unknown / do_all checkboxes for both script and LLM
- RuntimeError on LLM failure shown via messagebox

**UtilitySettings dataclass:** Expanded from 1 to 17 fields with full
to_dict/from_dict roundtrip and legacy mode migration.

**Files Modified:**
- `gui/dialogs/global_options.py` — UtilitySettings, _build_utility_section (Combobox model fields, _update_term_model_list, _update_gender_model_list), _on_apply, save defaults
- `functions/term_translation.py` — Rewritten: batch splitting, API.ini profile, RuntimeError, extract_code_segments(), validate_translation_code()
- `functions/API2Glossary.py` — infer_gender_llm(), _has_consensus(), _call_api_for_excerpt_custom()
- `gui/steps/analysis.py` — _worker() batch processing via translate_terms(), code validation, skip-empty, _save_results()/_finish_with_error() partial save on error
- `gui/steps/information.py` — Rewritten _infer_character_genders() with two modes

**Tests:**
- `dev/test_utility_settings.py` — 57 unit tests (dataclass, batching, consensus, error abort, model dropdown)
- `dev/test_utility_integration.py` — 7 live API tests with gpt-4.1-nano
- `dev/test_term_translation.py` — 100 tests (batch, skip-empty, code validation, partial save, manifest-only persistence, chunk save, code patterns in prompt)

---

### TASK 75++: Structured Output, Configurable Prompts & Token Efficiency
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Minimise output-token waste (previously 2k input → 33k output in 15
requests) by enforcing strict JSON-schema structured output and adding `max_tokens`
caps. OpenAI requests may also use `store=False`. Make prompts for Term Translation and Gender Inference
configurable in Global Options → Prompts. Hide Edit/TLC prompt sections.

**Structured Output (json_schema):**
- `term_translation.py` — `_TERM_TRANSLATION_SCHEMA` with strict `{"translations": [...]}` schema
- `API2Glossary.py` — `RESPONSE_SCHEMA` with single `details` string field (no enum constraint; accepts any gender value)
- `store=False` is sent for OpenAI utility requests; strict providers such as Mistral omit unsupported extra fields
- `term_translation.py` — `max_tokens=max(100, len(terms) * 20)`
- `API2Glossary.py` — `max_tokens=150`

**Configurable Prompts (Global Options → Prompts):**
- Three new PromptsSettings fields: `term_glossary`, `term_code`, `gender_inference`
- Three new DEFAULT constants with `{source_lang}`, `{target_lang}`, `{count}` (term) and `{name}`, `{excerpt}` (gender) placeholders
- `_get_prompt_template(prompt_type)` in term_translation.py reads from CherryAI.ini `[prompts]`
- `_get_gender_prompt(name, excerpt)` in API2Glossary.py reads from CherryAI.ini `[prompts]`
- Fallback to compiled-in defaults when ini has no value

**Prompt Type Routing:**
- `translate_term()` and `translate_terms()` accept `prompt_type="glossary"|"code"` kwarg
- `analysis.py _translate_terms()` passes `prompt_type="glossary"` for characters, `"code"` for code patterns

**Gender Normalization:**
- `_normalize_gender()` performs case-insensitive normalization via `_KNOWN_GENDERS` lookup dict
- Maps known values to canonical forms: female→Female, male→Male, non-binary→Non-Binary, etc.
- Maps Unsure/Unknown→Unknown, Neutral→Non-Binary
- Any unrecognized value is title-cased (e.g. "other"→"Other")
- All API result handlers use `_normalize_gender()` for consistent downstream values

**UI Changes (Global Options → Prompts):**
- Three utility prompt LabelFrames at top: Glossary, Code, Gender Inference
- Each has a Text widget + scrollbar + "Reset to Default" button
- Edit Step Prompt and TLC Step Prompt sections hidden (widgets exist for data round-trip)

**Files Modified:**
- `gui/dialogs/global_options.py` — PromptsSettings + 3 new defaults + UI sections + hide Edit/TLC
- `functions/term_translation.py` — json_schema, provider-gated `store=False`, max_tokens, prompt_type, configurable prompt
- `functions/API2Glossary.py` — json_schema single details field (no enum), provider-gated `store=False`, max_tokens=150, case-insensitive _normalize_gender, configurable prompt
- `gui/steps/analysis.py` — prompt_type="glossary" / "code" pass-through

**Tests:**
- `dev/test_utility_settings.py` — Expanded to 63 tests (+26 new: PromptsSettings fields, prompt_type routing, _get_prompt_template, _normalize_gender case-insensitive normalization, schema validation with details field)

---

### Phase 78.2: API Error Classification, Concurrent Execution & Validation
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Classify all API errors with user-facing messages and remediation steps,
add first-request validation gate, implement concurrent string execution, sort
requests by content type, and fix context-type conditional prompt injection.

**Completed Sub-tasks:**
1. ✅ API Error Classification System (`functions/common_errors.py`)
   - 20-category APIErrorCategory enum, ClassifiedAPIError dataclass
   - classify_api_error() maps exceptions to categories
   - TranslationAbortError with format_for_display()
2. ✅ First-Request Validation Gate (`gui/steps/translate.py`)
   - First chunk sent alone; fatal errors abort immediately
3. ✅ Retryable Non-Structured Output + API Log Failure Capture (`functions/api_client.py`)
  - _translate_chunk_with_retry() now keeps invalid/non-JSON structured-output failures on the retry path and only aborts after retries are exhausted
  - _translate_chunk() logs API-call failures, invalid JSON, invalid `translations` payloads, and discarded line-count mismatches to the structured API Log before re-raising
4. ✅ Request String Sorting by Type (`functions/prompt_builder.py`)
   - sort_requests_by_type(): Dialogue > Choice > Mixed/Unknown > Menu
   - RequestString dataclass with priority, RC chain detection
5. ✅ Concurrent Request Execution (`gui/steps/translate.py`)
   - ThreadPoolExecutor parallel strings, sequential within string
   - _group_chunks_into_strings(), _process_single_chunk(), _execute_string_sequential()
   - Thread-safe progress via threading.Lock
6. ✅ Context-Type Conditional Prompt Fix (`gui/steps/translate.py`)
   - _translate_chunk() now passes context_type to _build_system_prompt_from_manifest()
   - Enables §5.2 item 7b injection (was silently missing)

**Files Modified:**
- `functions/common_errors.py` — APIErrorCategory, ClassifiedAPIError, classify_api_error, TranslationAbortError
- `functions/api_client.py` — _translate_chunk_with_retry rewrite, _translate_chunk error classification
- `functions/prompt_builder.py` — _CONTEXT_TYPE_PRIORITY, RequestString, sort_requests_by_type, _build_string
- `gui/steps/translate.py` — Concurrent engine, validation gate, _process_single_chunk, context_type fix

**Tests (133 total):**
- `dev/test_api_error_classification.py` — 56 tests
- `dev/test_first_request_gate.py` — 14 tests
- `dev/test_request_sorting.py` — 22 tests
- `dev/test_concurrent_execution.py` — 23 tests
- `dev/test_context_type_prompts.py` — 18 tests

---

### FEATURE: Translation Step Number of Threads + Requests / Second Control
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Expose the existing concurrent request limit in Translation Step →
Request Options as a user-facing **Number of Threads** control, add an optional
**Requests / Second** pacing control beside it, persist both values, and verify
that live concurrent requests still return outputs in sorted order while paced
requests stay below the target rate.

**Completed Sub-tasks:**
1. ✅ Added **Number of Threads** `ttk.Spinbox` below Request Mode in
  `gui/steps/translate.py` (range 1-32, default 3)
2. ✅ Bound the widget to manifest field `RequestOptions.NumberOfThreads`
3. ✅ Added `TranslationOptions.max_concurrent` and returned it from
  `_get_options_from_ui()`
4. ✅ Applied the UI value to `self._api_client.config.max_concurrent` in
  `_do_translation()`
5. ✅ Restored the value from both manifest data and per-model `API.ini`
  `max_concurrent`
6. ✅ Fixed `_on_request_mode_changed()` to update
  `TranslationOptions.request_mode` with normalized keys instead of mutating
  `request_slicing`
7. ✅ Added regression coverage for request-option round-trip and sorted output
  under out-of-order future completion
8. ✅ Ran a live `gpt-4.1-nano` smoke test on four tiny Japanese lines:
  ordered output preserved, 1 worker = 6.446 s, 3 workers = 2.646 s
9. ✅ Follow-up bug fix: Translation-tab re-entry now preserves the saved
  manifest thread count instead of resetting to per-model/default `3`; normal
  transient 429 rate limits pause for 60 seconds before retry, while
  quota/billing/account-limit 429 messages abort immediately with a warning
  dialog; legacy lowercase `CherryAI.ini` aliases for Summary/SystemInstruction
  presets are normalized to canonical mixed-case keys
10. ✅ Added **Requests / Second** checkbox + float spinbox below Number of
  Threads in `gui/steps/translate.py`, persisted to
  `RequestOptions.RequestsPerSecondEnabled` /
  `RequestOptions.RequestsPerSecond` (range `0.01`-`999.99`)
11. ✅ Added shared API-client request-start pacing in
  `functions/api_client.py` so concurrent Translation workers respect one
  project-level RPS cap
12. ✅ Added adaptive RPS slowdown parsing for provider 429 text plus fallback
  reduction rules (`stated value` else `current × 0.9` below `1`, `current ×
  0.75` above `1`, unlimited treated as `50` before reducing)
13. ✅ Added official `mistral-medium-2505` fallback pricing/context metadata
  from the current Mistral Medium 3 model card and fixed model lookup to prefer
  curated fallback pricing over stale persisted unknown-pricing entries for the
  same model id
14. ✅ Added focused regressions in `dev/test_api_client.py`,
  `dev/test_translate_manifest.py`, and `dev/test_model_registry.py`
15. ✅ Added live verification script `dev/test_mistral_rps.py`; observed that
  an 8-request burst against `mistral-medium-2505` did not trigger a provider
  429 on the Experimental plan key, while a paced `0.40 RPS` run completed
  successfully and respected the configured delay
16. ✅ Follow-up Step 5 restore fix: manifest-saved model, Number of Threads,
  and Requests / Second values are now reapplied after Global Options and
  per-model defaults on Translation-tab re-entry, so projects like Kano no
  longer fall back to `Mock Translation`, default thread count, or `1.00 RPS`
17. ✅ Legacy manifest compatibility: Translation now restores older top-level
  `RequestsPerSecond` values on reopen and mirrors the current project RPS back
  to that key on save for backward-compatible round-trips
18. ✅ Progress window follow-up: the active `Processing chunk X/Y` line is now
  replaced by the final chunk result, and close/cancel is blocked while
  outstanding requests remain, reporting the remaining request count instead
19. ✅ Added focused regressions for the follow-up fixes in
  `dev/test_translation_status_cache.py` and `dev/test_api_client.py`

**Files Modified:**
- `gui/steps/translate.py` — Number of Threads UI, manifest/model restore,
  runtime max_concurrent wiring, request-mode bug fix, manifest-precedence fix,
  quota warning dialog routing
- `dev/test_request_preview.py` — 5 request-options regression tests
- `functions/common_errors.py` — explicit quota/billing 429 phrase detection
- `functions/api_client.py` — fixed 60-second transient 429 retry pause for chunked and line-by-line translation
- `functions/ini_manager.py` — canonical mixed-case alias normalization before seeding
- `dev/test_concurrent_execution.py` — sorted-completion ordering regression
- `dev/test_api_error_classification.py` — classifier phrase coverage + 60-second retry regressions
- `dev/test_ini_manager.py` — lowercase alias normalization regression

**Tests:**
- `C:/Python314/python.exe -m pytest dev/test_request_preview.py dev/test_concurrent_execution.py -q --timeout=20`
  → 75 passed, 2 skipped

---

### Phase 60: Input Step Improvements
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Fix Type column display bug, replace Sort Combobox with clickable column headers,
add file list filter, and implement cross-file preview search with automatic file switching.

**Completed Sub-tasks:**
1. ✅ Type Column Refresh Fix (`gui/steps/input_extract.py`)
   - Added `_update_file_list()` call after `_ensure_project_created()` + `_save_manifest_after_file_load()` in all 3 loading methods
   - Root cause: `_update_file_list()` was called before `_sync_lines_to_manifest()` set file types via `classify_file_type()`
2. ✅ Clickable Column Headers (`gui/steps/input_extract.py`)
   - Replaced Sort Combobox with clickable Name/Type/Lines column headings
   - ▲/▼ indicators for ascending/descending sort direction
   - Same column click toggles direction; different column resets to ascending
   - New attributes: `_sort_column`, `_sort_ascending`
   - New methods: `_on_column_sort()`, `_refresh_sort_headings()`
3. ✅ File List Filter (`gui/steps/input_extract.py`)
   - Filter Entry replaces Sort Combobox frame area
   - Matches against display name, file type, or line count (case-insensitive)
   - ✕ clear button resets filter; filter resets on New Project
   - New widgets: `_file_filter_var`, `_file_filter_entry`, `_file_filter_clear_btn`
4. ✅ Cross-File Preview Search (`gui/steps/input_extract.py`)
   - Added `idx` column to preview Treeview
   - Search text triggers cross-file search across ALL loaded files
   - Selecting a result auto-switches to the containing file in the file tree
   - ✕ clear button restores single-file preview mode
   - New methods: `_update_preview_single_file()`, `_update_preview_cross_file()`, `_on_preview_select()`, `_select_file_in_tree()`, `_on_preview_search_clear()`

**Files Modified:**
- `gui/steps/input_extract.py` — All 4 improvements

**Tests (60 total):**
- `dev/test_input_step_improvements.py` — 60 tests (all passing)

=============================================================================
TASK: INFORMATION STEP UI REFINEMENTS
=============================================================================
Status: ✅ COMPLETE

Goal: Three visual and UX refinements to the Information Step (Step 2).

1. ✅ Disabled Textbox Greying (`gui/steps/information.py`)
   - `_apply_widget_enabled_state()` static method: sets bg/fg for ScrolledText
   - THEME.bg_disabled / THEME.text_disabled when disabled; white/black when enabled
   - Applied to Summary, Style, Tone, System Instructions fields
   - Called by `_toggle_section_enabled()` and `_load_section_toggles()`

2. ✅ Button Right-Alignment (`gui/steps/information.py`)
   - Save, Delete, Toggle buttons for Style, Tone, SI now use `side="right"` pack
   - Reversed pack order (toggle → delete → save) for correct visual left-to-right
   - Matches existing Summary section button layout

3. ✅ Table Sorting by Count + Clickable Headers (`gui/steps/information.py`)
   - Glossary (Characters) defaults to count descending, Code Database already did
   - All column headings clickable: ascending → descending → reset to count
   - ▲/▼ arrows in active sort column heading
   - Glossary uses `char_{idx}` tags via `_get_char_idx()` for index mapping
   - Manifest saves in count-descending order for both tables
   - New attributes: `_char_sort_col`, `_char_sort_reverse`, `_char_sort_clicks`
   - New attributes: `_code_sort_col`, `_code_sort_reverse`, `_code_sort_clicks`
   - New methods: `_on_char_heading_click()`, `_update_char_heading_arrows()`
   - New methods: `_on_code_heading_click()`, `_update_code_heading_arrows()`
   - New method: `_get_char_idx()`

**Files Modified:**
- `gui/steps/information.py` — All 3 refinements

**Tests (76 total in test_section_toggles.py):**
- TestDisabledTextboxGreyOut — 11 tests
- TestButtonAlignment — 11 tests
- TestTableSorting — 19 tests

---

### FEATURE: Costs Step — Instant Reprice on Model Change + Estimation Progress Dialog
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** ~2 hours

**Goal:** Avoid full re-estimation when only the model (and therefore its pricing) changes.
Also add a non-blocking progress dialog that shows step-by-step feedback during estimation.

**Changes:**

1. **`EstimationResult.num_requests` field** — Added `num_requests: int = 0` field to
   the `EstimationResult` dataclass so each side (original/preprocessed) stores its
   request count directly alongside the other token fields.  `_do_estimation()` populates
   this when building both `original` and `preprocessed` result objects.

2. **`_reprice_for_model()` method** — New method that reads the stored token breakdown
   from `self._estimation_result` and reapplies the selected model's pricing rates and
   rate limits without running the expensive formation + token-counting pipeline.
   Updates all cost labels, prompt/cached breakdown rows, savings summary, model label,
   time estimate labels, request count labels, and the comparison table.

3. **`_on_model_changed()` updated** — Now calls `_reprice_for_model()` instead of
   `_run_estimation()` when `self._estimation_result` is available.  Full re-estimation
   is only triggered by the user clicking the "↻ Update Counts" button.

4. **`EstimationProgressDialog` class** — New non-blocking `Toplevel` class added before
   `CostsStep`.  Shows 7 step indicators (○/●/✓) and a `ttk.Progressbar`.  Cannot be
   dismissed by the user mid-estimation (`WM_DELETE_WINDOW` is a no-op).  Closes
   automatically when estimation completes.

5. **`_report_progress(step_idx)` helper** — Posts a step update to the dialog on the
   main thread via `self.after()`.  Safe to call from background thread.

6. **Progress wired into `_do_estimation()`** — Seven `_report_progress(N)` calls injected
   at key points: start, orig formation, prep formation, orig token count, prep token count,
   pricing, display update.

7. **`_estimation_complete()` closes dialog** — Calls `self._progress_dialog.close()` and
   clears the reference on both normal completion and exceptions (via `finally`).

**Files Modified:**
- `gui/steps/costs.py` — All changes above

**Tests:** All 92 existing cost tests pass (no regressions).

---

### Gender Inference Simplification
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Simplify the Gender Inference LLM prompt and schema to request only a
gender value (no romanization, no note). Accept any gender output from the LLM
and normalize case-insensitively. Only leave gender empty when "Unknown" or
below confidence threshold.

**Prompt Changes:**
- Removed name/romaji/note fields from prompt template
- New prompt focuses only on inferring gender from dialogue context
- Adds "Don't guess a gender if you are unsure." instruction
- Updated `DEFAULT_GENDER_INFERENCE_PROMPT` in `global_options.py`

**Schema Changes:**
- `RESPONSE_SCHEMA` reduced from 4 fields (`name`, `romaji`, `gender` enum, `note`) to 1 field (`details` string)
- No enum constraint — accepts any gender value from the LLM
- Schema name changed to `gender_inference_response`

**Normalization Changes:**
- `_VALID_GENDERS` frozenset replaced with `_KNOWN_GENDERS` case-insensitive lookup dict
- `_normalize_gender()` rewritten: strips whitespace, lowercases, checks dict
- Known mappings: female→Female, male→Male, non-binary→Non-Binary, nb→Non-Binary, transwoman→Transwoman, transman→Transman
- Unsure/Unknown→Unknown, Neutral→Non-Binary
- Unrecognized values title-cased (e.g. "other"→"Other")

**Return Value Changes:**
- `_call_api_for_excerpt()` / `_call_api_for_excerpt_custom()`: returns `{"gender": ...}` only (was `romaji`+`gender`+`note`)
- `_validate_gender_with_checks()`: returns `(gender, checks)` tuple (was `(romaji, gender, note, checks)`)
- `enrich_speakers_via_api()`: returns `{"gender": str, "checks": int}` per speaker
- `_write_enriched_to_glossary()`: writes only gender (no romaji/note)
- `test_api_connection()`: accepts any non-"Unknown" gender as valid

**Files Modified:**
- `functions/API2Glossary.py` — Prompt, schema, normalization, return values, docstring
- `gui/dialogs/global_options.py` — `DEFAULT_GENDER_INFERENCE_PROMPT`
- `dev/test_utility_settings.py` — Updated tests for new schema/normalization (57→63 tests)

**Tests:** 63 unit tests pass, 7 integration tests pass (real API: Male 100%, Female 100%).

---

### Gender Inference Batch Optimization
**Priority:** HIGH | **Status:** ✅ COMPLETE | **Effort:** Session

Goal: Fix UI freeze, add cancellation, respect limit settings, and optimize script-based
gender inference for large manifests (845+ speakers, 64K+ lines).

**Root Cause:** `_infer_character_genders()` called `infer_gender_comprehensive()` per-speaker
on the GUI thread, scanning ALL lines for each speaker. With 845 speakers × 5 honorifics ×
64,520 lines, this produced ~273M regex operations, freezing the UI for minutes. The script
pass had no cancel button, `WM_DELETE_WINDOW` was disabled, and `gender_script_maximum` /
`gender_script_minimum` settings were computed into a confidence threshold but never used to
limit actual line scanning. Self-pronouns were not analyzed (empty dicts passed).

**Solution — Batch Processing (`infer_genders_batch()`):**
New function in `name_glossary_functions.py` replaces per-speaker rescanning with five-phase
single-pass batch processing:
1. **Index pass** — detect line speakers in one sweep, build `speaker_dialogue` map
2. **Explicit gender** — 4 regex scans on joined full text (not per-speaker)
3. **Honorific from others** — single pass with pre-filter (skip lines without honorific
   substrings), only count when spoken by someone OTHER than the target
4. **Self-pronoun analysis** — per-speaker dialogue lines limited by `max_lines_per_speaker`
   with early exit when `min_evidence` reached (unless `do_all=True`)
5. **Combine signals** — same priority ordering as `infer_gender_comprehensive()`

**Solution — Background Thread + Cancel:**
- Script pass now runs in a background thread (was synchronous on GUI thread)
- Cancel button visible from the start (was only for LLM pass)
- `WM_DELETE_WINDOW` triggers cancel (was `lambda: None` / disabled)
- Progress dialog is non-modal (removed `grab_set()`)
- Queue-based messages: `("progress", cur, speaker)`, `("script_done", results)`, `("error", str)`
- `_poll_script()` polls via `after(100)`, chains into `_on_script_done()` → `_start_llm_pass()`

**Solution — Settings Respected:**
- `gender_script_maximum` → `max_lines_per_speaker` (limits dialogue lines scanned per speaker)
- `gender_script_minimum` → `min_evidence` (minimum evidence points required)
- `gender_script_ignore_unknown` → `ignore_unknown` (no-evidence lines excluded from limit)
- `gender_script_do_all` → `do_all` (force full scan even after consensus)

**Performance:** Real UCS data (845 speakers, 64,520 lines) → 5.12 seconds (was minutes/frozen).
Synthetic 200 speakers + 10K lines → under 2 seconds.

**Files Modified:**
- `functions/glossaries/name_glossary_functions.py` — Added `infer_genders_batch()`, added `Callable` to imports
- `gui/steps/information.py` — Rewrote `_infer_character_genders()` for background thread + batch

**Tests:** `dev/test_gender_batch.py` — 31 tests (9 basic, 2 priority, 5 limits, 2 cancel,
1 progress, 2 multi-speaker, 2 performance, 7 edge cases, 1 GUI integration). All 52 gender
tests pass (31 new + 21 existing).

---

## ✅ Phase 79 — Output Injection Standardization (DONE)

**Objective:** Fix stale data in Output step, correct Same as Source directory resolution, add explicit INJECTION output format with standardized parser handshake.

**Changes:**

1. **INJECTION OutputFormat** — New `OutputFormat.INJECTION` enum member; empty file extension (preserves original); FORMAT_DESCRIPTIONS: "Parser injection (original format preserved)". Explicit format choice in the Output Format dropdown.

2. **Standardized inject_to Handshake** — `parser_base.py` `inject_to(source, output, lines, *, orig_lines=None) → List[int]`: (0) Load source, (1) Extract keys, (2) Sequential first-instance find-replace, (3) Save. Returns failed indices.

3. **Fresh Line Reads** — `_get_fresh_lines_for_file()` reads directly from manifest manager via `resolve_line_field()`. Full Table View edits are immediately reflected without restart.

4. **Same as Source Fix** — `_get_same_as_source_dir()` returns `mgr.get_original_dir().parent` so `translated/` sits next to `Original/`.

5. **Write Injection Handshake** — `_write_injection()` 4-step handshake: load Original → extract keys → sequential match with orig verification → `parser.inject_to()`.

6. **LightVN Signature Update** — `inject_to()` accepts `*, orig_lines=None` (ignored) and returns `List[int]`.

**Files Modified:**
- `formats/parser_base.py` — Rewrote `inject_to()` with standardized handshake
- `formats/LightVN.py` — Updated `inject_to()` signature
- `gui/steps/output_inject.py` — INJECTION enum, _get_fresh_lines_for_file(), _write_injection(), _get_same_as_source_dir() fix, _build_file_list_from_filedir() update

**Tests:** `dev/test_output_injection.py` — 25 tests (8 standard inject_to, 2 LightVN signature, 2 fresh lines, 3 Same as Source, 4 INJECTION format, 2 write injection, 1 build file list, 3 edge cases). All 25 tests pass.

---

## ✅ Phase 80 — Manifest Overwrite Prevention (DONE)

**Objective:** Fix manifest corruption where loading or closing a project silently overwrites stored settings and step results. Three root causes identified via manifest diff analysis; two additional similar patterns discovered via codebase audit.

**Changes:**

1. **RequestOptions Overwrite Guard** (`gui/steps/translate.py`) — Added `_initializing` flag set `True` before `super().__init__()` and `False` after. `_populate_key_dropdown()` no longer calls `_on_key_changed()` during init — instead calls `_filter_models_by_provider()` directly without writing to manifest. `_on_key_changed()` skips all manifest writes when `_initializing` is `True`. `bind_combobox_to_field` for Model and RequestMode returns `None` from `manager_getter` during init, suppressing trace-triggered saves. Prevents overwriting `ApiKeyProvider`, `ApiKeyName`, `Model`, and `RequestMode` with defaults on load.

2. **Style/Tone/SI Text Preservation** (`gui/steps/information.py`) — `_ensure_style_tone_text()` now wraps both `delete` and `insert` inside `if prompt_text:` guard. Previously, text was unconditionally deleted then only conditionally inserted — when the active `si_preset` was missing from the INI file, user text was wiped. This also caused `_ensure_default_texts()` to detect empty fields and overwrite `si_preset` from "New Default" to "Default" with Output Examples.

3. **Step Data Merge-Not-Replace** (`gui/steps/preprocess.py`, `gui/steps/input_extract.py`, `gui/steps/analysis.py`) — `_update_step_data()` and `on_leave()` now start from `self.get_step_data()` (existing manifest data) and merge updated keys, instead of creating fresh dicts that discard stored results. Prevents loss of `dedup_map`, `aggr_dedup_map`, `aggr_numbers`, `ellipsis_counts`, `placeholder_captured`, `anchor_captured` (preprocessing), `manifest_path`, `suggested_project_name` (input), and `analysis_results` (analysis).

**Files Modified:**
- `gui/steps/translate.py` — `_initializing` guard, init-safe `_populate_key_dropdown()`, guarded `_on_key_changed()`, conditional `manager_getter` for Model/RequestMode bindings
- `gui/steps/information.py` — `_ensure_style_tone_text()` conditional delete+insert
- `gui/steps/preprocess.py` — `_update_step_data()` merge pattern
- `gui/steps/input_extract.py` — `_update_step_data()` merge pattern
- `gui/steps/analysis.py` — `on_leave()` merge pattern

**Tests:** `dev/test_manifest_overwrite.py` — 14 tests (TestPreprocessingDataPreservation: 2, TestInputDataPreservation: 1, TestAnalysisDataPreservation: 1, TestRequestOptionsPreservation: 3, TestInfoMetadataPreservation: 2, TestManifestRoundTrip: 3, TestManifestComparisonRegression: 2). All 14 tests pass.

END OF ROADMAP
=============================================================================