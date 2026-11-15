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
const part = (n: number): Instrument & { part: { index: number; of: number; blurb: string } } => ({
  id: `psyche_p${n}`, name: `Psyche questions, part ${n} of 5`, version: "1.0", timeframe: "How true is each statement of you, in general?",
  part: { index: n, of: 5, blurb: `Blurb for part ${n}` },
  items: Array.from({ length: 12 }, (_, i) => ({ key: `psyche_${(n - 1) * 12 + i + 1}`, text: `Statement ${(n - 1) * 12 + i + 1}`, options: OPTIONS })),
});
const PART_ROUTES = Object.fromEntries([1, 2, 3, 4, 5].map((n) => [`GET /api/v1/instruments/psyche_p${n}`, { body: part(n) }]));
const ADVICE = [
  { tag: "rumination_sleep_spill", text: "Before lights-out, try a 3-minute open-loop brain dump." },
  { tag: "env_or_somatic_check", text: "Do a quick body and room check." },
];
const EMPTY = { available: false, source: null, updated_at: null, traits: {}, persona_matrix: null, style: {}, advice: [],
  progress: { done: ["psyche_p2", "psyche_p4"], total: 5, answers_kept: true } };
const taken = (style: Record<string, boolean> = {}, advice = ADVICE) => ({
  available: true, source: "psyche60", updated_at: "2026-11-15T10:00:00Z", traits: {},
  persona_matrix: { stability_score: 14.5, agency_score: 9.25, quadrant_name: "Steady Anchor" }, style, advice,
  progress: { done: ["psyche_p1", "psyche_p2", "psyche_p3", "psyche_p4", "psyche_p5"], total: 5, answers_kept: true },
});

let persona: ReturnType<typeof taken> | typeof EMPTY;
const order = () => [...document.querySelectorAll("form fieldset legend")].map((l) => l.textContent);
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
    "GET /api/v1/instruments": { body: [...instruments, { id: "psyche60", name: psyche60.name, version: "1.0", items: 60 }, { id: "mini_ipip", name: "Mini-IPIP", version: "1.0", items: 20 },
      ...[1, 2, 3, 4, 5].map((n) => ({ id: `psyche_p${n}`, name: `Psyche questions, part ${n} of 5: Mind at rest`, version: "1.0", items: 12 }))] },
    "GET /api/v1/instruments/psyche60": { body: psyche60 },
    ...PART_ROUTES,
    "GET /api/v1/instruments/phq9": { body: phq9 },
    "POST /api/v1/responses": (c) => {
      const id = (c.body as { instrument_id: string }).instrument_id;
      if (id.startsWith("psyche_p")) persona = { ...EMPTY, progress: { ...EMPTY.progress, done: [...EMPTY.progress.done, id] } };
      return { body: responseOut({ total: 5 }) };
    },
  });
});

describe("Persona: psyche60", () => {
  it("shows five part cards with blurbs, ticks for done parts and the suggested next part first", async () => {
    render(<App initialPath="/persona" />);
    expect(await screen.findByText("2 of 5 parts done")).toBeTruthy();
    const cards = await screen.findAllByRole("listitem");
    expect(cards.map((c) => c.querySelector("strong")!.textContent)).toEqual(
      ["Mind at rest", "✓ Feelings and reactions", "People and authority", "✓ Focus and motivation", "Body and feedback"]);
    expect(cards[0].textContent).toMatch(/suggested next/);
    await waitFor(() => expect(cards[0].textContent).toMatch("Blurb for part 1"));
    expect(cards[0].textContent).toMatch("~1.5 min");
    expect(within(cards[1]).getByRole("button", { name: /Retake/ })).toBeTruthy();
    expect(screen.queryByText(/allow keeping questionnaire answers/)).toBeNull();
  });

  it("a part is 12 shuffled statements, four per page, in the same order after a reload; then 'Part n of 5 done'", async () => {
    const { unmount } = render(<App initialPath="/persona" />);
    fireEvent.click(await screen.findByRole("button", { name: "Start Mind at rest" }));
    const form = await screen.findByRole("form", { name: "Mind at rest" });
    expect(within(form).getByRole("status").textContent).toMatch(/Page 1 of 3/);
    expect(within(form).getAllByRole("group")).toHaveLength(4);
    const first = order();
    expect(first).not.toEqual(["Statement 1", "Statement 2", "Statement 3", "Statement 4"]);
    unmount();
    render(<App initialPath="/persona" />);
    fireEvent.click(await screen.findByRole("button", { name: "Start Mind at rest" }));
    const again = await screen.findByRole("form", { name: "Mind at rest" });
    expect(order()).toEqual(first);
    for (let p = 0; p < 3; p++) {
      within(again).getAllByRole("radio", { name: "Option 3" }).forEach((r) => fireEvent.click(r));
      fireEvent.click(within(again).getByRole("button", { name: p < 2 ? /Next/ : "Finish this part" }));
    }
    expect(await screen.findByRole("heading", { name: "Part 3 of 5 done" })).toBeTruthy();
    const sent = api.called("POST /api/v1/responses")[0].body as { instrument_id: string; answers: Record<string, number> };
    expect(sent.instrument_id).toBe("psyche_p1");
    expect(Object.keys(sent.answers)).toHaveLength(12);
    expect(screen.getByRole("button", { name: "Next part: People and authority" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Later" }));
    expect(await screen.findByText("3 of 5 parts done")).toBeTruthy();
  });

  it("asks for answer-keeping consent when parts cannot be combined", async () => {
    persona = { ...EMPTY, progress: { ...EMPTY.progress, answers_kept: false } };
    render(<App initialPath="/persona" />);
    expect(await screen.findByText("To combine your parts, allow keeping questionnaire answers in Settings → Consent.")).toBeTruthy();
  });

  it("with all five parts the persona shows: quadrant, plane and advice, no numbers, and the parts to retake", async () => {
    persona = taken();
    render(<App initialPath="/persona" />);
    expect(await screen.findByRole("heading", { name: "Steady Anchor" })).toBeTruthy();
    expect(screen.getByRole("img", { name: /Steady Anchor/ })).toBeTruthy();
    expect(screen.getByText(ADVICE[0].text)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Your five parts" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^Retake/ })).toHaveLength(5);
    const quadrant = document.querySelector(".persona-quadrant-panel")!.textContent!;
    expect(quadrant).not.toMatch(/\d/);
  });

  it("with a profile draws the five-part radar: labels, words-only accessible name, no numbers", async () => {
    const PROFILE = [
      { key: "mind_at_rest", label: "Mind at rest", level: 0.82 },
      { key: "feelings", label: "Feelings and reactions", level: 0.5 },
      { key: "people", label: "People and authority", level: 0.1 },
      { key: "focus", label: "Focus and motivation", level: 0.66 },
      { key: "body_feedback", label: "Body and feedback", level: 0.34 },
    ];
    persona = { ...taken(), profile: PROFILE } as ReturnType<typeof taken>;
    render(<App initialPath="/persona" />);
    const radar = await screen.findByRole("img", { name: /tendency shape/ });
    const name = radar.getAttribute("aria-label")!;
    expect(name).toBe("Your tendency shape across the five parts: Mind at rest, higher; Feelings and reactions, middle; "
      + "People and authority, lower; Focus and motivation, middle; Body and feedback, middle.");
    expect(name).not.toMatch(/\d/);
    expect([...radar.querySelectorAll(".radar-label")].map((l) => l.textContent)).toEqual(PROFILE.map((a) => a.label));
    expect(radar.querySelectorAll(".radar-ring")).toHaveLength(3);
    expect(radar.querySelectorAll(".radar-dot")).toHaveLength(5);
    expect(radar.querySelector(".radar-shape.grow")).toBeNull(); // no motion in tests / reduced motion
    expect(screen.getByText("No shape is better than another.")).toBeTruthy();
    const panel = document.querySelector(".persona-quadrant-panel")!.textContent!;
    expect(panel).not.toMatch(/\d/);
  });

  it("shows no radar before the profile exists", async () => {
    persona = { ...taken(), profile: [] } as ReturnType<typeof taken>;
    render(<App initialPath="/persona" />);
    expect(await screen.findByRole("heading", { name: "Steady Anchor" })).toBeTruthy();
    expect(screen.queryByRole("img", { name: /tendency shape/ })).toBeNull();
    expect(screen.queryByText("No shape is better than another.")).toBeNull();
  });

  it("renders advice as a numbered checklist when the person prefers structure", async () => {
    persona = taken({ structured_checklist_mode: true });
    render(<App initialPath="/persona" />);
    const list = within((await screen.findByRole("heading", { name: "For the next day or two" })).closest("section")!).getByRole("list");
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
    await waitFor(() => expect(screen.queryByText(/Mini-IPIP|Persona questions|psyche|Mind at rest/i)).toBeNull());
  });
});
