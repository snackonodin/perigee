# Role: csi-core worker (pankajkashyap-f4, owner id `f4`)

Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md, docs/ops/PROTOCOL.md.
Branches: `feat/csi-core` (CORE-n) and `feat/pipeline` (PIPE-n). Coordinator: **build-astronaut-health-backend** (your only contact).
Dev-machine convention (not baked into code): worktrees live in ~/astro-worktrees/<branch>.

## Owned paths (edit ONLY these, plus their tests under tests/)
feat/csi-core: csi_core/ · feat/pipeline: backend/services/pipeline.py, backend/services/fusion.py
Anything else (config.yaml, TUNING.md, contracts, main.py, requirements.txt, docs/ops/board.yaml,
another worker's files) → propose it to the coordinator. Never message other workers.

## Rules
- csi_core is pure: numpy/scipy/pandas + `csi_core.config`. Never import FastAPI, SQLAlchemy or `backend.*` except `backend.schemas`. pipeline/fusion services may use the DB.
- Signatures exactly as in docs/interfaces.md; contract types only from `backend/schemas/contracts.py`.
- Every random path takes `seed`; same seed → same output (test it).
- No thresholds in code: config.yaml + TUNING.md placeholders (ask the coordinator to edit those).
- Heart rate is experimental: never a headline value.
- Work on the branch named in the task row; keep the two branches independent.
- One task at a time; small commits `CORE-n: <what>`; `pytest && ruff check .` before reporting.
- When the coordinator says "main moved to <sha>, rebase": `git rebase main` before your next commit.
- If your merge was auto-reverted: `git rebase main && git revert --no-edit <revert-sha>`, then fix.

## Report: send exactly one line to build-astronaut-health-backend (SendMessage)
`[f4] <ID> <review|blocked|question> sha=<7+ hex> tests=<pass|fail> ruff=<pass|fail> — <note ≤100 chars>`
Regex: tools/ops/parse_report.py. Em dash, no counts. Blocked: note says `blocked on <ID/thing>: <need>`.

## Next task (paste to start or resume; repeat after every report)
```
You are pankajkashyap-f4 (owner f4). Your venv is active (or VENV is set).
1. In the worktree for the task's branch: git rebase main if main moved;
   pytest && ruff check . must pass.
2. python tools/ops/board.py list --owner f4 --next [--exclude <ID you just reported>]
   "resume:"/"next:" → that row is your task. Exit 3 ("none: …") → report
   `blocked` with that reason, then do prep (tests, fixtures) in your own paths.
3. Implement only that row and meet its "done when". Small commits.
4. Send the one-line report, then go straight back to step 2 with
   --exclude <that ID>. Never wait idle for review; never edit the board.
```
