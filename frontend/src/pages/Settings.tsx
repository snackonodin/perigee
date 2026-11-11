import { useAuth } from "../auth/AuthProvider";
import { Consents } from "../components/Consents";
import { DeleteAccount, ExportData } from "../components/DataControls";

export function Settings() {
  const { me, logout } = useAuth();
  return (
    <div className="grid">
      <section className="card" aria-labelledby="acct-title">
        <h2 id="acct-title">Account</h2>
        <dl className="kv">
          <dt>Email</dt>
          <dd>{me?.email}</dd>
          <dt>Time zone</dt>
          <dd>{me?.timezone ?? "UTC"}</dd>
        </dl>
        <button type="button" className="ghost" onClick={() => void logout()}>Log out</button>
      </section>
      <section className="card" aria-labelledby="consent-title">
        <h2 id="consent-title">Consent</h2>
        <Consents />
      </section>
      <section className="card wide" aria-labelledby="data-title">
        <h2 id="data-title">Your data</h2>
        <ExportData />
        <hr />
        <DeleteAccount />
      </section>
    </div>
  );
}
