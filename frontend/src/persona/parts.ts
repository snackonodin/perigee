// The persona questions in five themed parts (psyche_p1..p5, 12 statements each). Items are
// shuffled within a part, stable per person (seed = user id + part id), so a reload never
// reorders them half-way. Four statements per page.

export const PARTS = [
  { id: "psyche_p1", name: "Mind at rest" },
  { id: "psyche_p2", name: "Feelings and reactions" },
  { id: "psyche_p3", name: "People and authority" },
  { id: "psyche_p4", name: "Focus and motivation" },
  { id: "psyche_p5", name: "Body and feedback" },
] as const;
export type PartId = (typeof PARTS)[number]["id"];
export const PART_IDS: readonly string[] = PARTS.map((p) => p.id);
export const ITEMS_PER_PAGE = 4;

/** 32-bit FNV-1a hash of a string: the shuffle seed. */
function hash(s: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return h >>> 0;
}
/** mulberry32: small deterministic PRNG */
function rng(seed: number): () => number {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Fisher-Yates with a seed from (user, part): the same person always sees the same order. */
export function stableShuffle<T>(items: readonly T[], userId: string, partId: string): T[] {
  const out = [...items], rnd = rng(hash(`${userId}:${partId}`));
  for (let i = out.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [out[i], out[j]] = [out[j], out[i]]; }
  return out;
}

/** The next part to suggest: the first one not done (after `after`, wrapping), or null when all are done. */
export function nextPart(done: readonly string[], after?: string): PartId | null {
  const start = after ? PART_IDS.indexOf(after) + 1 : 0;
  for (let k = 0; k < PARTS.length; k++) {
    const p = PARTS[(start + k) % PARTS.length].id;
    if (!done.includes(p) && p !== after) return p;
  }
  return null;
}
