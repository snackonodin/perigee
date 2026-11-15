import { useEffect, useId, useState } from "react";
import { useMotionOK } from "../components/motion";

/** One radar axis. `level` is 0-1 and only sets the shape; it is never shown as a number. */
export interface RadarAxis { key: string; label: string; level: number; current?: boolean }

// Geometry in viewBox units, centred on (0, 0). The viewBox hugs the outer ring (plus room for the
// dots), so the ring fills the figure's width; ~1 unit per px at the 360 px desktop size.
const R = 255, RINGS = [0.25, 0.5, 0.75, 1], PAD = 10;
// radius = 12% + 88% x level of the outer ring (contract "Persona radar values"), so 0 is a small point
const BASE = 0.12;
const GROW_MS = 600, STAGGER_MS = 90;

const angle = (start: number, i: number, n: number) => start + (i * 2 * Math.PI) / n;
const poly = (pts: readonly (readonly [number, number])[]) => pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/** First view: each vertex extends from the centre, slightly staggered (rAF, ~0.9 s in all). */
function useGrow(n: number, growKey: string): number[] {
  const ok = useMotionOK();
  const [grow] = useState(() => {
    if (!ok) return false;
    try { if (localStorage.getItem(growKey)) return false; localStorage.setItem(growKey, "1"); } catch { /* grow this time */ }
    return true;
  });
  const [f, setF] = useState<number[]>(() => Array(n).fill(grow ? 0 : 1));
  useEffect(() => {
    if (!grow) return;
    let raf = 0;
    const t0 = performance.now();
    const frame = (now: number) => {
      const next = Array.from({ length: n }, (_, i) => easeOut(Math.max(0, Math.min(1, (now - t0 - i * STAGGER_MS) / GROW_MS))));
      setF(next);
      if (next.some((v) => v < 1)) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [grow, n]);
  return f.length === n ? f : Array(n).fill(1);
}

/** Radar: 4 grid rings, grey spokes, a light UV-to-teal gradient shape with a 2 px UV edge, a faint
 *  UV line from the centre to each vertex so the spikes read as stretches, a dot on every axis
 *  (bigger on the person's own) and a label box per axis. No numbers anywhere.
 *  `start` is the first axis angle (radians, screen coordinates: -PI/2 = straight up). */
export function Radar({ axes, label, growKey, start = -Math.PI / 2 }: { axes: readonly RadarAxis[]; label: string; growKey: string; start?: number }) {
  const gid = useId().replace(/:/g, "");
  const n = axes.length;
  const f = useGrow(n, growKey);
  if (n < 3) return null;
  const at = (i: number, r: number) => { const t = angle(start, i, n); return [r * Math.cos(t), r * Math.sin(t)] as const; };
  const level = (v: number) => Math.max(0, Math.min(1, Number.isFinite(v) ? v : 0));
  const shape = axes.map((a, i) => at(i, (BASE + (1 - BASE) * level(a.level)) * R * f[i]));
  const outer = axes.map((_, i) => at(i, R));
  const xs = outer.map(([x]) => x), ys = outer.map(([, y]) => y);
  const x0 = Math.min(...xs) - PAD, y0 = Math.min(...ys) - PAD, w = Math.max(...xs) + PAD - x0, h = Math.max(...ys) + PAD - y0;
  return <figure className="persona-radar">
    <div className="radar-box" role="img" aria-label={label}>
      <div className="radar-plot">
        <svg viewBox={`${x0.toFixed(1)} ${y0.toFixed(1)} ${w.toFixed(1)} ${h.toFixed(1)}`} aria-hidden="true" focusable="false">
          <defs>
            <linearGradient id={`radar-fill-${gid}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" className="radar-stop-a" />
              <stop offset="1" className="radar-stop-b" />
            </linearGradient>
          </defs>
          {RINGS.map((r) => <polygon key={r} className="radar-ring" points={poly(axes.map((_, i) => at(i, r * R)))} />)}
          {outer.map(([x, y], i) => <line key={axes[i].key} className="radar-spoke" x1={0} y1={0} x2={x} y2={y} />)}
          <polygon className="radar-area" points={poly(shape)} fill={`url(#radar-fill-${gid})`} />
          {shape.map(([x, y], i) => <line key={axes[i].key} className="radar-stretch" x1={0} y1={0} x2={x} y2={y} />)}
          {shape.map(([x, y], i) => <circle key={axes[i].key} className={`radar-dot${axes[i].current ? " current" : ""}`} cx={x} cy={y} r={axes[i].current ? 7.5 : 5} />)}
        </svg>
        {axes.map((a, i) => {
          // Outside the outer ring: above an upper corner / below a lower one, and aligned inward
          // from its corner (a right corner's box ends at the corner) so the boxes never overhang.
          const [x, y] = outer[i];
          const side = x > w * 0.1 ? "right" : x < -w * 0.1 ? "left" : "mid";
          const style = { left: `${(((x - x0) / w) * 100).toFixed(2)}%`, top: `${(((y - y0) / h) * 100).toFixed(2)}%` };
          return <span key={a.key} className={`radar-label${a.current ? " current" : ""}`} data-v={y <= 0 ? "above" : "below"} data-h={side} style={style} aria-hidden="true">{a.label}</span>;
        })}
      </div>
    </div>
    <figcaption>No shape is better than another.</figcaption>
  </figure>;
}
