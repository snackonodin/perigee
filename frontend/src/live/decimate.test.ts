import { describe, expect, it } from "vitest";
import { decimate, trimTo } from "./decimate";

describe("decimate", () => {
  it("returns short series untouched", () => {
    const pts = [{ t: 1, v: 1 }, { t: 2, v: 2 }];
    expect(decimate(pts, 10)).toBe(pts);
  });

  it("caps the point count and keeps spikes (min/max per bucket)", () => {
    const pts = Array.from({ length: 10_000 }, (_, i) => ({ t: i, v: i === 5_123 ? 99 : 14 }));
    const out = decimate(pts, 300);
    expect(out.length).toBeLessThanOrEqual(300);
    expect(out.some((p) => p.v === 99)).toBe(true);
    expect(out.map((p) => p.t)).toEqual([...out.map((p) => p.t)].sort((a, b) => a - b));
  });

  it("keeps gaps so lines break where data is missing", () => {
    const pts = Array.from({ length: 1_000 }, (_, i) => ({ t: i, v: i >= 400 && i < 600 ? null : 14 }));
    expect(decimate(pts, 100).some((p) => p.v === null)).toBe(true);
  });

  it("trimTo drops the oldest entries", () => {
    const a = [1, 2, 3, 4, 5];
    trimTo(a, 3);
    expect(a).toEqual([3, 4, 5]);
  });
});
