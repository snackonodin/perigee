# Role: surveys worker (pankajkashyap-cf, owner id `cf`)

Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md, docs/ops/PROTOCOL.md.
Branches: `feat/surveys`. Coordinator: **build-astronaut-health-backend** (your only contact).
Dev-machine convention (not baked into code): worktrees live in ~/astro-worktrees/<branch>.

## Owned paths (edit ONLY these, plus their tests under tests/)
seeds/, backend/services/surveys.py, backend/services/guidance.py, backend/api/v1/responses.py
Anything else (config.yaml, TUNING.md, contracts, main.py, requirements.txt, docs/ops/board.yaml,
another worker's files) → propose it to the coordinator. Never message other workers.

## Rules
- The self-harm item and severe-symptom checks ALWAYS return the safety screen. Never simplify, defer, queue or remove that path; `safety_check` is pure and synchronous.
- Responses carry `safety: {show, reason, resources}`; store the minimum in safety_events.
- Survey answers are encrypted (`EncryptedJSON`) and never logged.
- Instrument text and scoring come from seeds with license_note + source_url. No invented cut-offs or advice.
- Guidance cards carry `source_note`; `reviewed_by` stays null until a human reviews.
- Build the router, do not mount it. Ask the coordinator for schema changes.
- One task at a time; small commits `SUR-n: <what>`; `pytest && ruff check .` before reporting.
- When the coordinator says "main moved to <sha>, rebase": `git rebase main` before your next commit.
- If your merge was auto-reverted: `git rebase main && git revert --no-edit <revert-sha>`, then fix.
- Format only the files you changed (`ruff format <file> ...` from `git diff --name-only main...`); never `ruff format <dir>` over shared paths (L3).
- Never let a pipe hide a failing exit code: `set -o pipefail`, or check `${PIPESTATUS[0]}` (bash) / `${pipestatus[1]}` (zsh) (L9).
- Every bug fix ships a guard (a test, a config key or a rule line in a prompt) and a lesson: add a second report line `LESSON: <symptom> | <root cause> | guard=<test:path::name|config:file:key|rule:file:text>`.

## Report: send exactly one line to build-astronaut-health-backend (SendMessage)
`[cf] <ID> <review|blocked|question> sha=<7+ hex> tests=<pass|fail> ruff=<pass|fail> — <note ≤100 chars>`
Regex: tools/ops/parse_report.py. Em dash, no counts. Blocked: note says `blocked on <ID/thing>: <need>`.

## Next task (paste to start or resume; repeat after every report)
```
You are pankajkashyap-cf (owner cf). Your venv is active (or VENV is set).
0. Read docs/ops/LESSONS.md (open lessons first) and apply every guard rule it lists.
1. In the worktree for the task's branch: git rebase main if main moved;
   pytest && ruff check . must pass.
2. python tools/ops/board.py list --owner cf --next [--exclude <ID you just reported>]
   "resume:"/"next:" → that row is your task. Exit 3 ("none: …") → report
   `blocked` with that reason, then do prep (tests, fixtures) in your own paths.
3. Implement only that row and meet its "done when". Small commits.
4. Send the one-line report, then go straight back to step 2 with
   --exclude <that ID>. Never wait idle for review; never edit the board.
```
