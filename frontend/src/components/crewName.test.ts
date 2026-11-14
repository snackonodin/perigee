import { describe, expect, it } from "vitest";
import { crewName } from "./AppShell";

describe("header crew name", () => {
  it("never shows the full e-mail", () => {
    expect(crewName(null, "persona-dip@example.invalid")).toBe("persona-dip");
    expect(crewName("  ", "ada@example.invalid")).toBe("ada");
    expect(crewName("Ada", "ada@example.invalid")).toBe("Ada");
    expect(crewName(undefined, undefined)).toBe("Crew member");
  });
});
