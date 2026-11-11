"""Fuse one night's physiology with the latest mental indices into flag drafts.

Each signal is compared with the person's own baseline via robust z. A signal
counts only when its baseline has left warm-up, and physiology only when the
night is valid. Heart rate is never used (FR8). Levels are 0/1 against
``baseline.alert_robust_z``; no second level until a validated cut exists.

Physiology is two-sided (|z|). Mental indices are one-sided: ``index_direction``
gives +1 (higher is worse: PHQ, GAD, stress) or -1 (higher is better: WHO-5,
mood, energy) and an index flags only when direction * z >= alert. An index with
no direction is skipped, never guessed. ``mental_band_alerts`` (index -> cited
band label from the instrument catalog) flags the mental side even during
warm-up; fusion invents no cut-offs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from backend.schemas.contracts import BaselineState, Maturity, NightFeatures
from csi_core.config import CoreConfig
from csi_core.night import robust_z

PHYS_FEATURES = ("rr_med", "rr_var", "restless_frac", "presence_hours")
DOMAIN_PAIR = "physiology|mental"


@dataclass(frozen=True)
class FlagDraft:
    domain_pair: str
    phys_level: int
    mental_level: int
    state: str
    priority: float
    components: dict
    message_key: str


def _score(name: str, value: float | None, b: BaselineState | None, comps: dict) -> float | None:
    if b is None:
        comps[name] = {"value": value, "skipped": "no_baseline"}
        return None
    entry = {
        "value": value,
        "median": b.median,
        "mad": b.mad,
        "n": b.n,
        "maturity": b.maturity.value,
    }
    if b.maturity == Maturity.warm_up:
        comps[name] = entry | {"skipped": "warm_up"}
        return None
    z = robust_z(value, b) if value is not None else None
    if z is None:
        comps[name] = entry | {"skipped": "undefined"}
        return None
    comps[name] = entry | {"z": z}
    return z


def score_night(
    night: NightFeatures,
    baselines: dict[str, BaselineState],
    latest_indices: dict[str, float],
    cfg: CoreConfig,
    *,
    index_direction: Mapping[str, int] | None = None,
    mental_band_alerts: Mapping[str, str] | None = None,
) -> list[FlagDraft]:
    """Return flag drafts for this night ([] when nothing deviates).

    priority = max over counted deviations of (|z| for physiology, direction * z
    for mental) / alert_robust_z; a catalog band alert counts as 1.0.
    """
    index_direction = index_direction or {}
    mental_band_alerts = mental_band_alerts or {}
    alert = cfg.baseline.alert_robust_z
    phys: dict = {}
    mental: dict = {}
    phys_z: list[float] = []
    if night.valid:
        for f in PHYS_FEATURES:
            z = _score(f, getattr(night, f), baselines.get(f), phys)
            if z is not None:
                phys_z.append(z)
    else:
        phys["night"] = {"skipped": "invalid_night"}
    mental_dz: list[float] = []
    for k in sorted(latest_indices):
        direction = index_direction.get(k)
        if direction not in (1, -1):
            mental[k] = {"value": latest_indices[k], "skipped": "no_direction"}
            continue
        z = _score(k, latest_indices[k], baselines.get(k), mental)
        if z is not None:
            mental[k]["direction"] = direction
            mental_dz.append(direction * z)
    for k in sorted(mental_band_alerts):
        mental.setdefault(k, {})["band"] = {"band": mental_band_alerts[k], "source": "catalog"}

    phys_level = int(any(abs(z) >= alert for z in phys_z))
    mental_level = int(any(dz >= alert for dz in mental_dz) or bool(mental_band_alerts))
    if not (phys_level or mental_level):
        return []
    state = {(1, 1): "both", (1, 0): "phys_only", (0, 1): "mental_only"}[(phys_level, mental_level)]
    devs = [abs(z) / alert for z in phys_z] + [max(dz, 0.0) / alert for dz in mental_dz]
    devs += [1.0] * bool(mental_band_alerts)
    priority = max(devs)
    return [
        FlagDraft(
            domain_pair=DOMAIN_PAIR,
            phys_level=phys_level,
            mental_level=mental_level,
            state=state,
            priority=float(priority),
            components={
                "physiology": phys,
                "mental": mental,
                "alert_robust_z": alert,
                "night_date": night.date.isoformat(),
                "valid_night": night.valid,
            },
            message_key=f"flag.{state}",
        )
    ]
