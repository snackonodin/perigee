#!/usr/bin/env bash
# metrics.sh: one-screen delivery metrics from git history + the board. Read-only.
#   per task (board rows in `done` with a merge sha):
#     first commit → merge, cycle time. First commit = earliest commit in the merge's
#     branch side (sha^1..sha^2) whose subject starts with "<ID>:", else the earliest one.
#   merges per day on main (first-parent), reverts on main, median cycle time.
# Usage: tools/ops/metrics.sh [--days N]   (default: all history)
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

SINCE=()
if [[ "${1:-}" == "--days" ]]; then SINCE=(--since="${2:-7} days ago")
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then sed -n 2,7p "$0"; exit 0; fi
pick_python

fmt_dur() { local s=$1; printf '%dh%02dm' $((s / 3600)) $(((s % 3600) / 60)); }

echo "metrics $(date '+%Y-%m-%d %H:%M') base=$BASE@$(g rev-parse --short "$BASE")"
printf '%-8s %-8s %-11s %-11s %s\n' TASK MERGE FIRST MERGED CYCLE

cycles=()
board_src=(--ref "$BASE")
g cat-file -e "$BASE:docs/ops/board.yaml" 2>/dev/null || board_src=()
while IFS=$'\t' read -r id _state _owner _branch sha _rest; do
  [[ -z "$sha" ]] && continue
  g rev-parse --verify -q "$sha^2" >/dev/null || {
    printf '%-8s %-8s %s\n' "$id" "$sha" "(not a merge commit)"; continue; }
  merged="$(g log -1 --format=%ct "$sha")"
  first="$(g log --reverse --format='%at %s' "$sha^1..$sha^2" | awk -v id="$id:" 'index($2,id)==1{print $1; exit}')"
  [[ -z "$first" ]] && first="$(g log --reverse --format=%at "$sha^1..$sha^2" | head -1)"
  [[ -z "$first" ]] && continue
  c=$((merged - first)); ((c < 0)) && c=0
  cycles+=("$c")
  printf '%-8s %-8s %-11s %-11s %s\n' "$id" "${sha:0:7}" \
    "$(date -r "$first" '+%d %H:%M' 2>/dev/null || date -d "@$first" '+%d %H:%M')" \
    "$(date -r "$merged" '+%d %H:%M' 2>/dev/null || date -d "@$merged" '+%d %H:%M')" \
    "$(fmt_dur "$c")"
done < <("$PY" "$OPS_DIR/board.py" list ${board_src[@]+"${board_src[@]}"} --state done --format tsv 2>/dev/null)

echo
echo "merges/day on $BASE:"
g log "$BASE" --first-parent --merges ${SINCE[@]+"${SINCE[@]}"} --format=%cd --date=format:%Y-%m-%d \
  | sort | uniq -c | awk '{printf "  %s  %s\n", $2, $1}'
reverts="$(g log "$BASE" --first-parent ${SINCE[@]+"${SINCE[@]}"} --format=%s | grep -c '^Revert ' || true)"
merges="$(g log "$BASE" --first-parent --merges ${SINCE[@]+"${SINCE[@]}"} --format=%h | grep -c . || true)"
echo "merges=$merges reverts=$reverts tasks_done=${#cycles[@]}"
if [[ ${#cycles[@]} -gt 0 ]]; then
  sorted=($(printf '%s\n' "${cycles[@]}" | sort -n))
  n=${#sorted[@]}
  echo "cycle: median=$(fmt_dur "${sorted[$((n / 2))]}") min=$(fmt_dur "${sorted[0]}") max=$(fmt_dur "${sorted[$((n - 1))]}")"
fi
