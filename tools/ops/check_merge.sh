#!/usr/bin/env bash
# check_merge.sh <branch>: read-only merge dry run against main.
#   1. git merge-tree --write-tree: conflict detection (no refs, no index touched)
#   2. warn on files changed outside the branch's owned paths (CLAUDE.md)
#   3. check out the merged tree in a detached scratch worktree, run pytest + ruff
#   4. remove the scratch worktree (trap, also on Ctrl-C / failure)
# Exit: 0 MERGE OK · 1 conflict or checks failed · 2 usage error.
# Creates no commits and moves no branch. No network, no secrets.
# Env: BASE_BRANCH (default main), ASTRO_VENV (default ~/.venvs/astro-app).
set -uo pipefail

BR="${1:-}"
[[ -z "$BR" || "$BR" == "-h" || "$BR" == "--help" ]] && { sed -n 2,9p "$0"; exit 2; }
BASE="${BASE_BRANCH:-main}"
VENV="${ASTRO_VENV:-$HOME/.venvs/astro-app}"
PY="$VENV/bin/python"; RUFF="$VENV/bin/ruff"
[[ -x "$PY" ]] || PY="$(command -v python3)"
[[ -x "$RUFF" ]] || RUFF="$(command -v ruff || true)"
export PYTHONDONTWRITEBYTECODE=1 NO_COLOR=1

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not in a git repo" >&2; exit 2; }
g() { git -C "$ROOT" "$@"; }
g rev-parse --verify -q "$BR^{commit}" >/dev/null || { echo "no such branch: $BR" >&2; exit 2; }
g rev-parse --verify -q "$BASE^{commit}" >/dev/null || { echo "no such base: $BASE" >&2; exit 2; }

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

# 2. ownership (warning only; tests/ is shared)
case "${BR#feat/}" in
  csi-core)  own='^(csi_core/)' ;;
  db-ingest) own='^(backend/db\.py|backend/models/|migrations/|alembic\.ini|backend/services/(ingestion|runs)\.py|tools/cli\.py)' ;;
  accounts)  own='^(backend/security\.py|backend/deps\.py|backend/services/accounts\.py|backend/api/v1/(auth|me)\.py)' ;;
  surveys)   own='^(seeds/|backend/services/(surveys|guidance)\.py|backend/api/v1/responses\.py)' ;;
  ops)       own='^(docs/ops/|tools/ops/)' ;;
  *)         own='' ;;
esac
files="$(g diff --name-only "$BASE...$BR")"
echo "files: $(printf '%s\n' "$files" | sed '/^$/d' | wc -l | tr -d ' ') changed"
if [[ -n "$own" ]]; then
  outside="$(printf '%s\n' "$files" | grep -vE "$own" | grep -vE '^tests/' || true)"
  [[ -n "$outside" ]] && { echo "WARN  outside owned paths (coordinator approval needed):"; printf '  %s\n' $outside; }
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
g worktree add --quiet --detach "$WT" "$BASE" >/dev/null 2>&1 || { echo "MERGE FAIL: cannot create scratch worktree"; exit 1; }
git -C "$WT" read-tree -u --reset "$tree" || { echo "MERGE FAIL: cannot check out merged tree"; exit 1; }

out="$(cd "$WT" && "$PY" -m pytest -p no:cacheprovider --no-header 2>&1)"; trc=$?
summary="$(printf '%s\n' "$out" | grep -E '[0-9]+ (passed|failed|error)' | tail -1)"
rout=""; rrc=0
if [[ -n "$RUFF" ]]; then rout="$(cd "$WT" && "$RUFF" check . --no-cache --output-format concise 2>&1)"; rrc=$?; fi

ok=1
if [[ $trc -eq 0 ]]; then tres="pass"; else tres="FAIL"; ok=0
  printf '%s\n' "$out" | grep -E '^(FAILED|ERROR) ' | head -10 | sed 's/^/  /'; fi
if [[ -z "$RUFF" ]]; then rres="n/a"; elif [[ $rrc -eq 0 ]]; then rres="pass"; else rres="FAIL"; ok=0
  printf '%s\n' "$rout" | grep ':' | head -10 | sed 's/^/  /'; fi

echo "tests=$tres (${summary:-no summary}) ruff=$rres"
if [[ $ok -eq 1 ]]; then echo "MERGE OK $BR tree=${tree:0:7}"; exit 0
else echo "MERGE FAIL $BR: checks fail on the merged tree"; exit 1; fi
