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
  it("shows last night, check-ins due and baseline maturity", async () => {
    render(<App initialPath="/" />);
    const card = await screen.findByRole("region", { name: "Last night" });
    expect(within(card).getByText("17.9 breaths/min")).toBeTruthy();
    expect(within(card).getByRole("link", { name: "Start" }).getAttribute("href")).toBe("/psyche?instrument=daily_am");
    expect(within(card).getByText("mature")).toBeTruthy();
  });

  it("FlagWhy lists each signal with median ± MAD and z, highlighting |z| >= alert", async () => {
    render(<App initialPath="/" />);
    const table = await screen.findByRole("table");
    const rows = within(table).getAllByRole("row").map((r) => Array.from(r.children).map((c) => c.textContent));
    expect(rows).toContainEqual(["Body", "rr_med", "17.90", "14.00 ± 0.80", "+3.3"]);
    expect(rows).toContainEqual(["Mood", "phq2", "1.00", "–", "baseline warming up"]);
    expect(within(table).getByText("+3.3").className).toBe("z-high");
  });

  it("GuidanceCard shows the source and 'not yet clinically reviewed' when reviewed_by is null", async () => {
    const { baseElement } = render(<App initialPath="/" />);
    await screen.findByText("Try a wind-down routine");
    const cards = Array.from(baseElement.querySelectorAll<HTMLElement>("article.guidance"));
    expect(cards).toHaveLength(2);
    const unreviewed = cards.find((c) => c.textContent?.includes("Try a wind-down routine"))!;
    expect(unreviewed.textContent).toMatch(/Source: General sleep hygiene guidance/);
    expect(within(unreviewed).getByText("not yet clinically reviewed")).toBeTruthy();
    const reviewed = cards.find((c) => c.textContent?.includes("Reviewed card"))!;
    expect(reviewed.textContent).toMatch(/reviewed by Dr\. Example/);
    expect(reviewed.textContent).not.toMatch(/not yet clinically reviewed/);
  });
});

describe("Sleep", () => {
  it("lists nights with validity, quality and onset/midsleep/wake, and asks for the last 28 days", async () => {
    render(<App initialPath="/sleep" />);
    const table = await screen.findByRole("table");
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
    expect(pts).toHaveLength(2); // the invalid night is not drawn
    const outside = Array.from(pts).filter((p) => p.getAttribute("class") === "pt out");
    expect(outside.map((p) => p.textContent)).toEqual(["2026-11-10: 17.9 breaths/min"]);
  });

  it("RrTrend without a baseline has no band and says it is warming up", () => {
    render(<RrTrend nights={NIGHTS} now={Date.parse("2026-11-11T12:00:00Z")} />);
    expect(screen.queryByTestId("band")).toBeNull();
    expect(screen.getByText(/still warming up/)).toBeTruthy();
  });
});

describe("Psyche", () => {
  it("lists questionnaires (not the daily check-ins) and renders the form from instrument JSON", async () => {
    render(<App initialPath="/psyche" />);
    const list = await screen.findByRole("region", { name: "Questionnaires" });
    expect(within(list).queryByText(/Morning check-in/)).toBeNull();
    fireEvent.click(await within(list).findByRole("button", { name: "Start Patient Health Questionnaire-9 (PHQ-9)" }));
    const form = await screen.findByRole("form", { name: phq9.name });
    expect(within(form).getAllByRole("group")).toHaveLength(2);
    for (const g of within(form).getAllByRole("group")) fireEvent.click(within(g).getAllByRole("radio")[0]);
    fireEvent.click(within(form).getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Saved. Thank you.")).toBeTruthy();
  });
});

describe("Settings", () => {
  it("toggles a consent with the policy version", async () => {
    render(<App initialPath="/settings" />);
    const box = await screen.findByRole("checkbox", { name: /raw Wi-Fi sensing/ });
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
    fireEvent.change(screen.getByLabelText("Confirmation"), { target: { value: "Delete my account" } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
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
