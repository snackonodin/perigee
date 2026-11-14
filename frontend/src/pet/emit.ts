// Host -> pet event bus. Forwards to the mounted live pet only; while no pet is mounted
// (hidden, or the safety screen is open) emit() is a no-op and nothing is queued.
import type { PetEvent, PetEventName } from "./types";

type Listener = (e: PetEvent) => void;
let listener: Listener | null = null;

export function emit(event: PetEventName | PetEvent): void {
  if (!listener) return;
  const e: PetEvent = typeof event === "string" ? { name: event } : { ...event };
  e.at ??= Date.now();
  listener(e);
}

/** Used by the live pet. Returns the unsubscribe function. */
export function subscribe(fn: Listener): () => void {
  listener = fn;
  return () => { if (listener === fn) listener = null; };
}
