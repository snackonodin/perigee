# Project rules

Project: Astronaut Health Monitor (NASA Space Apps 2026).
Contactless breathing and sleep sensing from Wi-Fi CSI, weekly mental
check-ins, and a personalization engine that flags what is unusual
for each person. It is a screening and awareness tool, not a diagnostic.

Stack: Python 3.11+ (venv at ~/.venvs/astro-app, Python 3.13), FastAPI,
Pydantic v2, SQLAlchemy 2.x, Alembic, SQLite (WAL), pytest, ruff.
Signal code lives in csi_core (numpy, scipy, pandas).

Location: this repo sits in Google Drive. The venv (~/.venvs/astro-app) and
DATA_DIR (~/astro-data: raw CSI and the SQLite DB) live OUTSIDE Drive, because
Drive sync corrupts SQLite WAL files. Never put the DB or venv inside the repo.

Rules:
- Read docs/backend-plan.md before changing the data model or the API.
- Shared contracts live in backend/schemas/contracts.py. Both csi_core and the
  API import them. Do not redefine a contract field elsewhere.
- Routes are thin. Logic lives in backend/services/. csi_core never imports
  FastAPI, SQLAlchemy or anything else in backend/ except backend.schemas.
- Every user-owned table has user_id. Every query filters by user_id.
  Add a test that proves user A cannot read user B.
- Never log passwords, tokens, survey answers, notes or medication names.
- Raw data files are read-only. Never edit them.
- The self-harm item and severe-symptom checks must always show the
  safety screen. Never simplify or remove that path.
- Do not invent medical advice or thresholds. Every value goes in config.yaml
  and is listed as a placeholder in TUNING.md.
- Do not add a dependency without saying why. Pin versions in requirements.txt.
- One small task at a time. Run `pytest` and `ruff check .` before saying a
  task is done.

Folder ownership (parallel sessions, one branch each):
- csi_core/                                  -> branch feat/csi-core
- backend/models, migrations, services/ingestion.py, services/runs.py,
  tools/cli.py                               -> branch feat/db-ingest
- backend/security.py, services/accounts.py, api/v1/auth.py, api/v1/me.py
                                             -> branch feat/accounts
- seeds/, services/surveys.py, services/guidance.py, api/v1/responses.py
                                             -> branch feat/surveys
Change files outside your folder only through the coordinator session.

Commands:
  source ~/.venvs/astro-app/bin/activate
  pytest && ruff check .
