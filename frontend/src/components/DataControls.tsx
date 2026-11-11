import { useState } from "react";
import { api, errorText } from "../api/client";
import { useAuth } from "../auth/AuthProvider";

export const DELETE_PHRASE = "delete my account";

export function ExportData() {
  const [msg, setMsg] = useState<string | null>(null);
  async function run() {
    setMsg(null);
    const { data, error, response } = await api.POST("/api/v1/me/export");
    if (!data) return setMsg(errorText(error, response.status));
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "my-astro-health-data.json" });
    a.click();
    URL.revokeObjectURL(url);
    setMsg("Export ready: my-astro-health-data.json");
  }
  return (
    <div>
      <p className="muted">Download everything stored about you, as JSON.</p>
      <button type="button" className="ghost" onClick={run}>Export my data</button>
      <p role="status">{msg}</p>
    </div>
  );
}

/** Two-step delete: open the confirmation, type the phrase, then confirm. */
export function DeleteAccount() {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    setError(null);
    const { error: e, response } = await api.DELETE("/api/v1/me");
    setBusy(false);
    if (response.status === 204) await logout();
    else setError(errorText(e, response.status));
  }

  if (!open) {
    return (
      <div>
        <p className="muted">Permanently delete your account, all your data and your recordings.</p>
        <button type="button" className="danger" onClick={() => setOpen(true)}>Delete my account…</button>
      </div>
    );
  }
  return (
    <div className="confirm" role="group" aria-labelledby="del-title">
      <h3 id="del-title">This cannot be undone</h3>
      <p>
        Everything stored about you (nights, check-ins, questionnaires, recordings) is deleted for good. Export
        first if you want a copy. Type <strong>{DELETE_PHRASE}</strong> to confirm.
      </p>
      <label>
        Confirmation
        <input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </label>
      <div className="row">
        <button type="button" className="danger" disabled={typed.trim().toLowerCase() !== DELETE_PHRASE || busy} onClick={confirm}>
          Permanently delete
        </button>
        <button type="button" className="ghost" onClick={() => { setOpen(false); setTyped(""); }}>Cancel</button>
      </div>
      <p className="error" role="alert">{error}</p>
    </div>
  );
}
