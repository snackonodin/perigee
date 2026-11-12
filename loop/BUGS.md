# Loop bugs

## OPEN: main backend does not delegate Context Engine scoring

- Reproduce: pytest -q tests/test_engine_boundary.py
- Evidence: backend source has no import/call to engine.api.run(); standalone waiwai1/demo does delegate.
- Attempts: 0/3. Integration choice may change existing backend scoring, so keep this visible pending a safe adapter design.

## OPEN: standalone Context Engine fails open for absent or unparseable item 9

- Reproduce: pytest -q tests/safety/test_engine_safety.py
- Minimal inputs: clinical_scales.phq9_item9 omitted, null, or "invalid"; each currently returns routine output.
- Attempts: 0/3; cannot fix within the explicit no-engine-edit constraint. Missing/null/unparseable must stay safety-only.

## OPEN: Context Engine state has no schema version

- Reproduce: pytest -q tests/safety/test_engine_state.py::test_state_has_schema_version
- Evidence: run(payload)['state'] omits schema_version.
- Attempts: 0/3; engine edits are prohibited. A non-engine persistence adapter may add a version envelope if integration is approved.

## FIXED: backend survey safety skipped a missing PHQ-9 item 9

- Reproduce before fix: pytest -q tests/safety/test_backend_crisis.py (empty answers failed).
- Fix: safety_check now fails closed when a safety-trigger answer is missing.
- Regression guard: tests/safety/test_backend_crisis.py; existing tests/unit/test_surveys_safety.py.
- Fix attempts: 1/3. Verification: 15 targeted safety tests passed; Context Engine fuzz seed 7101, n=20: 0 violations, fitness 98.67.

Runtime setup failures belong in iteration reports and are not counted as app bugs.
