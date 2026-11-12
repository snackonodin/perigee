import { type FormEvent, useState } from "react";
import { api, errorText } from "../api/client";
import type { Instrument, ResponseOut } from "../api/types";
import { contentFromServer, localSafetyTriggered, SAFETY_FALLBACK } from "../safety/safety";
import { useSafety } from "../safety/SafetyProvider";

/** A questionnaire rendered from its catalog JSON. Safety comes first, always:
 *  1) local safety_trigger check → safety screen before the request is even sent;
 *  2) the server's safety result (also on a 500) → before any score is shown. */
export function CheckinForm({ instrument, onDone }: { instrument: Instrument; onDone?(): void }) {
  const { showSafety } = useSafety();
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<ResponseOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (localSafetyTriggered(instrument, answers)) showSafety(SAFETY_FALLBACK);
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
    } else if (out.ok) setResult(out);
    else {
      const errs = out.errors ?? [];
      setError(`Not saved (${out.error ?? "error"})${errs.length ? `: ${errs.join(", ")}` : ""}.`);
    }
  }

  if (result) {
    return (
      <div className="result" role="status">
        {/* `stored` = a response row was written. Whether the individual answers were kept
            depends on the survey_answers consent, which this result does not report. */}
        <p>{result.stored ? "Saved. Thank you." : "Scored only: nothing was stored (check-ins are off in Settings)."}</p>
        {typeof result.total === "number" && <p className="muted">Total score: {result.total}</p>}
        {onDone && <button type="button" onClick={onDone}>Done</button>}
      </div>
    );
  }

  return (
    <form onSubmit={submit} aria-label={instrument.name}>
      {instrument.timeframe && <p className="muted">{instrument.timeframe}</p>}
      {instrument.items.map((item) => (
        <fieldset key={item.key}>
          <legend>{item.text}</legend>
          {item.options.map((o) => (
            <label key={o.value} className="option">
              <input
                type="radio"
                name={item.key}
                value={o.value}
                required
                checked={answers[item.key] === o.value}
                onChange={() => setAnswers((a) => ({ ...a, [item.key]: o.value }))}
              />
              <span>{o.label}</span>
            </label>
          ))}
        </fieldset>
      ))}
      <button type="submit" disabled={busy}>Submit</button>
      <p className="error" role="alert">{error}</p>
    </form>
  );
}
