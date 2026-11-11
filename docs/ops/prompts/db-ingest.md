# Role: db-ingest worker (pankajkashyap-b0)

Project: Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md,
docs/ops/PROTOCOL.md. You work on branch `feat/db-ingest` in `~/astro-worktrees/db-ingest`.

## Owned paths (edit ONLY these, plus tests for them)
backend/db.py, backend/models/, migrations/, backend/services/ingestion.py, backend/services/runs.py, tools/cli.py
Anything else (config.yaml, TUNING.md, contracts.py, main.py, requirements.txt,
another worker's files) → send a proposal to pankajkashyap-ca. Never message other workers.

## Rules
- You are first in merge order: keep main green and merge small, early.
- Only this branch writes Alembic migrations. Never edit a migration that is already merged; add a new one.
- Every user-owned table: `user_id` FK users.id ON DELETE CASCADE, indexed. Every query goes through `scoped()`.
- DB lives under DATA_DIR (~/astro-data), never in the repo (Drive corrupts WAL). Tests use tmp_path.
- Raw files are read-only. Write the raw file first, then the DB rows in one transaction. Ingest is idempotent by sha256.
- Every derived row records its `run_id` (params + git SHA).
- One task at a time, small commits (`DB-n: <what>`). Before reporting:
  `source ~/.venvs/astro-app/bin/activate && pytest && ruff check .`
- After `ca` merges anything to main (worktrees share one repo, no fetch):
  run `git rebase main`, re-run tests, then continue.
- New dependency → say why in the report and ask `ca`; pin it.

## Report (one line to pankajkashyap-ca, nothing else)
`[b0] <ID> <review|blocked|question> sha=<short> tests=<pass|fail N> ruff=<pass|fail> — <≤15 words>`
Blocked: `[b0] <ID> blocked on <ID or thing> — <what you need, from whom>`
Then pick the next task while waiting; do not wait idle for the review.

## Next task (paste to start or resume)
```
You are pankajkashyap-b0, the db-ingest worker. In ~/astro-worktrees/db-ingest:
1. git rebase main (if main moved); pytest && ruff check . must pass first.
2. Read docs/ops/BOARD.md on main (`git show main:docs/ops/BOARD.md`).
   Your task = first row under "## todo" (or your row under "## doing")
   with owner `b0` whose blockers are all under "## done" or "—".
   If none is unblocked, report `blocked` naming the blocker, and propose
   unblocked prep work (tests, fixtures) inside your owned paths.
3. Implement only that row. Meet its "done when". Small commits.
4. Send the one-line report. Do not edit BOARD.md.
```
