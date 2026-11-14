import { describe, expect, it } from "vitest";
import { night, rrBaseline, today } from "../test/fixtures";
import { baselineState } from "./baselineState";

const REST = ["presence_hours", "restless_frac"] as const;
const presenceBase = { ...rrBaseline, feature: "presence_hours" };
const flag = (physiology: Record<string, unknown>, extra: Record<string, unknown> = {}) =>
  ({ ...today.flags[0], date: "2026-11-11", components: { alert_robust_z: 2.5, night_date: "2026-11-10", physiology, ...extra } });

describe("baseline-relative body state (engine cut-off, no frontend thresholds)", () => {
  it("changed when the latest night's flag is over the shipped cut-off for any feature", () => {
    const t = { ...today, baselines: [presenceBase], flags: [flag({ presence_hours: { z: 0.4 }, restless_frac: { z: 7.4 } })] };
    expect(baselineState(t, REST)).toBe("changed");
    expect(baselineState({ ...t, flags: [flag({ restless_frac: { z: -2.5 } })] }, REST)).toBe("changed");
  });
  it("usual when the night is valid, the baseline is past warm-up and nothing is over the cut-off", () => {
    expect(baselineState({ ...today, baselines: [presenceBase], flags: [flag({ presence_hours: { z: 1.2 } })] }, REST)).toBe("usual");
    expect(baselineState({ ...today, baselines: [presenceBase], flags: [] }, REST)).toBe("usual");
  });
  it("uses the cut-off from the data, not a fixed number", () => {
    const t = { ...today, baselines: [presenceBase], flags: [flag({ restless_frac: { z: 3 } }, { alert_robust_z: 3.5 })] };
    expect(baselineState(t, REST)).toBe("usual");
  });
  it("not compared during warm-up, when skipped, without a valid night, or for another night's flag", () => {
    expect(baselineState({ ...today, baselines: [{ ...presenceBase, maturity: "warm_up" }], flags: [] }, REST)).toBe("none");
    expect(baselineState({ ...today, baselines: [presenceBase], flags: [flag({ presence_hours: { skipped: "warm_up" } })] }, REST)).toBe("none");
    expect(baselineState({ ...today, latest_night: night("2026-11-10", null, false), baselines: [presenceBase], flags: [] }, REST)).toBe("none");
    expect(baselineState({ ...today, baselines: [], flags: [] }, REST)).toBe("none");
    const old = { ...flag({ restless_frac: { z: 9 } }), components: { alert_robust_z: 2.5, night_date: "2026-11-01", physiology: { restless_frac: { z: 9 } } } };
    expect(baselineState({ ...today, baselines: [presenceBase], flags: [old] }, REST)).toBe("usual");
  });
  it("respiration follows the same rule (fixture: rr_med z 3.29 over 2.5)", () => {
    expect(baselineState(today, ["rr_med"])).toBe("changed");
  });
});
