#!/usr/bin/env bash
# bus/post_update.sh: run by any pane after a commit. Posts the latest commit to coord/FEED.md
# so the coordinator picks it up. Usage: bash bus/post_update.sh [agent-name]   (default: codex)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
agent="${1:-codex}"
line="$(git -C "$root" log -1 --format='%h %s')"
bash "$root/coord/say.sh" "$agent" claude "update: $line"
