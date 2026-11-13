# Architecture (boundaries)

Short map of who computes what. Details: docs/backend-plan.md, coord/API_CONTRACT.md,
INTEGRATION_PLAN.md.

```
ESP CSI ──► csi_core / plugins (window estimates: RR, motion, presence, HR experimental)
              │
              ├─► nightly job ─► aggregates (rr_med, quality, valid_hours)
              │                    └─► waiwai1.engine.api.run(payload) ─► output + state
              │                         (28-night baseline, CUSUM, levels, indices)
              │                         persisted per (user_id, date) ─► GET /today, /nights
              │
              └─► live session ─► waiwai1.engine.sleep_scorer.score_sleep_session()
                                   experimental short-session summary, per session id
                                   (PROPOSED, pending INTEGRATION_PLAN D1–D4)

Surveys ─► backend/services/surveys.py ─► safety decision FIRST
           ─► safety_screen_required (top level, server-driven) ─► SafetyProvider (z 1000)

Frontend ─► glass UI (coord/DESIGN.md §13) ─► pet (pet-handoff/, src/pet/)
```

## Rules at each boundary

1. **Nightly engine** (`engine/api.py`): read-only. The backend adapter
   (`backend/services/context_engine.py`) maps stored data to the payload and adds
   `schema_version` to the state envelope. Spec constants never change.
2. **Session scorer** (`engine/sleep_scorer.py`, `engine/motion.py`): separate from the
   nightly engine. Its output never enters the `run()` payload, `state`, baselines, traits
   or clinical levels. It is labelled "experimental", not a validated sleep measure.
3. **Room calibration** (60 s empty room) is device/room noise only. It is never a
   person's baseline.
4. **Safety** is decided on the server before any scoring or storage. The safety screen
   is never glass, never animated, and covers everything, including the pet.
5. **Pet** receives only species, personaId, timeOfDay, safetyActive, reducedMotion,
   streakDays and nightsLogged. It never receives scores, vitals, survey results or
   Watch/Alert status. When `safetyActive` is true it renders nothing.
6. **Ownership**: CLAUDE.md folder table. Every user-owned row has `user_id`, and every
   query filters by it.
