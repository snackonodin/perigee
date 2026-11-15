import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { instruments, me, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";

const sample = {
  id: "theta45_breath_laptop_inside_3min",
  title: "45 degree geometry, natural breathing (90 s)",
  setup: "Seated person at 45 deg to the router-receiver line.",
  measured_by: "Host laptop running the team logger",
  measured_at: "2026-11-09T12:49:34+00:00",
  rows: 9869,
  packet_rate_hz: 100.3,
  truth: { bpm: 30, source: "Operator manual breath count" },
  windows: [{ t_start_s: 0, t_end_s: 30, spectral_bpm: 29.8, peak_count_bpm: 26.1 }],
  accuracy_pct: { spectral: 82.4, peak_count: 73.7 },
  accuracy_definition: "Mean over windows of 100 x (1 - |estimate - truth| / truth).",
};

describe("Monitor real ESP32 captures", () => {
  beforeEach(() => {
    vi.useRealTimers();
    signIn();
    mockApi({
      "GET /api/v1/me": { body: me },
      "GET /api/v1/today": { body: today },
      "GET /api/v1/nights": { body: [] },
      "GET /api/v1/instruments": { body: instruments },
      "GET /api/v1/me/consents": { body: {} },
      "GET /api/v1/monitor/modes": { body: [] },
      "GET /api/v1/monitor/sessions": { body: [] },
      "GET /api/v1/monitor/samples": { body: [sample] },
    });
  });

  it("renders a saved capture with its measured time and accuracy", async () => {
    render(<App initialPath="/monitor" />);
    expect(await screen.findByRole("heading", { name: "Real ESP32 captures" })).toBeTruthy();
    const time = document.querySelector("time[datetime='2026-11-09T12:49:34+00:00']");
    expect(time?.textContent).toMatch(/2026/);
    expect(screen.getByText("Spectral 82.4% accurate")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Download CSI capture (CSV)" })).toBeTruthy();
  });
});
