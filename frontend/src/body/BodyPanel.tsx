// BodyPanel: the user's anatomical body figure (supplied 2026-11-15), adapted for Perigee.
// Changes from the supplied version: no absolute thresholds (heart or breathing rate ranges,
// score cut-offs), no red, no "Healthy / Moderate / Needs attention" and no scores. Each region
// shows the person's own baseline-relative state, decided by the host from engine data:
// Usual (teal), Changed from your usual (amber), or no reading / not compared (grey).
// The heart beats at the person's heart rate only when one exists; the lungs breathe at their
// own rate. Coloured glows were replaced by scale and stroke emphasis.
import React, { useId, useState } from "react";
import {
  BODY, HEART, HEART_RV, AORTA, PULMONARY, VENA_CAVA, AURICLE,
  GROOVE, CORONARY_MAIN, CORONARY_FINE, FIBERS, BRAIN, LUNG_L,
  LUNG_R, RIBS, STERNUM, CLAVICLE, VAGUS,
} from "./bodyPaths";

export type Region = "mind" | "respiration" | "autonomic" | "rest" | "cabin";
/** Baseline-relative state of one region. Never a score. */
export type Status = "usual" | "changed" | "none";

export interface SystemInfo {
  state: Status;
  /** e.g. "14.2 br/min"; omitted = "No reading" */
  reading?: string;
  /** label override for a grey region that has a value but no comparison ("Not compared yet") */
  label?: string;
}

export interface BodyPanelProps {
  /** beats per minute, only when a heart-rate reading exists; null = still heart, no reading */
  heartRate: number | null;
  /** the person's own breathing rate for the lung motion; null = still lungs */
  breathRate: number | null;
  systems?: Partial<Record<Region, SystemInfo>>;
  activeRegion?: Region | null;
  onSelect?: (region: Region) => void;
}

// teal for usual, amber for changed, grey for none. Never red.
const COLOR: Record<Status, string> = {
  usual: "#1E7F6E",
  changed: "#C98A1B",
  none: "#9AA8B0",
};

const LABEL: Record<Status, string> = {
  usual: "Usual",
  changed: "Changed from your usual",
  none: "No reading",
};

const FONT = "var(--font, system-ui, -apple-system, 'Segoe UI', sans-serif)";

const CARD_W = 212;
const CARD_H = 76;

const POINTS: {
  r: Region; name: string; dot: [number, number];
  label: [number, number]; side: "l" | "r"; line: boolean;
}[] = [
  { r: "mind", name: "Mind", dot: [400, 54], label: [606, 54], side: "r", line: true },
  { r: "cabin", name: "Cabin", dot: [628, 128], label: [650, 128], side: "r", line: false },
  { r: "respiration", name: "Respiration", dot: [372, 172], label: [194, 172], side: "l", line: true },
  { r: "autonomic", name: "Autonomic", dot: [416, 188], label: [606, 188], side: "r", line: true },
  { r: "rest", name: "Rest", dot: [400, 262], label: [194, 262], side: "l", line: true },
];

function Pair({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <g transform="translate(320 0) scale(-1 1)">{children}</g>
    </>
  );
}

export function BodyPanel({
  heartRate, breathRate, systems,
  activeRegion = null, onSelect,
}: BodyPanelProps) {
  const p = `bp${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const id = (n: string) => `${p}-${n}`;
  const url = (n: string) => `url(#${id(n)})`;
  const c = (n: string) => `${p}-c-${n}`;

  // animation tempo only (clamped so a bad value cannot make it frantic); no judgement from it
  const bpm = typeof heartRate === "number" && Number.isFinite(heartRate) && heartRate > 0 ? Math.min(180, Math.max(30, heartRate)) : null;
  const brpm = typeof breathRate === "number" && Number.isFinite(breathRate) && breathRate > 0 ? Math.min(40, Math.max(4, breathRate)) : null;
  const [hover, setHover] = useState<Region | null>(null);
  const focus = hover ?? activeRegion;

  const statusOf = (r: Region): Status => systems?.[r]?.state ?? "none";
  const labelOf = (r: Region) => systems?.[r]?.label ?? LABEL[statusOf(r)];
  const readingOf = (r: Region) => systems?.[r]?.reading ?? "No reading";

  const col = (r: Region) => COLOR[statusOf(r)];
  const reg = (r: Region) => ({
    className: focus === r ? `${c("reg")} ${c("pop")}` : c("reg"),
    style: {
      color: col(r),
      opacity: focus && focus !== r ? 0.38 : 1,
      "--pop": r === "autonomic" ? 1.13 : 1.08,
    } as React.CSSProperties,
    onMouseEnter: () => setHover(r),
    onMouseLeave: () => setHover(null),
  });

  const aura = (r: Region) =>
    focus === r ? 0.4 : statusOf(r) === "none" ? 0 : 0.16;

  const soft = (extra: object) => ({
    fill: "none",
    stroke: "#FFFFFF",
    strokeLinecap: "round" as const,
    ...extra,
  });

  const fp = POINTS.find((q) => q.r === focus);
  const fst: Status = fp ? statusOf(fp.r) : "none";
  const cardX = fp
    ? fp.side === "r"
      ? Math.min(fp.label[0] - 14, 800 - CARD_W - 8)
      : Math.max(fp.label[0] + 14 - CARD_W, 8)
    : 0;

  // the status card sits below its label, or above it when below would cover another label
  const covers = (top: number) => POINTS.some((q) => q !== fp && q.label[1] + 8 > top && q.label[1] - 20 < top + CARD_H
    && (q.side === "r" ? q.label[0] + 110 : q.label[0]) > cardX && (q.side === "r" ? q.label[0] : q.label[0] - 120) < cardX + CARD_W);
  const below = fp ? fp.label[1] + 18 : 0, above = fp ? fp.label[1] - 26 - CARD_H : 0;
  const cardY = fp && covers(below) && above >= 4 ? above : below;

  const css = `
    @keyframes ${id("pulse")} {
      0%,100% { transform:scale(1) }
      8% { transform:scale(1.12) }
      18% { transform:scale(1) }
    }
    @keyframes ${id("ring")} {
      0% { transform:scale(.6);opacity:.7 }
      100% { transform:scale(2.6);opacity:0 }
    }
    @keyframes ${id("breathe")} {
      0%,100% { transform:scale(.99,.985) }
      50% { transform:scale(1.02,1.03) }
    }
    @keyframes ${id("scan")} {
      from { transform:translateY(-12px) }
      to { transform:translateY(640px) }
    }
    @keyframes ${id("ping")} {
      0% { transform:scale(.8);opacity:.9 }
      100% { transform:scale(1.6);opacity:0 }
    }
    @keyframes ${id("card")} {
      from { opacity:0;transform:translateY(5px) }
      to { opacity:1;transform:none }
    }
    .${c("beat")} {
      transform-box:fill-box;transform-origin:center;
      animation:${id("pulse")} calc(60s / var(--bpm,72)) ease-in-out infinite;
    }
    .${c("ring")} {
      transform-box:fill-box;transform-origin:center;
      animation:${id("ring")} calc(60s / var(--bpm,72)) ease-out infinite;
    }
    .${c("lungs")} {
      transform-box:fill-box;transform-origin:center;
      animation:${id("breathe")} calc(60s / var(--brpm,16)) ease-in-out infinite;
    }
    .${c("scan")} { animation:${id("scan")} 6s linear infinite }
    .${c("ping")} {
      transform-box:fill-box;transform-origin:center;
      animation:${id("ping")} 1.4s ease-out infinite;
    }
    .${c("card")} { animation:${id("card")} .22s ease-out both }
    .${c("reg")} {
      transition:transform .32s cubic-bezier(.2,.8,.2,1),opacity .25s,filter .3s;
      transform-box:fill-box;transform-origin:center;
    }
    .${c("pop")} {
      transform:scale(var(--pop,1.1));
    }
    .${c("pt")} {
      cursor:pointer;outline:none;
      transition:opacity .2s;
    }
    .${c("pt")}:hover .${c("dot")} {
      stroke-width:2.4;
    }
    .${c("pt")}:focus-visible .${c("dot")} {
      stroke:#5B4BDB;stroke-width:3;
    }
    @media(prefers-reduced-motion:reduce) {
      .${c("beat")},.${c("ring")},.${c("lungs")},
      .${c("scan")},.${c("ping")},.${c("card")} { animation:none }
      .${c("ring")},.${c("scan")} { display:none }
      .${c("reg")} { transition:none }
    }
  `;

  return (
    <svg
      viewBox="0 0 800 640"
      role="group"
      aria-label="Interactive anatomical body and health systems"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        width: "100%", height: "100%", overflow: "visible",
        "--bpm": bpm ?? 60, "--brpm": brpm ?? 16,
      } as React.CSSProperties}
    >
      <style>{css}</style>

      <defs>
        <linearGradient id={id("fill")} gradientUnits="userSpaceOnUse" x1="0" y1="18" x2="0" y2="633">
          <stop offset="0%" stopColor="#BFE9D6" stopOpacity=".6" />
          <stop offset="48%" stopColor="#BFE0F5" stopOpacity=".6" />
          <stop offset="100%" stopColor="#D9D0F5" stopOpacity=".6" />
        </linearGradient>
        <linearGradient id={id("rim")} gradientUnits="userSpaceOnUse" x1="90" y1="35" x2="225" y2="610">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="48%" stopColor="#BFE9E0" />
          <stop offset="100%" stopColor="#1E7F6E" />
        </linearGradient>
        <linearGradient id={id("lung")} gradientUnits="userSpaceOnUse" x1="135" y1="145" x2="185" y2="230">
          <stop offset="0%" stopColor="#A9EEE2" stopOpacity=".58" />
          <stop offset="100%" stopColor="#BFE0F5" stopOpacity=".24" />
        </linearGradient>
        <radialGradient id={id("heart")} gradientUnits="userSpaceOnUse" cx="-8" cy="-8" r="34">
          <stop offset="0%" stopColor="#FFE3D3" />
          <stop offset="30%" stopColor="#FFC9A8" />
          <stop offset="62%" stopColor="#F4A882" />
          <stop offset="100%" stopColor="#B86A45" />
        </radialGradient>
        <linearGradient id={id("vessel")} x1="0" y1="1" x2="1" y2="0">
          <stop offset="0%" stopColor="#F4B08C" />
          <stop offset="100%" stopColor="#C27250" />
        </linearGradient>
        <linearGradient id={id("scan")} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1E7F6E" stopOpacity="0" />
          <stop offset="100%" stopColor="#1E7F6E" stopOpacity=".45" />
        </linearGradient>
        <radialGradient id={id("bg")} gradientUnits="userSpaceOnUse" cx="400" cy="330" r="270">
          <stop offset="0%" stopColor="#D9D0F5" stopOpacity=".5" />
          <stop offset="100%" stopColor="#D9D0F5" stopOpacity="0" />
        </radialGradient>

        <filter id={id("edge")}><feGaussianBlur stdDeviation="4" /></filter>
        <filter id={id("soft")}><feGaussianBlur stdDeviation="5" /></filter>
        <filter id={id("fine")}><feGaussianBlur stdDeviation=".4" /></filter>
        <filter id={id("shadow")}><feGaussianBlur stdDeviation="7" /></filter>
        <filter id={id("hglow")}><feGaussianBlur stdDeviation="5" /></filter>
        <filter id={id("hblur")}><feGaussianBlur stdDeviation="1.1" /></filter>
        <filter id={id("hsoft")}><feGaussianBlur stdDeviation="2.2" /></filter>
        <clipPath id={id("clip")}><path d={BODY} /></clipPath>
        <clipPath id={id("hclip")}><path d={HEART} /></clipPath>
      </defs>

      <circle cx="400" cy="330" r="270" fill={url("bg")} />
      {[215, 300].map((r, i) => (
        <circle
          key={r} cx="400" cy="320" r={r} fill="none"
          stroke={focus === "cabin" ? col("cabin") : "#1E7F6E"}
          strokeOpacity={focus === "cabin" ? .65 - i * .2 : .12}
          strokeWidth={focus === "cabin" ? 2.2 : 1}
          style={{ transition: "all .3s" }}
        />
      ))}

      <g transform="translate(240 0)">
        <ellipse cx="160" cy="634" rx="52" ry="4" fill="#1E7F6E" opacity=".22" filter={url("shadow")} />
        <path d={BODY} fill={url("fill")} />

        <g clipPath={url("clip")}>
          <path d={BODY} fill="none" stroke="white" strokeWidth="8" opacity=".5" filter={url("edge")} />

          {/* Glass shading and anatomical highlights */}
          <g filter={url("soft")}>
            <Pair>
              <ellipse cx="212" cy="150" rx="17" ry="23" fill="white" opacity=".16" />
              <ellipse cx="186" cy="388" rx="17" ry="52" fill="white" opacity=".15" />
              <ellipse cx="185" cy="505" rx="10" ry="36" fill="#1E7F6E" opacity=".13" />
              <ellipse cx="120" cy="250" rx="12" ry="35" fill="white" opacity=".10" />
            </Pair>
            <ellipse cx="160" cy="250" rx="20" ry="26" fill="white" opacity=".15" />
          </g>
          <g {...soft({ opacity: .68, filter: url("soft") })}>
            <Pair>
              <path d="M216 145 C222 160 224 173 227 184" strokeWidth="3" />
              <path d="M194 353 C199 371 201 393 200 413" strokeWidth="3.5" />
            </Pair>
          </g>
          <circle cx="145" cy="39" r="2.2" fill="white" opacity=".85" filter={url("fine")} />

          {/* Nerve pathways */}
          <g fill="none" stroke="#CDBEF2" strokeWidth=".9" strokeLinecap="round" opacity=".7">
            <Pair>
              <path d="M222 150 C230 190 244 224 258 252 C264 268 268 282 271 298" />
              <path d="M242 214 C247 217 250 222 251 228 M257 252 C262 256 264 262 264 268" />
              <path d="M170 330 C177 362 182 396 184 430 C186 470 186 520 182 586" />
              <path d="M180 550 C187 559 187 572 184 580" />
            </Pair>
          </g>
          <path
            d={VAGUS} fill="none" stroke="#B9A6F0"
            strokeLinecap="round" strokeWidth={focus === "autonomic" ? 2.2 : 1.1}
            opacity={focus === "autonomic" ? 1 : .7}
            style={{ transition: "all .3s" }}
          />

          {/* Mind: anatomical brain */}
          <g {...reg("mind")}>
            <ellipse cx="160" cy="48" rx="34" ry="28" fill={col("mind")} opacity={aura("mind")} filter={url("soft")} pointerEvents="none" />
            <path d={BRAIN.outline} fill="#FFFFFF" fillOpacity=".25" stroke="#1E7F6E" strokeOpacity=".6" strokeWidth=".9" />
            <g fill="none" stroke="#FFFFFF" strokeWidth=".8" strokeLinecap="round" opacity=".8">
              {BRAIN.folds.map((d) => <path key={d} d={d} />)}
            </g>
          </g>

          {/* Ribcage: supplied body-proportioned ten rib pairs */}
          <g fill="none" stroke="#1E7F6E" strokeWidth="1.1" strokeOpacity=".33" filter={url("fine")}>
            <Pair>{RIBS.map((d) => <path key={d} d={d} />)}</Pair>
          </g>
          <g {...soft({ strokeWidth: 1.5, opacity: .44 })}>
            <Pair>{RIBS.map((d) => <path key={d} d={d} />)}</Pair>
          </g>

          {/* Spine */}
          <g filter={url("fine")}>
            {Array.from({ length: 14 }, (_, i) => {
              const w = 6 + i * .16, h = 4.5 + i * .13;
              return (
                <rect key={i} x={160 - w / 2} y={106 + i * 13.5}
                  width={w} height={h} rx={h / 2}
                  fill="#FFFFFF" fillOpacity=".55" stroke="#1E7F6E"
                  strokeOpacity=".48" strokeWidth=".65" />
              );
            })}
          </g>

          {/* Respiration: proportional lungs with animated breathing */}
          <g {...reg("respiration")}>
            <ellipse cx="160" cy="182" rx="56" ry="46" fill={col("respiration")} opacity={aura("respiration")} filter={url("soft")} pointerEvents="none" />
            <g transform="translate(160 182) scale(1.3 .93) translate(-160 -182)">
              <g className={brpm ? c("lungs") : undefined}>
                {[LUNG_L, LUNG_R].map((d) => (
                  <path key={d} d={d} fill={url("lung")} stroke="#FFFFFF" strokeWidth=".8" strokeOpacity=".65" />
                ))}
                <path d="M145 166 C148 176 148 188 143 198 M175 166 C172 176 172 188 177 198"
                  fill="none" stroke="#FFFFFF" strokeWidth=".8" opacity=".6" />
              </g>
            </g>
          </g>

          {/* Rest: core region */}
          <g {...reg("rest")}>
            <ellipse cx="160" cy="262" rx="36" ry="28" fill={col("rest")} opacity={aura("rest")} filter={url("soft")} pointerEvents="none" />
            <ellipse cx="160" cy="262" rx="30" ry="22" fill="none"
              stroke="currentColor" strokeWidth="1.2" strokeDasharray="3 4"
              opacity={focus === "rest" ? .9 : 0} />
          </g>

          {/* Autonomic: layered heart, vessels and coronary anatomy */}
          <g {...reg("autonomic")}>
            <ellipse cx="176" cy="188" rx="30" ry="32" fill={col("autonomic")} opacity={aura("autonomic")} filter={url("soft")} pointerEvents="none" />
            <g transform="translate(176 188) rotate(12) scale(.95)">
              {bpm && <circle className={c("ring")} r="15" fill="none" stroke="#E0956C" strokeWidth="1.3" />}
              <path d={HEART} fill="#D9875F" opacity=".32" filter={url("hglow")} />
              <g className={bpm ? c("beat") : undefined}>
                {/* Great vessels behind the myocardium */}
                <g fill={url("vessel")} stroke="#9A5A3C" strokeWidth=".55" strokeOpacity=".55">
                  <path d={VENA_CAVA} />
                  <path d={AORTA} />
                  <path d={PULMONARY} />
                </g>

                {/* Main muscle wall */}
                <path d={HEART} fill={url("heart")} stroke="#A8603F" strokeWidth=".65" strokeOpacity=".8" />

                <g clipPath={url("hclip")}>
                  <path d={HEART_RV} fill="#8A4A2E" opacity=".27" filter={url("hblur")} />
                  <path d={GROOVE} fill="none" stroke="#7A3F25" strokeWidth="1.8" opacity=".48" />
                  <g fill="none" stroke="#FFEBEE" strokeWidth=".5" opacity=".22">
                    {FIBERS.map((d) => <path key={d} d={d} />)}
                  </g>
                  <g fill="none" stroke="#B5643F" strokeWidth="1" strokeLinecap="round" opacity=".82">
                    {CORONARY_MAIN.map((d) => <path key={d} d={d} />)}
                  </g>
                  <g fill="none" stroke="#C27250" strokeWidth=".6" strokeLinecap="round" opacity=".72">
                    {CORONARY_FINE.map((d) => <path key={d} d={d} />)}
                  </g>
                  <ellipse cx="6.5" cy="-5" rx="6.5" ry="6" fill="#FFFFFF" opacity=".22" filter={url("hsoft")} />
                </g>
                <path d={AURICLE} fill="#F4B08C" stroke="#C27250" strokeWidth=".6" />
                <circle cx="4.5" cy="-6.5" r="1.3" fill="#FFFFFF" opacity=".8" filter={url("fine")} />
              </g>
            </g>
          </g>

          {/* Sternum and clavicles in front of the organs */}
          <path d={STERNUM} fill="#FFFFFF" fillOpacity=".2" stroke="#1E7F6E" strokeOpacity=".5" strokeWidth=".8" />
          <g {...soft({ strokeWidth: 1.4, opacity: .7 })}>
            <Pair><path d={CLAVICLE} /></Pair>
          </g>

          <g className={c("scan")}>
            <rect x="0" y="-12" width="320" height="12" fill={url("scan")} />
            <rect x="0" y="-1.5" width="320" height="1.5" fill="#1E7F6E" opacity=".8" />
          </g>
        </g>

        <path d={BODY} fill="none" stroke={url("rim")} strokeWidth="1.25" strokeLinejoin="round" />
      </g>

      {/* Interactive system markers */}
      {POINTS.map((pt) => {
        const st = statusOf(pt.r);
        const color = COLOR[st];
        const on = focus === pt.r;
        const [dx, dy] = pt.dot;
        const [lx, ly] = pt.label;
        const right = pt.side === "r";
        const sx = right ? 1 : -1;
        const fire = () => onSelect?.(pt.r);

        return (
          <g
            key={pt.r}
            className={c("pt")}
            role="button"
            tabIndex={0}
            aria-label={`${pt.name}: ${labelOf(pt.r)}${systems?.[pt.r]?.reading ? `, ${systems[pt.r]!.reading}` : ""}`}
            aria-pressed={activeRegion === pt.r}
            onMouseEnter={() => setHover(pt.r)}
            onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(pt.r)}
            onBlur={() => setHover(null)}
            onClick={fire}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fire();
              }
            }}
          >
            <rect
              x={right ? dx - 16 : lx - 120}
              y={dy - 16}
              width={right ? lx + 110 - (dx - 16) : dx + 16 - (lx - 120)}
              height="32"
              fill="transparent"
            />
            {pt.line && (
              <>
                <line
                  x1={dx + sx * 12} y1={dy}
                  x2={lx - sx * 16} y2={ly}
                  stroke={on ? color : "#9AA7B0"}
                  strokeWidth={on ? 1.6 : 1.1}
                />
                <circle cx={lx - sx * 16} cy={ly} r="2.6" fill={on ? color : "#9AA7B0"} />
              </>
            )}
            {on && (
              <circle className={c("ping")} cx={dx} cy={dy} r="17"
                fill="none" stroke={color} strokeWidth="2" />
            )}
            {activeRegion === pt.r && (
              <circle cx={dx} cy={dy} r="17" fill="none" stroke="#5B4BDB" strokeWidth="2.2" />
            )}
            <circle
              className={c("dot")}
              cx={dx} cy={dy} r={on ? 12.5 : 11}
              fill={color}
              fillOpacity={st === "none" ? .5 : .92}
              stroke="#1F3B36" strokeWidth="1.4"
              style={{ transition: "r .2s" }}
            />
            <text
              x={lx} y={ly + 7}
              textAnchor={right ? "start" : "end"}
              fontSize="20" fontFamily={FONT}
              fill={on ? color : "#1B2B2A"}
              fontWeight={on ? 600 : 400}
              style={{ transition: "fill .2s" }}
            >
              {pt.name}
            </text>
          </g>
        );
      })}

      {/* Status card follows the hovered or selected point */}
      {fp && (
        <g transform={`translate(${cardX} ${cardY})`} pointerEvents="none">
          <g className={c("card")}>
            <rect width={CARD_W} height={CARD_H} rx="12"
              fill="#FFFFFF" fillOpacity=".97"
              stroke={COLOR[fst]} strokeWidth="1.5" />
            <text x="16" y="23" fontSize="14" fontWeight="600"
              fontFamily={FONT} fill="#1B2B2A">
              {fp.name}
            </text>
            <circle cx="21" cy="40" r="4.5" fill={COLOR[fst]} />
            <text x="32" y="44" fontSize="12.5" fontWeight="600"
              fontFamily={FONT} fill="#33504A">
              {labelOf(fp.r)}
            </text>
            <text x="16" y="63" fontSize="12.5"
              fontFamily={FONT} fill="#5E7771">
              {readingOf(fp.r)}
            </text>
          </g>
        </g>
      )}
    </svg>
  );
}
