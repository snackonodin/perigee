# Handoff for the next session (coordinator) — 2026-11-14, 14:10 IST

Repo: `/Users/seemachauhan/waiwai/astro app` (branch `main`). Product name in use: **Perigee**
(header still says "Astronaut Vitals" in one constant until the user confirms; ask).
Submission deadline: **Sunday 15 Nov 2026, 11:59 PM local event time.**

Read first: `CLAUDE.md`, this file, `HANDOFF_FRONTEND.md` (frontend state), `coord/FEED.md`
(last 30 lines), `bus/issues_for_claude.md`, `DEPLOY.md`, `coord/overnight/BUGS.md`.
Standing rule (user): read the feed + issues every turn and resolve pane issues unprompted.

## 1. Blocking for submission (in order)

1. **Push to GitHub: NOT done.** Remote `origin` = https://github.com/snackonodin/perigee.git is
   set, but this machine has no GitHub credentials (no `gh`, no token). The user must run, in the
   Claude Code prompt: `! cd "/Users/seemachauhan/waiwai/astro app" && git push -u origin main`
   (username + a GitHub personal access token as password). No secrets are tracked (`.env` is
   ignored; checked).
2. **No-login demo (a Space Apps rule: judges must open the demo with no password/registration).**
   Not built yet. Plan: backend `POST /api/v1/auth/demo` (enabled only with env `DEMO_ACCESS=1`)
   that issues tokens for a seeded synthetic persona (`persona-drift@example.invalid`), plus a
   "Try the demo" button on Login (frontend, claude-fe). Add an isolation test (demo token can only
   read the synthetic persona) and a test that the route is 404 when `DEMO_ACCESS` is unset.
3. **Deploy (Option A chosen by the user):** backend on Railway (volume at `/data`), frontend on
   Vercel (root `frontend/`). Everything is prepared and tested locally in deploy mode (`DEPLOY.md`,
   `deploy/start.sh`, `Procfile`, `.python-version`, `frontend/vercel.json`,
   `deploy/vendor/engine/`). After the push: Railway env `DATA_DIR=/data`, fresh `SECRET_KEY`,
   fresh `FIELD_KEY` (Fernet), `SEED_DEMO=1`, `DEMO_PERSONA_PASSWORD`, `DEMO_ACCESS=1`; copy the
   Railway host into `frontend/vercel.json` (`REPLACE_WITH_BACKEND_HOST`), commit, push, deploy on
   Vercel. Then smoke-test with `BASE=https://<vercel-app> node coord/ui-audit/shots.mjs ...`.
   **App is NOT on Vercel yet.**
4. **Deck placeholders:** `[TEAM NAME]`, `[CHALLENGE NAME]`, `[DEMO URL]` (cover + impact slide).
   The deck is private; the user must share it publicly from its Share menu before submitting.

## 2. Presentation (top priority after the app)

- Deck artifact: **https://claude.ai/artifact/SprgWhfcPgPbgMqSzuZK5s** (Slides type, 7 slides, cap
  is 7). Source mirrored in `presentation/deck_source/project/` (deck.json, deck.css, slides/*.html).
  To edit: read the artifact (Artifact `read` with `paths`), edit, publish with `root` = the folder
  that holds `project/`. Images are uploaded assets (`/_blob/...` ids inside the slides).
- Order: cover · how (orbital path Sense→Learn→Detect→Speak) · sense (raw→filtered→spectrum graph)
  · baseline (40 nights + CUSUM graph computed with engine math; Watch night 36, Alert 37) · persona
  (2-axis plane + weekly-index gauge) · evidence (Sleep-EDF dot chart + NASA-calibrated bars) ·
  impact (statement + screenshots + demo box).
- Style: pastel aurora + frosted glass (backdrop blur) + clay objects, user-requested. Per the
  user: math shown as graphs, not formulas; one central animated visual per slide; no box rows.
  Formulas live in speaker notes. The `/impeccable` craft floor was applied (no eyebrow labels,
  no gradient text, mono only for data). Local render check: build a page from the slide files and
  screenshot with Chrome via CDP (`render.mjs` pattern: JS off, aurora `z-index:-1`).
- Presentation standards are screenshots in `presentation/` (7-slide limit, public no-login demo,
  NASA data required, judging: impact, creativity, validity, relevance, presentation).
- Submission text still to write: project details (what it does, benefits, tools, creativity),
  NASA data links, other data (Sleep-EDF, ODC-By), Super-Intelligence (AI) use disclosure, no NASA
  branding in generated content.

## 3. Evidence produced this session (all reproducible)

- `validation/nasa_calibrated_eval.py` → `validation/results/nasa_calibrated.json`: 200 crews ×
  3 sleep scenarios (Barger 2014: 6.09±0.67 h; Flynn-Evans 2016: 6.4±1.2 / 5.4±1.4 h) through the
  real engine. Nights counted 99.9 / 97.7 / 83.8 %; drifts caught 100 / 100 / 99.5 %; Alert median
  night 8 / 8 / 10; stable crews reaching Alert in 14 nights 1 / 2.5 / 0 %. RR is a stated design
  assumption (personal 12–18, noise 0.5), not NASA data.
- `validation/sleep_edf_eval.py <folder>` → `validation/results/sleep_edf.json`: app breathing core
  on 10 Sleep-EDF nights (5 subjects; download from the public S3 bucket, no account). 9/10 nights
  94–100 % windows kept; median error 0.65 br/min vs zero-crossing; one noisy night correctly
  refused (11 %); median night-to-night change 0.27 br/min.
- `THIRD_PARTY_LICENSES.md`: Sleep-EDF attribution (ODC-By 1.0), NASA papers, code licences.
  Verify citations before submission. OSDR environmental data: not used (unverified).
- Engine fuzz (earlier): 0 violations / 300 personas, fitness 98.67.

## 4. Open decisions for the user

- **D5:** engine treats missing/unreadable PHQ-9 item 9 as 0 and has no `schema_version` in state;
  4 engine tests fail by design (verdict (a)). Recommended: allow the one-line engine fix + version
  tag → full suite green. Backend already fails closed on the survey path.
- **Mini-IPIP intake** (20 personality items) is not in the app, so Persona stays empty and the pet
  uses the default tone. Deck speaker notes say "[shipped / in progress]".
- **Product name** final: Perigee vs Astronaut Vitals.

## 5. App state

- Backend: monitor on-demand ESP sessions (`/api/v1/monitor/*`), graded session scoring,
  station time, SPA deep-link fallback, all committed and tested. Full suite: only the 4 D5 engine
  tests fail (plus occasional load-timing flakes; fixed ones noted in `coord/overnight/BUGS.md`).
- Frontend (claude-fe): Orbit Pop redesign, overnight bugs V1–V11 closed, companion pet built and
  wired (`3ff48ec`). Frontend tests 175/175. See `HANDOFF_FRONTEND.md`.
- **Next frontend brief (user chose "deck and app together"):** carry the deck's craft rules into
  the app: remove eyebrow/kicker labels above headings, no gradient text, mono only for data and
  measurements, one authored motion moment per page (not the same entrance everywhere), glass
  only where it carries meaning. Send to claude-fe with screenshots from `coord/ui-audit/shots.mjs`.
- Servers (detached, do not survive reboot): main app :8765 (`~/astro-data`), demo app :8766
  (`~/astro-demo`, persona password in `~/astro-demo/.demo_password`). Venv: `~/.venvs/astro-app`.
- Overnight loop: `VENV=~/.venvs/astro-app NIGHT_UNTIL=10:00 nohup bash coord/overnight/night.sh`.

## 6. Panes

- claude-fe (frontend) — tmux pane `astro-app-97` before the reboot; check `ListAgents`.
- opencode (tests) — out of quota earlier; tasks in `bus/issues_for_opencode.md`.
- Feed: `bash coord/say.sh <from> <to> "msg"`; progress: `bash coord/progress.sh`.
