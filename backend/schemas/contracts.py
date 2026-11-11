"""Shared data contracts (PDF section 6).

Both csi_core and the API import these models, so a field can never mean two
things. Keep this module dependency-light: pydantic and the standard library
only. Never import FastAPI or SQLAlchemy here.

Conventions:
- IDs are UUID strings.
- Timestamps are timezone-aware datetimes; they are stored as UTC.
- Breathing rates are in breaths per minute (bpm), heart rate in beats per minute.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import uuid4

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def new_id() -> str:
    return str(uuid4())


def _require_tz(v: datetime) -> datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware (UTC)")
    return v


AwareDatetime = Annotated[datetime, AfterValidator(_require_tz)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Bpm = Annotated[float, Field(ge=0, le=120)]
Unit = Annotated[float, Field(ge=0, le=1)]


class Contract(BaseModel):
    """Base: strict about unknown fields so typos fail loudly."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)


# --------------------------------------------------------------------------- enums


class Posture(StrEnum):
    supine = "supine"
    side = "side"
    prone = "prone"
    sitting = "sitting"
    other = "other"


class ReferenceKind(StrEnum):
    hr = "hr"
    spo2 = "spo2"
    rr = "rr"


class SourceKind(StrEnum):
    csi = "csi"
    wearable = "wearable"
    synthetic = "synthetic"


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class Maturity(StrEnum):
    warm_up = "warm_up"
    widening = "widening"
    mature = "mature"


class CheckinSlot(StrEnum):
    am = "am"
    pm = "pm"


# --------------------------------------------------------------------------- capture


class CaptureStats(Contract):
    """FR4: capture quality numbers computed from a raw log."""

    rows: int = Field(ge=0)
    duration_s: float = Field(ge=0)
    mean_rows_per_s: float = Field(ge=0)
    max_gap_s: float = Field(ge=0)
    gaps_over_50ms: int = Field(ge=0)
    rate_changes: int = Field(ge=0)
    timestamp_wraps: int = Field(ge=0)


class RawFileRecord(Contract):
    path: str
    sha256: Sha256
    rows: int = Field(ge=0)
    kind: str = "csi"  # csi | markers | meta | reference


class SessionRecord(Contract):
    """FR1: a recording session plus its capture stats and file hashes."""

    id: str = Field(default_factory=new_id)
    user_id: str
    start_utc: AwareDatetime
    end_utc: AwareDatetime
    condition: str | None = None
    distance_m: float | None = Field(default=None, ge=0, le=20)
    posture: Posture | None = None
    paced_bpm: Bpm | None = None
    reference_device: str | None = None
    room_notes: str | None = None
    phone_model: str | None = None
    source_kind: SourceKind = SourceKind.csi
    files: list[RawFileRecord] = Field(default_factory=list)
    stats: CaptureStats | None = None
    usable: bool = False

    @model_validator(mode="after")
    def _end_after_start(self) -> SessionRecord:
        if self.end_utc <= self.start_utc:
            raise ValueError("end_utc must be after start_utc")
        return self


class MarkerRecord(Contract):
    session_id: str
    host_time: AwareDatetime
    label: str = Field(min_length=1, max_length=64)


class ReferenceReading(Contract):
    session_id: str
    ts: AwareDatetime
    kind: ReferenceKind
    value: float
    source: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _plausible(self) -> ReferenceReading:
        bounds = {"hr": (20, 250), "spo2": (50, 100), "rr": (0, 120)}
        lo, hi = bounds[self.kind.value]
        if not lo <= self.value <= hi:
            raise ValueError(f"{self.kind.value} value out of plausible range")
        return self


# --------------------------------------------------------------------------- physiology


class WindowEstimate(Contract):
    """FR6: one analysis window. rr_a = spectral estimator, rr_b = peak-count."""

    session_id: str
    t_start: AwareDatetime
    t_end: AwareDatetime
    rr_a: Bpm | None = None
    rr_b: Bpm | None = None
    pnr_db: float | None = None
    motion_flag: bool = False
    quality: Unit = 0.0
    presence: bool = True
    run_id: str | None = None

    @model_validator(mode="after")
    def _ordered(self) -> WindowEstimate:
        if self.t_end <= self.t_start:
            raise ValueError("t_end must be after t_start")
        return self


class HeartEstimate(Contract):
    """FR8: stored only, never used by fusion until validated."""

    session_id: str
    t_start: AwareDatetime
    t_end: AwareDatetime
    hr_bpm: float | None = Field(default=None, ge=20, le=250)
    quality: Unit = 0.0
    experimental: bool = True
    run_id: str | None = None

    @field_validator("experimental")
    @classmethod
    def _must_be_experimental(cls, v: bool) -> bool:
        if not v:
            raise ValueError("heart estimates stay experimental until validated")
        return v


class NightFeatures(Contract):
    """FR7: one row per user per night (date = the evening the night started)."""

    user_id: str
    date: date
    rr_med: Bpm | None = None
    rr_var: float | None = Field(default=None, ge=0)
    presence_hours: float = Field(ge=0, le=24)
    restless_frac: Unit = 0.0
    onset: AwareDatetime | None = None
    wake: AwareDatetime | None = None
    midsleep: AwareDatetime | None = None
    quality: Unit = 0.0
    valid: bool = False
    hr_med: float | None = None
    session_ids: list[str] = Field(default_factory=list)
    source_kind: SourceKind = SourceKind.csi
    run_id: str | None = None


class BaselineState(Contract):
    user_id: str
    feature: str
    median: float | None = None
    mad: float | None = Field(default=None, ge=0)
    n: int = Field(default=0, ge=0)
    window_days: int = Field(gt=0)
    maturity: Maturity = Maturity.warm_up


# --------------------------------------------------------------------------- mental


class CheckinRecord(Contract):
    user_id: str
    date: date
    slot: CheckinSlot
    instrument_id: str
    instrument_version: str
    answers: dict[str, int | float | str]
    tags: list[str] = Field(default_factory=list)


class SurveyResponse(Contract):
    """Input for a survey submission. Answers are red-class: never log them."""

    user_id: str
    instrument_id: str
    instrument_version: str
    administered_at: AwareDatetime
    answers: dict[str, int] = Field(min_length=1)

    def __repr__(self) -> str:  # keep answers out of accidental logs/tracebacks
        return (
            f"SurveyResponse(user_id={self.user_id!r}, instrument_id={self.instrument_id!r}, "
            f"answers=<{len(self.answers)} redacted>)"
        )

    __str__ = __repr__


class SafetyResult(Contract):
    """Returned by every survey/symptom path. The caller must act on show=True at once."""

    show: bool
    reason: str | None = None
    resources: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- provenance


class RunRecord(Contract):
    """FR10: which code, parameters and inputs produced a result."""

    id: str = Field(default_factory=new_id)
    kind: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    code_version: str = Field(min_length=1)
    input_hashes: list[Sha256] = Field(default_factory=list)
    status: RunStatus = RunStatus.queued
    started: AwareDatetime | None = None
    finished: AwareDatetime | None = None
    log: str = ""


__all__ = [
    "AwareDatetime",
    "BaselineState",
    "CaptureStats",
    "CheckinRecord",
    "CheckinSlot",
    "HeartEstimate",
    "MarkerRecord",
    "Maturity",
    "NightFeatures",
    "Posture",
    "RawFileRecord",
    "ReferenceKind",
    "ReferenceReading",
    "RunRecord",
    "RunStatus",
    "SafetyResult",
    "SessionRecord",
    "SourceKind",
    "SurveyResponse",
    "WindowEstimate",
    "new_id",
]
