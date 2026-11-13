"""Typed view of config.yaml. Pure: no environment, no backend imports."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    presence_rel_var: float


class NightCfg(_Section):
    min_valid_hours: float
    min_quality: float


class BaselineCfg(_Section):
    window_days: int
    warmup_nights: int
    mature_nights: int
    alert_robust_z: float
    mad_floor: dict[str, float] = Field(default_factory=dict)


class SafetyCfg(_Section):
    severe_symptom_codes: list[str]


class RetentionCfg(_Section):
    raw_days: int


class EstimatorsCfg(_Section):
    """Pluggable estimator cores as "module:function" specs (see resolve_estimator)."""

    breath: str = "csi_core.breath:reference_core"
    heart: str = "csi_core.heart:reference_core"
    motion: str = "csi_core.motion:reference_core"
    # What a core receives per window: "signal" = the clean 1-D signal x,
    # "matrix" = the bin-averaged, unfiltered (n, n_sub) amplitude window + active mask.
    breath_input: Literal["signal", "matrix"] = "signal"
    motion_input: Literal["signal", "matrix"] = "signal"
    # "iq": heart_core_iq(t_s, csi, active, cfg) on each window's packet-level complex CSI.
    heart_input: Literal["signal", "iq"] = "signal"


class AuthCfg(_Section):
    login_window_s: int = Field(default=900, gt=0)
    max_failures_per_email_ip: int = Field(default=5, gt=0)
    max_failures_per_email: int = Field(default=20, gt=0)


class RangeCfg(_Section):
    low: float
    high: float
    falloff_low: float = Field(gt=0)
    falloff_high: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> RangeCfg:
        if self.high <= self.low:
            raise ValueError("range high must be greater than low")
        return self


class SessionWeightsCfg(_Section):
    respiration: float = Field(ge=0)
    heart_rate: float = Field(ge=0)
    motion: float = Field(ge=0)

    @model_validator(mode="after")
    def _sum_to_one(self) -> SessionWeightsCfg:
        if abs(self.respiration + self.heart_rate + self.motion - 1.0) > 1e-6:
            raise ValueError("session_scoring.weights must sum to 1")
        return self


class SessionMotionCfg(_Section):
    mad_multiplier: float = Field(gt=0)
    floor_m_s2: float = Field(ge=0)
    jerk_threshold_m_s3: float | None = Field(default=None, gt=0)


class SessionScoringCfg(_Section):
    """Experimental short-session score (INTEGRATION_PLAN.md D2). All values are placeholders."""

    respiration_bpm: RangeCfg
    heart_rate_bpm: RangeCfg
    weights: SessionWeightsCfg
    motion: SessionMotionCfg


class MonitorDurationsCfg(_Section):
    sleep_analysis: float = Field(gt=0)
    heart_rate: float = Field(gt=0)
    breathing_rate: float = Field(gt=0)


class MonitorCfg(_Section):
    """On-demand ESP sessions. All values are placeholders (TUNING.md)."""

    baud: int = Field(gt=0)
    link_min_rows_per_s: float = Field(gt=0)
    link_interval_s: float = Field(gt=0)
    link_good_intervals: int = Field(ge=1)
    link_timeout_s: float = Field(gt=0)
    calibration_s: float = Field(ge=0)
    duration_s: MonitorDurationsCfg


class CoreConfig(_Section):
    capture: CaptureCfg
    preprocess: PreprocessCfg
    breath: BreathCfg
    night: NightCfg
    baseline: BaselineCfg
    safety: SafetyCfg
    retention: RetentionCfg
    estimators: EstimatorsCfg = EstimatorsCfg()
    auth: AuthCfg = AuthCfg()
    session_scoring: SessionScoringCfg | None = None
    monitor: MonitorCfg | None = None


def resolve_estimator(spec: str) -> Callable[..., Any]:
    """Import "package.module:function" and return the function.

    Specs are dotted module names, never file paths, so the app stays portable.
    """
    module_name, sep, func_name = spec.partition(":")
    if not sep or not module_name or not func_name:
        raise ValueError(f"estimator spec must look like 'module:function', got {spec!r}")
    fn = getattr(importlib.import_module(module_name), func_name, None)
    if not callable(fn):
        raise ValueError(f"estimator {spec!r} is not a callable")
    return fn


def load_config(path: Path | str | None = None) -> CoreConfig:
    p = Path(path) if path else DEFAULT_PATH
    with p.open() as fh:
        return CoreConfig.model_validate(yaml.safe_load(fh))


@lru_cache(maxsize=1)
def get_config() -> CoreConfig:
    return load_config()
