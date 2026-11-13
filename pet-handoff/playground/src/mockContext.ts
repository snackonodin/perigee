// Mock PetContext for the playground. The real app passes the same fields.
// There is NO backend: everything here is local state.
import type { PetContext } from "./pet/types";

export const DEFAULT_CONTEXT: PetContext = {
  species: "cat",
  personaId: "default",
  timeOfDay: "day",
  safetyActive: false,
  reducedMotion: false,
  streakDays: 2,
  nightsLogged: 5,
};

export function timeOfDayFor(date: Date): PetContext["timeOfDay"] {
  const h = date.getHours();
  if (h >= 5 && h < 12) return "morning";
  if (h >= 12 && h < 17) return "day";
  if (h >= 17 && h < 22) return "evening";
  return "night";
}
