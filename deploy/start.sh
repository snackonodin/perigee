#!/usr/bin/env bash
# deploy/start.sh: start the API on a host with a persistent disk (Railway, Render, Fly).
# Env (set in the host's dashboard, never committed):
#   SECRET_KEY, FIELD_KEY        required, generate fresh ones for the deployment
#   DATA_DIR                     the persistent volume mount, e.g. /data
#   DATABASE_URL                 default sqlite:///$DATA_DIR/db/astro.db
#   PORT                         provided by the host
#   SEED_DEMO=1                  optional: seed the 3 synthetic demo personas on start
#   DEMO_PERSONA_PASSWORD        required when SEED_DEMO=1
set -euo pipefail
cd "$(dirname "$0")/.."
: "${SECRET_KEY:?set SECRET_KEY}" "${FIELD_KEY:?set FIELD_KEY}" "${DATA_DIR:?set DATA_DIR (persistent volume)}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$DATA_DIR/db/astro.db}"
export PYTHONPATH="$PWD/deploy/vendor${PYTHONPATH:+:$PYTHONPATH}"   # vendored Context Engine
mkdir -p "$DATA_DIR/db" "$DATA_DIR/raw" "$DATA_DIR/processed"
python -m alembic upgrade head
if [ "${SEED_DEMO:-0}" = "1" ]; then
  # Seeding synthesises 14 nights per persona (~8 min the first time). Run it in the background
  # so the port opens at once (hosts kill apps that do not listen within a few minutes).
  : "${DEMO_PERSONA_PASSWORD:?set DEMO_PERSONA_PASSWORD when SEED_DEMO=1}"
  # The raw CSI capture needs ~850 MB to synthesise; skip it unless SEED_RAW=1 (small hosts).
  RAW_FLAG="--no-raw"; [ "${SEED_RAW:-0}" = "1" ] && RAW_FLAG=""
  (python -m tools.cli seed-personas --with-iss $RAW_FLAG > "$DATA_DIR/seed-personas.json" 2> "$DATA_DIR/seed-personas.log" &)
fi
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers
