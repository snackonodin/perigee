import type { NightOut } from "../api/types";
import { clock, fmt } from "./format";

export function NightsTable({ nights }: { nights: NightOut[] }) {
  if (nights.length === 0) return <p className="muted">No nights in this period.</p>;
  return (
    <div className="table-wrap">
      <table className="nights">
        <thead>
          <tr>
            <th scope="col">Night</th>
            <th scope="col">Valid</th>
            <th scope="col">Quality</th>
            <th scope="col">Breathing (median)</th>
            <th scope="col">In bed</th>
            <th scope="col">Onset</th>
            <th scope="col">Midsleep</th>
            <th scope="col">Wake</th>
            <th scope="col">Source</th>
          </tr>
        </thead>
        <tbody>
          {nights.map((n) => (
            <tr key={n.id} className={n.valid ? undefined : "invalid"}>
              <td>{n.date}</td>
              <td>{n.valid ? "yes" : "no"}</td>
              <td>{fmt(n.quality * 100, 0)} %</td>
              <td>{fmt(n.rr_med)}</td>
              <td>{fmt(n.presence_hours)} h</td>
              <td>{clock(n.onset)}</td>
              <td>{clock(n.midsleep)}</td>
              <td>{clock(n.wake)}</td>
              <td>{n.source_kind === "synthetic" ? "synthetic" : n.source_kind}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
