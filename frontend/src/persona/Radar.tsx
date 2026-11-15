import { type CSSProperties, useId, useState } from "react";
import { useMotionOK } from "../components/motion";
import type { components } from "../api/schema";

export type ProfileAxis = components["schemas"]["ProfileAxisOut"];

// Geometry in viewBox units. Labels are HTML boxes placed in % of the box so long part names wrap.
const W = 400, H = 290, CX = 200, CY = 150, R = 100, LABEL_R = 114, RINGS = [1 / 3, 2 / 3, 1];
const MIN_DRAW = 0.06; // a level of 0 still shows as a small point, not a collapsed line

/** Words, not numbers: level thirds for the accessible name. */
export function levelWord(level: number): "lower" | "middle" | "higher" {
  return level < 1 / 3 ? "lower" : level < 2 / 3 ? "middle" : "higher";
}

const angle = (i: number, n: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
const point = (i: number, n: number, r: number) => [CX + r * Math.cos(angle(i, n)), CY + r * Math.sin(angle(i, n))] as const;
const poly = (pts: readonly (readonly [number, number])[]) => pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

/** Five-axis tendency shape for the psyche parts. No numbers anywhere; grows from the centre once. */
export function Radar({ profile, growKey }: { profile: readonly ProfileAxis[]; growKey: string }) {
  const ok = useMotionOK();
  const gid = useId().replace(/:/g, "");
  const [grow] = useState(() => {
    if (!ok) return false;
    const key = `persona.radar.${growKey}`;
    try { if (localStorage.getItem(key)) return false; localStorage.setItem(key, "1"); } catch { /* grow this time */ }
    return true;
  });
  const n = profile.length;
  if (n < 3) return null;
  const clamp = (v: number) => Math.max(MIN_DRAW, Math.min(1, Number.isFinite(v) ? v : 0));
  const shape = profile.map((a, i) => point(i, n, clamp(a.level) * R));
  const label = `Your tendency shape across the five parts: ${profile.map((a) => `${a.label}, ${levelWord(a.level)}`).join("; ")}.`;
  return <figure className="persona-radar">
    <div className="radar-box" role="img" aria-label={label}>
      <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true" focusable="false">
        <defs>
          <linearGradient id={`radar-fill-${gid}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" className="radar-stop-a" />
            <stop offset="1" className="radar-stop-b" />
          </linearGradient>
        </defs>
        {RINGS.map((f) => <polygon key={f} className="radar-ring" points={poly(profile.map((_, i) => point(i, n, f * R)))} />)}
        {profile.map((a, i) => { const [x, y] = point(i, n, R); return <line key={a.key} className="radar-spoke" x1={CX} y1={CY} x2={x} y2={y} />; })}
        <g className={`radar-shape${grow ? " grow" : ""}`} style={{ transformOrigin: `${CX}px ${CY}px` } as CSSProperties}>
          <polygon className="radar-area" points={poly(shape)} fill={`url(#radar-fill-${gid})`} />
          {shape.map(([x, y], i) => <circle key={profile[i].key} className="radar-dot" cx={x} cy={y} r="3.5" />)}
        </g>
      </svg>
      {profile.map((a, i) => {
        const t = angle(i, n), [x, y] = point(i, n, LABEL_R);
        // anchor the box on the side facing the centre, so it sits just outside its corner
        const style = { left: `${(x / W) * 100}%`, top: `${(y / H) * 100}%`,
          transform: `translate(${(-50 + 50 * Math.cos(t)).toFixed(0)}%, ${(-50 + 50 * Math.sin(t)).toFixed(0)}%)` };
        return <span key={a.key} className="radar-label" style={style} aria-hidden="true">{a.label}</span>;
      })}
    </div>
    <figcaption>No shape is better than another.</figcaption>
  </figure>;
}
