import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// Overnight runs are serial but the machine is shared: with the full parallel vitest run
// under load avg 40-60, the first React paint of a page took >1 s, so findBy* hit its 1 s
// default. 4 s keeps waits bounded (no test waits forever) and assertions are unchanged.
configure({ asyncUtilTimeout: 4000 });

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
