import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import { NightsTable } from "../components/NightsTable";
import { RrTrend } from "../components/RrTrend";

const DAYS = 28;

export function Sleep() {
  const end = new Date();
  const start = new Date(end.getTime() - (DAYS - 1) * 86_400_000);
  const from = start.toISOString().slice(0, 10), to = end.toISOString().slice(0, 10);
  const nights = useLoad(() => api.GET("/api/v1/nights", { params: { query: { from, to } } }), [from, to]);
  const today = useLoad(() => api.GET("/api/v1/today"));
  const baseline = today.data?.baselines.find((b) => b.feature === "rr_med");
  return (
    <div className="grid">
      <section className="card wide" aria-labelledby="trend-title">
        <h2 id="trend-title">Breathing rate trend</h2>
        <LoadState state={nights} label="nights">
          {(n) => <RrTrend nights={n} baseline={baseline} days={DAYS} />}
        </LoadState>
        {today.error && <p className="muted">Baseline unavailable ({today.error}); showing nights without the band.</p>}
      </section>
      <section className="card wide" aria-labelledby="nights-title">
        <h2 id="nights-title">Nights</h2>
        {nights.data && <NightsTable nights={nights.data} />}
      </section>
    </div>
  );
}
