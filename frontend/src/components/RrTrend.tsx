import type { BaselineOut, NightOut } from "../api/types";
import { fmt } from "./format";

const W = 640, H = 220, L = 44, R = 12, T = 12, B = 28;
const DAY = 86_400_000;

/** rr_med per valid night over `days`, against the person's median ± MAD band (inline SVG). */
export function RrTrend({ nights, baseline, days = 28, now = Date.now() }: {
  nights: NightOut[];
  baseline?: BaselineOut;
  days?: number;
  now?: number;
}) {
  const pts = nights
    .filter((n) => n.valid && typeof n.rr_med === "number")
    .map((n) => ({ t: Date.parse(`${n.date}T00:00:00Z`), v: n.rr_med as number, d: n.date }))
    .sort((a, b) => a.t - b.t);
  if (pts.length === 0) return <p className="muted">No valid nights in the last {days} days.</p>;

  const end = now, start = now - (days - 1) * DAY;
  const med = typeof baseline?.median === "number" ? baseline.median : null;
  const mad = typeof baseline?.mad === "number" ? baseline.mad : null;
  const vals = pts.map((p) => p.v);
  if (med !== null) vals.push(med - (mad ?? 0), med + (mad ?? 0));
  const pad = Math.max((Math.max(...vals) - Math.min(...vals)) * 0.15, 0.5);
  const lo = Math.min(...vals) - pad, hi = Math.max(...vals) + pad;
  const x = (t: number) => L + ((t - start) / (end - start)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const out = (v: number) => med !== null && mad !== null && Math.abs(v - med) > mad;

  return (
    <figure className="trend">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="rr-title">
        <title id="rr-title">Breathing rate per night against your usual range</title>
        {med !== null && mad !== null && (
          <rect className="band" data-testid="band" x={L} width={W - L - R} y={y(med + mad)}
            height={Math.max(y(med - mad) - y(med + mad), 1)} />
        )}
        {med !== null && <line className="median" x1={L} x2={W - R} y1={y(med)} y2={y(med)} />}
        <line className="axis" x1={L} x2={W - R} y1={H - B} y2={H - B} />
        {[lo + pad, (lo + hi) / 2, hi - pad].map((v) => (
          <text key={v} className="label" x={L - 6} y={y(v) + 4} textAnchor="end">{fmt(v)}</text>
        ))}
        <text className="label" x={L} y={H - 8}>{new Date(start).toISOString().slice(0, 10)}</text>
        <text className="label" x={W - R} y={H - 8} textAnchor="end">{new Date(end).toISOString().slice(0, 10)}</text>
        <polyline className="line" points={pts.map((p) => `${x(p.t)},${y(p.v)}`).join(" ")} />
        {pts.map((p) => (
          <circle key={p.d} className={out(p.v) ? "pt out" : "pt"} cx={x(p.t)} cy={y(p.v)} r={3.5}>
            <title>{`${p.d}: ${fmt(p.v)} breaths/min`}</title>
          </circle>
        ))}
      </svg>
      <figcaption className="muted">
        Median breathing rate per valid night (breaths/min). Shaded: your median ± MAD.
        {(!baseline || baseline.maturity === "warm_up") && " Your usual range is still warming up."}
      </figcaption>
    </figure>
  );
}
