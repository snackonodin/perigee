// Every localStorage access for the pet goes through these (try/catch: private mode,
// blocked storage or quota errors never break the pet).
export function readKey(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
export function writeKey(key: string, value: string | null): void {
  try { if (value == null) localStorage.removeItem(key); else localStorage.setItem(key, value); } catch { /* ignore */ }
}
export const KEYS = {
  recent: "pet.dialog.recent", muted: "pet.dialog.muted", snoozeUntil: "pet.dialog.snoozeUntil",
  hidden: "pet.hidden", firstRun: "pet.firstRunDone", lastSeen: "pet.lastSeen", lastNight: "pet.lastNight",
  milestones: "pet.milestones", species: "pet.species",
} as const;
export const isMuted = () => readKey(KEYS.muted) === "true";
export const snoozedUntil = () => Number(readKey(KEYS.snoozeUntil) ?? 0) || 0;
