import { useState } from "react";
import { BreathingMonitor, HeartMonitor } from "../live/monitors";
import { ReplayControl } from "../live/ReplayControl";
import { StatusPill } from "../live/StatusPill";
import { type Mode, useVitals } from "../live/useVitals";

function LivePage({ kind }: { kind: "breathing" | "heart" }) {
  const [mode, setMode] = useState<Mode>({ kind: "live" });
  const v = useVitals(mode);
  return (
    <div className="grid">
      {kind === "heart" && (
        <p className="experimental card wide" role="note">
          EXPERIMENTAL: heart rate from Wi-Fi sensing is not validated. It is shown for research only, with no
          thresholds or alerts. Do not rely on it.
        </p>
      )}
      <section className="card wide" aria-labelledby="live-title">
        <div className="row">
          <h2 id="live-title">{kind === "heart" ? "Heart (live)" : "Breathing (live)"}</h2>
          <StatusPill status={v.status} replay={mode.kind === "replay"} />
        </div>
        {kind === "heart" ? <HeartMonitor hearts={v.hearts} /> : <BreathingMonitor windows={v.windows} />}
      </section>
      <section className="card wide" aria-labelledby="replay-title">
        <h2 id="replay-title">Replay demo night</h2>
        <ReplayControl mode={mode} onMode={setMode} />
      </section>
    </div>
  );
}

export const Breathing = () => <LivePage kind="breathing" />;
export const Heart = () => <LivePage kind="heart" />;
