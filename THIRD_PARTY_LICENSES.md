# Third-party data, resources and licences

Space Apps requires non-NASA materials to be freely available or open source, with the licence
listed. Everything below is used for validation or calibration only; none of it is shipped
inside the app.

## Data

| Resource | Used for | Licence / terms | Link |
|---|---|---|---|
| **PhysioNet Sleep-EDF Expanded** (sleep-cassette PSG + hypnograms) | `validation/sleep_edf_eval.py`: the app's breathing estimator run on real overnight oro-nasal respiration (sleep epochs only) | Open Data Commons Attribution License v1.0 (attribution required) | https://physionet.org/content/sleep-edfx/1.0.0/ (AWS: `s3://physionet-open/sleep-edfx/1.0.0/`, no account) |

Required attribution:
- B. Kemp, A. H. Zwinderman, B. Tuk, H. A. C. Kamphuisen, J. J. L. Oberyé. "Analysis of a sleep-dependent neuronal feedback loop: the slow-wave microcontinuity of the EEG." *IEEE Transactions on Biomedical Engineering* 47(9):1185–1194, 2000.
- A. L. Goldberger et al. "PhysioBank, PhysioToolkit, and PhysioNet: components of a new research resource for complex physiologic signals." *Circulation* 101(23):e215–e220, 2000.

## NASA and spaceflight literature (published summary statistics, no raw data)

| Source | Numbers used | Used for |
|---|---|---|
| Barger L. K. et al. "Prevalence of sleep deficiency and use of hypnotic drugs in astronauts before, during, and after spaceflight: an observational study." *The Lancet Neurology* 13(9):904–912, 2014. | ISS in-flight sleep 6.09 ± 0.67 h per night | `validation/nasa_calibrated_eval.py` sleep-duration model |
| Flynn-Evans E. E. et al. "Circadian misalignment affects sleep and medication use before and during spaceflight." *npj Microgravity* 2:15019, 2016. | 6.4 ± 1.2 h circadian-aligned vs 5.4 ± 1.4 h misaligned (21 astronauts, 3,248 days) | same, aligned and misaligned scenarios |
| NASA-STD-3001 (NASA Space Flight Human-System Standard) | cabin ppCO₂ ≤ 3.0 mmHg | Context Engine environmental note (`cabin_ppco2`) |
| NASA-TLX (Task Load Index), NASA Ames | workload input field | weekly mind indices (when supplied) |

Please verify each citation and URL before submission.

## Not used yet (unverified)

- NASA OSDR Environmental Data Application (CO₂, humidity, temperature telemetry) would fit
  `cabin_ppco2` / `cabin_temp_c`; variables and download access are not yet confirmed.
- NASA Life Sciences Portal bed-rest analog datasets (UTMB): likely fluid-shift physiology,
  weak fit for sleep or respiration.

## Code and design references

react-bits (MIT + Commons Clause, vendored copies under `frontend/src/vendor/react-bits/`),
GSAP 3.15.0 (standard GSAP licence), Lenis (MIT), Vanta (MIT) + three.js (MIT), fonts
Space Grotesk and JetBrains Mono (SIL Open Font License 1.1) via `@fontsource-variable`.
Team CSI scripts: `plugins/vendor/waiwai1/PROVENANCE.md`.
