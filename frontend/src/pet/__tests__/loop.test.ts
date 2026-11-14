import { describe, expect, it, vi } from "vitest";
import { createFrostLoop } from "../frost/loop";
import { createTrail } from "../frost/trailBuffer";

function harness() {
  const trail = createTrail();
  let hidden = false;
  const queue = new Map<number, (t: number) => void>();
  let next = 1;
  const listeners: Record<string, () => void> = {};
  const raf = vi.fn((cb: (t: number) => void) => { const id = next++; queue.set(id, cb); return id; });
  const caf = vi.fn((id: number) => { queue.delete(id); });
  const loop = createFrostLoop({
    draw: (now) => trail.prune(now, 30), size: () => trail.size(), isHidden: () => hidden, raf, caf,
    doc: { addEventListener: (n: string, f: () => void) => { listeners[n] = f; }, removeEventListener: () => {} } as unknown as Document,
  });
  const flush = (t: number) => { const cbs = [...queue.values()]; queue.clear(); cbs.forEach((cb) => cb(t)); };
  return { trail, loop, raf, caf, flush, setHidden: (h: boolean) => { hidden = h; listeners.visibilitychange?.(); } };
}

describe("frost rAF loop", () => {
  it("requests no frame while the trail is empty", () => {
    const h = harness();
    h.loop.kick();
    expect(h.raf).not.toHaveBeenCalled();
  });
  it("requests frames after a point is added and stops after the last prune", () => {
    const h = harness();
    h.trail.add(0, 0, 0); h.loop.kick();
    expect(h.raf).toHaveBeenCalledTimes(1);
    h.flush(1000);
    expect(h.loop.running()).toBe(true);
    h.flush(31000); // point is now older than T: pruned, loop stops
    expect(h.loop.running()).toBe(false);
    const calls = h.raf.mock.calls.length;
    h.flush(32000);
    expect(h.raf.mock.calls.length).toBe(calls);
  });
  it("does not run while hidden and resumes when visible", () => {
    const h = harness();
    h.trail.add(0, 0, 0);
    h.setHidden(true);
    h.loop.kick();
    expect(h.raf).not.toHaveBeenCalled();
    h.setHidden(false);
    expect(h.raf).toHaveBeenCalledTimes(1);
    h.setHidden(true);
    expect(h.caf).toHaveBeenCalled();
    expect(h.loop.running()).toBe(false);
  });
});
