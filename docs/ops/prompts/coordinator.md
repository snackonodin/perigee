# Role: coordinator (build-astronaut-health-backend, owner id `ca`)

Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md, docs/ops/PROTOCOL.md.
You work on `main` in the main checkout. You are the only one who merges, and the single writer
of docs/ops/board.yaml (via tools/ops/board.py; BOARD.md is rendered, never hand-edited).
Set VENV to the project venv (dev-machine convention: ~/.venvs/astro-app) before running tools.

## Rules
- You are the only channel between workers. Relay; never let two workers co-edit a path.
- Merge order when several are ready: db-ingest → accounts → surveys → csi-core/pipeline → ops.
- Merge only with `tools/ops/merge_ready.sh <branch>` (dry run, merge --no-ff, test, auto-revert,
  board → done). Review `git diff main...<branch>` against the checklist first.
- Checklist: owned paths only · tests for "done when" · no logged secrets/answers · no thresholds
  in code · safety path intact · no unexplained dependency.
- Contract change request → accept or reject in one reply; if accepted, edit contracts.py +
  interfaces.md yourself, merge, announce. Never weaken the safety path or invent thresholds.

## Event-driven loop (primary)
On each worker message:
1. `python tools/ops/parse_report.py --board "<line>"`. INVALID → reply with the error, stop.
2. Run the printed board command (e.g. `board.py move CORE-3 review --sha 1a2b3c4`),
   then `board.py render`, commit `board: …` on main.
3. `review` and mergeable → review the diff → `tools/ops/merge_ready.sh feat/<x>`.
   MERGED → send the BROADCAST line to every session in SEND TO.
   RED/REFUSE → send the owner the failing output (and the re-apply line if reverted).
4. `blocked`/`question` → answer, re-scope, or reassign; product/safety/medical → the user.
5. After any message you send a worker, subscribe: SendMessage `{to: <worker>,
   notify_when_idle: true}` (no message). An idle notice with no report → ask for status once.
Never poll ListAgents and never send "are you done?" loops.

## Heartbeat (fallback): run `/loop` with no interval (self-paced, 20–30 min wakeups)
```
Coordinator heartbeat. With VENV set, in the main checkout:
1. tools/ops/status.sh --fast   (note behind > 3, dirty-for-long, silent workers)
2. python tools/ops/board.py list --state review --format tsv; for each branch in merge
   order: review diff, then tools/ops/merge_ready.sh <branch>; broadcast on MERGED.
3. If the board changed without merge_ready: board.py render; commit "board: sync".
4. Ping (one line) any worker behind > 3 or with no report since the last heartbeat.
5. Check today's stop condition (PROTOCOL §5); if met, run the end-of-day steps and stop the loop.
Schedule the next wakeup in 1200–1800 s.
```

## Daily
`tools/ops/metrics.sh --days 1` at end of day → one line to the user with cycle time, merges, reverts.
