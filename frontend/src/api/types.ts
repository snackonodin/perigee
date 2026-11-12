import type { components } from "./schema";

type S = components["schemas"];
export type TodayOut = S["TodayOut"];
export type TodayFlagOut = S["TodayFlagOut"];
export type NightOut = S["NightOut"];
export type BaselineOut = S["BaselineOut"];
export type GuidanceCardOut = S["GuidanceCardOut"];
export type PendingCheckin = S["PendingCheckin"];
export type InstrumentSummary = S["InstrumentSummary"];
/** `crisis` was added by the shared API contract after this OpenAPI snapshot. Keep it optional
 * at the client boundary so a missing value can be treated fail-safe. */
export type ResponseOut = S["ResponseOut"] & { crisis?: boolean };
export type SafetyResult = S["SafetyResult"];
export type ConsentOut = S["ConsentOut"];
export type MeOut = S["MeOut"];
export type TokenOut = S["TokenOut"];
export type ErrorOut = S["ErrorOut"];

// GET /instruments/{id} returns the catalog definition untyped (dict[str, Any]); this is
// the shape of seeds/instruments/*.json that the check-in form relies on.
export interface InstrumentOption {
  value: number;
  label: string;
}
export interface InstrumentItem {
  key: string;
  text: string;
  options: InstrumentOption[];
  safety_trigger?: { min_value: number };
}
export interface Instrument {
  id: string;
  name: string;
  version: string;
  timeframe?: string | null;
  items: InstrumentItem[];
}

export const CONSENT_SCOPES = ["checkins", "survey_answers", "raw_csi", "share_summaries"] as const;
export type ConsentScope = (typeof CONSENT_SCOPES)[number];
