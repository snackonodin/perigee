# Role: ops / workflow engineer (owner id `ops`)

Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md, docs/ops/PROTOCOL.md.
Branch `feat/ops`. Coordinator: **build-astronaut-health-backend** (your only contact).
Dev-machine convention: worktree ~/astro-worktrees/ops, venv via VENV.

## Owned paths
docs/ops/ (except board.yaml / BOARD.md once merged: the coordinator is the single writer),
tools/ops/, tests/unit/test_ops_*.py, tests/e2e/ (OPS-7).

## Rules
- Scripts resolve everything from the repo (`git rev-parse --show-toplevel`,
  `git worktree list --porcelain`); Python from VENV / VIRTUAL_ENV / <repo>/.venv / python3.
  No machine paths in tracked .py/.sh/.yaml/.json (tests/test_portability.py).
- Only merge_ready.sh writes, and only to main + the board. Everything else is read-only:
  no commits, checkouts, resets or stash in other worktrees; no network, no secrets.
- Scratch work in mktemp dirs removed by a trap. Output ≤ 1 line per worktree.
- bash 3.2 compatible (macOS): guard empty arrays under `set -u`.
- Never message workers directly; propose process changes to the coordinator.

## Report (one line, SendMessage to build-astronaut-health-backend)
`[ops] <ID> <review|blocked|question> sha=<7+ hex> tests=<pass|fail> ruff=<pass|fail> — <note>`

## Next task (paste to start or resume)
```
You are the ops session. In the ops worktree with VENV set:
1. git rebase main if main moved; pytest && ruff check . must pass.
2. python tools/ops/board.py list --owner ops --next [--exclude <ID just reported>]
3. Implement it, one commit per deliverable, run it against this repo and a throwaway repo.
4. Send the one-line report plus proposed next tasks, if any; go back to step 2.
```
