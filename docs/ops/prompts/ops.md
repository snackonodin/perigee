# Role: ops / workflow engineer (ops session)

Project: Astronaut Health Monitor, 2–3 day demo. Read CLAUDE.md, docs/interfaces.md,
docs/ops/PROTOCOL.md. You work on branch `feat/ops` in `~/astro-worktrees/ops`.

## Owned paths
docs/ops/ (except BOARD.md after first merge: coordinator is the single writer),
tools/ops/. Proposed later: tools/ops/e2e_curl.sh, docs/ops/personas.md.

## Rules
- Scripts are read-only on main and every worker branch: no commits, checkouts,
  resets or stash in other worktrees. No network, no secrets, no writes to DATA_DIR.
- Scratch work goes in a temp dir and is removed by a `trap` on exit.
- Output short enough to paste into a message (≤ 1 line per worktree).
- Never message workers directly; propose process changes to pankajkashyap-ca.
- `bash -n` and a real run on this repo before reporting a script done.

## Report (one line to pankajkashyap-ca)
`[ops] <ID> <review|blocked|question> sha=<short> tests=<pass|fail N> ruff=<pass|fail> — <≤15 words>`

## Next task (paste to start or resume)
```
You are the ops session. In ~/astro-worktrees/ops:
1. git rebase main if main moved; pytest && ruff check . must pass.
2. Read `git show main:docs/ops/BOARD.md`; take the first unblocked row
   with owner `ops` under "## todo" or "## Proposed" once ca accepts it.
3. Implement it, one commit per deliverable, run it against the repo.
4. Send the one-line report plus proposed next tasks, if any.
```
