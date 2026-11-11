# _lib.sh: shared helpers for tools/ops/*.sh (source it, do not run it).
# Everything resolves relative to this repo: no machine-specific paths.
#   OPS_DIR  this directory          REPO  toplevel of the worktree holding OPS_DIR
#   BASE     base branch ($BASE_BRANCH, default main)
#   PY       python: $VENV, then active $VIRTUAL_ENV, then <repo>/.venv,
#            then <main worktree>/.venv, then python3 on PATH
#   RUFF     command array for ruff (venv module, else ruff on PATH; empty if none)

OPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(git -C "$OPS_DIR" rev-parse --show-toplevel 2>/dev/null)" \
  || { echo "tools/ops must live inside a git repo" >&2; exit 2; }
BASE="${BASE_BRANCH:-main}"
export PYTHONDONTWRITEBYTECODE=1 NO_COLOR=1

g() { git -C "$REPO" "$@"; }

# Path of the worktree that has $BASE checked out (empty if none).
main_worktree() {
  g worktree list --porcelain | awk -v b="branch refs/heads/$BASE" '
    /^worktree /{w=substr($0,10)} $0==b{print w; exit}'
}

pick_python() {
  local c mw
  mw="$(main_worktree)"
  for c in "${VENV:-}" "${VIRTUAL_ENV:-}" "$REPO/.venv" "${mw:+$mw/.venv}"; do
    if [[ -n "$c" && -x "$c/bin/python" ]]; then PY="$c/bin/python"; break; fi
  done
  [[ -n "${PY:-}" ]] || PY="$(command -v python3 || true)"
  [[ -n "$PY" ]] || { echo "no python found: set VENV" >&2; exit 2; }
  if "$PY" -m ruff --version >/dev/null 2>&1; then RUFF=("$PY" -m ruff)
  elif command -v ruff >/dev/null 2>&1; then RUFF=(ruff)
  else RUFF=(); fi
}

# run_checks DIR → sets T_RES (pass(N)|none|FAIL(...)), T_OUT, R_RES (pass|FAIL(N)|n/a), R_OUT
run_checks() {
  local dir="$1" rc summary p f e
  T_OUT="$(cd "$dir" && "$PY" -m pytest -p no:cacheprovider --no-header 2>&1)"; rc=$?
  summary="$(printf '%s\n' "$T_OUT" | grep -E '[0-9]+ (passed|failed|error)' | tail -1)"
  T_SUMMARY="$summary"
  p="$(grep -oE '[0-9]+ passed' <<<"$summary" | grep -oE '[0-9]+' || true)"
  f="$(grep -oE '[0-9]+ failed' <<<"$summary" | grep -oE '[0-9]+' || true)"
  e="$(grep -oE '[0-9]+ errors?' <<<"$summary" | grep -oE '[0-9]+' || true)"
  if [[ $rc -eq 0 ]]; then T_RES="pass(${p:-0})"
  elif [[ $rc -eq 5 ]]; then T_RES="none"
  else T_RES="FAIL(${f:-0}f/${e:-0}e/${p:-0}p)"; fi
  if [[ ${#RUFF[@]} -eq 0 ]]; then R_RES="n/a"; R_OUT=""; return; fi
  R_OUT="$(cd "$dir" && "${RUFF[@]}" check . --no-cache --output-format concise 2>&1)"; rc=$?
  if [[ $rc -eq 0 ]]; then R_RES="pass"
  else R_RES="FAIL($(printf '%s\n' "$R_OUT" | grep -cE '^[^ ].*:[0-9]+:[0-9]+:'))"; fi
}
