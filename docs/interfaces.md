# Interfaces between workstreams

Each parallel session owns one folder (see CLAUDE.md). These are the function
signatures other workstreams will call. Implement them exactly. If you need to
change one, message the coordinator first. All types come from
`backend/schemas/contracts.py` unless noted.

## csi_core (branch feat/csi-core)
Pure functions only: numpy/scipy/pandas, plus `csi_core.config.CoreConfig`. No DB, no FastAPI.

```python
# csi_core/timebase.py
def unwrap_us(ts_us: np.ndarray, bits: int = 32) -> np.ndarray: ...       # int64 monotonic µs
# csi_core/synth.py  (deterministic: every function takes seed)
def synth_night(out_dir: Path, *, start_utc: datetime, hours: float, rr_bpm: float | Callable[[float], float],
                fs: float = 100.0, n_sub: int = 52, motion_bursts: int = 6,
                absent_spans: list[tuple[float, float]] = (), seed: int = 0) -> list[Path]:
    """Writes hourly csi_HH.csv.gz files + meta.json + markers.csv in the capture format below."""
# csi_core/load.py
def read_rotating(files: list[Path]) -> pd.DataFrame: ...                  # columns: host_time_utc, ts_us, rate, a0..aN
def capture_stats(df: pd.DataFrame, cfg: CoreConfig) -> CaptureStats: ...
# csi_core/preprocess.py
@dataclass(frozen=True)
class CleanSignal: t_s: np.ndarray; x: np.ndarray; fs: float; t0_utc: datetime; quality_notes: list[str]
def clean(df: pd.DataFrame, cfg: CoreConfig) -> CleanSignal: ...
# csi_core/breath.py
def estimate_windows(sig: CleanSignal, session_id: str, cfg: CoreConfig) -> list[WindowEstimate]: ...
# csi_core/night.py
def aggregate(user_id: str, night: date, windows: list[WindowEstimate], cfg: CoreConfig) -> NightFeatures: ...
def update_baseline(prev: BaselineState, history: list[float], cfg: CoreConfig) -> BaselineState: ...
def robust_z(value: float, b: BaselineState) -> float | None: ...
# csi_core/fusion.py
@dataclass(frozen=True)
class FlagDraft: domain_pair: str; phys_level: int; mental_level: int; state: str; priority: float;
                 components: dict; message_key: str
def score_night(night: NightFeatures, baselines: dict[str, BaselineState],
                latest_indices: dict[str, float], cfg: CoreConfig) -> list[FlagDraft]: ...
```

**Capture file format (what synth writes and what real capture must write):**
gzip CSV with header `host_time_utc,ts_us,rate,a0,…,a51`. `host_time_utc` is ISO-8601 with Z,
`ts_us` is the raw 32-bit device counter (wraps), `rate` is the PHY rate column, and `aK` is the
amplitude of subcarrier K. `meta.json` holds the SessionRecord metadata fields (no id/user_id).
`markers.csv` columns: `host_time_utc,label`.

## Estimator plug-ins (portable seam for the team's own scripts)
`config.yaml` `estimators:` maps breath / heart / motion to a `"module:function"` spec,
resolved with `csi_core.config.resolve_estimator`. The team's scripts go in `plugins/`
inside the repo. No file paths anywhere. Core signatures (csi_core owns the exact types):
```python
def breath_core(x: np.ndarray, fs: float, cfg: CoreConfig) -> tuple[float | None, float | None, float | None]:
    """One window of cleaned signal -> (rr_a_bpm, rr_b_bpm, pnr_db). None = no estimate."""
def heart_core(x: np.ndarray, fs: float, cfg: CoreConfig) -> tuple[float | None, float]:   # (hr_bpm, quality)
def motion_core(x: np.ndarray, fs: float, cfg: CoreConfig) -> tuple[bool, float]:           # (motion, score)
```
The windowing, quality, presence and contract wrapping stay in csi_core, so a swapped
core changes numbers only, never shapes. A golden test on the synth fixture checks each swap.

## DB + ingestion (branch feat/db-ingest)
```python
# backend/db.py
def get_engine(url: str | None = None) -> Engine: ...       # PRAGMA foreign_keys, WAL, busy_timeout
SessionLocal: sessionmaker
# backend/models/base.py
class Base(DeclarativeBase): ...
class UserOwned: user_id: Mapped[str]                       # FK users.id ON DELETE CASCADE, indexed
def scoped(stmt, model, user_id: str): ...                  # adds WHERE model.user_id == user_id
# backend/services/ingestion.py
def ingest_session(db, user_id: str, src_dir: Path) -> SessionRecord: ...   # idempotent by sha256
# backend/services/runs.py
def create_run(db, kind: str, params: dict, input_hashes: list[str]) -> RunRecord: ...
def execute(db, run_id: str) -> RunRecord: ...              # process_session / run_nightly
# tools/cli.py: ingest, process, reset-demo, seed-personas, export
```
Tables owned here: users, refresh_tokens, profiles, consents, sessions, raw_files,
markers, reference_readings, window_estimates, heart_estimates, night_features,
baselines, flags, pipeline_runs, audit_log, instrument_catalog, survey_responses,
checkins_daily, indices, safety_events, guidance_cards, guidance_shown.
The accounts and surveys sessions import these models. Only this branch writes migrations.

## Accounts (branch feat/accounts)
```python
# backend/security.py
def hash_password(pw: str) -> str: ...; def verify_password(h: str, pw: str) -> bool: ...
def make_access_token(user_id: str) -> str: ...; def decode_access_token(tok: str) -> str: ...   # -> user_id
def new_refresh_token() -> tuple[str, str]: ...             # (plaintext, sha256)
def encrypt(b: bytes) -> bytes: ...; def decrypt(b: bytes) -> bytes: ...  # Fernet(FIELD_KEY)
class EncryptedJSON(TypeDecorator): ...                     # used by survey_responses.answers etc.
# backend/deps.py
def get_db() -> Iterator[Session]: ...; def current_user(...) -> str: ...  # returns user_id
# backend/services/accounts.py
def signup, login, refresh, logout, export_user(db, user_id) -> dict, delete_user(db, user_id, data_dir) -> None
```

## Surveys + guidance (branch feat/surveys)
```python
# seeds/instruments/{phq2,gad2,who5,phq9,daily_am,daily_pm}.json
#   {id, name, version, timeframe, license_note, source_url,
#    items:[{key,text,options:[{value,label}], safety_trigger?: {min_value}}],
#    scoring:{method:"sum"|"sum_x4", ranges:[{min,max,label}]}}
# backend/services/surveys.py
def load_catalog(db) -> None: ...                           # idempotent upsert from seeds/
def get_instrument(db, instrument_id: str) -> dict: ...
def safety_check(instrument: dict, answers: dict[str, int]) -> SafetyResult: ...   # pure, synchronous
def submit_response(db, user_id: str, data: SurveyResponse) -> dict: ...  # {id, total, scores, safety}
def weekly_indices(db, user_id: str, week_start: date) -> dict[str, float]: ...
# backend/services/guidance.py
def select_guidance(db, user_id: str, flag_id: str) -> list[dict]: ...
# seeds/guidance_cards.json: 5 cards, each with source_note and reviewed_by (null until reviewed)
```
