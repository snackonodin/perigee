import type { ReactNode } from "react";

export const CHARACTERS = [
  { id: "nimbus", name: "Nimbus", personality: "A soft-spoken little cloud who is never in a hurry." },
  { id: "pip", name: "Pip", personality: "A cheerful sprout-egg who loves small wins." },
  { id: "lumi", name: "Lumi", personality: "A thoughtful moon-bun who listens more than talks." },
] as const;

export type CharacterId = (typeof CHARACTERS)[number]["id"];

export function CharacterBody({ id }: { id: CharacterId }) {
  const outline = "var(--text, var(--ink))";
  const mint = "var(--mint, var(--aurora))";
  const peach = "var(--peach, var(--orange))";
  const lavender = "var(--lavender, var(--violet))";
  const butter = "var(--butter, var(--amber))";
  const alertSoft = "var(--alert-soft, var(--rose))";
  let art: ReactNode;

  if (id === "nimbus") {
    art = <>
      <path d="M8 24c0-7 5-12 12-12 1-7 7-11 14-10 6 0 10 4 12 10 8-2 16 4 16 12v22H8z" fill={mint} />
      <ellipse cx="22" cy="55" rx="5" ry="3" fill={mint} /><ellipse cx="50" cy="55" rx="5" ry="3" fill={mint} />
    </>;
  } else if (id === "pip") {
    art = <>
      <path d="M35 5v10M35 8c-6-8-13-4-12 0 3 5 8 5 12 2m0 0c5-8 13-5 11-1-2 5-7 6-11 3" fill="none" stroke="var(--teal, var(--aurora))" strokeWidth="2" />
      <ellipse cx="35" cy="40" rx="24" ry="29" fill={peach} />
    </>;
  } else {
    art = <>
      <path d="M13 22 10 7q0-3 3-2l14 12m22 5 3-15q0-3-3-2L35 18" fill={lavender} />
      <path d="M16 23C16 9 25 5 36 7c12 1 19 9 19 21v18c0 12-8 19-20 19S16 58 16 46z" fill={lavender} />
      <path d="m16 8 1.5 4 4 .5-3 2.5 1 4-3.5-2-3.5 2 1-4-3-2.5 4-.5z" fill={butter} />
    </>;
  }

  return <svg className="pet-body" viewBox="0 0 72 72" aria-hidden="true">
    <g stroke={outline} strokeWidth="2" strokeOpacity=".85" strokeLinejoin="round" strokeLinecap="round">{art}</g>
    <g stroke={outline} strokeWidth="0"><ellipse className="pet-eye" cx={id === "pip" ? 27 : 27} cy={id === "nimbus" ? 32 : id === "pip" ? 35 : 31} rx="3" ry="4" /><ellipse className="pet-eye" cx={id === "pip" ? 43 : 45} cy={id === "nimbus" ? 32 : id === "pip" ? 35 : 31} rx="3" ry="4" /></g>
    <g className="pet-brows" stroke={outline}><path d="M23 25h7"/><path d="M42 25h7"/></g>
    <g fill={id === "pip" ? alertSoft : peach}><ellipse className="pet-cheek" cx="19" cy="41" rx="4.5" ry="3"/><ellipse className="pet-cheek" cx="53" cy="41" rx="4.5" ry="3"/></g>
    <rect className="pet-mouth" x="31" y="41" width="10" height="5" rx="4" />
    <path className="pet-arm" d="M57 43q8 1 6 10" fill="none" stroke={id === "nimbus" ? mint : id === "pip" ? peach : lavender} strokeWidth="5" strokeLinecap="round" />
  </svg>;
}
