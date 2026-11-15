import { type CSSProperties, useId, useState } from "react";
import { useMotionOK } from "../components/motion";

/** One radar axis. `level` is 0-1 and only sets the shape; it is never shown as a number. */
export interface RadarAxis { key: string; label: string; level: number; current?: boolean }

// Geometry in viewBox units. Labels are HTML boxes placed in % of the box so long names wrap.
const W = 400, H = 300, CX = 200, CY = 150, R = 100, LABEL_R = 116, RINGS = [1 / 3, 2 / 3, 1];
const MIN_DRAW = 0.06; // a level of 0 still shows as a small point, not a collapsed line

const angle = (start: number, i: number, n: number) => start + (i * 2 * Math.PI) / n;
const poly = (pts: readonly (readonly [number, number])[]) => pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

/** Radar with a UV-to-teal gradient shape, grid, spokes, vertex dots and a label box per axis.
 *  No numbers anywhere. Grows from the centre once per `growKey`; never under reduced motion.
 *  `start` is the first axis angle (radians, screen coordinates: -PI/2 = straight up). */
export function Radar({ axes, label, growKey, start = -Math.PI / 2 }: { axes: readonly RadarAxis[]; label: string; growKey: string; start?: number }) {
  const ok = useMotionOK();
  const gid = useId().replace(/:/g, "");
  const [grow] = useState(() => {
    if (!ok) return false;
    try { if (localStorage.getItem(growKey)) return false; localStorage.setItem(growKey, "1"); } catch { /* grow this time */ }
    return true;
  });
  const n = axes.length;
  if (n < 3) return null;
  const at = (i: number, r: number) => { const t = angle(start, i, n); return [CX + r * Math.cos(t), CY + r * Math.sin(t)] as const; };
  const clamp = (v: number) => Math.max(MIN_DRAW, Math.min(1, Number.isFinite(v) ? v : 0));
  const shape = axes.map((a, i) => at(i, clamp(a.level) * R));
  return <figure className="persona-radar">
    <div className="radar-box" role="img" aria-label={label}>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id={`radar-fill-${gid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" className="radar-stop-a" />
            <stop offset="1" className="radar-stop-b" />
          </linearGradient>
        </defs>
        {RINGS.map((f) => <polygon key={f} className="radar-ring" points={poly(axes.map((_, i) => at(i, f * R)))} />)}
        {axes.map((a, i) => { const [x, y] = at(i, R); return <line key={a.key} className="radar-spoke" x1={CX} y1={CY} x2={x} y2={y} />; })}
        <g className={`radar-shape${grow ? " grow" : ""}`} style={{ transformOrigin: `${CX}px ${CY}px` } as CSSProperties}>
          <polygon className="radar-area" points={poly(shape)} fill={`url(#radar-fill-${gid})`} />
          {shape.map(([x, y], i) => <circle key={axes[i].key} className="radar-dot" cx={x} cy={y} r="3.5" />)}
        </g>
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
