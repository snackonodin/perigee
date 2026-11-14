import { afterEach, describe, expect, it, vi } from "vitest";
import { unlocked } from "../accessories";

afterEach(() => { vi.restoreAllMocks(); try { localStorage.clear(); } catch { /* */ } });

describe("accessories", () => {
  it("unlock at 3, 7, 14 and 30 lifetime nights", () => {
    expect(unlocked(2)).toEqual([]);
    expect(unlocked(3)).toEqual(["scarf"]);
    expect(unlocked(7)).toEqual(["scarf", "star"]);
    expect(unlocked(14)).toEqual(["scarf", "star", "moon"]);
    expect(unlocked(30)).toEqual(["scarf", "star", "moon", "crown"]);
  });
  it("a later smaller nightsLogged keeps what was earned", () => {
    unlocked(14);
    expect(unlocked(1)).toEqual(["scarf", "star", "moon"]);
  });
  it("a throwing storage does not crash", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(unlocked(7)).toEqual(["scarf", "star"]);
  });
});
