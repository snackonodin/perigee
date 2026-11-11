#!/usr/bin/env bash
# status.sh: read-only team status. One line per worktree of this repo:
#   name  branch  last-commit(age)  ahead/behind main  dirty  tests  ruff  subject
# Usage: tools/ops/status.sh [--fast]     (--fast skips pytest and ruff)
# Read-only: no git writes, no network. pytest runs without its cache and
# without .pyc files; ruff runs with --no-cache.
set -uo pipefail

FAST=0
[[ "${1:-}" == "--fast" ]] && FAST=1
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { sed -n 2,6p "$0"; exit 0; }

VENV="${ASTRO_VENV:-$HOME/.venvs/astro-app}"
PY="$VENV/bin/python"; RUFF="$VENV/bin/ruff"
[[ -x "$PY" ]] || PY="$(command -v python3)"
[[ -x "$RUFF" ]] || RUFF="$(command -v ruff || true)"
BASE="${BASE_BRANCH:-main}"

export PYTHONDONTWRITEBYTECODE=1 NO_COLOR=1

run_checks() {  # $1 = worktree dir → prints "tests=… ruff=…"
  local dir="$1" out rc summary t r
  out="$(cd "$dir" && "$PY" -m pytest -p no:cacheprovider --no-header 2>&1)"; rc=$?
  summary="$(printf '%s\n' "$out" | grep -E '[0-9]+ (passed|failed|error)' | tail -1)"
  local p f e
  p="$(grep -oE '[0-9]+ passed' <<<"$summary" | grep -oE '[0-9]+' || true)"
  f="$(grep -oE '[0-9]+ failed' <<<"$summary" | grep -oE '[0-9]+' || true)"
  e="$(grep -oE '[0-9]+ errors?' <<<"$summary" | grep -oE '[0-9]+' || true)"
  if [[ $rc -eq 0 ]]; then t="pass(${p:-0})"
  elif [[ $rc -eq 5 ]]; then t="none"
  else t="FAIL(${f:-0}f/${e:-0}e/${p:-0}p)"; fi
  if [[ -z "$RUFF" ]]; then r="n/a"
  else
    local n
    n="$(cd "$dir" && "$RUFF" check . --no-cache --quiet --output-format concise 2>&1 | grep -c ':' )"
    if [[ "$n" -eq 0 ]]; then r="pass"; else r="FAIL($n)"; fi
  fi
  printf 'tests=%-14s ruff=%s' "$t" "$r"
}

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not in a git repo" >&2; exit 2; }
git -C "$ROOT" rev-parse --verify -q "$BASE" >/dev/null || { echo "no branch $BASE" >&2; exit 2; }

printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M')" "base=$BASE@$(git -C "$ROOT" rev-parse --short "$BASE")"

wt="" br=""
emit() {
  [[ -z "$wt" ]] && return
  local name sha age subj ab ahead behind dirty checks=""
  name="$(basename "$wt")"; [[ "$br" == "$BASE" ]] && name="main"
  if [[ ! -d "$wt" ]]; then printf '%-10s %-16s MISSING %s\n' "$name" "$br" "$wt"; return; fi
  sha="$(git -C "$wt" log -1 --format=%h)"
  age="$(git -C "$wt" log -1 --format=%cr | sed -E 's/ (seconds?|minutes?|hours?|days?|weeks?) ago/\1/; s/seconds?/s/; s/minutes?/m/; s/hours?/h/; s/days?/d/; s/weeks?/w/')"
  subj="$(git -C "$wt" log -1 --format=%s | cut -c1-40)"
  ab="$(git -C "$wt" rev-list --left-right --count "$BASE"...HEAD 2>/dev/null)"
  behind="${ab%%[[:space:]]*}"; ahead="${ab##*[[:space:]]}"
  dirty="$(git -C "$wt" status --porcelain 2>/dev/null | grep -vc '__pycache__' || true)"
  [[ "$dirty" -gt 0 ]] && dirty="dirty($dirty)" || dirty="clean"
  [[ $FAST -eq 0 ]] && checks="$(run_checks "$wt")"
  printf '%-10s %-16s %s %-4s +%s/-%s %-9s %s "%s"\n' \
    "$name" "${br:-detached}" "$sha" "$age" "${ahead:-?}" "${behind:-?}" "$dirty" "$checks" "$subj"
}

while IFS= read -r line; do
  case "$line" in
    "worktree "*) emit; wt="${line#worktree }"; br="" ;;
    "branch "*)   br="${line#branch refs/heads/}" ;;
    "")           emit; wt="" ;;
  esac
done < <(git -C "$ROOT" worktree list --porcelain; echo)
