# Whole Astronaut Health Monitor test-and-report plan

## Scope and architecture found

Treat this entire repository and its included local source/data folders as one Astronaut Health Monitor app. User-facing surfaces are the React SPA (`frontend/`), offline FastAPI demo (`backend/static/demo/`), and the `waiwai1/demo/` scenario UI. `backend/` provides API, accounts, consent, surveys, jobs, persistence, readouts, and SSE; `csi_core/` supplies typed capture loading, estimators, nightly aggregation and fusion; `tools/cli.py`, `scripts/`, and `tools/ops/` support ingestion, operations and setup.

The app's Python signal work also lives in `waiwai1/` and `features script/waiwai1 exported/`: serial capture/logger/test flows, CSI analysis/calibration, live viewers, I/Q HR/movement experiments, firmware, reference data, tests and the Context Engine (`waiwai1/engine/api.py`). These are app components, not a separate product. Some team algorithms are byte-copied under `plugins/vendor/waiwai1.exportused/`; `plugins/team_*.py` adapt them into `csi_core` estimator hooks, and `plugins/team_capture.py` maps team CSV into the app's capture-folder contract. `backend/services/ingestion.py` uses `csi_core` on normalized raw captures. A second route injects precomputed windows through `backend/services/injection.py` and `/api/v1/ingest/estimates`; BRIDGE-1 remains the board task for a reliable live/offline bridge. Map and test both routes rather than replacing either by assumption.

The nightly app path is raw session → normalized capture → `csi_core` (configured team plugins where selected) → window/heart rows → nightly features/baselines/fusion → SQLite → readouts/API/React. The Context Engine is another required component in this app: the main backend currently does not call `waiwai1.engine.api.run()`. Add the required backend adapter and state boundary without changing `engine/`, `context-v2.md`, evaluator behavior or fixed constants. Graph communities describe code structure, not product boundaries or proof that no integration exists.

Repository inventory for planning: 1,073 non-dependency files were present, including Python/backend/frontend/firmware/tests, configuration and seeds, capture/reference CSV/JSON/log data, vendored scripts, migrations and generated caches/reports. Raw capture data is read-only; ignore caches/build artifacts when generating cases. Markdown review spans root rules/handoffs, backend/interface plans, ops board/protocol/lessons/personas/prompts, loop plan/bugs/reports, waiwai1 protocols/spec, exported team docs and both graph reports. Use `docs/ops/board.yaml` as the task-status source; rendered handoffs/status and old raw snapshots can be stale. Current board's CORE-8 says scripts are pending, while the team scripts and exported source are present locally; reconcile that row against actual files and provenance.

## User-facing flows and state machines

### Main React app

1. Unauthenticated entry at /login: Sign in/Create account, email and password; successful auth returns to requested route, failure shows error.
2. Authenticated shell has six tabs: / Overview, /breathing, /heart, /sleep, /psyche, /settings. Guarded routes redirect to login.
3. Overview loads /today: latest night, flags/guidance, pending check-ins, baseline maturity and sync state; cover loading/empty/error.
4. Breathing and Heart connect to live/replay SSE, parse events, reconnect using Last-Event-ID, render charts/status, handle end/disconnect. Heart is experimental.
5. Sleep shows nightly table/trends and date filters, including no-data/error.
6. Psyche loads instrument catalog and indices, selects a check-in, renders radio options, submits and shows saved/scored-only/errors. PHQ-9 item 9 safety must precede results; server safety takes precedence even on HTTP 500.
7. Settings edits display name/timezone, changes consent scopes, exports data, deletes account and signs out.
8. Global safety overlay handles local/server triggers, resources and acknowledgement; it must not be dismissed by background clicks or reveal routine scores first.
9. Navigation/reload: direct deep link while signed out → login → requested route; valid/expired/invalid token handling, tab/back/forward and errors.

### Offline /demo

Load persona file → select one of three synthetic personas → login → Today → select/check-in → safety or score result → acknowledgement → logout. Also cover bad/missing persona, bad credentials, refresh/reload and protected calls after logout. Persona switching/re-login must not leak one user's data into another view.

### API and data flow

Signup/login → token-authenticated profile/consents → browse instruments → submit response/check-in → Today/readouts → optionally register capture or inject estimate batch → queue/poll processing job → nights/flags/indices/guidance → live/replay SSE → logout/export/delete. Repeat each user-owned operation with a second user to assert isolation.

### CSI script flows (waiwai1/)

Operator flows: serial preflight → capture packets/events/metadata → inspect/compare → analyze; calibrate with fit and held-out days; live breathing/dashboard read a growing capture while only logger owns serial; optional I/Q heart/movement analysis; synthetic checks. Hardware-dependent parts use fixtures/fakes in CI and are explicitly marked unverified on hardware. Scripts must not alter source captures.

### State transitions to cover

- Auth signed-out → submitting → signed-in/error; access expiry → refresh or signed-out; logout/revoke → protected request rejected.
- Consent unset/granted/revoked per scope → retention and truthful response wording.
- Check-in unanswered → partial → complete → local safety check → request → server safety or ordinary result/error. Safety survives storage failure.
- Session absent → registered/new (201) or idempotent duplicate (200); job queued → running → succeeded/failed.
- Injection new batch → stored (201) or duplicate/no-op (200); invalid batch → no partial writes.
- Night pipeline sessions/windows → night features → baseline/maturity → flags/readout; quality-gated and alert nights obey configured exclusion.
- SSE live/replay connect → events → cursor resume after reconnect → bye/disconnect; user A never receives B events.
- Context Engine payload + prior state → result + next state; carry/reload, schema version, duplicate user/night behavior where a persistence adapter exists.
- UI loading/empty/error/success/safety transitions listed above.
- Capture preflight fail aborts; healthy stream records; quit/duration closes files; repeat never overwrites prior raw data.

## Inputs and allowed values

### Auth, profile, consent

| Flow | Fields | Allowed values / boundaries |
|---|---|---|
| Signup | email, password | email ≤320 chars; password PASSWORD_MIN..PASSWORD_MAX (UI minimum 10, API constant authoritative); unknown fields forbidden |
| Login | email, password | email ≤320 chars; password ≤PASSWORD_MAX; include wrong/blank/oversize and lockout boundaries |
| Refresh/logout | refresh_token | nonempty string ≤256 chars; logout unknown token is idempotent |
| Profile patch | display_name, timezone | nullable optional strings; display name ≤DISPLAY_NAME_MAX, timezone ≤64 chars; unknown fields forbidden |
| Consent update | scopes, policy_version | one or more of checkins, survey_answers, raw_csi, share_summaries → bool; version 1..32 chars |
| Account lifecycle | bearer token | caller identity only; export own data; test deletion only on disposable DB |

### Survey inputs

POST /responses fields: instrument_id (1..32 chars), instrument_version (loose input), administered_at (timezone-aware ISO datetime when supplied), answers map. UI requires every item and only offers seed-defined integer options. Exhaust every finite answer combination, then missing/null/wrong-type/out-of-range/extra/duplicate API cases. Seeds remain source of truth.

| Instrument | Item keys | Allowed value per item | Safety |
|---|---|---|---|
| daily_am | sleep_quality, energy, mood | 0..4 | none |
| daily_pm | mood, stress, energy | 0..4 | none |
| phq2 | phq2_1, phq2_2 | 0..3 | none |
| gad2 | gad2_1, gad2_2 | 0..3 | none |
| who5 | who5_1..who5_5 | 0..5 | none |
| phq9 | phq9_1..phq9_9 | 0..3 | phq9_9 >=1 → safety first/only; missing/null/unparseable/string "1" fail closed per task |

### Main API inputs

| Endpoint | Inputs / allowed values |
|---|---|
| GET /api/v1/health, /version | none |
| POST /auth/signup, /auth/login, /auth/refresh, /auth/logout | fields above |
| GET/PATCH /me | caller token; profile patch fields above |
| GET/PUT /me/consents | scopes above |
| POST /me/export, DELETE /me | caller token |
| GET /instruments, GET /instruments/{instrument_id} | catalog ID; unknown ID → 404 |
| POST /responses | survey inputs above |
| POST /sessions | src_dir 1..512 chars relative to DATA_DIR/inbox/user; reject traversal/absolute paths; duplicate hash no-op |
| GET /sessions | optional from/to timezone-aware datetimes, limit 1..MAX_LIMIT; invalid range rejected |
| GET /sessions/{session_id}, GET /windows | session ID; windows requires nonempty session_id; owner-scoped |
| POST /ingest/estimates | injection batch: session ID, timestamped windows, optional experimental hearts/motion and code-version header; strict contract, atomic; hash replay no-op |
| POST /jobs/process | kind 1..64 chars, params JSON object; supported/unsupported kind |
| GET /jobs/{job_id} | job ID; status queued/running/succeeded/failed |
| GET /nights | optional from/to ISO dates |
| GET /nights/{day} | ISO date |
| GET /flags | optional since date |
| GET /indices | optional week date |
| GET /checkins | route-defined date/slot filters |
| GET /guidance | flag_id 1..36 chars, caller-owned |
| GET /today | auth only |
| GET /live/vitals | optional replay_session 1..64 chars, speed >0..10000, max_s >0..service max, Last-Event-ID cursor |
| GET /demo/* | static assets/persona list and API calls used by demo JS |

Contract enums: Posture supine/side/prone/sitting/other; ReferenceKind hr/spo2/rr; SourceKind csi/wearable/synthetic; RunStatus queued/running/succeeded/failed; Maturity warm_up/widening/mature; CheckinSlot am/pm. Other constraints: timezone-aware timestamps; BPM 0..120; Unit 0..1; distance 0..20m; ordered session/window start/end; nonnegative counts/durations; lowercase 64-hex SHA-256; HR 20..250 and experimental=true; RR reference 0..120; SpO2 50..100.

### Context Engine input/state contract

Keep separate direct tests for waiwai1/engine/api.py and evals/fuzz_eval.py. Inputs: mode; persona user_id, E/A/C/N/O trait totals 4..20, optional matrix axes/quadrant and RR median/MAD; sensing rr_med, rr_var, restless_frac, midsleep_shift, quality, valid_hours; cognitive PVT/DSST/Stroop/n-back/matrix results; behavioral KSS 1..9, stress/workload 0..10, caffeine bool, symptom list, PT/ICE item scores and Mini-IPIP; clinical PHQ-9 0..27, item 9 0..3, GAD-7 0..21, WHO-5 0..100, K6 0..24; environment CO2/temperature; exercise log; timestamp; previous state. PT items 0..4, ICE/Mini-IPIP items 1..5. Fuzz each with missing/null/empty/wrong type/negative/huge/nonfinite/unicode.

Do not conflate this engine's state with csi_core BaselineState. Assert state schema/version, state carry and reload, history cap/exclusions, cold start, duplicate user/night idempotency if an adapter exists, stable/drift/spike/30-night step scenarios, determinism, fail-closed crisis and no crashes. Do not edit engine/, the spec, evals/, or fixed constants.

### waiwai1 CLI/operator fields

- capture.py: port, baud, output-dir, condition (empty/still_breathing/motion label), distance, trial, session ID, day, phone MAC, posture, paced rate, ground-truth device, phone model, room notes, arrangement, beta angle, phone/RX chest distance and height/orientation, Wi-Fi channel, position label/offset, expected chest displacement, carrier frequency, helper/operator, duration and preflight controls.
- analyze.py: capture/events/empty-reference/config paths, MAC, output.
- analyze_test.py: capture, marker file/name, manual rate (report-only), config, output.
- inspect_capture.py: capture, MAC, empty reference, output, signal-scan flag, config.
- calibrate.py: manifest, config, fit day, held-out day, output.
- live_breath.py: growing capture, MAC, config, window, refresh.
- live_monitor.py: growing capture, MAC, config, port.
- heart_rate.py: I/Q capture, window, start time, output; experimental.
- movement.py: I/Q capture, window/hop, carrier frequency, Doppler factor, start time, output, follow flag, MAC.
- logger.py/test1.py: serial port, session name, baud, output; interactive keys/taps and no-overwrite.
- tools/cli.py: DB URL, verbose; ingest user/dirs; process session/nightly/user/date; reset confirmation; persona anchor; injection file/user/code-version/session; export user/output; backup output/raw option; restore archive/force.

Use CLI parser contract tests to enumerate options and limits. Physical radio/geometry/ECG/PPG cannot be simulated by this loop; fixture coverage is not hardware accuracy evidence.

## Endpoint inventory

All main endpoints use base /api/v1, except static demos:

| Method/path | Function |
|---|---|
| GET /health, /version | health/build metadata |
| POST /auth/signup, /auth/login, /auth/refresh, /auth/logout | account/token lifecycle |
| GET/PATCH /me; GET/PUT /me/consents; POST /me/export; DELETE /me | profile, consent, export, delete |
| GET /instruments, GET /instruments/{instrument_id}, POST /responses | catalog and safety-first response |
| POST /sessions; GET /sessions, /sessions/{session_id}, /windows | register/read session |
| POST /ingest/estimates | idempotent estimate batch |
| POST /jobs/process, GET /jobs/{job_id} | queue/poll work |
| GET /nights, /nights/{day}, /flags, /indices, /checkins, /guidance, /today | readouts |
| GET /live/vitals | authenticated live/replay SSE |
| GET /demo/* | demo assets/persona file |
| GET / | intended React mount; current main.py mounts /demo and root availability must be verified |

`waiwai1/demo/serve.py` scenario process (app test/demo surface): GET / and /index.html; GET /api/scenario?name=stable|drift|spike|crisis; unknown route 404. Each request makes a fresh in-memory 10-night replay and passes returned engine state to the next night.

## Test strategy, invariants and loop behavior

- Exhaust finite small spaces: survey answers, consent booleans, safety item values, demo scenarios and categorical states. Pairwise cover larger inputs.
- Seed 7–60 night stateful sequences; record seed and minimized payload/state for every failure.
- Cover every UI/API edge once, then seeded 20–50 step walks. Prefer Playwright for both demos; if unavailable, use TestClient/HTTP and frontend tests and report visual limits.
- Adversarial values for accepted fields: missing, null, empty, wrong type, negative, huge, nonfinite, unicode, duplicate. Never put credentials or red-class answers in logs/reports.
- Assert no unexpected 5xx, SSE resume/end, no uncaught browser errors or blank page; crisis is first/only presentation.
- Add tests under tests/safety/ and a delegation/math guard. Assert required engine delegation and scan backend/demo code for copied Context Engine constants/z/CUSUM logic. Main app's distinct csi_core robust-z logic must not be mislabeled as copied Context Engine code.
- Every iteration uses a fresh isolated DB, starts app, runs invariant suite and next generated batch, writes loop/reports/<timestamp>.md and appends confirmed failures to loop/BUGS.md with minimal reproducer/seed.
- After any allowed non-engine fix, run waiwai1/evals/fuzz_eval.py and require no violation or fitness drop.
- Stop at 3 full clean iterations, 20 iterations, 60 minutes, or 3 bugs after max fix attempts. Print cases/coverage, bugs fixed/open, unsupported checks and stop reason.
- Support python loop/run_loop.py --iterations 20 --budget-min 60 and --smoke (<2 minutes).

## Known limits to record

- If Playwright/browser runtime is unavailable, only HTTP/component behavior is verified, not visual presentation.
- Synthetic CSI does not establish physical respiration, heart-rate or movement accuracy; heart/movement are experimental.
- The app has persistence and idempotent session/batch paths, but `csi_core.BaselineState` and Context Engine state are different contracts. Define an explicit adapter/persistence envelope; do not silently equate them. The direct engine function cannot provide database idempotency by itself.
- Main backend currently does not call `waiwai1.engine.api.run()`. This is a required whole-app integration task; a backend-side delegation guard must pass without changing engine math.
- Context Engine durable schema_version, persistent reload equivalence, and persisted duplicate-night behavior may be unavailable absent an integration. Demo response omits full state.
- Map current test names to every flow during build and report uncovered areas; do not weaken existing safety, privacy, or isolation tests.

## Whole-app completion roadmap (checked against repository files)

This is the completion order for the app represented by the entire repository. `waiwai1/` and the exported team source/captures are components in the app workflow; the root app README, waiwai1 README, this plan and the coordination handoff must use that same scope. Do not infer product boundaries from folder names or graph communities.

1. **Reconcile inventory and source of truth.** Treat `docs/ops/board.yaml` as status input, then compare every row to current files/tests before assigning work: current `backend/main.py` already mounts routers although CA-1 is listed todo; CA-2/CA-5 and other rendered status may also have moved. `waiwai1/` is present but untracked; `features script/waiwai1 exported/` is ignored; decide which source scripts/docs/tests belong in the app repository while keeping raw capture data read-only and reviewing license/provenance. Reconcile CORE-8's “user supplies scripts” blocker against those files. **Current workspace warning:** adapters/tests import `plugins.vendor.waiwai1`, but the working tree shows that folder deleted and `plugins/vendor/waiwai1.exportused/` untracked; required Python dependencies are unavailable, so reproduce with an import regression test before fixing. For overlaps, document which `csi_core` contract, `plugins/team_*` adapter, vendored algorithm, or `waiwai1` CLI owns each operation.
2. **Prove signal paths.** Test the raw path: `waiwai1`/team CSV → `plugins/team_capture.py` → normalized capture folder → `backend.services.ingestion` → `csi_core` loader/estimators (configured plugin) → pipeline/run rows → nightly baseline/fusion → API/readouts/UI. Test the precomputed path: team script estimates → CLI/API injection → idempotent DB rows → nightly processing and `/live/vitals`. Finish BRIDGE-1 retry/spool/restart/replay without reimplementing script math.
3. **Integrate Context Engine safely.** Backend must call `waiwai1.engine.api.run()`. Define an explicit service adapter between request/schema and the engine payload/state, persist its returned state with schema version and duplicate-night protection outside `engine/`, and verify reload equivalence. Keep engine and spec constants unchanged. Preserve the crisis fail-closed invariant at the application boundary; engine-only failures remain visible if prohibited changes prevent repair.
4. **Finish end-user journeys.** Verify routes and OpenAPI against code/board; complete real-pipeline synthetic personas, `/demo`, React build/root/offline FE-5, auth/consent/check-in/safety/settings/export/delete, readouts, SSE replay and recovery. Run API E2E plus a browser walk for every UI state; retain per-user isolation and privacy checks.
5. **Finish product board and operational tasks.** Complete or explicitly defer CORE-7/8, CA-2/3/4/5, BRIDGE-1, PERF-1, F6-SLEEP, F4-SYMPTOM and FE-5 based on verified state. PERF-1 exercises SQLite WAL with concurrent injection/SSE/nightly runs and records measurements. Symptom safety must precede persistence. Bootstrap/migrations, backups/restores, portability, CLI commands, firmware/serial setup, and data provenance need documented runbooks.
6. **Release verification and evidence.** Run full Python pytest/ruff, frontend typecheck/Vitest/build, waiwai1 unit tests and fuzz evaluator, migrations on a clean disposable DB, full browser/API journeys, then three consecutive clean full loop iterations. Rehearse with hardware and independent references separately. Require qualified content/license review; retain `TUNING.md` placeholder labels until validated. Record scientific/hardware limits and deferred scope (cloud/outbox, PMC, medication/nutrition, crew view) rather than silently claiming completion.

### Architecture checks the loop must keep visible

- Main API router mounting exists in `backend/main.py`; assert actual OpenAPI route inventory and reconcile the possibly stale CA-1 board row instead of assuming it is unwired.
- Raw capture and precomputed estimate ingestion are different supported paths. Test both from the team scripts through storage and consumer surfaces.
- `plugins/vendor/waiwai1.exportused/` contains vendored team code; provenance says the source license is pending and movement is not vendored there. `plugins/team_*` are adapters, not a substitute for source/provenance review.
- `waiwai1/demo/serve.py` is an app scenario harness; `backend/static/demo/` and `frontend/` are the other two UI surfaces. Test each intended audience/launch mode.
- The whole repo contains app code, reference/raw capture data, generated reports and caches. Generate cases from source contracts/fixtures; never mutate or expose raw data in reports.
