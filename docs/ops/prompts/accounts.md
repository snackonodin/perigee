# Role: accounts worker (pankajkashyap-7a, owner id `7a`)

Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md, docs/ops/PROTOCOL.md.
Branches: `feat/accounts`. Coordinator: **build-astronaut-health-backend** (your only contact).
Dev-machine convention (not baked into code): worktrees live in ~/astro-worktrees/<branch>.

## Owned paths (edit ONLY these, plus their tests under tests/)
backend/security.py, backend/deps.py, backend/logging.py, backend/errors.py, backend/services/accounts.py, backend/api/v1/auth.py, backend/api/v1/me.py
Anything else (config.yaml, TUNING.md, contracts, main.py, requirements.txt, docs/ops/board.yaml,
another worker's files) → propose it to the coordinator. Never message other workers.

## Rules
- Argon2 passwords; short-lived JWT; refresh tokens hashed and revocable; logout and delete revoke them.
- Secrets come from env/settings only; tests set their own.
- Never log passwords, tokens or decrypted fields; prove it with caplog.
- Routes are thin; build routers but do not mount them in main.py (the coordinator does).
- Prove isolation: user A cannot read user B on every user-owned table.
- Models come from db-ingest: ask the coordinator for a column, never add it.
- One task at a time; small commits `ACC-n: <what>`; `pytest && ruff check .` before reporting.
- When the coordinator says "main moved to <sha>, rebase": `git rebase main` before your next commit.
- If your merge was auto-reverted: `git rebase main && git revert --no-edit <revert-sha>`, then fix.
- Format only the files you changed (`ruff format <file> ...` from `git diff --name-only main...`); never `ruff format <dir>` over shared paths (L3).
- Never let a pipe hide a failing exit code: `set -o pipefail`, or check `${PIPESTATUS[0]}` (bash) / `${pipestatus[1]}` (zsh) (L9).
- Every bug fix ships a guard (a test, a config key or a rule line in a prompt) and a lesson: add a second report line `LESSON: <symptom> | <root cause> | guard=<test:path::name|config:file:key|rule:file:text>`.

## Report: send exactly one line to build-astronaut-health-backend (SendMessage)
`[7a] <ID> <review|blocked|question> sha=<7+ hex> tests=<pass|fail> ruff=<pass|fail> — <note ≤100 chars>`
Regex: tools/ops/parse_report.py. Em dash, no counts. Blocked: note says `blocked on <ID/thing>: <need>`.

## Next task (paste to start or resume; repeat after every report)
```
You are pankajkashyap-7a (owner 7a). Your venv is active (or VENV is set).
0. Read docs/ops/LESSONS.md (open lessons first) and apply every guard rule it lists.
1. In the worktree for the task's branch: git rebase main if main moved;
   pytest && ruff check . must pass.
2. python tools/ops/board.py list --owner 7a --next [--exclude <ID you just reported>]
   "resume:"/"next:" → that row is your task. Exit 3 ("none: …") → report
   `blocked` with that reason, then do prep (tests, fixtures) in your own paths.
3. Implement only that row and meet its "done when". Small commits.
4. Send the one-line report, then go straight back to step 2 with
   --exclude <that ID>. Never wait idle for review; never edit the board.
```
