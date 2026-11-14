// Accessories unlock from LIFETIME nights logged (3/7/14/30) and are kept forever:
// a smaller nightsLogged later, or a broken streak, never removes one.
import { ACCESSORY_NIGHTS } from "./petConfig";

export type Accessory = "scarf" | "star" | "moon" | "crown";
const ORDER: Accessory[] = ["scarf", "star", "moon", "crown"];
const KEY = "pet.accessories";

function load(): Accessory[] {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(raw) ? raw.filter((a): a is Accessory => ORDER.includes(a)) : [];
  } catch { return []; }
}

export function unlocked(nightsLogged: number): Accessory[] {
  const now = ORDER.filter((_, i) => nightsLogged >= ACCESSORY_NIGHTS[i]);
  const all = ORDER.filter((a) => now.includes(a) || load().includes(a));
  try { localStorage.setItem(KEY, JSON.stringify(all)); } catch { /* storage unavailable: still render */ }
  return all;
}
