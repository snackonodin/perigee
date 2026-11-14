// Pet preferences shared by the corner pet and Settings: hidden, muted, snooze, and the
// "Breathe with me" signal. Persisted in localStorage (try/catch via dialog/storage.ts).
import { useSyncExternalStore } from "react";
import { SNOOZE_MS } from "./petConfig";
import { KEYS, isMuted, readKey, snoozedUntil, writeKey } from "./dialog/storage";

const subs = new Set<() => void>();
let version = 0;
const notify = () => { version++; subs.forEach((f) => f()); };
const subscribe = (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; };
let buddyListener: (() => void) | null = null;

export const petStore = {
  hidden: () => readKey(KEYS.hidden) === "true",
  muted: isMuted,
  snoozedUntil,
  setHidden(v: boolean) { writeKey(KEYS.hidden, v ? "true" : null); notify(); },
  setMuted(v: boolean) { writeKey(KEYS.muted, v ? "true" : null); notify(); },
  snooze(now = Date.now()) { writeKey(KEYS.snoozeUntil, String(now + SNOOZE_MS)); notify(); },
  unsnooze() { writeKey(KEYS.snoozeUntil, null); notify(); },
  startBuddy() { buddyListener?.(); },
  onBuddy(fn: () => void) { buddyListener = fn; return () => { if (buddyListener === fn) buddyListener = null; }; },
};

/** Re-renders when any pet preference changes. */
export function usePetPrefs() {
  useSyncExternalStore(subscribe, () => version, () => version);
  return { hidden: petStore.hidden(), muted: petStore.muted(), snoozedUntil: petStore.snoozedUntil() };
}
