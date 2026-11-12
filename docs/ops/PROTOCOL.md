# Team protocol: the loop

Six Claude sessions. The coordinator **build-astronaut-health-backend** (owner `ca`, merges to
main) plus workers `f4` csi-core + pipeline, `b0` db-ingest, `7a` accounts, `cf` surveys, and `ops`.
Each branch has its own worktree, and all share one repo, so there is no fetch or push.
Dev-machine conventions (not baked into code): worktrees in `~/astro-worktrees/<branch>`,
venv at `~/.venvs/astro-app`. Tools find Python via `VENV`, an active venv, `<repo>/.venv`,
then `python3`. Set `VENV` (or activate the venv) before running `tools/ops/*`.

Role prompts: `docs/ops/prompts/<role>.md`.
Board: `docs/ops/board.yaml`, the source of truth, written only by the coordinator via
`tools/ops/board.py`. `BOARD.md` is rendered from it.

## 1. The loop

```
worker:  board.py --next ─► implement (small commits) ─► pytest + ruff ─► 1-line report ─┐
            ▲                                                                            │
            └──── board.py --next --exclude <ID> (immediately, never idle) ◄────────────┤
coordinator:  parse_report.py ─► board move review ─► review diff ─► merge_ready.sh ◄────┘
              MERGED ─► BOARD done + "main moved to <sha>, rebase" ─► workers rebase
```

1. **Pick.** `python tools/ops/board.py list --owner <id> --next`. It reads main's board and
   returns the owner's `doing` row (resume), or else the first `todo` row whose blockers are
   satisfied. A blocker is satisfied when it is `done`, or when it belongs to the same owner and
   is in `review` (the work is already on that branch). Exit 3 means nothing is pickable;
   report `blocked` with the printed reason and do prep work in your own paths.
2. **Implement** in small commits named `<ID>: <what>`, only in owned paths, plus the test that
   proves the row's "done when".
3. **Verify:** `pytest && ruff check .`
4. **Report** one line to the coordinator via SendMessage, in exactly this format:
   `[<id>] <ID> <review|blocked|question> sha=<hex7+> tests=<pass|fail> ruff=<pass|fail> — <note>`
   The regex lives in `tools/ops/parse_report.py`:
   `^\[(f4|b0|7a|cf|ops)\] [A-Z]+-\d+ (review|blocked|question) sha=[0-9a-f]{7,40} tests=(pass|fail) ruff=(pass|fail) — .{1,100}$`
   Then run step 1 again with `--exclude <ID>`. Never wait idle for review.
5. **Intake (coordinator).** Run `parse_report.py --board "<line>"`. An INVALID line is bounced
   with the reason. Otherwise run the printed `board.py move …`.
6. **Merge (coordinator).** Review `git diff main...<branch>`, then run
   `tools/ops/merge_ready.sh <branch>`. It refuses if main's worktree is dirty, then:
   check_merge.sh → `merge --no-ff` → pytest + ruff on main.
   - Red: automatic `git revert -m 1`, rows go back to `doing`, failing tests are printed,
     exit 1.
   - Green: rows go to `done` with the merge sha, BOARD.md is rendered and committed, and it
     prints `BROADCAST: main moved to <sha>, rebase` plus `SEND TO: <sessions>`.
7. **Broadcast (coordinator):** send that line to each listed session.

## 2. Coordinator automation

**Event-driven (primary).** Workers report through SendMessage. After every message the
coordinator sends a worker, it subscribes with `SendMessage {to: <worker>, notify_when_idle: true}`.
An idle notice that arrives with no report gets one status ping. No polling and no
"are you done?" loops.

**Heartbeat (fallback).** The coordinator runs a self-paced `/loop` with no interval that wakes
every 20–30 min. Each pass:
1. `status.sh --fast`;
2. `merge_ready.sh` on `review` rows, in merge order;
3. board render + commit;
4. broadcast rebase notices;
5. ping workers that are silent or more than 3 commits behind.

The exact recipe is in `prompts/coordinator.md`.

## 3. Rebase-after-merge rule
- When main moves, every worker runs `git rebase main` **before its next commit**, then re-runs
  pytest + ruff and fixes anything that broke on its own branch.
- Never merge main into a feature branch; rebase only. Never rewrite main.
- A rebase conflict in a path you do not own is an ownership bug: report `blocked`, do not
  edit the other side.
- A branch more than 3 commits behind main is not reviewed until it rebases.
- **After an auto-revert** git will not re-merge the reverted commits. The owner runs
  `git rebase main && git revert --no-edit <revert-sha>` (re-applies the work), fixes it,
  commits and reports `review` again. merge_ready prints the exact line.

## 4. Merge order
When several branches are in review: **db-ingest → accounts → surveys → csi-core/pipeline → ops.**
Models and migrations land first because accounts and surveys import them. csi-core is pure and
may merge alone at any time when nothing ahead of it is waiting. Only the coordinator merges,
and only through merge_ready.sh, so every merge is `--no-ff` and can be reverted.

## 5. Blocker escalation
| Situation | Worker | Coordinator | Time box |
|---|---|---|---|
| Waiting on another row | `blocked on <ID>`; prep in own paths (tests, fixtures, stubs) | re-prioritise the blocking row | — |
| Contract / shared-file change | `question` with the exact diff | accept or reject in 1 reply; edit contracts.py + interfaces.md, merge, announce | 1 loop |
| Tests fail, cause unclear | after 20 min, `blocked` with the failing test name | pair via messages or re-scope | 20 min |
| Product, safety or medical content | `question`; never guess a threshold | ask the user; never weaken the safety path | user |
| Ownership conflict | stop; report | decide the owner, update CLAUDE.md | 1 loop |

Workers may send each other one-line coordination heads-ups ("I'm editing X now", "not touching Y").
Design questions, contract changes, ownership and task assignment go through the coordinator.

## 6. Daily stop conditions
A day ends at the earlier of (a) its goal being met, or (b) the hour the user sets. At (b)
without (a), the coordinator re-plans the board before stopping.

| Day | Goal: merged to main and green |
|---|---|
| 1 | DB-1..4, CORE-1..6, ACC-1..3, SUR-1..3, OPS-1..13. Every branch rebased. |
| 2 | DB-5..6, CORE-7, PIPE-1..2, ACC-4..7, SUR-4..7, CA-1, OPS-6. |
| 3 | CA-2..4, OPS-7: `/today`, 3 personas, demo page, e2e flow. Feature freeze at midday, then fixes and two clean rehearsals. |

**End of day (coordinator):**
1. Merge or explicitly park every `review` row.
2. Main is green.
3. `git tag day<N>-green`.
4. Run `metrics.sh --days 1` and `status.sh`, and send the user one line per worker.
5. Tell the workers to stop. Each commits WIP as `WIP <ID>: …` on its own branch.

**Hard stop:** if main is red and not fixed within 30 min, revert merges back to the last
`day<N>-green` (never `reset --hard` main) and re-plan.

## 7. Tools (all under tools/ops/, all path-free)
| Tool | Who | Writes? | What |
|---|---|---|---|
| `status.sh [--fast]` | anyone | no | one line per worktree: branch, sha, age, ±main, dirty, tests, ruff |
| `check_merge.sh <br>` | anyone | no | merge-tree conflicts, ownership + reformat-only warnings (L3), tests on the merged tree in a scratch worktree (tracked files only, L1); if `frontend/` changed, `npm ci --offline` + `tsc` + `vitest` too (LOOP-2) |
| `merge_ready.sh <br> [ID…]` | coordinator | main + board + lessons | check → merge → test the merge commit in a scratch checkout (pytest, ruff, and the frontend checks when `frontend/` changed) → auto-revert + lesson stub, or board done + broadcast |
| `lessons.py add/list/close/render/stats` | coordinator (stubs: merge_ready, stress) | lessons | source of truth for lessons; `close` refuses unless the guard exists |
| `board.py list/move/render/validate/owners` | list: anyone; move/render: coordinator | board | source of truth for tasks |
| `parse_report.py [--board] "<line>"` | coordinator | no | validates a report, prints the board command |
| `metrics.sh [--days N]` | anyone | no | cycle time per task, merges/day, reverts, lesson counts / recurrences / mean time to guard |

All tools exit 2 with a clear message when the chosen Python lacks pytest; this is never
reported as a test failure.

Frontend checks (LOOP-2) keep `node_modules` outside the repo, keyed by the lockfile hash:
`$ASTRO_NODE_CACHE` (default `~/.cache/astro-node-modules/<sha256>`). `npm ci` runs with
`--offline --ignore-scripts`: a lockfile whose packages are not in the local npm cache fails
loudly (run `npm ci` in `frontend/` once; new packages need approval first).

## 8. Lessons: the loop learns from every failure
`docs/ops/lessons.yaml` is the source of truth; `LESSONS.md` is rendered from it by
`tools/ops/lessons.py` (single writer: the coordinator, like the board).
- **Read first.** Every task starts by reading `docs/ops/LESSONS.md` (step 0 of every prompt).
- **Every failure becomes a lesson.** RED merge / revert → `merge_ready.sh` adds a stub (failing
  tests, branch, sha). A flaky seed → `stress.sh` calls `add_lesson_stub` (`_lib.sh`) with
  `SOURCE=stress KEY=flaky:<test id>`. A bug fix, review rejection or coordination mistake →
  the worker adds a `LESSON: <symptom> | <cause> | guard=<ref>` line under its report.
- **Same failure again = recurrence, not a new lesson.** Lessons carry a `key` (first failing
  test id, `flaky:<test>`, …); a recurrence reopens a closed lesson: its guard did not hold.
- **Closed means guarded.** `lessons.py close ID --guard REF` refuses unless REF exists:
  `test:<path>[::name]`, `config:<file>:<dotted.key>` or `rule:<prompt file>:<text>`.
  `tests/unit/test_ops_lessons.py` re-checks every closed guard and that LESSONS.md is current.
- **Measured.** `metrics.sh` prints lessons, open, closed, recurrences and mean time to guard.
