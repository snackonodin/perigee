# Overnight: OpenCode tests and demos the app (2026-11-14)

1. Start: `VENV=<project venv> NIGHT_UNTIL=10:00 nohup bash coord/overnight/night.sh > coord/overnight/night.log 2>&1 &`
   (demo app on port 8766 with its OWN data in ~/astro-demo; never
   touches ~/astro-data or port 8765). Stop: `touch coord/overnight/STOP`.
2. Each cycle (45 min) appends a row to coord/overnight/REPORT.md and posts to the feed.
3. Triage every cycle: backend/frontend test failures in your folders → fix (never weaken
   safety/a11y). Visual bugs seen in coord/overnight/shots/<cycle>/<persona>/*.png → post
   to claude-fe with the file path. Engine/backend bugs → bus/issues_for_claude.md.
4. Open items for you: de-flake auth.test + test_live (load races); add demo/scenarios.json
   (index of the 4 demo/*.json scenarios with expected outcome per scenario).
5. Do not run other full suites in parallel with the loop.
