// rAF controller for the frost: runs only while the trail has points and the tab is
// visible; stops itself when the trail empties; resumes on visibilitychange.
export interface FrostLoopDeps {
  draw(now: number): void;
  size(): number;
  isHidden(): boolean;
  raf(cb: (t: number) => void): number;
  caf(id: number): void;
  doc?: Pick<Document, "addEventListener" | "removeEventListener">;
}

export function createFrostLoop(d: FrostLoopDeps) {
  let id = 0;
  const frame = (t: number) => {
    id = 0;
    d.draw(t);
    if (d.size() > 0 && !d.isHidden()) id = d.raf(frame);
  };
  const kick = () => { if (!id && d.size() > 0 && !d.isHidden()) id = d.raf(frame); };
  const stop = () => { if (id) d.caf(id); id = 0; };
  const onVis = () => (d.isHidden() ? stop() : kick());
  d.doc?.addEventListener("visibilitychange", onVis);
  return {
    kick, stop,
    running: () => id !== 0,
    dispose() { stop(); d.doc?.removeEventListener("visibilitychange", onVis); },
  };
}
