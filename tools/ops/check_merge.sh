#!/usr/bin/env bash
# check_merge.sh <branch>: read-only merge dry run against main.
#   1. git merge-tree --write-tree: conflict detection (no refs, no index touched)
#   2. warn on files changed outside the branch's owned paths (CLAUDE.md), and flag
#      changes there that are ONLY reformatting (L3: broad `ruff format <dir>`)
#   3. check out the merged tree in a detached scratch worktree, run pytest + ruff.
#      The scratch tree holds tracked files only, so untracked files never count (L1).
#   4. remove the scratch worktree (trap, also on Ctrl-C / failure)
# Exit: 0 MERGE OK · 1 conflict or checks failed · 2 usage error.
# Creates no commits and moves no branch. No network, no secrets.
# Env: BASE_BRANCH (default main), VENV (see _lib.sh).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

BR="${1:-}"
[[ -z "$BR" || "$BR" == "-h" || "$BR" == "--help" ]] && { sed -n 2,11p "$0"; exit 2; }
g rev-parse --verify -q "$BR^{commit}" >/dev/null || { echo "no such branch: $BR" >&2; exit 2; }
g rev-parse --verify -q "$BASE^{commit}" >/dev/null || { echo "no such base: $BASE" >&2; exit 2; }
pick_python

base_sha="$(g rev-parse --short "$BASE")"; br_sha="$(g rev-parse --short "$BR")"
ab="$(g rev-list --left-right --count "$BASE...$BR")"
behind="${ab%%[[:space:]]*}"; ahead="${ab##*[[:space:]]}"
echo "check $BR@$br_sha → $BASE@$base_sha  (+$ahead/-$behind)"
[[ "$ahead" -eq 0 ]] && { echo "NOTHING TO MERGE: $BR has no commits ahead of $BASE"; exit 0; }
[[ "$behind" -gt 3 ]] && echo "WARN  $behind commits behind $BASE: ask owner to rebase (PROTOCOL §2)"

# 1. conflicts
mt="$(g merge-tree --write-tree --name-only --no-messages "$BASE" "$BR" 2>&1)"; rc=$?
if [[ $rc -ne 0 ]]; then
  echo "CONFLICT in:"; printf '%s\n' "$mt" | tail -n +2 | sed '/^$/d; s/^/  /'
  echo "MERGE CONFLICT $BR: owner must 'git rebase $BASE' and resolve"
  exit 1
fi
tree="$(printf '%s\n' "$mt" | head -1)"

# 2. ownership (warning only; tests/ is shared). Mirrors CLAUDE.md "Folder ownership":
#    keep the two in step when ownership changes.
case "${BR#feat/}" in
  csi-core)  own='^(csi_core/)' ;;
  db-ingest) own='^(backend/db\.py|backend/models/|migrations/|alembic\.ini|backend/services/(ingestion|runs)\.py|tools/cli\.py|backend/api/v1/(sessions|jobs)\.py|backend/worker\.py)' ;;
  accounts)  own='^(backend/(security|deps|logging|errors)\.py|backend/services/accounts\.py|backend/api/v1/(auth|me)\.py|backend/static/|docs/ops/|tools/ops/)' ;;
  surveys)   own='^(seeds/|backend/services/(surveys|guidance|readouts)\.py|backend/api/v1/(instruments|responses|guidance|nights|today)\.py)' ;;
  pipeline)  own='^(backend/services/(pipeline|fusion|personas)\.py)' ;;
  ops)       own='^(docs/ops/|tools/ops/)' ;;
  *)         own='' ;;
esac
files="$(g diff --name-only "$BASE...$BR")"
echo "files: $(printf '%s\n' "$files" | sed '/^$/d' | wc -l | tr -d ' ') changed"
# reformat_only FILE: 0 when BR's version of FILE differs from BASE's only by formatting:
# whitespace for any file; for .py, BR's version equals `ruff format` of BASE's version.
reformat_only() {
  local f="$1" formatted
  g cat-file -e "$BASE:$f" 2>/dev/null && g cat-file -e "$BR:$f" 2>/dev/null || return 1
  if g diff --quiet -w --ignore-blank-lines "$BASE...$BR" -- "$f"; then return 0; fi
  [[ "$f" == *.py && ${#RUFF[@]} -gt 0 ]] || return 1
  formatted="$(cd "$REPO" && g show "$BASE:$f" | "${RUFF[@]}" format --stdin-filename "$f" - 2>/dev/null)" \
    || return 1
  [[ "$formatted" == "$(g show "$BR:$f")" ]]
}

if [[ -n "$own" ]]; then
  outside="$(printf '%s\n' "$files" | grep -vE "$own" || true)"
  reformatted=()
  while IFS= read -r f; do
    [[ -n "$f" ]] && reformat_only "$f" && reformatted+=("$f")
  done <<<"$outside"
  if [[ ${#reformatted[@]} -gt 0 ]]; then
    echo "WARN  reformat-only changes outside owned paths (L3: format only files you changed):"
    printf '%s\n' "${reformatted[@]}" | sed 's/^/  /'
  fi
  outside="$(printf '%s\n' "$outside" | grep -vE '^tests/' || true)"
  if [[ -n "$outside" ]]; then
    echo "WARN  outside owned paths (coordinator approval needed):"
    printf '%s\n' "$outside" | sed 's/^/  /'
  fi
fi

# 3. tests on the merged tree in a scratch worktree
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/astro-merge.XXXXXX")"
WT="$SCRATCH/wt"
cleanup() {
  g worktree remove --force "$WT" >/dev/null 2>&1
  rm -rf "$SCRATCH"
  g worktree prune >/dev/null 2>&1
}
trap cleanup EXIT INT TERM
g worktree add --quiet --detach "$WT" "$BASE" >/dev/null 2>&1 \
  || { echo "MERGE FAIL: cannot create scratch worktree"; exit 1; }
git -C "$WT" read-tree -u --reset "$tree" || { echo "MERGE FAIL: cannot check out merged tree"; exit 1; }

run_checks "$WT"
ok=1
if [[ "$T_RES" != pass* && "$T_RES" != none ]]; then ok=0; show_test_failure; fi
if [[ "$R_RES" == FAIL* ]]; then ok=0
  printf '%s\n' "$R_OUT" | grep -E ':[0-9]+:[0-9]+:' | head -10 | sed 's/^/  /'; fi

echo "tests=$T_RES (${T_SUMMARY:-no summary}) ruff=$R_RES python=$PY"
if [[ $ok -eq 1 ]]; then echo "MERGE OK $BR tree=${tree:0:7}"; exit 0
else echo "MERGE FAIL $BR: checks fail on the merged tree"; exit 1; fi
