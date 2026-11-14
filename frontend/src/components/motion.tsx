// Motion gate. Every scripted animation goes through useMotionOK(): off under the OS reduced-motion
// setting, the in-app Reduce motion switch, tests, and while the safety screen is open.
import { useSyncExternalStore } from "react";

function motionAllowed(): boolean {
  if (import.meta.env.MODE === "test" || typeof window === "undefined" || !window.matchMedia) return false;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  if (document.documentElement.dataset.reduceMotion === "true") return false;
  return !document.querySelector(".safety");
}
function subscribe(onChange: () => void) {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-reduce-motion"] });
  media.addEventListener?.("change", onChange);
  return () => { observer.disconnect(); media.removeEventListener?.("change", onChange); };
}
export function useMotionOK(): boolean {
  return useSyncExternalStore(subscribe, motionAllowed, () => false);
}

// Craft pass: no generic page entrances. Each page keeps one authored moment of its own
// (Today: breathing orb; Sleep: arc draw; Monitor: session ring; Persona: trait dials).
