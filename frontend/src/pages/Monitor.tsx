import { useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import "./Monitor.css";

type Mode = "sleep_analysis" | "heart_rate" | "breathing_rate";
type SessionState = "connecting" | "link_check" | "calibrating" | "running" | "finalizing" | "complete" | "link_error" | "stopped";
interface MonitorSession {
  id: string;
  mode: Mode;
  state: SessionState;
  remaining_s?: number | null;
  error?: string | null;
  summary?: Record<string, unknown> | null;
}

const ACTIVE_STATES: SessionState[] = ["connecting", "link_check", "calibrating", "running", "finalizing"];
const MODE_LABELS: Record<Mode, string> = {
  sleep_analysis: "Sleep analysis",
  heart_rate: "Measure heart rate",
  breathing_rate: "Measure breathing rate",
};

export function Monitor() {
  const [session, setSession] = useState<MonitorSession | null>(null);
  const [starting, setStarting] = useState(false);
  const [showRates, setShowRates] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = !!session && ACTIVE_STATES.includes(session.state);

  useEffect(() => {
    if (!session || !ACTIVE_STATES.includes(session.state)) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const result = await api.GET("/api/v1/monitor/sessions/{session_id}", {
        params: { path: { session_id: session.id }, query: { show_rates: showRates } },
      });
      if (cancelled) return;
      if (result.data) setSession(result.data as MonitorSession);
      else setError(errorText(result.error, result.response.status));
      if (session.state !== "complete" && session.state !== "link_error" && session.state !== "stopped") {
        timer = setTimeout(() => void poll(), 1000);
      }
    };
    timer = setTimeout(() => void poll(), 1000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [session?.id, session?.state, showRates]);

  useEffect(() => {
    if (session?.state !== "complete") return;
    let cancelled = false;
    void api.GET("/api/v1/monitor/sessions/{session_id}", {
      params: { path: { session_id: session.id }, query: { show_rates: showRates } },
    }).then((result) => {
      if (!cancelled && result.data) setSession(result.data as MonitorSession);
    });
    return () => { cancelled = true; };
  }, [session?.id, session?.state, showRates]);

  async function start(mode: Mode) {
    setStarting(true);
    setError(null);
    setSession(null);
    const result = await api.POST("/api/v1/monitor/sessions", { body: { mode } });
    setStarting(false);
    if (result.data) setSession(result.data as MonitorSession);
    else if (result.response.status === 503) setError("No sensor is set up on this device.");
    else if (result.response.status === 409) setError("A monitor session is already active. Stop it before starting another.");
    else setError(errorText(result.error, result.response.status));
  }

  async function stop() {
    if (!session) return;
    setError(null);
    const result = await api.POST("/api/v1/monitor/sessions/{session_id}/stop", {
      params: { path: { session_id: session.id } },
    });
    if (result.data) setSession(result.data as MonitorSession);
    else setError(errorText(result.error, result.response.status));
  }

  const summary = session?.summary ?? null;
  const readings = Array.isArray(summary?.readings) ? summary.readings as Record<string, unknown>[] : [];
  const showValues = showRates || session?.mode === "heart_rate" || session?.mode === "breathing_rate";

  return (
    <section className="monitor-page" aria-labelledby="monitor-title">
      <header className="monitor-header">
        <div><p className="eyebrow">On-demand sensor session</p><h1 id="monitor-title">Monitor</h1></div>
        {session && <span className={`monitor-state monitor-state-${session.state}`} role="status">{stateLabel(session.state)}</span>}
      </header>

      {!active && <section className="card glass monitor-start" aria-labelledby="monitor-start-title">
        <h2 id="monitor-start-title">Choose a session</h2>
        <p className="muted">The sensor connects only for the session you choose.</p>
        <div className="monitor-start-actions">
          {(Object.keys(MODE_LABELS) as Mode[]).map((mode) => <button key={mode} type="button" disabled={starting} onClick={() => void start(mode)}>{starting ? "Connecting…" : MODE_LABELS[mode]}</button>)}
        </div>
      </section>}

      {active && session && <section className="card glass monitor-session" aria-live="polite">
        {session.state === "calibrating" ? <div className="monitor-calibration"><h2>Please leave the room for 60 s</h2><p className="monitor-countdown" aria-label={`${session.remaining_s ?? 0} seconds remaining`}>{session.remaining_s ?? 0}<span>s</span></p><p className="muted">The sensor is checking the room before measuring.</p></div> : <div><h2>{MODE_LABELS[session.mode]}</h2><p className="muted">{stateLabel(session.state)}</p>{session.state === "running" && session.remaining_s != null && <p className="monitor-countdown">{session.remaining_s}<span>s</span></p>}</div>}
        <button type="button" className="ghost monitor-stop" onClick={() => void stop()}>Stop session</button>
      </section>}

      {error && <p className="error monitor-error" role="alert">{error}</p>}
      {session?.state === "link_error" && session.error && <p className="error monitor-error" role="alert">{session.error}</p>}

      {session?.state === "complete" && <section className="card glass monitor-results" aria-labelledby="monitor-results-title">
        <h2 id="monitor-results-title">Session results</h2>
        {summary ? <>
          {session.mode === "sleep_analysis" && <SessionScore summary={summary} />}
          <div className="monitor-flags">
            <FlagCard title="Breathing" block={asRecord(summary.respiration)} />
            <FlagCard title="Heart" block={asRecord(summary.heart_rate)} />
            <FlagCard title="Movement" block={asRecord(summary.motion)} motion />
          </div>
          {session.mode === "sleep_analysis" && <p className="muted">{summaryLimitations(summary.limitations)}</p>}
          {session.mode === "sleep_analysis" && <label className="monitor-rate-switch"><span>Show measured rates (experimental)</span><input type="checkbox" role="switch" checked={showRates} onChange={(event) => setShowRates(event.target.checked)} /></label>}
          {showValues && readings.length > 0 && <div className="monitor-readings"><h3>Measured rates <span className="monitor-experimental">Experimental</span></h3><ul>{readings.map((reading, index) => <li key={`${String(reading.time_s)}-${index}`}>{formatReading(reading)}</li>)}</ul></div>}
        </> : <p className="muted">No session summary is available.</p>}
      </section>}

      {session?.state === "stopped" && <p className="muted monitor-ended" role="status">Session stopped.</p>}
    </section>
  );
}

function SessionScore({ summary }: { summary: Record<string, unknown> }) {
  const score = summary.sleep_score;
  const status = summary.score_status;
  if (status === "insufficient_inputs" || typeof score !== "number") return <p className="muted">Experimental session score unavailable: insufficient inputs.</p>;
  const components = asRecord(summary.components);
  return <div className="monitor-score"><h3>Experimental session score</h3><strong>{score}</strong>{components && <ul>{Object.entries(components).map(([name, value]) => <li key={name}>{name.replaceAll("_", " ")}: {String(value)}</li>)}</ul>}</div>;
}

function FlagCard({ title, block, motion = false }: { title: string; block?: Record<string, unknown>; motion?: boolean }) {
  const flag = stringValue(block?.flag);
  const label = motion ? flag === "still" ? "Still" : flag === "motion_flags" ? "Movement flagged" : "No data" : flag ? flagLabel(flag) : "No data";
  const variant = flag === "in_range" || flag === "still" ? "ok" : flag === "below_range" || flag === "above_range" || flag === "motion_flags" ? "warn" : "neutral";
  return <div className="monitor-flag-card"><h3>{title}</h3><span className={`monitor-chip monitor-chip-${variant}`}>{label}</span>{block?.in_range_pct != null && <p>{String(block.in_range_pct)}% in range</p>}</div>;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}
function stringValue(value: unknown): string | undefined { return typeof value === "string" ? value : undefined; }
function summaryLimitations(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string").join(" ") || "Experimental session result. Not a clinical measure.";
  return "Experimental session result. Not a clinical measure.";
}
function flagLabel(flag: string): string { return ({ in_range: "In range", below_range: "Below range", above_range: "Above range", no_data: "No data" } as Record<string, string>)[flag] ?? "No data"; }
function stateLabel(state: SessionState): string { return ({ connecting: "Connecting", link_check: "Checking signal", calibrating: "Calibrating", running: "Running", finalizing: "Finalizing", complete: "Done", link_error: "Connection problem", stopped: "Stopped" })[state]; }
function formatReading(reading: Record<string, unknown>): string {
  const time = typeof reading.time_s === "number" ? `${reading.time_s}s` : "Reading";
  const position = typeof reading.position === "string" ? ` · ${reading.position}` : "";
  const value = typeof reading.value === "number" ? ` · ${reading.value}` : "";
  return `${time}${position}${value}`;
}
