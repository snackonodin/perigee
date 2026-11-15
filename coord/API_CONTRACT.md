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
At most `DEMO_MAX_USERS` visitors (default 0 = no cap): then 503 `{"error":"demo_full"}`. A visitor may
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

## Psyche question bank, added 2026-11-15 (replaces Mini-IPIP on Persona)

Instrument `psyche60`: 60 items `psyche_1..60`, values 1-5 ("Not true of me" .. "Deeply true of
me"), each item has `module` (m1..m10). Submit with `POST /api/v1/responses`; the response carries
no module scores. `GET /api/v1/persona` then returns `source:"psyche60"`, `persona_matrix`
`{stability_score, agency_score, quadrant_name}`, `style` (6 booleans: show_raw_telemetry,
calm_non_alarming_tone, structured_checklist_mode, private_scheduled_recovery,
baseline_only_framing, privacy_lock_reminder) and `advice: [{tag, text}]`. Advice is matched to
the latest night and check-ins from the last 3 days, so a new check-in can change it at once;
empty while a safety screen is pending. `traits` is `{}` for psyche60. Spec: docs/psyche60.md.
Show no numbers from it. `mini_ipip` stays in the catalog but the UI should use psyche60.

## Pet speech bubble, added 2026-11-15

`GET /api/v1/pet/bubble` (auth) → `{id, voice, badge, playful, pet_animation, bubble, micro_try,
ui_action, disclaimer}`. One bubble, chosen server-side from seeds/pet_dialogue_bank.json in this
order: safety (pending safety screen → `safety_phq9_item9`, voice `unmodulated`, `playful:false`,
`ui_action:"HALT_AND_OPEN_CRISIS_SCREEN"`), support/context cards, domain nudges, then the
four-state bubble in the persona voice (warm/bright/quiet/calm from the quadrant). `bubble` is
null before the first night (`id:"no_night_yet"`). `playful:false` → no playful pet animation.
`badge` is green / amber / support / crisis / neutral; never render red for it. Never contains scores.
Not wired (no data yet): cabin CO2 nudge, weekly reflection, exploratory pattern, severe somatic flag.

## Demo choices, added 2026-11-15

`POST /api/v1/auth/demo` now takes an optional JSON body (no body = as before, copy of drift):
- `{"crew": "iss-flight" | "iss-aligned" | "iss-misaligned"}` → private copy of that NASA-calibrated
  ISS crew member (~1.5 s). Sleep length from Barger 2014 / Flynn-Evans 2016; people synthetic.
- `{"profile": {"sleep_hours": 4-10, "regularity": 0-4, "stress": 0-4, "mood": 0-4,
  "recent_change": bool}}` → the visitor's own synthetic 14 nights + check-ins + weekly surveys
  (~5 s; show a loading state). `regularity` 0 = very irregular .. 4 = very regular; `stress`
  0 = none .. 4 = very high; `mood` 0 = very low .. 4 = very good; `recent_change` = new
  schedule, travel or illness (adds a breathing drift). No PHQ-9 is ever simulated.
- Both together → 422. Unknown crew → 422. Same 50-visitor cap (503 demo_full), same TokenOut.

## Spaceflight hazards, added 2026-11-15 (docs/hazards.md)

New daily instrument `body_cabin` (submit like any survey): red flags FIRST (`red_chest`,
`red_faint`, `red_breath`, 0/1 → any 1 opens the safety screen with the medical reason),
11 symptoms 0/1 (`sym_*`, each has `group`: cabin/gravity/general/immune), `exercise_min`
(0/15/30/45/60/90), `exercise_effort` (0-10), `friction_crew` and `friction_external` (0-4).
`GET /api/v1/today` adds `cabin: {date, ppco2_mmhg, temp_c, rh_pct, level}` (level usual |
elevated | high | no_reading; null when no reading) and `context_tags: [{kind, text}]` (max 2,
only for a Watch/Alert night; render under the breathing strip, never instead of the flag).
`GET /api/v1/pet/bubble` may return `safety_severe_somatic` (ui_action OPEN_MEDICAL_HELP_NOW).

## Psyche in five parts, added 2026-11-15

The 60 questions also come as 5 themed instruments of 12 items, `psyche_p1`..`psyche_p5`
(1 Mind at rest, 2 Feelings and reactions, 3 People and authority, 4 Focus and motivation,
5 Body and feedback; each has `part: {index, of, blurb}`). Same item keys and answers as psyche60.
Submit each like any survey, in any order, on any day. When all 5 are answered (with
survey-answer consent, so answers are kept encrypted) the server scores them as the full bank
and `GET /api/v1/persona` becomes available. `/persona.progress = {done: [ids], total: 5,
answers_kept}`; answers_kept=false means the parts can't be combined (ask for consent).
UI: one part at a time, items SHUFFLED within the part (stable per user), ~1.5 min each.

## Persona radar profile, added 2026-11-15

`GET /api/v1/persona` (psyche60 source) adds `profile: [{key, label, level}]`, five axes in this
order: mind_at_rest "Mind at rest", feelings "Feelings and reactions", people "People and
authority", focus "Focus and motivation", body_feedback "Body and feedback". `level` is 0-1
(mean of the part's two modules, rescaled). A tendency shape, not a score: render as a radar
with a gradient fill and NO numbers; add "No shape is better than another." Empty for mini_ipip
or before all five parts are done.

## Persona type radar, added 2026-11-15 (replaces the separate 5-part radar on screen)

`GET /api/v1/persona` adds `type_mix: [{type, share}]` in this order: Autonomous Pioneer, Steady
Anchor, Internal Deliberator, Dynamic Explorer. `share` is 0-1 and the four sum to 1 (bilinear share
of the Stability x Agency plane). Render ONE 4-axis radar in place of the quadrant plane, axes =
the four types, the person's own quadrant_name highlighted, no numbers. `profile` (5 parts) stays in
the API but is no longer drawn.

## Persona radar values, updated 2026-11-15

`type_mix` items are now `{type, level, share}`. Draw the radar from `level` (0-1, per axis,
independent, contrast-widened): radius = 12% + 88% x level of the outer ring. Do NOT rescale to
the largest value. `share` (sums to 1) is only for the accessible ordering text.
