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

1. tests/safety/test_engine_safety.py::test_missing_crisis_item_fails_closed, assertion line 30: expected crisis_override_triggered is True when phq9_item9 is absent; actual False. **Verdict (b)**: context-v2.md §9, Module 5 (“Safeguards & NASA Operational Extensions”) requires the override for PHQ-9 Item 9 > 0; it does not define missing-item behavior.
2. tests/safety/test_engine_safety.py::test_crisis_item9_fails_closed_before_routine_output[None], assertion line 21: expected True for null; actual False. **Verdict (b)** for the same §9 Module 5 reason; null/malformed fail-closed handling is not stated there.
3. tests/safety/test_engine_safety.py::test_crisis_item9_fails_closed_before_routine_output[invalid], assertion line 21: expected True for the unparseable string invalid; actual False. **Verdict (b)** for the same §9 Module 5 reason. The "1" and positive numeric cases passed.
4. tests/safety/test_engine_state.py::test_state_has_schema_version, assertion line 32: expected result state schema_version to be non-null; actual None. **Verdict (b)**: context-v2.md §9 “INPUT / OUTPUT SPECIFICATION” shows no schema_version requirement in the engine state/API shape. The backend integration adds the version envelope when it persists and returns state.

No failure was classified (c), so no backend code fix or follow-up test run was needed. The engine was not changed.

## Loop run — 2026-11-13 (full suite, capture enabled)

Command: `PYTHONPATH=waiwai1 /tmp/astro-app-verify312/bin/python -m pytest --timeout=60 -q` from the repo root. No `-p no:capture`, no selection/exclusions. Wall time `real 580.89s`. No test was weakened, skipped or deleted.

Result: **586 collected, 541 passed, 34 failed, 10 errors, 1 skipped**.
Caveat: pytest did not print its own final count line (file ends after the short-summary list), so passed/skipped are derived from `--collect-only -q` (586) minus the 44 FAILED/ERROR entries and the one progress `s`. The skipped test is `tests/e2e/test_curl_flow.py` (E2E=1 guard).

### One repeated setup failure (10 errors)

All 10 errors are the same module-scoped fixture timeout in `tests/pipeline/test_personas.py::seeded` (line 63: `personas.seed(...)`), each `Failed: Timeout (>60.0s)`, not a per-test assertion. This looks like the known slow synthetic-seed setup, not a code regression; no open-handle/lock evidence was collected this run. DB file involved:
`/private/var/folders/g2/mfvndm3s1yscv308bqj7wv8h0000gn/T/pytest-of-seemachauhan/pytest-12/astro-data0/db/astro.db`
Errored: test_p1_steady_no_flag_and_calibrated, test_p2_drift_phys_only, test_p3_mental_only_from_catalog_bands, test_three_synthetic_users_with_14_valid_nights, test_reseed_is_idempotent, test_reset_demo_removes_everything, test_demo_password_env_is_used_and_not_echoed, test_final_phq9_option_shows_safety_path, test_generated_passwords_returned_once_never_logged, test_history_flag_counts.

### Failures by group

**A. Worktree executable-bit regression — 10 failures (`tests/unit/test_ops_scripts.py`).** Source scripts are mode `664` in the worktree but `100755` in the git index, so ruff reports `EXE001` and shell invocation returns `Permission denied`; tests expect rc 0.

| Test | Line | Expected | Actual |
|---|---|---|---|
| test_check_merge_ok_parses_summary_with_warnings | 94 | returncode 0 | 1 (EXE001/ruff fail on merged tree) |
| test_merge_ready_green_moves_board_and_broadcasts | 129 | returncode 0 | 1 (`REFUSE: check_merge failed`) |
| test_merge_ready_red_after_merge_auto_reverts_and_records_lesson | 159 | stdout has `REVERTED` + `test_flaky` | `REFUSE: check_merge failed` |
| test_merge_ready_ignores_untracked_files_in_main | 200 | returncode 0 | 1 (`REFUSE`) |
| test_check_merge_warns_on_reformat_outside_ownership | 207 | returncode 0 | 1 (EXE001/ruff fail) |
| test_check_merge_skips_frontend_when_untouched | 290 | returncode 0 | 1 (EXE001/ruff fail) |
| test_check_merge_runs_frontend_with_cache_outside_repo | 300 | returncode 0 | 1 (EXE001 on tools/ops/board.py, lessons.py) |
| test_merge_ready_frontend_red_reverts_and_records_lesson | 351 | `RED: tests=pass` + `frontend=FAIL(vitest)` | `REFUSE: check_merge failed` (check_merge.sh Permission denied) |
| test_merge_ready_green_with_frontend | 364 | returncode 0 | 1 (`REFUSE`) |
| test_metrics_reports_lessons | 226 | stdout has `reverts=1` | `reverts=0` |

**B. Survey submission contract drift — 18 failures (`tests/unit/test_surveys_{fuzz,api,db}.py`).** Current `/responses` returns `crisis:true`/`ok:false` for payloads these tests treat as routine, and service-level invalid/storage paths no longer raise `SubmissionError`.

| Test | Line | Expected | Actual |
|---|---|---|---|
| test_storage_follows_consent_exactly | 319 | `j["ok"] is True` | `ok False`, `crisis True` |
| test_no_list_route_returns_another_users_rows | 257 (decorator) | no foreign rows | Hypothesis `FlakyFailure`; 60s timeout in `surveys.weekly_indices` (backend/services/surveys.py:514) |
| test_every_response_carries_safety_and_one_event | 178 | `safety["show"] is False` | `True` for `answers={}` |
| test_storage_failure_is_500_with_safety | 186 | status 500 | 200 |
| test_item9_positive_returns_safety | 142 | `ok True` and `safety.show True` | `ok False`, safety true |
| test_invalid_input_still_returns_safety_200[answers0-4] (×5) | 162 | `error == "invalid"` | `error == "safety"` |
| test_missing_version_uses_catalog_current | 276 | `stored is True` | `False` |
| test_missing_version_invalid_answers_still_safety | 287 | `error == "invalid"` | `error == "safety"` |
| test_survey_without_answers_consent_keeps_no_answers[None] | 244 | `stored True` + `safety.show True` | `stored False` |
| test_survey_without_answers_consent_keeps_no_answers[False] | 244 | `stored True` + `safety.show True` | `stored False` |
| test_safety_checked_before_validation_with_bad_option | 219 | raises `SubmissionError` | DID NOT RAISE |
| test_safety_survives_invalid_answers | 128 | raises `SubmissionError` | DID NOT RAISE |
| test_safety_survives_storage_failure | 145 | raises `SubmissionError` | DID NOT RAISE |
| test_logs_contain_no_answer_values | 203 | raises `SubmissionError` | DID NOT RAISE |

**C. Engine read-only expectations — 4 failures.** Same four documented in the prior classification (engine is not edited).

| Test | Line | Expected | Actual |
|---|---|---|---|
| test_missing_crisis_item_fails_closed | 30 | `crisis_override_triggered is True` | `False` |
| test_crisis_item9_fails_closed_before_routine_output[invalid] | 21 | `True` | `False` |
| test_crisis_item9_fails_closed_before_routine_output[None] | 21 | `True` | `False` |
| test_state_has_schema_version | 32 | `state["schema_version"]` non-null | `None` |

**D. Schema expectation drift — 1 failure.**

| Test | Line | Expected | Actual |
|---|---|---|---|
| test_all_interface_tables_exist | 62 | table set == `EXPECTED_TABLES` | extra table `context_engine_nights` |

**E. Live SSE tail timing — 1 failure.**

| Test | Line | Expected | Actual |
|---|---|---|---|
| test_live_default_starts_now_and_tails_new_rows | 154 | events `["window","heart"]` | `[]` (no new rows observed in window) |

## Rerun — 2026-11-13 19:14 IST (capture on, no `-p no:capture`)

- Command: `PYTHONPATH=/tmp/astro-pytest-capture-compat:waiwai1 /tmp/astro-app-verify312/bin/python -m pytest --timeout=60 --timeout-method=signal --basetemp=/tmp/astro-pytest-session-20261113-191445 -q -rfE tests/safety tests/backend tests/db/test_migrations.py tests/pipeline` → **60 passed, 4 failed, 10 errors**, wall 151.9s.
- SQLite: `personas.seed()` writes to `$DATABASE_URL` set by `tests/pipeline/test_personas.py::seeded` (lines 49–54) = `<basetemp>/astro-data0/db/astro.db`, which is already a private temp DB per pytest session (`tmp_path_factory`). `lsof` before the run showed no process with any `astro*.db` open and nothing on :8765. No contention.
- 10 errors = one fixture setup timeout. The stack ends in `csi_core/synth.py:136 synth_night → pandas to_csv → gzip.write`: CPU-bound synthetic-capture writing, not a lock. Local override (timeout only, no test edits): `--timeout=900 tests/pipeline/test_personas.py` → **10 passed**, setup 95.8s, wall 112.4s. With that override the selection is 70 passed, 4 failed.
- Verdicts:
  - 4 direct-engine failures, unchanged: `test_engine_safety.py:21` [None], `:21` [invalid], `:30` (missing Item 9), `test_engine_state.py:32` (schema_version). Verdict **(b)**: the tests demand more than context-v2.md §9 Module 5 (override only for Item 9 > 0) and the §9 I/O spec (no schema_version). The engine is read-only and the BLOCKER stays in DECISIONS.md; the tests were not changed.
  - 10 persona setup errors: not a code defect. The fixture needs about 96s against the 60s per-test budget. Not (c); REQUEST filed with the tests owner.
- No verdict (c) items, so no backend change was made.

## Full suite — 2026-11-13 19:24 IST (integrator, capture on)

Command: `PYTHONPATH=/tmp/astro-pytest-capture-compat:waiwai1 /tmp/astro-app-verify312/bin/python -m pytest --timeout=900 --timeout-method=signal --basetemp=/tmp/astro-pytest-full-<hhmmss> -q -rfE -p no:cacheprovider` → **552 passed, 33 failed, 1 skipped, 0 errors**, wall 649.8s. The 900s timeout is the local override for the persona fixture (REQUEST in pane-integrator.md / bus/issues_for_opencode.md).

| Group | Tests | Assertion | Expected vs actual | Verdict |
|---|---|---|---|---|
| Engine | `tests/safety/test_engine_safety.py:21` ([None], [invalid]), `:30`; `tests/safety/test_engine_state.py:32` | crisis_override / state.schema_version | True / non-null vs False / None | **(b)** stronger than context-v2.md §9 Module 5 + §9 I/O. Engine read-only; BLOCKER stays |
| Survey crisis contract (17) | `tests/unit/test_surveys_api.py` (item9_positive 142, invalid_input ×5 162, missing_version_uses_catalog_current 276, missing_version_invalid_answers 287, storage_failure_is_500 186); `tests/unit/test_surveys_db.py` (without_answers_consent ×2 244, safety_checked_before_validation 219, safety_survives_invalid_answers 128, safety_survives_storage_failure 145, logs_contain_no_answer_values 203); `tests/unit/test_surveys_fuzz.py` (every_response_carries_safety 178, storage_follows_consent 319) | Item 9 positive → `ok:true, stored:true` + safety, or SubmissionError raised; empty PHQ-9 answers → `safety.show` false | Now `ok:false, crisis:true, stored:false`, no raise; empty/missing Item 9 now fails closed | **(b) against the integration contract / DECISION NEEDED.** All 17 come from one change: `backend/services/surveys.py:335` and `:600` return early on safety, and `safety_check` fails closed on missing Item 9 (coord/API_CONTRACT.md). The tests encode the pre-integration feat/surveys contract (store consented answers + show safety). Not weakened. The user must pick one contract |
| Schema | `tests/db/test_models.py:62` test_all_interface_tables_exist | table set == EXPECTED_TABLES | extra `context_engine_nights` (migration 0005) | **(b)** intended new table; the tests owner should add it to EXPECTED_TABLES |
| Ops scripts (10) | `tests/unit/test_ops_scripts.py` (94, 129, 159, 200, 207, 226, 290, 300, 351, 364) | returncode 0 / GREEN / reverts=1 | EXE001 exec-bit + ruff failures, REFUSE on dirty main, reverts=0 | **Not backend.** Dirty multi-pane worktree and `tools/ops` changes owned by ops. Not (c) |
| Live SSE | `tests/db/test_live.py:154` | events [window, heart] | [] | **(b) timing flake.** Passes in isolation 2/2 (13 passed, ~15s). Fails only under full-suite load |

No verdict (c) items, so no backend change was made. Open decision: the survey crisis contract above.

## Engine test verdicts — 2026-11-13

The four direct-engine tests were not edited. Verdict key: **(a)** test expects behavior the spec lacks, **(b)** test is wrong, **(c)** engine bug. `AGENTS.md` requires the override only for PHQ-9 Item 9 > 0; `coord/API_CONTRACT.md` assigns missing/unparseable fail-closed handling to the backend API, and `schema_version` is a backend persistence envelope.

| Test | Assertion line | Expected vs actual | Verdict |
|---|---|---|---|
| `tests/safety/test_engine_safety.py::test_missing_crisis_item_fails_closed` | 30 | `crisis_override_triggered is True` when Item 9 is absent; actual `False` | **(a)** |
| `tests/safety/test_engine_safety.py::test_crisis_item9_fails_closed_before_routine_output[None]` | 21 | `True` for a null Item 9; actual `False` | **(a)** |
| `tests/safety/test_engine_safety.py::test_crisis_item9_fails_closed_before_routine_output[invalid]` | 21 | `True` for an unparseable Item 9; actual `False` | **(a)** |
| `tests/safety/test_engine_state.py::test_state_has_schema_version` | 32 | `state["schema_version"]` non-null; actual `None` | **(a)** |

No verdict (c): the engine matches the spec it owns. The four tests remain unmodified and are expected to fail until the spec/owner decision changes.

## Suite run — 2026-11-13 20:51 IST

`coord/suite.sh` run once (no other suite line was active in `coord/FEED.md`); capture enabled, global `--timeout=60`, wall 538.31s. Result: **591 collected, 586 passed, 4 failed, 0 errors, 1 skipped**. Output: `coord/last_suite.txt`.

Failures are only the four read-only engine tests classified above:
`tests/safety/test_engine_safety.py::test_missing_crisis_item_fails_closed`,
`::test_crisis_item9_fails_closed_before_routine_output[None]`,
`::test_crisis_item9_fails_closed_before_routine_output[invalid]`,
and `tests/safety/test_engine_state.py::test_state_has_schema_version`.

## Engine test verdicts — 2026-11-13 (user rubric: a = spec lacks it, b = test wrong, c = engine bug)

Engine is not edited. Item 9 is treated as safety-critical. The engine reads it as `crisis=_num(clinical,"phq9_item9")>0` (waiwai1/engine/api.py:123). `_num` maps None, non-numeric and absent values to 0.0 (api.py:15-19), so an unreadable or missing Item 9 yields no override.

| Test | Assertion | Spec (context-v2.md) | Expected vs actual | Verdict |
|---|---|---|---|---|
| tests/safety/test_engine_safety.py::test_crisis_item9_fails_closed_before_routine_output[None] | :21 `assert result["safety_status"]["crisis_override_triggered"] is True` | §9 Module 5, l.541: "Zero-Latency Item 9 Override: PHQ-9 Item 9 > 0 halts normal flow…" | True vs False | **(a)** the spec defines only > 0, with nothing about null |
| …[invalid] | :21 (same line) | same l.541 | True vs False | **(a)** the spec has no rule for unparseable values |
| test_missing_crisis_item_fails_closed | :30 `assert result["safety_status"]["crisis_override_triggered"] is True` | same l.541; also l.32 "Any detected suicidal ideation… (e.g., PHQ-9 Item 9 > 0)" | True vs False | **(a)** an absent item is not "detected"; the spec has no fail-closed rule |
| tests/safety/test_engine_state.py::test_state_has_schema_version | :32 `assert result["state"].get("schema_version") is not None` | §9 INPUT / OUTPUT SPECIFICATION (l.549 ff.) shows no `state`/`schema_version` field | non-null vs None | **(a)** the spec lacks it |

**No (c).** The engine matches the written spec. However, the engine **fails open** on null, unparseable or missing Item 9. That is a real safety gap in the spec, not a code defect. Recommend the spec owner add "missing or unreadable Item 9 ⇒ override" to §9 Module 5. Mitigation in place: the backend decides survey safety before the engine (top-level `safety_screen_required`, server-driven `/today` lock).

**Offer (not done):** add `schema_version` in the backend envelope only. The backend already wraps persisted and returned state with `schema_version: "1"` (backend/services/context_engine.py). The engine test calls `run()` directly, so it would still fail; passing it requires an engine or spec change. Spec numbers unchanged.

## Guard test and suite rerun after `45b1e02` — 2026-11-13 (opencode)

- Added `tests/pipeline/test_sleep_scorer_guard.py` (7 tests), commit `0ad4a31`. It asserts: scorer output placed in `sensing_data` is ignored (`run()` returns the identical result), no scorer keys reach the result or returned `state`, `engine/api.py` does not reference `sleep_scorer`/`score_sleep_session`, missing RR/HR/motion give `sleep_score is None` + `score_status == "insufficient_inputs"`, and HR 120/45 is reported unclamped with display reference `[80, 90]` and normal range `[65, 90]`.
- Full suite (`PATH=/tmp/astro-app-verify312/bin:$PATH bash coord/suite.sh`) at waiwai1 HEAD `45b1e02`: **610 collected, 604 passed, 5 failed, 0 errors, 1 skipped**. `addopts -q` plus the script's `-q` suppress pytest's final count line; totals derive from the progress rows (72×8 + 34 = 610) minus the one `s` and the five `FAILED` lines.
- Failures: the same four read-only engine verdict-(a) tests above, plus `tests/contract/test_api_contract.py::test_api_contract_endpoints_and_bad_inputs` — a `TimeoutError` while waiting on the live server during the full run; it passes in isolation (`.`, 1 passed). No new genuine failures and no (c) verdicts.
- Persona oracle after `45b1e02`: `tests/pipeline/test_personas.py` **10/10 passed**. P1 steady still has `|robust_z| < 1.5` on every `PHYS_FEATURES`, zero flags (history included), and calibrated baseline `n == 13`, so the spec-literal admission change did not move the oracle.
- Frontend: the 54 failing vitest tests were handed to codex in `bus/issues_for_codex.md`, committed `c860496` (Codex owns `frontend/`).
