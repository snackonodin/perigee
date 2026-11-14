import { emit } from "../pet";
import { type FormEvent, useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import type { Instrument, ResponseOut } from "../api/types";
import { contentFromServer, localSafetyTriggered, SAFETY_FALLBACK } from "../safety/safety";
import { useSafety } from "../safety/SafetyProvider";
import { friendlyName } from "./instrumentNames";

/** A questionnaire rendered from its catalog JSON. Safety comes first, always:
 *  1) local safety_trigger check → safety screen before the request is even sent;
 *  2) the server's safety result (also on a 500) → before any score is shown. */
export function CheckinForm({ instrument, onDone, onSubmitted, submitLabel = "Send check-in" }: {
  instrument: Instrument;
  onDone?(): void;
  /** Called with a stored, non-crisis result instead of showing the score card (e.g. the personality quiz). */
  onSubmitted?(out: ResponseOut): void;
  submitLabel?: string;
}) {
  useEffect(() => { emit("quiz_start"); }, []);
  const { showSafety } = useSafety();
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<ResponseOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const item = instrument.items[step];

  function next() {
    if (answers[item.key] === undefined) {
      setError("Choose one response to continue.");
      return;
    }
    setError(null);
    setStep((current) => Math.min(current + 1, instrument.items.length - 1));
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
    if (localSafety) showSafety(SAFETY_FALLBACK);
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
    <form onSubmit={submit} aria-label={friendlyName(instrument.id, instrument.name)}>
      {instrument.timeframe && <p className="muted">{instrument.timeframe}</p>}
      <div className="checkin-progress" role="status">Question {step + 1} of {instrument.items.length}
        <div className="progress-track" aria-hidden="true"><span style={{width:`${((step+1)/instrument.items.length)*100}%`}}/></div>
      </div>
      <fieldset className="checkin-question-card" key={item.key}>
        <legend>{item.text}</legend>
        <div className="checkin-question-options">{item.options.map((o) => (
          <label key={o.value} className={answers[item.key] === o.value ? "checkin-question-option selected" : "checkin-question-option"}>
            <input type="radio" name={item.key} value={o.value} checked={answers[item.key] === o.value}
              onChange={() => {
                setAnswers((a) => ({ ...a, [item.key]: o.value }));
                setError(null);
                if (item.safety_trigger && o.value >= item.safety_trigger.min_value) showSafety(SAFETY_FALLBACK);
              }}/>
            <span>{o.label}</span>{answers[item.key]===o.value&&<svg className="checkin-selected-mark" aria-hidden="true" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>}
          </label>
        ))}</div>
      </fieldset>
      <div className="checkin-actions">
        {step>0&&<button type="button" className="ghost" onClick={previous}>Previous</button>}
        {step<instrument.items.length-1
          ? <button type="button" onClick={next}>Next <span aria-hidden="true">→</span></button>
          : <button type="submit" disabled={busy}>{submitLabel}</button>}
      </div>
      <p className="error" role="alert">{error}</p>
    </form>
  );
}
