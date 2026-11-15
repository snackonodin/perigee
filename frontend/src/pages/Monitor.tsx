import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Icon } from "../components/icons";
import { useLoad } from "../api/useLoad";
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
const MODE_INFO: Record<Mode, { icon: string; line: string }> = {
  sleep_analysis: { icon: "sleep", line: "Breathing, heart and movement while you rest, with an experimental session score." },
  heart_rate: { icon: "monitor", line: "A short experimental heart-rate estimate while you sit still." },
  breathing_rate: { icon: "breath", line: "Your breathing rate while you sit still near the sensor." },
};
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
  const [mode, setMode] = useState<Mode>("sleep_analysis");
  const [noSensor, setNoSensor] = useState(false);
  const modes = useLoad(() => api.GET("/api/v1/monitor/modes"));
  const timing = new Map((modes.data ?? []).map((m) => [m.mode, m]));
  const phaseTotal = useRef<{ state?: SessionState; total: number }>({ total: 0 });
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
    setNoSensor(false);
    setSession(null);
    const result = await api.POST("/api/v1/monitor/sessions", { body: { mode } });
    setStarting(false);
    if (result.data) setSession(result.data as MonitorSession);
    else if (result.response.status === 503) setNoSensor(true);
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
        <div><h1 id="monitor-title">Monitor</h1></div>
        <StatusIsland state={session?.state} noSensor={noSensor && !session} />
      </header>

      {!active && <section className="card monitor-start" data-pet-avoid aria-labelledby="monitor-start-title">
        <h2 id="monitor-start-title">Choose a session</h2>
        <p className="muted">The sensor connects only for the session you choose. Every session starts with a short empty-room check.</p>
        <div className="monitor-modes" role="radiogroup" aria-labelledby="monitor-start-title">
          {(Object.keys(MODE_LABELS) as Mode[]).map((m) => <label key={m} className={`monitor-mode tile-press${mode === m ? " selected" : ""}`}>
            <input type="radio" name="monitor-mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
            <span className="monitor-mode-icon" aria-hidden="true"><Icon name={MODE_INFO[m].icon} /></span>
            <strong>{MODE_LABELS[m]}</strong>{timing.get(m) && <span className="meta-label monitor-mode-time">{duration(timing.get(m)!.total_s)} · incl. {duration(timing.get(m)!.calibration_s)} room check</span>}<span className="monitor-mode-line">{MODE_INFO[m].line}</span>
          </label>)}
        </div>
        <div className="monitor-start-row"><button type="button" className="btn-uv monitor-go" disabled={starting} onClick={() => void start(mode)}>{starting ? "Connecting…" : `Start ${MODE_LABELS[mode].toLowerCase()}`}</button></div>
        {noSensor && <p className="monitor-nosensor" role="status"><Icon name="monitor" size={20} /><span>No sensor is set up on this device. Connect the receiver, then start again.</span></p>}
      </section>}

      {active && session && <section className="card monitor-session" aria-live="polite">
        <ProgressRing session={session} totalRef={phaseTotal} />
        <div className="monitor-session-copy">
          {session.state === "calibrating" ? <><h2>Please leave the room for 60 s</h2><p className="section-meta">Room check</p><p className="muted">The sensor is checking the empty room before measuring.</p></>
            : <><h2>{MODE_LABELS[session.mode]}</h2><p className="section-meta">{stateLabel(session.state)}</p><p className="muted">{session.state === "running" ? "Stay still near the sensor until the ring closes." : "Getting the sensor ready."}</p></>}
          <button type="button" className="ghost monitor-stop" onClick={() => void stop()}>Stop session</button>
        </div>
      </section>}

      {error && <p className="error monitor-error" role="alert">{error}</p>}
      {session?.state === "link_error" && session.error && <p className="error monitor-error" role="alert">{session.error}</p>}

      {session?.state === "complete" && <section className="card monitor-results" aria-labelledby="monitor-results-title">
        <h2 id="monitor-results-title">Session results</h2>
        {summary ? <>
          {session.mode === "sleep_analysis" && <SessionScore summary={summary} />}
          {/* each mode shows the measure it is for (plus movement); sleep analysis shows all */}
          <div className={`monitor-flags monitor-flags-${session.mode === "sleep_analysis" ? 3 : 2}`}>
            {session.mode !== "heart_rate" && <FlagCard title="Breathing" block={asRecord(summary.respiration)} />}
            {session.mode !== "breathing_rate" && <FlagCard title="Heart" block={asRecord(summary.heart_rate)} />}
            <FlagCard title="Movement" block={asRecord(summary.motion)} motion />
          </div>
          <PeakEstimates peaks={asRecord(summary.peak_estimates)} />
          {session.mode === "sleep_analysis" && <p className="muted">{summaryLimitations(summary.limitations)}</p>}
          {session.mode === "sleep_analysis" && <label className="monitor-rate-switch"><span>Show measured rates (experimental)</span><input type="checkbox" role="switch" checked={showRates} onChange={(event) => setShowRates(event.target.checked)} /></label>}
          {showValues && readings.length > 0 && <div className="monitor-readings"><h3>Measured rates <span className="monitor-experimental">Experimental</span></h3><ul>{readings.map((reading, index) => <li key={`${String(reading.time_s)}-${index}`}>{formatReading(reading)}</li>)}</ul></div>}
        </> : <p className="muted">No session summary is available.</p>}
      </section>}

      {session?.state === "stopped" && <p className="muted monitor-ended" role="status">Session stopped.</p>}

      {!active && <RealCaptures />}
    </section>
  );
}

/** Dynamic-island status pill: one pill that morphs Connecting -> Calibrating -> Running -> Done. */
function StatusIsland({ state, noSensor = false }: { state?: SessionState; noSensor?: boolean }) {
  const label = state ? stateLabel(state) : noSensor ? "No sensor" : "Sensor idle";
  return <span className={`status-island island-${state ?? (noSensor ? "nosensor" : "idle")}`} role="status" aria-label={`Session status: ${label}`}>
    <i className="island-dot" aria-hidden="true" /><span key={label} className="island-label">{label}</span>
  </span>;
}

/** Progress ring for the current phase; the satellite dot shows time left. The phase total is the
 *  first remaining_s seen in that phase (durations are config values, not repeated here). */
function ProgressRing({ session, totalRef }: { session: MonitorSession; totalRef: { current: { state?: SessionState; total: number } } }) {
  const remaining = session.remaining_s ?? null;
  if (totalRef.current.state !== session.state) totalRef.current = { state: session.state, total: remaining ?? 0 };
  else if (remaining != null && remaining > totalRef.current.total) totalRef.current.total = remaining;
  const total = totalRef.current.total;
  const timed = remaining != null && total > 0 && (session.state === "calibrating" || session.state === "running");
  const progress = timed ? 1 - remaining! / total : 0;
  const r = 88, c = 2 * Math.PI * r;
  return <div className={`progress-ring ${timed ? "" : "indeterminate"}`} style={{ "--p": progress } as CSSProperties}>
    <svg viewBox="0 0 200 200" aria-hidden="true">
      <circle className="ring-track" cx="100" cy="100" r={r} />
      <circle className="ring-fill" cx="100" cy="100" r={r} strokeDasharray={c} strokeDashoffset={c * (1 - progress)} />
    </svg>
    <span className="satellite" style={{ "--sat-a": `${-90 + progress * 360}deg`, "--sat-r": "88px" } as CSSProperties} aria-hidden="true" />
    {timed ? <p className="monitor-countdown" aria-label={`${remaining} seconds remaining`}>{remaining}<span>s</span></p>
      : <p className="meta-label ring-wait">{session.state === "finalizing" ? "Finishing" : "Preparing"}</p>}
  </div>;
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
function duration(seconds: number): string { return seconds >= 60 && seconds % 60 === 0 ? `${seconds / 60} min` : seconds >= 60 ? `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s` : `${Math.round(seconds)} s`; }
function stateLabel(state: SessionState): string { return ({ connecting: "Connecting", link_check: "Checking signal", calibrating: "Calibrating", running: "Running", finalizing: "Finalizing", complete: "Done", link_error: "Connection problem", stopped: "Stopped" })[state]; }
function formatReading(reading: Record<string, unknown>): string {
  const time = typeof reading.time_s === "number" ? `${reading.time_s}s` : "Reading";
  const position = typeof reading.position === "string" ? ` · ${reading.position}` : "";
  const value = typeof reading.value === "number" ? ` · ${reading.value}` : "";
  return `${time}${position}${value}`;
}

type Rec = Record<string, unknown>;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const bpm = (v: unknown): string => { const n = num(v); return n == null ? "–" : `${n.toFixed(1)}`; };

/** Raw per-window estimates: both breathing methods and heart-rate peaks. A breathing window
 *  where the two methods disagree is marked unconfirmed (it never becomes a flag or score). */
function PeakEstimates({ peaks }: { peaks?: Rec }) {
  const breathing = (Array.isArray(peaks?.breathing) ? peaks.breathing : []) as Rec[];
  const heart = (Array.isArray(peaks?.heart_rate) ? peaks.heart_rate : []) as Rec[];
  if (!peaks || (breathing.length === 0 && heart.length === 0)) return null;
  return <div className="monitor-peaks">
    <h3>Peak estimates <span className="monitor-experimental">Experimental</span></h3>
    {breathing.length > 0 && <table className="monitor-peak-table">
      <caption>Breathing, breaths per minute, per window</caption>
      <thead><tr><th scope="col">Window end</th><th scope="col">Spectral peak</th><th scope="col">Peak count</th><th scope="col">Status</th></tr></thead>
      <tbody>{breathing.map((w, i) => <tr key={i}>
        <td>{bpm(w.time_s)} s</td><td>{bpm(w.spectral_bpm)}</td><td>{bpm(w.peak_count_bpm)}</td>
        <td>{w.confirmed ? <span className="monitor-chip monitor-chip-ok">Methods agree</span> : <span className="monitor-chip monitor-chip-neutral">Unconfirmed</span>}</td>
      </tr>)}</tbody>
    </table>}
    {heart.length > 0 && <table className="monitor-peak-table">
      <caption>Heart rate, beats per minute, per window</caption>
      <thead><tr><th scope="col">Window end</th><th scope="col">Peak estimate</th></tr></thead>
      <tbody>{heart.map((w, i) => <tr key={i}><td>{bpm(w.time_s)} s</td><td>{bpm(w.bpm)}</td></tr>)}</tbody>
    </table>}
    {typeof peaks.note === "string" && <p className="muted">{peaks.note}</p>}
  </div>;
}

/** Real ESP32 captures from the team's saved tests. Demo accounts only (the API returns
 *  an empty list for a real account, and then nothing renders). */
function RealCaptures() {
  const samples = useLoad(() => api.GET("/api/v1/monitor/samples"));
  const list = (samples.data ?? []) as Rec[];
  if (list.length === 0) return null;
  async function download(id: string) {
    const r = await api.GET("/api/v1/monitor/samples/{sample_id}/capture.csv", { params: { path: { sample_id: id } }, parseAs: "blob" });
    if (!r.data) return;
    const url = URL.createObjectURL(r.data as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${id}.csv`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="card monitor-real" aria-labelledby="monitor-real-title">
    <h2 id="monitor-real-title">Real ESP32 captures</h2>
    <p className="muted">Recorded by the team with the real sensor. Shown on demo accounts so you can see real data next to the synthetic nights.</p>
    {list.map((d) => {
      const acc = asRecord(d.accuracy_pct) ?? {};
      const truth = asRecord(d.truth) ?? {};
      const windows = (Array.isArray(d.windows) ? d.windows : []) as Rec[];
      const when = typeof d.measured_at === "string" ? new Date(d.measured_at) : null;
      return <article key={String(d.id)} className="monitor-real-item">
        <h3>{String(d.title)}</h3>
        <p className="monitor-real-meta">Measured by the host at <time dateTime={String(d.measured_at)}>{when ? when.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit", timeZoneName: "short" }) : "–"}</time> · {String(d.rows)} packets at {bpm(d.packet_rate_hz)} Hz</p>
        <p className="muted">{String(d.setup)}</p>
        <table className="monitor-peak-table">
          <caption>Breathing, breaths per minute. True rate {bpm(truth.bpm)} (operator count)</caption>
          <thead><tr><th scope="col">Window</th><th scope="col">Spectral peak</th><th scope="col">Peak count</th></tr></thead>
          <tbody>{windows.map((w, i) => <tr key={i}><td>{bpm(w.t_start_s)}–{bpm(w.t_end_s)} s</td><td>{bpm(w.spectral_bpm)}</td><td>{bpm(w.peak_count_bpm)}</td></tr>)}</tbody>
        </table>
        <p className="monitor-real-acc"><span className="monitor-chip monitor-chip-ok">Spectral {bpm(acc.spectral)}% accurate</span> <span className="monitor-chip monitor-chip-ok">Peak count {bpm(acc.peak_count)}% accurate</span></p>
        <p className="muted monitor-real-small">{String(d.accuracy_definition ?? "")} {String(d.measured_by ?? "")}.</p>
        <button type="button" className="ghost" onClick={() => void download(String(d.id))}>Download CSI capture (CSV)</button>
      </article>;
    })}
  </section>;
}
