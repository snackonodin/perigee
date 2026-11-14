// Mounts the companion pet in #companion-slot and gives it ONLY what the pet contract
// allows (pet-handoff/contract.d.ts PetContext): species, persona tone, station time of
// day, the safety flag, reduced motion and night counts. Never scores, levels, answers or
// Watch/Alert status: the persona name is read from the engine output and nothing else.
import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import type { NightOut } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { emit, Pet, type PersonaId, type PetBubble, type Species, type TimeOfDay } from "../pet";
import { CHECKIN_SAVED, usePersona } from "../persona/PersonaProvider";
import { SAFETY_FALLBACK } from "../safety/safety";
import { useSafety, useSafetyActive } from "../safety/SafetyProvider";
import type { components } from "../api/schema";

type PetBubbleOut = components["schemas"]["PetBubbleOut"];
const ANIMATION: Record<string, PetBubble["animation"]> = {
  calm_float: "calm", calm_present: "calm", curious_tilt: "tilt", cozy_listen: "cozy", cozy_support: "cozy", cozy_glow: "cozy",
};
/** Server bubble -> pet props. Badge is visual only and never red. */
export function toPetBubble(b: PetBubbleOut): PetBubble | null {
  if (!b.bubble) return null;
  return {
    id: b.id, text: b.bubble, tryLine: b.micro_try ?? null, playful: b.playful,
    badge: b.badge === "green" ? "green" : b.badge === "amber" ? "amber" : "neutral",
    animation: ANIMATION[b.pet_animation] ?? "calm",
  };
}

const PERSONA: Record<string, PersonaId> = {
  "Autonomous Pioneer": "autonomous_pioneer", "Dynamic Explorer": "dynamic_explorer",
  "Internal Deliberator": "internal_deliberator", "Steady Anchor": "steady_anchor",
};
const MILESTONES = [3, 7, 14, 30] as const;
const DAY = 86_400_000;

const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } };

/** Station clock (minutes since midnight) from the profile offset; null offset = UTC. */
export function stationMinutes(offsetMin: number | null | undefined, now = Date.now()): number {
  const d = new Date(now + (offsetMin ?? 0) * 60000);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}
/** morning 05-12, day 12-17, evening 17-22, night 22-05, in station time. */
export function timeOfDayAt(minutes: number): TimeOfDay {
  const h = minutes / 60;
  return h >= 5 && h < 12 ? "morning" : h >= 12 && h < 17 ? "day" : h >= 17 && h < 22 ? "evening" : "night";
}
/** Lifetime valid nights and the run of consecutive valid nights ending last night. */
export function nightCounts(nights: readonly NightOut[], today: string): { nightsLogged: number; streakDays: number } {
  const valid = new Set(nights.filter((n) => n.valid).map((n) => n.date));
  let streak = 0;
  for (let t = Date.parse(`${today}T00:00:00Z`) - DAY; valid.has(new Date(t).toISOString().slice(0, 10)); t -= DAY) streak++;
  return { nightsLogged: valid.size, streakDays: streak };
}
export function speciesPref(): Species {
  const s = read("pet.species");
  return s === "fox" || s === "bunny" ? s : "cat";
}

function useReducedMotionSwitch(): boolean {
  return useSyncExternalStore((cb) => {
    const o = new MutationObserver(cb);
    o.observe(document.documentElement, { attributes: true, attributeFilter: ["data-reduce-motion"] });
    return () => o.disconnect();
  }, () => document.documentElement.dataset.reduceMotion === "true", () => false);
}

export function CompanionHost() {
  const { me } = useAuth();
  const safetyActive = useSafetyActive();
  const { showSafety } = useSafety();
  const { persona } = usePersona();
  const reducedMotion = useReducedMotionSwitch();
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  const [species, setSpecies] = useState<Species>(speciesPref);
  const [wide, setWide] = useState(() => window.innerWidth >= 768);
  const [clock, setClock] = useState(() => Date.now());
  useEffect(() => { setSlot(document.getElementById("companion-slot")); }, []);
  useEffect(() => {
    const onSpecies = () => setSpecies(speciesPref());
    const onResize = () => setWide(window.innerWidth >= 768);
    window.addEventListener("pet-species", onSpecies);
    window.addEventListener("resize", onResize);
    const tick = window.setInterval(() => setClock(Date.now()), 60000);
    return () => { window.removeEventListener("pet-species", onSpecies); window.removeEventListener("resize", onResize); window.clearInterval(tick); };
  }, []);

  const today = useLoad(() => api.GET("/api/v1/today"));
  const to = new Date().toISOString().slice(0, 10), from = new Date(Date.now() - 365 * DAY).toISOString().slice(0, 10);
  const nights = useLoad(() => api.GET("/api/v1/nights", { params: { query: { from, to } } }), [from, to]);

  const engine = (today.data as { context_engine?: { dashboard_visualization_data?: { persona_matrix?: { quadrant_name?: string } } } | null } | undefined)?.context_engine;
  const quadrant = (persona?.available ? persona.persona_matrix?.quadrant_name : null) ?? engine?.dashboard_visualization_data?.persona_matrix?.quadrant_name ?? "";
  const personaId: PersonaId = PERSONA[quadrant] ?? "default";

  // one speech bubble chosen by the server: on app open and after every check-in or quiz.
  // A pending safety screen comes back as HALT_AND_OPEN_CRISIS_SCREEN: open the existing one.
  const [bubble, setBubble] = useState<PetBubble | null>(null);
  const loadBubble = useCallback(() => {
    api.GET("/api/v1/pet/bubble").then(({ data }) => {
      if (!data) return;
      if (data.ui_action === "HALT_AND_OPEN_CRISIS_SCREEN") { setBubble(null); showSafety(SAFETY_FALLBACK); return; }
      setBubble(toPetBubble(data));
    }).catch(() => { /* offline: the pet's own dialog cache still speaks */ });
  }, [showSafety]);
  useEffect(() => { loadBubble(); }, [loadBubble]);
  useEffect(() => {
    window.addEventListener(CHECKIN_SAVED, loadBubble);
    return () => window.removeEventListener(CHECKIN_SAVED, loadBubble);
  }, [loadBubble]);
  const minutes = stationMinutes(me?.station_time_offset_min, clock);
  const timeOfDay = timeOfDayAt(minutes);
  const counts = useMemo(() => nightCounts(nights.data ?? [], to), [nights.data, to]);

  // app events (no health data in any of them)
  useEffect(() => {
    if (safetyActive) return;
    const last = Number(read("pet.lastSeen") ?? 0);
    const firstRun = read("pet.firstRunDone") !== "true";
    const id = window.setTimeout(() => { if (!firstRun) emit(last && Date.now() - last > DAY ? "welcome_back" : "app_open"); }, 1200);
    write("pet.lastSeen", String(Date.now()));
    return () => window.clearTimeout(id);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- once per app open
  const latest = today.data?.latest_night?.date;
  useEffect(() => {
    if (!latest || safetyActive) return;
    const prev = read("pet.lastNight");
    if (prev && latest > prev) emit("night_logged");
    write("pet.lastNight", latest);
  }, [latest, safetyActive]);
  useEffect(() => {
    if (safetyActive) return;
    let done: number[] = [];
    try { const d = JSON.parse(read("pet.milestones") ?? "[]"); if (Array.isArray(d)) done = d; } catch { /* reset */ }
    const hit = MILESTONES.filter((m) => counts.streakDays >= m && !done.includes(m)).at(-1);
    if (hit) { emit({ name: "streak_milestone", milestone: hit }); write("pet.milestones", JSON.stringify([...done, ...MILESTONES.filter((m) => m <= hit)])); }
  }, [counts.streakDays, safetyActive]);
  // bedtime_near: 30 min before 22:00 station time (the pet has no station clock of its own)
  const bedtimeNear = minutes >= 21 * 60 + 30 && minutes < 22 * 60;
  useEffect(() => { if (bedtimeNear && !safetyActive) emit("bedtime_near"); }, [bedtimeNear, safetyActive]);

  if (!slot) return null;
  return createPortal(<Pet species={species} personaId={personaId} timeOfDay={timeOfDay} safetyActive={safetyActive}
    reducedMotion={reducedMotion} streakDays={counts.streakDays} nightsLogged={counts.nightsLogged}
    placement={wide ? "stage" : "corner"} size={wide ? 96 : 72} bubble={bubble} />, slot);
}
