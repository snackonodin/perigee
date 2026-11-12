import type { GuidanceCardOut } from "../api/types";

export function GuidanceCard({ card }: { card: GuidanceCardOut }) {
  return (
    <article className="guidance">
      <h4>{card.title}</h4>
      <p>{card.body}</p>
      {card.contact_support_text && <p>{card.contact_support_text}</p>}
      <p className="src">
        Source: {card.source_note}
        {" · "}
        {card.reviewed_by ? `reviewed by ${card.reviewed_by}` : <strong>not yet clinically reviewed</strong>}
      </p>
    </article>
  );
}
