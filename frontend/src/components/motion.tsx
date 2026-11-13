// Motion wrappers (P2). Every animation goes through useMotionOK(): off under the OS reduced-motion
// setting, the in-app Reduce motion switch, tests, and while the safety screen is open.
import { Suspense, createElement, lazy, useSyncExternalStore, type ReactNode } from "react";

// Loaded only when motion is allowed: gsap/ScrollTrigger touch window.matchMedia at import time.
const AnimatedContent = lazy(() => import("../vendor/react-bits/AnimatedContent"));
const SplitText = lazy(() => import("../vendor/react-bits/SplitText"));

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

/** Staggered first-view enter: children rise 8 px in 40 ms steps. */
export function Reveal({ children, className }: { children: ReactNode; className?: string }) {
  const ok = useMotionOK();
  if (!ok) return <div className={className}>{children}</div>;
  return <Suspense fallback={<div className={className}>{children}</div>}><AnimatedContent className={className} trigger="mount" distance={8} duration={0.35} stagger={0.04} ease="power2.out">{children}</AnimatedContent></Suspense>;
}

/** Page title split-reveal by words, 250 ms, once. */
export function TitleReveal({ text, tag = "h1", id }: { text: string; tag?: "h1" | "h2"; id?: string }) {
  const ok = useMotionOK();
  if (!ok) return createElement(tag, { id }, text);
  return <Suspense fallback={createElement(tag, { id }, text)}><span id={id} className="title-reveal"><SplitText text={text} tag={tag} splitType="words" textAlign="left" trigger="load" duration={0.25} delay={40} effect="fade" /></span></Suspense>;
}
