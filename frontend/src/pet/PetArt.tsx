// Static pet art: picks the species drawing and sets data-mood. No timers, aria-hidden.
import type { CSSProperties } from "react";
import "./rig.css";
import "./pet.css";
import { Cat } from "./species/Cat";
import type { PetMood, Species } from "./types";

// Fox and bunny arrive in phase 02; until then they render the cat.
const DRAW = { cat: Cat, fox: Cat, bunny: Cat } as const;

export function PetArt({ species, mood, size = 256, accessories = [], animated = false }: {
  species: Species; mood: PetMood; size?: number; accessories?: readonly string[]; animated?: boolean;
}) {
  const Draw = DRAW[species] ?? Cat;
  return <div className="pet-art" data-mood={mood} data-species={species} data-size={size < 96 ? "sm" : "md"}
    data-static={animated ? undefined : ""} data-acc={accessories.join(" ") || undefined}
    style={{ "--pet-size": `${size}px` } as CSSProperties} aria-hidden="true">
    <Draw />
  </div>;
}
