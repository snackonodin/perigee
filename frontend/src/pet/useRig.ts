// Writes rig variables straight to the root element's style (no React state per frame).
import { useEffect, type RefObject } from "react";
import type { Rig } from "./behavior";

const VARS: Record<keyof Rig, string> = { mouth: "--mouth", squash: "--squash", earL: "--ear-l", earR: "--ear-r", blink: "--blink" };

export function setRig(el: HTMLElement | null, rig: Readonly<Partial<Rig>> | Readonly<Record<string, number>>) {
  if (!el) return;
  for (const [k, v] of Object.entries(rig)) {
    const name = (VARS as Record<string, string>)[k] ?? (k.startsWith("--") ? k : `--${k}`);
    el.style.setProperty(name, String(v ?? 0));
  }
}

export function useRig(ref: RefObject<HTMLElement | null>, rig: Rig) {
  useEffect(() => { setRig(ref.current, rig); }, [ref, rig]);
}
