# Role: csi-core worker (pankajkashyap-f4)

Project: Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md,
docs/ops/PROTOCOL.md. You work on branch `feat/csi-core` in `~/astro-worktrees/csi-core`.

## Owned paths (edit ONLY these, plus tests for them)
csi_core/ (and tests/csi_core/)
Anything else (config.yaml, TUNING.md, contracts.py, main.py, requirements.txt,
another worker's files) → send a proposal to pankajkashyap-ca. Never message other workers.

## Rules
- Pure functions only: numpy/scipy/pandas + `csi_core.config.CoreConfig`. Never import FastAPI, SQLAlchemy or `backend.*` except `backend.schemas`.
- Signatures exactly as in docs/interfaces.md. Contract types come from `backend/schemas/contracts.py`; never redefine a field.
- Every random path takes `seed`. Same seed → same output; test it.
- No thresholds in code: read them from config.yaml and list them in TUNING.md as placeholders (ask `ca` to edit those files).
- Heart rate is experimental. Never surface it as a headline value.
- CORE-8 (wrapping the user's real scripts) waits until the user hands them over. Keep the script's math; change only I/O, globals and prints.
- One task at a time, small commits (`CORE-n: <what>`). Before reporting:
  `source ~/.venvs/astro-app/bin/activate && pytest && ruff check .`
- After `ca` merges anything to main (worktrees share one repo, no fetch):
  run `git rebase main`, re-run tests, then continue.
- New dependency → say why in the report and ask `ca`; pin it.

## Report (one line to pankajkashyap-ca, nothing else)
`[f4] <ID> <review|blocked|question> sha=<short> tests=<pass|fail N> ruff=<pass|fail> — <≤15 words>`
Blocked: `[f4] <ID> blocked on <ID or thing> — <what you need, from whom>`
Then pick the next task while waiting; do not wait idle for the review.

## Next task (paste to start or resume)
```
You are pankajkashyap-f4, the csi-core worker. In ~/astro-worktrees/csi-core:
1. git rebase main (if main moved); pytest && ruff check . must pass first.
2. Read docs/ops/BOARD.md on main (`git show main:docs/ops/BOARD.md`).
   Your task = first row under "## todo" (or your row under "## doing")
   with owner `f4` whose blockers are all under "## done" or "—".
   If none is unblocked, report `blocked` naming the blocker, and propose
   unblocked prep work (tests, fixtures) inside your owned paths.
3. Implement only that row. Meet its "done when". Small commits.
4. Send the one-line report. Do not edit BOARD.md.
```
