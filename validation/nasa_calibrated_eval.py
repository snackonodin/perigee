#!/usr/bin/env python3
"""Run the real Context Engine on synthetic crews calibrated to published NASA sleep statistics.

Sleep duration per night (hours) is drawn from published spaceflight actigraphy summaries:
  iss_inflight         N(6.09, 0.67)  Barger et al., Lancet Neurology 2014 (ISS, in flight)
  circadian_aligned    N(6.4, 1.2)    Flynn-Evans et al., npj Microgravity 2016
  circadian_misaligned N(5.4, 1.4)    Flynn-Evans et al., npj Microgravity 2016
Sleep duration becomes the engine's ``valid_hours`` (the engine counts a night only when it is
at least 4 h and quality is at least 0.60). Breathing (rr_med) is a DESIGN ASSUMPTION, not NASA
data: each crew member has a personal rate U(12, 18) br/min with night-to-night noise
N(0, 0.5), the same spread the demo personas use.

For every scenario: STABLE crews (42 nights, no change) measure false alarms; DRIFT crews
(after night 28, +0.12 br/min per night) measure detection. Nothing in the engine is changed.

    python validation/nasa_calibrated_eval.py   ->  validation/results/nasa_calibrated.json
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "deploy" / "vendor", ROOT / "waiwai1"):
    if p.is_dir():
        sys.path.insert(0, str(p))
from engine.api import run  # noqa: E402

SCENARIOS = {
    "iss_inflight": (6.09, 0.67, "Barger et al. 2014"),
    "circadian_aligned": (6.4, 1.2, "Flynn-Evans et al. 2016"),
    "circadian_misaligned": (5.4, 1.4, "Flynn-Evans et al. 2016"),
}
CREW, NIGHTS, ONSET, DRIFT_PER_NIGHT, SEED = 200, 42, 28, 0.12, 2026


def level(out: dict) -> int:
    return int((out.get("scores_and_metrics") or {}).get("phys_level") or 0)


def crew_series(rng: random.Random, mean_h: float, sd_h: float, drift: bool) -> dict:
    rr0 = rng.uniform(12.0, 18.0)
    state: dict = {}
    accepted = 0
    first_watch = first_alert = None
    any_flag_after = False
    for n in range(NIGHTS):
        hours = min(10.0, max(0.5, rng.gauss(mean_h, sd_h)))
        rr = rr0 + rng.gauss(0.0, 0.5)
        if drift and n >= ONSET:
            rr += DRIFT_PER_NIGHT * (n - ONSET + 1)
        payload = {
            "persona": {"user_id": "sim", "baselines": {"rr_med": rr0, "mad_rr": 0.5}},
            "sensing_data": {
                "rr_med": round(rr, 2),
                "quality": rng.uniform(0.75, 0.98),
                "valid_hours": round(hours, 2),
            },
            "state": state,
            "timestamp_utc": "2026-01-01T06:00:00Z",
        }
        out = run(payload)
        state = out.get("state", state)
        accepted += hours >= 4.0
        lv = level(out)
        if n >= ONSET:
            if lv >= 1:
                any_flag_after = True
                first_watch = first_watch if first_watch is not None else n - ONSET + 1
            if lv >= 2 and first_alert is None:
                first_alert = n - ONSET + 1
    return {
        "accepted": accepted,
        "flag_after": any_flag_after,
        "first_watch": first_watch,
        "first_alert": first_alert,
    }


def summarise(rows: list[dict], drift: bool) -> dict:
    total_nights = len(rows) * NIGHTS
    out = {
        "crew": len(rows),
        "night_gate_pass_rate": round(sum(r["accepted"] for r in rows) / total_nights, 4),
    }
    if drift:
        alerts = [r["first_alert"] for r in rows if r["first_alert"] is not None]
        watches = [r["first_watch"] for r in rows if r["first_watch"] is not None]
        out.update(
            alert_detection_rate=round(len(alerts) / len(rows), 4),
            median_nights_to_watch=statistics.median(watches) if watches else None,
            median_nights_to_alert=statistics.median(alerts) if alerts else None,
        )
    else:
        out.update(
            crew_with_any_flag_in_14_nights=round(
                sum(r["flag_after"] for r in rows) / len(rows), 4
            ),
            crew_with_alert_in_14_nights=round(
                sum(r["first_alert"] is not None for r in rows) / len(rows), 4
            ),
        )
    return out


def main() -> int:
    rng = random.Random(SEED)
    results = {
        "seed": SEED,
        "crew_per_group": CREW,
        "nights": NIGHTS,
        "drift_onset_night": ONSET,
        "drift_br_per_min_per_night": DRIFT_PER_NIGHT,
        "scenarios": {},
    }
    for name, (mean_h, sd_h, source) in SCENARIOS.items():
        stable = [crew_series(rng, mean_h, sd_h, False) for _ in range(CREW)]
        drifting = [crew_series(rng, mean_h, sd_h, True) for _ in range(CREW)]
        results["scenarios"][name] = {
            "sleep_hours": {"mean": mean_h, "sd": sd_h, "source": source},
            "stable": summarise(stable, False),
            "drift": summarise(drifting, True),
        }
    out = ROOT / "validation" / "results" / "nasa_calibrated.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + "\n")
    sys.stdout.write(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
