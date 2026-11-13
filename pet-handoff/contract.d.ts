/**
 * contract.d.ts: the public surface of src/pet/. Copy these declarations into
 * src/pet/types.ts as real `export type` / `export interface` code (phase 01) and
 * implement the values in phase 06. Do not rename or remove anything here.
 *
 * The pet REPLACES the app's current src/companion/. That module's public props are
 * kept below under "Legacy compatibility", so existing call sites keep compiling.
 */

// ---------------------------------------------------------------- inputs

export type Species = "cat" | "fox" | "bunny";

/** Persona ids from personas.json. "default" = the person has no persona yet. */
export type PersonaId =
  | "autonomous_pioneer"
  | "dynamic_explorer"
  | "internal_deliberator"
  | "steady_anchor"
  | "default";

export type Tone = "warm" | "quiet" | "bright";

export type TimeOfDay = "morning" | "day" | "evening" | "night";

/**
 * Everything the host app gives the pet. This is the COMPLETE list.
 * The pet never receives scores, vitals, survey answers or results, clinical values,
 * or the engine's Watch/Alert status. Do not add fields for them.
 */
export interface PetContext {
  species: Species;
  personaId: PersonaId;
  timeOfDay: TimeOfDay;
  /** true while the app's safety screen is open. Pet renders NOTHING and runs nothing. */
  safetyActive: boolean;
  /** true if the user turned on "Reduce motion" (the pet ALSO checks the media query). */
  reducedMotion: boolean;
  /** consecutive nights logged; used only for the streak_milestone line at 3/7/14/30 */
  streakDays: number;
  /** lifetime nights logged, never decreases; drives accessory unlocks at 3/7/14/30 */
  nightsLogged: number;
}

/** Props of the main <Pet /> component. */
export interface PetProps extends PetContext {
  /** optional display name used in {petName}; default per species: "Miso", "Ember", "Clover" */
  petName?: string;
  /** "corner" = 96x96 slot (default); "stage" = free walking over [data-pet-perch] panels */
  placement?: "corner" | "stage";
  /** rendered size in CSS px for the art box; default 96 */
  size?: number;
  /** called after the user hides the pet with its own control */
  onHiddenChange?: (hidden: boolean) => void;
}

// ---------------------------------------------------------------- events

export type PetEventName =
  | "first_run"
  | "app_open"
  | "welcome_back"
  | "quiz_start"
  | "quiz_complete"
  | "bedtime_near"
  | "sleep_start"
  | "wake"
  | "night_logged"
  | "streak_milestone"
  | "idle_long"
  | "pet_tap"
  | "goodbye";

/** Event detail. It carries NO health data: quiz_complete has no score or result. */
export interface PetEvent {
  name: PetEventName;
  /** epoch ms; emit() fills it in if omitted */
  at?: number;
  /** only for streak_milestone: 3 | 7 | 14 | 30 */
  milestone?: 3 | 7 | 14 | 30;
}

/**
 * Host → pet event bus. Safe to call any time: it is a no-op while safetyActive is true,
 * while dialog is muted/snoozed, or while a form field has focus (the line is dropped,
 * not queued).
 */
export declare function emit(event: PetEventName | PetEvent): void;

// ---------------------------------------------------------------- dialog

export type LineTod = TimeOfDay | "any";

export interface DialogLine {
  /** "<event>.<tone>.<nn>", unique */
  id: string;
  /** <= 90 chars, may contain {petName} */
  text: string;
  tod: LineTod;
  /** relative weight, 1 = normal, integer 1..5 */
  weight: number;
}

/** cache.json shape: event -> tone -> lines */
export type DialogCache = Record<PetEventName, Record<Tone, DialogLine[]>>;

// ---------------------------------------------------------------- internal mood

/** The pet's own mood. Comes ONLY from engagement and time of day. */
export type PetMood = "neutral" | "happy" | "calm" | "playful" | "sleepy" | "sleeping" | "petting";

// ---------------------------------------------------------------- legacy compatibility
// From the current src/companion/ (CompanionFace.tsx, characters.tsx). Keep exporting.

export type CharacterId = "nimbus" | "pip" | "lumi";

/** Legacy mood names. Map: neutral->neutral, happy->happy, calm->calm,
 *  encouraging->happy, concerned->calm (the pet never looks sad), tired->sleepy,
 *  sleeping->sleeping. */
export type Mood = "neutral" | "happy" | "calm" | "encouraging" | "concerned" | "tired" | "sleeping";

/** Legacy character -> new species. */
export declare const LEGACY_CHARACTER_TO_SPECIES: Readonly<Record<CharacterId, Species>>;
// value: { nimbus: "cat", pip: "fox", lumi: "bunny" }

export declare const CHARACTERS: ReadonlyArray<{ id: CharacterId; name: string; personality: string }>;

/** Legacy static face: <CompanionFace character="nimbus" mood="happy" />. Renders the
 *  mapped species, static (no timers), aria-hidden. */
export interface CompanionFaceProps {
  character: CharacterId;
  mood: Mood;
}

/** Legacy imperative API (mirrors window.companion in dev builds). */
export interface CompanionApi {
  setMood(name: Mood): void;
  /** returns false if muted, safetyActive, rate-limited, or the text fails the banned-terms guard */
  say(text: string): boolean;
  perchTo(elementId: string): void;
  setCharacter(id: CharacterId): void;
  show(): void;
  hide(): void;
  setMuted(muted: boolean): void;
  readonly state: { mood: Mood | "hidden"; character: CharacterId; visible: boolean; muted: boolean };
}

// ---------------------------------------------------------------- module exports (src/pet/index.ts)
// export { Pet } from "./Pet";                    // (props: PetProps) => JSX.Element | null
// export { PetControls } from "./PetControls";    // hide-pet + mute-dialog (+ breathing buddy)
// export { PetArt } from "./PetArt";              // static art: ({ species, mood, size? }) — used by render.mjs and CompanionFace
// export { emit } from "./emit";
// export { CompanionFace, CHARACTERS, LEGACY_CHARACTER_TO_SPECIES } from "./CompanionFace";
// export type * from "./types";
