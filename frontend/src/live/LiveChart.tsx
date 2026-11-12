import { fmt } from "../components/format";
import { decimate, type Pt } from "./decimate";

export interface Series {
  name: string;
  points: Pt[];
  className: string;
}

const W = 640, H = 200, L = 40, R = 10, T = 10, B = 22;
export const MAX_DRAW_POINTS = 300;

/** Polylines broken at gaps (null), decimated to MAX_DRAW_POINTS per series. */
export function LiveChart({ series, unit, label }: { series: Series[]; unit: string; label: string }) {
  const drawn = series.map((s) => ({ ...s, points: decimate(s.points, MAX_DRAW_POINTS) }));
  const all = drawn.flatMap((s) => s.points).filter((p) => p.v !== null) as { t: number; v: number }[];
  if (all.length === 0) {
    return <p className="muted chart-empty">Waiting for data…</p>;
  }
  const t0 = Math.min(...all.map((p) => p.t)), t1 = Math.max(...all.map((p) => p.t));
  const lo0 = Math.min(...all.map((p) => p.v)), hi0 = Math.max(...all.map((p) => p.v));
  const pad = Math.max((hi0 - lo0) * 0.15, 0.5);
  const lo = lo0 - pad, hi = hi0 + pad;
  const x = (t: number) => (t1 === t0 ? (L + W - R) / 2 : L + ((t - t0) / (t1 - t0)) * (W - L - R));
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const segments = (pts: Pt[]) => {
    const segs: string[] = [];
    let cur: string[] = [];
    for (const p of pts) {
      if (p.v === null) {
        if (cur.length) segs.push(cur.join(" "));
        cur = [];
      } else cur.push(`${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`);
    }
    if (cur.length) segs.push(cur.join(" "));
    return segs;
  };
  return (
    <svg className="live-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line className="axis" x1={L} x2={W - R} y1={H - B} y2={H - B} />
      {[lo + pad, (lo + hi) / 2, hi - pad].map((v) => (
        <text key={v} className="label" x={L - 6} y={y(v) + 4} textAnchor="end">
          {fmt(v)}
        </text>
      ))}
      <text className="label" x={W - R} y={H - 6} textAnchor="end">
        {unit}
      </text>
      {drawn.flatMap((s) =>
        segments(s.points).map((pts, i) => (
          <polyline key={`${s.name}-${i}`} className={s.className} data-series={s.name} points={pts} />
        )),
      )}
    </svg>
  );
}
