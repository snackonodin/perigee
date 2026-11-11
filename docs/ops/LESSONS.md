# Lessons: what failed, why, and the guard that stops it recurring

The loop learns from failure. Every RED merge, revert, flaky test, review rejection or
coordination mistake gets one entry here. An entry is not closed until its **guard** exists
(a test, a script check, a config exclusion or a prompt rule). Every worker reads this file
before starting each task (see docs/ops/prompts/*.md).

Format: `L<n> | date | where it surfaced | symptom | root cause | guard (file/test) | status`

| ID | Date | Surfaced in | Symptom | Root cause | Guard | Status |
|---|---|---|---|---|---|---|
| L1 | 2026-11-11 | merge_ready (PIPE-4) | Merge auto-reverted: tests 460 pass, ruff 124 errors | Untracked `features script/` folder in main was linted as app code | pyproject `extend-exclude`, `norecursedirs`, `.gitignore`; check_merge should lint only tracked files | guard in place; tooling TODO (LOOP-1) |
| L2 | 2026-11-11 | b0 DB-6, cf, coordinator | "1 failed" appears once in ~5 full runs, never reproducible | Order dependence: lazy `_load_builtins()` imports re-register handlers over monkeypatched `runs._HANDLERS` | RUN_KINDS + `setdefault`; conftest imports builtins up front; random-order runs (QA-1) | partly guarded; QA-1 hunts remaining |
| L3 | 2026-11-11 | f4, cf, 7a (3 times) | Other teams' files reformatted in a worktree | Broad `ruff format <dir>` over shared paths | Rule: format only files you changed (`ruff format $(git diff --name-only)`); check_merge warns on out-of-ownership paths | rule; tooling TODO |
| L4 | 2026-11-11 | coordinator → 7a | Bug report about relative raw_path was wrong | Coordinator inferred behaviour without reading the code | Rule: reproduce or cite file:line before filing a bug to a worker | rule |
| L5 | 2026-11-11 | merge_ready (DB-8) | FK IntegrityError in another team's test | New fallback copied a non-user id from params into an FK column | Fallback only if the referenced row exists; test with bogus id | guarded (ab4e738) |
| L6 | 2026-11-11 | f4 PIPE-4 | Backfilled nights saw surveys answered later that week | `weekly_indices(week_start)` has no upper time bound | `weekly_indices(..., until=)` (LEAK-1) | open |
| L7 | 2026-11-11 | f4 PIPE-4 | Steady persona flagged on normal nights | Small-n MAD too narrow + FR13 excludes flagged nights → baseline ratchets narrower | `baseline.mad_floor` (config) + persona calibration test | guarded |
| L8 | 2026-11-11 | coordinator | Ran `git rebase` inside a worker's worktree | Coordinator used worker tree to test a merge | Rule: coordinator tests merges only in scratch worktrees (check_merge.sh) | rule |
| L9 | 2026-11-11 | coordinator | pytest failure hidden: `pytest | tail -1 && next` continued | Pipe masks exit code | Rule: use `set -o pipefail` or check `${PIPESTATUS[0]}`; merge_ready already does | rule |
| L10 | 2026-11-11 | ops session | Session ended at usage limit; messages to its socket failed | Single owner for a whole workstream | Board rows are owner-reassignable; prompts are self-contained so any session can resume a row | rule |
