import { describe, expect, it } from "vitest";
import { initial, moodOf, reduce, STATES, type BehaviorEvent, type BehaviorState } from "../behavior";
import { HAPPY_MS, PET_MAX_MS } from "../petConfig";

const run = (s: BehaviorState, e: BehaviorEvent, t: number) => reduce(s, e, t);

describe("pet behavior", () => {
  it("tap -> happy, then back to idle after 1200 ms", () => {
    let s = run(initial(), { type: "tap" }, 0);
    expect(s.state).toBe("happy");
    s = run(s, { type: "tick" }, HAPPY_MS - 1);
    expect(s.state).toBe("happy");
    s = run(s, { type: "tick" }, HAPPY_MS);
    expect(s.state).toBe("idle");
  });
  it("3 taps within 1500 ms -> playful", () => {
    let s = initial();
    s = run(s, { type: "tap" }, 0); s = run(s, { type: "poke" }, 500); s = run(s, { type: "tap" }, 1400);
    expect(s.state).toBe("playful");
  });
  it("3 taps spread over more than 1500 ms stay happy", () => {
    let s = initial();
    s = run(s, { type: "tap" }, 0); s = run(s, { type: "tap" }, 900); s = run(s, { type: "tap" }, 1600);
    expect(s.state).toBe("happy");
  });
  it("long press -> petting, released at 5000 ms at most", () => {
    let s = run(initial(), { type: "pressStart" }, 0);
    expect(s.state).toBe("petting");
    s = run(s, { type: "tick" }, PET_MAX_MS);
    expect(s.state).toBe("idle");
    s = run(run(initial(), { type: "pressStart" }, 0), { type: "pressEnd" }, 800);
    expect(s.state).toBe("idle");
  });
  it("bedtime -> yawn -> sleeping; a tap wakes it and it sleeps again after 30 s", () => {
    let s = run(initial(), { type: "enterBedtime" }, 0);
    expect(s.state).toBe("yawning");
    s = run(s, { type: "tick" }, 1400);
    expect(s.state).toBe("sleeping");
    s = run(s, { type: "tap" }, 2000);
    expect(s.state).toBe("waking");
    s = run(s, { type: "tick" }, 3800);
    expect(s.state).toBe("idle");
    s = run(s, { type: "tick" }, 3800 + 30000);
    expect(s.state).toBe("yawning");
    s = run(s, { type: "leaveBedtime" }, 40000);
    expect(s.state).toBe("stretching");
  });
  it("idle 45 s -> one stretch", () => {
    let s = run(initial(), { type: "idleFor", ms: 45000 }, 0);
    expect(s.state).toBe("stretching");
    s = run(run(s, { type: "tick" }, 1800), { type: "idleFor", ms: 50000 }, 1900);
    expect(s.state).toBe("idle");
  });
  it("no transition ever yields a sad state, and moods come only from state + time of day", () => {
    const events: BehaviorEvent[] = [{ type: "tick" }, { type: "tap" }, { type: "poke" }, { type: "pressStart" }, { type: "pressEnd" }, { type: "idleFor", ms: 60000 },
      { type: "yawn" }, { type: "enterBedtime" }, { type: "leaveBedtime" }, { type: "perchFound" }, { type: "arrived" }, { type: "leavePerch" }, { type: "followStart" }, { type: "followStop" }];
    let s = initial(); let t = 0;
    for (let i = 0; i < 2000; i++) {
      s = run(s, events[(i * 7 + (i >> 3)) % events.length], (t += 137));
      expect(STATES).toContain(s.state);
      for (const tod of ["morning", "day", "evening", "night"] as const) expect(moodOf(s.state, tod)).not.toMatch(/sad|concerned|annoyed/);
    }
  });
});
