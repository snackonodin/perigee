# Deploying Astronaut Vitals (plan, 2026-11-14)

## What Vercel can and cannot host for this app

| Part | Vercel? | Why |
|---|---|---|
| React frontend (`frontend/`, Vite build) | **Yes**, static hosting | Plain static files |
| FastAPI backend (`backend/`) | **Only as a demo** | Vercel Python functions have a read-only disk (only `/tmp`, wiped between cold starts), so the SQLite DB and `DATA_DIR` cannot persist; long requests (the SSE live stream) hit the function time limit; numpy + scipy + pandas push the function size close to Vercel's bundle limit |
| ESP sensor (Monitor) | **No** (anywhere in the cloud) | USB serial exists only on the machine the ESP is plugged into |

## Recommended: two options, pick one

**Option A: real hosted app (recommended).**
- Frontend on **Vercel**. A rewrite sends `/api/*` to the backend, so the browser sees one origin and needs no CORS.
- Backend + SQLite on a host with a **persistent disk** (Render, Railway or Fly.io; one small instance plus a 1 GB volume).
- Users, check-ins and nights persist. The Monitor page shows "No sensor is set up on this device" in the cloud, which is correct; sensor sessions still work on a local install.

**Option B: Vercel-only demo (fastest for judges).**
- Frontend and a demo backend both on Vercel. At cold start the backend seeds the 3 synthetic personas into `/tmp` and serves them read-mostly.
- Data resets on each cold start, and it is labelled "Simulated data" (already in the header).
- Sign-up works but does not persist. Live SSE is replaced by polling, or hidden.

## Work needed (either option)

1. **Vendor or submodule `waiwai1/`.** The engine lives in its own git repo, untracked by this one; a cloud build cannot see it.
2. **Build settings:** `frontend/` → `npm ci && npm run build` with output `dist`. Today Vite writes to `../backend/static/app`, so add a deploy build mode.
3. **Secrets:** `SECRET_KEY` and `FIELD_KEY` as host environment variables, newly generated. Never reuse the local `.env`.
4. **Backend start:** `alembic upgrade head`, then `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` (Option A), or a seeding cold-start hook (Option B).
5. **Smoke test:** the overnight loop's API checks plus screenshots, pointed at the deployed URL (`BASE=` is already supported by `coord/ui-audit/shots.mjs`).

## Tentative timeline (IST, 14 Nov)

| Step | Who | Estimate |
|---|---|---|
| Frontend bug fixes + final animations | claude-fe | ~2–3 h (until about 16:00) |
| Deploy prep (vendor engine, build mode, start scripts, health checks) | claude | ~2 h, in parallel |
| First deploy + smoke test on the live URL | claude, with your accounts | ~1 h |
| **Hosted URL ready** | | **about 18:00–19:00 IST today**, if accounts are ready and nothing unexpected blocks |

## Needed from you

- Option A or B.
- For A: a Vercel account plus a Render, Railway or Fly account (free tiers are fine for a demo). For B: a Vercel account only.
- I never deploy or push anything without your go-ahead. Deploying publishes the app.

## Option A: prepared and tested locally (2026-11-14, 13:00 IST)

The user chose Option A. In the repo:
- `deploy/vendor/engine/`: byte-identical Context Engine copy with sha256 hashes (`scripts/sync_engine.sh`; re-run after any engine change).
- `deploy/start.sh`: migrates, optionally seeds the demo personas **in the background**, then serves on `$PORT`. It refuses to start without `SECRET_KEY`, `FIELD_KEY` and `DATA_DIR`.
- `Procfile` (`web: bash deploy/start.sh`) and `.python-version` (3.12) for Railway/Render native Python builds; no Docker needed.
- `frontend/vercel.json`: build to `dist`, SPA fallback, `/api/*` rewritten to the backend.
- Backend `engine_revision()` hashes the imported engine file, so it works without the waiwai1 checkout.

Verified locally in deploy mode: `env -i` with fresh keys, `DATA_DIR` in a temp folder, `SEED_DEMO=1`. Migrations ran, 3 personas seeded (14 nights each, about 8 min on first boot), health 200, persona login 200, `/today` 200 with engine output, `/nights`, `/monitor/modes` and the `/body` deep link 200. The isolation suite passes 32/32.

### Steps (about 30 min once the accounts exist)

1. **Backend on Railway** (volumes available on the trial; on Render a persistent disk needs a paid plan):
   1. New project → Deploy from GitHub repo → root of this repo.
   2. Add a **Volume** mounted at `/data`.
   3. Variables:
      - `DATA_DIR=/data`
      - `SECRET_KEY`: a new random value.
      - `FIELD_KEY`: a new Fernet key.
      - `SEED_DEMO=1` and `DEMO_PERSONA_PASSWORD`: for the judges' demo accounts.
      - `DEMO_ACCESS=1`: enables `POST /api/v1/auth/demo`, the no-login "Try the demo" sign-in (Space Apps requires a demo without registration).
   4. Start command: `bash deploy/start.sh` (the Procfile already says so).
   5. Copy the public URL, e.g. `https://astro-api.up.railway.app`.
2. **Frontend on Vercel:**
   1. New project → same repo → Root Directory `frontend`. Keep "include files outside the root directory" on: the build reads `../seeds/safety_resources.json`.
   2. In `frontend/vercel.json`, replace `REPLACE_WITH_BACKEND_HOST` with the backend host. Commit.
   3. Deploy.
3. **Smoke test:** `BASE=https://<vercel-app> node coord/ui-audit/shots.mjs ...` plus the persona API checks.

Caveats:
- `/api/v1/live/vitals` (SSE) may be buffered or cut by the Vercel proxy. The Monitor page polls, so it is unaffected.
- No ESP in the cloud, so Monitor shows "No sensor is set up on this device".
- The repo must be on GitHub for both hosts. Pushing is your call.
