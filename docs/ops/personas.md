# Demo personas: data spec (OPS-6)

Three **synthetic** users for the demo. Every value below is generated, and no real person's
data is used. Each user has `users.is_synthetic = 1`, rows are tagged `source_kind = synthetic`
(the raw demo session excepted, see §3), and all three are excluded from real statistics
(`v_real_users`).

Expected outcomes in §6 are **derived from the config placeholders on main** (`config.yaml`:
`baseline.alert_robust_z = 2.5`, `warmup_nights = 5`, `mature_nights = 14`,
`night.min_valid_hours = 3.0`, `night.min_quality = 0.5`, `capture.min_rows_per_s = 50`) and the
cited band labels in `seeds/instruments/*.json` (`alert: true` ranges). If a placeholder changes,
the expectations change with it; the oracle tests (§7) read the config, they do not hard-code 2.5.
Nothing here is a clinical threshold or advice.

Consumers: `tools/cli.py seed-personas` (DB-6), the pipeline window-seed path (PIPE-1, f4),
`/today` (CA-2), the demo page (CA-4), `tests/e2e/curl_flow.sh` (OPS-7).

## 1. Timeline (all relative to an anchor, so seeding is reproducible)

`seed-personas --anchor YYYY-MM-DD` (default: today, local). Let **D** = anchor date (demo day).
Nights are dated by the evening they start (contract `NightFeatures.date`).

| Night | Dates | Source | Path |
|---|---|---|---|
| History | D-14 … D-2 (13 nights) | window-level synthetic | PIPE-1 seed path → `run_nightly` |
| Demo night | D-1 (evening before demo) | 6.0 h window-level + **1.5 h raw 100 Hz** | §3 |

Onset 23:00 UTC ± jitter. Windows follow `breath.window_s = 60`, `step_s = 30`
(about 900 windows per 7.5 h night).

## 2. History nights: window-level (PIPE-1, owned by f4)

A seed function writes `WindowEstimate` rows directly. There is no raw file or `sessions.raw_path`,
and there is one synthetic `SessionRecord` per night with `source_kind = synthetic`. Then
`run_nightly` runs as usual, so `aggregate` → `night_features` → baselines → fusion is the same code
the demo night uses.

Per night *k* with seed `persona_seed * 100 + k` (numpy `default_rng`):
- `rr_night ~ Normal(rr_base[k], σ_rr)`; each window `rr_a = rr_b = rr_night + Normal(0, σ_win)`.
- Duration `~ Normal(7.5 h, 0.25 h)`, every window `presence = True`.
- A `restless[k]` share of windows gets `motion_flag = True` and `rr_a = None` (as the estimator does).
- `quality ~ Uniform(0.8, 1.0)`, `pnr_db ~ Uniform(6, 12)`.

**Calibration rule (must hold, tested):** the history generator must match what the raw path
produces on a steady synth night, or the demo night itself becomes the outlier. Measured on main
(`synth_night` → `read_rotating` → `clean` → `estimate_windows` → `aggregate`, 1 h, 100 Hz,
seed 7): constant `rr_bpm` gives rr_a exactly equal to the true value (p10 = p90), so per-window
rr variance is ≈ 0, quality is 1.0 (0.9 with motion), and restless is 0.15 at 6 bursts/h.
So in the history set `σ_win = 0` and keep night-to-night variation in `rr_night`. Choose
`restless` around what the raw part will show (≈ 0.05 at 1 burst per 1.5 h; measure and pin).
PIPE-1's test: for P1, every feature's |z| on the demo night is < 1.5.

## 3. Demo night: one night, two sessions (recommended)

**Decision for the coordinator: how the raw night meets `min_valid_hours = 3.0`.**

| Option | What | Problem |
|---|---|---|
| A. demo config override (`min_valid_hours: 1.0`) | 1.5 h raw night alone | `presence_hours` ≈ 1.5 vs a 7.5 h baseline gives z ≈ −15, a **physiology flag on every persona**, P1 included. It also needs a second config file. |
| B. 3 h raw night | valid without override | the same `presence_hours` z ≈ −11 flag on everyone; synth time doubles (§8) |
| **C. split night** (recommended) | 6.0 h window-level (22:30–04:30) + 1.5 h raw synth (04:30–06:00), both dated D-1, aggregated together | none: presence ≈ 7.5 h, valid without an override, and the last 1.5 h goes through the true path live |

Option C: `aggregate` already takes windows from several sessions (`session_ids`). The raw part is
`synth_night(hours=1.5, fs=100.0, n_sub=52, motion_bursts=1, seed=persona_seed)`, written under
`DATA_DIR`, then `ingest_session` (it must be `usable`: measured 99.5 rows/s ≥ 50) and
`process_session`. That session has `source_kind = csi`, `room_notes = "synth seed=…"`, marker
`demo_night`. The night row keeps `source_kind = synthetic`, because a night with any synthetic input
counts as synthetic.

Always pass `motion_bursts` explicitly. The synth default of 6 does not scale with `hours`: on
0.25 h it gave rr_med 9.7 for a true 14.0 and presence 0.16 h (motion swamps the window).

## 4. Personas

| | P1 `steady` | P2 `breath-drift` | P3 `mental-dip` |
|---|---|---|---|
| email | `persona-steady@example.invalid` | `persona-drift@example.invalid` | `persona-dip@example.invalid` |
| persona_seed | 101 | 202 | 303 |
| rr_base (bpm), history | 14.0 all nights | 13.0 for D-14…D-6; then 13.6, 14.0, 14.4, 14.8 (D-5…D-2) | 15.0 all nights |
| σ_rr (bpm) | 0.5 | 0.5 | 0.5 |
| restless, history | 0.05 ± 0.015 | 0.05 ± 0.015 | 0.05 ± 0.015 |
| demo night rr (raw `rr_bpm`; window part the same) | 14.0 | **16.0** | 15.0 |
| demo night restless | ≈ 0.05 | **≈ 0.20** (`motion_bursts=4` raw, 0.20 in window part) | ≈ 0.05 |
| presence | 7.5 h | 7.5 h | 7.5 h (variant §6 note) |

Passwords come from the env var `DEMO_PERSONA_PASSWORD` (or are generated and printed once by the
CLI). They are never committed or logged. Profiles: minimal, with consent scopes check-ins + survey
answers granted.

## 5. Survey schedule (synthetic answers; submitted via `submit_response`, never logged)

Daily `daily_am` (sleep_quality, energy, mood: 0–4) and `daily_pm` (mood, stress, energy: 0–4) on
D-14 … D-1. Weekly PHQ-2, GAD-2 and WHO-5 on **D-14** and **D-7**.

| | P1 | P2 | P3 |
|---|---|---|---|
| daily AM/PM | 3 / 3 / 3, stress 1 (±1 jitter, seeded) | same as P1 | D-14…D-8 like P1; D-7…D-1 mood 3→1, energy 3→1, stress 1→3 (linear, rounded) |
| PHQ-2 (D-14, D-7) | 1, 1 | 1, 1 | 1, **3** (`at or above screening cutoff`, alert) |
| GAD-2 (D-14, D-7) | 1, 1 | 1, 1 | 1, **3** (alert) |
| WHO-5 (D-14, D-7) | 68, 68 (items sum 17) | 68, 64 | 64, **44** (`low wellbeing`, alert) |
| PHQ-9 on D | — | — | **total 12 (`moderate`, alert), item `phq9_9 = 1`** |

**P3's PHQ-9 is submitted live in the demo** (page or `curl_flow.sh`), not seeded, so the audience
sees the safety screen in the response. `seed-personas --include-final-phq9` seeds it instead for
unattended runs. The item-9 answer is synthetic and exists only to show the safety path.
Answers for 12 with item 9 = 1: `phq9_1..9 = 2,2,2,1,1,2,1,0,1`.

## 6. Expected outcome per persona (demo night D-1 → `/today` on D)

Baseline maturity after 13 history nights: n = 13 valid non-alert nights for P1/P3 → `widening`
(≥ warmup_nights 5, < mature_nights 14), so physiology z counts. Weekly indices have n ≤ 2 →
`warm_up`, so mental z is skipped and **mental flags come only from catalog band alerts**
(`mental_band_alerts`). Fusion invents no cut-offs.

| | phys_level | mental_level | state | priority | why |
|---|---|---|---|---|---|
| P1 | 0 | 0 | — (no flag; `/today` shows "within your usual range") | — | all |z| < 1.5 by calibration |
| P2 | 1 | 0 | `phys_only` | ≫ 1 (rr z ≈ (16.0 − ~13.3)/σ̂ ≈ 4–6 → ~2) | rr_med and restless_frac above baseline; D-3/D-2 are themselves alert nights, so FR13 keeps them out of the baseline |
| P3 | 0 | 1 | `mental_only` | 1.0 | band alerts from D-7: phq2 and gad2 `at or above screening cutoff`, who5 `low wellbeing`; after the live PHQ-9, phq9 `moderate` too |

P3 safety: the PHQ-9 response returns `safety.show = true` with reason item `phq9_9`, and a
minimal `safety_events` row is written. It is independent of fusion and always shown.
Guidance: P2 and P3 get `select_guidance` cards for their flag (unreviewed, `reviewed_by = null`).

Variant (your call): to also show `both`, give P3 presence 6.0 h on D-1 (window part 4.5 h) →
presence z ≈ −6 → `phys_level 1` → `state both`.

**Open questions for the coordinator.**
1. Option A/B/C in §3.
2. Which band window feeds `mental_band_alerts`? Proposed: the latest administration per
   instrument within its own timeframe (14 days for PHQ/GAD/WHO-5).
3. Do daily check-ins become indices (SUR-5)? If daily means are indices with a direction, P3 gets
   a z-based mental signal too, since 13 days of history gives `widening`.

## 7. Oracle tests (CA-3 / DB-6 acceptance)

`tests/e2e/test_personas.py` (tmp DATA_DIR, fixed anchor):
- three users, `is_synthetic`; 14 `night_features` each, all `valid`; demo night `session_ids` has 2 entries;
- raw session usable, `mean_rows_per_s ≥ capture.min_rows_per_s`;
- P1 → no flag; P2 → one flag `phys_only`; P3 → one flag `mental_only`; asserts use `cfg.baseline.alert_robust_z`;
- P3 PHQ-9 submit → `safety.show is True`; no answer text in captured logs;
- reseeding with the same anchor is idempotent (raw ingest dedups by sha256; window seed is upsert by (user, night)).

## 8. Runtime on a laptop (measured on the dev machine, Python 3.13)

| Step | Cost | 3 personas |
|---|---|---|
| `synth_night` raw, 100 Hz, 52 subcarriers | ≈ 44 s per hour (gzip CSV write dominates), ≈ 50 MB/h | 1.5 h each: **≈ 3.3 min**, ≈ 225 MB (option B: ≈ 6.6 min, 450 MB) |
| read + clean + windows (+ ingest hashing) | ≈ 2 s per hour | ≈ 10 s |
| window-level history (≈ 900 windows × 13.8 nights) | bulk insert, one transaction | ≈ 37 k rows, < 10 s |
| surveys (≈ 34 submissions each) | encrypt + insert | < 5 s |
| run_nightly over 14 nights | aggregate + baselines + fusion | < 5 s |
| **Total, first seed** | | **≈ 4 min** |

Speed-up: keep raw demo files under `DATA_DIR/synth-cache/<seed>/`. synth is deterministic by seed,
so a reseed reuses them (sha256 matches) and takes about 30 s. Do not commit them. `reset-demo` keeps
the cache.
