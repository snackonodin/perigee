import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { me, today } from "../test/fixtures";
import { mockApi, signIn } from "../test/mockApi";
import { BodyPanel } from "./BodyPanel";

const SYSTEMS = {
  respiration: { state: "changed" as const, reading: "16 br/min" },
  autonomic: { state: "none" as const, reading: "0.8", label: "Not compared yet" },
  rest: { state: "usual" as const, reading: "7.5 h" },
  mind: { state: "usual" as const, reading: "From your check-ins" },
  cabin: { state: "none" as const },
};

describe("BodyPanel", () => {
  it("names each region by its baseline-relative state, never a score or a health verdict", () => {
    const { container } = render(<BodyPanel heartRate={null} breathRate={13} systems={SYSTEMS} />);
    expect(screen.getByRole("button", { name: "Respiration: Changed from your usual, 16 br/min" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Rest: Usual, 7.5 h" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Autonomic: Not compared yet, 0.8" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Cabin: No reading" })).toBeTruthy();
    const html = container.innerHTML;
    expect(html).not.toMatch(/Healthy|Moderate|Needs attention|Score|\d bpm/);
    expect(html.toUpperCase()).not.toMatch(/#E5484D|#2FB67C|DROP-SHADOW/);
  });

  it("the hover card shows the state and reading on separate lines", () => {
    const { container } = render(<BodyPanel heartRate={null} breathRate={13} systems={SYSTEMS} />);
    fireEvent.mouseEnter(screen.getByRole("button", { name: /^Respiration/ }));
    const texts = [...container.querySelectorAll("text")].map((t) => t.textContent);
    expect(texts).toContain("Changed from your usual");
    expect(texts).toContain("16 br/min");
  });

  it("the heart beats only with a heart rate; the lungs breathe only with a breathing rate", () => {
    const still = render(<BodyPanel heartRate={null} breathRate={null} systems={SYSTEMS} />);
    expect(still.container.querySelector("[class$='-beat'], [class$='-lungs'], [class$='-ring']")).toBeNull();
    still.unmount();
    const live = render(<BodyPanel heartRate={62} breathRate={14} systems={SYSTEMS} />);
    expect(live.container.querySelector("[class$='-beat']")).toBeTruthy();
    expect(live.container.querySelector("[class$='-lungs']")).toBeTruthy();
    expect((live.container.querySelector("svg") as SVGElement).style.getPropertyValue("--bpm")).toBe("62");
  });

  it("selects a region by click or keyboard", () => {
    const onSelect = vi.fn();
    render(<BodyPanel heartRate={null} breathRate={13} systems={SYSTEMS} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /^Mind/ }));
    fireEvent.keyDown(screen.getByRole("button", { name: /^Rest/ }), { key: "Enter" });
    expect(onSelect.mock.calls.map((c) => c[0])).toEqual(["mind", "rest"]);
  });
});

describe("Body page", () => {
  it("clicking a hotspot opens that system's detail", async () => {
    signIn();
    mockApi({ "GET /api/v1/me": { body: me }, "GET /api/v1/today": { body: today }, "GET /api/v1/nights": { body: [] } });
    render(<App initialPath="/body" />);
    fireEvent.click(await screen.findByRole("button", { name: /^Rest:/ }));
    expect((await screen.findByRole("heading", { name: "Rest" })).id).toBe("body-detail-title");
  });

  it("Cabin says no sensor is connected, and nothing on the page shows z or a raw cut-off", async () => {
    signIn();
    mockApi({ "GET /api/v1/me": { body: me }, "GET /api/v1/today": { body: today }, "GET /api/v1/nights": { body: [] } });
    render(<App initialPath="/body" />);
    expect(await screen.findByRole("button", { name: "Cabin: No reading, No cabin sensor connected." })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Respiration: Changed from your usual/ })).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\bz\b|2\.5|3\.29/);
  });
});
