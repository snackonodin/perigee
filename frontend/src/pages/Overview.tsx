import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { FlagWhy } from "../components/FlagWhy";
import { fmt } from "../components/format";
import { GuidanceCard } from "../components/GuidanceCard";
import { TodayCard } from "../components/TodayCard";

const STATE_LABEL: Record<string, string> = {
  both: "Body and mood both differ from your usual",
  phys_only: "Your sleep breathing differs from your usual",
  mental_only: "Your check-ins differ from your usual",
};

export function Overview() {
  const { data: today, error, loading } = useLoad(() => api.GET("/api/v1/today"));
  if (loading && !today) return <p className="muted panel">Loading…</p>;
  if (!today) return <p className="error panel" role="alert">{error}</p>;
  return (
    <div className="grid">
      <TodayCard today={today} />
      <section className="card wide" aria-labelledby="flags-title">
        <h2 id="flags-title">What stands out</h2>
        {today.flags.length === 0 ? (
          <p className="muted">Nothing unusual for you in the last 7 days.</p>
        ) : (
          today.flags.slice(0, 3).map((f) => (
            <article key={f.id} className="flag">
              <h3>{STATE_LABEL[f.state] ?? f.state}</h3>
              <p className="muted">
                {f.date} · priority {fmt(f.priority, 2)}
              </p>
              <FlagWhy components={f.components} />
              {f.guidance.length > 0 && <h4>Suggestions</h4>}
              {f.guidance.map((g) => (
                <GuidanceCard key={g.card_key} card={g} />
              ))}
            </article>
          ))
        )}
      </section>
    </div>
  );
}
