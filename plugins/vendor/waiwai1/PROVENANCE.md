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
| `movement.py` | `f7267bb7180be13d82dfe52c4ace6a61d17a4499071737542146017333382e9d` | I/Q Doppler acceleration for Monitor sessions (vendored 2026-11-14; adapter `plugins/team_movement.py` aliases `heart_rate`) |
| `logger.py` | `2daf7946aa59b296776167ccc74f86e30c0b636e49f2717ed950f545280fcf77` | ESP serial row parser (`parse_c_line`, `PACKET_FIELDS`) for on-demand Monitor capture (vendored 2026-11-14) |

Not vendored: `capture.py` and `calibrate.py` (matplotlib) run on the capture device, not in the app.
`movement.py` imports `heart_rate` absolutely, so `plugins/team_movement.py` aliases the vendored
module instead of editing the file.

Upstream dependency pins: numpy==1.26.4, scipy==1.13.1. The app runs them with its own
pins (requirements.txt); the golden test in `tests/pipeline/test_team_plugins.py` checks
the vendored code's outputs through our adapters on a real (anonymised) capture slice.
