// Layout of the daily "Body & cabin" check-in (instrument body_cabin) inside CheckinForm:
// page 1 the three red flags, page 2 the symptoms grouped by item.group as Yes/No chips,
// page 3 exercise minutes and effort, page 4 the two friction sliders.
import type { InstrumentItem } from "../api/types";

export const BODY_CABIN = "body_cabin";
const PAGE: Record<string, string> = { red_flag: "red", cabin: "sym", gravity: "sym", general: "sym", immune: "sym", exercise: "ex", friction: "fr" };
const SECTION: Record<string, string> = { cabin: "Cabin air", gravity: "Gravity", general: "General", immune: "Immune-like" };

export const bodyCabinLayout = {
  groupBy: (i: InstrumentItem) => PAGE[i.group ?? ""] ?? i.key,
  sectionOf: (i: InstrumentItem) => SECTION[i.group ?? ""],
  control: (i: InstrumentItem): "chips" | "slider" => (i.group === "friction" || i.options.length > 6 ? "slider" : "chips"),
};
