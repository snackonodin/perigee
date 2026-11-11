import { Link } from "react-router";
import type { TodayOut } from "../api/types";
import { fmt, MATURITY_LABEL } from "./format";

const SLOT_LABEL: Record<string, string> = { am: "Morning check-in", pm: "Evening check-in" };

export function TodayCard({ today }: { today: TodayOut }) {
  const n = today.latest_night;
  return (
    <section className="card wide" aria-labelledby="today-title">
      <h2 id="today-title">Last night</h2>
      {n ? (
        <>
          <dl className="kv">
            <dt>Night of</dt>
            <dd>{n.date}</dd>
            <dt>Breathing rate (median)</dt>
            <dd>{fmt(n.rr_med)} breaths/min</dd>
            <dt>Time in bed</dt>
            <dd>{fmt(n.presence_hours)} h</dd>
            <dt>Restless</dt>
            <dd>{fmt(n.restless_frac * 100, 0)} %</dd>
            <dt>Signal quality</dt>
            <dd>{fmt(n.quality * 100, 0)} %</dd>
          </dl>
          {!n.valid && <p className="muted">Not enough good signal: this night is not used for your baselines.</p>}
        </>
      ) : (
        <p className="muted">No night recorded yet.</p>
      )}
      <h3>Check-ins due</h3>
      {!today.checkins_consent ? (
        <p className="muted">Check-ins are off (turn them on in Settings).</p>
      ) : today.pending_checkins.length === 0 ? (
        <p className="muted">All done for today.</p>
      ) : (
        <ul className="plain">
          {today.pending_checkins.map((p) => (
            <li key={p.slot}>
              {SLOT_LABEL[p.slot] ?? p.slot} <Link to={`/psyche?instrument=${encodeURIComponent(p.instrument_id)}`}>Start</Link>
            </li>
          ))}
        </ul>
      )}
      <h3>Baselines</h3>
      {today.baselines.length === 0 ? (
        <p className="muted">Baselines start after your first valid nights.</p>
      ) : (
        <ul className="plain">
          {today.baselines.map((b) => (
            <li key={b.feature}>
              {b.feature}: <span className={`maturity ${b.maturity}`}>{MATURITY_LABEL[b.maturity] ?? b.maturity}</span>{" "}
              <span className="muted">({b.n} nights)</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
