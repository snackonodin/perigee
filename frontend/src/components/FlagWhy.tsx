import { fmt } from "./format";

interface Entry {
  value?: number | null;
  median?: number | null;
  mad?: number | null;
  z?: number;
  skipped?: string;
  band?: { band?: string };
}

const SKIP_NOTE: Record<string, string> = {
  warm_up: "baseline warming up",
  no_baseline: "no baseline yet",
  undefined: "not enough spread",
};

/** The "why" of a flag: each signal's value against the person's own median ± MAD, and z. */
export function FlagWhy({ components }: { components: Record<string, unknown> }) {
  const alert = typeof components.alert_robust_z === "number" ? components.alert_robust_z : null;
  const rows: { domain: string; name: string; e: Entry }[] = [];
  for (const [domain, key] of [
    ["Body", "physiology"],
    ["Mood", "mental"],
  ] as const) {
    const entries = components[key];
    if (entries && typeof entries === "object") {
      for (const [name, e] of Object.entries(entries as Record<string, Entry>)) {
        if (e && typeof e === "object") rows.push({ domain, name, e });
      }
    }
  }
  if (rows.length === 0) return <p className="muted">No details recorded.</p>;
  return (
    <table className="why">
      <thead>
        <tr>
          <th scope="col">Area</th>
          <th scope="col">Signal</th>
          <th scope="col">Value</th>
          <th scope="col">Your usual (median ± MAD)</th>
          <th scope="col">z</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(({ domain, name, e }) => {
          const z = typeof e.z === "number" ? e.z : null;
          const high = z !== null && alert !== null && Math.abs(z) >= alert;
          const note = e.band?.band ? `questionnaire band: ${e.band.band}` : SKIP_NOTE[e.skipped ?? ""] ?? "–";
          return (
            <tr key={`${domain}.${name}`}>
              <td>{domain}</td>
              <td>{name}</td>
              <td>{fmt(e.value, 2)}</td>
              <td>{e.median === undefined || e.median === null ? "–" : `${fmt(e.median, 2)} ± ${fmt(e.mad, 2)}`}</td>
              <td className={high ? "z-high" : undefined}>{z === null ? note : `${z >= 0 ? "+" : ""}${fmt(z, 1)}`}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
