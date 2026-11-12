import { authFetch, endSession, refreshSession } from "../api/client";
import type { LiveEvent } from "./types";
import { SseParser } from "./sse";

export const VITALS_PATH = "/api/v1/live/vitals";

export type StreamState = "connecting" | "open" | "reconnecting" | "ended" | "error" | "stopped";
export interface StreamStatus {
  state: StreamState;
  detail?: string;
  attempt?: number;
}

export interface VitalsOptions {
  /** Replay one of the caller's sessions instead of the live tail. */
  replay?: { sessionId: string; speed: number };
  onEvent(e: LiveEvent): void;
  onStatus(s: StreamStatus): void;
  signal: AbortSignal;
  /** Injectable for tests. */
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

const BACKOFF_MS = [1000, 2000, 4000, 8000, 15000, 30000];

function defaultSleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const t = window.setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      window.clearTimeout(t);
      resolve();
    });
  });
}

function parse(type: string, data: string): LiveEvent | null {
  if (!["hello", "window", "heart", "bye", "end"].includes(type)) return null;
  try {
    return { type, data: JSON.parse(data) } as LiveEvent;
  } catch {
    return null;
  }
}

/**
 * Read /live/vitals until aborted (live) or `end` (replay).
 * - Bearer auth through authFetch (one refresh on 401), never a token in the URL.
 * - Live: reconnect with Last-Event-ID so nothing is lost or repeated; `bye: max_s` →
 *   reconnect at once; a dropped connection → exponential backoff; `bye: unauthorized`
 *   → refresh the token, then reconnect (or sign out if that fails).
 * - Replay: runs once from the start; `end` finishes it.
 */
export async function runVitals(opts: VitalsOptions): Promise<void> {
  const { signal, onEvent, onStatus } = opts;
  const sleep = opts.sleep ?? defaultSleep;
  let lastId: string | null = null;
  let attempt = 0;

  while (!signal.aborted) {
    onStatus({ state: attempt === 0 ? "connecting" : "reconnecting", attempt });
    const url = new URL(VITALS_PATH, window.location.origin);
    if (opts.replay) {
      url.searchParams.set("replay_session", opts.replay.sessionId);
      url.searchParams.set("speed", String(opts.replay.speed));
    }
    const headers: Record<string, string> = { Accept: "text/event-stream" };
    if (lastId && !opts.replay) headers["Last-Event-ID"] = lastId;

    let res: Response;
    try {
      res = await authFetch(new Request(url, { headers, signal }));
    } catch {
      if (signal.aborted) break;
      await sleep(BACKOFF_MS[Math.min(attempt++, BACKOFF_MS.length - 1)], signal);
      continue;
    }
    if (res.status === 401) {
      onStatus({ state: "error", detail: "signed out" }); // authFetch already tried a refresh
      return;
    }
    if (!res.ok || !res.body) {
      const body = await res.json().catch(() => null);
      const detail = (body && typeof body === "object" && "message" in body && String(body.message)) || `HTTP ${res.status}`;
      if (res.status >= 400 && res.status < 500) {
        onStatus({ state: "error", detail }); // e.g. replay of a session that is not yours
        return;
      }
      await sleep(BACKOFF_MS[Math.min(attempt++, BACKOFF_MS.length - 1)], signal);
      continue;
    }

    const parser = new SseParser();
    const reader = res.body.getReader();
    let next: "reconnect-now" | "backoff" | "refresh" | "done" = "backoff";
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const m of parser.feedBytes(value)) {
          const ev = parse(m.event, m.data);
          if (!ev) continue;
          if (m.id !== null && !opts.replay) lastId = m.id;
          if (ev.type === "hello") {
            attempt = 0;
            onStatus({ state: "open" });
          }
          if (ev.type === "bye") next = ev.data.reason === "unauthorized" ? "refresh" : "reconnect-now";
          if (ev.type === "end") next = "done";
          onEvent(ev);
        }
      }
    } catch {
      if (signal.aborted) break; // reader aborted by us
    } finally {
      reader.releaseLock();
    }

    if (next === "done") {
      onStatus({ state: "ended" });
      return;
    }
    if (next === "refresh") {
      if (!(await refreshSession())) {
        endSession();
        onStatus({ state: "error", detail: "signed out" });
        return;
      }
      continue;
    }
    if (next === "backoff") await sleep(BACKOFF_MS[Math.min(attempt++, BACKOFF_MS.length - 1)], signal);
  }
  onStatus({ state: "stopped" });
}
