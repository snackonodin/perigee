#!/usr/bin/env bash
# Set up the app on any machine (macOS/Linux). Run from anywhere:
#   bash scripts/bootstrap.sh
# Env overrides: PYTHON (default python3), VENV (default <repo>/.venv),
#                DATA_DIR (default ~/astro-data). Nothing machine-specific is
#                written into the repo except a local, gitignored .env.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
VENV="${VENV:-$REPO/.venv}"
DATA_DIR="${DATA_DIR:-$HOME/astro-data}"

"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'

if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$REPO/requirements.txt"

mkdir -p "$DATA_DIR/raw" "$DATA_DIR/processed" "$DATA_DIR/db"

if [ ! -f "$REPO/.env" ]; then
  SECRET_KEY="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  FIELD_KEY="$("$VENV/bin/python" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  umask 077
  cat > "$REPO/.env" <<EOF
SECRET_KEY=$SECRET_KEY
FIELD_KEY=$FIELD_KEY
DATA_DIR=$DATA_DIR
DATABASE_URL=sqlite:///$DATA_DIR/db/astro.db
API_HOST=127.0.0.1
API_PORT=8000
EOF
  echo "wrote $REPO/.env (keep it secret; back up FIELD_KEY or encrypted fields are unreadable)"
fi

cd "$REPO"
if [ -f alembic.ini ]; then "$VENV/bin/alembic" upgrade head; fi
"$VENV/bin/python" -m pytest -q
echo "ready: source $VENV/bin/activate && uvicorn backend.main:app --host 127.0.0.1"
