import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { TABS } from "./routes/tabs";

describe("app shell", () => {
  it("shows all six tabs and the synthetic badge", () => {
    render(<App initialPath="/" />);
    const nav = screen.getByRole("navigation", { name: "Sections" });
    const labels = Array.from(nav.querySelectorAll("a")).map((a) => a.textContent);
    expect(labels).toEqual(["Overview", "Breathing", "Heart", "Sleep", "Psyche", "Settings"]);
    expect(TABS).toHaveLength(6);
    expect(screen.getByText("Synthetic data")).toBeTruthy();
  });

  it.each(TABS.map((t) => [t.path, t.label] as const))("routes %s to %s", (path, label) => {
    render(<App initialPath={path} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(label);
    expect(screen.getByRole("link", { name: label }).getAttribute("aria-current")).toBe("page");
  });

  it("labels Heart as experimental, and only Heart", () => {
    render(<App initialPath="/heart" />);
    expect(screen.getByRole("note").textContent).toMatch(/Experimental/);
    render(<App initialPath="/sleep" />);
    expect(screen.getAllByRole("note")).toHaveLength(1);
  });
});
