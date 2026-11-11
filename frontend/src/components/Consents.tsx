import { useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import { CONSENT_SCOPES, type ConsentOut, type ConsentScope } from "../api/types";

/** Version label of the consent wording below (same label the demo page used). */
export const CONSENT_POLICY_VERSION = "demo-1";

export const CONSENT_TEXT: Record<ConsentScope, string> = {
  checkins: "Store my daily check-in answers so they can be compared with my sleep.",
  survey_answers: "Keep my individual questionnaire answers (otherwise only scores are kept).",
  raw_csi: "Keep the raw Wi-Fi sensing recordings of my nights (otherwise only derived features).",
  share_summaries: "Allow summaries of my results to be shared with my support team.",
};

export function Consents() {
  const [state, setState] = useState<Record<string, ConsentOut> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<ConsentScope | null>(null);

  useEffect(() => {
    api.GET("/api/v1/me/consents").then(({ data, error: e, response }) =>
      data ? setState(data) : setError(errorText(e, response.status)),
    );
  }, []);

  async function toggle(scope: ConsentScope, granted: boolean) {
    setBusy(scope);
    setError(null);
    const { data, error: e, response } = await api.PUT("/api/v1/me/consents", {
      body: { scopes: { [scope]: granted }, policy_version: CONSENT_POLICY_VERSION },
    });
    setBusy(null);
    if (data) setState(data);
    else setError(errorText(e, response.status));
  }

  if (!state) return <p className={error ? "error" : "muted"}>{error ?? "Loading…"}</p>;
  return (
    <fieldset className="consents">
      <legend>What may be stored</legend>
      {CONSENT_SCOPES.map((scope) => (
        <label key={scope} className="option">
          <input
            type="checkbox"
            checked={state[scope]?.granted ?? false}
            disabled={busy !== null}
            onChange={(e) => toggle(scope, e.target.checked)}
          />
          <span>{CONSENT_TEXT[scope]}</span>
        </label>
      ))}
      <p className="muted">Consent wording version {CONSENT_POLICY_VERSION}. You can change these at any time.</p>
      <p className="error" role="alert">{error}</p>
    </fieldset>
  );
}
