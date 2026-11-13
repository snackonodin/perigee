# Integration plan: new waiwai1 pieces (2026-11-13)

Owner: Claude (coordinator). Contract changes happen only after the decisions in §6.

## 1. What is new in waiwai1 (separate git repo, untracked by the app repo)

| Piece | What it does |
|---|---|
| `engine/sleep_scorer.py` (4.3 KB) | `score_sleep_session(respiration_bpm, heart_rate_samples, motion_samples, jerk_threshold_m_s3)` → an **experimental short-session** 0–100 score (40% RR in 12–23, 40% HR in 65–90, 20% motion-free windows) plus a `dashboard` block (15 s high HR, latest/mean RR, motion flags, accel, jerk). `null` + `insufficient_inputs` until it has RR, HR and motion. |
| `engine/motion.py` (5.7 KB) | `motion_features()` (rolling median + k·1.4826·MAD threshold on \|a\|, jerk = Δa/Δt, jerk flags off until a threshold is given) and `experimental_sleep_score()`. |
| `engine/SLEEP_SCORER_INTEGRATION.md` | Says the scorer is separate from `engine.api.run`: it must not touch the 28-night baseline, CUSUM, traits or clinical levels. Gives the field-to-display map. |
| `engine/ASTRO_APP_SLEEP_MONITOR_HANDOFF.md` | Proposes the product flow: connect the ESP over USB serial (one reader), link check at ≥90 rows/s for 3×2 s, a 60 s empty-room calibration, then three modes (Breathing, Heart, Full sleep at 180 s) on one non-scrolling screen, and a session state machine. Proposed routes: `/api/sleep-monitor/*`. |
| `engine/api.py` commit `45b1e02` | Baseline admission is now spec-literal (`z_raw < 1.5 and S_t < 2.0`, context-v2 §5.2), replacing `z < 1.0`. Fuzz: 0 violations. |
| `engine/live_sleep_dashboard.html`, `live-sleep-summary.json`, `motion-live.log`, `data/20261113_*` | Research viewer, one trial summary, a log and raw captures. These are not app code. Raw data stays read-only. |

## 2. Where they plug in

- **`engine.api.run` payload/output and state round-trip: no change.** The scorer output never enters the payload, `state`, baselines or traits. A guard test proves this.
- **Nightly job: no change.** Fusion still sends only nightly aggregates (`rr_med`, `quality`, `valid_hours`).
- **Backend (after decisions):** add `backend/services/sleep_monitor.py` as a thin adapter, like `context_engine.py`. It imports `waiwai1.engine.sleep_scorer` and does no math of its own. It persists the summary per session id next to the raw capture. Routes go under the existing v1 style: `/api/v1/monitor/{devices,connect,calibration,sessions,sessions/{id},sessions/{id}/stop}`. Live state reuses the existing SSE channel (`/api/v1/live`), not a new socket.
- **openapi.json:** new `MonitorSession`/`SessionSummary` schemas, added only after decisions D1–D4. It was regenerated today with no drift.
- **Frontend:** a new one-viewport **Monitor** screen (Codex, after decisions). The safety lock (`safety_screen_required`, `--z-safety`) still covers it.
- **Pet events:** the scorer emits nothing to the pet. The pet gets only `night_logged` (a nightly job completed) and its time-of-day events. It never sees scores, HR/RR or Watch/Alert. See `pet-handoff/`.

## 3. Doc changes

- **ARCHITECTURE.md** (new, this commit): nightly engine vs session scorer boundary, and the pet boundary.
- **DESIGN.md:** §10 now points to `pet-handoff/` and drops the old engine-driven pet mood (superseded PET_SPEC §5). Monitor screen layout follows once D1–D4 are decided.
- **backend/openapi.json:** unchanged until D1–D4.

## 4. Ordered tasks

| # | Task | Owner |
|---|---|---|
| 1 | INTEGRATION_PLAN, ARCHITECTURE.md, DESIGN.md §10 note, DECISIONS entry, openapi regen check, `pet-handoff/` | claude (done in this commit) |
| 2 | Glass Tasks 5 (Settings) and 6 (Login/register/baseline); commit the dev companion route | codex (queued) |
| 3 | Guard test: `score_sleep_session` output never reaches `run()` payload/state; scorer invariants (null on missing inputs, HR never clamped) | opencode |
| 4 | Full suite after `45b1e02` (persona oracle P1 \|z\|<1.5 may shift); fix the 53 failing frontend tests from the pastel/glass redesign | opencode |
| 5 | `services/sleep_monitor.py` adapter, config placeholders, routes, openapi, tests (user A ≠ user B) | claude, after D1–D4 |
| 6 | Monitor screen (one viewport, glass, experimental label) | codex, after 5 |
| 7 | Drop in the returned `frontend-src-pet/` as `src/pet/`, wire PetContext (safetyActive from SafetyProvider, streak/nights from `/nights`) | codex, after the pet returns |

## 5. Contradictions and risks

1. **FR8 vs heart display.** `NightOut` says "Heart rate is never exposed (FR8)". The scorer puts HR on the main screen and inside the score. Note that `/live/vitals` already streams experimental HR.
2. **Hard-coded ranges.** 12–23, 65–90, the 80–90 reference band, 0.85, 0.02 and 40/40/20 are fixed inside a read-only engine file. CLAUDE.md requires every value in `config.yaml` + TUNING.md. The scorer has no ranges parameter, so config cannot drive it without an engine change.
3. **"sleep_score" wording.** A 0–100 "sleep score" reads as clinical. Show it only as "Experimental session score" with its limitations, and never to the pet.
4. **safety_screen_required is unaffected.** The scorer has no survey input, and the Monitor screen sits under the safety layer. Starting a monitor session must not clear or bypass the lock (test in task 5).
5. **Spec numbers are unchanged** (z 1.5/2.5, CUSUM 0.5/2/4, MAD 0.40, 3 nights). `45b1e02` aligns admission with §5.2 and may move persona expectations, so it needs a re-run (task 4).
6. **Two "baselines".** The 60 s empty-room step is a room calibration, never a person's baseline. UI and API call it "calibration".
7. **Two motion definitions** (csi_core `motion_z: 4.0`, motion.py 3·MAD/0.10, scorer 0.85/0.02). Kept separate and labelled "motion flags", not body movements.
8. **Portability.** The serial port must come from config/env, never a path. `waiwai1/` is its own repo, so a new device needs it checked out next to the app (document in bootstrap).
9. **Old item-9 gap.** The engine still fails open on a missing item 9 (AUDIT.md). The backend lock covers it on the survey path.

## 6. Decisions needed from you

- **D1** Show heart rate on the Monitor screen (amends FR8 for live sessions only), or hide HR and score RR + motion only?
- **D2** Keep the scorer's ranges and weights fixed in the engine (TUNING.md lists them as engine-owned, read-only), or ask the engine owner for a `ranges=` parameter so config.yaml drives them?
- **D3** Is the ESP serial service in the app backend now, or do the waiwai1 live tools stay research-only for the demo?
- **D4** Show the experimental session score number, or show only the components (RR in range %, motion-free %)?
- **D5** (carried over) Add "missing item 9 ⇒ override" to context-v2 §9? Add `schema_version` in the backend envelope?

## 7. Decided by the user (2026-11-14)

- **D1 Heart/breath rates:** hidden by default. A "Measure" panel lets the person voluntarily run
  a heart-rate or breathing-rate measurement; only then is that value shown, labelled experimental.
- **D2 Ranges:** 12–23 breaths/min and 65–90 bpm are the reference ranges. Readings outside lower the
  session score, graded by how far outside (separately for low and high). Checked: nothing like this
  existed (the engine scorer only counted in-range %). Built as `backend/services/session_scoring.py`
  with every value in `config.yaml session_scoring` + TUNING.md. Engine untouched.
- **D3 ESP:** not always on. Choosing Sleep analysis, Measure heart rate or Measure breathing rate
  connects the ESP for that session only, then releases it.
- **D4 Display:** flags by default (in range / below range / above range, still / motion flags);
  a "Show measured rates (experimental)" toggle reveals the numbers.

Next: task 5 becomes (a) session scoring, done; (b) on-demand `services/sleep_monitor.py` (serial
open on start, link check, calibration, run, close) + `/api/v1/monitor/*` + openapi; then task 6
(Codex Monitor screen, DESIGN.md §14).
