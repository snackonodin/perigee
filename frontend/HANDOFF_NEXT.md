# Frontend handoff for the next model

Updated: 2026-11-13  
Repository: `/Users/seemachauhan/waiwai/astro app`  
Frontend owner: `frontend/`  
Latest frontend milestone: `b27914d` — `feat(frontend): refine visual health screens`

## Start here

Continue the existing React app. The immediate next screen is **Briefing**. Build it as a read-only, compact in-app screen, then continue with the Consent placeholder and the remaining Settings controls. Do not restart or replace the shell, sign-in flow, Today, Safety, Persona, Body, Sleep, or Check-in screens. The app should remain a viewport-sized mobile-first application with tab navigation and route changes, not a long web page.

Before starting a subtask, read `coord/*.md`, act on REQUEST lines addressed to frontend, and run a scoped Graphify query before searching or reading source. See `AGENTS.md` and the coordination protocol supplied by the user for ownership, graph, build, and checkpoint rules. Append progress only to `coord/pane-frontend.md`; never edit another pane's file. After code changes run `graphify update .`. Do not edit `backend/`, `waiwai1/engine/`, constants, tests, `tools/ops/`, `scripts/`, or vendor files.

## Product and visual brief from the user

- Working concept/name: **Perigee**, a calm astronaut health companion in warm, cinematic spacecraft crew quarters. Health values are always framed as unusual or usual **for this person against their own 28-night baseline**. Avoid diagnostic language and never rank crew.
- Look: deep navy/indigo space theme by default, with aurora teal, violet, amber, orange, and soft rose accents; provide a daylight theme. Use original inline SVG/vector details, static star/space decoration, geometric sans UI plus monospace telemetry, local fonts/system fallbacks, and no CDN or new dependency.
- Visual reference ideas are layout inspiration only: Google Health card hierarchy/rings/timelines; Happify warmth and mood calendar; a filled gradient radar; a hologram scan with hotspots and linked panels; five personality dials on an arc. References are in root `imageref/`. Do not copy art, characters, branding, or game UI.
- Make each screen feel distinct. Use gradient charts and vector details where data supports them; charts use thin lines, soft baseline bands, very faint gridlines, and latest-night dots only. Keep step/CUSUM series unsmoothed. Every level includes an icon and a word, not color alone.
- App behavior: bottom tabs on mobile and side rail on desktop; transitions/swipes should change screens without scrolling down to reach other content. Use one hero per screen, 44px targets, visible focus, AA contrast, chart summaries, and 390px/desktop layouts. Honor reduced motion in CSS and the in-app setting; no flashing.
- Persona adaptation, if actually supplied by persona data: Neuroticism ≥15 uses warm/normalizing language; Conscientiousness ≥16 offers numbered exact steps; Extraversion ≤8 suggests quiet solo recovery; Openness ≥16 exposes expandable telemetry. Do not invent persona values.
- Highest priority: crisis true **or missing** must show the full-screen calm safety view before any scores/results or saving. Include backend instructions, crew-surgeon contact direction, and an “I have read this” acknowledgement gate. No scores or alarms on that screen.

## Completed frontend work

- App shell, sign-in, authentication and safety provider are in place. The shell has mobile bottom tabs, desktop rail, route changes, horizontal swipe navigation and reduced-motion handling.
- Today shows a prominent level/readiness hero, quiet signal tiles, personal baseline framing and advisory. Vitals use the authorized live endpoint; HR is explicitly experimental and only shown when live data is available.
- Safety was implemented as a full-screen first response. `SafetyProvider` fails closed when crisis/safety fields are missing and keeps routine score display behind acknowledgement.
- Persona now has individual colored trait dials, selected-trait popover, a gradient filled radar, optional personal comparison outline, and honest blank/missing trait states. Missing values are **not** filled with a repeated placeholder.
- Body has an interactive original SVG systems hologram for Respiration, Autonomic, Rest, Mind and Cabin. SVG proportions are constrained to correct the crooked layout; hotspot selection updates a vector readout and detail panel. HR remains clearly experimental; no stored HR is fabricated.
- Sleep shows valid sensed-presence nights, latest-night emphasis, breathing-rate personal median ± MAD band, available midsleep regularity and expandable night details. The API does not provide sleep stages, so none are fabricated.
- Check-in is one question at a time, with a monthly calendar of logged entry-type dots. The contract has no explicit mood field, so the calendar does not infer mood. It has a warm illustrated/orbit header.
- Consent is currently a placeholder tab. Settings has account, consent, export/delete and logout flows, but the requested in-app reduced-motion/theme/text-size controls should be inspected and completed as needed.
- Recent visual work is in commit `b27914d`; previous app-shell/Today/Body visual refresh is `2cfb858`. Build after `b27914d` passed `tsc --noEmit && vite build`; `graphify update .` completed. This is a frontend build check only, not a full test-suite run.

## Current display and runtime

- At the last check both `http://127.0.0.1:5173/` (Vite) and `http://127.0.0.1:8765/` (API/app host) returned HTTP 200. Processes may stop when the session ends.
- Vite: `cd frontend && npm run dev` (dependencies currently installed in this working tree).
- Production build: `npm --prefix frontend run build`; output is configured under `backend/static/app`.
- API app: from repo root, `/opt/anaconda3/bin/python3.12 run_app.py`; local setup previously required API dependency installation and `alembic upgrade head`.
- Sign in before accessing protected screens. Then use tabs/swipes for Today, Sleep, Body, Persona, Check-in, Briefing, Consent. Settings is available from the shell shortcut.

## API/data boundaries and known coordination items

- Use only endpoints documented in root `HANDOFF.md`, `coord/API_CONTRACT.md`, and generated OpenAPI types. Current screens read `/api/v1/today`, `/api/v1/nights`, `/api/v1/checkins`, `/api/v1/instruments`, `/api/v1/instruments/{instrument_id}`, `/api/v1/indices`, `/api/v1/live/vitals`, and use documented response submission/auth/settings endpoints.
- `frontend/src/api/client.ts` has empty contract-shaped `TODO(api)` fallbacks only for GET `/today` and GET `/nights` on network errors or 5xx. It deliberately does not hide 401s, and its mock response carries `X-TODO-API-Mock`. Keep fallbacks visible and never invent physiological or persona values.
- If any API problem occurs, do not silently work around it. Append to `coord/pane-integrator.md` a REQUEST with endpoint/method/body, contract expectation, actual status/body, and exact failing frontend line; then use a contract-shaped mock marked `TODO(api)` and continue frontend work. Do not edit backend or contract.
- Existing integrator REQUESTs document API startup/auth detail, `/nights` contract coverage and absent mood schema. The Check-in calendar currently correctly uses entry types only.
- The backend may return engine `context_engine` data inside Today. Use it read-only. The engine owns scoring; do not calculate new health scores or reinterpret level thresholds in the frontend.

## Continuation plan

1. **Briefing:** inspect documented Today/context payload and current guidance components. Build a compact read-only flight-surgeon summary using only returned fields; keep it calm and personal, identify missing data, and avoid diagnosis. Make it visually distinct and usable without page scrolling.
2. **Consent:** replace its placeholder with the existing consent flow/components if appropriate; retain the existing demo-1 consent text/version and API contract. Do not duplicate a second consent policy.
3. **Settings:** add the requested reduced-motion, theme (dark/daylight), and text-size preferences if not already present. Persist locally only where appropriate and confirm controls affect the app shell; maintain focus, contrast and reduced-motion behavior.
4. After each two-screen checkpoint, run only the frontend build or lint, update `STATUS.md` and `coord/pane-frontend.md`, stage/commit only files changed for that milestone by explicit path, then stop for user review as the coordination/token protocol requires. Show the app URL and what to click.
5. Keep a final build check, Graphify refresh after code edits, and a concise checkpoint display. Do not run unrelated/full tests unless asked.

## Last checkpoint record

`b27914d` updated Body alignment and vector readout, distinct Persona dials/radar with true missing values, Sleep gradient telemetry and Check-in's illustrated calendar composition. Files changed: `frontend/src/pages/Body.tsx`, `Persona.tsx`, `Sleep.tsx`, `Psyche.tsx`, `frontend/src/theme/shell.css`, root `STATUS.md`, and `coord/pane-frontend.md`. API payloads were unchanged. The next implementation task is Briefing.
