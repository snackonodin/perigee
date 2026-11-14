import { useState } from "react";
import "./Persona.css";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { Instrument, InstrumentItem } from "../api/types";
import { CheckinForm } from "../components/CheckinForm";
import { AdviceList } from "../persona/AdviceList";
import { usePersona } from "../persona/PersonaProvider";

const QUIZ_ID = "psyche60";
// Engine axes: stability and agency on 4-20, quadrants split at the midpoint. Used only to place
// the dot; no number is ever shown.
const AXIS_MIN = 4, AXIS_MAX = 20;
const QUADRANTS = [
  { name: "Steady Anchor", x: "left", y: "top" },
  { name: "Autonomous Pioneer", x: "right", y: "top" },
  { name: "Internal Deliberator", x: "left", y: "bottom" },
  { name: "Dynamic Explorer", x: "right", y: "bottom" },
] as const;
const unit = (v: number) => Math.max(0, Math.min(1, (v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN)));

/** Two-axis plane: agency left to right, stability bottom to top, with the person's place. */
function Plane({ stability, agency, quadrant }: { stability: number; agency: number; quadrant: string }) {
  const S = 240, pad = 16, span = S - 2 * pad;
  const cx = pad + unit(agency) * span, cy = pad + (1 - unit(stability)) * span;
  return <figure className="persona-plane">
    <svg viewBox={`0 0 ${S} ${S}`} role="img" aria-label={`Your place on the plane: ${quadrant}`}>
      <rect className="plane-bg" x={pad} y={pad} width={span} height={span} rx="12" />
      {QUADRANTS.map((q) => <rect key={q.name} className={`plane-q${q.name === quadrant ? " current" : ""}`}
        x={q.x === "left" ? pad : S / 2} y={q.y === "top" ? pad : S / 2} width={span / 2} height={span / 2} rx="10" />)}
      <line className="plane-axis" x1={S / 2} y1={pad} x2={S / 2} y2={S - pad} />
      <line className="plane-axis" x1={pad} y1={S / 2} x2={S - pad} y2={S / 2} />
      {QUADRANTS.map((q) => <text key={q.name} aria-hidden="true" className={`plane-name${q.name === quadrant ? " current" : ""}`}
        x={q.x === "left" ? pad + 10 : S - pad - 10} y={q.y === "top" ? pad + 18 : S - pad - 10} textAnchor={q.x === "left" ? "start" : "end"}>{q.name}</text>)}
      <circle className="plane-dot" cx={cx} cy={cy} r="7" />
    </svg>
    <figcaption>Across: agency, how much you like to steer. Up: stability, how settled you tend to feel.</figcaption>
  </figure>;
}

/** The persona questions, one module (six statements) per page. Not a check-in. */
function PersonaQuiz({ onFinished, onCancel }: { onFinished(): void; onCancel(): void }) {
  const quiz = useLoad(() => api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: QUIZ_ID } } }));
  return <section className="persona-quiz" aria-labelledby="persona-quiz-title">
    <div className="persona-section-title"><h2 id="persona-quiz-title">Persona questions</h2>
      <p className="muted">60 short statements on ten pages, about 8 minutes. There are no right or wrong answers.</p></div>
    <LoadState state={quiz} label="the persona questions">{instrument =>
      <CheckinForm instrument={instrument as unknown as Instrument} groupBy={(i: InstrumentItem) => i.module ?? i.key}
        submitLabel="See my persona" onSubmitted={onFinished}/>}</LoadState>
    <button type="button" className="link persona-quiz-cancel" onClick={onCancel}>Cancel</button>
  </section>;
}

export function Persona() {
  const { persona, loading, reload } = usePersona();
  const [quizOpen, setQuizOpen] = useState(false);
  const head = <header className="persona-head"><div><h1>Persona</h1><p>How you like to work and rest, in your own words. Private to you.</p></div></header>;
  if (quizOpen) return <div className="persona-page">{head}<PersonaQuiz onCancel={() => setQuizOpen(false)} onFinished={() => { setQuizOpen(false); reload(); }}/></div>;
  if (loading && !persona) return <div className="persona-page">{head}<p className="muted">Loading your persona…</p></div>;
  const matrix = persona?.available && persona.source === QUIZ_ID ? persona.persona_matrix : null;
  return <div className="persona-page">{head}
    {!matrix
      ? <section className="persona-empty"><h2>Your persona</h2><p>Your persona appears after the persona questions. It shapes how Perigee words things for you; it is not a score.</p>
          <button type="button" className="persona-take" onClick={() => setQuizOpen(true)}>Take the persona questions (about 8 min)</button></section>
      : <div className="persona-layout">
          <section className="persona-quadrant-panel" aria-labelledby="quadrant-title">
            <h2 id="quadrant-title">{matrix.quadrant_name}</h2>
            <p className="muted">Your place on two everyday axes: how settled you tend to feel, and how much you like to steer. No place is better than another.</p>
            <Plane stability={matrix.stability_score} agency={matrix.agency_score} quadrant={matrix.quadrant_name} />
            <button type="button" className="link persona-retake" onClick={() => setQuizOpen(true)}>Retake the persona questions</button>
          </section>
          <section className="persona-advice-panel"><AdviceList emptyText="No suggestions right now. They appear when your nights or check-ins point to something worth trying." /><p className="persona-footnote">Suggestions follow your latest night and check-ins. They are not medical advice.</p></section>
        </div>}
  </div>;
}
