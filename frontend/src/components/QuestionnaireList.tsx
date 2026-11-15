import type { InstrumentSummary } from "../api/types";
import { friendlyName } from "./instrumentNames";

// Daily check-ins are offered on Overview ("Check-ins due"); the rest are questionnaires.
export const DAILY_INSTRUMENTS = new Set(["daily_am", "daily_pm", "body_cabin"]);
// Not check-ins: the persona questions live on the Persona page only (mini_ipip is retired).
export const NOT_CHECKINS = new Set(["mini_ipip", "psyche60", "psyche_p1", "psyche_p2", "psyche_p3", "psyche_p4", "psyche_p5"]);

export function QuestionnaireList({ items, onStart, dailyOnly = false, completedIds=[] }: { items: InstrumentSummary[]; onStart(id: string): void; dailyOnly?: boolean; completedIds?:string[] }) {
  const list = items.filter((i) => !NOT_CHECKINS.has(i.id) && DAILY_INSTRUMENTS.has(i.id) === dailyOnly);
  if (list.length === 0) return <p className="muted">{dailyOnly ? "No daily check-ins are available right now." : "No questionnaires available."}</p>;
  return (
    <ul className="plain">
      {list.map((i) => (
        <li key={i.id} className="questionnaire-row">
          <span className="questionnaire-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 4h12v16H6zM9 8h6m-6 4h6m-6 4h4"/></svg></span>
          <span className="questionnaire-name">{friendlyName(i.id, i.name)} <small>({i.items} questions)</small></span>
          {(completedIds.includes(i.id)||dailyOnly)?<span className={`questionnaire-state ${completedIds.includes(i.id)?"done":"due"}`}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={completedIds.includes(i.id)?"m5 12 4 4L19 6":"M12 4v8l5 3"}/></svg>{completedIds.includes(i.id)?"Done":"Due today"}</span>:<span aria-hidden="true"/>}
            <button type="button" className="ghost" onClick={() => onStart(i.id)} aria-label={`Start ${friendlyName(i.id, i.name)}`}>
              Begin
          </button>
        </li>
      ))}
    </ul>
  );
}
