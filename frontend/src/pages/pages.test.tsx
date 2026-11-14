import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { RrTrend } from "../components/RrTrend";
import { instruments, me, night, phq9, responseOut, rrBaseline, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const NIGHTS = [night("2026-11-10", 17.9), night("2026-11-09", 14.2), night("2026-11-08", null, false)];
const CONSENTS = {
  checkins: { granted: true, ts: "2026-11-01T00:00:00Z", policy_version: "demo-1" },
  survey_answers: { granted: false, ts: null, policy_version: null },
  raw_csi: { granted: false, ts: null, policy_version: null },
  share_summaries: { granted: false, ts: null, policy_version: null },
};

let api: ReturnType<typeof mockApi>;
beforeEach(() => {
  signIn();
  api = mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/nights": { body: NIGHTS },
    "GET /api/v1/checkins": { body: [] },
    "GET /api/v1/instruments": { body: instruments },
    "GET /api/v1/instruments/phq9": { body: phq9 },
    "POST /api/v1/responses": { body: responseOut({ total: 1 }) },
    "GET /api/v1/me/consents": { body: CONSENTS },
    "PUT /api/v1/me/consents": (c) => ({
      body: { ...CONSENTS, raw_csi: { granted: (c.body as { scopes: { raw_csi: boolean } }).scopes.raw_csi, ts: "2026-11-11T00:00:00Z", policy_version: "demo-1" } },
    }),
    "POST /api/v1/me/export": { body: { user: { id: "u-1" }, tables: {} } },
    "DELETE /api/v1/me": { status: 204 },
    "POST /api/v1/auth/logout": { status: 204 },
  });
});

describe("Overview", () => {
  it("shows the latest personal breathing signal and due check-in", async () => {
    render(<App initialPath="/" />);
    const hero = await screen.findByRole("region", { name: "Your breathing, in context" });
    expect(within(hero).getByRole("img", { name: "Breathing rate 14.2 breaths per minute" })).toBeTruthy();
    expect(within(hero).getByRole("link", { name: /Check in/ }).getAttribute("href")).toBe("/checkin?instrument=daily_am");
    const breathing = screen.getByRole("heading", { name: /^Breathing$/ }).closest("article")!;
    expect(within(breathing).getByText("17.9")).toBeTruthy();
    expect(within(breathing).getByText("Your usual range")).toBeTruthy();
  });

  it("shows a personal check-in signal without exposing a score or raw z-scores", async () => {
    render(<App initialPath="/" />);
    const mindHeading = await screen.findByRole("heading", { name: "Mind and check-ins" });
    const mind = mindHeading.closest("article")!;
    expect(mind.textContent).not.toMatch(/24|\/ 100/);
    expect(mind.textContent).toMatch(/From your recent personal inputs/);
    expect(document.body.textContent).not.toMatch(/[+-]\d+\.\d+\s*z\b/);
  });

  it("shows the server advisory instead of rendering stale guidance cards", async () => {
    render(<App initialPath="/" />);
    expect(await screen.findByText("A small shift, in your context")).toBeTruthy();
    expect(screen.getByText("Your signals can vary from night to night. We are comparing them with your own recent pattern.")).toBeTruthy();
    expect(screen.queryByText("Try a wind-down routine")).toBeNull();
  });
});

describe("Sleep", () => {
  it("lists nights with validity, quality and onset/midsleep/wake, and asks for the last 28 days", async () => {
    render(<App initialPath="/sleep" />);
    fireEvent.click(await screen.findByRole("button", { name: "Night-by-night details" }));
    const table = (await screen.findAllByRole("table")).find((candidate) => candidate.classList.contains("nights"))!;
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(4);
    expect(Array.from(rows[1].children).map((c) => c.textContent)).toEqual(
      ["2026-11-10", "yes", "82 %", "17.9", "7.5 h", "22:40 UTC", "02:25 UTC", "06:10 UTC", "synthetic"],
    );
    expect(rows[3].className).toBe("invalid");
    const q = api.called("GET /api/v1/nights")[0].query;
    const days = (Date.parse(q.get("to")!) - Date.parse(q.get("from")!)) / 86_400_000;
    expect(days).toBe(27);
  });

  it("RrTrend draws valid nights only, the median ± MAD band, and marks nights outside it", () => {
    const now = Date.parse("2026-11-11T12:00:00Z");
    const { container } = render(<RrTrend nights={NIGHTS} baseline={rrBaseline} now={now} />);
    expect(screen.getByTestId("band")).toBeTruthy();
    const pts = container.querySelectorAll("circle");
    expect(pts).toHaveLength(1); // the current chart marks only its latest valid night
    expect(pts[0].getAttribute("class")).toBe("pt out");
    expect(pts[0].querySelector("title")?.textContent).toBe("Latest night 2026-11-10: 17.9 breaths/min");
  });

  it("RrTrend without a baseline has no band and says it is warming up", () => {
    render(<RrTrend nights={NIGHTS} now={Date.parse("2026-11-11T12:00:00Z")} />);
    expect(screen.queryByTestId("band")).toBeNull();
    expect(screen.getByText(/still warming up/)).toBeTruthy();
  });
});

describe("Psyche", () => {
  it("separates daily check-ins from other reflections and renders the selected form", async () => {
    render(<App initialPath="/checkin" />);
    expect(await screen.findByRole("heading", { name: "A quick check-in" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "More reflections" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Start Mood, nine questions" }));
    const form = await screen.findByRole("form", { name: "Mood, nine questions" });
    expect(within(form).getAllByRole("group")).toHaveLength(1);
    fireEvent.click(within(form).getAllByRole("radio")[0]);
    fireEvent.click(within(form).getByRole("button", { name: "Next" }));
    expect(within(form).getByRole("group", { name: /better off dead/ })).toBeTruthy();
    fireEvent.click(within(form).getAllByRole("radio")[0]);
    fireEvent.click(within(form).getByRole("button", { name: "Send check-in" }));
    expect(await screen.findByText("Saved. Thank you.")).toBeTruthy();
    // the result never shows a score, total or band
    expect(screen.getByText("Saved. Thank you.").closest(".checkin-result")!.textContent).not.toMatch(/score|total|band|\d/i);
  });
});

describe("Settings", () => {
  it("toggles a consent with the policy version", async () => {
    render(<App initialPath="/settings" />);
    const box = await screen.findByRole("switch", { name: /raw sensor recordings/i });
    expect((box as HTMLInputElement).checked).toBe(false);
    fireEvent.click(box);
    await waitFor(() => expect((box as HTMLInputElement).checked).toBe(true));
    expect(api.called("PUT /api/v1/me/consents")[0].body).toEqual({ scopes: { raw_csi: true }, policy_version: "demo-1" });
  });

  it("exports the data as a JSON download", async () => {
    const createURL = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: createURL, revokeObjectURL: vi.fn() }));
    render(<App initialPath="/settings" />);
    fireEvent.click(await screen.findByRole("button", { name: "Export my data" }));
    expect(await screen.findByText(/Export ready/)).toBeTruthy();
    expect(createURL).toHaveBeenCalledTimes(1);
  });

  it("delete needs a confirmation step and the typed phrase, then signs out", async () => {
    render(<App initialPath="/settings" />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete my account…" }));
    const confirm = screen.getByRole("button", { name: "Permanently delete" }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Confirmation"), { target: { value: "delete" } });
    expect(confirm.disabled).toBe(true);
    expect(api.called("DELETE /api/v1/me")).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Confirmation"), { target: { value: "DELETE" } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeTruthy();
    expect(api.called("DELETE /api/v1/me")).toHaveLength(1);
  });

  it("cancel closes the confirmation without deleting", async () => {
    render(<App initialPath="/settings" />);
    fireEvent.click(await screen.findByRole("button", { name: "Delete my account…" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("button", { name: "Permanently delete" })).toBeNull();
    expect(api.called("DELETE /api/v1/me")).toHaveLength(0);
  });
});
