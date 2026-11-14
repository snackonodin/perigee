import { describe, expect, it } from "vitest";
import { plainHeadline, plainMessage } from "./advisory";

describe("engine advisory wording", () => {
  it("replaces the [PATTERN] tag with a plain title", () => {
    expect(plainHeadline("[BODY SIGNAL FIRST] Recovery Advisory")).toBe("Body signals first: a recovery note");
    expect(plainHeadline("[MIND SIGNAL FIRST] Recovery Advisory")).toBe("Mind signals first: a recovery note");
    expect(plainHeadline("[CONVERGING SIGNALS] Recovery Advisory")).not.toMatch(/\[|CONVERGING/);
    expect(plainHeadline("[STEADY] Recovery Advisory")).not.toMatch(/\[/);
  });
  it("keeps headlines without a tag unchanged", () => {
    expect(plainHeadline("A small shift, in your context")).toBe("A small shift, in your context");
    expect(plainHeadline(undefined)).toBeUndefined();
  });
  it("swaps only the classification phrase in the message", () => {
    const out = plainMessage("Your current pattern is classified as body signal first; review the contributing measures and context.");
    expect(out).toBe("Your current pattern shows body signals changing first; review the contributing measures and context.");
    expect(out).not.toMatch(/classified/);
  });
});
