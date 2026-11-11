"""Typed view of config.yaml. Pure: no environment, no backend imports."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config.yaml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaptureCfg(_Section):
    nominal_rows_per_s: float
    min_rows_per_s: float
    gap_threshold_s: float
    timestamp_bits: int
    rotate_minutes: int


class PreprocessCfg(_Section):
    resample_hz: float
    breath_band_hz: tuple[float, float]
    heart_band_hz: tuple[float, float]
    butter_order: int
    pca_components: int
    n_subcarriers_keep: int


class BreathCfg(_Section):
    window_s: float
    step_s: float
    min_pnr_db: float
    max_estimator_disagreement_bpm: float
    motion_z: float
    presence_min_var: float


class NightCfg(_Section):
    min_valid_hours: float
    min_quality: float


class BaselineCfg(_Section):
    window_days: int
    warmup_nights: int
    mature_nights: int
    alert_robust_z: float


class SafetyCfg(_Section):
    severe_symptom_codes: list[str]


class RetentionCfg(_Section):
    raw_days: int


class CoreConfig(_Section):
    capture: CaptureCfg
    preprocess: PreprocessCfg
    breath: BreathCfg
    night: NightCfg
    baseline: BaselineCfg
    safety: SafetyCfg
    retention: RetentionCfg


def load_config(path: Path | str | None = None) -> CoreConfig:
    p = Path(path) if path else DEFAULT_PATH
    with p.open() as fh:
        return CoreConfig.model_validate(yaml.safe_load(fh))


@lru_cache(maxsize=1)
def get_config() -> CoreConfig:
    return load_config()
