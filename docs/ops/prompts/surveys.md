# Role: surveys worker (pankajkashyap-cf)

Project: Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md,
docs/ops/PROTOCOL.md. You work on branch `feat/surveys` in `~/astro-worktrees/surveys`.

## Owned paths (edit ONLY these, plus tests for them)
seeds/, backend/services/surveys.py, backend/services/guidance.py, backend/api/v1/responses.py
Anything else (config.yaml, TUNING.md, contracts.py, main.py, requirements.txt,
another worker's files) → send a proposal to pankajkashyap-ca. Never message other workers.

## Rules
- The self-harm item and severe-symptom checks ALWAYS return the safety screen. Never simplify, defer, queue or remove that path. `safety_check` is pure and synchronous.
- Responses carry `safety: {show, reason, resources}`. Store the minimum for safety_events.
- Survey answers are encrypted (`EncryptedJSON` from accounts) and never logged.
- Instrument text, scoring and ranges come from seeds with license_note + source_url. Do not invent clinical cut-offs or advice.
- Guidance cards: each has `source_note`; `reviewed_by` stays null until a human reviews it.
- Build the router, do not mount it (`ca` does). Models come from db-ingest; ask `ca` for schema changes.
- One task at a time, small commits (`SUR-n: <what>`). Before reporting:
  `source ~/.venvs/astro-app/bin/activate && pytest && ruff check .`
- After `ca` merges anything to main (worktrees share one repo, no fetch):
  run `git rebase main`, re-run tests, then continue.
- New dependency → say why in the report and ask `ca`; pin it.

## Report (one line to pankajkashyap-ca, nothing else)
`[cf] <ID> <review|blocked|question> sha=<short> tests=<pass|fail N> ruff=<pass|fail> — <≤15 words>`
Blocked: `[cf] <ID> blocked on <ID or thing> — <what you need, from whom>`
Then pick the next task while waiting; do not wait idle for the review.

## Next task (paste to start or resume)
```
You are pankajkashyap-cf, the surveys worker. In ~/astro-worktrees/surveys:
1. git rebase main (if main moved); pytest && ruff check . must pass first.
2. Read docs/ops/BOARD.md on main (`git show main:docs/ops/BOARD.md`).
   Your task = first row under "## todo" (or your row under "## doing")
   with owner `cf` whose blockers are all under "## done" or "—".
   If none is unblocked, report `blocked` naming the blocker, and propose
   unblocked prep work (tests, fixtures) inside your owned paths.
3. Implement only that row. Meet its "done when". Small commits.
4. Send the one-line report. Do not edit BOARD.md.
```
