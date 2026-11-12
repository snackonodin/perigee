import { useEffect, useRef, useState } from "react";
import { trimTo } from "./decimate";
import { runVitals, type StreamStatus } from "./stream";
import type { HeartEvent, HelloLive, HelloReplay, WindowEvent } from "./types";

export const KEEP_EVENTS = 2000; // raw events kept per series (oldest dropped)
export const MAX_FPS = 30;

export interface Vitals {
  status: StreamStatus;
  hello: HelloLive | HelloReplay | null;
  windows: readonly WindowEvent[];
  hearts: readonly HeartEvent[];
  version: number; // bumps on each rendered frame
}

export type Mode = { kind: "live" } | { kind: "replay"; sessionId: string; speed: number };

/** Subscribe to /live/vitals. Events are buffered in refs and React re-renders at most
 *  MAX_FPS times a second, however fast a replay streams. */
export function useVitals(mode: Mode): Vitals {
  const windows = useRef<WindowEvent[]>([]);
  const hearts = useRef<HeartEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>({ state: "connecting" });
  const [hello, setHello] = useState<HelloLive | HelloReplay | null>(null);
  const [version, setVersion] = useState(0);
  const key = mode.kind === "live" ? "live" : `replay:${mode.sessionId}:${mode.speed}`;

  useEffect(() => {
    const ctl = new AbortController();
    windows.current = [];
    hearts.current = [];
    setHello(null);
    setVersion((v) => v + 1);
    let pending = false;
    let lastFrame = 0;
    let raf = 0;
    const frame = () => {
      raf = 0;
      const now = performance.now();
      if (now - lastFrame < 1000 / MAX_FPS) {
        raf = requestAnimationFrame(frame);
        return;
      }
      lastFrame = now;
      pending = false;
      setVersion((v) => v + 1);
    };
    const schedule = () => {
      if (!pending) {
        pending = true;
        raf = requestAnimationFrame(frame);
      }
    };
    void runVitals({
      replay: mode.kind === "replay" ? { sessionId: mode.sessionId, speed: mode.speed } : undefined,
      signal: ctl.signal,
      onStatus: setStatus,
      onEvent: (e) => {
        if (e.type === "hello") {
          // a replay cannot resume: a (re)started replay begins again from its first event
          if (e.data.mode === "replay") {
            windows.current = [];
            hearts.current = [];
          }
          setHello(e.data);
        } else if (e.type === "window") {
          windows.current.push(e.data);
          trimTo(windows.current, KEEP_EVENTS);
        } else if (e.type === "heart") {
          hearts.current.push(e.data);
          trimTo(hearts.current, KEEP_EVENTS);
        }
        schedule();
      },
    });
    return () => {
      ctl.abort();
      if (raf) cancelAnimationFrame(raf);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { status, hello, windows: windows.current, hearts: hearts.current, version };
}
