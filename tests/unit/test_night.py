from datetime import UTC, date, datetime, timedelta

import pytest

from backend.schemas.contracts import BaselineState, Maturity, WindowEstimate
from csi_core.night import aggregate, robust_z, update_baseline

T0 = datetime(2026, 11, 10, 23, 0, tzinfo=UTC)


def _w(i, rr=15.0, motion=False, presence=True, q=0.9, sid="s1"):
    a = T0 + timedelta(seconds=30 * i)
    return WindowEstimate(
        session_id=sid,
        t_start=a,
        t_end=a + timedelta(seconds=60),
        rr_a=None if motion or not presence else rr,
        rr_b=None if motion or not presence else rr,
        motion_flag=motion,
        presence=presence,
        quality=q if presence else 0.0,
    )


def test_aggregate_valid_night(cfg) -> None:
    ws = [_w(i, rr=14.0 + (i % 3)) for i in range(8 * 120)]  # 8 h of 30-s steps
    ws[10] = _w(10, motion=True)
    ws[11] = _w(11, motion=True)
    nf = aggregate("u", date(2026, 11, 10), ws, cfg)
    assert nf.valid
    assert nf.rr_med == 15.0
    assert nf.rr_var == pytest.approx(2 / 3, rel=0.01)
    assert nf.presence_hours == pytest.approx(8.0, abs=0.02)  # overlaps not double counted
    assert nf.restless_frac == pytest.approx(2 / 960)
    assert nf.onset == T0
    assert nf.midsleep == nf.onset + (nf.wake - nf.onset) / 2
    assert nf.session_ids == ["s1"]


def test_absent_spans_reduce_presence(cfg) -> None:
    ws = [_w(i, presence=i < 120) for i in range(240)]  # 1 h present, 1 h absent
    nf = aggregate("u", date(2026, 11, 10), ws, cfg)
    assert nf.presence_hours == pytest.approx(1.0, abs=0.02)
    assert not nf.valid  # below min_valid_hours


def test_empty_night(cfg) -> None:
    nf = aggregate("u", date(2026, 11, 10), [], cfg)
    assert not nf.valid and nf.presence_hours == 0 and nf.rr_med is None


def test_low_quality_invalid(cfg) -> None:
    ws = [_w(i, q=0.1) for i in range(8 * 120)]
    assert not aggregate("u", date(2026, 11, 10), ws, cfg).valid


def _prev(cfg):
    return BaselineState(user_id="u", feature="rr_med", window_days=cfg.baseline.window_days)


def test_baseline_maturity_steps(cfg) -> None:
    b = cfg.baseline
    assert update_baseline(_prev(cfg), [15.0] * (b.warmup_nights - 1), cfg).maturity == (
        Maturity.warm_up
    )
    assert update_baseline(_prev(cfg), [15.0] * b.warmup_nights, cfg).maturity == (
        Maturity.widening
    )
    assert update_baseline(_prev(cfg), [15.0] * b.mature_nights, cfg).maturity == (Maturity.mature)


def test_baseline_uses_last_window(cfg) -> None:
    hist = [100.0] * 10 + [14.0, 15.0, 16.0] * 20
    st = update_baseline(_prev(cfg), hist, cfg)
    assert st.n == cfg.baseline.window_days
    assert st.median == 15.0 and st.mad == 1.0
    assert st.user_id == "u" and st.feature == "rr_med"


def test_baseline_ignores_nan(cfg) -> None:
    st = update_baseline(_prev(cfg), [float("nan"), 15.0], cfg)
    assert st.n == 1 and st.median == 15.0


def test_robust_z(cfg) -> None:
    st = update_baseline(_prev(cfg), [14.0, 15.0, 16.0] * 5, cfg)
    assert robust_z(15.0, st) == 0.0
    assert robust_z(15.0 + 1.4826 * 3, st) == pytest.approx(3.0)
    flat = update_baseline(_prev(cfg), [15.0] * 5, cfg)
    assert robust_z(16.0, flat) is None  # MAD 0: undefined
    assert robust_z(16.0, _prev(cfg)) is None
