// Pure walking helpers. The pet walks only on wide screens without reduced motion, along
// the top edge of [data-pet-perch] panels, never over [data-pet-avoid], forms or focus.
import { WALK_MIN_WIDTH_PX } from "./petConfig";

export interface Box { left: number; top: number; width: number; height: number }
export interface Point { x: number; y: number }

export const canWalk = (viewportWidth: number, reducedMotion: boolean) => viewportWidth >= WALK_MIN_WIDTH_PX && !reducedMotion;

const overlaps = (a: Box, b: Box) => a.left < b.left + b.width && b.left < a.left + a.width && a.top < b.top + b.height && b.top < a.top + a.height;
export const avoids = (r: Box, avoid: readonly Box[]) => !avoid.some((a) => overlaps(r, a));

/** Perch spots: a point on the top edge of each visible perch panel, where the pet's
 *  box (size x size, feet on the edge) touches nothing to avoid. */
export function perchTargets(rects: readonly Box[], viewport: { width: number; height: number }, size: number, avoid: readonly Box[] = []): Point[] {
  const out: Point[] = [];
  for (const r of rects) {
    if (r.width < size * 2 || r.top < size || r.top > viewport.height - 40) continue;
    for (const f of [0.82, 0.18, 0.5]) {
      const x = r.left + r.width * f;
      const box = { left: x - size / 2, top: r.top - size, width: size, height: size };
      if (box.left < 0 || box.left + size > viewport.width) continue;
      if (avoids(box, avoid)) { out.push({ x, y: r.top }); break; }
    }
  }
  return out;
}

/** Move pos toward target at speed px/s over dt seconds; returns the new point and whether it arrived. */
export function stepToward(pos: Point, target: Point, speed: number, dt: number): { pos: Point; arrived: boolean } {
  const dx = target.x - pos.x, dy = target.y - pos.y, d = Math.hypot(dx, dy), step = speed * dt;
  if (d <= step || d === 0) return { pos: { ...target }, arrived: true };
  return { pos: { x: pos.x + dx / d * step, y: pos.y + dy / d * step }, arrived: false };
}
