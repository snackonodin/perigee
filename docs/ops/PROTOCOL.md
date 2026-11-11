# Team protocol — the loop

Six Claude sessions: coordinator `ca` (merges to main) + workers `f4` csi-core,
`b0` db-ingest, `7a` accounts, `cf` surveys, and `ops`. One branch and one worktree
each (`~/astro-worktrees/<name>`), all sharing one repo, so no fetch/push is needed.
Role prompts: `docs/ops/prompts/<role>.md`. Board: `docs/ops/BOARD.md`.

## 1. The loop

```
worker:  pick task ─► implement (small commits) ─► pytest + ruff ─► 1-line report
                                                                       │
coordinator:  check_merge.sh ─► review diff ─► merge --no-ff ─► BOARD ─┘
              └─► "main moved to <sha>, rebase" ─► workers rebase ─► next task
```

1. **Pick.** Read `git show main:docs/ops/BOARD.md`. Your task is the first row under
   `todo` with your owner id whose blockers are all `done` or `—`. Tell nobody; just
   start (`ca` sees it in the next status sweep or report).
2. **Implement** in small commits named `<ID>: <what>`, only in owned paths. Add the
   test that proves the row's "done when".
3. **Verify:** `source ~/.venvs/astro-app/bin/activate && pytest && ruff check .`
4. **Report** one line to `pankajkashyap-ca`:
   `[<id>] <ID> review sha=<short> tests=pass ruff=pass — <≤15 words>`
   Then start the next unblocked task. Do not wait idle for review.
5. **Review + merge (ca).** `tools/ops/check_merge.sh feat/<x>` must print `MERGE OK`.
   Review `git diff main...feat/<x>` against the checklist in `prompts/coordinator.md`.
   Merge with `git merge --no-ff`, re-run pytest + ruff on main.
   If the review finds problems, send one message with every fix needed. The row
   goes back to `doing`.
6. **Board (ca).** Move the rows, commit `board: <IDs> → done`, and unblock dependants.
7. **Announce (ca):** "main moved to <sha>, rebase" goes to each worker with an unmerged branch.

Cadence: `ca` runs `tools/ops/status.sh` at least once per loop and pastes the output
into its notes. A healthy loop is 30–90 min per task. A task over ~2 h gets split.

## 2. Rebase-after-merge rule
- When main moves, every worker runs `git rebase main` **before its next commit**,
  re-runs pytest + ruff, and fixes anything that broke on its own branch.
- Never merge main into a feature branch; rebase only. Never rewrite main.
- A rebase conflict in a path you do not own means an ownership bug. Stop and
  report `blocked` to `ca`; do not resolve it by editing the other side.
- A branch more than 3 commits behind main does not get reviewed until it rebases.

## 3. Merge order
When several branches are in review at once:
**db-ingest → accounts → surveys → csi-core → ops.**
Models and migrations land first because accounts and surveys import them.
csi-core is pure and rarely conflicts, so it goes last in a batch. It may still
merge on its own at any time when nothing ahead of it is waiting.
Only `ca` merges. Only `--no-ff` (one revertable merge commit per task batch).
If main goes red after a merge, run `git revert -m 1 <merge>` immediately, then send
the owner the failing test.

## 4. Blocker escalation
| Situation | Worker does | Coordinator does | Time box |
|---|---|---|---|
| Waiting on another row | report `blocked on <ID>`; do prep inside own paths (tests, fixtures, stubs behind the interface) | re-prioritise the blocking row | — |
| Need a contract / shared-file change | report `question` with the exact diff proposed | accept or reject in 1 reply; if accepted, edit contracts.py + interfaces.md, merge, announce | 1 loop |
| Tests fail and you can't see why | after 20 min, report `blocked` with the failing test name | pair via messages or re-scope | 20 min |
| Product, safety or medical-content question | report `question`; never guess a threshold | escalate to the user; never weaken the safety path | user |
| Ownership conflict | stop; report | decide owner, update CLAUDE.md | 1 loop |

Workers never message each other. All cross-team traffic goes through `ca`.

## 5. Daily stop conditions
Each day ends at the earlier of: (a) the day's goal is met, or (b) the hour the
user sets. Only (a) moves the plan forward. At (b) without (a), `ca` re-plans the
board before stopping.

| Day | Goal: merged to main and green |
|---|---|
| 1 | DB-1..3, CORE-1..4, ACC-1..3, SUR-1..2. Status shows every branch rebased. |
| 2 | DB-4..6, CORE-5..7, ACC-4..7, SUR-3..7, CA-1 (routers mounted). |
| 3 | CA-2..4: `/today`, 3 personas, demo page. Feature freeze at midday; afternoon is fixes and two clean demo rehearsals. |

**End-of-day steps (ca):**
1. Merge or explicitly park every branch in review. No half-merged state.
2. main green: `pytest && ruff check .`
3. `git tag day<N>-green`
4. Run `tools/ops/status.sh` and send the user one line per worker: done, in progress, blocked.
5. Tell workers to stop. Each worker commits WIP as `WIP <ID>: …` on its own branch.
   It never leaves uncommitted changes behind.

**Hard stop at any time:** if main is red and not fixed within 30 min, reset the plan
to the last `day<N>-green` tag by reverting merges (never `reset --hard` on main) and
re-plan.

## 6. Tools
- `tools/ops/status.sh [--fast]`: read-only. One line per worktree: branch,
  last commit, ahead/behind main, and the pytest/ruff result (`--fast` skips the checks).
- `tools/ops/check_merge.sh feat/<x>`: read-only dry run. Detects conflicts with
  merge-tree, then runs tests on a temporary merge in a scratch worktree and removes it.
