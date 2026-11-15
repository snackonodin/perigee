# Psyche question bank (60 items)

Supplied by the project owner on 2026-11-15 (items, scoring and advice matrix). Replaces the
Mini-IPIP quiz on the Persona page. Non-clinical: heuristic demo bands only, no cut-offs are
shown, nothing here changes a physiological threshold, an alert or the safety path.

- Instrument: `seeds/instruments/psyche60.json` (items `psyche_1..60`, answers 1-5,
  "Not true of me" .. "Deeply true of me"; the three middle labels were filled in by us).
  Item wording: owner's text with citation markers removed. Research inspirations are in the
  owner's source list (HERA/HI-SEAS/MARS-500, sleep-deprivation EEG/PVT, NASA-TLX, WESAD,
  simulated-ISS CO2, Your Mental Health Today, Empathy Quotient, BPAQ).
- Scoring: `backend/services/psyche.py`, spec in the JSON's `psyche_spec`, thresholds in
  `config.yaml psyche:` (placeholders, TUNING.md).
  - Reverse items (6 - raw): Q4, Q8, Q16, Q18, Q23, Q27, Q34, Q36, Q42. Module mean = mean of 6.
  - Stability (16 items, x4, 4-20): raw Q4, Q8, Q16, Q18, Q34, Q36, Q50, Q54; inverted Q1, Q2,
    Q5, Q12, Q13, Q14, Q15, Q17. (The owner's text says "14 items" but lists and divides by 16;
    we follow the list.)
  - Agency (12 items, x4): raw Q19, Q20, Q21, Q30, Q32, Q35, Q37, Q41, Q55; inverted Q23, Q38, Q40.
  - Quadrant: crossing at 12 (inclusive), same names as the Context Engine.
  - UI flags: show_raw_telemetry, calm_non_alarming_tone, structured_checklist_mode,
    private_scheduled_recovery, baseline_only_framing, privacy_lock_reminder (owner rules).
- Advice (owner decision matrix, texts lightly edited): a module mean >= 3.5 plus a current
  signal from the user's own data. Signals available in the app today and the substitutes used:
  | Tag | Owner trigger | Implemented with |
  |---|---|---|
  | rumination_sleep_spill | M1 + restless sleep or high worry/stress | engine body signal (Body or Converging state or phys_level>=1) or daily_pm stress >= 3 |
  | reactive_friction_risk | M3 + short sleep / PVT lapses or elevated RR | engine body signal or daily_am sleep_quality <= 1 |
  | autonomy_strain | M4 + high workload / team conflict | daily_pm stress >= 3 (no workload slider yet) |
  | vigilance_saturation | M5 + PVT drop / mental fatigue | daily energy <= 1 (no mini-PVT yet) |
  | long_middle_drift | M6 + mind signal first + low mood | engine mind signal or mood <= 1 |
  | env_or_somatic_check | mean(Q43,Q45) or mean(Q44,Q48) >= 3.5 + body signal first | as written |
  | circadian_anchor_drift | M9 + midsleep shift >= 0.75 h or late caffeine | midsleep vs median of last 7 nights (no caffeine tag yet) |
- Safety first: no advice while a safety screen is pending (surveys.safety_state). The PHQ-9
  item-9 path is unchanged. Module scores never reach the client; /persona returns only the
  quadrant, axes, style flags and advice text.
- Not implemented yet: longitudinal module z-scores (needs >= 4 retakes), on-device free-text.
- Parts: the bank is also offered as 5 themed parts of 12 (psyche_p1..p5: m1+m9, m2+m3, m4+m7, m5+m6, m8+m10). The persona is scored once all 5 are kept; answers are reassembled from the encrypted survey store, never copied elsewhere.
