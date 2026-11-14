import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { emit } from "../emit";
import { Pet } from "../Pet";
import { PetControls } from "../PetControls";
import type { PetProps } from "../types";

const base: PetProps = { species: "fox", personaId: "internal_deliberator", timeOfDay: "day", safetyActive: false, reducedMotion: true, streakDays: 0, nightsLogged: 0 };
beforeEach(() => { try { localStorage.clear(); localStorage.setItem("pet.firstRunDone", "true"); } catch { /* */ } });
afterEach(() => { vi.useRealTimers(); });

describe("pet accessibility", () => {
  it("art is aria-hidden, the tap target is a labelled button, the bubble is a polite status", () => {
    const { container } = render(<Pet {...base} />);
    expect(container.querySelector(".pet-art")!.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByRole("button", { name: "Pet Ember" })).toBeTruthy();
    const bubble = screen.getByRole("status");
    expect(bubble.getAttribute("aria-live")).toBe("polite");
    act(() => emit("app_open"));
    expect(bubble.textContent!.length).toBeGreaterThan(0);
    expect(bubble.getAttribute("tabindex")).toBeNull();
  });
  it("controls are focusable buttons of at least 44 px, and their state persists", () => {
    render(<PetControls />);
    for (const name of ["Hide pet", "Mute pet messages", "Quiet for 1 hour", "Breathe with me"]) {
      const b = screen.getByRole("button", { name }) as HTMLButtonElement;
      b.focus();
      expect(document.activeElement).toBe(b);
      expect(parseInt(b.style.minWidth)).toBeGreaterThanOrEqual(44);
      expect(parseInt(b.style.minHeight)).toBeGreaterThanOrEqual(44);
    }
    act(() => screen.getByRole("button", { name: "Mute pet messages" }).click());
    expect(localStorage.getItem("pet.dialog.muted")).toBe("true");
    expect(screen.getByRole("button", { name: "Unmute pet messages" })).toBeTruthy();
    expect(screen.getByText("Relaxation exercise. Not a medical tool.")).toBeTruthy();
  });
  it("a hidden pet shows only a Show pet button", () => {
    localStorage.setItem("pet.hidden", "true");
    const { container } = render(<Pet {...base} />);
    expect(screen.getByRole("button", { name: "Show pet" })).toBeTruthy();
    expect(container.querySelector("svg")).toBeNull();
    act(() => screen.getByRole("button", { name: "Show pet" }).click());
    expect(screen.getByRole("button", { name: "Pet Ember" })).toBeTruthy();
  });
  it("quiz_complete shows a completion line only", () => {
    render(<Pet {...base} />);
    act(() => emit("quiz_complete"));
    expect(screen.getByRole("status").textContent).not.toMatch(/score|result|level|high|low|better|worse/i);
  });
});
