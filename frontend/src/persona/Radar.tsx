import { useEffect, useId, useState } from "react";
import { useMotionOK } from "../components/motion";

/** One radar axis. `level` is 0-1 and only sets the shape; it is never shown as a number. */
export interface RadarAxis { key: string; label: string; level: number; current?: boolean }

// Geometry in viewBox units. Labels are HTML boxes placed in % of the box so long names wrap.
const W = 400, H = 300, CX = 200, CY = 150, R = 100, LABEL_R = 116, RINGS = [0.25, 0.5, 0.75, 1];
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
  const at = (i: number, r: number) => { const t = angle(start, i, n); return [CX + r * Math.cos(t), CY + r * Math.sin(t)] as const; };
  const level = (v: number) => Math.max(0, Math.min(1, Number.isFinite(v) ? v : 0));
  const shape = axes.map((a, i) => at(i, (BASE + (1 - BASE) * level(a.level)) * R * f[i]));
  return <figure className="persona-radar">
    <div className="radar-box" role="img" aria-label={label}>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id={`radar-fill-${gid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" className="radar-stop-a" />
            <stop offset="1" className="radar-stop-b" />
          </linearGradient>
        </defs>
        {RINGS.map((r) => <polygon key={r} className="radar-ring" points={poly(axes.map((_, i) => at(i, r * R)))} />)}
        {axes.map((a, i) => { const [x, y] = at(i, R); return <line key={a.key} className="radar-spoke" x1={CX} y1={CY} x2={x} y2={y} />; })}
        <polygon className="radar-area" points={poly(shape)} fill={`url(#radar-fill-${gid})`} />
        {shape.map(([x, y], i) => <line key={axes[i].key} className="radar-stretch" x1={CX} y1={CY} x2={x} y2={y} />)}
        {shape.map(([x, y], i) => <circle key={axes[i].key} className={`radar-dot${axes[i].current ? " current" : ""}`} cx={x} cy={y} r={axes[i].current ? 5.5 : 3.5} />)}
      </svg>
      {axes.map((a, i) => {
        const t = angle(start, i, n), [x, y] = at(i, LABEL_R);
        // anchor the box on the side facing the centre, so it sits just outside its corner
        const style = { left: `${(x / W) * 100}%`, top: `${(y / H) * 100}%`,
          transform: `translate(${(-50 + 50 * Math.cos(t)).toFixed(0)}%, ${(-50 + 50 * Math.sin(t)).toFixed(0)}%)` };
        return <span key={a.key} className={`radar-label${a.current ? " current" : ""}`} style={style} aria-hidden="true">{a.label}</span>;
      })}
    </div>
    <figcaption>No shape is better than another.</figcaption>
  </figure>;
}
