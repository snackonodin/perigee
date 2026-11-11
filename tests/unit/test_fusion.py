from datetime import date

import pytest

from backend.schemas.contracts import BaselineState, NightFeatures
from csi_core.fusion import FlagDraft, score_night
from csi_core.night import update_baseline

HIST = [14.0, 15.0, 16.0] * 6  # median 15, MAD 1, mature


def _b(cfg, feature, hist=HIST):
    prev = BaselineState(user_id="u", feature=feature, window_days=cfg.baseline.window_days)
    return update_baseline(prev, hist, cfg)


def _night(rr=15.0, valid=True):
    return NightFeatures(
        user_id="u",
        date=date(2026, 11, 10),
        rr_med=rr,
        presence_hours=7.0,
        quality=0.9,
        valid=valid,
    )


def _z(cfg, k):
    return 15.0 + k * 1.4826  # value at robust z = k


def test_steady_night_no_flags(cfg) -> None:
    assert score_night(_night(), {"rr_med": _b(cfg, "rr_med")}, {}, cfg) == []


def test_phys_only(cfg) -> None:
    rr = _z(cfg, cfg.baseline.alert_robust_z + 0.5)
    (f,) = score_night(_night(rr), {"rr_med": _b(cfg, "rr_med")}, {}, cfg)
    assert isinstance(f, FlagDraft)
    assert (f.phys_level, f.mental_level, f.state) == (1, 0, "phys_only")
    assert f.message_key == "flag.phys_only"
    assert f.priority == pytest.approx(
        (cfg.baseline.alert_robust_z + 0.5) / cfg.baseline.alert_robust_z
    )
    assert f.components["physiology"]["rr_med"]["z"] == pytest.approx(
        cfg.baseline.alert_robust_z + 0.5
    )


DIRS = {"who5": -1, "gad2": 1, "phq2": 1}


def test_phys_two_sided_and_mental_worse_direction(cfg) -> None:
    a = cfg.baseline.alert_robust_z
    rr = _z(cfg, -3 * a)  # low breathing rate also counts
    who5 = _z(cfg, -a)  # WHO-5 drop = worse
    bl = {"rr_med": _b(cfg, "rr_med"), "who5": _b(cfg, "who5")}
    (f,) = score_night(_night(rr), bl, {"who5": who5}, cfg, index_direction=DIRS)
    assert f.state == "both" and f.priority == pytest.approx(3.0)
    assert f.components["mental"]["who5"]["direction"] == -1


def test_mental_improvement_does_not_flag(cfg) -> None:
    a = cfg.baseline.alert_robust_z
    bl = {"who5": _b(cfg, "who5"), "gad2": _b(cfg, "gad2")}
    idx = {"who5": _z(cfg, 3 * a), "gad2": _z(cfg, -3 * a)}  # both better
    assert score_night(_night(), bl, idx, cfg, index_direction=DIRS) == []


def test_index_without_direction_is_skipped(cfg) -> None:
    bl = {"mood": _b(cfg, "mood"), "rr_med": _b(cfg, "rr_med")}
    (f,) = score_night(_night(_z(cfg, 10)), bl, {"mood": _z(cfg, 10)}, cfg, index_direction=DIRS)
    assert f.mental_level == 0
    assert f.components["mental"]["mood"]["skipped"] == "no_direction"


def test_band_alert_flags_during_warm_up(cfg) -> None:
    young = _b(cfg, "phq2", [1.0, 2.0])
    (f,) = score_night(
        _night(),
        {"phq2": young},
        {"phq2": 5.0},
        cfg,
        index_direction=DIRS,
        mental_band_alerts={"phq2": "positive screen (>=3)"},
    )
    assert (f.phys_level, f.mental_level, f.state) == (0, 1, "mental_only")
    assert f.priority == 1.0
    c = f.components["mental"]["phq2"]
    assert c["skipped"] == "warm_up"
    assert c["band"] == {"band": "positive screen (>=3)", "source": "catalog"}


def test_mental_only_when_night_invalid(cfg) -> None:
    rr = _z(cfg, 10)
    bl = {"rr_med": _b(cfg, "rr_med"), "gad2": _b(cfg, "gad2")}
    (f,) = score_night(_night(rr, valid=False), bl, {"gad2": _z(cfg, 5)}, cfg, index_direction=DIRS)
    assert f.state == "mental_only" and f.phys_level == 0
    assert f.components["physiology"]["night"]["skipped"] == "invalid_night"


def test_warm_up_baseline_never_flags(cfg) -> None:
    young = _b(cfg, "rr_med", [14.0, 16.0])
    assert score_night(_night(_z(cfg, 50)), {"rr_med": young}, {}, cfg) == []


def test_missing_baseline_is_skipped(cfg) -> None:
    assert score_night(_night(), {}, {"phq2": 6.0}, cfg) == []


def test_mad_floor_from_config_damps_tight_baseline(cfg) -> None:
    tight = _b(cfg, "presence_hours", [7.5, 7.52, 7.54] * 6)  # MAD 0.02 h
    night = NightFeatures(
        user_id="u",
        date=date(2026, 11, 10),
        rr_med=15.0,
        presence_hours=7.3,
        quality=0.9,
        valid=True,
    )
    no_floor = cfg.model_copy(
        update={"baseline": cfg.baseline.model_copy(update={"mad_floor": {}})}
    )
    assert score_night(night, {"presence_hours": tight}, {}, no_floor)  # z ~ -7.4: flagged
    floored = cfg.model_copy(
        update={"baseline": cfg.baseline.model_copy(update={"mad_floor": {"presence_hours": 0.2}})}
    )
    assert score_night(night, {"presence_hours": tight}, {}, floored) == []  # z ~ -0.7
