import type { InstrumentSummary } from "../api/types";

// Daily check-ins are offered on Overview ("Check-ins due"); the rest are questionnaires.
export const DAILY_INSTRUMENTS = new Set(["daily_am", "daily_pm"]);

export function QuestionnaireList({ items, onStart }: { items: InstrumentSummary[]; onStart(id: string): void }) {
  const list = items.filter((i) => !DAILY_INSTRUMENTS.has(i.id));
  if (list.length === 0) return <p className="muted">No questionnaires available.</p>;
  return (
    <ul className="plain">
      {list.map((i) => (
        <li key={i.id} className="row">
          <span>
            {i.name} <span className="muted">({i.items} questions)</span>
          </span>
          <button type="button" className="ghost" onClick={() => onStart(i.id)} aria-label={`Start ${i.name}`}>
            Start
          </button>
        </li>
      ))}
    </ul>
  );
}
