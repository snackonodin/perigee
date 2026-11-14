import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import type { Instrument } from "../api/types";
import { instruments, me, phq9, responseOut, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const OPTIONS = [1, 2, 3, 4, 5].map((value) => ({ value, label: `Option ${value}` }));
// Two modules of two statements keep the walk-through short; the real bank is 10 x 6.
const psyche60: Instrument = {
  id: "psyche60",
  name: "Perigee psyche questions (60 items)",
  version: "1.0",
  timeframe: "How true is each statement of you, in general?",
  items: [
    { key: "psyche_1", module: "m1", text: "My mind keeps running background simulations.", options: OPTIONS },
    { key: "psyche_2", module: "m1", text: "I replay conversations at night.", options: OPTIONS },
    { key: "psyche_7", module: "m2", text: "I notice how the crew feels.", options: OPTIONS },
    { key: "psyche_8", module: "m2", text: "I can step back from strong feelings.", options: OPTIONS },
  ],
};
const ADVICE = [
  { tag: "rumination_sleep_spill", text: "Before lights-out, try a 3-minute open-loop brain dump." },
  { tag: "env_or_somatic_check", text: "Do a quick body and room check." },
];
const EMPTY = { available: false, source: null, updated_at: null, traits: {}, persona_matrix: null, style: {}, advice: [] };
const taken = (style: Record<string, boolean> = {}, advice = ADVICE) => ({
  available: true, source: "psyche60", updated_at: "2026-11-15T10:00:00Z", traits: {},
  persona_matrix: { stability_score: 14.5, agency_score: 9.25, quadrant_name: "Steady Anchor" }, style, advice,
});

let persona: ReturnType<typeof taken> | typeof EMPTY;
let api: ReturnType<typeof mockApi>;
beforeEach(() => {
  signIn();
  persona = EMPTY;
  api = mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/nights": { body: [] },
    "GET /api/v1/checkins": { body: [] },
    "GET /api/v1/persona": () => ({ body: persona }),
    "GET /api/v1/instruments": { body: [...instruments, { id: "psyche60", name: psyche60.name, version: "1.0", items: 60 }, { id: "mini_ipip", name: "Mini-IPIP", version: "1.0", items: 20 }] },
    "GET /api/v1/instruments/psyche60": { body: psyche60 },
    "GET /api/v1/instruments/phq9": { body: phq9 },
    "POST /api/v1/responses": (c) => {
      if ((c.body as { instrument_id: string }).instrument_id === "psyche60") persona = taken();
      return { body: responseOut({ total: 5 }) };
    },
  });
});

describe("Persona: psyche60", () => {
  it("offers the questions, pages them by module, then shows the quadrant and advice with no numbers", async () => {
    render(<App initialPath="/persona" />);
    fireEvent.click(await screen.findByRole("button", { name: "Take the persona questions (about 8 min)" }));
    const form = await screen.findByRole("form", { name: "Persona questions" });
    expect(within(form).getByRole("status").textContent).toMatch(/Page 1 of 2/);
    expect(within(form).getAllByRole("group")).toHaveLength(2);
    // a page needs every statement answered
    fireEvent.click(within(form).getAllByRole("radio", { name: "Option 4" })[0]);
    fireEvent.click(within(form).getByRole("button", { name: /Next/ }));
    expect(screen.getByRole("alert").textContent).toMatch(/each statement/);
    fireEvent.click(within(form).getAllByRole("radio", { name: "Option 2" })[1]);
    fireEvent.click(within(form).getByRole("button", { name: /Next/ }));
    expect(within(form).getByRole("status").textContent).toMatch(/Page 2 of 2/);
    within(form).getAllByRole("radio", { name: "Option 3" }).forEach((r) => fireEvent.click(r));
    fireEvent.click(within(form).getByRole("button", { name: "See my persona" }));

    expect(await screen.findByRole("heading", { name: "Steady Anchor" })).toBeTruthy();
    const sent = api.called("POST /api/v1/responses")[0].body as { instrument_id: string; answers: Record<string, number> };
    expect(sent).toMatchObject({ instrument_id: "psyche60", answers: { psyche_1: 4, psyche_2: 2, psyche_7: 3, psyche_8: 3 } });
    expect(screen.getByRole("img", { name: /Steady Anchor/ })).toBeTruthy();
    expect(screen.getByText(ADVICE[0].text)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retake the persona questions" })).toBeTruthy();
    // nothing numeric from the persona: no axis scores, no totals
    const page = document.querySelector(".persona-page")!.textContent!;
    expect(page.replace(ADVICE[0].text, "")).not.toMatch(/\d/);
  });

  it("renders advice as a numbered checklist when the person prefers structure", async () => {
    persona = taken({ structured_checklist_mode: true });
    render(<App initialPath="/persona" />);
    const list = await screen.findByRole("list");
    expect(list.tagName).toBe("OL");
    expect(within(list).getAllByRole("listitem")).toHaveLength(2);
  });

  it("shows advice on Today under the hero, and none when the list is empty", async () => {
    persona = taken();
    const { unmount } = render(<App initialPath="/" />);
    expect(await screen.findByText(ADVICE[1].text)).toBeTruthy();
    unmount();
    persona = taken({}, []);
    render(<App initialPath="/" />);
    await screen.findByRole("heading", { name: "Today" });
    await waitFor(() => expect(api.called("GET /api/v1/persona").length).toBeGreaterThan(1));
    expect(screen.queryByRole("heading", { name: "For the next day or two" })).toBeNull();
  });

  it("calm tone turns red off app-wide; baseline framing changes the wording", async () => {
    persona = taken({ calm_non_alarming_tone: true, baseline_only_framing: true });
    render(<App initialPath="/" />);
    await waitFor(() => expect(document.documentElement.dataset.calm).toBe("true"));
    expect((await screen.findAllByText("Compared with your usual")).length).toBeGreaterThan(0);
  });

  it("fetches advice again right after a check-in is saved", async () => {
    render(<App initialPath="/checkin?instrument=phq9" />);
    const form = await screen.findByRole("form", { name: "Mood, nine questions" });
    const before = api.called("GET /api/v1/persona").length;
    fireEvent.click(within(form).getAllByRole("radio")[0]);
    fireEvent.click(within(form).getByRole("button", { name: "Next" }));
    fireEvent.click(within(form).getAllByRole("radio")[0]);
    fireEvent.click(within(form).getByRole("button", { name: "Send check-in" }));
    await screen.findByText("Saved. Thank you.");
    await waitFor(() => expect(api.called("GET /api/v1/persona").length).toBe(before + 1));
  });

  it("is not offered as a check-in, and the old Mini-IPIP is gone", async () => {
    render(<App initialPath="/checkin" />);
    await screen.findAllByText("Mood, nine questions");
    await waitFor(() => expect(screen.queryByText(/Mini-IPIP|Persona questions|psyche/i)).toBeNull());
  });
});
