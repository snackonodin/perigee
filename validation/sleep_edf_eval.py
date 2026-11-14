#!/usr/bin/env python3
"""Check our breathing estimator on real overnight respiration (PhysioNet Sleep-EDF Expanded).

Data: Sleep-EDF Expanded (Kemp et al. 2000; Goldberger et al. 2000, PhysioNet), Open Data
Commons Attribution License v1.0. Files are read from a local folder you download yourself:

    https://physionet-open.s3.amazonaws.com/sleep-edfx/1.0.0/sleep-cassette/<file>

What it does, per night:
1. Reads the oro-nasal respiration channel and the hypnogram (sleep stages) with a minimal EDF
   reader (no extra dependency).
2. Keeps only epochs scored as sleep (stages 1-4, R).
3. Runs the app's own breathing core (csi_core.breath.reference_core) on 60 s windows every
   30 s, with the app's acceptance rule: spectral peak and peak counting must agree within
   cfg.breath.max_estimator_disagreement_bpm, and the peak-to-noise ratio must be at least
   cfg.breath.min_pnr_db.
4. Compares accepted windows with an independent zero-crossing breath count on the same signal.

This validates the realism of rr_med / rr_var and the estimator's acceptance logic on real
breathing. It cannot test multi-week drift (one night per file).

    python validation/sleep_edf_eval.py <folder with *-PSG.edf and *-Hypnogram.edf>
      -> validation/results/sleep_edf.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from csi_core.breath import reference_core  # noqa: E402
from csi_core.config import get_config  # noqa: E402

SLEEP = {"Sleep stage 1", "Sleep stage 2", "Sleep stage 3", "Sleep stage 4", "Sleep stage R"}


def read_edf(path: Path) -> tuple[dict, list[np.ndarray]]:
    raw = path.read_bytes()
    n_hdr, n_rec = int(raw[184:192]), int(raw[236:244])
    rec_dur, ns = float(raw[244:252]), int(raw[252:256])
    h = raw[256:n_hdr]

    def field(offset: int, width: int) -> list[str]:
        return [
            h[offset + i * width : offset + (i + 1) * width].decode("latin-1").strip()
            for i in range(ns)
        ]

    o = 0
    labels = field(o, 16)
    o += 16 * ns
    o += 80 * ns  # transducer
    o += 8 * ns  # physical dimension
    pmin = [float(x) for x in field(o, 8)]
    o += 8 * ns
    pmax = [float(x) for x in field(o, 8)]
    o += 8 * ns
    dmin = [float(x) for x in field(o, 8)]
    o += 8 * ns
    dmax = [float(x) for x in field(o, 8)]
    o += 8 * ns
    o += 80 * ns  # prefiltering
    nsamp = [int(x) for x in field(o, 8)]
    rec_len = sum(nsamp)
    data = np.frombuffer(raw[n_hdr : n_hdr + n_rec * rec_len * 2], dtype="<i2").reshape(
        n_rec, rec_len
    )
    sigs, start = [], 0
    for i in range(ns):
        d = data[:, start : start + nsamp[i]].reshape(-1).astype(float)
        start += nsamp[i]
        if labels[i] != "EDF Annotations" and dmax[i] != dmin[i]:
            d = pmin[i] + (d - dmin[i]) * (pmax[i] - pmin[i]) / (dmax[i] - dmin[i])
        sigs.append(d)
    meta = {"labels": labels, "fs": [n / rec_dur for n in nsamp], "duration_s": n_rec * rec_dur}
    return meta, sigs


def sleep_mask(hyp: Path, n_seconds: int) -> np.ndarray:
    raw = hyp.read_bytes()
    n_hdr = int(raw[184:192])
    text = raw[n_hdr:].decode("latin-1")
    mask = np.zeros(n_seconds, dtype=bool)
    for tal in text.split("\x00"):
        parts = tal.split("\x14")
        if len(parts) < 2 or not parts[0]:
            continue
        head = parts[0].split("\x15")
        try:
            onset = float(head[0])
            dur = float(head[1]) if len(head) > 1 and head[1] else 0.0
        except ValueError:
            continue
        if any(p in SLEEP for p in parts[1:]):
            a, b = int(onset), int(onset + dur)
            mask[max(0, a) : min(n_seconds, b)] = True
    return mask


def zero_cross_bpm(x: np.ndarray, fs: float) -> float | None:
    x = x - np.median(x)
    up = np.flatnonzero((x[:-1] < 0) & (x[1:] >= 0))
    if up.size < 3:
        return None
    return 60.0 * (up.size - 1) / ((up[-1] - up[0]) / fs)


def night(psg: Path, hyp: Path, cfg) -> dict:
    meta, sigs = read_edf(psg)
    idx = next(i for i, lab in enumerate(meta["labels"]) if "resp" in lab.lower())
    fs = meta["fs"][idx]
    x = sigs[idx]
    mask = sleep_mask(hyp, int(meta["duration_s"]))
    win, step = int(cfg.breath.window_s * fs), int(cfg.breath.step_s * fs)
    accepted, ref_err, total = [], [], 0
    for s in range(0, len(x) - win, step):
        t0 = int(s / fs)
        if not mask[t0 : t0 + int(cfg.breath.window_s)].all():
            continue
        total += 1
        seg = x[s : s + win]
        seg = seg - seg.mean()
        rr_a, rr_b, pnr = reference_core(seg, fs, cfg)
        if rr_a is None or rr_b is None or pnr is None:
            continue
        if (
            abs(rr_a - rr_b) <= cfg.breath.max_estimator_disagreement_bpm
            and pnr >= cfg.breath.min_pnr_db
        ):
            accepted.append(rr_a)
            ref = zero_cross_bpm(seg, fs)
            if ref is not None:
                ref_err.append(abs(rr_a - ref))
    acc = np.array(accepted)
    return {
        "file": psg.name,
        "channel": meta["labels"][idx],
        "fs_hz": fs,
        "sleep_windows": total,
        "accepted_windows": int(acc.size),
        "acceptance_rate": round(acc.size / total, 4) if total else None,
        "rr_med": round(float(np.median(acc)), 2) if acc.size else None,
        "rr_var": round(float(np.var(acc)), 3) if acc.size else None,
        "rr_p10_p90": [
            round(float(np.percentile(acc, 10)), 2),
            round(float(np.percentile(acc, 90)), 2),
        ]
        if acc.size
        else None,
        "mae_vs_zero_crossing_bpm": round(float(np.mean(ref_err)), 2) if ref_err else None,
        "within_2bpm_of_zero_crossing": round(float(np.mean(np.array(ref_err) <= 2.0)), 4)
        if ref_err
        else None,
    }


def main(folder: str) -> int:
    cfg = get_config()
    d = Path(folder)
    rows = []
    for psg in sorted(d.glob("*-PSG.edf")):
        hyps = sorted(d.glob(psg.name[:7] + "*-Hypnogram.edf"))
        if hyps:
            rows.append(night(psg, hyps[0], cfg))
    # Two nights per subject (SC4ssN...: ss = subject, N = night): real night-to-night change.
    by_subject: dict[str, list[float]] = {}
    for r in rows:
        if r["rr_med"] is not None:
            by_subject.setdefault(r["file"][3:5], []).append(r["rr_med"])
    deltas = [abs(v[0] - v[1]) for v in by_subject.values() if len(v) == 2]
    ok = [r for r in rows if r["acceptance_rate"] is not None]
    summary = {
        "nights": len(rows),
        "subjects": len(by_subject),
        "mean_acceptance_rate": round(float(np.mean([r["acceptance_rate"] for r in ok])), 4),
        "rr_med_range": [min(r["rr_med"] for r in ok), max(r["rr_med"] for r in ok)],
        "mean_mae_vs_zero_crossing_bpm": round(
            float(
                np.mean(
                    [
                        r["mae_vs_zero_crossing_bpm"]
                        for r in ok
                        if r["mae_vs_zero_crossing_bpm"] is not None
                    ]
                )
            ),
            2,
        ),
        "night_to_night_abs_delta_rr_med": [round(x, 2) for x in deltas],
        "median_night_to_night_delta_bpm": round(float(np.median(deltas)), 2) if deltas else None,
    }
    out = {
        "dataset": "PhysioNet Sleep-EDF Expanded (sleep-cassette)",
        "licence": "Open Data Commons Attribution License v1.0",
        "window_s": cfg.breath.window_s,
        "step_s": cfg.breath.step_s,
        "summary": summary,
        "nights": rows,
    }
    dst = ROOT / "validation" / "results" / "sleep_edf.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=2) + "\n")
    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
