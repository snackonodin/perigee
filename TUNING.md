# TUNING: placeholder values

Every threshold, weight and cutoff below is a **placeholder**. None has been
validated on real data. Do not present any of them as clinical thresholds.
When a value is validated, record the data and date next to it.

| Key (config.yaml) | Value | Why it exists | Validated? |
|---|---|---|---|
| capture.nominal_rows_per_s | 100 | Expected CSI packet rate | no |
| capture.min_rows_per_s | 50 | FR4: refuse to mark a session usable below this | no |
| preprocess.resample_hz | 20 | Uniform grid for filtering | no |
| preprocess.breath_band_hz | 0.1–0.7 | 6–42 breaths/min | no |
| preprocess.heart_band_hz | 0.8–2.0 | Experimental HR only | no |
| preprocess.n_subcarriers_keep | 20 | Top-variance subcarriers before PCA | no |
| breath.window_s / step_s | 60 / 30 | Window-level RR estimates | no |
| breath.min_pnr_db | 3.0 | Reject windows with no clear spectral peak | no |
| breath.max_estimator_disagreement_bpm | 3.0 | Spectral vs peak-count agreement | no |
| breath.motion_z | 4.0 | Motion flag from robust z of window variance | no |
| breath.presence_rel_var | 0.1 | Empty-room detection, scale-free: window variance relative to the session median. Fails if the room is empty all night (median is then 'absent'); acceptable for the demo | no |
| night.min_valid_hours | 3.0 | Night validity | no |
| night.min_quality | 0.5 | Night validity | no |
| baseline.window_days | 28 | Rolling personal baseline | no |
| baseline.warmup_nights / mature_nights | 5 / 14 | Maturity states | no |
| baseline.alert_robust_z | 2.5 | Deviation that raises a physiological flag | no |
| session_scoring.respiration_bpm.low / high | 12 / 23 | Monitor session reference range (operator-supplied, SLEEP_SCORER_INTEGRATION.md) | no |
| session_scoring.heart_rate_bpm.low / high | 65 / 90 | Monitor session reference range (operator-supplied) | no |
| session_scoring.*.falloff_low / falloff_high | 0.25 / 0.25 | Fraction of range width beyond an edge at which a reading earns 0 credit; low and high tuned separately | no |
| session_scoring.weights | 0.40 / 0.40 / 0.20 | Respiration / heart rate / motion share of the experimental session score | no |
| session_scoring.motion.mad_multiplier / floor_m_s2 | 0.85 / 0.02 | Motion flag threshold for Monitor sessions (engine motion_features) | no |
| auth.login_window_s | 900 | Login-failure counting window (s) | no |
| auth.max_failures_per_email_ip | 5 | Failed logins per (email, IP) before 429 | no |
| auth.max_failures_per_email | 20 | Failed logins per email across IPs before 429 | no |
| baseline.mad_floor.* | rr_med 0.3, rr_var 0.05, presence_hours 0.2, restless_frac 0.01 | Lower bound on MAD in robust z; small-n MAD underestimates spread and, with FR13 excluding flagged nights, ratchets narrower | no |
