#!/usr/bin/env bash
# usage: coord/say.sh <from> <to> "message"   (to = claude|claude-fe|opencode|you|all; codex retired 2026-11-14)
d="$(cd "$(dirname "$0")" && pwd)"
printf '[%s] %s -> %s: %s\n' "$(date '+%m-%d %H:%M')" "$1" "$2" "$3" >> "$d/FEED.md"
