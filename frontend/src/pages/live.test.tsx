import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Breathing, Heart } from "./Live";
import { me, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const ev = (event: string, data: object, id?: string) =>
  `${id ? `id: ${id}\n` : ""}event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const window_ = (i: number, over: object = {}) => ({
  session_id: "s1", t_start: `2026-11-11T00:${String(i).padStart(2, "0")}:00Z`, t_end: "x",
  rr_a: 14 + i / 10, rr_b: 14.2, pnr_db: 6.5, quality: 0.83, motion: i === 3, motion_score: i, presence: true, ...over,
});
const heart = (i: number) => ({ session_id: "s1", t_start: `2026-11-11T00:${String(i).padStart(2, "0")}:00Z`, t_end: "x", hr_bpm: 58 + i, quality: 0.6, experimental: true });

function stream(text: string, open = false): Response {
  const body = new ReadableStream({
    start(c) {
      c.enqueue(new TextEncoder().encode(text));
      if (!open) c.close();
    },
  });
  return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
}

const HELLO = ev("hello", { mode: "live", poll_s: 2, heartbeat_s: 15, max_s: 300 });
const SESSIONS = [{ id: "sess-1", user_id: "u-1", start_utc: "2026-11-10T22:00:00Z", end_utc: "2026-11-11T06:00:00Z", source_kind: "synthetic", usable: true }];

function routes(liveText: string, onLive?: (q: URLSearchParams) => void) {
  return {
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/sessions": { body: SESSIONS },
    "GET /api/v1/live/vitals": (c: { query: URLSearchParams }) => {
      onLive?.(c.query);
      return { response: stream(liveText, true) }; // stays open: no reconnect loop in the test
    },
  };
}

describe("Heart (live)", () => {
  it("always shows the EXPERIMENTAL banner, before any data, and never raises alerts", async () => {
    signIn();
    mockApi(routes(HELLO + [1, 2, 3].map((i) => ev("heart", heart(i), `0-${i}`)).join("")));
    render(<Heart />);
    const note = await screen.findByRole("note");
    expect(note.textContent).toMatch(/^EXPERIMENTAL/);
    expect(note.textContent).toMatch(/no\s+thresholds or alerts/);
    expect(await screen.findByText("61")).toBeTruthy(); // latest hr
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("img", { name: "Experimental heart-rate estimate per window" })).toBeTruthy();
  });
});

describe("Breathing (live)", () => {
  it("draws rr_a and a faint rr_b, shows PNR, quality, presence and the motion strip", async () => {
    signIn();
    mockApi(routes(HELLO + [1, 2, 3, 4].map((i) => ev("window", window_(i), `${i}-0`)).join("")));
    const { container } = render(<Breathing />);
    const chart = await screen.findByRole("img", { name: /Breathing rate per window, latest 14\.4/ });
    expect(container.querySelector(".stats .big")?.textContent).toMatch(/^14\.4/); // latest rr_a
    expect(screen.getByText("6.5 dB")).toBeTruthy();
    expect(screen.getByText("In bed")).toBeTruthy();
    expect(chart.querySelector('[data-series="rr_a"]')).toBeTruthy();
    expect(chart.querySelector('[data-series="rr_b"]')?.getAttribute("class")).toBe("trace faint");
    const strip = screen.getByRole("img", { name: /Motion per window/ });
    expect(strip.children).toHaveLength(4);
    expect(strip.querySelectorAll(".flagged")).toHaveLength(1);
  });

  it("shows no breathing value while nobody is in bed", async () => {
    signIn();
    mockApi(routes(HELLO + ev("window", window_(1, { presence: false, rr_a: null, rr_b: null }), "1-0")));
    render(<Breathing />);
    expect(await screen.findByText("Not detected")).toBeTruthy();
  });

  it("Replay demo night streams the chosen session at the chosen speed", async () => {
    signIn();
    const queries: URLSearchParams[] = [];
    mockApi(routes(HELLO, (q) => queries.push(q)));
    render(<Breathing />);
    const group = await screen.findByRole("group", { name: "Replay demo night" });
    const night = await within(group).findByLabelText("Night");
    fireEvent.change(night, { target: { value: "sess-1" } });
    fireEvent.change(within(group).getByLabelText("Speed"), { target: { value: "3600" } });
    fireEvent.click(within(group).getByRole("button", { name: "Replay demo night" }));
    expect(await within(group).findByRole("button", { name: "Back to live" })).toBeTruthy();
    const replay = queries.find((q) => q.get("replay_session"));
    expect(replay?.get("replay_session")).toBe("sess-1");
    expect(replay?.get("speed")).toBe("3600");
    expect(within(group).getByRole("option", { name: /2026-11-10 22:00 UTC \(synthetic\)/ })).toBeTruthy();
  });
});
