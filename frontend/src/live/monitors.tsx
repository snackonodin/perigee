import { fmt } from "../components/format";
import type { Pt } from "./decimate";
import { LiveChart } from "./LiveChart";
import type { HeartEvent, WindowEvent } from "./types";

const ms = (iso: string) => Date.parse(iso);

export function BreathingMonitor({ windows }: { windows: readonly WindowEvent[] }) {
  const last = windows.at(-1);
  const rrA: Pt[] = windows.map((w) => ({ t: ms(w.t_start), v: w.presence ? w.rr_a : null }));
  const rrB: Pt[] = windows.map((w) => ({ t: ms(w.t_start), v: w.presence ? w.rr_b : null }));
  const scores = windows.map((w) => w.motion_score).filter((s): s is number => typeof s === "number");
  const maxScore = scores.length ? Math.max(...scores) : 0;
  return (
    <div className="monitor">
      <dl className="stats">
        <div>
          <dt>Breathing rate</dt>
          <dd className="big">{last?.presence ? fmt(last.rr_a) : "–"} <small>breaths/min</small></dd>
        </div>
        <div>
          <dt>Second estimate</dt>
          <dd>{last?.presence ? fmt(last.rr_b) : "–"}</dd>
        </div>
        <div>
          <dt>Peak-to-noise</dt>
          <dd>{fmt(last?.pnr_db)} dB</dd>
        </div>
        <div>
          <dt>Signal quality</dt>
          <dd>
            <meter min={0} max={1} value={last?.quality ?? 0} aria-label="Signal quality" /> {fmt((last?.quality ?? 0) * 100, 0)} %
          </dd>
        </div>
        <div>
          <dt>Presence</dt>
          <dd className={last?.presence ? "present" : "absent"}>{last ? (last.presence ? "In bed" : "Not detected") : "–"}</dd>
        </div>
      </dl>
      <LiveChart
        label={`Breathing rate per window${last?.presence ? `, latest ${fmt(last.rr_a)} breaths per minute` : ""}`}
        unit="breaths/min"
        series={[
          { name: "rr_b", points: rrB, className: "trace faint" },
          { name: "rr_a", points: rrA, className: "trace" },
        ]}
      />
      <div className="motion-strip" role="img" aria-label="Motion per window (darker = more movement)">
        {windows.slice(-120).map((w) => (
          <span
            key={w.t_start}
            className={w.motion ? "m flagged" : "m"}
            data-score={w.motion_score ?? ""}
            style={{ opacity: w.motion_score === null || maxScore === 0 ? 0.15 : 0.2 + 0.8 * (w.motion_score / maxScore) }}
            title={`${w.t_start.slice(11, 16)} UTC${w.motion ? ": movement" : ""}`}
          />
        ))}
      </div>
      <p className="muted small">Motion shades are relative within this view; marked windows were flagged as movement.</p>
    </div>
  );
}

export function HeartMonitor({ hearts }: { hearts: readonly HeartEvent[] }) {
  const last = hearts.at(-1);
  const hr: Pt[] = hearts.map((h) => ({ t: ms(h.t_start), v: h.hr_bpm }));
  return (
    <div className="monitor">
      <dl className="stats">
        <div>
          <dt>Heart rate (experimental)</dt>
          <dd className="big">{fmt(last?.hr_bpm, 0)} <small>beats/min</small></dd>
        </div>
        <div>
          <dt>Signal quality</dt>
          <dd>
            <meter min={0} max={1} value={last?.quality ?? 0} aria-label="Signal quality" /> {fmt((last?.quality ?? 0) * 100, 0)} %
          </dd>
        </div>
      </dl>
      <LiveChart label="Experimental heart-rate estimate per window" unit="beats/min" series={[{ name: "hr", points: hr, className: "trace pulse" }]} />
    </div>
  );
}
