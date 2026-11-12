# Integration audit — 2026-11-12

## Running path and source of truth

Graph query located `backend/services/pipeline.py`, `backend/services/fusion.py`, `backend/services/runs.py`, `backend/worker.py`, `backend/services/readouts.py`, `waiwai1/engine/api.py`, and the engine boundary tests. Direct source verification confirms the existing nightly path is CSI capture → `csi_core` windows → persisted `window_estimates` → `fusion.run_nightly()` → `csi_core.night.aggregate()` / `csi_core.fusion.score_night()` → `night_features`, `baselines`, and `flags` → readouts/API. There is no backend import or call to `waiwai1.engine.api.run()`.

`waiwai1/engine/api.py` is the only `engine/api.py` and the only `def run(payload: dict)` found. `plugins/vendor/waiwai1.exportused` contains signal pipeline implementations, not a second Context Engine. `waiwai1/engine/api.py` is the Context Engine source of truth; vendored signal estimators remain a separate configurable estimator implementation.

## Ranked gaps that block integrated demo

1. **Critical — safety before persistence/display:** `/responses` safety is calculated before validation, but a triggered result currently continues into normal scoring/storage. Engine itself currently treats missing/unparseable Item 9 as zero and returned state lacks `schema_version`; engine edits are forbidden. Backend must short-circuit on PHQ-9 Item 9 positive or malformed/missing when a PHQ-9 submission is being processed, return a minimal top-level crisis response, and never persist routine scores/answers or produce routine output first. Existing backend API shape only exposes nested `safety`.
2. **Critical — no Context Engine execution:** nightly fusion uses only `csi_core`; there is no stored-data → Context Engine payload builder or engine call.
3. **Critical — no durable engine result/state:** there is no engine-night table, unique `(user_id, night_date)` result row, full output JSON, schema-versioned returned state, or engine revision provenance. Existing `NightFeaturesRow` is unique per source kind and does not preserve engine state/output.
4. **High — nightly payload inputs incomplete:** current nightly data has respiration, quality, duration and check-in/weekly-index sources; cognitive, behavioral, environmental and clinical source mappings need explicit treatment. Raw PHQ-9 answers may be unavailable under consent rules, so Item 9 safety cannot be inferred from absent stored answers; the submission path must enforce it synchronously.
5. **High — admission/history invariants:** existing csi_core baseline logic uses configurable window days and excludes flagged dates; it does not establish the engine-specific capped 28-valid-night history, valid-only / non-alert admission, or `z < 1.5` condition. Engine state does implement 28-entry caps and `z < 1` admission, which differs from the handoff's requested `z < 1.5`; reconcile against fixed spec before altering anything. Cold-start language exists in `waiwai1/context-v2.md`; backend persistence/admission remains absent.
6. **High — one-command demo launch:** no root `run_app.py` was found. `backend.config.Settings.api_port` defaults to 8000, not 8765. The existing `waiwai1/demo` can directly invoke the engine but is separate from the API-hosted `/demo` static page.
7. **Medium — API contract:** no `coord/API_CONTRACT.md` exists. Engine result and crisis shapes are not represented as an integration contract.
8. **Medium — missing tests:** `tests/test_engine_boundary.py` checks delegation exists but fails at present. `tests/safety/test_backend_crisis.py` exists; test ownership belongs to the loop pane. Engine safety/state tests exist but currently fail for fail-closed Item 9 and `schema_version` unless source changes beyond this role's authority have landed.

## Additional scan / limitations

Direct targeted scan found stub/pass declarations in `backend/services/jobs.py` and `backend/services/surveys.py`; these are exception classes / caught-exception branches and were not yet classified as defects. No exhaustive repo-wide TODO/FIXME/missing endpoint/database audit is complete. `backend/models/physiology.py` has no Context Engine output/state model. `migrations/` contains revisions through `0004` only. Existing run provenance records app code version but not a dedicated engine source hash. No tests have yet been run in this task.

## Decision points

No product decision is needed to wire the existing engine, persist its JSON and state, or make the crisis path short-circuit. If the backend lacks the PHQ-9 Item 9 answer because the survey was not submitted or answer retention is declined, do not infer a crisis; fail closed only for a PHQ-9 response whose Item 9 is missing, null, or unparseable. Preserve the user's consent rules and existing red-class handling.

## Implementation status update — 2026-11-12

- Backend now builds the documented nightly payload, invokes the single `engine.api.run()` entry point, and handles empty-data nights for existing users as `NO_ESTIMATE` engine runs. The unowned-user/no-data operator case preserves its prior no-op behavior.
- `context_engine_nights` plus migration `0005` persist full output JSON, state JSON with backend-added `schema_version`, `engine_revision`, and `run_id`, unique per user/date. State reload is from the immediately preceding persisted engine result; rerunning a night reuses the prior-night state.
- `/responses` now short-circuits after a triggered safety check, returns top-level `crisis: true`, and skips routine scoring/answers. Safety events remain minimal and independently committed.
- `/api/v1/today` returns `context_engine`; the API contract is `coord/API_CONTRACT.md`; `python run_app.py` serves on localhost:8765 and redirects `/` to `/demo` unless the built React app exists. The static demo renders the context result.
- Added integrator-owned regression coverage in `tests/backend/test_context_engine_integration.py`. Fuzz evaluator reports zero violations. Focused tests currently pass for backend crisis, migration parity, engine delegation boundary, state persistence/idempotency and the no-data run alias. Full suite remains pending.
- **Unresolved engine/spec mismatch:** `waiwai1/engine/api.py` is explicitly read-only. Its baseline admission currently uses `z < 1.0` and its `history` list retains 27 prior z values (then appends current), while the handoff asks for `z < 1.5` and a 28-entry history. The engine caps `baseline_rr` and `context_history` at 28 and does not add `NO_ESTIMATE` readings or non-nominal levels to the baseline. No backend math was copied to compensate. This spec mismatch needs an engine-owner decision/change outside the integrator's permitted files.
- Payload data not represented in the current backend schema (cognitive outcomes, environmental logs, personality traits) is sent as empty/default values; check-in and available clinical score fields are mapped. A full source-data mapping requires upstream persistence/API work.

## Final verification update — 2026-11-12

- Focused integration suite previously passed: 12 tests across `tests/backend/test_context_engine_integration.py`, `tests/test_engine_boundary.py`, and `tests/safety/test_backend_crisis.py`; migration parity passed 5 tests; the pipeline regression passed 10 tests and its no-window alias regression passed after correction.
- Final engine evaluator rerun: `PYTHONPATH=waiwai1 /tmp/astro-app-verify312/bin/python waiwai1/evals/fuzz_eval.py` → 0 violations, fitness 98.67.
- Live server launched with `python run_app.py` on `127.0.0.1:8765`; `/api/v1/health`, `/`, `/demo/`, and `/openapi.json` returned 200. OpenAPI contains `ResponseOut.crisis` and `TodayOut.context_engine`.
- A combined final pytest invocation stalled after initial progress and was interrupted, so it did not provide a final aggregate test count. Earlier focused runs above are the verified results.
- Root React app is available when `backend/static/app` has a build; otherwise root redirects to `/demo/`. Frontend-owned generated API types and root `STATUS.md` updates were requested in `coord/pane-frontend.md`; those requests remain with the frontend pane under the ownership rules.
- Additional whole-repo risks remain as documented in HANDOFF/loop plan: missing persisted cognitive/environmental sources, hardware and scientific validation, vendor license review, and the engine baseline threshold mismatch (`z < 1.0` versus requested `z < 1.5`).

## Pytest isolation and engine failure classification — 2026-11-13

### SQLite/process isolation

The timed-out personas fixture uses /private/tmp/astro-pytest-session-20261113-captured/astro-data0/db/astro.db for the captured rerun. In the prior run it used pytest's pytest-11/astro-data0/db/astro.db. lsof found no open handles on either failed-run fixture database after pytest exited. The concurrently running other-pane app is PID 23759 (/opt/anaconda3/bin/python3.12 run_app.py), cwd the repository, and has /Users/seemachauhan/astro-data/db/astro.db open; that is a different file. ps showed no loop/run_loop.py process. No database contention with the personas fixture was found.

tests/pipeline/test_personas.py::seeded (loop-owned, lines 49–64) currently creates an isolated tmp_path_factory directory and sets its SQLite URL there, with module fixture scope. I appended a REQUEST in coord/pane-integrator.md asking loop to make the fixture explicitly session scoped while keeping one private temporary database per run. The local rerun override used a unique --basetemp=/tmp/astro-pytest-session-20261113-captured, so no previous pytest tree or live DB was reused. The current timeout is in synthetic capture generation (personas.seed → raw_demo_dir → csi_core.synth.synth_night → pandas datetime formatting), not an open SQLite lock; one 60-second fixture timeout caused 10 downstream persona setup errors.

### Captured pytest rerun

Reran the full requested selection with pytest capture enabled (no -p no:capture), using a temporary shim only to bypass the Anaconda/macOS readline import crash. Result: **60 passed, 4 failed, 10 errors, 1 warning**; pytest duration 138.61s, command wall time 143.99s. capsys was available and test_csv_and_cli passed. The no-window alias regression passed. The personas setup timeout described above remains.

### Four failures (all verdict b: test expectation exceeds Context Engine v2 spec)

1. tests/safety/test_missing_crisis_item_fails_closed, assertion test_engine_safety.py:30: expected crisis_override_triggered is True when phq9_item9 is absent; actual False. **Verdict (b)**: context-v2.md §9, Module 5 (“Safeguards & NASA Operational Extensions”) requires the override for PHQ-9 Item 9 > 0; it does not define missing-item behavior.
2. tests/safety/test_crisis_item9_fails_closed_before_routine_output[None], assertion test_engine_safety.py:21: expected True for null; actual False. **Verdict (b)** for the same §9 Module 5 reason; null/malformed fail-closed handling is not stated there.
3. tests/safety/test_crisis_item9_fails_closed_before_routine_output[invalid], assertion test_engine_safety.py:21: expected True for the unparseable string invalid; actual False. **Verdict (b)** for the same §9 Module 5 reason. The "1" and positive numeric cases passed.
4. tests/safety/test_state_has_schema_version, assertion test_engine_state.py:32: expected result state schema_version to be non-null; actual None. **Verdict (b)**: context-v2.md §9 “INPUT / OUTPUT SPECIFICATION” shows no schema_version requirement in the engine state/API shape. The backend integration adds the version envelope when it persists and returns state.

No failure was classified (c), so no backend code fix or follow-up test run was needed. The engine was not changed.
