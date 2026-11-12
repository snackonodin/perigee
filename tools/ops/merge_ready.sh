#!/usr/bin/env bash
# merge_ready.sh <branch> [ID ...]: COORDINATOR ONLY. Writes to main.
#   0. refuse if the main worktree is dirty or the branch has nothing to merge
#   1. tools/ops/check_merge.sh <branch> must print MERGE OK
#   2. git merge --no-ff <branch> in the main worktree
#   3. pytest + ruff on the merge commit, in a scratch checkout (tracked files only, L1);
#      if the merge touches frontend/, also npm ci (offline) + tsc + vitest (LOOP-2)
#      red   → git revert -m 1 automatically, board rows → doing, a lesson stub with the
#              failing tests, branch and sha (docs/ops/lessons.yaml; same failure again =
#              recurrence), exit 1 with failing tests
#      green → board rows → done (sha = merge commit), render BOARD.md, commit the board,
#              print the "main moved to <sha>, rebase" broadcast and who to send it to
# IDs default to the board rows on <branch> in state `review`.
# Exit: 0 merged · 1 refused / red (reverted) · 2 usage or environment error.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

BR="${1:-}"
[[ -z "$BR" || "$BR" == "-h" || "$BR" == "--help" ]] && { sed -n 2,15p "$0"; exit 2; }
shift; IDS=("$@")
pick_python

MAIN="$(main_worktree)"
[[ -n "$MAIN" ]] || { echo "REFUSE: no worktree has $BASE checked out" >&2; exit 2; }
m() { git -C "$MAIN" "$@"; }
g rev-parse --verify -q "$BR^{commit}" >/dev/null || { echo "no such branch: $BR" >&2; exit 2; }

dirty="$(m status --porcelain)"
if [[ -n "$dirty" ]]; then
  echo "REFUSE: $BASE working tree is dirty; commit or clean it first:"
  printf '%s\n' "$dirty" | head -10 | sed 's/^/  /'
  exit 1
fi
ahead="$(g rev-list --count "$BASE..$BR")"
[[ "$ahead" -gt 0 ]] || { echo "REFUSE: $BR has nothing to merge into $BASE"; exit 1; }

BOARD_FILE="$MAIN/docs/ops/board.yaml"
board() { "$PY" "$OPS_DIR/board.py" --file "$BOARD_FILE" "$@"; }
HAVE_BOARD=0; [[ -f "$BOARD_FILE" ]] && HAVE_BOARD=1
if [[ $HAVE_BOARD -eq 1 && ${#IDS[@]} -eq 0 ]]; then
  while IFS=$'\t' read -r id _state _owner branch _rest; do
    [[ "$branch" == "$BR" ]] && IDS+=("$id")
  done < <(board list --state review --format tsv)
fi
label="${IDS[*]:-no board IDs}"

# 1. dry run
echo "== check_merge $BR"
"$OPS_DIR/check_merge.sh" "$BR" || { echo "REFUSE: check_merge failed; nothing merged"; exit 1; }

# 2. merge
echo "== merge $BR into $BASE ($label)"
if ! m merge --no-ff --no-edit -m "Merge $BR ($label)" "$BR" >/dev/null; then
  m merge --abort >/dev/null 2>&1
  echo "REFUSE: merge failed in $MAIN; aborted, $BASE unchanged"; exit 1
fi
merge_sha="$(m rev-parse --short HEAD)"

commit_board() {  # $1 = state, $2 = sha or "", $3 = message
  [[ $HAVE_BOARD -eq 1 && ${#IDS[@]} -gt 0 ]] || return 0
  local id
  for id in "${IDS[@]}"; do board move "$id" "$1" ${2:+--sha "$2"} >/dev/null || return 1; done
  board render >/dev/null && m add docs/ops/board.yaml docs/ops/BOARD.md \
    && m commit -q -m "$3" >/dev/null
}

# 3. verify on main
echo "== pytest + ruff on $BASE@$merge_sha (scratch checkout: tracked files only)"
CHECK_FRONTEND=0
frontend_touched "$merge_sha^1" "$merge_sha" && CHECK_FRONTEND=1
CHECK_FRONTEND=$CHECK_FRONTEND checks_in_scratch "$merge_sha"
if [[ "$T_RES" != pass* && "$T_RES" != none || "$R_RES" == FAIL* || "$F_RES" == FAIL* ]]; then
  echo "RED: tests=$T_RES ruff=$R_RES frontend=$F_RES. Reverting $merge_sha"
  show_test_failure
  [[ "$F_RES" == FAIL* ]] && show_frontend_failure
  printf '%s\n' "$R_OUT" | grep -E ':[0-9]+:[0-9]+:' | head -10 | sed 's/^/  /'
  if ! m revert -m 1 --no-edit HEAD >/dev/null; then
    echo "REVERT FAILED: fix $BASE by hand NOW (git -C <main> revert -m 1 $merge_sha)"; exit 2
  fi
  commit_board doing "" "board: $label → doing (merge $merge_sha reverted)" \
    || echo "WARN board not updated"
  rev_sha="$(m log -1 --format=%h --grep='^Revert ' 2>/dev/null)"
  LESSONS_FILE="$MAIN/docs/ops/lessons.yaml"
  if [[ -f "$LESSONS_FILE" ]]; then
    fails=()
    while IFS= read -r l; do [[ -n "$l" ]] && fails+=("$l"); done < <(failing_lines)
    if add_lesson_stub "$LESSONS_FILE" merge_ready "merge_ready ($label)" \
        "RED after merging $BR: tests=$T_RES ruff=$R_RES frontend=$F_RES; merge $merge_sha reverted" \
        "$BR" "$merge_sha" "$(lesson_key)" ${fails[@]+"${fails[@]}"} \
      && m add docs/ops/lessons.yaml docs/ops/LESSONS.md \
      && m commit -q -m "lessons: stub for reverted merge of $BR ($merge_sha)" >/dev/null; then
      echo "LESSON: stub added in docs/ops/lessons.yaml; fill in cause + guard, then lessons.py close"
    else
      echo "WARN lesson stub not recorded: add it by hand (tools/ops/lessons.py add)"
    fi
  fi
  echo "REVERTED: $BASE at $(m rev-parse --short HEAD). Send the owner of $BR the failing tests and:"
  echo "  git rebase $BASE && git revert --no-edit $rev_sha   # re-apply your work (git won't re-merge reverted commits)"
  echo "  then fix, commit, pytest + ruff, report review again"
  exit 1
fi

if ! commit_board done "$merge_sha" "board: $label → done ($merge_sha)"; then
  echo "WARN merged and green, but the board update failed: run board.py move by hand"
fi
new_sha="$(m rev-parse --short HEAD)"
echo "MERGED $BR → $BASE@$merge_sha tests=$T_RES ruff=$R_RES frontend=$F_RES"

# who needs to rebase: every owner branch with commits not on main
to=()
if [[ $HAVE_BOARD -eq 1 ]]; then
  while IFS=$'\t' read -r _id sess obr; do
    [[ -z "$obr" || "$obr" == "$BASE" ]] && continue
    g rev-parse --verify -q "$obr" >/dev/null || continue
    [[ "$(g rev-list --count "$BASE..$obr")" -gt 0 ]] && to+=("$sess")
  done < <(board owners)
fi
echo "BROADCAST: main moved to $new_sha, rebase"
echo "SEND TO: ${to[*]:-(no unmerged branches)}"
