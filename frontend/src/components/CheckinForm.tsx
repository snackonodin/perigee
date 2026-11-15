import { emit } from "../pet";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, errorText } from "../api/client";
import type { Instrument, InstrumentItem, ResponseOut } from "../api/types";
import { contentFromServer, fallbackFor, localSafetyTriggered } from "../safety/safety";
import { useSafety } from "../safety/SafetyProvider";
import { announceCheckinSaved } from "../persona/PersonaProvider";
import { friendlyName } from "./instrumentNames";

/** A questionnaire rendered from its catalog JSON. Safety comes first, always:
 *  1) local safety_trigger check → safety screen before the request is even sent;
 *  2) the server's safety result (also on a 500) → before any score is shown. */
export function CheckinForm({ instrument, onDone, onSubmitted, submitLabel = "Send check-in", groupBy, sectionOf, control }: {
  instrument: Instrument;
  /** Show several questions per page: items with the same group key share a page (e.g. a module). */
  groupBy?(item: InstrumentItem): string;
  /** optional subheading for items inside a page (e.g. "Cabin air"); shown when it changes */
  sectionOf?(item: InstrumentItem): string | undefined;
  /** how an item is answered: option cards (default), compact chips, or a slider */
  control?(item: InstrumentItem): "cards" | "chips" | "slider";
  onDone?(): void;
  /** Called with a stored, non-crisis result instead of showing the score card (e.g. the personality quiz). */
  onSubmitted?(out: ResponseOut): void;
  submitLabel?: string;
}) {
  useEffect(() => { emit("quiz_start"); }, []);
  const { showSafety } = useSafety();
  // sliders always show a value, so they start answered at their first option ("None")
  const [answers, setAnswers] = useState<Record<string, number>>(() => Object.fromEntries(
    instrument.items.filter((it) => control?.(it) === "slider" && it.options.length).map((it) => [it.key, it.options[0].value])));
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<ResponseOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);
  // pages: one item each, or one group (module) each
  const pages: InstrumentItem[][] = [];
  for (const it of instrument.items) {
    const last = pages[pages.length - 1];
    if (groupBy && last && groupBy(last[0]) === groupBy(it)) last.push(it); else pages.push([it]);
  }
  const page = pages[step];

  function next() {
    if (page.some((q) => answers[q.key] === undefined)) {
      setError(page.length > 1 ? "Choose one response for each statement to continue." : "Choose one response to continue.");
      return;
    }
    setError(null);
    setStep((current) => Math.min(current + 1, pages.length - 1));
    if (page.length > 1) formRef.current?.scrollIntoView?.({ block: "start" });
  }

  function previous() {
    setError(null);
    setStep((current) => Math.max(0, current - 1));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (instrument.items.some((question) => answers[question.key] === undefined)) {
      setError("Please answer each card before sending your check-in.");
      return;
    }
    const localSafety = localSafetyTriggered(instrument, answers);
    // the triggering item's own reason (a body red flag is a medical reason, not the safety item)
    if (localSafety) showSafety(fallbackFor(instrument.items.find((it) => it.safety_trigger && (answers[it.key] ?? -1) >= it.safety_trigger.min_value)?.safety_trigger?.reason));
    setBusy(true);
    setError(null);
    let out: ResponseOut | undefined;
    try {
      const { data, error: err, response } = await api.POST("/api/v1/responses", {
        body: { instrument_id: instrument.id, instrument_version: instrument.version, answers },
      });
      // a storage failure (500) still carries the safety result: honour it
      out = data ?? (err && typeof err === "object" && ("safety" in err || "crisis" in err) ? (err as ResponseOut) : undefined);
      if (!out) setError(errorText(err, response.status));
    } catch {
      setError(errorText(undefined));
    }
    setBusy(false);
    if (!out) return;
    // The shared API contract requires a top-level crisis boolean. Missing is treated as
    // crisis, and safety.show is an independent fail-safe. Never expose routine scores first.
    const crisis = out.crisis !== false || out.safety?.show !== false;
    if (crisis) {
      showSafety(contentFromServer(out.safety ?? {}));
      setResult(null);
    } else if (out.ok) {
      if (out.stored) announceCheckinSaved();
      // companion: completion only, never on a safety response, never with any data
      if (!localSafety && out.safety_screen_required === false) emit("quiz_complete");
      if (onSubmitted) onSubmitted(out);
      else setResult(out);
    }
    else {
      const errs = out.errors ?? [];
      setError(`Not saved (${out.error ?? "error"})${errs.length ? `: ${errs.join(", ")}` : ""}.`);
    }
  }

  if (result) {
    return (
      <div className="checkin-result" role="status">
        {/* `stored` = a response row was written. Whether the individual answers were kept
            depends on the survey_answers consent, which this result does not report. */}
        <p>{result.stored ? "Saved. Thank you." : "Scored only: nothing was stored (check-ins are off in Settings)."}</p>
        {onDone && <button type="button" onClick={onDone}>Done</button>}
      </div>
    );
  }

  return (
    <form ref={formRef} data-pet-sit onSubmit={submit} aria-label={friendlyName(instrument.id, instrument.name)}>
      {instrument.timeframe && <p className="muted">{instrument.timeframe}</p>}
      <div className="checkin-progress" role="status">{pages.length === instrument.items.length ? `Question ${step + 1} of ${pages.length}` : `Page ${step + 1} of ${pages.length}`}
        <div className="progress-track" aria-hidden="true"><span style={{width:`${((step+1)/pages.length)*100}%`}}/></div>
      </div>
      {page.map((item, i) => {
        const kind = control?.(item) ?? "cards";
        const section = sectionOf?.(item);
        const heading = section && (i === 0 || sectionOf?.(page[i - 1]) !== section) ? <h3 className="checkin-section">{section}</h3> : null;
        const choose = (value: number) => {
          setAnswers((a) => ({ ...a, [item.key]: value }));
          setError(null);
          if (item.safety_trigger && value >= item.safety_trigger.min_value) showSafety(fallbackFor(item.safety_trigger.reason));
        };
        if (kind === "slider") {
          const values = item.options.map((o) => o.value), v = answers[item.key] ?? values[0];
          const label = item.options.find((o) => o.value === v)?.label ?? "";
          return <div key={item.key}>{heading}<label className="checkin-slider">
            <span className="checkin-slider-text">{item.text}</span><output>{label}</output>
            <input type="range" min={Math.min(...values)} max={Math.max(...values)} step={1} value={v} aria-label={item.text} aria-valuetext={label}
              onChange={(e) => { const n = Number(e.target.value); const o = item.options.reduce((b, x) => (Math.abs(x.value - n) < Math.abs(b.value - n) ? x : b)); choose(o.value); }} />
          </label></div>;
        }
        return <div key={item.key}>{heading}<fieldset className={kind === "chips" ? "checkin-chips-item" : "checkin-question-card"}>
        <legend>{item.text}</legend>
        <div className={kind === "chips" ? "checkin-chips" : "checkin-question-options"}>{item.options.map((o) => (
          <label key={o.value} className={answers[item.key] === o.value ? `${kind === "chips" ? "checkin-chip" : "checkin-question-option"} selected` : kind === "chips" ? "checkin-chip" : "checkin-question-option"}>
            <input type="radio" name={item.key} value={o.value} checked={answers[item.key] === o.value}
              onChange={() => choose(o.value)}/>
            <span>{o.label}</span>{kind === "cards" && answers[item.key]===o.value&&<svg className="checkin-selected-mark" aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>}
          </label>
        ))}</div>
      </fieldset></div>;
      })}
      <div className="checkin-actions">
        {step>0&&<button type="button" className="ghost" onClick={previous}>Previous</button>}
        {step<pages.length-1
          ? <button type="button" onClick={next}>Next <span aria-hidden="true">→</span></button>
          : <button type="submit" disabled={busy}>{submitLabel}</button>}
      </div>
      <p className="error" role="alert">{error}</p>
    </form>
  );
}
