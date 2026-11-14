import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import seed from "../../../seeds/safety_resources.json";
import { CheckinForm } from "../components/CheckinForm";
import { phq9, responseOut, SERVER_SAFETY } from "../test/fixtures";
import { mockApi } from "../test/mockApi";
import { contentFromServer, localSafetyTriggered, SAFETY_ACK_DELAY_MS, SAFETY_FALLBACK } from "./safety";
import { SafetyProvider, useSafety, useSafetyActive } from "./SafetyProvider";

describe("safety rules", () => {
  it("offline fallback is the seed file's text (one source of truth with the server)", () => {
    expect(SAFETY_FALLBACK.reason).toBe(seed.reasons.safety_item);
    expect(SAFETY_FALLBACK.resources).toEqual(seed.resources);
  });

  it.each([
    [{ phq9_1: 1, phq9_9: 0 }, false],
    [{ phq9_1: 0, phq9_9: 1 }, true],
    [{ phq9_9: 3 }, true],
    [{}, false],
  ])("local pre-check %j -> %s", (answers, expected) => {
    expect(localSafetyTriggered(phq9, answers)).toBe(expected);
  });

  it("server text wins; missing pieces fall back to the seed", () => {
    expect(contentFromServer(SERVER_SAFETY)).toEqual(SERVER_SAFETY);
    expect(contentFromServer({ reason: null, resources: [] })).toEqual(SAFETY_FALLBACK);
  });
});

function Raise() {
  const { showSafety } = useSafety();
  return <button onClick={() => showSafety(SAFETY_FALLBACK)}>raise</button>;
}

describe("SafetyOverlay", () => {
  it("cannot be acknowledged for 3 s (a double click on Submit must not dismiss it unread)", () => {
    vi.useFakeTimers();
    expect(SAFETY_ACK_DELAY_MS).toBeGreaterThanOrEqual(2000);
    render(<SafetyProvider><Raise /></SafetyProvider>);
    fireEvent.click(screen.getByText("raise"));
    const ack = screen.getByRole("button", { name: /Please read this \(3\)/ }) as HTMLButtonElement;
    expect(ack.disabled).toBe(true);
    fireEvent.click(ack);
    fireEvent.click(ack); // the stray second click of a double click
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    act(() => vi.advanceTimersByTime(SAFETY_ACK_DELAY_MS - 300));
    expect((screen.getByRole("button", { name: /Please read this/ }) as HTMLButtonElement).disabled).toBe(true);
    act(() => vi.advanceTimersByTime(600));
    const ready = screen.getByRole("button", { name: "I have read this" }) as HTMLButtonElement;
    expect(ready.disabled).toBe(false);
    fireEvent.click(ready);
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("exposes a read-only active flag: true while shown, false after acknowledgement", () => {
    vi.useFakeTimers();
    function Flag() { return <span data-testid="flag">{String(useSafetyActive())}</span>; }
    render(<SafetyProvider><Raise /><Flag /></SafetyProvider>);
    expect(screen.getByTestId("flag").textContent).toBe("false");
    fireEvent.click(screen.getByText("raise"));
    expect(screen.getByTestId("flag").textContent).toBe("true");
    act(() => vi.advanceTimersByTime(SAFETY_ACK_DELAY_MS + 300));
    fireEvent.click(screen.getByRole("button", { name: "I have read this" }));
    expect(screen.getByTestId("flag").textContent).toBe("false");
    vi.useRealTimers();
  });

  it("useSafetyActive is false outside a provider", () => {
    function Flag() { return <span data-testid="flag2">{String(useSafetyActive())}</span>; }
    render(<Flag />);
    expect(screen.getByTestId("flag2").textContent).toBe("false");
  });

  it("renders in a portal on <body>, above the page, with the resources", () => {
    const { container } = render(<SafetyProvider><Raise /></SafetyProvider>);
    fireEvent.click(screen.getByText("raise"));
    const dialog = screen.getByRole("alertdialog");
    expect(container.contains(dialog)).toBe(false);
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    for (const r of SAFETY_FALLBACK.resources) expect(screen.getByText(r)).toBeTruthy();
  });
});

function answer(item: string, label: string) {
  const target = new RegExp(item, "i");
  let group = screen.getAllByRole("group")[0];
  while (!target.test(group.textContent ?? "")) {
    const current = Array.from(group.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    if (!current.some((radio) => radio.checked)) fireEvent.click(current[0]);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    group = screen.getAllByRole("group")[0];
  }
  fireEvent.click(Array.from(group.querySelectorAll("label")).find((l) => l.textContent === label)!.querySelector("input")!);
}

function renderForm() {
  render(<SafetyProvider><CheckinForm instrument={phq9} /></SafetyProvider>);
  answer("Little interest", "Not at all");
  answer("better off dead", "Several days");
}

describe("CheckinForm safety order", () => {
  it("shows safety before the request completes and keeps scores hidden when the server requires safety", async () => {
    let release!: () => void;
    const pending = new Promise<void>((r) => (release = r));
    const api = mockApi({
      "POST /api/v1/responses": async () => {
        await pending;
        return { body: responseOut({ safety: { show: true, ...SERVER_SAFETY } }) };
      },
    });
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Send check-in" }));
    // local pre-check: on screen while the request is still in flight, with the seed text
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.getByText(SAFETY_FALLBACK.reason)).toBeTruthy();
    expect(screen.queryByText(/Total score/)).toBeNull();
    release();
    expect(await screen.findByText("Server reason text.")).toBeTruthy(); // server text replaces it
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.queryByText(/Total score/)).toBeNull();
    expect(api.called("POST /api/v1/responses")[0].body).toEqual({
      instrument_id: "phq9",
      instrument_version: "1.0",
      answers: { phq9_1: 0, phq9_9: 1 },
    });
  });

  it("a 500 from /responses still shows its safety result", async () => {
    mockApi({
      "POST /api/v1/responses": {
        status: 500,
        body: responseOut({ ok: false, stored: false, error: "storage", safety: { show: true, ...SERVER_SAFETY } }),
      },
    });
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Send check-in" }));
    expect(await screen.findByText("Server reason text.")).toBeTruthy();
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(screen.queryByText(/Total score/)).toBeNull();
    expect(screen.queryByText(/Scored only:/)).toBeNull();
  });

  it("keeps the local safety screen when the server cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("offline"))));
    renderForm();
    fireEvent.click(screen.getByRole("button", { name: "Send check-in" }));
    expect(screen.getByRole("alertdialog")).toBeTruthy();
    expect(await screen.findByText(/Cannot reach the server/)).toBeTruthy();
    expect(screen.getByText(SAFETY_FALLBACK.resources[0])).toBeTruthy();
  });

  it("no trigger and server show=false: no safety screen", async () => {
    mockApi({ "POST /api/v1/responses": { body: responseOut() } });
    render(<SafetyProvider><CheckinForm instrument={phq9} /></SafetyProvider>);
    answer("Little interest", "Several days");
    answer("better off dead", "Not at all");
    fireEvent.click(screen.getByRole("button", { name: "Send check-in" }));
    expect(await screen.findByText("Saved. Thank you.")).toBeTruthy();
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });
});

describe("result wording", () => {
  it("never claims the answers were kept or dropped; `stored` only means a row was written", async () => {
    mockApi({ "POST /api/v1/responses": { body: responseOut({ stored: false }) } });
    render(<SafetyProvider><CheckinForm instrument={phq9} /></SafetyProvider>);
    answer("Little interest", "Several days");
    answer("better off dead", "Not at all");
    fireEvent.click(screen.getByRole("button", { name: "Send check-in" }));
    const status = await screen.findByText("Scored only: nothing was stored (check-ins are off in Settings).");
    expect(status.textContent).toMatch(/nothing was stored/);
    expect(status.textContent).not.toMatch(/answers were not kept/);
  });
});
