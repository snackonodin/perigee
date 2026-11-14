// Pointer + keyboard -> behavior events. Tap: up < 300 ms and moved < 8 px. Long press
// >= 600 ms: petting until release. Enter = tap; Space held 600 ms = petting.
import { useMemo, useRef } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import type { BehaviorEvent } from "./behavior";
import { LONG_PRESS_MS, TAP_MAX_MOVE_PX, TAP_MAX_MS } from "./petConfig";
import type { Scheduler } from "./scheduler";

export function useInteractions(scheduler: Scheduler, dispatch: (e: BehaviorEvent) => void, onTap: () => void) {
  const g = useRef({ t0: 0, x0: 0, y0: 0, moved: false, pressing: false, cancel: () => {} });
  return useMemo(() => {
    const start = () => {
      const s = g.current;
      s.pressing = false; s.moved = false; s.t0 = Date.now(); s.cancel();
      s.cancel = scheduler.after(LONG_PRESS_MS, () => { s.pressing = true; dispatch({ type: "pressStart" }); });
    };
    const finish = (isTap: boolean) => {
      const s = g.current;
      s.cancel(); s.cancel = () => {};
      if (s.pressing) { s.pressing = false; dispatch({ type: "pressEnd" }); return; }
      if (isTap) { dispatch({ type: "tap" }); onTap(); }
    };
    return {
      onPointerDown(e: PointerEvent) { g.current.x0 = e.clientX; g.current.y0 = e.clientY; start(); },
      onPointerMove(e: PointerEvent) {
        const s = g.current;
        if (!s.moved && Math.hypot(e.clientX - s.x0, e.clientY - s.y0) >= TAP_MAX_MOVE_PX) { s.moved = true; if (!s.pressing) { s.cancel(); s.cancel = () => {}; } }
      },
      onPointerUp() { const s = g.current; finish(!s.moved && Date.now() - s.t0 < TAP_MAX_MS); },
      onPointerCancel() { finish(false); },
      onPointerLeave() { if (g.current.pressing) finish(false); },
      onKeyDown(e: KeyboardEvent) {
        if (e.key === "Enter") { e.preventDefault(); if (!e.repeat) { dispatch({ type: "tap" }); onTap(); } }
        if (e.key === " ") { e.preventDefault(); if (!e.repeat) start(); }
      },
      onKeyUp(e: KeyboardEvent) { if (e.key === " ") { e.preventDefault(); finish(true); } },
      onClick(e: { preventDefault(): void }) { e.preventDefault(); },
    };
  }, [scheduler, dispatch, onTap]);
}
