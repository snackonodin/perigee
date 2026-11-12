import { useState } from "react";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { Mode } from "./useVitals";

export const SPEEDS = [1, 10, 60, 600, 3600] as const;

export function ReplayControl({ mode, onMode }: { mode: Mode; onMode(m: Mode): void }) {
  const sessions = useLoad(() => api.GET("/api/v1/sessions"));
  const [sessionId, setSessionId] = useState("");
  const [speed, setSpeed] = useState<number>(600);
  return (
    <div className="replay" role="group" aria-label="Replay demo night">
      <LoadState state={sessions} label="your recorded nights">
        {(list) =>
          list.length === 0 ? (
            <p className="muted">No recorded nights to replay yet.</p>
          ) : (
            <div className="row replay-row">
              <label>
                Night
                <select value={sessionId} onChange={(e) => setSessionId(e.target.value)}>
                  <option value="">Choose a night…</option>
                  {list.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.start_utc.slice(0, 16).replace("T", " ")} UTC{s.source_kind === "synthetic" ? " (synthetic)" : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Speed
                <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
                  {SPEEDS.map((s) => (
                    <option key={s} value={s}>
                      {s}×
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" disabled={!sessionId} onClick={() => onMode({ kind: "replay", sessionId, speed })}>
                Replay demo night
              </button>
              {mode.kind === "replay" && (
                <button type="button" className="ghost" onClick={() => onMode({ kind: "live" })}>
                  Back to live
                </button>
              )}
            </div>
          )
        }
      </LoadState>
    </div>
  );
}
