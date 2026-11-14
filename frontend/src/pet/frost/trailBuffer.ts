// Ring buffer of trail points {x, y, born}. Cap 300; a point is added only when the pet
// moved >= 6 CSS px since the last one; points older than T seconds are dropped.
export interface TrailPoint { x: number; y: number; born: number }
export interface Trail {
  add(x: number, y: number, now: number, minStep?: number): boolean;
  prune(now: number, T: number): void;
  points(): TrailPoint[];
  size(): number;
  clear(): void;
}

export function createTrail(cap = 300): Trail {
  const buf: TrailPoint[] = [];
  let head = 0; // index of the oldest point once full
  let last: TrailPoint | null = null;
  return {
    add(x, y, now, minStep = 6) {
      if (last && Math.hypot(x - last.x, y - last.y) < minStep) return false;
      const p = { x, y, born: now };
      if (buf.length < cap) buf.push(p); else { buf[head] = p; head = (head + 1) % cap; }
      last = p;
      return true;
    },
    prune(now, T) {
      const keep = this.points().filter((p) => (now - p.born) / 1000 < T);
      buf.length = 0; head = 0; buf.push(...keep);
      if (!keep.length) last = null;
    },
    points: () => (buf.length < cap ? buf.slice() : [...buf.slice(head), ...buf.slice(0, head)]),
    size: () => buf.length,
    clear() { buf.length = 0; head = 0; last = null; },
  };
}

/** Brush radius and alpha for a point of a given age (seconds). */
export const brush = (r0: number, age: number, T: number) => {
  const k = Math.max(0, 1 - age / T);
  return { r: r0 * k, alpha: k };
};
