# Spaceflight hazards in Perigee (context, never diagnosis)

Owner request 2026-11-15. All five hazard themes go into three existing integration points:
cabin and body context, daily/weekly check-ins, and the Context Engine. Nothing here moves a
physiological threshold or hides a flag; tags only explain a Watch/Alert night.

| Hazard | In the app | Engine input (existing) |
|---|---|---|
| Closed environment (CO2 pockets, ventilation, temperature, humidity) | `cabin_readings` per night (synthetic for the demo crew); Today `cabin` + tag "Cabin ppCO2 x mmHg ... check airflow near the bunk" at >= 2.5 mmHg (config `hazards.co2_tag_mmhg`), level `high` at >= 3.0 (`co2_limit_mmhg`) | `environmental_logs.cabin_ppco2` (engine: note above 3 mmHg, `ventilation_anomaly`) |
| Altered gravity (fluid shift: headache, vision; hypokinesis) | `body_cabin` check-in: headache, stuffiness, vision change or eye strain, tiredness, nausea; exercise minutes + session RPE (CR10) | `somatic_symptoms`, `exercise_log` |
| Isolation and confinement (immune-like symptoms, external-authority friction) | `body_cabin`: feverish, sore throat, cough, muscle or joint pain, stomach upset, daytime drowsiness (tag "Immune-like symptoms logged"); friction within crew vs with outside schedule/support | `somatic_symptoms`, `team_friction_vas` (crew, 0-4 -> 0-100) |
| Severe physical symptoms (Gate 1) | `body_cabin` red flags first: sudden severe chest pain, fainting, severe breathlessness -> safety screen with "Get medical help right now"; the pet shows the medical card | bypasses everything (surveys.safety_check, reason `severe_symptom`) |
| Radiation, comms delay | Not shown to the crew (no data; un-actionable). Store-and-forward sync is future work. | none |

Persona stays voice-only. The 3-night persistence valve is unchanged. The safety lock is per
instrument: a clean body_cabin answer never clears a PHQ-9 lock (tests/backend/test_hazards.py).
ppCO2 numbers are the owner's NASA-STD-3001 Vol. 2 citation (2.5 mmHg: <1% headache; 3.0 mmHg:
1-hour limit); verify against the standard before release. Demo crew cabin data are synthetic.
