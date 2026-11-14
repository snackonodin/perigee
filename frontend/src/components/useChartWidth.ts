import { useLayoutEffect, useRef, useState } from "react";

/**
 * Measured pixel width of a chart's box, so an SVG can use a viewBox of the same
 * width (1 unit = 1 px) and its 12 px axis labels stay 12 px at any screen size.
 * Falls back to `fallback` where layout is unavailable (tests, first paint).
 */
export function useChartWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => { const w = Math.round(el.getBoundingClientRect().width); if (w > 0) setWidth(w); };
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}
