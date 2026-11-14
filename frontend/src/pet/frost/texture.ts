// Frost texture tile, drawn once per page: tint at alpha <= 0.55, ~3% fine noise, and 40
// seeded crystal strokes (mulberry32, seed 7) so it looks the same every load.
import { FROST_TINT_ALPHA } from "../petConfig";
import { mulberry32 } from "./prng";

let cached: HTMLCanvasElement | null = null;

export function makeFrostTile(size = 256, seed = 7): HTMLCanvasElement | null {
  if (cached) return cached;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  let g: CanvasRenderingContext2D | null = null;
  try { g = c.getContext("2d"); } catch { g = null; }
  if (!g) return null;
  const rnd = mulberry32(seed);
  g.fillStyle = `rgba(234,244,251,${Math.min(FROST_TINT_ALPHA, .55)})`; // --frost-tint #EAF4FB
  g.fillRect(0, 0, size, size);
  const noise = Math.round(size * size * .03);
  for (let i = 0; i < noise; i++) {
    g.fillStyle = `rgba(255,255,255,${(rnd() * .08).toFixed(3)})`;
    g.fillRect(Math.floor(rnd() * size), Math.floor(rnd() * size), 1, 1);
  }
  g.strokeStyle = "rgba(255,255,255,.25)";
  g.lineWidth = 1;
  g.lineCap = "round";
  for (let i = 0; i < 40; i++) {
    const x = rnd() * size, y = rnd() * size, a = rnd() * Math.PI * 2, len = 6 + rnd() * 12;
    const ex = x + Math.cos(a) * len, ey = y + Math.sin(a) * len;
    g.beginPath(); g.moveTo(x, y); g.lineTo(ex, ey);
    const branches = 1 + Math.floor(rnd() * 3);
    for (let b = 0; b < branches; b++) {
      const t = .3 + rnd() * .5, bx = x + (ex - x) * t, by = y + (ey - y) * t, ba = a + (rnd() < .5 ? -1 : 1) * (.5 + rnd() * .5), bl = len * (.3 + rnd() * .3);
      g.moveTo(bx, by); g.lineTo(bx + Math.cos(ba) * bl, by + Math.sin(ba) * bl);
    }
    g.stroke();
  }
  cached = c;
  return c;
}
