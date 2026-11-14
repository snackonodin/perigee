import { describe, expect, it } from "vitest";
import { createFollow, laggedPointer, notePointer, stepFollow } from "../follow";
import { FOLLOW_DEADZONE_PX, FOLLOW_LAG_MS } from "../petConfig";

const env = (random = () => 0.99) => ({ size: 96, viewport: { width: 1280, height: 800 }, random });
const run = (s: ReturnType<typeof createFollow>, from: number, ms: number, e = env()) => {
  let t = from;
  for (; t < from + ms; t += 16) stepFollow(s, t, 0.016, e);
  return t;
};

describe("cursor follow", () => {
  it("chases the pointer with lag and stops in the dead zone, short of the cursor", () => {
    const s = createFollow({ x: 1200, y: 720 });
    notePointer(s, 300, 300, 0);
    stepFollow(s, 10, 0.016, env());
    expect(s.pos.x).toBeGreaterThan(1190); // barely moved on the first frame: eased start
    run(s, 16, 6000);
    const d = Math.hypot(s.pos.x - 300, s.pos.y - 300);
    expect(d).toBeGreaterThan(48 + 24); // never on top of the cursor (radius + 24 px)
    expect(d).toBeLessThanOrEqual(FOLLOW_DEADZONE_PX + 1);
    expect(stepFollow(s, 7000, 0.016, env()).moving).toBe(false);
  });
  it("uses where the pointer was, not where it is", () => {
    const s = createFollow({ x: 0, y: 0 });
    notePointer(s, 100, 100, 0);
    notePointer(s, 900, 100, FOLLOW_LAG_MS - 50);
    expect(laggedPointer(s, FOLLOW_LAG_MS)).toEqual({ x: 100, y: 100 });
    expect(laggedPointer(s, FOLLOW_LAG_MS * 2)).toEqual({ x: 900, y: 100 });
  });
  it("takes detours on long chases and stays inside the viewport", () => {
    const s = createFollow({ x: 1200, y: 720 });
    notePointer(s, 60, 60, 0);
    let detoured = false;
    for (let t = 0; t < 4000; t += 16) {
      stepFollow(s, t, 0.016, env(() => 0.001));
      detoured ||= !!s.detour;
      expect(s.pos.x).toBeGreaterThanOrEqual(56); expect(s.pos.y).toBeGreaterThanOrEqual(56);
      expect(s.pos.x).toBeLessThanOrEqual(1224); expect(s.pos.y).toBeLessThanOrEqual(744);
    }
    expect(detoured).toBe(true);
  });
  it("does not move without a pointer", () => {
    const s = createFollow({ x: 500, y: 500 });
    expect(stepFollow(s, 0, 0.016, env()).moving).toBe(false);
    expect(s.pos).toEqual({ x: 500, y: 500 });
  });
});
