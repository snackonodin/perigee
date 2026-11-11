#!/usr/bin/env bash
# stress.sh: hunt order dependence and flaky tests (QA-1, lesson L2).
# Usage: tools/ops/stress.sh [-n N] [-- extra pytest args]
#   1. N full runs in random order (pytest-randomly), each with a fresh seed (default N=10)
#   2. one run in REVERSED collection order (tools/ops/pytest_reverse.py)
#   3. one run in fixed order (-p no:randomly)
# Prints one line per run (label, seed, result). For every failure it prints the failing
# tests and the exact command that reproduces that run. Exit 0 only if every run passed.
# Full logs go to $STRESS_LOG_DIR, or to a new temp dir (printed at the start).
# Extra args after -- go to every run, e.g.  tools/ops/stress.sh -n 3 -- -m "not slow"
# Python: see _lib.sh (VENV, active venv, <repo>/.venv, ...).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

N=10
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n) N="${2:?-n needs a number}"; shift 2 ;;
    --) shift; EXTRA=("$@"); break ;;
    -h|--help) sed -n 2,12p "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done
[[ "$N" =~ ^[0-9]+$ ]] || { echo "-n must be a non-negative integer" >&2; exit 2; }

pick_python
if ! "$PY" -c 'import pytest_randomly' >/dev/null 2>&1; then
  echo "ERROR: pytest-randomly is not installed in $PY (pip install -r requirements.txt)" >&2
  exit 2
fi

LOG_DIR="${STRESS_LOG_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/astro-stress.XXXXXX")}"
mkdir -p "$LOG_DIR"
echo "stress: $N random + reversed + fixed runs on $(g rev-parse --short HEAD); logs in $LOG_DIR"

BASE_ARGS=(-m pytest -p no:cacheprovider -rfE)
FAILED_RUNS=0
REPROS=()

quote() { printf '%q ' "$@"; }

# run_one LABEL SEED_TEXT ARGS... : one full pytest run, result line, repro on failure
run_one() {
  local label="$1" seed_text="$2"; shift 2
  local log="$LOG_DIR/$label.log" rc summary start end
  start=$(date +%s)
  (cd "$REPO" && "$PY" "${BASE_ARGS[@]}" "$@" ${EXTRA[@]+"${EXTRA[@]}"}) >"$log" 2>&1
  rc=$?
  end=$(date +%s)
  summary="$(grep -E '[0-9]+ (passed|failed|errors?)' "$log" | tail -1 | sed -E 's/^=+ //; s/ =+$//')"
  if [[ $rc -eq 0 ]]; then
    printf '%-10s %-22s PASS  %s (%ss)\n' "$label" "$seed_text" "${summary:-?}" $((end - start))
  else
    FAILED_RUNS=$((FAILED_RUNS + 1))
    printf '%-10s %-22s FAIL  rc=%s %s (%ss)\n' "$label" "$seed_text" "$rc" \
      "${summary:-no summary}" $((end - start))
    grep -E '^(FAILED|ERROR) ' "$log" | head -15 | sed 's/^/    /'
    local repro
    repro="cd $(quote "$REPO")&& $(quote "$PY" "${BASE_ARGS[@]}" "$@" ${EXTRA[@]+"${EXTRA[@]}"})"
    echo "    reproduce: $repro"
    echo "    log:       $log"
    REPROS+=("$label: $repro")
    record_lessons "$label" "$seed_text" "$log"
  fi
}

# record_lessons LABEL SEED_TEXT LOG: one lesson stub per failing test (LOOP-1 helper from
# _lib.sh). Guarded so stress.sh works before LOOP-1 lands; a helper error never changes
# the stress result.
record_lessons() {
  type add_lesson_stub >/dev/null 2>&1 || return 0
  local label="$1" seed_text="$2" log="$3" main br sha line tid
  local -a lines=()
  main="$(main_worktree)"; [[ -n "$main" ]] || main="$REPO"
  br="$(g rev-parse --abbrev-ref HEAD)"; sha="$(g rev-parse --short HEAD)"
  while IFS= read -r line; do lines+=("$line"); done \
    < <(grep -E '^(FAILED|ERROR) ' "$log" | head -15)
  for line in ${lines[@]+"${lines[@]}"}; do
    tid="$(awk '{print $2}' <<<"$line")"
    add_lesson_stub "$main/docs/ops/lessons.yaml" stress "tools/ops/stress.sh $label" \
      "$tid failed under $seed_text" "$br" "$sha" "flaky:$tid" "${lines[@]}" \
      || echo "    (add_lesson_stub failed; stress result unchanged)" >&2
  done
}

for ((i = 1; i <= N; i++)); do
  seed="$("$PY" -c 'import secrets; print(secrets.randbelow(2**32))')"
  run_one "random-$i" "seed=$seed" -p randomly --randomly-seed="$seed"
done
run_one "reversed" "order=reversed" -p no:randomly -p tools.ops.pytest_reverse
run_one "fixed" "order=fixed" -p no:randomly

echo
if [[ $FAILED_RUNS -eq 0 ]]; then
  echo "stress: all $((N + 2)) runs passed"
  exit 0
fi
echo "stress: $FAILED_RUNS of $((N + 2)) runs FAILED. Reproduce with:"
printf '  %s\n' "${REPROS[@]}"
exit 1
