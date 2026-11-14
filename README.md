# perigee
Contactless Wi-Fi CSI sleep sensing fused with psychometric self-reports to track crew strain in isolated, confined and extreme environments. Personal-baseline CUSUM drift detection, context-aware advisories, crisis-first safety design. Research prototype, 

## Astronaut Health Monitor (repository guide)

The app is this whole repository: a FastAPI service and React frontend, offline demos, SQLite-backed processing, `csi_core/`, team estimator adapters, and the capture/analysis/live/Context Engine scripts under `waiwai1/`. Team code is adapted through `plugins/` and capture/injection paths into the backend. See `CLAUDE.md`, `docs/backend-plan.md`, `docs/interfaces.md`, and `waiwai1/README.md` for architecture and setup details.

## Test-and-report loop

From this repository root, run a short pre-commit pass:

```sh
python loop/run_loop.py --smoke
```

Run the full loop with the default limits:

```sh
python loop/run_loop.py --iterations 20 --budget-min 60
```

The loop needs the project Python dependencies, including FastAPI, SQLAlchemy, Pydantic Settings, pytest, and the Context Engine's Python requirements. It creates a fresh temporary database per iteration, starts the API locally, runs focused safety/API tests and the curl flow, then runs the seeded Context Engine fuzz evaluator. Smoke uses one iteration and a smaller generated batch. Nonzero exit means an invariant failed or the runtime could not start; reports distinguish those cases.

Reports go to `loop/reports/`; confirmed application bugs go to `loop/BUGS.md`. Failures are reproducible from the reported seed. Run `pytest` and `ruff check .` for the regular project checks. The frontend commands are `cd frontend && npm test` and `npm run build`.
