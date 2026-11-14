import { api } from "../api/client";
import type { BaselineOut, NightOut, TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { plainHeadline, plainMessage } from "../components/advisory";
import { fmt } from "../components/format";
import { friendlyName } from "../components/instrumentNames";
import { LoadState } from "../components/LoadState";
import { StatusChip, type Status } from "../components/StatusChip";
import "./Briefing.css";

type EngineToday = TodayOut & { context_engine?: {
  scores_and_metrics?: { phys_level?: number; mental_level?: number };
  user_facing_advisory?: { headline?: string; personality_tailored_message?: string };
} | null };
type Checkin = { date: string; instrument_id: string; slot: string };

const DAY = 86_400_000;
const WEEK = 7;
const iso = (t: number) => new Date(t).toISOString().slice(0, 10);
function levelStatus(level?: number): Status { return level == null ? "none" : level >= 2 ? "alert" : level === 1 ? "watch" : "normal"; }

/** Read-only weekly summary built from /today, /nights and /checkins (no new API). Prints cleanly. */
export function Briefing() {
  const now = Date.now(), from = iso(now - (WEEK - 1) * DAY), to = iso(now);
  const today = useLoad(() => api.GET("/api/v1/today"));
  const nights = useLoad(() => api.GET("/api/v1/nights", { params: { query: { from, to } } }), [from, to]);
  const checkins = useLoad(() => api.GET("/api/v1/checkins", { params: { query: { from, to } } }), [from, to]);
  return <div className="screen-page briefing-page">
    <header className="page-heading"><div><h1>Briefing</h1><p className="section-meta telemetry">{from} → {to}</p><p>A read-only summary of your last seven days, compared with your own usual.</p></div>
      <button type="button" className="ghost briefing-print" onClick={() => window.print()}>Print</button></header>
    <LoadState state={today} label="your weekly briefing">{raw => {
      const t = raw as EngineToday, engine = t.context_engine;
      const baseline = t.baselines.find(b => b.feature === "rr_med");
      const body = levelStatus(engine?.scores_and_metrics?.phys_level ?? t.flags[0]?.phys_level);
      const mind = levelStatus(engine?.scores_and_metrics?.mental_level ?? t.flags[0]?.mental_level);
      const advisory = engine?.user_facing_advisory;
      return <div className="briefing-grid">
        <section className="card briefing-status" aria-labelledby="brief-status-title">
<h2 id="brief-status-title">Where things stand</h2>
          <dl className="briefing-chips">
            <div><dt>Body signals</dt><dd><StatusChip state={body}/></dd></div>
            <div><dt>Mind and check-ins</dt><dd><StatusChip state={mind}/></dd></div>
          </dl>
          {advisory?.headline && <p className="briefing-note"><strong>{plainHeadline(advisory.headline)}</strong>{advisory.personality_tailored_message && <> {plainMessage(advisory.personality_tailored_message)}</>}</p>}
        </section>
        <LatestNight night={t.latest_night ?? undefined}/>
        <section className="card briefing-wide" aria-labelledby="brief-rr-title">
          <h2 id="brief-rr-title">Night breathing vs your usual range</h2><p className="section-meta">Last 7 nights</p>
          <LoadState state={nights} label="the last seven nights">{data => <WeekBreathing nights={data} baseline={baseline} from={from}/>}</LoadState>
        </section>
        <section className="card briefing-wide" aria-labelledby="brief-ci-title">
          <h2 id="brief-ci-title">Check-ins completed</h2><p className="section-meta">This week</p>
          <LoadState state={checkins} label="this week's check-ins">{data => <WeekCheckins items={data as Checkin[]}/>}</LoadState>
        </section>
        <p className="footnote briefing-wide">Screening and awareness only. Differences are described as unusual for you, not as a medical finding.</p>
      </div>;
    }}</LoadState>
  </div>;
}

function LatestNight({ night }: { night?: NightOut }) {
  return <section className="card" aria-labelledby="brief-night-title">
    <h2 id="brief-night-title">Last recorded night</h2>{night && <p className="section-meta telemetry">{night.date}</p>}
    {night?.valid ? <dl className="briefing-stats">
      <div><dt>Breathing</dt><dd>{fmt(night.rr_med)}<small>br/min</small></dd></div>
      <div><dt>Time present</dt><dd>{fmt(night.presence_hours, 1)}<small>h</small></dd></div>
    </dl> : <p className="muted">No valid night yet. It appears after a full night near the sensor.</p>}
  </section>;
}

function WeekBreathing({ nights, baseline, from }: { nights: NightOut[]; baseline?: BaselineOut; from: string }) {
  const band = baseline?.median != null && baseline.mad != null ? [baseline.median - baseline.mad, baseline.median + baseline.mad] as const : null;
  const days = Array.from({ length: WEEK }, (_, i) => iso(Date.parse(`${from}T00:00:00Z`) + i * DAY));
  const rows = days.map(d => ({ d, n: nights.find(n => n.date === d && n.valid && n.rr_med != null) }));
  const recorded = rows.filter(r => r.n).length;
  const inside = band ? rows.filter(r => r.n && r.n.rr_med! >= band[0] && r.n.rr_med! <= band[1]).length : 0;
  return <>
    <p className="briefing-summary">{recorded} of {WEEK} nights recorded{band ? ` · ${inside} within your usual range (${fmt(band[0])}–${fmt(band[1])} br/min)` : " · your usual range is still building"}</p>
    <table className="briefing-table"><thead><tr><th scope="col">Night</th><th scope="col">Breathing</th><th scope="col">Vs your usual</th></tr></thead>
      <tbody>{rows.map(({ d, n }) => {
        const v = n?.rr_med;
        const where = v == null ? "No reading" : !band ? "Range building" : v < band[0] ? "Below your usual" : v > band[1] ? "Above your usual" : "Within your usual";
        return <tr key={d}><td>{d}</td><td>{v == null ? "—" : `${fmt(v)} br/min`}</td><td>{where}</td></tr>;
      })}</tbody></table>
  </>;
}

function WeekCheckins({ items }: { items: Checkin[] }) {
  if (!items.length) return <p className="muted">No check-ins this week. They are optional and add context to your nights.</p>;
  const byInstrument = new Map<string, number>();
  for (const c of items) byInstrument.set(c.instrument_id, (byInstrument.get(c.instrument_id) ?? 0) + 1);
  const days = new Set(items.map(c => c.date)).size;
  return <>
    <p className="briefing-summary">{items.length} check-in{items.length === 1 ? "" : "s"} on {days} day{days === 1 ? "" : "s"}</p>
    <ul className="briefing-list">{[...byInstrument].map(([id, n]) => <li key={id}><span>{friendlyName(id)}</span><span className="telemetry">× {n}</span></li>)}</ul>
  </>;
}
