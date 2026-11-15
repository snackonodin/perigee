import { useState } from "react";
import "./Persona.css";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { Instrument, InstrumentItem } from "../api/types";
import { CheckinForm } from "../components/CheckinForm";
import { AdviceList } from "../persona/AdviceList";
import { Radar } from "../persona/Radar";
import { usePersona } from "../persona/PersonaProvider";
import { useAuth } from "../auth/AuthProvider";
import { ITEMS_PER_PAGE, nextPart, PARTS, type PartId, stableShuffle } from "../persona/parts";

const BANK = "psyche60";
// Axis order matches GET /persona type_mix; the axes sit where the old plane had each quadrant:
// Autonomous Pioneer top-right, Steady Anchor bottom-right, Internal Deliberator bottom-left,
// Dynamic Explorer top-left (first axis at -45 degrees, then clockwise).
const TYPE_ORDER = ["Autonomous Pioneer", "Steady Anchor", "Internal Deliberator", "Dynamic Explorer"] as const;
type TypeShare = { type: string; share: number };

/** The four persona types as one radar: shape from each type's share (scaled to the largest, so the
 *  leading type reaches the outer ring), the person's own type highlighted. No numbers. */
function TypeRadar({ mix, quadrant, userId }: { mix: readonly TypeShare[]; quadrant: string; userId: string }) {
  const share = new Map(mix.map((m) => [m.type, Number.isFinite(m.share) ? Math.max(0, m.share) : 0]));
  const top = Math.max(...TYPE_ORDER.map((t) => share.get(t) ?? 0));
  if (!(top > 0)) return null;
  const axes = TYPE_ORDER.map((t) => ({ key: t, label: t, level: (share.get(t) ?? 0) / top, current: t === quadrant }));
  const ranked = [...TYPE_ORDER].sort((x, y) => (share.get(y) ?? 0) - (share.get(x) ?? 0));
  const label = `Your persona leans most toward ${ranked[0]}, then ${ranked.slice(1, -1).join(", then ")}, and least toward ${ranked[ranked.length - 1]}.`;
  return <Radar axes={axes} label={label} start={-Math.PI / 4} growKey={`persona.types.${userId}`} />;
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
  const { me } = useAuth();
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
            <p className="muted">How your answers lean across the four persona types. Your own type is highlighted.</p>
            <TypeRadar mix={persona?.type_mix ?? []} quadrant={matrix.quadrant_name} userId={me?.id ?? "anon"} />
          </section>
          <section className="persona-advice-panel"><AdviceList emptyText="No suggestions right now. They appear when your nights or check-ins point to something worth trying." /><p className="persona-footnote">Suggestions follow your latest night and check-ins. They are not medical advice.</p></section>
        </div>
        <section className="persona-empty persona-retake-parts" aria-labelledby="retake-title"><h2 id="retake-title">Your five parts</h2>
          <p className="muted">Retake any part; your persona updates from your newest answers.</p>{keptOff}
          <PartCards done={done} onStart={setPart}/></section></>}
  </div>;
}
