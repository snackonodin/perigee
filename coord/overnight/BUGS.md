# Bugs found in overnight testing (2026-11-14, 04:10–10:00 IST)

Filled by the coordinator from coord/overnight/REPORT.md, the loop logs and the per-persona
screenshots. Fixing starts after 10:00. Owner: claude (backend/infra), claude-fe (frontend).

| # | Found | Area | Symptom | Evidence | Owner | Status |
|---|---|---|---|---|---|---|
| N1 | 04:11 cycle | tests / isolation | `test_isolation` GET /monitor/sessions FAILED and PUT /me/consents ERROR with 401 "invalid or expired token" | Slow (niced, loaded) run: the `world` fixture takes >15 min, longer than `access_token_minutes=15`, so tokens expire before use. Not a leak. Fix: give the isolation app a long access-token lifetime in the fixture (or mint tokens per case) | claude | FIXED 12:45 (isolation app tokens live 4 h; verifying) |
| N2 | 04:11 cycle | tooling | `test_portability` flagged `coord/overnight/night.sh` default `$HOME/.venvs/...` | Machine path in a committed script | claude | FIXED 05:55 (VENV passed in env) |
| N3 | 04:11 cycle | tooling | `night.sh` rebuilt the frontend and restarted the demo every cycle (`last_sha` never set) and re-ran the 1–2 h backend suite each cycle | Loop logic | claude | FIXED 05:50 (suite only when HEAD changes) |
| N4 | 04:11 cycle | engine (D5) | 4 known engine tests (item 9 fail-closed ×3, state schema_version) | AUDIT.md verdict (a) | user decision D5 | waiting |
| V1 | 04:11 shots (drift, dip) | frontend copy | The "quiet note" shows raw engine codes: "[BODY SIGNAL FIRST] Recovery Advisory" / "[MIND SIGNAL FIRST]…", and "Your current pattern is classified as body signal first" (jargon) on Today and Sleep | shots/20261114-0411/{drift,dip}/1440_.png, 1440_sleep.png | claude-fe (map codes to plain titles; keep engine text intact otherwise) | open |
| V2 | 04:11 shots (all) | frontend | **Briefing** and **Consent** tabs are still placeholders: "View coming in a later frontend task." | */1440_briefing.png | claude-fe | open |
| V3 | 04:11 shots (drift) | data label | Today says "NIGHTS LOGGED 10 / 28" while Sleep says "14 / 28 NIGHTS" for the same person (Today counts nights admitted to the baseline, Sleep counts valid nights) | drift/1440_.png vs 1440_sleep.png | claude-fe (label Today "In your baseline 10 / 28" or use valid nights) | open |
| V4 | 04:11 shots (drift) | proportions | Sleep "Breathing-rate trend" chart axis labels are ~24–26 px (y "16.0", dates) — larger than the card title; Body detail shows "16.0 br/min" with the unit as big as the number | drift/1440_sleep.png, 1440_body.png | claude-fe (axis labels 12 px mono; unit at 40 %) | open |
| V5 | 04:11 shots (dip, 390) | mobile header | "Astronaut Vitals" + "Simulated data" each wrap onto 2 lines at 390 px | dip/390_.png | claude-fe (hide "Simulated data" text into a small chip, or drop it below 480 px) | open |
| V6 | 04:11 shots (all) | header | With no display name the header shows the full e-mail (e.g. persona-steady@example.invalid), crowding the nav | */1440_*.png | claude-fe (show the local part, or "Crew member") | open |
| V7 | 04:11 shots (dip) | Today breathing tile | "Your usual range 15.0–15.5" bar shows no marker for tonight's value | dip/390_.png | claude-fe | open |
| V8 | 04:11 shots (drift, dip) | Today hero | "58 resilience index" / "92 resilience index" floats under the button with no label or explanation | drift/1440_.png | claude-fe (label as a mono stat with a one-line meaning, or move into the telemetry strip) | open |
| V9 | 04:11 shots (drift) | Body | Detail card says "Personal baseline · 28 nights" and "Building · 10 / 28 nights" in the same card (contradiction) | drift/1440_body.png | claude-fe | open |
| N5 | 05:50 cycle | tooling | Loop reported frontend 'Tests 104 passed (104)' (117 expected): a test file failed to load under load and the loop only grepped the Tests line | night.sh | claude | FIXED 06:25 (Test Files line + full log saved; takes effect on next loop start) |
