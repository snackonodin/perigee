import { describe, expect, it } from "vitest";
import { decimate, trimTo } from "./decimate";

describe("decimate", () => {
  it("returns short series untouched", () => {
    const pts = [{ t: 1, v: 1 }, { t: 2, v: 2 }];
    expect(decimate(pts, 10)).toBe(pts);
  });

  it("caps the point count and keeps spikes (min/max per bucket)", () => {
    const pts = Array.from({ length: 10_000 }, (_, i) => ({ t: i, v: i === 5_123 ? 99 : 14 }));
    const out = decimate(pts, 300);
    expect(out.length).toBeLessThanOrEqual(300);
    expect(out.some((p) => p.v === 99)).toBe(true);
    expect(out.map((p) => p.t)).toEqual([...out.map((p) => p.t)].sort((a, b) => a - b));
  });

  it("keeps gaps so lines break where data is missing", () => {
    const pts = Array.from({ length: 1_000 }, (_, i) => ({ t: i, v: i >= 400 && i < 600 ? null : 14 }));
    expect(decimate(pts, 100).some((p) => p.v === null)).toBe(true);
  });

  it("trimTo drops the oldest entries", () => {
    const a = [1, 2, 3, 4, 5];
    trimTo(a, 3);
    expect(a).toEqual([3, 4, 5]);
  });
});

describe("chart axis labels (regression: duplicate keys left stale labels)", () => {
  it("LiveChart keeps exactly 3 y labels from 1 point to many, plus start/end times", async () => {
    const { render } = await import("@testing-library/react");
    const { LiveChart } = await import("./LiveChart");
    const pts = (n: number) => Array.from({ length: n }, (_, i) => ({ t: Date.UTC(2026, 10, 11, 22, i), v: n === 1 ? 70 : 50 + (i % 7) * 9 }));
    const { container, rerender } = render(<LiveChart label="x" unit="u" series={[{ name: "a", points: pts(1), className: "trace" }]} />);
    rerender(<LiveChart label="x" unit="u" series={[{ name: "a", points: pts(2), className: "trace" }]} />);
    rerender(<LiveChart label="x" unit="u" series={[{ name: "a", points: pts(60), className: "trace" }]} />);
    expect(container.querySelectorAll('text[data-axis="y"]')).toHaveLength(3);
    const times = [...container.querySelectorAll('text[data-axis="t"]')].map((t) => t.textContent);
    expect(times).toEqual(["22:00 UTC", "u", "22:59 UTC"]);
  });

  it("RrTrend keeps exactly 3 y labels when a single night grows to many", async () => {
    const { render } = await import("@testing-library/react");
    const { RrTrend } = await import("../components/RrTrend");
    const { night } = await import("../test/fixtures");
    const now = Date.parse("2026-11-11T12:00:00Z");
    const { container, rerender } = render(<RrTrend nights={[night("2026-11-10", 14)]} now={now} />);
    rerender(<RrTrend nights={[night("2026-11-10", 14), night("2026-11-09", 15), night("2026-11-08", 13)]} now={now} />);
    expect(container.querySelectorAll('text[data-axis="y"]')).toHaveLength(3);
  });
});
