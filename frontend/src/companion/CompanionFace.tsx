import type { CharacterId } from "./characters";
import { CharacterBody } from "./characters";

export type Mood = "neutral" | "happy" | "calm" | "encouraging" | "concerned" | "tired" | "sleeping";

export function CompanionFace({ character, mood }: { character: CharacterId; mood: Mood }) {
  return <div className="pet" data-character={character} data-mood={mood} aria-hidden="true">
    <CharacterBody id={character} />
  </div>;
}
