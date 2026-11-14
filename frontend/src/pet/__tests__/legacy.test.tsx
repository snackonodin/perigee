import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CHARACTERS, CompanionFace, LEGACY_CHARACTER_TO_SPECIES } from "../CompanionFace";
import type { Mood } from "../types";

const MOODS: Mood[] = ["neutral", "happy", "calm", "encouraging", "concerned", "tired", "sleeping"];

describe("legacy CompanionFace", () => {
  it("renders every character x mood statically, with no timers", () => {
    vi.useFakeTimers();
    for (const c of CHARACTERS) for (const m of MOODS) {
      const { container, unmount } = render(<CompanionFace character={c.id} mood={m} />);
      const art = container.querySelector(".pet-art")!;
      expect(art.getAttribute("aria-hidden")).toBe("true");
      expect(art.getAttribute("data-species")).toBe(LEGACY_CHARACTER_TO_SPECIES[c.id]);
      unmount();
    }
    expect(vi.getTimerCount()).toBe(0);
    vi.useRealTimers();
  });
  it("concerned never looks sad: same face as calm", () => {
    const a = render(<CompanionFace character="nimbus" mood="concerned" />).container.querySelector(".pet-art")!;
    const b = render(<CompanionFace character="nimbus" mood="calm" />).container.querySelector(".pet-art")!;
    expect(a.getAttribute("data-mood")).toBe("calm");
    expect(a.innerHTML).toBe(b.innerHTML);
  });
  it("maps nimbus/pip/lumi to cat/fox/bunny", () => {
    expect(LEGACY_CHARACTER_TO_SPECIES).toEqual({ nimbus: "cat", pip: "fox", lumi: "bunny" });
  });
});
