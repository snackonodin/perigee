// Pure behavior state machine: reduce(state, event, now) -> state. No DOM, no timers.
// Mood comes only from engagement (taps, petting) and time of day. There is no sad state.
import { HAPPY_MS, PET_MAX_MS, PLAYFUL_MS, POKE_COUNT, POKE_WINDOW_MS, RESLEEP_MS, STRETCH_IDLE_MS, STRETCH_MS, YAWN_MS } from "./petConfig";
import type { PetMood, TimeOfDay } from "./types";

export type PetState = "idle" | "happy" | "petting" | "playful" | "yawning" | "stretching" | "walking" | "sitting" | "sleepy" | "sleeping" | "waking";
export type BehaviorEvent =
  | { type: "tick" } | { type: "tap" } | { type: "poke" } | { type: "pressStart" } | { type: "pressEnd" }
  | { type: "idleFor"; ms: number } | { type: "yawn" } | { type: "enterBedtime" } | { type: "leaveBedtime" }
  | { type: "perchFound" } | { type: "arrived" } | { type: "leavePerch" };

export interface Rig { mouth: number; squash: number; earL: number; earR: number; blink: number }
export interface BehaviorState {
  state: PetState;
  /** when a timed state ends (epoch ms); undefined = holds */
  until?: number;
  bedtime: boolean;
  taps: number[];
  /** after a tap wakes a sleeping pet: go back to sleep at this time if still bedtime */
  resleepAt?: number;
  stretchedIdle: boolean;
  rig: Rig;
}

export const STATES: readonly PetState[] = ["idle", "happy", "petting", "playful", "yawning", "stretching", "walking", "sitting", "sleepy", "sleeping", "waking"];

const RIG: Record<PetState, Rig> = {
  idle: { mouth: 0, squash: 0, earL: 0, earR: 0, blink: 0 },
  happy: { mouth: .8, squash: 0, earL: .2, earR: .2, blink: 0 },
  petting: { mouth: .2, squash: .1, earL: -.5, earR: -.5, blink: 0 },
  playful: { mouth: .6, squash: 0, earL: .4, earR: .4, blink: 0 },
  yawning: { mouth: 1, squash: 0, earL: -.2, earR: -.2, blink: .5 },
  stretching: { mouth: 0, squash: -.4, earL: -.3, earR: -.3, blink: .3 },
  walking: { mouth: 0, squash: 0, earL: .1, earR: .1, blink: 0 },
  sitting: { mouth: 0, squash: .05, earL: 0, earR: 0, blink: 0 },
  sleepy: { mouth: 0, squash: 0, earL: -.2, earR: -.2, blink: .55 },
  sleeping: { mouth: 0, squash: .15, earL: -.3, earR: -.3, blink: 0 },
  waking: { mouth: 0, squash: -.4, earL: 0, earR: 0, blink: .4 },
};

export function initial(bedtime = false): BehaviorState {
  const state: PetState = bedtime ? "sleeping" : "idle";
  return { state, bedtime, taps: [], stretchedIdle: false, rig: RIG[state] };
}

const to = (s: BehaviorState, state: PetState, now: number, ms?: number, extra: Partial<BehaviorState> = {}): BehaviorState =>
  ({ ...s, ...extra, state, until: ms == null ? undefined : now + ms, rig: RIG[state] });

export function reduce(s: BehaviorState, e: BehaviorEvent, now: number): BehaviorState {
  switch (e.type) {
    case "tick": {
      if (s.until != null && now >= s.until) {
        if (s.state === "yawning" && s.bedtime) return to(s, "sleeping", now);
        if (s.state === "waking") return to(s, "idle", now, undefined, { resleepAt: s.bedtime ? now + RESLEEP_MS : undefined });
        return to(s, "idle", now);
      }
      if (s.resleepAt != null && now >= s.resleepAt && s.bedtime && s.state === "idle") return to(s, "yawning", now, YAWN_MS, { resleepAt: undefined });
      return s;
    }
    case "tap": case "poke": {
      if (s.state === "sleeping") return to(s, "waking", now, STRETCH_MS);
      const taps = [...s.taps.filter((t) => now - t < POKE_WINDOW_MS), now];
      if (taps.length >= POKE_COUNT) return to(s, "playful", now, PLAYFUL_MS, { taps: [], stretchedIdle: false });
      return to(s, "happy", now, HAPPY_MS, { taps, stretchedIdle: false });
    }
    case "pressStart":
      return s.state === "sleeping" ? s : to(s, "petting", now, PET_MAX_MS, { stretchedIdle: false });
    case "pressEnd":
      return s.state === "petting" ? to(s, "idle", now) : s;
    case "idleFor":
      if (s.state === "idle" && !s.stretchedIdle && e.ms >= STRETCH_IDLE_MS) return to(s, "stretching", now, STRETCH_MS, { stretchedIdle: true });
      return s;
    case "yawn":
      return s.state === "idle" || s.state === "sitting" ? to(s, "yawning", now, YAWN_MS) : s;
    case "enterBedtime":
      if (s.bedtime) return s;
      return to({ ...s, bedtime: true }, "yawning", now, YAWN_MS);
    case "leaveBedtime":
      if (!s.bedtime) return s;
      return to({ ...s, bedtime: false, resleepAt: undefined }, "stretching", now, STRETCH_MS);
    case "perchFound":
      return s.state === "idle" ? to(s, "walking", now) : s;
    case "arrived":
      return s.state === "walking" ? to(s, "sitting", now) : s;
    case "leavePerch":
      return s.state === "walking" || s.state === "sitting" ? to(s, "idle", now) : s;
  }
}

/** The pet's visible mood: engagement + time of day only. */
export function moodOf(state: PetState, timeOfDay: TimeOfDay): PetMood {
  switch (state) {
    case "happy": return "happy";
    case "playful": return "playful";
    case "petting": return "petting";
    case "yawning": case "sleepy": return "sleepy";
    case "sleeping": return "sleeping";
    case "stretching": case "waking": return "calm";
    default: return timeOfDay === "evening" || timeOfDay === "night" ? "calm" : "neutral";
  }
}
