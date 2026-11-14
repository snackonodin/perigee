import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import cache from "../dialog/cache.json";
import { pickLine } from "../dialog/picker";
import { mulberry32 } from "../frost/prng";
import type { DialogCache } from "../types";

const C = cache as unknown as DialogCache;
beforeEach(() => { try { localStorage.clear(); } catch { /* */ } });
afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ""; });

describe("dialog picker", () => {
  it("filters by time of day (or any)", () => {
    for (let i = 0; i < 40; i++) {
      localStorage.clear();
      const l = pickLine(C, "app_open", "warm", "morning", i, { random: mulberry32(i) })!;
      expect(["morning", "any"]).toContain(l.tod);
    }
  });
  it("does not repeat any of the last 8 lines", () => {
    const seen: string[] = [];
    const r = mulberry32(3);
    // evening pool = 8 "any" + 1 evening line = 9, so 9 picks are all different
    for (let i = 0; i < 9; i++) seen.push(pickLine(C, "quiz_complete", "warm", "evening", i, { random: r })!.id);
    expect(new Set(seen).size).toBe(9);
    expect(JSON.parse(localStorage.getItem("pet.dialog.recent")!)).toHaveLength(8);
  });
  it("weights: a weight-2 line is picked about twice as often as a weight-1 line", () => {
    const r = mulberry32(11), counts: Record<string, number> = {};
    for (let i = 0; i < 3000; i++) {
      localStorage.removeItem("pet.dialog.recent");
      const id = pickLine(C, "app_open", "quiet", "day", i, { random: r })!.id;
      counts[id] = (counts[id] ?? 0) + 1;
    }
    const ratio = counts["app_open.quiet.01"] / counts["app_open.quiet.03"]; // weights 2 and 1
    expect(ratio).toBeGreaterThan(1.6);
    expect(ratio).toBeLessThan(2.4);
  });
  it("respects the per-event cooldown", () => {
    const lastShown = {};
    expect(pickLine(C, "pet_tap", "warm", "day", 0, { lastShown })).not.toBeNull();
    expect(pickLine(C, "pet_tap", "warm", "day", 19999, { lastShown })).toBeNull();
    expect(pickLine(C, "pet_tap", "warm", "day", 20000, { lastShown })).not.toBeNull();
  });
  it("shows nothing while a form field has focus", () => {
    const input = document.createElement("input");
    document.body.append(input); input.focus();
    expect(pickLine(C, "app_open", "warm", "day", 0)).toBeNull();
  });
  it("muted, snoozed and safety return null", () => {
    localStorage.setItem("pet.dialog.muted", "true");
    expect(pickLine(C, "app_open", "warm", "day", 0)).toBeNull();
    localStorage.clear();
    localStorage.setItem("pet.dialog.snoozeUntil", "5000");
    expect(pickLine(C, "app_open", "warm", "day", 4999)).toBeNull();
    expect(pickLine(C, "app_open", "warm", "day", 5000)).not.toBeNull();
    expect(pickLine(C, "wake", "warm", "day", 0, { safetyActive: true })).toBeNull();
  });
  it("still works when localStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(pickLine(C, "app_open", "warm", "day", 0)).not.toBeNull();
  });
});
