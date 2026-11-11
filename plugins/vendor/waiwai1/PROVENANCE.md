# Provenance: waiwai1 (team CSI scripts)

- **Source:** `<main repo>/features script/waiwai1/` (the team's own scripts, dropped into
  the main checkout by the user; that folder is gitignored and never committed).
- **Vendored on:** 2026-11-11, by f4 (SCR-1).
- **Licence:** pending confirmation from the team. No LICENSE file or licence/copyright
  headers were present in the source folder.
- **Modifications:** none. Files are byte-identical copies; do not edit them here. Adapters
  live in `plugins/team_*.py` and call these modules.

| File | sha256 | Used for |
|---|---|---|
| `pipeline.py` | `14c8fc7ab75e599de483921fe30edba2f0fe2d292f3c9e9d03cdcd20b0d03ee4` | breath (rate A/B, PNR) and amplitude motion feature |
| `heart_rate.py` | `85c83d5d112258f33dcc89b28a3617d88bfab8cb21f6444e0607a9f4dd42af6d` | experimental I/Q heart rate (SCR-2, vendored 2026-11-12) |

Not vendored yet: `movement.py` (I/Q Doppler movement; imports `heart_rate` absolutely,
so its adapter will alias the vendored module rather than edit the file). `logger.py`/`capture.py`
(pyserial) and `calibrate.py` (matplotlib) run on the capture device, not in the app.

Upstream dependency pins: numpy==1.26.4, scipy==1.13.1. The app runs them with its own
pins (requirements.txt); the golden test in `tests/pipeline/test_team_plugins.py` checks
the vendored code's outputs through our adapters on a real (anonymised) capture slice.
