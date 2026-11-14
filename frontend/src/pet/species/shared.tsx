// Shared art pieces for every species: palette helpers, <PetDefs>, the face (eyes, shines,
// nose, "w" mouth, blush), rim light, contact shadow and accessories. All colors come from
// tokens as var(--token, #fallback). No outlines; strokes are >= 4 viewBox units.
import type { CSSProperties, ReactNode } from "react";
import type { Species } from "../types";

export type Tok = readonly [name: string, fallback: string];
export const T = {
  eye: ["pet-eye", "#1F2A37"], shine: ["pet-eye-shine", "#FFFFFF"], nose: ["pet-nose", "#E8909C"],
  mouth: ["pet-mouth", "#8A5A5A"], blush: ["pet-blush", "#FBB8C2"], rim: ["pet-rim", "#BFE0F5"],
  shadow: ["pet-shadow", "rgba(31,42,55,.14)"], star: ["pet-star", "#FFF1B8"], zzz: ["pet-zzz", "#5B6B7A"],
  mint: ["mint", "#BFE9D6"], lavender: ["lavender", "#D9D0F5"], peach: ["peach", "#FFD9C7"], sky: ["sky", "#BFE0F5"],
} as const satisfies Record<string, Tok>;

export const v = ([name, fb]: Tok) => `var(--${name}, ${fb})`;
export const fill = (t: Tok): CSSProperties => ({ fill: v(t) });
export const stroke = (t: Tok, width: number): CSSProperties => ({ fill: "none", stroke: v(t), strokeWidth: width, strokeLinecap: "round", strokeLinejoin: "round" });
/** Pivot for a rig part, in viewBox units (transform-box: view-box). */
export const pivot = (x: number, y: number): CSSProperties => ({ "--ox": `${x}px`, "--oy": `${y}px` } as CSSProperties);

export interface Palette { fur: Tok; shade: Tok; deep: Tok; inner: Tok }
export const PALETTE: Record<Species, Palette> = {
  cat: { fur: ["pet-cat-fur", "#FFF4D6"], shade: ["pet-cat-shade", "#F2DDB0"], deep: ["pet-cat-deep", "#D9BC86"], inner: ["pet-cat-inner", "#FBD5DA"] },
  fox: { fur: ["pet-fox-fur", "#FFC9A8"], shade: ["pet-fox-shade", "#F4A882"], deep: ["pet-fox-deep", "#D9875F"], inner: ["pet-fox-cream", "#FFF1E6"] },
  bunny: { fur: ["pet-bunny-fur", "#F3EEFF"], shade: ["pet-bunny-shade", "#DCD2F5"], deep: ["pet-bunny-deep", "#BDB0E3"], inner: ["pet-bunny-inner", "#FBD5DA"] },
};
export const FOX_CREAM: Tok = ["pet-fox-cream", "#FFF1E6"];
export const FOX_TIP: Tok = ["pet-fox-tip", "#6B4A3A"];

/** Head geometry every species shares; the face is placed from these numbers (BRIEF §1). */
export interface HeadGeo { cx: number; cy: number; rx: number; ry: number }

/** Gradients, clip paths and the static fur grain. Ids are prefixed per species. */
export function PetDefs({ species, head, body }: { species: Species; head: HeadGeo; body: string }) {
  const p = PALETTE[species], id = (s: string) => `${species}-${s}`;
  return <defs>
    <linearGradient id={id("fur")} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" style={{ stopColor: "#FFFFFF", stopOpacity: .18 }} />
      <stop offset=".35" style={{ stopColor: v(p.fur) }} />
      <stop offset="1" style={{ stopColor: v(p.fur) }} />
    </linearGradient>
    <linearGradient id={id("body")} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" style={{ stopColor: v(p.fur) }} />
      <stop offset="1" style={{ stopColor: v(p.shade) }} />
    </linearGradient>
    <radialGradient id={id("blush")}>
      <stop offset="0" style={{ stopColor: v(T.blush), stopOpacity: 1 }} />
      <stop offset="1" style={{ stopColor: v(T.blush), stopOpacity: 0 }} />
    </radialGradient>
    <clipPath id={id("head-clip")}><ellipse cx={head.cx} cy={head.cy} rx={head.rx} ry={head.ry} /></clipPath>
    <clipPath id={id("body-clip")}><path d={body} /></clipPath>
    <filter id={id("grain")} x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="7" />
      <feColorMatrix values="0 0 0 0 .45  0 0 0 0 .35  0 0 0 0 .25  0 0 0 .5 0" />
    </filter>
  </defs>;
}

/** Static fur grain (opacity <= 0.12), skipped for small renders via CSS. */
export function Grain({ species, clip }: { species: Species; clip: "head" | "body" }) {
  return <rect className="pet-grain" x="0" y="0" width="256" height="256" filter={`url(#${species}-grain)`}
    clipPath={`url(#${species}-${clip}-clip)`} opacity=".1" />;
}

/** Eyes, shines, nose, mouth, open mouth and blush, sized from the head (BRIEF §1). */
export function Face({ species, head, noseTok = T.nose }: { species: Species; head: HeadGeo; noseTok?: Tok }) {
  const w = head.rx * 2, top = head.cy - head.ry;
  const ey = top + head.ry * 2 * .57;               // 57% down the head: below the midline
  const dx = w * .46 / 2;                            // centers 46% of head width apart
  const er = w * .14 / 2;                            // eye width 14% of head width
  const ex = [head.cx - dx, head.cx + dx];
  const ny = ey + er * 1.15, nw = w * .05, mw = w * .11, my = ny + 6;
  const eye = (x: number, side: "l" | "r") => <g data-part={`eye-${side}`} style={pivot(x, ey)} key={side}>
    <g className="eye-open">
      <g className="pupil">
        <ellipse cx={x} cy={ey} rx={er} ry={er * 1.15} style={fill(T.eye)} />
        <circle cx={x + er * .38} cy={ey - er * .45} r={er * .35} style={fill(T.shine)} />
        <circle cx={x - er * .38} cy={ey + er * .45} r={er * .15} style={fill(T.shine)} />
      </g>
    </g>
    <path className="eye-happy" d={`M${x - er} ${ey + 3} Q${x} ${ey - er * 1.3} ${x + er} ${ey + 3}`} style={stroke(T.eye, 6)} />
    <path className="eye-closed" d={`M${x - er} ${ey - 1} Q${x} ${ey + er * .9} ${x + er} ${ey - 1}`} style={stroke(T.eye, 5)} />
  </g>;
  return <>
    <g data-part="blush">
      <ellipse cx={ex[0] - er * .9} cy={ny + 2} rx={er * 1.25} ry={er * .7} fill={`url(#${species}-blush)`} opacity=".55" />
      <ellipse cx={ex[1] + er * .9} cy={ny + 2} rx={er * 1.25} ry={er * .7} fill={`url(#${species}-blush)`} opacity=".55" />
    </g>
    <g data-part="eyes" style={pivot(head.cx, ey)}>{eye(ex[0], "l")}{eye(ex[1], "r")}</g>
    <path data-part="nose" d={`M${head.cx - nw / 2} ${ny} H${head.cx + nw / 2} Q${head.cx + nw * .3} ${ny + nw * .6} ${head.cx} ${ny + nw * .7} Q${head.cx - nw * .3} ${ny + nw * .6} ${head.cx - nw / 2} ${ny} Z`} style={fill(noseTok)} />
    <path data-part="mouth" d={`M${head.cx - mw / 2} ${my} q${mw / 4} ${mw * .35} ${mw / 2} 0 q${mw / 4} ${mw * .35} ${mw / 2} 0`} style={stroke(T.mouth, 4.5)} />
    <g data-part="mouth-open" style={pivot(head.cx, my + 2)}>
      <ellipse cx={head.cx} cy={my + 5} rx={mw * .32} ry={mw * .34} style={fill(T.mouth)} />
    </g>
  </>;
}

/** 8-unit rim light on the head's top-right (glass tint, opacity .6). */
export function Rim({ head }: { head: HeadGeo }) {
  const a = (deg: number) => [head.cx + head.rx * .92 * Math.cos(deg), head.cy - head.ry * .92 * Math.sin(deg)];
  const [x1, y1] = a(1.25), [x2, y2] = a(.35), [cx, cy] = a(.8);
  return <path data-part="rim" d={`M${x1} ${y1} Q${cx + 8} ${cy - 8} ${x2} ${y2}`} style={stroke(T.rim, 8)} opacity=".55" />;
}

export function Shadow({ cx = 128, cy = 242, rx = 84 }: { cx?: number; cy?: number; rx?: number }) {
  return <g data-part="shadow"><ellipse cx={cx} cy={cy} rx={rx} ry={10} style={fill(T.shadow)} /></g>;
}

/** Accessories unlocked by lifetime nights (3/7/14/30). Each is hidden unless the root
 *  carries data-acc-<name>. Positions come from the species' head and neck. */
export function Accessories({ head, neckY }: { head: HeadGeo; neckY: number }) {
  const top = head.cy - head.ry, l = head.cx - head.rx;
  const flower = (x: number, y: number, t: Tok, k: number) => <g key={k}>
    {[0, 72, 144, 216, 288].map((a) => <circle key={a} cx={x + 6 * Math.cos(a * Math.PI / 180)} cy={y + 6 * Math.sin(a * Math.PI / 180)} r={5} style={fill(t)} />)}
    <circle cx={x} cy={y} r={4} style={fill(T.star)} />
  </g>;
  return <g data-part="accessories">
    <g className="acc acc-scarf">
      <path d={`M${head.cx - 48} ${neckY - 6} Q${head.cx} ${neckY + 14} ${head.cx + 48} ${neckY - 6}`} style={stroke(T.mint, 14)} />
      <path d={`M${head.cx + 22} ${neckY + 2} l8 30`} style={stroke(T.mint, 12)} />
    </g>
    <g className="acc acc-star">
      <path d={starPath(l + head.rx * .3, top + head.ry * .62, 10)} style={fill(T.star)} />
    </g>
    <g className="acc acc-moon">
      <path d={`M${head.cx - 26} ${neckY + 18} a12 12 0 1 0 12 16 a9 9 0 1 1 -12 -16 Z`} style={fill(T.lavender)} />
    </g>
    <g className="acc acc-crown">
      {flower(head.cx - 30, top + 8, T.peach, 1)}{flower(head.cx, top + 2, T.lavender, 2)}{flower(head.cx + 30, top + 8, T.sky, 3)}
    </g>
  </g>;
}

function starPath(cx: number, cy: number, r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 10; i++) {
    const rr = i % 2 ? r * .5 : r, a = -Math.PI / 2 + i * Math.PI / 5;
    pts.push(`${(cx + rr * Math.cos(a)).toFixed(1)} ${(cy + rr * Math.sin(a)).toFixed(1)}`);
  }
  return `M${pts.join(" L")} Z`;
}

/** Wraps a species drawing in the shared svg root. */
export function PetSvg({ species, children }: { species: Species; children: ReactNode }) {
  return <svg className="pet-svg" viewBox="0 0 256 256" aria-hidden="true" focusable="false" data-species={species}>{children}</svg>;
}
