# Task board — Astronaut Health Monitor demo

**Single writer: pankajkashyap-ca (coordinator).** Workers never edit this file;
they report, and the coordinator moves rows. To move a task, cut the row and
paste it under the new column. Keep IDs stable.

Owners: `ca` coordinator · `f4` csi-core · `b0` db-ingest · `7a` accounts ·
`cf` surveys · `ops` workflow (session names are `pankajkashyap-<id>`).
Branch = `feat/<name>`, worktree = `~/astro-worktrees/<name>`.
**Next task for a worker** = the first row under `todo` with that owner whose
blockers are all in `done` (or `—`).
"Done when" always includes: `pytest && ruff check .` pass on the branch.

## todo

| ID | Task | Owner | Branch | Done when | Blockers |
|----|------|-------|--------|-----------|----------|
| DB-1 | `backend/db.py`: `get_engine` (FK, WAL, busy_timeout), `SessionLocal`; DB under `DATA_DIR` | b0 | db-ingest | test shows PRAGMAs set on a tmp DB | — |
| DB-2 | `models/base.py` `Base`, `UserOwned`, `scoped()` + all tables in interfaces.md | b0 | db-ingest | every user-owned table has indexed `user_id` FK CASCADE; `scoped` test | DB-1 |
| DB-3 | First Alembic migration | b0 | db-ingest | `alembic upgrade head` on empty tmp DB; downgrade works | DB-2 |
| DB-4 | `services/ingestion.py` `ingest_session` | b0 | db-ingest | re-ingest of same dir is a no-op (sha256); stats stored; `usable` honors threshold | DB-3, CORE-3 |
| DB-5 | `services/runs.py` `create_run`, `execute` (process_session, run_nightly) | b0 | db-ingest | output rows carry `run_id`; params + git SHA stored | DB-4, CORE-7 |
| DB-6 | `tools/cli.py` ingest / process / reset-demo / seed-personas / export | b0 | db-ingest | each subcommand has a test on tmp DATA_DIR | DB-5 |
| CORE-1 | `timebase.unwrap_us` | f4 | csi-core | wrap at 2^32 handled; monotonic; test over 3 wraps | — |
| CORE-2 | `synth.synth_night` (seeded) | f4 | csi-core | writes hourly `csi_HH.csv.gz` + meta.json + markers.csv in interfaces.md format; same seed → same bytes | CORE-1 |
| CORE-3 | `load.read_rotating`, `capture_stats` | f4 | csi-core | reads synth output; stats match known rate/gaps | CORE-2 |
| CORE-4 | `preprocess.clean` → `CleanSignal` | f4 | csi-core | quality_notes populated on gaps; no FastAPI/SQLAlchemy imports | CORE-3 |
| CORE-5 | `breath.estimate_windows` | f4 | csi-core | synth at 14 bpm recovers 14±1 bpm; motion windows flagged | CORE-4 |
| CORE-6 | `night.aggregate`, `update_baseline`, `robust_z` | f4 | csi-core | baseline maturity stages tested; alert nights excluded | CORE-5 |
| CORE-7 | `fusion.score_night` → `FlagDraft` | f4 | csi-core | components dict explains priority; thresholds only from config.yaml | CORE-6 |
| CORE-8 | Wrap user's real breathing / heart-rate / motion scripts into csi_core | f4 | csi-core | same outputs as scripts on a sample file; HR stays experimental | user supplies scripts |
| ACC-1 | `security.py` `hash_password` / `verify_password` (Argon2) | 7a | accounts | wrong pw fails; hash never logged | — |
| ACC-2 | access JWT + `new_refresh_token` (plaintext, sha256) | 7a | accounts | expired token rejected; secret from env only | ACC-1 |
| ACC-3 | `encrypt` / `decrypt` (Fernet FIELD_KEY) + `EncryptedJSON` | 7a | accounts | round-trip test; ciphertext ≠ plaintext in DB | DB-2 |
| ACC-4 | `backend/deps.py` `get_db`, `current_user` | 7a | accounts | 401 without token; returns user_id | DB-1, ACC-2 |
| ACC-5 | `services/accounts.py` signup/login/refresh/logout/export/delete | 7a | accounts | logout + delete revoke refresh tokens; delete removes raw files | DB-3, ACC-4 |
| ACC-6 | `api/v1/auth.py`, `api/v1/me.py` (routers, not mounted) | 7a | accounts | TestClient flow signup→login→me→logout | ACC-5 |
| ACC-7 | Isolation test: user A cannot read user B | 7a | accounts | test over every user-owned table via `scoped` | ACC-5 |
| SUR-1 | `seeds/instruments/*.json` (phq2, gad2, who5, phq9, daily_am, daily_pm) | cf | surveys | schema test; self-harm item has `safety_trigger`; license_note + source_url set | — |
| SUR-2 | `safety_check` (pure) | cf | surveys | trigger at min_value always shows; severe codes from config.yaml | SUR-1 |
| SUR-3 | `load_catalog` (idempotent), `get_instrument` | cf | surveys | 2nd load is a no-op | DB-3, SUR-1 |
| SUR-4 | `submit_response` (answers encrypted, safety first) | cf | surveys | safety object in response; answers never logged | SUR-2, SUR-3, ACC-3 |
| SUR-5 | `weekly_indices` | cf | surveys | ranges from seed scoring only | SUR-4 |
| SUR-6 | `seeds/guidance_cards.json` (5 cards) + `select_guidance` | cf | surveys | each card has source_note; `reviewed_by` null | DB-3 |
| SUR-7 | `api/v1/responses.py` router (not mounted) | cf | surveys | TestClient: safety path returns `{show, reason, resources}` | SUR-4, ACC-4 |
| CA-1 | Integrate routers in `backend/main.py` | ca | main | all routers mounted; /openapi.json lists them | ACC-6, SUR-7 |
| CA-2 | `/api/v1/today` (night features, flags, guidance, due check-ins) | ca | main | e2e test with seeded user | CA-1, DB-5, SUR-6 |
| CA-3 | Three synthetic personas (`is_synthetic`) via normal ingestion | ca | main | `cli seed-personas` → `/today` differs per persona | DB-6, CA-2, OPS-6 |
| CA-4 | Demo HTML page (single file, localhost) | ca | main | login → today → check-in → safety screen shown in a dry run | CA-2 |

## doing

| ID | Task | Owner | Branch | Done when | Blockers |
|----|------|-------|--------|-----------|----------|
| OPS-1 | BOARD.md | ops | ops | seeded from interfaces.md | — |
| OPS-2 | Role prompts `docs/ops/prompts/` | ops | ops | 6 files, each < 60 lines | — |
| OPS-3 | PROTOCOL.md | ops | ops | loop, escalation, merge order, rebase rule, daily stop | — |
| OPS-4 | `tools/ops/status.sh` | ops | ops | read-only; ≤ 1 line per worktree | — |
| OPS-5 | `tools/ops/check_merge.sh <branch>` | ops | ops | dry-run merge + tests in scratch worktree, cleaned up | — |

## review

| ID | Task | Owner | Branch | Done when | Blockers |
|----|------|-------|--------|-----------|----------|

## done

| ID | Task | Owner | Branch | Done when | Blockers |
|----|------|-------|--------|-----------|----------|
| SCAF | Scaffold: layout, config, contracts, docs, health API | ca | main | 7b576d3 | — |

## Proposed (coordinator to accept or drop)

| ID | Task | Owner | Note |
|----|------|-------|------|
| OPS-6 | Persona data spec (3 personas: steady, poor-sleep drift, mental-dip + safety demo) | ops | feeds CA-3 |
| OPS-7 | `tools/ops/e2e_curl.sh` demo flow against localhost | ops | feeds CA-4 rehearsal |
| CA-0 | Add `backend/db.py` (db-ingest) and `backend/deps.py` (accounts) to CLAUDE.md ownership; interfaces.md assigns them, CLAUDE.md does not | ca | avoids an ownership dispute |
