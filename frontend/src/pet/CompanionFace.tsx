// Legacy compatibility for the old src/companion/ API: static art, no timers, aria-hidden.
import { PetArt } from "./PetArt";
import type { CharacterId, Mood, PetMood, Species } from "./types";

export const LEGACY_CHARACTER_TO_SPECIES: Readonly<Record<CharacterId, Species>> = { nimbus: "cat", pip: "fox", lumi: "bunny" };

export const CHARACTERS: ReadonlyArray<{ id: CharacterId; name: string; personality: string }> = [
  { id: "nimbus", name: "Miso the cat", personality: "A soft-spoken cat who is never in a hurry." },
  { id: "pip", name: "Ember the fox", personality: "A cheerful fox who loves small wins." },
  { id: "lumi", name: "Clover the bunny", personality: "A thoughtful bunny who listens more than talks." },
];

/** The pet never looks sad: concerned -> calm, encouraging -> happy, tired -> sleepy. */
const MOOD: Record<Mood, PetMood> = { neutral: "neutral", happy: "happy", calm: "calm", encouraging: "happy", concerned: "calm", tired: "sleepy", sleeping: "sleeping" };

export function CompanionFace({ character, mood, size = 96 }: { character: CharacterId; mood: Mood; size?: number }) {
  return <PetArt species={LEGACY_CHARACTER_TO_SPECIES[character] ?? "cat"} mood={MOOD[mood] ?? "neutral"} size={size} />;
}
