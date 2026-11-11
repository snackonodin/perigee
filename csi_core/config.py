"""Typed view of config.yaml. Pure: no environment, no backend imports."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

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


class AuthCfg(_Section):
    login_window_s: int = Field(default=900, gt=0)
    max_failures_per_email_ip: int = Field(default=5, gt=0)
    max_failures_per_email: int = Field(default=20, gt=0)


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
