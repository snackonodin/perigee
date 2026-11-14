import { api } from "../api/client";
import type { components } from "../api/schema";
import type { InstrumentSummary } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "./format";
import "./IndexCards.css";
import { LoadState } from "./LoadState";
import { friendlyName } from "./instrumentNames";

type IndexOut = components["schemas"]["IndexOut"];
type IndicesOut = components["schemas"]["IndicesOut"];

const DAY = 86_400_000;

/** Monday (UTC, ISO week start) of the week containing `t`, as YYYY-MM-DD. */
export function mondayOf(t: number): string {
  const d = new Date(t);
  const dow = (d.getUTCDay() + 6) % 7; // Mon=0 … Sun=6
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - dow * DAY)
    .toISOString()
    .slice(0, 10);
}

/** The last `n` ISO-week Mondays, oldest first, ending with the current week. */
export function lastMondays(n: number, now: number): string[] {
  const cur = Date.parse(`${mondayOf(now)}T00:00:00Z`);
  return Array.from({ length: n }, (_, i) => new Date(cur - (n - 1 - i) * 7 * DAY).toISOString().slice(0, 10));
}

const DIRECTION: Record<string, string> = { "1": "higher is worse", "-1": "higher is better" };

function label(key: string, names: Map<string, string>): string {
  const [inst, item] = key.split(".");
  const base = names.get(inst) ?? inst;
  return item ? `${base} · ${item.replace(/_/g, " ")}` : base;
}

function value(key: string, v: number | undefined): string {
  if (v === undefined) return "no data this week";
  return key === "who5" ? `${fmt(v, 0)} %` : fmt(v, key.includes(".") ? 1 : 0);
}

/** Week-by-week values as an inline SVG sparkline; weeks without data are gaps. */
function Sparkline({ title, weeks, values }: { title: string; weeks: string[]; values: (number | undefined)[] }) {
  const W = 220, H = 48, P = 6;
  const nums = values.filter((v): v is number => v !== undefined);
  if (nums.length === 0) return null;
  let latestIndex = -1;
  values.forEach((v, i) => { if (v !== undefined) latestIndex = i; });
  const lo = Math.min(...nums), hi = Math.max(...nums);
  const span = hi - lo || 1;
  const x = (i: number) => P + (i / Math.max(weeks.length - 1, 1)) * (W - 2 * P);
  const y = (v: number) => H - P - ((v - lo) / span) * (H - 2 * P);
  // Split into runs of consecutive weeks so a missing week leaves a gap.
  const runs: { i: number; v: number }[][] = [];
  values.forEach((v, i) => {
    if (v === undefined) return;
    const last = runs.at(-1);
    if (last && last.at(-1)!.i === i - 1) last.push({ i, v });
    else runs.push([{ i, v }]);
  });
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: last ${weeks.length} weeks`}>
      {runs.map((run) =>
        run.length > 1 ? (
          <polyline key={run[0].i} className="line" points={run.map((p) => `${x(p.i)},${y(p.v)}`).join(" ")} />
        ) : null,
      )}
      {(() => {
        const i = latestIndex;
        const v = values[i];
        return i < 0 || v === undefined ? null : <circle className="pt" cx={x(i)} cy={y(v)} r={2.5}>
          <title>{`Latest week of ${weeks[i]}: ${fmt(v, 1)}`}</title>
        </circle>;
      })()}
    </svg>
  );
}

/** Citation for a band alert, from the instrument catalog (scoring.ranges_source). */
function useCitations(ids: string[]) {
  return useLoad(
    async () => {
      const entries = await Promise.all(
        ids.map(async (id) => {
          const r = await api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: id } } });
          const scoring = (r.data as { scoring?: { ranges_source?: string } } | undefined)?.scoring;
          return [id, scoring?.ranges_source ?? ""] as const;
        }),
      );
      return { data: Object.fromEntries(entries) as Record<string, string> };
    },
    [ids.join(",")],
  );
}

/** Weekly mental indices: value, band, direction, a cited band-alert badge and a trend. */
export function IndexCards({
  instruments = [],
  weeks = 8,
  now = Date.now(),
}: {
  instruments?: InstrumentSummary[];
  weeks?: number;
  now?: number;
}) {
  const mondays = lastMondays(weeks, now);
  const load = useLoad(async () => {
    const res = await Promise.all(mondays.map((week) => api.GET("/api/v1/indices", { params: { query: { week } } })));
    const bad = res.find((r) => r.data === undefined);
    return bad ? { error: bad.error, response: bad.response } : { data: res.map((r) => r.data as IndicesOut) };
  }, [mondays.join(",")]);

  const all = load.data ?? [];
  const current = all.at(-1)?.indices ?? {};
  const alertIds = Object.entries(current)
    .filter(([k, v]) => v.band_alert && !k.includes("."))
    .map(([k]) => k)
    .sort();
  const cites = useCitations(alertIds);
  const names = new Map(instruments.map((i) => [i.id, friendlyName(i.id, i.name)]));

  return (
    <LoadState state={load} label="weekly indices">
      {(series) => {
        const keys = Array.from(new Set(series.flatMap((w) => Object.keys(w.indices)))).sort();
        if (keys.length === 0) {
          return <p className="vital-empty"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19h16M7 16v-4m5 4V8m5 8v-6"/></svg><span>No questionnaires or check-ins in the last {weeks} weeks yet; your patterns appear here after the first ones.</span></p>;
        }
        return (
          <>
            <div className="index-grid">
              {keys.map((key) => {
                const now_: IndexOut | undefined = current[key];
                const title = label(key, names);
                return (
                  <article className="index" key={key} aria-labelledby={`idx-${key}`}>
                    <h3 id={`idx-${key}`}>{title}</h3>
                    <p className="index-value">{value(key, now_?.value)}</p>
                    <dl className="kv">
                      <dt>Band</dt>
                      <dd>{now_?.band ?? (key.includes(".") ? "no band (check-in item)" : "–")}</dd>
                      <dt>Direction</dt>
                      <dd>{DIRECTION[String(now_?.direction ?? series.find((w) => w.indices[key])?.indices[key].direction)] ?? "not set"}</dd>
                    </dl>
                    {now_?.band_alert && (
                      <div className="band-alert">
                        <span className="badge">band alert</span>
                        <details>
                          <summary>Why this badge</summary>
                          <p className="muted">
                            This score is in a range that the published source marks as worth following up.
                            It is a screening signal, not a diagnosis.
                          </p>
                          <p className="footnote">Source: {cites.data?.[key] || "instrument catalog"}</p>
                        </details>
                      </div>
                    )}
                    <Sparkline title={title} weeks={mondays} values={series.map((w) => w.indices[key]?.value)} />
                  </article>
                );
              })}
            </div>
            <p className="footnote muted">
              Week of {mondays.at(-1)} (Monday, UTC). Trends show the last {weeks} weeks. Questionnaires show the
              latest score in each week; check-in items show the weekly average.
            </p>
          </>
        );
      }}
    </LoadState>
  );
}
