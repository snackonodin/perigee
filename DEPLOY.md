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
