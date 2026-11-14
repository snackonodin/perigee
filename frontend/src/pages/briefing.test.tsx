import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "../App";
import { me, night, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const d = (back: number) => new Date(Date.now() - back * 86_400_000).toISOString().slice(0, 10);
const CONSENTS = {
  checkins: { granted: true, ts: "2026-11-01T00:00:00Z", policy_version: "demo-1" },
  survey_answers: { granted: false, ts: null, policy_version: null },
  raw_csi: { granted: false, ts: null, policy_version: null },
  share_summaries: { granted: false, ts: null, policy_version: null },
};

beforeEach(() => {
  signIn();
  mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/nights": { body: [night(d(0), 15.1), night(d(1), 14.9), night(d(2), null, false)] },
    "GET /api/v1/checkins": { body: [
      { id: "c1", date: d(0), instrument_id: "phq9", instrument_version: "1", slot: "am", created_at: "", answers: { q1: 3 } },
      { id: "c2", date: d(1), instrument_id: "phq9", instrument_version: "1", slot: "am", created_at: "", answers: { q1: 2 } },
    ] },
    "GET /api/v1/me/consents": { body: CONSENTS },
  });
});

describe("Briefing", () => {
  it("summarises the week from existing endpoints, without showing answers", async () => {
    const { container } = render(<App initialPath="/briefing" />);
    expect(await screen.findByText(/2 of 7 nights recorded/)).toBeTruthy();
    expect(await screen.findByText(/2 check-ins on 2 days/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Print" })).toBeTruthy();
    expect(screen.queryByText(/View coming in a later/)).toBeNull();
    expect(container.textContent).not.toMatch(/q1/);
  });
});

describe("Consent", () => {
  it("shows the consent switches, policy version and data controls", async () => {
    render(<App initialPath="/consent" />);
    expect(await screen.findByRole("switch", { name: /Raw sensor recordings/ })).toBeTruthy();
    expect(screen.getByText(/Policy · demo-1/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Your data" })).toBeTruthy();
  });
});
