// Persona -> tone (pet-handoff/personas.json). Tone changes wording only, never behavior.
import type { PersonaId, Tone } from "../types";

const TONE: Record<PersonaId, Tone> = {
  autonomous_pioneer: "bright",
  dynamic_explorer: "warm",
  internal_deliberator: "quiet",
  steady_anchor: "quiet",
  default: "warm",
};

export const toneFor = (personaId: PersonaId): Tone => TONE[personaId] ?? "warm";
