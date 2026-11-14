// Chooses one line: time-of-day filter, skip the last 8 shown, weighted random, per-event
// cooldown. Returns null when muted, snoozed, a form field has focus, or safety is active.
import { DIALOG_COOLDOWN_MS, DIALOG_RECENT } from "../petConfig";
import type { DialogCache, DialogLine, PetEventName, TimeOfDay, Tone } from "../types";
import { isMuted, KEYS, readKey, snoozedUntil, writeKey } from "./storage";

export interface PickDeps {
  random?: () => number;
  safetyActive?: boolean;
  /** last time each event showed a line (in-memory, per pet) */
  lastShown?: Partial<Record<PetEventName, number>>;
  doc?: Pick<Document, "activeElement">;
}

export function formFocused(doc: Pick<Document, "activeElement"> = document): boolean {
  const el = doc.activeElement as HTMLElement | null;
  if (!el || el === document.body) return false;
  return el.matches?.("input, textarea, select, [contenteditable=''], [contenteditable='true']") ?? false;
}

function recent(): string[] {
  try { const r = JSON.parse(readKey(KEYS.recent) ?? "[]"); return Array.isArray(r) ? r.filter((x) => typeof x === "string") : []; } catch { return []; }
}

export function pickLine(cache: DialogCache, event: PetEventName, tone: Tone, tod: TimeOfDay, now: number, deps: PickDeps = {}): DialogLine | null {
  if (deps.safetyActive || isMuted() || now < snoozedUntil() || formFocused(deps.doc)) return null;
  const cooldown = DIALOG_COOLDOWN_MS[event] ?? DIALOG_COOLDOWN_MS.default;
  const last = deps.lastShown?.[event];
  if (last != null && now - last < cooldown) return null;
  const pool = (cache[event]?.[tone] ?? []).filter((l) => l.tod === tod || l.tod === "any");
  if (!pool.length) return null;
  let seen = recent();
  let options = pool.filter((l) => !seen.includes(l.id));
  if (!options.length) { seen = []; options = pool; }
  const random = deps.random ?? Math.random;
  const total = options.reduce((n, l) => n + l.weight, 0);
  let r = random() * total, line = options[options.length - 1];
  for (const l of options) { r -= l.weight; if (r < 0) { line = l; break; } }
  writeKey(KEYS.recent, JSON.stringify([...seen, line.id].slice(-DIALOG_RECENT)));
  if (deps.lastShown) deps.lastShown[event] = now;
  return line;
}

export const fill = (text: string, petName: string) => text.split("{petName}").join(petName);
