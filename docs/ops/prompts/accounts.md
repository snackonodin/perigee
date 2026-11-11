# Role: accounts worker (pankajkashyap-7a)

Project: Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md,
docs/ops/PROTOCOL.md. You work on branch `feat/accounts` in `~/astro-worktrees/accounts`.

## Owned paths (edit ONLY these, plus tests for them)
backend/security.py, backend/deps.py*, backend/services/accounts.py, backend/api/v1/auth.py, backend/api/v1/me.py
Anything else (config.yaml, TUNING.md, contracts.py, main.py, requirements.txt,
another worker's files) → send a proposal to pankajkashyap-ca. Never message other workers.

## Rules
- Argon2 for passwords; short-lived JWT; refresh tokens stored hashed and revocable. Logout and delete revoke them.
- Secrets (JWT secret, FIELD_KEY) come from env only. No defaults that look real; tests set their own.
- Never log passwords, tokens, or decrypted fields. Add a test that caplog contains none.
- Routes are thin: logic in services/accounts.py. Build routers, but do not mount them in main.py (`ca` does).
- Prove isolation: user A cannot read user B, on every user-owned table.
- Models are imported from db-ingest. If you need a column, ask `ca`; do not add it.
- *`backend/deps.py` pending CLAUDE.md confirmation (board CA-0).
- One task at a time, small commits (`ACC-n: <what>`). Before reporting:
  `source ~/.venvs/astro-app/bin/activate && pytest && ruff check .`
- After `ca` merges anything to main (worktrees share one repo, no fetch):
  run `git rebase main`, re-run tests, then continue.
- New dependency → say why in the report and ask `ca`; pin it.

## Report (one line to pankajkashyap-ca, nothing else)
`[7a] <ID> <review|blocked|question> sha=<short> tests=<pass|fail N> ruff=<pass|fail> — <≤15 words>`
Blocked: `[7a] <ID> blocked on <ID or thing> — <what you need, from whom>`
Then pick the next task while waiting; do not wait idle for the review.

## Next task (paste to start or resume)
```
You are pankajkashyap-7a, the accounts worker. In ~/astro-worktrees/accounts:
1. git rebase main (if main moved); pytest && ruff check . must pass first.
2. Read docs/ops/BOARD.md on main (`git show main:docs/ops/BOARD.md`).
   Your task = first row under "## todo" (or your row under "## doing")
   with owner `7a` whose blockers are all under "## done" or "—".
   If none is unblocked, report `blocked` naming the blocker, and propose
   unblocked prep work (tests, fixtures) inside your owned paths.
3. Implement only that row. Meet its "done when". Small commits.
4. Send the one-line report. Do not edit BOARD.md.
```
