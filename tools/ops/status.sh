#!/usr/bin/env bash
# status.sh: read-only team status. One line per worktree of this repo:
#   name  branch  last-commit(age)  ahead/behind main  dirty  tests  ruff  subject
# Usage: tools/ops/status.sh [--fast]     (--fast skips pytest and ruff)
# Read-only: no git writes, no network. pytest runs without its cache and
# without .pyc files; ruff runs with --no-cache. Python: see _lib.sh.
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

FAST=0
case "${1:-}" in
  --fast) FAST=1 ;;
  -h|--help) sed -n 2,6p "$0"; exit 0 ;;
esac
[[ $FAST -eq 0 ]] && pick_python
g rev-parse --verify -q "$BASE" >/dev/null || { echo "no branch $BASE" >&2; exit 2; }

printf '%s base=%s@%s\n' "$(date '+%Y-%m-%d %H:%M')" "$BASE" "$(g rev-parse --short "$BASE")"

wt="" br=""
emit() {
  [[ -z "$wt" ]] && return
  local name sha age subj ab ahead behind dirty checks=""
  name="$(basename "$wt")"; [[ "$br" == "$BASE" ]] && name="$BASE"
  if [[ ! -d "$wt" ]]; then printf '%-10s %-16s MISSING\n' "$name" "$br"; return; fi
  sha="$(git -C "$wt" log -1 --format=%h)"
  age="$(git -C "$wt" log -1 --format=%cr | sed -E 's/ ago$//; s/ seconds?/s/; s/ minutes?/m/; s/ hours?/h/; s/ days?/d/; s/ weeks?/w/; s/ months?/mo/')"
  subj="$(git -C "$wt" log -1 --format=%s | cut -c1-40)"
  ab="$(git -C "$wt" rev-list --left-right --count "$BASE"...HEAD 2>/dev/null)"
  behind="${ab%%[[:space:]]*}"; ahead="${ab##*[[:space:]]}"
  dirty="$(git -C "$wt" status --porcelain 2>/dev/null | grep -c . || true)"
  [[ "$dirty" -gt 0 ]] && dirty="dirty($dirty)" || dirty="clean"
  if [[ $FAST -eq 0 ]]; then
    run_checks "$wt"; checks="$(printf 'tests=%-14s ruff=%-8s' "$T_RES" "$R_RES")"
  fi
  printf '%-10s %-16s %s %-4s +%s/-%s %-9s %s"%s"\n' \
    "$name" "${br:-detached}" "$sha" "$age" "${ahead:-?}" "${behind:-?}" "$dirty" \
    "${checks:+$checks }" "$subj"
}

while IFS= read -r line; do
  case "$line" in
    "worktree "*) emit; wt="${line#worktree }"; br="" ;;
    "branch "*)   br="${line#branch refs/heads/}" ;;
    "")           emit; wt="" ;;
  esac
done < <(g worktree list --porcelain; echo)
