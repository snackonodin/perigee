export interface Pt {
  t: number; // ms since epoch
  v: number | null; // null = gap (no estimate)
}

/** Keep at most `max` points for drawing. Each bucket of consecutive points becomes its
 *  min and max (in time order), so spikes survive decimation; gaps (null) are kept as one
 *  null so lines break where data is missing. */
export function decimate(points: Pt[], max: number): Pt[] {
  if (points.length <= max) return points;
  const buckets = Math.max(1, Math.floor(max / 2));
  const size = points.length / buckets;
  const out: Pt[] = [];
  for (let b = 0; b < buckets; b++) {
    const slice = points.slice(Math.floor(b * size), Math.floor((b + 1) * size));
    const vals = slice.filter((p) => p.v !== null);
    if (vals.length === 0) {
      if (slice.length) out.push({ t: slice[0].t, v: null });
      continue;
    }
    let lo = vals[0], hi = vals[0];
    for (const p of vals) {
      if ((p.v as number) < (lo.v as number)) lo = p;
      if ((p.v as number) > (hi.v as number)) hi = p;
    }
    if (lo === hi) out.push(lo);
    else out.push(...(lo.t <= hi.t ? [lo, hi] : [hi, lo]));
  }
  return out;
}

/** Drop the oldest entries beyond `keep` (bounded memory for long or fast replays). */
export function trimTo<T>(arr: T[], keep: number): void {
  if (arr.length > keep) arr.splice(0, arr.length - keep);
}
