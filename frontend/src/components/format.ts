export function fmt(v: number | null | undefined, digits = 1): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "–";
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return "–";
  const d = new Date(iso);
  // Fixed 24 h HH:MM in UTC: the same on every device, whatever its locale.
  return Number.isNaN(d.getTime()) ? "–" : `${d.toISOString().slice(11, 16)} UTC`;
}

export const MATURITY_LABEL: Record<string, string> = {
  warm_up: "warming up",
  widening: "widening",
  mature: "mature",
};
