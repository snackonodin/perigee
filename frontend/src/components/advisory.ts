/**
 * Plain-language wording for the context engine's advisory.
 *
 * The engine (waiwai1/engine/api.py) names a pattern ("Steady", "Body Signal First",
 * "Mind Signal First", "Converging Signals") and puts it in the headline as a
 * "[PATTERN] Recovery Advisory" tag and in the message as "classified as <pattern>".
 * Those are engine codes, not words for a person. We swap only the code and keep
 * the rest of the engine text unchanged.
 */
const PATTERN_TITLE: Record<string, string> = {
  "steady": "Close to your usual: a recovery note",
  "body signal first": "Body signals first: a recovery note",
  "mind signal first": "Mind signals first: a recovery note",
  "converging signals": "Body and mind signals together: a recovery note",
};
const PATTERN_PHRASE: Record<string, string> = {
  "steady": "is close to your usual",
  "body signal first": "shows body signals changing first",
  "mind signal first": "shows check-in signals changing first",
  "converging signals": "shows body and check-in signals changing together",
};
const TAG = /^\s*\[([^\]]+)\]\s*(.*)$/;

export function plainHeadline(headline?: string | null): string | undefined {
  if (!headline) return undefined;
  const m = TAG.exec(headline);
  if (!m) return headline;
  const code = m[1].trim().toLowerCase();
  return PATTERN_TITLE[code] ?? (m[2].trim() || headline);
}

export function plainMessage(message?: string | null): string | undefined {
  if (!message) return undefined;
  return message.replace(/is classified as ([a-z ]+?)(?=[;,.]|$)/i, (whole, code: string) =>
    PATTERN_PHRASE[code.trim().toLowerCase()] ?? whole);
}
