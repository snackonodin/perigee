// Frost behind the [data-pet-perch] glass tiles (below their text: the canvas sits under
// the page content and shows through the glass). The pet's path clears it; it re-forms
// from the edges inward over T seconds. Unmounted under safety; not used under reduced motion.
import { useEffect, useRef, type MutableRefObject } from "react";
import { createPortal } from "react-dom";
import { FROST_BRUSH_R0, FROST_REFORM_S } from "../petConfig";
import { createFrostLoop } from "./loop";
import { makeFrostTile } from "./texture";
import { brush, type Trail } from "./trailBuffer";
import "./frost.css";

export const backingSize = (cssW: number, cssH: number, dpr: number) => {
  const k = 0.5 * Math.min(dpr, 2);
  return { width: Math.round(cssW * k), height: Math.round(cssH * k), k };
};

export function FrostTrail({ trail, kickRef, T = FROST_REFORM_S, r0 = FROST_BRUSH_R0 }: {
  trail: Trail; kickRef: MutableRefObject<(() => void) | null>; T?: number; r0?: number;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = canvas.current;
    let g: CanvasRenderingContext2D | null = null;
    try { g = c?.getContext("2d") ?? null; } catch { g = null; }
    const tile = makeFrostTile();
    if (!c || !g || !tile) return;
    let k = 1;
    const resize = () => {
      const s = backingSize(window.innerWidth, window.innerHeight, window.devicePixelRatio || 1);
      c.width = s.width; c.height = s.height; k = s.k;
      draw(performance.now());
    };
    const pattern = g.createPattern(tile, "repeat");
    const perches = () => [...document.querySelectorAll("[data-pet-perch]")].map((el) => el.getBoundingClientRect());
    const draw = (now: number) => {
      trail.prune(now, T);
      g!.globalCompositeOperation = "source-over";
      g!.clearRect(0, 0, c.width, c.height);
      g!.save();
      g!.beginPath();
      for (const r of perches()) g!.roundRect?.(r.left * k, r.top * k, r.width * k, r.height * k, 16 * k) ?? g!.rect(r.left * k, r.top * k, r.width * k, r.height * k);
      g!.clip();
      g!.fillStyle = pattern ?? "rgba(234,244,251,.55)";
      g!.fillRect(0, 0, c.width, c.height);
      g!.globalCompositeOperation = "destination-out";
      for (const p of trail.points()) {
        const { r, alpha } = brush(r0, (now - p.born) / 1000, T);
        if (r <= 0) continue;
        const x = p.x * k, y = p.y * k, rr = r * k;
        const grad = g!.createRadialGradient(x, y, 0, x, y, rr);
        grad.addColorStop(0, `rgba(0,0,0,${alpha})`); grad.addColorStop(1, "rgba(0,0,0,0)");
        g!.fillStyle = grad;
        g!.beginPath(); g!.arc(x, y, rr, 0, Math.PI * 2); g!.fill();
      }
      g!.restore();
      g!.globalCompositeOperation = "source-over";
    };
    const loop = createFrostLoop({
      draw, size: () => trail.size(), isHidden: () => document.hidden,
      raf: (cb) => requestAnimationFrame(cb), caf: (id) => cancelAnimationFrame(id), doc: document,
    });
    kickRef.current = loop.kick;
    const redraw = () => { if (!loop.running()) draw(performance.now()); };
    resize();
    window.addEventListener("resize", resize);
    window.addEventListener("scroll", redraw, { passive: true });
    return () => {
      loop.dispose(); trail.clear(); kickRef.current = null;
      window.removeEventListener("resize", resize); window.removeEventListener("scroll", redraw);
    };
  }, [trail, kickRef, T, r0]);
  return createPortal(<canvas ref={canvas} className="pet-frost" aria-hidden="true" />, document.body);
}
