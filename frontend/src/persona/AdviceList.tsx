import { usePersona } from "./PersonaProvider";

/** Context-matched advice from the persona, as calm cards (or a numbered checklist when the
 *  person prefers structure). Nothing renders when there is no advice. */
export function AdviceList({ headingLevel = "h2", emptyText }: { headingLevel?: "h2" | "h3"; emptyText?: string }) {
  const { persona, style } = usePersona();
  const advice = persona?.available ? persona.advice ?? [] : [];
  if (!advice.length) return emptyText ? <p className="advice-empty muted">{emptyText}</p> : null;
  const H = headingLevel;
  return <section className="advice" aria-labelledby="advice-title">
    <H id="advice-title">For the next day or two</H>
    {style.structured_checklist_mode
      ? <ol className="advice-checklist">{advice.map((a) => <li key={a.tag}>{a.text}</li>)}</ol>
      : <ul className="advice-cards">{advice.map((a) => <li key={a.tag} className="advice-card">{a.text}</li>)}</ul>}
  </section>;
}
