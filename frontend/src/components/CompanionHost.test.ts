import { describe, expect, it } from "vitest";
import { night } from "../test/fixtures";
import { nightCounts, stationMinutes, timeOfDayAt } from "./CompanionHost";

describe("companion host context", () => {
  it("time of day comes from station time", () => {
    expect(timeOfDayAt(5 * 60)).toBe("morning");
    expect(timeOfDayAt(12 * 60)).toBe("day");
    expect(timeOfDayAt(17 * 60)).toBe("evening");
    expect(timeOfDayAt(22 * 60)).toBe("night");
    expect(timeOfDayAt(4 * 60 + 59)).toBe("night");
    const noonUtc = Date.parse("2026-11-14T12:00:00Z");
    expect(stationMinutes(null, noonUtc)).toBe(720);
    expect(stationMinutes(330, noonUtc)).toBe(17 * 60 + 30);
  });
  it("nightsLogged counts valid nights; streak is consecutive valid nights ending last night", () => {
    const nights = [night("2026-11-13", 15), night("2026-11-12", 15), night("2026-11-11", null, false), night("2026-11-10", 14), night("2026-11-09", 14)];
    expect(nightCounts(nights, "2026-11-14")).toEqual({ nightsLogged: 4, streakDays: 2 });
    expect(nightCounts([], "2026-11-14")).toEqual({ nightsLogged: 0, streakDays: 0 });
  });
});
