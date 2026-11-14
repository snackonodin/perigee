import { describe, expect, it } from "vitest";
import { backingSize } from "../frost/FrostTrail";
import { brush, createTrail } from "../frost/trailBuffer";

describe("frost trail buffer", () => {
  it("caps at 300 and overwrites the oldest", () => {
    const t = createTrail(300);
    for (let i = 0; i < 350; i++) t.add(i * 10, 0, i);
    expect(t.size()).toBe(300);
    expect(t.points()[0].born).toBe(50);
    expect(t.points().at(-1)!.born).toBe(349);
  });
  it("adds a point only after >= 6 px of movement", () => {
    const t = createTrail();
    expect(t.add(0, 0, 0)).toBe(true);
    expect(t.add(3, 4, 1)).toBe(false); // 5 px
    expect(t.add(6, 0, 2)).toBe(true);
    expect(t.size()).toBe(2);
  });
  it("prune drops points with age >= T", () => {
    const t = createTrail();
    t.add(0, 0, 0); t.add(10, 0, 10000); t.add(20, 0, 20000);
    t.prune(30000, 30);
    expect(t.points().map((p) => p.born)).toEqual([10000, 20000]);
    t.prune(60000, 30);
    expect(t.size()).toBe(0);
  });
  it("brush radius is r0 * (1 - age/T)", () => {
    expect(brush(28, 0, 30)).toEqual({ r: 28, alpha: 1 });
    expect(brush(28, 15, 30)).toEqual({ r: 14, alpha: .5 });
    expect(brush(28, 30, 30)).toEqual({ r: 0, alpha: 0 });
  });
  it("backing store is 0.5x CSS size x min(DPR, 2)", () => {
    expect(backingSize(1000, 600, 1)).toMatchObject({ width: 500, height: 300 });
    expect(backingSize(1000, 600, 2)).toMatchObject({ width: 1000, height: 600 });
    expect(backingSize(1000, 600, 3)).toMatchObject({ width: 1000, height: 600 });
  });
});
