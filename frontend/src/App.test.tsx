import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "./App";
import { Heart } from "./pages/Live";
import { TABS } from "./routes/tabs";
import { instruments, me, today } from "./test/fixtures";
import { mockApi, signIn } from "./test/mockApi";

beforeEach(() => {
  signIn();
  mockApi({
    "GET /api/v1/me": { body: me },
    "GET /api/v1/today": { body: today },
    "GET /api/v1/nights": { body: [] },
    "GET /api/v1/instruments": { body: instruments },
    "GET /api/v1/me/consents": { body: {} },
  });
});

describe("app shell", () => {
  it("shows the current app sections and the synthetic badge for a synthetic account", async () => {
    render(<App initialPath="/" />);
    const nav = await screen.findByRole("navigation", { name: /^Sections/ });
    expect(Array.from(nav.querySelectorAll("a")).map((a) => a.textContent)).toEqual(
      TABS.map((tab) => tab.label),
    );
    expect(screen.getByText("Simulated data")).toBeTruthy();
  });

  it.each(TABS.map((t) => [t.path, t.label] as const))("marks %s as the current tab", async (path, label) => {
    render(<App initialPath={path} />);
    const link = await screen.findByRole("link", { name: label });
    expect(link.getAttribute("aria-current")).toBe("page");
  });

  it("labels Heart as experimental", async () => {
    render(<Heart />);
    expect((await screen.findByRole("note")).textContent).toMatch(/experimental/i);
  });
});
