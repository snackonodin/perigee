# Whole Astronaut Health Monitor test-and-report plan

## Scope and architecture found

The project root is the whole Astronaut Health Monitor, not just waiwai1/. The main app is FastAPI + SQLite (backend/, csi_core/, migrations/, seeds/) with an offline vanilla-JS page at /demo and a React app under frontend/. Its nightly pipeline is csi_core → backend pipeline/fusion services → database/readouts/API.

waiwai1/ is a separate CSI experiment/prototype with serial capture, offline analysis, live viewers, and a separate Context Engine in waiwai1/engine/api.py. Its README says it does not modify the parent project. The graph report shows separate communities, and graph path queries found no route from the main nightly route/pipeline to that engine. Main backend currently does not call engine.api.run(); it uses csi_core and backend.services.fusion. This is a material requirement gap. Add a guard that makes it visible, without altering scoring math or silently substituting an engine.

Planning inventory covered repository instructions, status/handoffs, backend/API/interface docs, operations board/protocol/lessons/personas/prompts, CSI protocols and Context Engine spec, plus graphify-out/GRAPH_REPORT.md. Graph queries and path queries located the major app areas. Board docs list outstanding work (BRIDGE-1, PERF-1, F6-SLEEP, F4-SYMPTOM, FE-5); handoff notes say some status claims are historical and worktree branches may differ. The loop tests the checked-out tree.

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

Separate waiwai1/demo server: GET / and /index.html; GET /api/scenario?name=stable|drift|spike|crisis; unknown route 404. Each request makes a fresh in-memory 10-night replay and passes returned engine state to the next night.

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
- Main app has persistence and idempotent session/batch paths, but its baseline/fusion state differs from standalone Context Engine state. Direct pure-function engine API cannot itself provide user/night idempotency; that requires a persistence adapter.
- Main backend currently does not call engine.api.run(). A delegation guard cannot pass until integration is added outside engine; report as open rather than changing engine math.
- Context Engine durable schema_version, persistent reload equivalence, and persisted duplicate-night behavior may be unavailable absent an integration. Demo response omits full state.
- Map current test names to every flow during build and report uncovered areas; do not weaken existing safety, privacy, or isolation tests.
