import numpy as np

from csi_core.timebase import count_wraps, unwrap_us

P = 1 << 32


def _raw(true_us: np.ndarray) -> np.ndarray:
    return (true_us % P).astype(np.int64)


def test_no_wrap_is_identity() -> None:
    ts = np.arange(0, 10_000_000, 10_000, dtype=np.int64)
    out = unwrap_us(ts)
    assert out.dtype == np.int64
    np.testing.assert_array_equal(out, ts)
    assert count_wraps(ts) == 0


def test_three_wraps() -> None:
    step = 10_000_000  # 10 s
    true = np.arange(P - 5 * step, 4 * P, step, dtype=np.int64)
    raw = _raw(true)
    assert count_wraps(raw) == 3
    np.testing.assert_array_equal(unwrap_us(raw), true - (P - 5 * step) + raw[0])
    assert np.all(np.diff(unwrap_us(raw)) > 0)


def test_small_backwards_jitter_is_not_a_wrap() -> None:
    ts = np.array([1000, 2000, 1990, 3000, 4000], dtype=np.int64)
    assert count_wraps(ts) == 0
    np.testing.assert_array_equal(unwrap_us(ts), ts)


def test_jitter_right_after_wrap() -> None:
    true = np.array([P - 2000, P - 1000, P + 500, P + 490, P + 1500], dtype=np.int64)
    raw = _raw(true)
    assert count_wraps(raw) == 1
    np.testing.assert_array_equal(unwrap_us(raw), true)


def test_empty_and_single() -> None:
    assert unwrap_us(np.array([], dtype=np.int64)).size == 0
    np.testing.assert_array_equal(unwrap_us(np.array([7])), [7])
