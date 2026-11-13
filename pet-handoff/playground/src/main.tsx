// Playground shell: mock context controls + three glass panels the pet can perch on.
// You may edit this file to test things, but it is NOT returned. Only src/pet/ is.
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import "./tokens.css";
import "./playground.css";
import { Pet } from "./pet";
import type { PetContext, PersonaId, Species, TimeOfDay } from "./pet/types";
import { DEFAULT_CONTEXT, timeOfDayFor } from "./mockContext";

const SPECIES: Species[] = ["cat", "fox", "bunny"];
const PERSONAS: PersonaId[] = ["default", "autonomous_pioneer", "dynamic_explorer", "internal_deliberator", "steady_anchor"];
const TODS: TimeOfDay[] = ["morning", "day", "evening", "night"];

function App() {
  const [ctx, setCtx] = useState<PetContext>({ ...DEFAULT_CONTEXT, timeOfDay: timeOfDayFor(new Date()) });
  const set = <K extends keyof PetContext>(k: K, v: PetContext[K]) => setCtx((c) => ({ ...c, [k]: v }));

  return (
    <div className="pg">
      <div className="aurora" aria-hidden="true" />
      <header className="glass pg-controls">
        <h1>Pet playground</h1>
        <label>Species <select value={ctx.species} onChange={(e) => set("species", e.target.value as Species)}>
          {SPECIES.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>Persona <select value={ctx.personaId} onChange={(e) => set("personaId", e.target.value as PersonaId)}>
          {PERSONAS.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>Time <select value={ctx.timeOfDay} onChange={(e) => set("timeOfDay", e.target.value as TimeOfDay)}>
          {TODS.map((s) => <option key={s}>{s}</option>)}</select></label>
        <label>Streak <input type="number" min={0} value={ctx.streakDays} onChange={(e) => set("streakDays", Number(e.target.value))} /></label>
        <label>Nights <input type="number" min={0} value={ctx.nightsLogged} onChange={(e) => set("nightsLogged", Number(e.target.value))} /></label>
        <label><input type="checkbox" checked={ctx.reducedMotion} onChange={(e) => set("reducedMotion", e.target.checked)} /> Reduced motion</label>
        <label><input type="checkbox" checked={ctx.safetyActive} onChange={(e) => set("safetyActive", e.target.checked)} /> Safety screen open</label>
      </header>

      <main className="pg-panels">
        <section className="glass" data-pet-perch><h2>Tonight</h2><p>A glass card the pet can walk on and sit on.</p></section>
        <section className="glass" data-pet-perch><h2>Weekly check-in</h2>
          <form data-pet-avoid onSubmit={(e) => e.preventDefault()}>
            <label>Sample field <input placeholder="The pet must stay quiet while this has focus" /></label>
          </form>
        </section>
        <section className="glass" data-pet-perch><h2>Sleep</h2><p>Another perch.</p></section>
      </main>

      {ctx.safetyActive && (
        <div className="pg-safety" role="dialog" aria-modal="true" aria-labelledby="pg-safety-h">
          <h2 id="pg-safety-h">Safety screen (mock)</h2>
          <p>In the real app this shows support contacts. The pet must be completely gone.</p>
          <button onClick={() => set("safetyActive", false)}>Close mock safety screen</button>
        </div>
      )}

      <Pet {...ctx} placement="stage" />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
