"""Guard: committed capture fixtures carry no device identifiers or raw serial lines."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

FIXTURES = sorted((Path(__file__).resolve().parents[1] / "fixtures").glob("*.csv"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_has_no_identifiers(path: Path) -> None:
    df = pd.read_csv(path, dtype=str, low_memory=False)
    assert "raw_line" not in df.columns and "session_id" not in df.columns
    if "mac" in df.columns:
        macs = df["mac"].str.replace(":", "", regex=False).str.strip("0")
        assert (macs == "").all(), "fixture contains a non-zero MAC"
    if "phone_mac" in df.columns:
        assert df["phone_mac"].isna().all()


def test_there_is_a_fixture_to_check() -> None:
    assert FIXTURES
