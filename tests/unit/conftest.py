from datetime import UTC, datetime
from pathlib import Path

import pytest

from csi_core.config import CoreConfig, load_config
from csi_core.synth import synth_night

START = datetime(2026, 11, 10, 22, 55, tzinfo=UTC)
RR = 15.0
ABSENT = [(420.0, 480.0)]


@pytest.fixture(scope="session")
def cfg() -> CoreConfig:
    return load_config()


@pytest.fixture(scope="session")
def night_dir(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, list[Path]]:
    """10 min at 20 Hz crossing an hour boundary: 2 hourly files."""
    d = tmp_path_factory.mktemp("synth")
    paths = synth_night(
        d,
        start_utc=START,
        hours=10 / 60,
        rr_bpm=RR,
        fs=20.0,
        n_sub=12,
        motion_bursts=2,
        absent_spans=ABSENT,
        seed=7,
    )
    return d, paths
