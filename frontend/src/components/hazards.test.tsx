import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import type { Instrument } from "../api/types";
import { instruments, me, night, responseOut, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const YN = [{ value: 0, label: "No" }, { value: 1, label: "Yes" }];
const RED = { min_value: 1, reason: "severe_symptom" };
const MEDICAL = /severe physical symptom/;
// A short body_cabin: the real one has 3 red flags, 11 symptoms, exercise and 2 friction items.
const bodyCabin: Instrument = {
  id: "body_cabin", name: "Body and cabin check-in", version: "1.0", timeframe: "Today.",
  items: [
    { key: "red_chest", group: "red_flag", text: "Sudden severe chest pain right now", options: YN, safety_trigger: RED },
    { key: "red_faint", group: "red_flag", text: "Fainting, or nearly fainting, today", options: YN, safety_trigger: RED },
    { key: "red_breath", group: "red_flag", text: "Severe breathlessness right now", options: YN, safety_trigger: RED },
    { key: "sym_headache", group: "cabin", text: "Headache", options: YN },
    { key: "sym_throat", group: "immune", text: "Sore throat", options: YN },
    { key: "exercise_min", group: "exercise", text: "Exercise today (minutes)", options: [{ value: 0, label: "None" }, { value: 30, label: "About 30" }] },
    { key: "exercise_effort", group: "exercise", text: "How hard was that exercise overall?", options: Array.from({ length: 11 }, (_, i) => ({ value: i, label: `Effort ${i}` })) },
    { key: "friction_crew", group: "friction", text: "Friction within the crew today", options: ["None", "A little", "Some", "A lot", "Very much"].map((label, value) => ({ value, label })) },
  ],
};
const HIGH_CABIN = { date: "2026-11-10", ppco2_mmhg: 3.26, temp_c: 22.4, rh_pct: 50, level: "high" };
const TAGS = [
  { kind: "cabin_co2", text: "Cabin ppCO₂ 3.3 mmHg that night: check the airflow near the bunk." },
  { kind: "symptoms", text: "Body symptoms logged: headache, stuffiness." },
  { kind: "immune", text: "A third tag that must not show." },
];

let api: ReturnType<typeof mockApi>;
function setup(extra: Record<string, unknown> = {}, todayOver: Record<string, unknown> = {}) {
  signIn();
  api = mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: { ...today, ...todayOver } },
    "GET /api/v1/nights": { body: [] },
    "GET /api/v1/checkins": { body: [] },
    "GET /api/v1/instruments": { body: [...instruments, { id: "body_cabin", name: bodyCabin.name, version: "1.0", items: 19 }] },
    "GET /api/v1/instruments/body_cabin": { body: bodyCabin },
    "POST /api/v1/responses": { body: responseOut() },
    ...extra,
  });
}
const form = () => screen.findByRole("form", { name: "Body & cabin" });
const answer = (f: HTMLElement, text: string, label: string) =>
  fireEvent.click(within(within(f).getByRole("group", { name: text })).getByRole("radio", { name: label }));

describe("Body & cabin check-in", () => {
  beforeEach(() => localStorage.setItem("pet.firstRunDone", "true"));

  it("is listed with the daily check-ins", async () => {
    setup();
    render(<App initialPath="/checkin" />);
    expect(await screen.findByText("Body & cabin")).toBeTruthy();
  });

  it("red flags first, then grouped symptom chips, exercise, then a friction slider; sends every answer", async () => {
    setup();
    render(<App initialPath="/checkin?instrument=body_cabin" />);
    const f = await form();
    expect(within(f).getAllByRole("group").map((g) => g.querySelector("legend")!.textContent)).toEqual(
      ["Sudden severe chest pain right now", "Fainting, or nearly fainting, today", "Severe breathlessness right now"]);
    for (const t of ["Sudden severe chest pain right now", "Fainting, or nearly fainting, today", "Severe breathlessness right now"]) answer(f, t, "No");
    fireEvent.click(within(f).getByRole("button", { name: /Next/ }));
    expect(within(f).getByRole("heading", { name: "Cabin air" })).toBeTruthy();
    expect(within(f).getByRole("heading", { name: "Immune-like" })).toBeTruthy();
    answer(f, "Headache", "Yes"); answer(f, "Sore throat", "No");
    fireEvent.click(within(f).getByRole("button", { name: /Next/ }));
    answer(f, "Exercise today (minutes)", "About 30");
    fireEvent.change(within(f).getByRole("slider", { name: /How hard/ }), { target: { value: "6" } });
    fireEvent.click(within(f).getByRole("button", { name: /Next/ }));
    expect((within(f).getByRole("slider", { name: /Friction within the crew/ }) as HTMLInputElement).value).toBe("0");
    fireEvent.click(within(f).getByRole("button", { name: "Send check-in" }));
    await screen.findByText("Saved. Thank you.");
    expect(api.called("POST /api/v1/responses")[0].body).toMatchObject({ instrument_id: "body_cabin", answers: {
      red_chest: 0, red_faint: 0, red_breath: 0, sym_headache: 1, sym_throat: 0, exercise_min: 30, exercise_effort: 6, friction_crew: 0 } });
  });

  it("a red-flag Yes opens the safety screen at once, with the medical reason", async () => {
    setup();
    render(<App initialPath="/checkin?instrument=body_cabin" />);
    answer(await form(), "Fainting, or nearly fainting, today", "Yes");
    expect((await screen.findByRole("alertdialog")).textContent).toMatch(MEDICAL);
  });

  it("the server's crisis result shows the existing safety screen with the server's reason", async () => {
    setup({ "POST /api/v1/responses": { body: responseOut({ crisis: true, safety_screen_required: true, safety: { show: true, reason: "Server medical reason.", resources: ["Call your flight surgeon"] } }) } });
    render(<App initialPath="/checkin?instrument=body_cabin" />);
    const f = await form();
    for (const t of ["Sudden severe chest pain right now", "Fainting, or nearly fainting, today", "Severe breathlessness right now"]) answer(f, t, "No");
    fireEvent.click(within(f).getByRole("button", { name: /Next/ }));
    answer(f, "Headache", "No"); answer(f, "Sore throat", "No");
    fireEvent.click(within(f).getByRole("button", { name: /Next/ }));
    answer(f, "Exercise today (minutes)", "None");
    fireEvent.click(within(f).getByRole("button", { name: /Next/ }));
    fireEvent.click(within(f).getByRole("button", { name: "Send check-in" }));
    expect((await screen.findByRole("alertdialog")).textContent).toMatch("Server medical reason.");
  });

  it("the pet's OPEN_MEDICAL_HELP_NOW opens the same safety screen", async () => {
    setup({ "GET /api/v1/pet/bubble": { body: { id: "safety_severe_somatic", voice: "unmodulated", badge: "medical", playful: false, pet_animation: "calm_alert", bubble: "Get medical help right away.", micro_try: null, ui_action: "OPEN_MEDICAL_HELP_NOW", disclaimer: null } } });
    render(<App initialPath="/" />);
    expect((await screen.findByRole("alertdialog")).textContent).toMatch(MEDICAL);
  });
});

describe("spaceflight context on Today, Body and Briefing", () => {
  beforeEach(() => localStorage.setItem("pet.firstRunDone", "true"));

  it("Today: at most two calm tags and a cabin line under the breathing reading, the status still shown", async () => {
    setup({}, { cabin: HIGH_CABIN, context_tags: TAGS });
    render(<App initialPath="/" />);
    const card = (await screen.findByRole("heading", { name: "Breathing" })).closest("article")!;
    expect(within(card).getAllByRole("listitem").map((l) => l.textContent)).toEqual([TAGS[0].text, TAGS[1].text]);
    expect(card.textContent).toMatch("Cabin air: high · ppCO₂ 3.3 mmHg");
    expect(card.querySelector(".status-chip")).toBeTruthy();
  });

  it("Body: cabin high is amber 'High' with the readings; no reading says no sensor", async () => {
    setup({}, { cabin: HIGH_CABIN });
    const { unmount } = render(<App initialPath="/body" />);
    expect(await screen.findByRole("button", { name: "Cabin: High, ppCO₂ 3.3 mmHg · 22.4 °C · 50 %" })).toBeTruthy();
    unmount();
    setup({}, { cabin: { ...HIGH_CABIN, level: "no_reading", ppco2_mmhg: null, temp_c: null, rh_pct: null } });
    render(<App initialPath="/body" />);
    expect(await screen.findByRole("button", { name: "Cabin: No reading, No cabin sensor connected." })).toBeTruthy();
  });

  it("Briefing: the last-night card adds the cabin air", async () => {
    setup({}, { cabin: HIGH_CABIN, latest_night: night("2026-11-10", 17.9) });
    render(<App initialPath="/briefing" />);
    await waitFor(() => expect(document.querySelector(".briefing-cabin")?.textContent).toBe("Cabin air that night: high · ppCO₂ 3.3 mmHg"));
  });
});
