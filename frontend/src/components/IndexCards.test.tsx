import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import type { components } from "../api/schema";
import { instruments, me } from "../test/fixtures";
import { type Call, mockApi, signIn } from "../test/mockApi";
import { IndexCards, lastMondays, mondayOf } from "./IndexCards";

type IndicesOut = components["schemas"]["IndicesOut"];

const NOW = Date.parse("2026-11-12T10:00:00Z"); // a Thursday
const PHQ2_SOURCE = "Kroenke 2003. Alert basis: score >=3 is the published positive-screen cut-off.";

// Three weeks of data out of eight; the week of 2026-10-26 is missing (a gap in the trend).
const BY_WEEK: Record<string, IndicesOut["indices"]> = {
  "2026-10-19": { who5: { value: 72, band: "above screening cutoff", band_alert: false, direction: -1 } },
  "2026-11-02": {
    who5: { value: 64, band: "above screening cutoff", band_alert: false, direction: -1 },
    phq2: { value: 2, band: "below screening cutoff", band_alert: false, direction: 1 },
  },
  "2026-11-09": {
    who5: { value: 60, band: "above screening cutoff", band_alert: false, direction: -1 },
    phq2: { value: 3, band: "at or above screening cutoff", band_alert: true, direction: 1 },
    "daily_pm.stress": { value: 2.5, band: null, band_alert: false, direction: 1 },
  },
};

const NAMES = [
  ...instruments,
  { id: "phq2", name: "Patient Health Questionnaire-2 (PHQ-2)", version: "1.0", items: 2 },
  { id: "who5", name: "WHO-Five Well-Being Index (WHO-5)", version: "1.0", items: 5 },
  { id: "daily_pm", name: "Evening check-in", version: "1.0", items: 3 },
];

function indices(c: Call) {
  const week = c.query.get("week")!;
  return { body: { week_start: week, indices: BY_WEEK[week] ?? {}, run_id: null } };
}

let api: ReturnType<typeof mockApi>;
beforeEach(() => {
  signIn();
  api = mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/checkins": { body: [] },
    "GET /api/v1/indices": indices,
    "GET /api/v1/instruments": { body: NAMES },
    "GET /api/v1/instruments/phq2": {
      body: { id: "phq2", name: "PHQ-2", version: "1.0", items: [], scoring: { ranges_source: PHQ2_SOURCE } },
    },
  });
});

function card(name: RegExp | string) {
  return screen.getByRole("article", { name });
}

describe("week maths", () => {
  it("mondayOf gives the ISO-week Monday in UTC", () => {
    expect(mondayOf(NOW)).toBe("2026-11-09");
    expect(mondayOf(Date.parse("2026-11-09T00:00:00Z"))).toBe("2026-11-09");
    expect(mondayOf(Date.parse("2026-11-15T23:59:59Z"))).toBe("2026-11-09"); // Sunday
  });

  it("lastMondays is oldest-first and ends with the current week", () => {
    expect(lastMondays(3, NOW)).toEqual(["2026-10-26", "2026-11-02", "2026-11-09"]);
  });
});

describe("IndexCards", () => {
  it("asks /indices once per week for the last 8 weeks", async () => {
    render(<IndexCards instruments={NAMES} now={NOW} />);
    await screen.findByRole("article", { name: /Mood, two questions/ });
    const weeks = api.called("GET /api/v1/indices").map((c) => c.query.get("week"));
    expect(weeks).toEqual(lastMondays(8, NOW));
    expect(weeks.at(-1)).toBe("2026-11-09");
  });

  it("shows value, band and direction, with a cited band-alert badge only when band_alert", async () => {
    render(<IndexCards instruments={NAMES} now={NOW} />);
    const phq2 = await screen.findByRole("article", { name: /Mood, two questions/ });
    expect(within(phq2).getByText("3")).toBeTruthy();
    expect(within(phq2).getByText("at or above screening cutoff")).toBeTruthy();
    expect(within(phq2).getByText("higher is worse")).toBeTruthy();
    expect(within(phq2).getByText("band alert")).toBeTruthy();
    fireEvent.click(within(phq2).getByText("Why this badge"));
    expect(await within(phq2).findByText(`Source: ${PHQ2_SOURCE}`)).toBeTruthy();
    expect(within(phq2).getByText(/not a diagnosis/)).toBeTruthy();

    const who5 = card(/Wellbeing, five questions/);
    expect(within(who5).getByText("60 %")).toBeTruthy();
    expect(within(who5).getByText("higher is better")).toBeTruthy();
    expect(within(who5).queryByText("band alert")).toBeNull();
  });

  it("labels check-in items and shows no band for them", async () => {
    render(<IndexCards instruments={NAMES} now={NOW} />);
    const stress = await screen.findByRole("article", { name: "Evening check-in · stress" });
    expect(within(stress).getByText("2.5")).toBeTruthy();
    expect(within(stress).getByText("no band (check-in item)")).toBeTruthy();
    expect(within(stress).getByText("higher is worse")).toBeTruthy();
  });

  it("shows the latest week and connects only consecutive weeks with data", async () => {
    render(<IndexCards instruments={NAMES} now={NOW} />);
    const who5 = await screen.findByRole("article", { name: /Wellbeing, five questions/ });
    const svg = within(who5).getByRole("img", { name: /last 8 weeks/ });
    expect(svg.querySelectorAll("circle")).toHaveLength(1);
    expect(svg.querySelector("circle title")?.textContent).toBe("Latest week of 2026-11-09: 60.0");
    // 2026-10-19 stands alone (2026-10-26 is missing); only Nov 2 → Nov 9 is connected.
    expect(svg.querySelectorAll("polyline")).toHaveLength(1);
  });

  it("an index with no value this week says so and shows no badge", async () => {
    BY_WEEK["2026-11-09"] = { who5: BY_WEEK["2026-11-09"].who5 };
    try {
      render(<IndexCards instruments={NAMES} now={NOW} />);
      const phq2 = await screen.findByRole("article", { name: /Mood, two questions/ });
      expect(within(phq2).getByText("no data this week")).toBeTruthy();
      expect(within(phq2).queryByText("band alert")).toBeNull();
      expect(within(phq2).getByText("higher is worse")).toBeTruthy(); // from an earlier week
    } finally {
      BY_WEEK["2026-11-09"] = {
        who5: { value: 60, band: "above screening cutoff", band_alert: false, direction: -1 },
        phq2: { value: 3, band: "at or above screening cutoff", band_alert: true, direction: 1 },
        "daily_pm.stress": { value: 2.5, band: null, band_alert: false, direction: 1 },
      };
    }
  });

  it("empty state when there is no data in any week", async () => {
    api = mockApi({ "GET /api/v1/indices": { body: { week_start: "x", indices: {}, run_id: null } } });
    render(<IndexCards instruments={NAMES} now={NOW} />);
    expect(await screen.findByText(/No questionnaires or check-ins in the last 8 weeks/)).toBeTruthy();
  });

  it("an API error shows the shared error state with Retry", async () => {
    api = mockApi({ "GET /api/v1/indices": { status: 500, body: { error: "internal_error", message: "boom" } } });
    render(<IndexCards instruments={NAMES} now={NOW} />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Could not load weekly indices/);
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeTruthy();
  });
});

describe("Psyche page", () => {
  it("keeps weekly patterns available from the Check-in page", async () => {
    render(<App initialPath="/checkin" />);
    expect(await screen.findByRole("heading", { name: "Check-in" })).toBeTruthy();
    fireEvent.click(screen.getByText("Weekly patterns"));
    expect(await screen.findByRole("article", { name: /Mood, two questions/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "More reflections" })).toBeTruthy();
  });
});
