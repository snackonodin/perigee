// SAFETY.md S1: while the safety screen is open the pet renders nothing and runs nothing.
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { emit } from "../emit";
import { Pet } from "../Pet";
import { PetControls } from "../PetControls";
import type { PetProps } from "../types";

const base: PetProps = { species: "cat", personaId: "default", timeOfDay: "day", safetyActive: false, reducedMotion: false, streakDays: 0, nightsLogged: 0 };

beforeEach(() => { vi.useFakeTimers(); try { localStorage.clear(); localStorage.setItem("pet.firstRunDone", "true"); } catch { /* */ } });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe("pet safety", () => {
  it("renders nothing and starts no timers or animation frames while safetyActive", () => {
    const raf = vi.spyOn(window, "requestAnimationFrame");
    const { container } = render(<Pet {...base} safetyActive placement="stage" />);
    expect(container.innerHTML).toBe("");
    expect(vi.getTimerCount()).toBe(0);
    act(() => vi.advanceTimersByTime(60000));
    expect(raf).not.toHaveBeenCalled();
  });
  it("a mounted pet flipped to safetyActive clears everything", () => {
    const { container, rerender } = render(<Pet {...base} placement="stage" />);
    expect(container.innerHTML).not.toBe("");
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    const raf = vi.spyOn(window, "requestAnimationFrame");
    rerender(<Pet {...base} placement="stage" safetyActive />);
    expect(container.innerHTML).toBe("");
    expect(vi.getTimerCount()).toBe(0);
    act(() => vi.advanceTimersByTime(60000));
    expect(raf).not.toHaveBeenCalled();
  });

  it("emit() while safetyActive renders no text, and controls are absent", () => {
    const { container } = render(<><Pet {...base} safetyActive /><PetControls safetyActive /></>);
    act(() => { emit("quiz_complete"); emit("app_open"); });
    expect(container.innerHTML).toBe("");
    expect(container.textContent).toBe("");
  });
  it("after safety clears: fresh pet, no line for 60 s", () => {
    const { container, rerender } = render(<Pet {...base} safetyActive />);
    rerender(<Pet {...base} />);
    expect(container.querySelector("button[aria-label='Pet Miso']")).not.toBeNull();
    act(() => { emit("app_open"); vi.advanceTimersByTime(59000); emit("welcome_back"); });
    expect(container.querySelector(".pet-bubble")!.textContent).toBe("");
    act(() => { vi.advanceTimersByTime(2000); emit("app_open"); });
    expect(container.querySelector(".pet-bubble")!.textContent).not.toBe("");
  });
});
