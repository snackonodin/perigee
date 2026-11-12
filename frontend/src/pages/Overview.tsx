import { Link } from "react-router";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { FlagWhy } from "../components/FlagWhy";
import { fmt } from "../components/format";
import { GuidanceCard } from "../components/GuidanceCard";
import { LoadState } from "../components/LoadState";

type EngineToday = TodayOut & {
  context_engine?: {
    safety_status?: { crisis_override_triggered?: boolean };
    scores_and_metrics?: { phys_level?: number; mental_level?: number };
    fatigue_and_health_ratings?: {
      mental_fatigue_score?: number;
      physiological_fatigue_score?: number;
      overall_health_resilience_index?: number;
    };
    dashboard_visualization_data?: {
      dual_axis_timeline_point?: { respiration_bpm?: number; respiration_baseline_band?: number[] };
    };
    user_facing_advisory?: { headline?: string; personality_tailored_message?: string };
    flight_surgeon_briefing_snippet?: string;
  } | null;
};

function levelText(level?: number): { icon: string; text: string; className: string } {
  if (level === undefined || level === null) return { icon: "◌", text: "Building your picture", className: "quiet" };
  if (level >= 2) return { icon: "◌", text: "Alert", className: "high" };
  if (level === 1) return { icon: "◌", text: "Watch", className: "watch" };
  return { icon: "◌", text: "Normal", className: "usual" };
}

function Ring({ level, label }: { level?: number; label: string }) {
  const radius = 67;
  const circumference = 2 * Math.PI * radius;
  const valid = typeof level === "number" && Number.isFinite(level);
  const score = valid ? Math.max(1, Math.min(3, Math.max(0, level!))) / 3 : 0;
  const status = levelText(level);
  return (
    <figure className="today-ring" aria-label={valid ? `${label}: ${status.text}` : `${label}: no reading yet`}>
      <svg viewBox="0 0 160 160" role="img" aria-label={valid ? `${status.text}, level ${Math.round(level!)}` : "No reading yet"}>
        <circle className="ring-track" cx="80" cy="80" r={radius} />
        <circle className={`ring-value ${status.className}`} cx="80" cy="80" r={radius} strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score)} />
        <text className="hero-value" x="80" y="78" textAnchor="middle">{valid ? Math.round(level!) : "—"}</text>
        <text className="hero-label" x="80" y="99" textAnchor="middle">{valid ? status.text : "no reading"}</text>
      </svg>
      <figcaption className="sr-only">{valid ? `${label} ${Math.round(score)} out of 100` : `${label} is not available yet`}</figcaption>
    </figure>
  );
}

function SystemTile({ title, value, detail, level }: { title: string; value: string; detail: string; level?: number }) {
  const status = levelText(level);
  return (
    <article className="system-tile">
      <h3>{title}</h3>
      <strong>{value}</strong>
      <p>{detail}</p>
      <span className={`level ${status.className}`}><span aria-hidden="true">{status.icon}</span>{status.text}</span>
    </article>
  );
}

function BaselineBand({ value, band }: { value?: number; band?: number[] }) {
  if (typeof value !== "number" || !band || band.length < 2 || !band.every(Number.isFinite)) {
    return <p className="muted">Your personal range will appear as your baseline takes shape.</p>;
  }
  const low = Math.min(band[0], band[1]);
  const high = Math.max(band[0], band[1]);
  const span = Math.max(high - low, Math.abs(high) * 0.08, 1);
  const left = Math.max(0, Math.min(100, ((value - (low - span)) / (3 * span)) * 100));
  return (
    <div aria-label={`Your rate ${fmt(value)} breaths per minute; personal range ${fmt(low)} to ${fmt(high)}`}>
      <div className="baseline-track" aria-hidden="true"><span className="baseline-marker" style={{ left: `${left}%` }} /></div>
      <div className="baseline-caption"><span>{fmt(low)}</span><span>Your 28-night range</span><span>{fmt(high)}</span></div>
    </div>
  );
}

export function Overview() {
  const load = useLoad(() => api.GET("/api/v1/today"));
  return (
    <LoadState state={load} label="today's personal snapshot">
      {(raw) => {
        const today = raw as EngineToday;
        const engine = today.context_engine;
        const night = today.latest_night;
        const rr = engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm ?? night?.rr_med ?? undefined;
        const rrBand = engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_baseline_band;
        const baseline = today.baselines.find((b) => b.feature === "rr_med");
        const band = rrBand ?? (baseline?.median != null && baseline.mad != null
          ? [baseline.median - baseline.mad, baseline.median + baseline.mad]
          : undefined);
        const physiology = engine?.scores_and_metrics?.phys_level ?? today.flags[0]?.phys_level;
        const mental = engine?.scores_and_metrics?.mental_level ?? today.flags[0]?.mental_level;
        const health = engine?.fatigue_and_health_ratings;
        const resilience = health?.overall_health_resilience_index;
        const advisory = engine?.user_facing_advisory;
        const status = levelText(physiology);

        return (
          <>
            <header className="page-heading">
              <div><p className="eyebrow">Crew quarters · personal log</p><h1>Today</h1>
                <p>Your recent signals, seen against your own 28-night baseline.</p></div>
              {night && <span className={`status-chip ${status.className}`}><span aria-hidden="true">{status.icon}</span>{status.text}</span>}
            </header>

            <div className="grid today-grid">
              <section className="card today-hero" aria-labelledby="ring-heading">
                <Ring level={physiology} label="Today's level" />
                <div className="hero-copy">
                  <p className="eyebrow">{night ? `Night of ${night.date}` : "First nights"}</p>
                  <h2 id="ring-heading">{resilience === undefined ? "Your picture is taking shape" : "Your systems, in context"}</h2>
                  <p>{physiology === undefined
                    ? "A personal baseline grows from valid nights. No one else is used as a comparison."
                    : "Today's level, read against your own recent pattern."}</p>
                  {today.sync_status?.state === "api_mock"
                    ? <p className="api-mock-note" role="status">API unavailable · empty preview only; no scores or readings are being shown.</p>
                    : today.sync_status?.state === "offline" && <p className="offline-note"><span aria-hidden="true">◉</span> Saved on this station</p>}
                </div>
              </section>

              <section className="tile-grid" aria-label="Personal system signals">
                <SystemTile title="Resilience" value={resilience == null ? "—" : `${Math.round(resilience)} / 100`}
                  detail="A view of your recent signals" />
                <SystemTile title="Respiration" value={rr == null ? "—" : `${fmt(rr)} /min`}
                  detail={night ? `${fmt(night.presence_hours)} h sensed overnight` : "No overnight signal yet"} level={physiology} />
                <SystemTile title="Mind" value={health?.mental_fatigue_score == null ? "—" : `${Math.round(health.mental_fatigue_score)} / 100`}
                  detail={health?.mental_fatigue_score == null ? "Check-ins help add context" : "From your recent check-ins and inputs"} level={mental} />
                <SystemTile title="Rest" value={night ? `${fmt(night.presence_hours, 1)} h` : "—"}
                  detail={night ? `${fmt(night.restless_frac * 100, 0)}% movement flagged` : "No night recorded yet"} />
                <SystemTile title="Personal baseline" value={baseline ? `${baseline.n} nights` : "Starting"}
                  detail={baseline?.maturity === "mature" ? "28-night window" : "Builds with valid nights"} />
              </section>

              <section className="card baseline-card" aria-labelledby="baseline-title">
                <div className="row"><div><p className="eyebrow">Your pattern</p><h2 id="baseline-title">Breathing through the night</h2></div>
                  <Link to="/sleep">Open Sleep</Link></div>
                <p className="metric-lead">{rr == null ? "Waiting for a valid night" : `${fmt(rr)} breaths per minute`}</p>
                <BaselineBand value={rr ?? undefined} band={band} />
                <p className="footnote">The shaded band shows your own median ± MAD when available. Changes are described as unusual for you, not compared with other crew.</p>
              </section>

              <section className="card advisory-card" aria-labelledby="advisory-title">
                <div className="advisory-mark" aria-hidden="true">✧</div>
                <div><p className="eyebrow">A quiet note</p>
                  <h2 id="advisory-title">{advisory?.headline ?? "Keep noticing your own rhythm"}</h2>
                  <p>{advisory?.personality_tailored_message ?? "A single night can move around. Your personal range becomes clearer as more valid nights come in."}</p>
                  {today.flags.slice(0, 1).map((flag) => <div className="today-flag" key={flag.id}>
                    <p className="muted">{flag.date} · a signal looks different from your usual pattern</p>
                    <FlagWhy components={flag.components} />
                    {flag.guidance.slice(0, 1).map((card) => <GuidanceCard key={card.card_key} card={card} />)}
                  </div>)}
                </div>
              </section>

              <section className="card checkin-prompt" aria-labelledby="checkin-title">
                <span className="prompt-icon" aria-hidden="true">♡</span>
                <div><p className="eyebrow">Daily check-in</p><h2 id="checkin-title">Add a little context</h2>
                  <p>{today.pending_checkins.length ? "A short check-in is ready when you are." : "Your check-ins can help make sense of patterns over time."}</p></div>
                {today.pending_checkins[0] && <Link className="action-link" to={`/checkin?instrument=${encodeURIComponent(today.pending_checkins[0].instrument_id)}`}>Begin <span aria-hidden="true">→</span></Link>}
              </section>
            </div>
          </>
        );
      }}
    </LoadState>
  );
}
