// Static pet art: picks the species drawing and sets data-mood. No timers, aria-hidden.
import type { CSSProperties } from "react";
import "./rig.css";
import "./pet.css";
import { Bunny } from "./species/Bunny";
import { Cat } from "./species/Cat";
import { Fox } from "./species/Fox";
import type { PetMood, Species } from "./types";

const DRAW = { cat: Cat, fox: Fox, bunny: Bunny } as const;

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
