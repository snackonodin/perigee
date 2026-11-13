import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { SAFETY_ACK_DELAY_MS, SAFETY_FALLBACK } from "./safety/safety";
import { SafetyProvider, useSafety } from "./safety/SafetyProvider";
import { instruments, me, today } from "./test/fixtures";
import { mockApi, type Reply, signIn } from "./test/mockApi";
import tokensCss from "./theme/tokens.css?raw";

// ---------------------------------------------------------------- contrast (WCAG AA for the current pastel palette)

function token(name: string): string {
  const m = tokensCss.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`no token --${name}`);
  return m[1];
}
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function ratio(fg: string, bg: string): number {
  const [hi, lo] = [luminance(token(fg)), luminance(token(bg))].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

describe("contrast on the pastel theme (WCAG AA, 4.5:1 for text)", () => {
  const INK_ON_NEUTRAL = ["text", "muted", "ok-ink", "warn-ink", "alert-ink", "teal-ink"];
  const PAIRS = [
    ...INK_ON_NEUTRAL.flatMap((fg) => ["surface", "bg"].map((bg) => [fg, bg] as const)),
    ...["mint", "sky", "peach", "lavender", "butter", "alert-soft"].map((bg) => ["text", bg] as const),
    ["ok-ink", "mint"], ["warn-ink", "butter"], ["alert-ink", "alert-soft"],
    ["teal-ink", "mint"], ["teal-ink", "sky"], ["surface", "teal"], ["bg", "teal"],
  ] as const;
  it.each(PAIRS)("%s on %s", (fg, bg) => {
    expect(ratio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });
});

// ---------------------------------------------------------------- safety overlay keyboard

function Raise() {
  const { showSafety } = useSafety();
  return <button onClick={() => showSafety(SAFETY_FALLBACK)}>raise</button>;
}

function renderInRoot(ui: React.ReactElement) {
  const root = document.body.appendChild(Object.assign(document.createElement("div"), { id: "root" }));
  return { root, ...render(ui, { container: root }) };
}

describe("safety overlay keyboard and focus", () => {
  it("traps focus, ignores Escape, makes the app inert, and restores focus after", () => {
    vi.useFakeTimers();
    const { root } = renderInRoot(<SafetyProvider><Raise /></SafetyProvider>);
    const raise = screen.getByText("raise");
    raise.focus();
    fireEvent.click(raise);
    const dialog = screen.getByRole("alertdialog");
    const title = screen.getByRole("heading", { name: "You deserve support right now" });
    expect(document.activeElement).toBe(title);
    expect(root.hasAttribute("inert")).toBe(true);

    // Escape does nothing; keyboard focus cycles among the live safety controls.
    fireEvent.keyDown(dialog, { key: "Tab" });
    const contact = screen.getByRole("button", { name: "Contact crew surgeon" });
    expect(document.activeElement).toBe(contact);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.getByRole("alertdialog")).toBeTruthy();

    act(() => vi.advanceTimersByTime(SAFETY_ACK_DELAY_MS + 300));
    const ack = screen.getByRole("button", { name: "I have read this" });
    expect(document.activeElement).toBe(ack);
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(title); // wraps, never leaves the dialog
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(ack);
    expect(screen.getByText("You can now close this screen.")).toBeTruthy();

    fireEvent.click(ack);
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(root.hasAttribute("inert")).toBe(false);
    expect(document.activeElement).toBe(raise);
    root.remove();
  });
});

// ---------------------------------------------------------------- shell keyboard

describe("shell keyboard support", () => {
  it("has a skip link to the main content and moves focus to it after a tab change", async () => {
    signIn();
    mockApi({
      "GET /api/v1/me": { body: me },
      "GET /api/v1/today": { body: today },
      "GET /api/v1/nights": { body: [] },
    });
    render(<App initialPath="/" />);
    const skip = await screen.findByRole("link", { name: "Skip to content" });
    expect(skip.getAttribute("href")).toBe("#main");
    fireEvent.click(screen.getByRole("link", { name: "Sleep" }));
    const main = await screen.findByRole("main", { name: "Sleep" });
    expect(document.activeElement).toBe(main);
  });
});

// ---------------------------------------------------------------- loading and error states

const FAIL: Reply = { status: 503, body: { error: "unavailable", message: "database busy" } };

function flaky(ok: Reply) {
  let n = 0;
  return () => (n++ === 0 ? FAIL : ok);
}

describe.each([
  ["/", "GET /api/v1/today", { body: today }, "today's personal snapshot", "Your picture is taking shape", "fallback"],
  ["/sleep", "GET /api/v1/nights", { body: [] }, "nightly timeline", "No valid nights in this window yet.", "fallback"],
  ["/checkin", "GET /api/v1/checkins", { body: [] }, "your check-in calendar", "Check-in calendar", "retry"],
  ["/settings", "GET /api/v1/me/consents", { body: {} }, "your consents", "What may be stored", "retry"],
] as const)("page %s", (path, route, ok, label, ready, behavior) => {
  it("shows the loading state and the endpoint's designed recovery", async () => {
    signIn();
    let release!: () => void;
    const gate = new Promise<void>((r) => (release = r));
    const next = flaky(ok);
    mockApi({
      "GET /api/v1/me": { body: me },
      "GET /api/v1/today": { body: today },
      "GET /api/v1/nights": { body: [] },
      "GET /api/v1/instruments": { body: instruments },
      "GET /api/v1/checkins": { body: [] },
      "GET /api/v1/indices": { body: { week_start: "2026-11-09", indices: {}, run_id: null } },
      "GET /api/v1/me/consents": { body: {} },
      [route]: async () => {
        await gate;
        return next();
      },
    });
    render(<App initialPath={path} />);
    const busy = await screen.findByText(`Loading ${label}…`);
    expect(busy.getAttribute("aria-busy")).toBe("true");
    release();
    if (behavior === "fallback") {
      expect(await screen.findByText(ready)).toBeTruthy();
      expect(screen.getByText(/API unavailable|Showing sample data/)).toBeTruthy();
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
      return;
    }
    const alert = await screen.findByText(`Could not load ${label}: database busy`);
    expect(alert.closest("[role=alert]")).toBeTruthy();
    fireEvent.click(within(alert.closest("[role=alert]")!).getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(ready)).toBeTruthy();
    expect(screen.queryByText(/Could not load/)).toBeNull();
  });
});
