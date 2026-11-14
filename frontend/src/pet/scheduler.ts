// The ONLY place in src/pet/ that creates timers. clearAll() is called when the pet
// unmounts or the safety screen opens; count() lets tests prove nothing is left.
export interface Scheduler {
  after(ms: number, fn: () => void): () => void;
  every(minMs: number, maxMs: number, fn: () => void): () => void;
  clearAll(): void;
  count(): number;
}

export function createScheduler(random: () => number = Math.random): Scheduler {
  const live = new Set<ReturnType<typeof setTimeout>>();
  const after = (ms: number, fn: () => void) => {
    const id = setTimeout(() => { live.delete(id); fn(); }, ms);
    live.add(id);
    return () => { clearTimeout(id); live.delete(id); };
  };
  return {
    after,
    every(minMs, maxMs, fn) {
      let cancel = () => {};
      let stopped = false;
      const next = () => { if (!stopped) cancel = after(minMs + random() * (maxMs - minMs), () => { fn(); next(); }); };
      next();
      return () => { stopped = true; cancel(); };
    },
    clearAll() { for (const id of live) clearTimeout(id); live.clear(); },
    count: () => live.size,
  };
}
