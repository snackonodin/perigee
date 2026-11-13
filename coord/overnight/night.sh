#!/usr/bin/env bash
# coord/overnight/night.sh: unattended test + demo loop for OpenCode (2026-11-14).
#
# Every cycle (default 45 min, NIGHT_INTERVAL_S):
#   1. If HEAD moved: rebuild the frontend (served by both app instances).
#   2. Backend suite (coord/suite.sh, serial, niced) and frontend vitest (niced).
#   3. Context Engine demo scenarios (demo/run_demo.py).
#   4. A SEPARATE demo app on port 8766 with its own data folder (default ~/astro-demo, never
#      the real DATA_DIR): migrate, seed the 3 synthetic personas, log in as each, smoke the
#      API (today, nights, monitor modes/sessions), screenshot every page at 1440 and 390.
#   5. Append one line to coord/overnight/REPORT.md and post one line to coord/FEED.md.
# Stop: touch coord/overnight/STOP (checked between steps). One step at a time on purpose:
# the machine was overloaded by parallel suites.
#
# Usage: nohup bash coord/overnight/night.sh > coord/overnight/night.log 2>&1 &
set -uo pipefail
cd "$(git rev-parse --show-toplevel)" || exit 1
. coord/env.sh

VENV="${VENV:-$HOME/.venvs/astro-app}"   # project convention (CLAUDE.md); outside the synced repo
[ -x "$VENV/bin/python" ] && export PATH="$VENV/bin:$PATH"
PY="${PY:-python}"
INTERVAL="${NIGHT_INTERVAL_S:-2700}"
DEMO_DIR="${DEMO_DATA_DIR:-$HOME/astro-demo}"
DEMO_PORT="${DEMO_PORT:-8766}"
OUT=coord/overnight
SHOTS="$OUT/shots"
REPORT="$OUT/REPORT.md"
PAGES="/ /sleep /body /persona /checkin /monitor /settings /briefing"
PERSONAS="steady drift dip"
mkdir -p "$SHOTS" "$DEMO_DIR/db"
[ -f "$REPORT" ] || printf '# Overnight report\n\n| time | sha | backend suite | frontend tests | engine demo | demo app | shots |\n|---|---|---|---|---|---|---|\n' > "$REPORT"

UNTIL="${NIGHT_UNTIL:-}"   # optional local end time HH:MM (e.g. 10:00); empty = run until STOP
past_until() { [ -n "$UNTIL" ] && [ "$(date +%H%M)" -ge "${UNTIL/:/}" ] && [ "$(date +%H%M)" -lt 1200 ]; }
stop() { [ -f "$OUT/STOP" ] || past_until; }
say() { bash coord/say.sh opencode-night "$1" "$2"; }
nicer() { nice -n 10 "$@"; }

# Demo password: generated once, kept out of git (mode 600, outside the repo).
PWF="$DEMO_DIR/.demo_password"
[ -f "$PWF" ] || { umask 077; "$PY" -c "import secrets;print(secrets.token_urlsafe(18))" > "$PWF"; }
export DEMO_PERSONA_PASSWORD="$(cat "$PWF")"
demo_env() { env DATA_DIR="$DEMO_DIR" DATABASE_URL="sqlite:///$DEMO_DIR/db/astro.db" "$@"; }

DEMO_PID=""
start_demo() {
  [ -n "$DEMO_PID" ] && kill "$DEMO_PID" 2>/dev/null && sleep 2
  demo_env "$PY" -m alembic upgrade head > "$OUT/demo_migrate.log" 2>&1 || return 1
  demo_env "$PY" -m tools.cli seed-personas > "$OUT/demo_seed.json" 2>"$OUT/demo_seed.log" || return 1
  demo_env "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port "$DEMO_PORT" > "$OUT/demo_app.log" 2>&1 &
  DEMO_PID=$!
  for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:$DEMO_PORT/api/v1/health" >/dev/null && return 0; sleep 1; done
  return 1
}
trap '[ -n "$DEMO_PID" ] && kill "$DEMO_PID" 2>/dev/null' EXIT

login() {  # $1 = persona key -> prints "access refresh"
  curl -s -X POST "http://127.0.0.1:$DEMO_PORT/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d "{\"email\":\"persona-$1@example.invalid\",\"password\":\"$DEMO_PERSONA_PASSWORD\"}" |
    "$PY" -c "import sys,json;d=json.load(sys.stdin);print(d['access_token'],d['refresh_token'])"
}

last_sha=""
while ! stop; do
  t0=$(date '+%m-%d %H:%M'); sha=$(git rev-parse --short HEAD); stamp=$(date +%Y%m%d-%H%M)

  if [ "$sha" != "$last_sha" ]; then
    (cd frontend && nicer npm run build > "../$OUT/frontend_build.log" 2>&1) && build=ok || build=FAIL
    demo_ok=restart
  else build=same; demo_ok=keep; fi
  stop && break

  nicer bash coord/suite.sh >/dev/null 2>&1
  be_fail=$(grep -cE '^(FAILED|ERROR)' coord/last_suite.txt || true)
  be_pass=$(grep -oE '[0-9]+ passed' coord/last_suite.txt | tail -1)
  stop && break

  fe=$(cd frontend && nicer npx vitest run --reporter=dot 2>&1 | grep -E '^ +Tests ' | tr -s ' ')
  stop && break

  PYTHONPATH=waiwai1 nicer "$PY" demo/run_demo.py > "$OUT/engine_demo.log" 2>&1 && eng=ok || eng=FAIL
  stop && break

  app=ok
  if [ "$demo_ok" = restart ] || ! curl -sf "http://127.0.0.1:$DEMO_PORT/api/v1/health" >/dev/null; then
    start_demo || app="FAIL(start)"
  fi
  smoke=""
  if [ "$app" = ok ]; then
    for p in $PERSONAS; do
      set -- $(login "$p" 2>/dev/null)
      if [ -z "${1:-}" ]; then smoke="$smoke $p:login-FAIL"; app=FAIL; continue; fi
      a=$1 r=$2; B="http://127.0.0.1:$DEMO_PORT/api/v1"; H="Authorization: Bearer $a"
      codes=""
      for path in today "nights?from=$(date -v-30d +%F 2>/dev/null || date -d '-30 days' +%F)&to=$(date +%F)" monitor/modes monitor/sessions; do
        codes="$codes$(curl -s -o /dev/null -w '%{http_code}' "$B/$path" -H "$H"),"
      done
      start=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$B/monitor/sessions" -H "$H" -H 'Content-Type: application/json' -d '{"mode":"heart_rate"}')
      case "$codes$start" in 200,200,200,200,503) ;; *) app=FAIL ;; esac
      smoke="$smoke $p:$codes$start"
      dir="$SHOTS/$stamp/$p"; mkdir -p "$dir"
      BASE="http://127.0.0.1:$DEMO_PORT" nicer node coord/ui-audit/shots.mjs "$dir" "$a" "$r" 1440 900 $PAGES > /dev/null 2>&1
      BASE="http://127.0.0.1:$DEMO_PORT" nicer node coord/ui-audit/shots.mjs "$dir" "$a" "$r" 390 844 $PAGES > /dev/null 2>&1
      rm -rf "$dir/.profile"
    done
  fi
  # keep only the 3 newest shot sets
  n=$(ls -1d "$SHOTS"/*/ 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 3 ] && ls -1d "$SHOTS"/*/ | sort | head -n $((n - 3)) | xargs rm -rf

  line="| $t0 | $sha (build $build) | ${be_pass:-?}, $be_fail failing | ${fe:-?} | $eng | $app${smoke} | $SHOTS/$stamp |"
  echo "$line" >> "$REPORT"
  say claude "night cycle $t0 @$sha: backend ${be_pass:-?} / $be_fail failing; frontend${fe:-?}; engine demo $eng; demo app $app. Details: $REPORT"
  for _ in $(seq 1 $((INTERVAL / 30))); do stop && break; sleep 30; done
done
say all "overnight loop stopped (STOP file)."
