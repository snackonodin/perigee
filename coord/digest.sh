#!/usr/bin/env bash
# Coordination digest: FEED tail, 24h commits, dirty counts, issue queues, silent agents.
# Plain bash, macOS-safe (BSD date), no LLM calls. Writes coord/DIGEST.md.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1

OUT="coord/DIGEST.md"
NOW=$(date +%s)
YEAR=$(date +%Y)

commits_since() {
  git log --since="24 hours ago" --oneline -- "$@" 2>/dev/null | wc -l | tr -d ' '
}

dirty_files() {
  git status --porcelain -- "$@" 2>/dev/null | wc -l | tr -d ' '
}

issue_count() {
  file="$1"
  [ -f "$file" ] || { echo 0; return; }
  count=$(grep -cE '^[^#[:space:]]' "$file" 2>/dev/null)
  echo "${count:-0}"
}

feed_epoch() {
  agent="$1"
  line=$(grep -E "^\[[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}\] ${agent} ->" coord/FEED.md 2>/dev/null | tail -n 1)
  [ -z "$line" ] && { echo 0; return; }
  stamp=$(printf '%s\n' "$line" | sed -E 's/^\[([0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2})\].*/\1/')
  date -j -f "%Y-%m-%d %H:%M" "$YEAR-$stamp" +%s 2>/dev/null || echo 0
}

last_commit_epoch() {
  epoch=$(git log -1 --format=%ct -- "$@" 2>/dev/null | tr -d ' ')
  echo "${epoch:-0}"
}

silent_agent() {
  agent="$1"
  shift
  feed=$(feed_epoch "$agent")
  commit=$(last_commit_epoch "$@")
  last="$feed"
  [ "$commit" -gt "$last" ] && last="$commit"
  if [ "$last" -eq 0 ]; then
    echo "- $agent: no FEED post and no commit on record"
    return
  fi
  age=$(( (NOW - last) / 60 ))
  if [ "$age" -ge 90 ]; then
    echo "- $agent: ${age}m since last FEED post or commit"
  fi
}

CLAUDE_PATHS=(engine backend docs waiwai1/engine)
CODEX_PATHS=(frontend)
OPENCODE_PATHS=(tests demo)

{
  echo "# Coordination digest — $(date '+%Y-%m-%d %H:%M %Z')"
  echo
  echo "## FEED (last 10 lines)"
  echo
  echo '```'
  tail -n 10 coord/FEED.md 2>/dev/null || true
  echo '```'
  echo
  echo "## Commits in the last 24 hours"
  echo
  echo "| Owner | Paths | Commits |"
  echo "|---|---|---|"
  echo "| claude | ${CLAUDE_PATHS[*]} | $(commits_since "${CLAUDE_PATHS[@]}") |"
  echo "| codex | ${CODEX_PATHS[*]} | $(commits_since "${CODEX_PATHS[@]}") |"
  echo "| opencode | ${OPENCODE_PATHS[*]} | $(commits_since "${OPENCODE_PATHS[@]}") |"
  echo
  echo "## Uncommitted files"
  echo
  echo "| Area | Paths | Files |"
  echo "|---|---|---|"
  echo "| claude | ${CLAUDE_PATHS[*]} | $(dirty_files "${CLAUDE_PATHS[@]}") |"
  echo "| codex | ${CODEX_PATHS[*]} | $(dirty_files "${CODEX_PATHS[@]}") |"
  echo "| opencode | ${OPENCODE_PATHS[*]} | $(dirty_files "${OPENCODE_PATHS[@]}") |"
  echo
  echo "## Open issues"
  echo
  echo "| Queue | Open |"
  echo "|---|---|"
  for file in bus/issues_for_*.md; do
    [ -e "$file" ] || continue
    name="${file##*/}"
    name="${name#issues_for_}"
    name="${name%.md}"
    echo "| $name | $(issue_count "$file") |"
  done
  echo
  echo "## SILENT AGENTS (no FEED post and no commit for 90+ minutes)"
  echo
  silent=$( { silent_agent claude "${CLAUDE_PATHS[@]}"; silent_agent codex "${CODEX_PATHS[@]}"; silent_agent opencode "${OPENCODE_PATHS[@]}"; } )
  if [ -n "$silent" ]; then
    printf '%s\n' "$silent"
  else
    echo "None."
  fi
} > "$OUT"

echo "wrote $OUT"
