
2026-11-12 integrator: `waiwai1/engine/api.py` is the sole Context Engine source of truth. `plugins/vendor/waiwai1.exportused` is signal-estimator vendor code, not a duplicate engine. Do not relocate or edit the engine as part of backend wiring.

2026-11-12 — Test ownership and engine boundary
- Integrator may create/edit tests/safety/ and tests/backend/ for persistence, state, idempotency, and crisis-path coverage. Loop owns loop/ and all other tests/ paths. If loop needs coverage in integrator-owned tests, loop appends a REQUEST and integrator implements it.
- The Context Engine is read-only: no edits under waiwai1/engine/ and no fixed spec constant changes. Tests may import and call run().
- Existing tests must not be weakened or deleted to obtain a pass.

BLOCKER (2026-11-12): The direct engine tests in `tests/safety/test_engine_safety.py` fail for absent/null/unparseable PHQ-9 Item 9, and `tests/safety/test_engine_state.py::test_state_has_schema_version` fails because `waiwai1/engine/api.py` does not return that field. The engine is read-only by decision; no backend change can make these direct-engine assertions pass without changing engine behavior. Backend safety and persistence coverage is separate and should remain enabled.

BLOCKER (2026-11-13, classification of direct-engine tests): waiwai1/engine/api.py currently returns crisis_override_triggered: false when PHQ-9 Item 9 is absent, null, or unparseable, and its direct state object has no schema_version. These are the four direct-engine failures recorded in coord/AUDIT.md. However, context-v2.md §9 Module 5 explicitly requires crisis override only for Item 9 > 0 and §9 INPUT / OUTPUT SPECIFICATION does not require a state schema version; classify the corresponding stronger direct-engine assertions as test expectations beyond the written engine spec. The backend survey route remains fail-closed, and its Context Engine persistence adapter adds schema_version. Engine changes remain outside integrator authority; only revise these tests/spec with an explicit engine-owner decision, never weaken tests silently.
