# Backend plan (repo copy)

Condensed from "Backend Plan, Stage 1: Requirements and Setup" (28-page PDF, the
team's source document). Section numbers match the PDF. Where the repo deviates
from the PDF, it says so under **Repo decisions**.

Tags: **[MVP]** = needed for the event demo; **[LATER]** = design for it now, build after.

## Repo decisions (beyond the PDF)
- **Demo scope (2–3 days):** synthetic CSI → breathing pipeline → night features →
  baselines → flags + guidance → `/today`; accounts + isolation; PHQ-2, GAD-2,
  WHO-5 and daily check-ins with the safety path; three synthetic personas;
  one demo HTML page. **Cut for the demo:** sync outbox/cloud, PMC report,
  symptoms, environment, real dataset adapters, live streaming, heart-rate display.
- **Paths:** code in Google Drive; venv `~/.venvs/astro-app`; `DATA_DIR=~/astro-data`
  (raw + SQLite) outside Drive, because Drive sync corrupts SQLite WAL files.
- **Auth:** Argon2 + short-lived JWT access tokens + a `refresh_tokens` table
  (hashed, revocable). Logout and account delete revoke tokens.
- **Safety item is data:** the instrument catalog marks the item with
  `safety_trigger`; severe symptom codes live in `config.yaml`.
- **Outbox (when built):** red-class fields stay encrypted inside the payload;
  account deletion enqueues `op='delete'` so the cloud copy is purged too.
- **Contracts:** `backend/schemas/contracts.py`, imported by csi_core and the API.

## 1. What the backend must do
1. Ingest data from the Python capture/processing scripts.
2. Store each person's data safely: sessions, breathing and sleep features, check-ins, surveys, flags.
3. Hold reference (public) datasets separately.
4. Run processing: raw CSI → features; survey answers → indices; fusion.
5. Serve results through an API.
6. Manage accounts and consent (personal baseline and persona per user).
7. Log reproducibly: code version, parameters, input file for each result.

## 2. Key decisions
- D1 Python + FastAPI. D2 SQLite (WAL) via SQLAlchemy + Alembic; Postgres later.
- D3 Raw CSI as compressed files on disk, hourly rotation; DB holds path, SHA-256,
  row count and quality stats. Raw kept 14 days; derived features kept indefinitely.
  (8 h at 100 rows/s ≈ 2.9 M rows ≈ 1 GB plain CSV.)
- D4 Scripts become the pure-function library `csi_core`; API starts jobs, a worker runs them.
- D5 One offline laptop. D6 Local accounts, Argon2, one role. D7 Encrypt sensitive
  fields, record consent, export + delete. D8 Separate research store + replay personas.
- D9 Store UTC, unwrapped device timestamp, and host time. The 32-bit µs counter
  wraps every ~71.6 min; unwrapping is mandatory. D10 UUIDs everywhere.

## 3. Functional requirements
Ingestion: FR1 register session with metadata; FR2 ingest raw log, markers,
reference-device readings; FR3 idempotent by file hash; FR4 capture stats, refuse
`usable` below rows/s threshold; FR5 live streaming [LATER].
Processing: FR6 window estimates (two estimators, PNR, motion, quality, presence);
FR7 nightly features (rr_med, rr_var, presence_hours, restless_frac, onset, wake,
midsleep, quality); FR8 heart rate stored as experimental only; FR9 weekly indices
and fusion state; FR10 every output row records its run.
Accounts: FR11 signup/login/logout/delete-all; FR12 onboarding (Mini-IPIP,
chronotype, habits, preferences); FR13 baselines (median, MAD, n, maturity) updated
only from valid non-alert nights; FR14 learned links [LATER]; FR15 strict isolation.
Surveys: FR16 data-driven instrument catalog; FR17 daily check-ins and weekly
modules; FR18 self-harm item via a dedicated immediate safety path, minimal storage,
never queued. API: FR19 authenticated endpoints; FR20 job endpoints.
Datasets: FR21 registry (license, source, access date, checksum, citation); FR22
loaders to normalized shapes. Ops: FR23 audit log; FR24 CLI ingest/process/export/reset-demo.

## 4. Non-functional
Privacy (minimum collection, nothing sensitive in logs); security (Argon2, env
secrets, field encryption, encrypted backups, TLS when networked, localhost for
demo); reliability (raw file first, then DB in a transaction); offline-first;
performance (100 rows/s ingest, one night processed in < 10 min); reproducibility
(seeds, stored params, git SHA); explainability (flags store score components);
testability (synthetic data, no hardware); maintainability (types, ruff, one config).

## 5. Data model (UUID PKs; every user-owned table has indexed user_id)
- users(id, email, password_hash, status, created_at, is_synthetic); profiles; consents(scope, granted, ts, policy_version)
- devices; sessions(…metadata, raw_path, raw_sha256, rows, mean_rows_per_s, max_gap_s, gaps_over_50ms, usable, run_id); markers; reference_readings
- window_estimates; heart_estimates (experimental); night_features (+source_kind); pipeline_runs
- instrument_catalog; checkins_daily; survey_responses (answers encrypted); indices
- persona; baselines; flags(domain_pair, phys_level, mental_level, state, priority, components); associations [LATER]; safety_events (minimal); audit_log
- Research store: datasets, ref_subjects, ref_records, replay_personas
- Sensitivity: Green = derived physiology; Amber = check-ins, indices, flags; Red = survey answers, free text, safety_events (field-encrypted, never logged)

## 6. Scripts → backend
Pure typed functions, no globals/prints/hard-coded paths, one config file,
structured results, fixed seeds, explicit quality/error fields.
Path A file drop [MVP]; Path B HTTP and Path C live stream [LATER].

## 7. Accounts and personalization
Lifecycle incl. export/delete; onboarding outputs; per-user isolation tests;
baseline maturity (warm-up, widening, mature); consent scopes (check-ins, survey
answers, raw CSI, sharing); synthetic accounts flagged and excluded from real stats
(`v_real_users`); minimal profile.

## 8. Reference datasets
Separate store, licenses recorded, large files on disk, citations in About.
Adapters: ESP32 CSI sleep (IEEE DataPort), Sleep-EDF/SHHS, BIDMC, WESAD,
LifeSnaps, PMData. Replay personas = synthetic users fed through normal ingestion.

## 10. Security checklist
Argon2; secrets in env; encrypt red fields with a key outside the DB; localhost
for the demo; encrypted tested backups; export + delete (incl. raw files);
collect minimum; team/synthetic/public data only at the event; DPDP/GDPR advice
before any real users (not legal advice).

## 11. Testing
Unit tests on synthetic signals; DB tests (migrations, constraints, isolation);
contract tests; end-to-end raw → features; golden files; simulator scenarios.

## 13. Order of work (Stage 1)
1 repo/env → 2 contracts → 3 csi_core → 4 DB + first migration → 5 ingestion tool
→ 6 accounts + isolation → 7 instrument catalog + surveys → 8 dataset registry +
one adapter → 9 minimal API.

## 14. Risks
Time (steps 1–6 are the minimum); overnight capture reliability; storage growth;
SQLite single writer; schema drift (contracts prevent); logging leaks; heart-rate creep.

## 16–22. Stage 2 (summary)
Features: F1 exercise log [MVP], F2 weekly PMC-style report [MVP], F3
store-and-forward outbox [MVP], F4 symptom episodes with severe-symptom safety
[MVP], F5 cabin environment log [MVP manual], F6 sleep regularity [MVP computed],
F7 medication [LATER], F8 nutrition [LATER], F9 mission events [LATER], F10
guidance cards (5–8, reviewed, no AI medical advice) [MVP], F11 crew view [LATER].
Build order: F3, F1, F4, F6, F10, F2, F5.
Service rules: transactional outbox, idempotent, user-scoped, provenance,
safety-first return field. Routes thin; services never import FastAPI.
API prefix `/api/v1`; safety object `{show, reason, resources}` on survey and
symptom responses; frontend generated from `/openapi.json`; keep v1 stable
(add fields, never rename).
