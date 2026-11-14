import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import type { Instrument } from "../api/types";
import { instruments, me, responseOut, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const OPTIONS = [1, 2, 3, 4, 5].map((value) => ({ value, label: `Option ${value}` }));
// Two items keep the walk-through short; the real instrument has 20.
const miniIpip: Instrument = {
  id: "mini_ipip",
  name: "Mini-IPIP personality questions (20 items)",
  version: "1.0",
  timeframe: "Describe yourself as you generally are now, not as you wish to be in the future.",
  items: [
    { key: "mini_ipip_1", text: "Am the life of the party.", options: OPTIONS },
    { key: "mini_ipip_2", text: "Sympathize with others' feelings.", options: OPTIONS },
  ],
};
const EMPTY = { available: false, source: null, updated_at: null, traits: {}, persona_matrix: null };
const TAKEN = {
  available: true, source: "mini_ipip", updated_at: "2026-11-14T14:00:00Z",
  traits: { E: 12, A: 17, C: 18, N: 9, O: 16 },
  persona_matrix: { stability_score: 14, agency_score: 13, quadrant_name: "Autonomous Pioneer" },
};

let persona: typeof EMPTY | typeof TAKEN;
let api: ReturnType<typeof mockApi>;
beforeEach(() => {
  signIn();
  persona = EMPTY;
  api = mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/checkins": { body: [] },
    "GET /api/v1/persona": () => ({ body: persona }),
    "GET /api/v1/instruments": { body: [...instruments, { id: "mini_ipip", name: miniIpip.name, version: "1.0", items: 20 }] },
    "GET /api/v1/instruments/mini_ipip": { body: miniIpip },
    "POST /api/v1/responses": () => { persona = TAKEN; return { body: responseOut({ total: 5 }) }; },
  });
});

describe("Persona: personality questions", () => {
  it("offers the questions when no traits exist, sends them, then shows traits and the quadrant", async () => {
    render(<App initialPath="/persona" />);
    fireEvent.click(await screen.findByRole("button", { name: "Take the personality questions (2 min)" }));
    expect(await screen.findByText(miniIpip.timeframe!)).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Option 4"));
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    fireEvent.click(await screen.findByLabelText("Option 2"));
    fireEvent.click(screen.getByRole("button", { name: "See my traits" }));
    expect(await screen.findByText("Autonomous Pioneer")).toBeTruthy();
    const sent = api.called("POST /api/v1/responses")[0].body as { instrument_id: string; answers: Record<string, number> };
    expect(sent.instrument_id).toBe("mini_ipip");
    expect(sent.answers).toEqual({ mini_ipip_1: 4, mini_ipip_2: 2 });
    expect(screen.getByRole("button", { name: "Retake the personality questions" })).toBeTruthy();
    expect(screen.queryByText(/Total score/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Take the personality questions (2 min)" })).toBeNull();
  });

  it("is not offered as a check-in", async () => {
    render(<App initialPath="/checkin" />);
    await screen.findAllByText("Mood, nine questions");
    await waitFor(() => expect(screen.queryByText(/Mini-IPIP|personality/i)).toBeNull());
  });
});
