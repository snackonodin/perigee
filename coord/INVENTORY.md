# Repository inventory

285 tracked and non-ignored untracked paths inventoried; generated graph output, caches, virtual environments, node_modules, and recorded/raw data excluded.

| Path | Purpose | Status | Depends on |
|---|---|---|---|
| `.codex/hooks.json` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `.env.example` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `.gitignore` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `AGENTS.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `CLAUDE.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `HANDOFF.md` | Project config, script, data, or documentation | partial | project runtime/tooling |
| `HANDOFF_RAW.md` | Project config, script, data, or documentation | partial | project runtime/tooling |
| `LICENSE` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `README.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `STATUS.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `TUNING.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `alembic.ini` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `backend/__init__.py` | Backend application infrastructure | stub | FastAPI, settings, services |
| `backend/api/__init__.py` | FastAPI route | stub | backend services, schemas, dependencies |
| `backend/api/v1/__init__.py` | FastAPI route | stub | backend services, schemas, dependencies |
| `backend/api/v1/auth.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/guidance.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/ingest.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/instruments.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/jobs.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/live.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/me.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/nights.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/responses.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/sessions.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/api/v1/today.py` | FastAPI route | complete | backend services, schemas, dependencies |
| `backend/config.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/db.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/deps.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/errors.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/logging.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/main.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/models/__init__.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/models/accounts.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/models/base.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/models/capture.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/models/mental.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/models/ops.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/models/physiology.py` | SQLAlchemy persistence model | complete | backend.models.base, contracts, migrations |
| `backend/schemas/__init__.py` | Shared API/data contract | stub | Pydantic and standard library |
| `backend/schemas/contracts.py` | Shared API/data contract | complete | Pydantic and standard library |
| `backend/security.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/services/__init__.py` | Backend service logic | stub | models, schemas, csi_core, related services |
| `backend/services/accounts.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/backup.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/fusion.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/guidance.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/ingestion.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/injection.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/jobs.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/live.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/personas.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/pipeline.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/readouts.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/runs.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/sessions.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/services/surveys.py` | Backend service logic | complete | models, schemas, csi_core, related services |
| `backend/static/demo/app.css` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/static/demo/app.js` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/static/demo/index.html` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/static/demo/personas.json` | Backend application infrastructure | complete | FastAPI, settings, services |
| `backend/worker.py` | Backend application infrastructure | complete | FastAPI, settings, services |
| `config.yaml` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `coord/AUDIT.md` | Coordination/integration artifact | partial | repository implementation and protocol |
| `coord/DECISIONS.md` | Coordination/integration artifact | stub | repository implementation and protocol |
| `coord/INVENTORY.md` | Coordination/integration artifact | partial | repository implementation and protocol |
| `coord/pane-frontend.md` | Coordination/integration artifact | complete | repository implementation and protocol |
| `coord/pane-integrator.md` | Coordination/integration artifact | stub | repository implementation and protocol |
| `coord/pane-loop.md` | Coordination/integration artifact | complete | repository implementation and protocol |
| `csi_core/__init__.py` | CSI estimation and fusion | stub | NumPy/SciPy, shared contracts/config |
| `csi_core/breath.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/config.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/fusion.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/heart.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/load.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/motion.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/night.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/preprocess.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/synth.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/timebase.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `csi_core/windows.py` | CSI estimation and fusion | complete | NumPy/SciPy, shared contracts/config |
| `datasets/__init__.py` | Project config, script, data, or documentation | stub | project runtime/tooling |
| `datasets/adapters/__init__.py` | Project config, script, data, or documentation | stub | project runtime/tooling |
| `docs/backend-plan.md` | Project documentation | partial | project requirements and implementation |
| `docs/interfaces.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/BOARD.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/LESSONS.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/PROTOCOL.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/board.yaml` | Project documentation | complete | project requirements and implementation |
| `docs/ops/lessons.yaml` | Project documentation | complete | project requirements and implementation |
| `docs/ops/personas.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/prompts/accounts.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/prompts/coordinator.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/prompts/csi-core.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/prompts/db-ingest.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/prompts/ops.md` | Project documentation | complete | project requirements and implementation |
| `docs/ops/prompts/surveys.md` | Project documentation | complete | project requirements and implementation |
| `frontend/.gitignore` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/.npmrc` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/index.html` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/package-lock.json` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/package.json` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/scripts/gen-api.mjs` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/App.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/App.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/a11y.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/api/client.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/api/schema.d.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/api/tokens.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/api/types.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/api/useLoad.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/auth/AuthProvider.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/auth/auth.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/AppShell.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/CheckinForm.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/Consents.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/DataControls.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/FlagWhy.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/GuidanceCard.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/IndexCards.css` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/IndexCards.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/IndexCards.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/LoadState.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/NightsTable.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/QuestionnaireList.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/RrTrend.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/TodayCard.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/components/format.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/LiveChart.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/ReplayControl.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/StatusPill.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/decimate.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/decimate.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/monitors.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/sse.test.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/sse.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/stream.test.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/stream.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/types.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/live/useVitals.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/main.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/Live.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/Login.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/Overview.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/Psyche.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/Settings.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/Sleep.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/live.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/pages/pages.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/routes/Placeholder.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/routes/tabs.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/safety/SafetyProvider.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/safety/safety.test.tsx` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/safety/safety.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/test-setup.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/test/fixtures.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/test/mockApi.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/theme/shell.css` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/src/theme/tokens.css` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/tsconfig.json` | React frontend/build/test | complete | frontend package and backend API contract |
| `frontend/vite.config.ts` | React frontend/build/test | complete | frontend package and backend API contract |
| `graph.json` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `handoff_raw.sh` | Project config, script, data, or documentation | partial | project runtime/tooling |
| `loop/BUGS.md` | Project config, script, data, or documentation | partial | project runtime/tooling |
| `loop/PLAN.md` | Project config, script, data, or documentation | partial | project runtime/tooling |
| `loop/reports/20261112T143913Z-iteration-01.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `loop/reports/20261112T144008Z-iteration-01.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `loop/reports/20261112T144107Z-iteration-01.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `loop/reports/20261112T144452Z-iteration-01.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `loop/reports/20261112T144712Z-iteration-01.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `loop/reports/20261112T144854Z-iteration-01.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `loop/run_loop.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `migrations/env.py` | Database migration | complete | SQLAlchemy models and Alembic |
| `migrations/script.py.mako` | Database migration | complete | SQLAlchemy models and Alembic |
| `migrations/versions/20261111_0001_initial_schema.py` | Database migration | complete | SQLAlchemy models and Alembic |
| `migrations/versions/20261111_0002_timeframe_text_survey_answers.py` | Database migration | complete | SQLAlchemy models and Alembic |
| `migrations/versions/20261111_0003_pipeline_runs_user_id.py` | Database migration | complete | SQLAlchemy models and Alembic |
| `migrations/versions/20261112_0004_window_estimates_motion_score.py` | Database migration | complete | SQLAlchemy models and Alembic |
| `plugins/__init__.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/team_breath.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/team_capture.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/team_heart.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/team_motion.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/vendor/__init__.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/vendor/waiwai1.exportused/PROVENANCE.md` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/vendor/waiwai1.exportused/__init__.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/vendor/waiwai1.exportused/heart_rate.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/vendor/waiwai1.exportused/pipeline.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `plugins/vendor/waiwai1/PROVENANCE.md` | Project config, script, data, or documentation | dead (deleted in worktree) | project runtime/tooling |
| `plugins/vendor/waiwai1/__init__.py` | Project config, script, data, or documentation | dead (deleted in worktree) | project runtime/tooling |
| `plugins/vendor/waiwai1/heart_rate.py` | Project config, script, data, or documentation | dead (deleted in worktree) | project runtime/tooling |
| `plugins/vendor/waiwai1/pipeline.py` | Project config, script, data, or documentation | dead (deleted in worktree) | project runtime/tooling |
| `pyproject.toml` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `requirements.txt` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `scripts/bootstrap.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `seeds/guidance_cards.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/instruments/daily_am.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/instruments/daily_pm.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/instruments/gad2.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/instruments/phq2.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/instruments/phq9.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/instruments/who5.json` | Seed data | complete | backend catalog/guidance loaders |
| `seeds/safety_resources.json` | Seed data | complete | backend catalog/guidance loaders |
| `tests/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/api/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/api/conftest.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_accounts_service.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_delete_ingested.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_demo_page.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_deps.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_health.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_isolation.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_logging.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_login_throttle.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_routes_accounts.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/api/test_security.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/contract/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/contract/test_contracts.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/db/conftest.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_api_sessions_jobs.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_backup.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_cli.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_engine.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_ingest_properties.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_ingestion.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_live.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_migrations.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_models.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/db/test_runs.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/e2e/curl_flow.sh` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/e2e/test_curl_flow.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/pipeline/conftest.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_fixture_privacy.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_injection.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_leak.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_personas.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_pipeline.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_team_e2e.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_team_heart_iq.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/pipeline/test_team_plugins.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/safety/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/safety/test_backend_crisis.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/safety/test_engine_safety.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/safety/test_engine_state.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/test_engine_boundary.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/test_portability.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/test_smoke.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/__init__.py` | Automated regression/integration test | stub | application modules and fixtures |
| `tests/unit/conftest.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/dummy_plugins.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_estimators.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_fusion.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_load.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_load_team.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_night.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_ops_board.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_ops_lessons.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_ops_parse_report.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_ops_scripts.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_api.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_db.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_fuzz.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_guidance.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_readouts.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_safety.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_scoring.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_surveys_seeds.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_synth.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tests/unit/test_timebase.py` | Automated regression/integration test | complete | application modules and fixtures |
| `tools/__init__.py` | Project config, script, data, or documentation | stub | project runtime/tooling |
| `tools/cli.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/__init__.py` | Project config, script, data, or documentation | stub | project runtime/tooling |
| `tools/ops/_lib.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/board.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/check_merge.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/lessons.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/merge_ready.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/metrics.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/parse_report.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/pytest_reverse.py` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/status.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `tools/ops/stress.sh` | Project config, script, data, or documentation | complete | project runtime/tooling |
| `waiwai1` | Project config, script, data, or documentation | complete | project runtime/tooling |

## Integration additions

| Path | Purpose | Status | Depends on |
|---|---|---|---|
| `backend/services/context_engine.py` | Context Engine payload mapping, run delegation, state/version persistence | complete | backend models, engine API, nightly fusion |
| `migrations/versions/20261112_0005_context_engine_nights.py` | Context Engine output/state persistence schema | complete | Alembic, ContextEngineNight model |
| `run_app.py` | Local one-command app launcher on port 8765 | complete | backend.main, uvicorn |
| `coord/API_CONTRACT.md` | Frontend/backend response and persistence contract | complete | backend OpenAPI and integration service |
| `tests/backend/test_context_engine_integration.py` | Backend Context Engine persistence, state, idempotency, and crisis route coverage | complete | backend app, database |
