import { type FormEvent, useState } from "react";
import type { components } from "../api/schema";
import { BRAND } from "../brand";
import { Icon } from "../components/icons";
import { TextReveal } from "../components/motion";

export type DemoBody = components["schemas"]["DemoIn"];
type Profile = components["schemas"]["DemoProfileIn"];

// Three NASA-calibrated ISS crew members (people synthetic). Neutral one-line labels.
const CREW = [
  { id: "iss-flight", line: "In flight, ~6 h sleep, a slow breathing drift" },
  { id: "iss-aligned", line: "Circadian-aligned, ~6.4 h, steady" },
  { id: "iss-misaligned", line: "Misaligned schedule, ~5.4 h, a tougher week" },
] as const;
const REGULARITY = ["Very irregular", "Irregular", "Somewhat regular", "Regular", "Very regular"];
const STRESS = ["None", "Low", "Moderate", "High", "Very high"];
const MOOD = ["Very low", "Low", "Okay", "Good", "Very good"];

function Scale({ name, legend, labels, value, onChange }: { name: string; legend: string; labels: string[]; value: number; onChange(v: number): void }) {
  return <fieldset className="demo-scale">
    <legend>{legend}</legend>
    <div className="demo-scale-options">{labels.map((l, i) => (
      <label key={l} className={value === i ? "selected" : undefined}>
        <input type="radio" name={name} value={i} checked={value === i} onChange={() => onChange(i)} />{l}
      </label>
    ))}</div>
  </fieldset>;
}

/** First screen for signed-out visitors when the public demo is on: live a day as an ISS crew
 *  member, or make your own synthetic nights from five answers. No sign-in needed. */
export function DemoChoice({ busy, error, onChoose, onAccount }: {
  busy: "crew" | "profile" | null; error: string | null;
  onChoose(body: DemoBody, kind: "crew" | "profile"): void; onAccount(): void;
}) {
  const [profile, setProfile] = useState<Profile>({ sleep_hours: 7, regularity: 2, stress: 1, mood: 3, recent_change: false });
  const set = (p: Partial<Profile>) => setProfile((x) => ({ ...x, ...p }));
  const make = (e: FormEvent) => { e.preventDefault(); onChoose({ profile }, "profile"); };
  const locked = busy !== null;
  return <main className="demo-choice" aria-labelledby="demo-title">
    <header className="demo-head">
      <p className="auth-brand"><span className="brand-mark" aria-hidden="true"><Icon name="brand" size={22}/></span>{BRAND}</p>
      <TextReveal id="demo-title" text={`Explore ${BRAND}`} />
      <p className="muted">No sign-in needed. Pick a way in; you get your own private copy.</p>
    </header>
    <div className="demo-cards">
      <section className="demo-card" aria-labelledby="crew-title">
        <h2 id="crew-title">Live a day as an astronaut</h2>
        <p className="muted">Pick one of three ISS crew members. Sleep patterns are calibrated to published NASA studies; the people are synthetic.</p>
        <ul className="demo-crew">{CREW.map((c) => (
          <li key={c.id}><button type="button" className="demo-crew-option" disabled={locked} onClick={() => onChoose({ crew: c.id }, "crew")}>
            <strong>{c.line.slice(0, c.line.indexOf(","))}</strong><span>{c.line.slice(c.line.indexOf(",") + 2)}</span></button></li>
        ))}</ul>
        {busy === "crew" && <p className="demo-busy" role="status">Preparing your crew member…</p>}
      </section>
      <section className="demo-card" aria-labelledby="own-title">
        <h2 id="own-title">Make your own</h2>
        <form onSubmit={make} aria-labelledby="own-title" className="demo-own">
          <label className="demo-slider">How many hours do you usually sleep? <output>{profile.sleep_hours} h</output>
            <input type="range" min={4} max={10} step={0.5} value={profile.sleep_hours} onChange={(e) => set({ sleep_hours: Number(e.target.value) })} />
          </label>
          <Scale name="regularity" legend="How regular is your sleep schedule?" labels={REGULARITY} value={profile.regularity} onChange={(v) => set({ regularity: v })} />
          <Scale name="stress" legend="Stress lately" labels={STRESS} value={profile.stress} onChange={(v) => set({ stress: v })} />
          <Scale name="mood" legend="Mood lately" labels={MOOD} value={profile.mood} onChange={(v) => set({ mood: v })} />
          <label className="demo-check"><input type="checkbox" checked={profile.recent_change} onChange={(e) => set({ recent_change: e.target.checked })} />
            New schedule, travel or illness lately</label>
          <button type="submit" disabled={locked} aria-busy={busy === "profile"}>{busy === "profile" ? "Building your 14 nights…" : "Build my nights"}</button>
          <p className="demo-note">Synthetic data for exploring the app, not a health assessment.</p>
        </form>
      </section>
    </div>
    <p className="error" role="alert">{error}</p>
    <p className="demo-account"><button type="button" className="link" onClick={onAccount}>I have an account</button></p>
  </main>;
}
