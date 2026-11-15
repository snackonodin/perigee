import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Pet } from "../Pet";
import { petStore } from "../store";
import type { PetProps } from "../types";

const base: PetProps = { species: "cat", personaId: "internal_deliberator", timeOfDay: "day", safetyActive: false, reducedMotion: true, streakDays: 0, nightsLogged: 0 };
beforeEach(() => { vi.useFakeTimers(); try { localStorage.clear(); localStorage.setItem("pet.firstRunDone", "true"); } catch { /* */ } });
afterEach(() => { vi.useRealTimers(); });

describe("Breathe with me", () => {
  it("shows a large 'Breathe in' / 'Breathe out' cue on the 4 s / 6 s clock, a halo, and ends after 10 cycles", () => {
    const { container } = render(<Pet {...base} />);
    expect(container.querySelector(".pet-buddy-halo")).toBeNull();
    act(() => petStore.startBuddy());
    const root = container.querySelector(".pet")!;
    expect(root.getAttribute("data-buddy")).toBe("true");
    expect(container.querySelector(".pet-buddy-halo")).toBeTruthy();
    const cue = () => container.querySelector(".pet-buddy-cue")!;
    expect(cue().textContent).toBe("Breathe in");
    expect(cue().getAttribute("aria-live")).toBe("polite");
    act(() => { vi.advanceTimersByTime(3990); });
    expect(cue().textContent).toBe("Breathe in");
    act(() => { vi.advanceTimersByTime(20); });
    expect(cue().textContent).toBe("Breathe out");
    expect(container.querySelector(".pet-buddy-halo")!.getAttribute("data-phase")).toBe("out");
    act(() => { vi.advanceTimersByTime(5970); });
    expect(cue().textContent).toBe("Breathe out");
    act(() => { vi.advanceTimersByTime(40); });
    expect(cue().textContent).toBe("Breathe in");
    act(() => { vi.advanceTimersByTime(90_000); });
    expect(container.querySelector(".pet-buddy-cue")).toBeNull();
    expect(container.querySelector(".pet-buddy-halo")).toBeNull();
  });

  it("starting the exercise closes the options menu so it cannot cover the cue", () => {
    const { container } = render(<Pet {...base} />);
    act(() => screen.getByRole("button", { name: "Companion options" }).click());
    expect(container.querySelector(".pet-menu")).toBeTruthy();
    act(() => screen.getByRole("button", { name: "Breathe with me" }).click());
    expect(container.querySelector(".pet-menu")).toBeNull();
    expect(container.querySelector(".pet-buddy-cue")!.textContent).toBe("Breathe in");
  });

  it("Stop ends the exercise at once", () => {
    const { container } = render(<Pet {...base} />);
    act(() => petStore.startBuddy());
    act(() => screen.getByRole("button", { name: "Stop" }).click());
    expect(container.querySelector(".pet-buddy-cue")).toBeNull();
    expect(container.querySelector(".pet")!.getAttribute("data-buddy")).toBeNull();
  });
});
