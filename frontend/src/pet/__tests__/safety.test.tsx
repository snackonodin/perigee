// SAFETY.md S1: while the safety screen is open the pet renders nothing and runs nothing.
import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Pet } from "../Pet";
import type { PetProps } from "../types";

const base: PetProps = { species: "cat", personaId: "default", timeOfDay: "day", safetyActive: false, reducedMotion: false, streakDays: 0, nightsLogged: 0 };

beforeEach(() => { vi.useFakeTimers(); });
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
});
