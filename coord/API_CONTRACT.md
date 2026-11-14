# Backend and Context Engine API contract

## App origin

Run `python run_app.py` from the repository root. The API, offline React build (when built), and static demo share `http://127.0.0.1:8765`. Without a React build, `/` redirects to `/demo/`.

## Nightly integration

The authenticated job flow remains `POST /api/v1/jobs/process` with `{"kind":"run_nightly","params":{"date":"YYYY-MM-DD"}}`, followed by polling `GET /api/v1/jobs/{job_id}`. A successful nightly run calls `waiwai1.engine.api.run(payload)` exactly once in backend fusion, stores the Context Engine output/state at most once for `(user_id,date)`, and makes the latest non-crisis output available as `GET /api/v1/today.context_engine`.

The stored JSON contains the engine's structured output. Its `state` always contains `schema_version: "1"`; state and full output are stored in the user-owned `context_engine_nights` table with `engine_revision` and nullable `run_id`. The request payload is not persisted. Client-visible results must be treated as personal health data and remain user-scoped.

## Survey safety response (2026-11-13 contract)

`POST /api/v1/responses` decides safety **before** any DB write or scoring and returns it at the top level:

- `safety_screen_required: boolean` is true when PHQ-9 Item 9 is positive, unparseable, or missing. The client must show the safety screen immediately, before any score. `crisis` is a deprecated alias with the same value.
- `missing_safety_item: string | null` names an unanswered safety item (e.g. `"phq9_9"`) so the client can ask for it after the safety screen.
- `safety` keeps its meaning: `show` is true for a positive or unparseable answer (and records one minimal safety event), and false for a missing item.
- Storage follows consent as before. The stored `survey_responses` row has `safety_flag=true` when the screen was required. If only the safety item is missing and the rest is valid, the row is stored with `total=null` and `scores.incomplete=true` (no total or band is invented).
- If scoring or storage raises, the response is HTTP 500 with `safety_screen_required` still set and `error` = `storage` or `internal`. A DB failure never suppresses the safety screen.
- Logs record only that a flag fired, never answers or item values.

## Invariants

- The engine remains the sole owner of Context Engine scoring/math; backend code only maps persisted fields to its JSON payload.
- Engine results and state are persisted atomically with the nightly run; duplicate user/date runs update the same row and use the preceding night’s state.
- `NO_ESTIMATE` engine outputs may be stored for audit, but the engine receives quality/duration and controls its own state update.
- Clinical item values are not logged; raw engine payloads are not persisted.

## Monitor sessions (on-demand ESP), added 2026-11-14

Authenticated (Bearer). Decided by the user in INTEGRATION_PLAN.md §7. The ESP opens only for a
chosen session and closes after it. One session at a time per device.

| Method | Path | Body / query | Success | Errors |
|---|---|---|---|---|
| POST | `/api/v1/monitor/sessions` | `{"mode": "sleep_analysis" \| "heart_rate" \| "breathing_rate"}` | 202 `MonitorSessionOut` (state `connecting`) | 409 `busy`, 503 `no_receiver` |
| GET | `/api/v1/monitor/sessions` | `show_rates` (bool, default false) | 200 `MonitorSessionOut[]`, newest first, caller's only | |
| GET | `/api/v1/monitor/sessions/{session_id}` | `show_rates` | 200 `MonitorSessionOut` | 404 (also for another user's id) |
| POST | `/api/v1/monitor/sessions/{session_id}/stop` | — | 202 `MonitorSessionOut` | 404 if not the caller's active session |

States: `connecting → link_check → calibrating (60 s empty room, every session) → running →
finalizing → complete`; or `link_error` (with a plain `error` message; partial capture kept) or
`stopped` (stopped before running). Poll every 1 s while active; `remaining_s` counts down the
calibration and run phases.

`summary` (when complete): `sleep_score` (experimental; `null` with `score_status`
`insufficient_inputs`, or `not_applicable` for the two Measure modes), `components`,
`respiration` / `heart_rate` blocks with `flag` (`in_range` | `below_range` | `above_range` |
`no_data`), `counts`, `in_range_pct`, `values_shown`, `readings` (`time_s`, `position`, plus
`value` and `deviation` only when values are shown), `motion` (`flag` `still` | `motion_flags`
| `no_data`, `flag_timestamps_s`), `limitations`, `calibration`, `run_seconds`, `stopped_early`.
Values are shown only with `show_rates=true`, or for the measure chosen in a Measure mode.

## Station time (replaces time zones), added 2026-11-14

`GET /api/v1/me` returns `station_time_offset_min` (int minutes from UTC, or null = UTC).
`PATCH /api/v1/me` accepts `{"station_time_offset_min": <int -720..840> | null}`; null clears it.
`timezone` remains in the schema for old clients but is not used. Frontend: compute the offset
from the station clock time the person types (HH:MM) minus current UTC, rounded to the nearest
15 minutes and wrapped into -720..840; leave the field blank to send nothing (UTC).

`GET /api/v1/monitor/modes` (authenticated) → `[{mode, calibration_s, duration_s, total_s}]` from
config.yaml `monitor` (placeholders). Use it for tile durations; never copy the numbers into the UI.

## Public demo sign-in, added 2026-11-14

`POST /api/v1/auth/demo` (no body, no auth) → 200 `TokenOut` for a **fresh private copy** of the
seeded synthetic persona `settings.demo_email` (default `drift@ex.com`), only when
the server runs with `DEMO_ACCESS=1`; otherwise 404. Updated 2026-11-14 evening: every call creates a
new visitor account (`demo-<hex>@example.invalid`, synthetic) holding a copy of the persona's 14
nights, check-ins and surveys, so visitors never see each other's answers. Copy takes ~2 s.
At most `DEMO_MAX_USERS` visitors (default 50): then 503 `{"error":"demo_full"}`. A visitor may
`DELETE /api/v1/me` (frees a slot); the seeded template personas stay 403 `demo_protected`.
The copy starts with **no personality traits**: the visitor takes the Mini-IPIP quiz.
Frontend: a "Try the demo" button on Login calls this route once, stores the tokens like a
normal login (re-use them on return visits; do not call /auth/demo again while a refresh token
works), and marks setup done. On 503 show "The demo is full right now."
`POST /api/v1/auth/signup`: 403 `{"error":"signup_closed"}` once `SIGNUP_MAX_USERS` real accounts
exist (0 = no cap, the default).

## Persona from the quiz, added 2026-11-14

Instrument `mini_ipip` (20 items, values 1-5, keys `mini_ipip_1..20`, wording from context-v2 §2.2)
is in `GET /api/v1/instruments`; submit it with `POST /api/v1/responses` like any survey. The
response's `scores.traits` holds the five trait totals `{E,A,C,N,O}` (4-20 each), scored by the
Context Engine. No bands, no alert, not part of weekly indices.
`GET /api/v1/persona` (auth) → `{available, source, updated_at, traits, persona_matrix}` where
`persona_matrix = {stability_score, agency_score, quadrant_name}` straight from the engine; ready
as soon as the quiz is submitted, **no nights needed**. `available:false` (traits `{}`,
persona_matrix null) until the quiz is taken. Retaking replaces the traits. The nightly engine run
also receives the traits from then on (wording and layout only; traits never change scores).
