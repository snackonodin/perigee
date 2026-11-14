// Pure cursor-follow motion (mouse/pen only, wide screens, no reduced motion).
// The pet chases a *lagged* copy of the pointer, stops inside a dead zone so it never
// sits on what the user is clicking, keeps a gap behind the cursor, wobbles a little
// and now and then takes a detour. No DOM, no timers: Pet.tsx drives it from rAF.
import {
  FOLLOW_ACCEL, FOLLOW_DEADZONE_PX, FOLLOW_DETOUR_CHANCE_S, FOLLOW_DETOUR_MAX_MS, FOLLOW_DETOUR_MAX_PX, FOLLOW_DETOUR_MIN_DIST_PX,
  FOLLOW_DETOUR_MIN_PX, FOLLOW_EASE, FOLLOW_EDGE_PX, FOLLOW_GAP_PX, FOLLOW_LAG_MS, FOLLOW_MAX_SPEED_PX_S, FOLLOW_STOP_SPEED_PX_S,
  FOLLOW_WOBBLE_HZ, FOLLOW_WOBBLE_PX, FOLLOW_COOLDOWN_MS, FOLLOW_INTEREST_MAX_MS, FOLLOW_INTEREST_MIN_MS, IGNORE_MAX_MS, IGNORE_MIN_MS,
  MOOD_WEIGHTS, WANDER_MAX_MS, WANDER_MIN_MS, WANDER_POINTER_CLEAR_PX, WANDER_TRIES, FOLLOW_MIN_DIST_PX,
  HOP_CROUCH, HOP_HEIGHT_PX, HOP_LAND, HOP_SETTLE, HOP_STRETCH, HOP_TAKEOFF,
} from "./petConfig";
import { avoids, type Box, type Point } from "./walk";

interface Sample { t: number; x: number; y: number }
export interface FollowState {
  /** pet centre, viewport px */
  pos: Point;
  vel: Point;
  history: Sample[];
  detour?: { at: Point; until: number };
  phase: number;
}

export const createFollow = (pos: Point): FollowState => ({ pos: { ...pos }, vel: { x: 0, y: 0 }, history: [], phase: 0 });

/** Record a pointer sample (keeps ~1 s of history). */
export function notePointer(s: FollowState, x: number, y: number, t: number): void {
  s.history.push({ t, x, y });
  while (s.history.length > 2 && t - s.history[0].t > 1000) s.history.shift();
}

/** The pointer as it was FOLLOW_LAG_MS ago (the oldest sample if history is shorter). */
export function laggedPointer(s: FollowState, now: number): Point | null {
  const h = s.history;
  if (!h.length) return null;
  const want = now - FOLLOW_LAG_MS;
  for (let i = h.length - 1; i >= 0; i--) if (h[i].t <= want) return { x: h[i].x, y: h[i].y };
  return { x: h[0].x, y: h[0].y };
}

export interface FollowEnv { size: number; viewport: { width: number; height: number }; random?: () => number }

export const clampToViewport = (p: Point, size: number, vp: { width: number; height: number }): Point => {
  const m = size / 2 + FOLLOW_EDGE_PX;
  return { x: Math.min(Math.max(p.x, m), Math.max(m, vp.width - m)), y: Math.min(Math.max(p.y, m), Math.max(m, vp.height - m)) };
};

/** Advance one frame. Returns whether the pet is visibly moving. Mutates s. */
export function stepFollow(s: FollowState, now: number, dt: number, env: FollowEnv): { moving: boolean } {
  const rnd = env.random ?? Math.random;
  const ptr = laggedPointer(s, now);
  let goal: Point = s.pos;
  if (ptr) {
    const dx = ptr.x - s.pos.x, dy = ptr.y - s.pos.y, d = Math.hypot(dx, dy);
    if (d > FOLLOW_DEADZONE_PX) {
      const ux = dx / d, uy = dy / d;
      // stand FOLLOW_GAP_PX short of the (lagged) pointer: dead space behind the cursor
      goal = { x: ptr.x - ux * FOLLOW_GAP_PX, y: ptr.y - uy * FOLLOW_GAP_PX };
      // side-to-side wobble, perpendicular to the heading, fading in with distance
      s.phase += dt * FOLLOW_WOBBLE_HZ * 2 * Math.PI;
      const w = Math.sin(s.phase) * FOLLOW_WOBBLE_PX * Math.min(1, d / 300);
      goal = { x: goal.x - uy * w, y: goal.y + ux * w };
      // occasional detour: a waypoint off to one side of the straight line
      if (!s.detour && d > FOLLOW_DETOUR_MIN_DIST_PX && rnd() < FOLLOW_DETOUR_CHANCE_S * dt) {
        const side = rnd() < 0.5 ? -1 : 1, off = side * (FOLLOW_DETOUR_MIN_PX + rnd() * (FOLLOW_DETOUR_MAX_PX - FOLLOW_DETOUR_MIN_PX));
        const mid = { x: (s.pos.x + goal.x) / 2, y: (s.pos.y + goal.y) / 2 };
        s.detour = { at: clampToViewport({ x: mid.x - uy * off, y: mid.y + ux * off }, env.size, env.viewport), until: now + FOLLOW_DETOUR_MAX_MS };
      }
    } else s.detour = undefined;
  }
  if (s.detour) {
    if (now > s.detour.until || Math.hypot(s.detour.at.x - s.pos.x, s.detour.at.y - s.pos.y) < 16) s.detour = undefined;
    else goal = s.detour.at;
  }
  // eased steering: desired speed grows with distance (lag), capped; velocity eases toward it
  const gx = goal.x - s.pos.x, gy = goal.y - s.pos.y, gd = Math.hypot(gx, gy);
  const speed = Math.min(FOLLOW_MAX_SPEED_PX_S, gd * FOLLOW_EASE);
  const want = gd > 0.5 ? { x: gx / gd * speed, y: gy / gd * speed } : { x: 0, y: 0 };
  const k = Math.min(1, FOLLOW_ACCEL * dt);
  s.vel = { x: s.vel.x + (want.x - s.vel.x) * k, y: s.vel.y + (want.y - s.vel.y) * k };
  s.pos = clampToViewport({ x: s.pos.x + s.vel.x * dt, y: s.pos.y + s.vel.y * dt }, env.size, env.viewport);
  const moving = Math.hypot(s.vel.x, s.vel.y) > FOLLOW_STOP_SPEED_PX_S;
  if (!moving && !s.detour) s.vel = { x: 0, y: 0 };
  return { moving };
}

// ---- Moods: follow for a while, wander to a free spot, or ignore the pointer -------------

export type Mood = "follow" | "wander" | "ignore";
export interface MoodState { mood: Mood; until: number; followCooldownUntil: number }

const between = (rnd: () => number, lo: number, hi: number) => lo + rnd() * (hi - lo);
export const moodDuration = (m: Mood, rnd: () => number): number =>
  m === "follow" ? between(rnd, FOLLOW_INTEREST_MIN_MS, FOLLOW_INTEREST_MAX_MS)
    : m === "wander" ? between(rnd, WANDER_MIN_MS, WANDER_MAX_MS) : between(rnd, IGNORE_MIN_MS, IGNORE_MAX_MS);

/** Weighted pick (50 / 35 / 15). While the chase cooldown runs, follow is not an option. */
export function pickMood(rnd: () => number, followAllowed = true): Mood {
  const w = { ...MOOD_WEIGHTS, follow: followAllowed ? MOOD_WEIGHTS.follow : 0 };
  let r = rnd() * (w.follow + w.wander + w.ignore);
  for (const m of ["follow", "wander", "ignore"] as const) { if ((r -= w[m]) < 0) return m; }
  return "ignore";
}

export const createMoods = (now: number, rnd: () => number = Math.random): MoodState =>
  ({ mood: "follow", until: now + moodDuration("follow", rnd), followCooldownUntil: 0 });

/** When the current mood has run out, pick the next one. Returns true if the mood changed. Mutates m. */
export function advanceMood(m: MoodState, now: number, rnd: () => number = Math.random): boolean {
  if (now < m.until) return false;
  if (m.mood === "follow") m.followCooldownUntil = now + FOLLOW_COOLDOWN_MS;
  const next = pickMood(rnd, now >= m.followCooldownUntil);
  const changed = next !== m.mood;
  m.mood = next;
  m.until = now + moodDuration(next, rnd);
  return changed;
}

/** A random free spot (pet centre) for a wander: inside the viewport, its box touching nothing
 *  to avoid, and well away from the pointer. Null when none is found. */
export function pickWanderSpot(viewport: { width: number; height: number }, size: number, avoid: readonly Box[],
  pointer: Point | null, rnd: () => number = Math.random): Point | null {
  const m = size / 2 + FOLLOW_EDGE_PX;
  if (viewport.width < 2 * m || viewport.height < 2 * m) return null;
  for (let i = 0; i < WANDER_TRIES; i++) {
    const p = { x: between(rnd, m, viewport.width - m), y: between(rnd, m, viewport.height - m) };
    if (pointer && Math.hypot(p.x - pointer.x, p.y - pointer.y) < WANDER_POINTER_CLEAR_PX) continue;
    if (avoids({ left: p.x - size / 2, top: p.y - size / 2, width: size, height: size }, avoid)) return p;
  }
  return null;
}

// ---- Keep away: never closer than FOLLOW_MIN_DIST_PX to the cursor -------------------------

/** Where to hop when the pointer is too close: straight away from it, far enough to clear the
 *  minimum distance; if the screen edge blocks that, any free spot that is far enough. Null when
 *  the pointer is not too close (or no spot is free). */
export function fleeTarget(pos: Point, pointer: Point, size: number, viewport: { width: number; height: number },
  avoid: readonly Box[] = [], rnd: () => number = Math.random): Point | null {
  const dx = pos.x - pointer.x, dy = pos.y - pointer.y, d = Math.hypot(dx, dy);
  if (d >= FOLLOW_MIN_DIST_PX) return null;
  const ux = d > 1 ? dx / d : 1, uy = d > 1 ? dy / d : 0, want = FOLLOW_MIN_DIST_PX + 60;
  const straight = clampToViewport({ x: pointer.x + ux * want, y: pointer.y + uy * want }, size, viewport);
  const clear = avoids({ left: straight.x - size / 2, top: straight.y - size / 2, width: size, height: size }, avoid);
  if (clear && Math.hypot(straight.x - pointer.x, straight.y - pointer.y) >= FOLLOW_MIN_DIST_PX) return straight;
  return pickWanderSpot(viewport, size, avoid, pointer, rnd);
}

// ---- Hop pose: one shared phase drives the body and the travel speed -----------------------

export interface HopPose { hop: number; squash: number; ears: number; tail: number }
const lerp = (a: number, b: number, t: number) => a + (b - a) * Math.max(0, Math.min(1, t));
const ease = (t: number) => 0.5 - 0.5 * Math.cos(Math.PI * Math.max(0, Math.min(1, t)));

/** Pose at phase 0..1 of a hop: crouch, take-off stretch, airborne arc, landing squash, settle, pause.
 *  hop is px (negative = up); ears and tail trail the body by a beat. */
export function hopPose(phase: number): HopPose {
  const p = ((phase % 1) + 1) % 1;
  let hop = 0, squash = 0;
  if (p < HOP_TAKEOFF) squash = lerp(0, HOP_CROUCH, ease(p / HOP_TAKEOFF));
  else if (p < HOP_LAND) {
    const a = (p - HOP_TAKEOFF) / (HOP_LAND - HOP_TAKEOFF);
    hop = -HOP_HEIGHT_PX * Math.sin(Math.PI * a);
    squash = a < 0.35 ? lerp(HOP_STRETCH, -0.15, a / 0.35) : a > 0.85 ? lerp(-0.15, 0, (a - 0.85) / 0.15) : -0.15;
  } else if (p < HOP_SETTLE) {
    const a = (p - HOP_LAND) / (HOP_SETTLE - HOP_LAND);
    squash = HOP_CROUCH * 0.7 * Math.cos(Math.PI * a * 1.5) * (1 - a);
    hop = -2 * Math.sin(Math.PI * Math.min(1, a * 1.6)) * (a > 0.35 ? 1 : 0);
  }
  // ears and tail trail: they follow the body's vertical motion one beat later
  const lag = hopHeightAt(p - 0.08);
  return { hop, squash, ears: -lag / HOP_HEIGHT_PX * 0.6, tail: lag / HOP_HEIGHT_PX * 0.5 };
}
const hopHeightAt = (phase: number) => {
  const p = ((phase % 1) + 1) % 1;
  return p >= HOP_TAKEOFF && p < HOP_LAND ? -HOP_HEIGHT_PX * Math.sin(Math.PI * (p - HOP_TAKEOFF) / (HOP_LAND - HOP_TAKEOFF)) : 0;
};

/** Travel speed multiplier at a phase: it covers ground only while airborne (mean = 1 over a hop). */
export function hopSpeed(phase: number): number {
  const p = ((phase % 1) + 1) % 1;
  return p >= HOP_TAKEOFF && p < HOP_LAND ? 1 / (HOP_LAND - HOP_TAKEOFF) : 0;
}

// ---- Fixed perch spots: the pet only moves between designated spots and home ---------------

const far = (p: Point, pointer: Point | null) => !pointer || Math.hypot(p.x - pointer.x, p.y - pointer.y) >= FOLLOW_MIN_DIST_PX;
const same = (a: Point, b?: Point | null) => !!b && Math.hypot(a.x - b.x, a.y - b.y) < 8;

/** Escape or settle: the spot nearest `from` that keeps the minimum distance from the pointer. */
export function nearestSpot(spots: readonly Point[], from: Point, pointer: Point | null, except?: Point | null): Point | null {
  let best: Point | null = null, bd = Infinity;
  for (const p of spots) {
    if (same(p, except) || !far(p, pointer)) continue;
    const d = Math.hypot(p.x - from.x, p.y - from.y);
    if (d < bd) { bd = d; best = p; }
  }
  return best;
}

/** "Follow" between fixed spots: the spot closest to the pointer that is still a card's width away. */
export const spotTowardPointer = (spots: readonly Point[], pointer: Point, current?: Point | null): Point | null =>
  nearestSpot(spots, pointer, pointer, current);

/** "Wander": any other spot that keeps the minimum distance from the pointer. */
export function otherSpot(spots: readonly Point[], current: Point | null, pointer: Point | null, rnd: () => number = Math.random): Point | null {
  const ok = spots.filter((p) => !same(p, current) && far(p, pointer));
  return ok.length ? ok[Math.floor(rnd() * ok.length)] : null;
}
