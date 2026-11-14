import { describe, expect, it } from "vitest";
import { advanceMood, createFollow, createMoods, fleeTarget, hopPose, hopSpeed, laggedPointer, notePointer, pickMood, pickWanderSpot, stepFollow } from "../follow";
import {
  FOLLOW_COOLDOWN_MS, FOLLOW_DEADZONE_PX, FOLLOW_MIN_DIST_PX, HOP_HEIGHT_PX, HOP_LAND, HOP_SETTLE, HOP_TAKEOFF, FOLLOW_GAP_PX, FOLLOW_INTEREST_MAX_MS, FOLLOW_INTEREST_MIN_MS, FOLLOW_LAG_MS, WANDER_POINTER_CLEAR_PX,
} from "../petConfig";

/** Deterministic random (mulberry32). */
const seeded = (seed: number) => () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

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
  it("keeps a wide berth: at least the gap behind the cursor, stops inside the dead zone", () => {
    expect(FOLLOW_MIN_DIST_PX).toBeGreaterThanOrEqual(300);
    expect(FOLLOW_GAP_PX).toBeGreaterThanOrEqual(FOLLOW_MIN_DIST_PX);
    expect(FOLLOW_DEADZONE_PX).toBeGreaterThan(FOLLOW_GAP_PX);
    const s = createFollow({ x: 1200, y: 720 });
    notePointer(s, 300, 300, 0);
    run(s, 0, 8000);
    expect(Math.hypot(s.pos.x - 300, s.pos.y - 300)).toBeGreaterThan(FOLLOW_GAP_PX - 20);
  });
});

describe("pet moods", () => {
  it("picks follow / wander / ignore at about 50 / 35 / 15 %", () => {
    const rnd = seeded(42), n = 20000, c = { follow: 0, wander: 0, ignore: 0 };
    for (let i = 0; i < n; i++) c[pickMood(rnd)]++;
    expect(c.follow / n).toBeCloseTo(0.5, 1);
    expect(c.wander / n).toBeCloseTo(0.35, 1);
    expect(c.ignore / n).toBeCloseTo(0.15, 1);
  });
  it("never chases while the cooldown runs", () => {
    const rnd = seeded(7);
    for (let i = 0; i < 2000; i++) expect(pickMood(rnd, false)).not.toBe("follow");
  });
  it("loses interest after 4-8 s, then cannot chase again until the cooldown ends", () => {
    const rnd = seeded(3), m = createMoods(0, rnd);
    expect(m.mood).toBe("follow");
    expect(m.until).toBeGreaterThanOrEqual(FOLLOW_INTEREST_MIN_MS);
    expect(m.until).toBeLessThanOrEqual(FOLLOW_INTEREST_MAX_MS);
    expect(advanceMood(m, m.until - 1, rnd)).toBe(false);
    const end = m.until;
    advanceMood(m, end, rnd);
    expect(m.mood).not.toBe("follow");
    expect(m.followCooldownUntil).toBe(end + FOLLOW_COOLDOWN_MS);
  });
  it("over a long session it mixes all three moods and never chases nonstop", () => {
    const rnd = seeded(11), m = createMoods(0, rnd), seen = new Set<string>();
    let t = 0, chase = 0, longest = 0;
    for (let i = 0; i < 400; i++) {
      const was = m.mood, from = t; t = m.until; advanceMood(m, t, rnd); seen.add(m.mood);
      if (was === "follow") { chase += t - from; longest = Math.max(longest, chase); } else chase = 0;
    }
    expect(seen).toEqual(new Set(["follow", "wander", "ignore"]));
    expect(longest).toBeLessThanOrEqual(FOLLOW_INTEREST_MAX_MS);
  });
  it("wanders only to free spots inside the screen, away from the pointer", () => {
    const vp = { width: 1280, height: 800 }, form = { left: 0, top: 0, width: 1280, height: 400 }, ptr = { x: 640, y: 600 };
    const rnd = seeded(5);
    for (let i = 0; i < 200; i++) {
      const p = pickWanderSpot(vp, 96, [form], ptr, rnd);
      if (!p) continue;
      expect(p.y - 48).toBeGreaterThanOrEqual(400);
      expect(p.x - 48).toBeGreaterThanOrEqual(0);
      expect(p.x + 48).toBeLessThanOrEqual(1280);
      expect(Math.hypot(p.x - ptr.x, p.y - ptr.y)).toBeGreaterThanOrEqual(WANDER_POINTER_CLEAR_PX);
    }
    expect(pickWanderSpot(vp, 96, [{ left: 0, top: 0, width: 1280, height: 800 }], null, rnd)).toBeNull();
  });
});

describe("keep away (one card width)", () => {
  const vp = { width: 1440, height: 900 };
  it("does nothing while the cursor is far enough", () => {
    expect(fleeTarget({ x: 200, y: 200 }, { x: 200 + FOLLOW_MIN_DIST_PX, y: 200 }, 96, vp)).toBeNull();
  });
  it("hops straight away, clearing the minimum distance", () => {
    const t = fleeTarget({ x: 700, y: 450 }, { x: 600, y: 450 }, 96, vp)!;
    expect(t.x).toBeGreaterThan(700);
    expect(Math.hypot(t.x - 600, t.y - 450)).toBeGreaterThanOrEqual(FOLLOW_MIN_DIST_PX);
  });
  it("does not escape onto text or controls: picks another free spot", () => {
    const heading = { left: 800, top: 300, width: 400, height: 300 };
    const t = fleeTarget({ x: 700, y: 450 }, { x: 600, y: 450 }, 96, vp, [heading], seeded(4))!;
    const box = { left: t.x - 48, top: t.y - 48, width: 96, height: 96 };
    const overlaps = box.left < heading.left + heading.width && heading.left < box.left + 96 && box.top < heading.top + heading.height && heading.top < box.top + 96;
    expect(overlaps).toBe(false);
    expect(Math.hypot(t.x - 600, t.y - 450)).toBeGreaterThanOrEqual(FOLLOW_MIN_DIST_PX);
  });
  it("when cornered, picks any free spot far enough from the cursor", () => {
    const ptr = { x: 1300, y: 800 };
    const t = fleeTarget({ x: 1380, y: 840 }, ptr, 96, vp, [], seeded(9))!;
    expect(Math.hypot(t.x - ptr.x, t.y - ptr.y)).toBeGreaterThanOrEqual(FOLLOW_MIN_DIST_PX);
  });
});

describe("chibi hop", () => {
  const at = (p: number) => hopPose(p);
  it("crouches about 10 % before take-off and stretches about 8 % on the way up", () => {
    const crouch = at(HOP_TAKEOFF - 0.001), stretch = at(HOP_TAKEOFF + 0.001);
    expect(1 - 0.12 * crouch.squash).toBeCloseTo(0.9, 1);
    expect(1 - 0.12 * stretch.squash).toBeCloseTo(1.08, 1);
  });
  it("arcs about 12 px at mid-flight and lands with a squash, then pauses on the ground", () => {
    expect(at((HOP_TAKEOFF + HOP_LAND) / 2).hop).toBeCloseTo(-HOP_HEIGHT_PX, 0);
    expect(at(HOP_LAND + 0.001).squash).toBeGreaterThan(0.4);
    const rest = at((HOP_SETTLE + 1) / 2);
    expect(rest.hop).toBe(0);
    expect(rest.squash).toBe(0);
  });
  it("ears and tail trail the body by a beat", () => {
    const takeoff = at(HOP_TAKEOFF + 0.01);
    expect(Math.abs(takeoff.ears)).toBeLessThan(0.05);
    expect(Math.abs(at(HOP_LAND + 0.02).ears)).toBeGreaterThan(0.05);
  });
  it("covers ground only while airborne, at the same mean speed", () => {
    expect(hopSpeed(HOP_TAKEOFF / 2)).toBe(0);
    expect(hopSpeed((HOP_SETTLE + 1) / 2)).toBe(0);
    let sum = 0; const n = 1000; for (let i = 0; i < n; i++) sum += hopSpeed(i / n);
    expect(sum / n).toBeCloseTo(1, 1);
  });
});
