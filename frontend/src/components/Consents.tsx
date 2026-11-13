import { useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "./LoadState";
import { CONSENT_SCOPES, type ConsentOut, type ConsentScope } from "../api/types";

/** Version label of the consent wording below (same label the demo page used). */
export const CONSENT_POLICY_VERSION = "demo-1";

export const CONSENT_TEXT: Record<ConsentScope, string> = {
  checkins: "Store my daily check-in answers so they can be compared with my sleep.",
  survey_answers: "Keep my individual questionnaire answers (otherwise only scores are kept).",
  raw_csi: "Keep the raw Wi-Fi sensing recordings of my nights (otherwise only derived features).",
  share_summaries: "Allow summaries of my results to be shared with my support team.",
};

/** Human labels for the consent scopes (B6). The scope key stays the API contract. */
export const CONSENT_LABEL: Record<ConsentScope, string> = {
  checkins: "Daily check-ins",
  survey_answers: "Questionnaire answers",
  raw_csi: "Raw sensor recordings",
  share_summaries: "Share summaries with my support team",
};

export function Consents() {
  const loaded = useLoad(() => api.GET("/api/v1/me/consents"));
  const [state, setState] = useState<Record<string, ConsentOut> | null>(null);
  const [errors, setErrors] = useState<Partial<Record<ConsentScope, string>>>({});
  const [saved, setSaved] = useState<Partial<Record<ConsentScope, boolean>>>({});
  const [busy, setBusy] = useState<ConsentScope | null>(null);

  useEffect(() => {
    if (loaded.data) setState(loaded.data);
  }, [loaded.data]);

  async function toggle(scope: ConsentScope, granted: boolean) {
    setBusy(scope);
    setErrors((current) => ({ ...current, [scope]: undefined }));
    setSaved((current) => ({ ...current, [scope]: false }));
    const { data, error: e, response } = await api.PUT("/api/v1/me/consents", {
      body: { scopes: { [scope]: granted }, policy_version: CONSENT_POLICY_VERSION },
    });
    setBusy(null);
    if (data) {
      setState(data);
      setSaved((current) => ({ ...current, [scope]: true }));
    } else setErrors((current) => ({ ...current, [scope]: errorText(e, response.status) }));
  }

  if (!state) return <LoadState state={loaded} label="your consents">{() => <div className="settings-skeleton" aria-label="Loading consent settings"><span /><span /><span /><span /></div>}</LoadState>;
  return (
    <fieldset className="consents settings-consents">
      <legend>What may be stored</legend>
      {CONSENT_SCOPES.map((scope) => (
        <label key={scope} className="option settings-consent-row consent-switch-row">
          <span className="settings-consent-copy"><span className="consent-label">{CONSENT_LABEL[scope]}</span><span className="muted">{CONSENT_TEXT[scope]}</span><span className="settings-saved" role="status">{saved[scope] ? "Saved" : ""}</span><span className="error" role="alert">{errors[scope]}</span></span>
          <input
            type="checkbox"
            role="switch"
            aria-label={CONSENT_LABEL[scope]}
            checked={state[scope]?.granted ?? false}
            disabled={busy !== null}
            onChange={(e) => toggle(scope, e.target.checked)}
          />
        </label>
      ))}
      <p className="muted">Consent wording version {CONSENT_POLICY_VERSION}. You can change these at any time.</p>
    </fieldset>
  );
}
