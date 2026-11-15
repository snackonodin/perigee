import seed from "../../../seeds/safety_resources.json";
import type { Instrument } from "../api/types";

export interface SafetyContent {
  reason: string;
  resources: string[];
}

/** Offline fallback, bundled at build time from seeds/safety_resources.json (one source of
 *  truth with the server). Used when a local trigger fires and the server cannot answer. */
export const SAFETY_FALLBACK: SafetyContent = {
  reason: seed.reasons.safety_item,
  resources: [...seed.resources],
};

/** Offline fallback for a specific trigger reason (e.g. "severe_symptom" for a body red flag);
 *  unknown reasons use the safety-item text. */
export function fallbackFor(reason?: string | null): SafetyContent {
  const reasons = seed.reasons as Record<string, string>;
  return { reason: (reason && reasons[reason]) || SAFETY_FALLBACK.reason, resources: [...seed.resources] };
}

/** The acknowledge button stays disabled this long after the screen appears, so a stray or
 *  double click (its second click lands where the button appears) cannot dismiss it unread. */
export const SAFETY_ACK_DELAY_MS = 3000;

/** Local copy of the server rule: any answer >= an item's safety_trigger.min_value. */
export function localSafetyTriggered(inst: Pick<Instrument, "items">, answers: Record<string, number>): boolean {
  return inst.items.some(
    (it) => it.safety_trigger !== undefined && typeof answers[it.key] === "number" && answers[it.key] >= it.safety_trigger.min_value,
  );
}

/** Server result wins; missing pieces fall back to the bundled seed text. */
export function contentFromServer(s: { reason?: string | null; resources?: string[] }): SafetyContent {
  return {
    reason: s.reason || SAFETY_FALLBACK.reason,
    resources: s.resources && s.resources.length ? s.resources : SAFETY_FALLBACK.resources,
  };
}
