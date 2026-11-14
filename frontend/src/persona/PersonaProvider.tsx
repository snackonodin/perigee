// The person's persona (psyche60): quadrant, feedback-style flags and context-matched advice.
// Fetched once per session and again whenever a check-in is saved, so new advice shows at once.
// Style flags only change wording and colour; they never touch scores, alerts or the safety path.
import { createContext, type ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type PersonaOut = components["schemas"]["PersonaOut"];
export type PersonaStyle = Partial<Record<
  "show_raw_telemetry" | "calm_non_alarming_tone" | "structured_checklist_mode" | "private_scheduled_recovery" | "baseline_only_framing" | "privacy_lock_reminder",
  boolean>>;

/** Fired by CheckinForm after a response is stored (no data on the event). */
export const CHECKIN_SAVED = "perigee:checkin-saved";
export const announceCheckinSaved = () => window.dispatchEvent(new Event(CHECKIN_SAVED));

interface PersonaState { persona: PersonaOut | null; style: PersonaStyle; loading: boolean; reload(): void }
const Ctx = createContext<PersonaState>({ persona: null, style: {}, loading: false, reload: () => {} });
export const usePersona = () => useContext(Ctx);

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [persona, setPersona] = useState<PersonaOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [n, setN] = useState(0);
  const reload = useCallback(() => setN((x) => x + 1), []);
  useEffect(() => {
    let live = true;
    setLoading(true);
    api.GET("/api/v1/persona").then(({ data }) => { if (live) { setPersona(data ?? null); setLoading(false); } })
      .catch(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [n]);
  useEffect(() => {
    window.addEventListener(CHECKIN_SAVED, reload);
    return () => window.removeEventListener(CHECKIN_SAVED, reload);
  }, [reload]);
  const style: PersonaStyle = persona?.available ? (persona.style ?? {}) : {};
  // calm tone: no red anywhere in the app (the safety screen keeps its own colours, see shell.css)
  useEffect(() => {
    const root = document.documentElement;
    if (style.calm_non_alarming_tone) root.dataset.calm = "true"; else delete root.dataset.calm;
    return () => { delete root.dataset.calm; };
  }, [style.calm_non_alarming_tone]);
  return <Ctx.Provider value={{ persona, style, loading, reload }}>{children}</Ctx.Provider>;
}
