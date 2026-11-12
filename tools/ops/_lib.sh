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
  [[ -n "$PY" ]] || { echo "ERROR: no python found; set VENV=<your venv>" >&2; exit 2; }
  if ! "$PY" -c 'import pytest' >/dev/null 2>&1; then
    echo "ERROR: $PY has no pytest: it is not the project venv." >&2
    echo "  Set VENV=<venv dir> (or activate it, or create <repo>/.venv with scripts/bootstrap.sh)." >&2
    exit 2
  fi
  if "$PY" -m ruff --version >/dev/null 2>&1; then RUFF=("$PY" -m ruff)
  elif command -v ruff >/dev/null 2>&1; then RUFF=(ruff)
  else RUFF=(); fi
}

# run_checks DIR → sets T_RES (pass(N)|none|FAIL(...)|ERROR(no summary)), T_OUT, T_SUMMARY,
#                    R_RES (pass|FAIL(N)|n/a), R_OUT
# show_test_failure: prints FAILED/ERROR lines, or the last 20 lines when there is no summary.
run_checks() {
  local dir="$1" rc summary p f e
  T_OUT="$(cd "$dir" && "$PY" -m pytest -p no:cacheprovider --no-header 2>&1)"; rc=$?
  summary="$(printf '%s\n' "$T_OUT" | grep -E '[0-9]+ (passed|failed|error)' | tail -1 | sed -E 's/^=+ //; s/ =+$//')"
  T_SUMMARY="$summary"
  p="$(grep -oE '[0-9]+ passed' <<<"$summary" | grep -oE '[0-9]+' || true)"
  f="$(grep -oE '[0-9]+ failed' <<<"$summary" | grep -oE '[0-9]+' || true)"
  e="$(grep -oE '[0-9]+ errors?' <<<"$summary" | grep -oE '[0-9]+' || true)"
  if [[ $rc -eq 0 ]]; then T_RES="pass(${p:-0})"
  elif [[ $rc -eq 5 ]]; then T_RES="none"
  elif [[ -z "$summary" ]]; then T_RES="ERROR(no summary)"
  else T_RES="FAIL(${f:-0}f/${e:-0}e/${p:-0}p)"; fi
  if [[ ${#RUFF[@]} -eq 0 ]]; then R_RES="n/a"; R_OUT=""; return; fi
  R_OUT="$(cd "$dir" && "${RUFF[@]}" check . --no-cache --output-format concise 2>&1)"; rc=$?
  if [[ $rc -eq 0 ]]; then R_RES="pass"
  else R_RES="FAIL($(printf '%s\n' "$R_OUT" | grep -cE '^[^ ].*:[0-9]+:[0-9]+:'))"; fi
}

show_test_failure() {
  if [[ -z "${T_SUMMARY:-}" ]]; then
    echo "  pytest printed no summary; last 20 lines (python: $PY):"
    printf '%s\n' "$T_OUT" | tail -20 | sed 's/^/  | /'
  else
    printf '%s\n' "$T_OUT" | grep -E '^(FAILED|ERROR) ' | head -15 | sed 's/^/  /'
  fi
}

# checks_in_scratch REF: run_checks on a detached scratch worktree of REF, so only TRACKED
# files are tested and linted (L1: an untracked folder in main once failed ruff and
# auto-reverted a good merge). Sets the same variables as run_checks. Returns 1 when no
# scratch worktree could be made (T_RES=ERROR(...)).
checks_in_scratch() {
  local ref="$1" scratch wt
  scratch="$(mktemp -d "${TMPDIR:-/tmp}/astro-check.XXXXXX")"; wt="$scratch/wt"
  if ! g worktree add --quiet --detach "$wt" "$ref" >/dev/null 2>&1; then
    rm -rf "$scratch"
    T_RES="ERROR(no scratch worktree)"; T_SUMMARY=""; T_OUT=""; R_RES="n/a"; R_OUT=""
    return 1
  fi
  run_checks "$wt"
  F_RES="n/a"; F_OUT=""
  if [[ "${CHECK_FRONTEND:-0}" == 1 ]]; then frontend_checks "$wt"; fi
  g worktree remove --force "$wt" >/dev/null 2>&1
  rm -rf "$scratch"
  g worktree prune >/dev/null 2>&1
  return 0
}

# failing_lines: FAILED/ERROR test lines and ruff findings from the last run_checks.
failing_lines() {
  { printf '%s\n' "${T_OUT:-}" | grep -E '^(FAILED|ERROR) ' | head -15
    printf '%s\n' "${R_OUT:-}" | grep -E ':[0-9]+:[0-9]+:' | head -10
    [[ "${F_RES:-}" == FAIL* ]] && printf '%s\n' "${F_OUT:-}" \
      | grep -E 'error TS|FAIL |npm ci --offline failed' | head -10; } | sed 's/ - .*//; s/^[[:space:]]*//'
}

# add_lesson_stub FILE SOURCE SURFACED SYMPTOM BRANCH SHA KEY [FAILING LINE ...]
# Adds an open lesson to FILE (docs/ops/lessons.yaml) and renders LESSONS.md; a lesson with
# the same KEY gets a recurrence instead. No-op when FILE does not exist. stress.sh (QA-1)
# calls this for a flaky seed: SOURCE=stress, KEY=flaky:<test node id>.
add_lesson_stub() {
  local file="$1" src="$2" surfaced="$3" symptom="$4" br="$5" sha="$6" key="$7"
  shift 7
  [[ -f "$file" ]] || return 0
  "$PY" "$OPS_DIR/lessons.py" --file "$file" add --source "$src" --surfaced "$surfaced" \
    --symptom "$symptom" ${br:+--branch "$br"} ${sha:+--sha "$sha"} ${key:+--key "$key"} \
    --failing "$@"
}

# lesson_key: stable key for the last failure (first failing test id, else first ruff file).
lesson_key() {
  local t r
  t="$(printf '%s\n' "${T_OUT:-}" | grep -E '^(FAILED|ERROR) ' | head -1 | awk '{print $2}')"
  if [[ -n "$t" ]]; then echo "red:$t"; return; fi
  r="$(printf '%s\n' "${R_OUT:-}" | grep -E ':[0-9]+:[0-9]+:' | head -1 | cut -d: -f1)"
  if [[ -n "$r" ]]; then echo "red:ruff:$r"; return; fi
  if [[ "${F_RES:-}" == FAIL* ]]; then
    local tool="${F_RES#FAIL(}"; tool="${tool%)}"; tool="${tool// /-}"
    r="$(printf '%s\n' "${F_OUT:-}" | grep -oE 'src/[A-Za-z0-9_./-]+\.tsx?' | head -1)"
    echo "red:frontend:$tool${r:+:$r}"; return
  fi
  echo ""
}

# ---------------------------------------------------------------- frontend (LOOP-2)
# frontend_checks DIR: npm ci (lockfile, --ignore-scripts, --offline: local npm cache only,
# no network) + `tsc --noEmit` + `vitest run` for DIR/frontend. node_modules lives OUTSIDE
# the repo, keyed by the lockfile's sha256: $ASTRO_NODE_CACHE (default
# ~/.cache/astro-node-modules)/<hash>/node_modules, symlinked into DIR/frontend.
# Sets F_RES (n/a | pass | FAIL(npm ci|tsc|vitest)), F_OUT. NPM / NPX override the binaries.
NPM="${NPM:-npm}"
NPX="${NPX:-npx}"

node_cache_root() { echo "${ASTRO_NODE_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/astro-node-modules}"; }

lock_hash() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else sha256sum "$1" | awk '{print $1}'; fi
}

frontend_checks() {
  local fe="$1/frontend" cache tmp out
  F_RES="n/a"; F_OUT=""
  [[ -f "$fe/package-lock.json" ]] || return 0
  cache="$(node_cache_root)/$(lock_hash "$fe/package-lock.json")"
  if [[ ! -d "$cache/node_modules" ]]; then
    mkdir -p "$(node_cache_root)"
    tmp="$(mktemp -d "$(node_cache_root)/.build.XXXXXX")"
    cp "$fe/package.json" "$fe/package-lock.json" "$tmp/"
    [[ -f "$fe/.npmrc" ]] && cp "$fe/.npmrc" "$tmp/"
    if ! out="$(cd "$tmp" && "$NPM" ci --ignore-scripts --offline --no-audit --no-fund 2>&1)"; then
      rm -rf "$tmp"
      F_RES="FAIL(npm ci)"
      F_OUT="$out"$'\n'"npm ci --offline failed: packages missing from the local npm cache? Run \`npm ci\` in frontend/ once (new packages need approval first)."
      return 1
    fi
    mv "$tmp" "$cache" 2>/dev/null || rm -rf "$tmp"  # another run won the race: use theirs
  fi
  rm -rf "$fe/node_modules"
  ln -s "$cache/node_modules" "$fe/node_modules"
  if ! out="$(cd "$fe" && "$NPX" --no-install tsc --noEmit 2>&1)"; then
    F_RES="FAIL(tsc)"; F_OUT="$out"; return 1
  fi
  if ! out="$(cd "$fe" && "$NPX" --no-install vitest run 2>&1)"; then
    F_RES="FAIL(vitest)"; F_OUT="$out"; return 1
  fi
  F_RES="pass"; F_OUT="$out"
  return 0
}

# frontend_touched BASE_REF HEAD_REF: 0 when the diff between them touches frontend/.
frontend_touched() { g diff --name-only "$1" "$2" -- frontend/ | grep -q .; }

show_frontend_failure() {
  printf '%s\n' "${F_OUT:-}" | grep -E 'error TS|FAIL |✗|×|npm (ERR|error)|npm ci --offline failed' \
    | head -15 | sed 's/^/  /'
}
