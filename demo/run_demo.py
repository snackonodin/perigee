#!/usr/bin/env python3
"""Run the four demo night-series through the real Context Engine.

Each JSON fixture chains its returned ``state`` into the next night, exactly as the
nightly backend does. The engine is never modified: if a check fails, adjust the
fixture data. Exits non-zero when any scenario fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "waiwai1"))

from engine.api import run  # noqa: E402

HERE = Path(__file__).resolve().parent


def emit(message: str = "") -> None:
    sys.stdout.write(message + "\n")
FIXTURES = ("stable_week.json", "slow_drift.json", "single_night_spike.json", "crisis.json")
LEVEL_NAMES = {0: "normal", 1: "watch"}


def level(out: dict) -> int | None:
    metrics = out.get("scores_and_metrics")
    if not isinstance(metrics, dict):
        return None
    value = metrics.get("phys_level")
    return int(value) if isinstance(value, (int, float)) else None


def crisis(out: dict) -> bool:
    return bool((out.get("safety_status") or {}).get("crisis_override_triggered"))


def run_series(doc: dict) -> list[tuple[str, dict]]:
    state: dict = {}
    results = []
    for night in doc["nights"]:
        payload = {
            "persona": doc.get("persona", {}),
            "sensing_data": night.get("sensing_data", {}),
            "clinical_scales": night.get("clinical_scales", {}),
            "state": state,
            "timestamp_utc": f"{night['date']}T06:00:00Z",
        }
        out = run(payload)
        state = out.get("state", state)
        results.append((night["date"], out))
    return results


def check_series(doc: dict, results: list[tuple[str, dict]]) -> list[str]:
    expect = doc.get("expect", {})
    errors: list[str] = []
    levels = [level(out) for _, out in results]
    crises = [crisis(out) for _, out in results]

    if expect.get("never_crisis") and any(crises):
        fired = [date for (date, _), fired in zip(results, crises, strict=True) if fired]
        errors.append(f"crisis override fired unexpectedly on {fired}")

    if expect.get("below_alert"):
        alerts = [
            date
            for (date, _), lv in zip(results, levels, strict=True)
            if lv is not None and lv >= 2
        ]
        if alerts:
            errors.append(f"reached Alert on {alerts}")

    if expect.get("watch_before_alert"):
        watch = [i for i, lv in enumerate(levels) if lv == 1]
        alert = [i for i, lv in enumerate(levels) if lv is not None and lv >= 2]
        if not watch:
            errors.append("never reached Watch")
        if not alert:
            errors.append("never reached Alert")
        if watch and alert and min(watch) >= min(alert):
            errors.append("Alert came before Watch")

    date_required = expect.get("crisis_on_night")
    if date_required:
        dates = [date for date, _ in results]
        if date_required not in dates:
            errors.append(f"{date_required} is not in the series")
        else:
            index = dates.index(date_required)
            early = [
                date
                for (date, _), fired in zip(results[:index], crises[:index], strict=True)
                if fired
            ]
            if early:
                errors.append(f"crisis override fired before {date_required} on {early}")
            if not crises[index]:
                errors.append(f"crisis override did not fire on {date_required}")
    return errors


def main() -> int:
    failures = 0
    for name in FIXTURES:
        doc = json.loads((HERE / name).read_text(encoding="utf-8"))
        results = run_series(doc)
        errors = check_series(doc, results)
        emit(f"\n== {doc.get('name', name)} ==")
        emit(f"   {doc.get('description', '')}")
        for date, out in results:
            label = "crisis" if crisis(out) else LEVEL_NAMES.get(level(out), "alert")
            emit(f"   {date}  {label}")
        if errors:
            failures += 1
            emit("   FAIL: " + "; ".join(errors))
        else:
            emit("   PASS")
    emit(f"\n{len(FIXTURES) - failures}/{len(FIXTURES)} scenarios passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
