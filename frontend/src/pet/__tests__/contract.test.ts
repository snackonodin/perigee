import { describe, expect, it } from "vitest";
import * as pet from "../index";
import type { PetContext, PetEvent, PetProps } from "../types";

describe("public contract", () => {
  it("PetProps compiles with exactly the contract fields", () => {
    const ctx: PetContext = { species: "bunny", personaId: "steady_anchor", timeOfDay: "evening", safetyActive: false, reducedMotion: false, streakDays: 2, nightsLogged: 9 };
    const p: PetProps = { ...ctx, petName: "Clover", placement: "corner", size: 96, onHiddenChange: () => {} };
    const e: PetEvent = { name: "streak_milestone", milestone: 7 };
    expect(p.species).toBe("bunny");
    expect(e.name).toBe("streak_milestone");
  });
  it("index exports every runtime name", () => {
    for (const name of ["Pet", "PetControls", "PetArt", "emit", "CompanionFace", "CHARACTERS", "LEGACY_CHARACTER_TO_SPECIES"]) {
      expect(pet).toHaveProperty(name);
    }
  });
});
