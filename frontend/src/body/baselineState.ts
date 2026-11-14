// Baseline-relative state of a body system for the latest night, from data the API already
// returns. The cut-off is the engine's own (flag components.alert_robust_z, from config); the
// frontend never invents one and never shows z or the numbers behind it.
//   changed: the latest night's flag has |z| >= alert_robust_z for any of the features
//   usual:   the latest night is valid, the first feature's baseline is past warm-up and has
//            nothing over the cut-off
//   none:    otherwise (warm-up, skipped, no valid latest night, no cut-off)
import type { TodayOut } from "../api/types";

export type BaselineState = "usual" | "changed" | "none";
interface Component { z?: number | null; skipped?: string | null }

export function baselineState(today: Pick<TodayOut, "latest_night" | "flags" | "baselines">, features: readonly string[]): BaselineState {
  const night = today.latest_night;
  if (!night?.valid) return "none";
  const flag = today.flags.find((f) => ((f.components as { night_date?: string }).night_date ?? f.date) === night.date);
  const comps = flag?.components as { alert_robust_z?: number; physiology?: Record<string, Component> } | undefined;
  const cut = comps?.alert_robust_z;
  const parts = features.map((k) => comps?.physiology?.[k]);
  if (typeof cut === "number" && parts.some((c) => typeof c?.z === "number" && Math.abs(c.z) >= cut)) return "changed";
  if (parts.some((c) => c?.skipped)) return "none";
  const base = today.baselines.find((b) => b.feature === features[0]);
  if (!base || base.maturity === "warm_up") return "none";
  // a flag exists for this night but carries no cut-off: we cannot say "usual"
  if (flag && typeof cut !== "number") return "none";
  return "usual";
}
