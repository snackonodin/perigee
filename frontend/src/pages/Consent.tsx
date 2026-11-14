import { Link } from "react-router";
import { Consents } from "../components/Consents";
import { DeleteAccount, ExportData } from "../components/DataControls";
import { Reveal, TitleReveal } from "../components/motion";
import "./Briefing.css";

/** Consent tab: the same switch rows as Settings, the policy version, and export/delete. */
export function Consent() {
  return <div className="screen-page consent-page">
    <header className="page-heading"><div><TitleReveal text="Consent"/><p>Choose what may be stored about you.</p></div></header>
    <Reveal className="consent-grid">
      <section className="card glass settings-section" aria-labelledby="consent-scopes-title">
        <h2 id="consent-scopes-title">What may be stored</h2>
        <Consents />
      </section>
      <section className="card glass settings-section" aria-labelledby="consent-data-title">
        <h2 id="consent-data-title">Your data</h2>
        <ExportData />
        <hr />
        <DeleteAccount />
        <p className="footnote">Profile and accessibility choices are in <Link to="/settings">Settings</Link>.</p>
      </section>
    </Reveal>
  </div>;
}
