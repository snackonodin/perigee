
2026-11-12 integrator: `waiwai1/engine/api.py` is the sole Context Engine source of truth. `plugins/vendor/waiwai1.exportused` is signal-estimator vendor code, not a duplicate engine. Do not relocate or edit the engine as part of backend wiring.

2026-11-12 — Test ownership and engine boundary
- Integrator may create/edit tests/safety/ and tests/backend/ for persistence, state, idempotency, and crisis-path coverage. Loop owns loop/ and all other tests/ paths. If loop needs coverage in integrator-owned tests, loop appends a REQUEST and integrator implements it.
- The Context Engine is read-only: no edits under waiwai1/engine/ and no fixed spec constant changes. Tests may import and call run().
- Existing tests must not be weakened or deleted to obtain a pass.

BLOCKER (2026-11-12): The direct engine tests in `tests/safety/test_engine_safety.py` fail for absent/null/unparseable PHQ-9 Item 9, and `tests/safety/test_engine_state.py::test_state_has_schema_version` fails because `waiwai1/engine/api.py` does not return that field. The engine is read-only by decision; no backend change can make these direct-engine assertions pass without changing engine behavior. Backend safety and persistence coverage is separate and should remain enabled.

BLOCKER (2026-11-13, classification of direct-engine tests): waiwai1/engine/api.py currently returns crisis_override_triggered: false when PHQ-9 Item 9 is absent, null, or unparseable, and its direct state object has no schema_version. These are the four direct-engine failures recorded in coord/AUDIT.md. However, context-v2.md §9 Module 5 explicitly requires crisis override only for Item 9 > 0 and §9 INPUT / OUTPUT SPECIFICATION does not require a state schema version; classify the corresponding stronger direct-engine assertions as test expectations beyond the written engine spec. The backend survey route remains fail-closed, and its Context Engine persistence adapter adds schema_version. Engine changes remain outside integrator authority; only revise these tests/spec with an explicit engine-owner decision, never weaken tests silently.

REQUEST (2026-11-13, companion pet → frontend + coordinator), see coord/PET_SPEC.md §5:
1. Support resources shown directly by the app, not the pet: when `today.context_engine.scores_and_metrics.mental_level >= 2` or `clinical_floor_breached` is true (non-crisis distress), a support-resources card must be visible on Today. Frontend: confirm whether one exists; if not, add one with the same resource text the safety object uses. The pet stays silent in this state.
2. TUNING.md placeholders for the companion's UI mood cut-offs (frontend/src/companion/moodConfig.ts): FATIGUE_TIRED=65 and MOOD_HAPPY_BELOW=50 reuse the engine's own level-1 cut-off and neutral midpoint; idle 5s, sleep 120s and bubble limits are UI-only. Coordinator: list them as placeholders.
3. SafetyProvider (read-only for the companion) should expose a read-only "safety screen open" signal so the pet can hide; until then the pet hides on any aria-modal dialog.

DECISION NEEDED (2026-11-13, integrator): survey crisis contract. 17 tests in tests/unit/test_surveys_{api,db,fuzz}.py expect PHQ-9 Item 9 positive to still store/score consented answers with safety shown (and empty answers to be "invalid", not crisis). Current backend (surveys.py:335/:600 + fail-closed safety_check) follows coord/API_CONTRACT.md: crisis short-circuits, nothing routine stored. Pick one; then either the tests owner updates those tests or the integrator reverts the early return. Not changed meanwhile. Details: coord/AUDIT.md "Full suite — 2026-11-13".

DECIDED (2026-11-13, user): survey safety = store with safety_flag (not short-circuit). Safety decided first; top-level safety_screen_required (positive/unparseable/missing item 9) + missing_safety_item; storage failure still returns the screen. Implemented in be2fba8. Engine baseline admission set spec-literal (z_raw < 1.5 and S_t < 2.0, context-v2.md 5.2) in waiwai1 45b1e02; fuzz 0 violations.

REQUEST (2026-11-13, art director → integrator/backend): so the safety lock can survive reloads and clear only on the server's word (DESIGN.md §11), expose the unresolved safety state on GET: add `safety_screen_required` and `missing_safety_item` to `GET /api/v1/today` (from the latest `survey_responses.safety_flag` not yet resolved by a complete, non-positive re-submission). Until then the frontend keeps the lock in sessionStorage.

DONE (2026-11-13): GET /api/v1/today returns top-level `safety_screen_required` + `missing_safety_item` from the server (surveys.safety_state: a flagged survey row or an unacknowledged survey safety event newer than the user's latest clean safety-instrument submission). Test: tests/safety/test_today_safety_state.py (includes user A/B isolation).

DECIDED (2026-11-13, coordinator): new waiwai1 session scorer (`engine/sleep_scorer.py`, `engine/motion.py`) stays separate from `engine.api.run`; its output never enters the nightly payload/state. Backend/API/UI wiring waits on INTEGRATION_PLAN.md D1–D4 (HR display vs FR8, engine-fixed ranges, ESP serial service scope, score display). Pet spec moves to `pet-handoff/`; pet mood is never driven by engine status (supersedes PET_SPEC §5 and the 2026-11-13 companion REQUEST item 2).

DECIDED (2026-11-14, user, INTEGRATION_PLAN D1–D4): rates hidden by default with a voluntary "Measure" panel (heart / breathing), labelled experimental; reference ranges RR 12–23, HR 65–90 grade the session score by distance outside, low and high separately (config.yaml session_scoring, placeholders); the ESP connects only when a Monitor session is chosen; flags by default with a "Show measured rates (experimental)" toggle. Implemented scoring in backend/services/session_scoring.py (engine read-only; motion flags reuse engine motion_features). D5 still open.

DECIDED (2026-11-14, user): no Earth time zones. The app uses STATION TIME: an optional field where the person enters their station's clock time once; stored as `profiles.settings.station_time_offset_min` (minutes from UTC, -720..840). Blank = UTC (the atomic-time scale the ISS keeps). Night boundaries use it (`backend/services/station_time.py`); the legacy `profiles.timezone` column is no longer read. API: `station_time_offset_min` on GET/PATCH /api/v1/me.
DECIDED (2026-11-14, coordinator): react-bits components are MIT + Commons Clause; in-app use is allowed, never sell/redistribute them standalone. Licence kept at frontend/src/vendor/react-bits/LICENSE.md.

## D-name (2026-11-14)
Product name is **Perigee** (user decision). Replaces "Astronaut Vitals" everywhere (frontend/src/brand.ts, index.html title, docs).
