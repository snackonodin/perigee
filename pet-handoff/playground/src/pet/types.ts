// PHASE 01 replaces this file with the full contents of ../../../contract.d.ts, converted
// to real exports (keep every name). This minimal version only lets the playground compile.
export type Species = "cat" | "fox" | "bunny";
export type PersonaId = "autonomous_pioneer" | "dynamic_explorer" | "internal_deliberator" | "steady_anchor" | "default";
export type TimeOfDay = "morning" | "day" | "evening" | "night";
export interface PetContext {
  species: Species;
  personaId: PersonaId;
  timeOfDay: TimeOfDay;
  safetyActive: boolean;
  reducedMotion: boolean;
  streakDays: number;
  nightsLogged: number;
}
export interface PetProps extends PetContext {
  petName?: string;
  placement?: "corner" | "stage";
  size?: number;
  onHiddenChange?: (hidden: boolean) => void;
}
