import { useState } from "react";
import "./Persona.css";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { Instrument, InstrumentItem } from "../api/types";
import { CheckinForm } from "../components/CheckinForm";
import { AdviceList } from "../persona/AdviceList";
import { usePersona } from "../persona/PersonaProvider";
import { useAuth } from "../auth/AuthProvider";
import { ITEMS_PER_PAGE, nextPart, PARTS, type PartId, stableShuffle } from "../persona/parts";

const BANK = "psyche60";
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

type PartInstrument = Instrument & { part?: { index: number; of: number; blurb?: string } };

/** One part: 12 statements in a stable per-person shuffle, four per page, through the same
 *  CheckinForm as every check-in (so the safety path is identical). Not a check-in itself. */
function PartQuiz({ partId, onFinished, onCancel }: { partId: PartId; onFinished(): void; onCancel(): void }) {
  const { me } = useAuth();
  const quiz = useLoad(() => api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: partId } } }), [partId]);
  const part = PARTS.find((p) => p.id === partId)!;
  return <section className="persona-quiz" aria-labelledby="persona-quiz-title">
    <div className="persona-section-title"><h2 id="persona-quiz-title">{part.name}</h2>
      <p className="muted">Part {PARTS.indexOf(part) + 1} of {PARTS.length} · 12 short statements, about 1.5 minutes. There are no right or wrong answers.</p></div>
    <LoadState state={quiz} label="this part">{raw => {
      const inst = raw as unknown as PartInstrument;
      const items = stableShuffle(inst.items, me?.id ?? "anon", partId);
      const page = new Map(items.map((it, i) => [it.key, String(Math.floor(i / ITEMS_PER_PAGE))]));
      return <CheckinForm key={partId} instrument={{ ...inst, name: part.name, items }} groupBy={(i: InstrumentItem) => page.get(i.key) ?? i.key}
        submitLabel="Finish this part" onSubmitted={onFinished}/>;
    }}</LoadState>
    <button type="button" className="link persona-quiz-cancel" onClick={onCancel}>Cancel</button>
  </section>;
}

/** The five part cards: blurb, ~1.5 min, a tick when done; the suggested next part first. */
function PartCards({ done, onStart }: { done: readonly string[]; onStart(id: PartId): void }) {
  const blurbs = useLoad(() => Promise.all(PARTS.map((p) => api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: p.id } } })))
    .then((rs) => ({ data: Object.fromEntries(rs.map((r, i) => [PARTS[i].id, (r.data as unknown as PartInstrument | undefined)?.part?.blurb ?? ""])) })));
  const suggested = nextPart(done);
  const ordered = suggested ? [PARTS.find((p) => p.id === suggested)!, ...PARTS.filter((p) => p.id !== suggested)] : [...PARTS];
  return <ul className="persona-parts">{ordered.map((p) => {
    const isDone = done.includes(p.id), isNext = p.id === suggested;
    return <li key={p.id} className={`persona-part${isDone ? " done" : ""}${isNext ? " next" : ""}`}>
      <div className="persona-part-text"><strong>{isDone && <span className="persona-part-tick" aria-label="Done">✓ </span>}{p.name}</strong>
        <span>{blurbs.data?.[p.id] ?? ""}</span><span className="persona-part-time">~1.5 min{isNext ? " · suggested next" : ""}</span></div>
      <button type="button" className={isNext ? undefined : "ghost"} aria-label={`${isDone ? "Retake" : "Start"} ${p.name}`} onClick={() => onStart(p.id)}>{isDone ? "Retake" : "Start"}</button>
    </li>;
  })}</ul>;
}

export function Persona() {
  const { persona, loading, reload } = usePersona();
  const [part, setPart] = useState<PartId | null>(null);
  const [justDone, setJustDone] = useState<PartId | null>(null);
  const head = <header className="persona-head"><div><h1>Persona</h1><p>How you like to work and rest, in your own words. Private to you.</p></div></header>;
  const done = persona?.progress?.done ?? [];
  if (part) return <div className="persona-page">{head}<PartQuiz partId={part} onCancel={() => setPart(null)}
    onFinished={() => { setJustDone(part); setPart(null); reload(); }}/></div>;
  if (loading && !persona) return <div className="persona-page">{head}<p className="muted">Loading your persona…</p></div>;
  const matrix = persona?.available && persona.source === BANK ? persona.persona_matrix : null;
  const keptOff = persona?.progress?.answers_kept === false
    && <p className="persona-consent-note">To combine your parts, allow keeping questionnaire answers in Settings → Consent.</p>;
  // after a part: "Part n of 5 done", then the next part or later
  if (justDone) {
    const doneNow = done.includes(justDone) ? done : [...done, justDone];
    const n = Math.min(PARTS.length, doneNow.length), next = nextPart(doneNow, justDone);
    return <div className="persona-page">{head}<section className="persona-empty persona-part-done" data-pet-perch aria-live="polite">
      <h2>Part {n} of {PARTS.length} done</h2>
      <p>{next ? "Take the next part now, or come back to it later. Your answers are saved." : matrix ? "All five parts are done. Your persona is ready." : "All five parts are done. Your persona is being put together."}</p>
      {keptOff}
      <div className="persona-part-actions">
        {next && <button type="button" onClick={() => { setJustDone(null); setPart(next); }}>Next part: {PARTS.find((p) => p.id === next)!.name}</button>}
        <button type="button" className={next ? "ghost" : undefined} onClick={() => setJustDone(null)}>{next ? "Later" : "See my persona"}</button>
      </div>
    </section></div>;
  }
  return <div className="persona-page">{head}
    {!matrix
      ? <section className="persona-empty" data-pet-perch><h2>Your persona</h2>
          <p>Five short parts, about a minute and a half each, in any order and on any day. Your persona appears when all five are done. It shapes how Perigee words things for you; it is not a score.</p>
          <p className="persona-progress">{done.length} of {PARTS.length} parts done</p>
          {keptOff}
          <PartCards done={done} onStart={setPart}/></section>
      : <><div className="persona-layout">
          <section className="persona-quadrant-panel" data-pet-perch aria-labelledby="quadrant-title">
            <h2 id="quadrant-title">{matrix.quadrant_name}</h2>
            <p className="muted">Your place on two everyday axes: how settled you tend to feel, and how much you like to steer. No place is better than another.</p>
            <Plane stability={matrix.stability_score} agency={matrix.agency_score} quadrant={matrix.quadrant_name} />
          </section>
          <section className="persona-advice-panel"><AdviceList emptyText="No suggestions right now. They appear when your nights or check-ins point to something worth trying." /><p className="persona-footnote">Suggestions follow your latest night and check-ins. They are not medical advice.</p></section>
        </div>
        <section className="persona-empty persona-retake-parts" aria-labelledby="retake-title"><h2 id="retake-title">Your five parts</h2>
          <p className="muted">Retake any part; your persona updates from your newest answers.</p>{keptOff}
          <PartCards done={done} onStart={setPart}/></section></>}
  </div>;
}
