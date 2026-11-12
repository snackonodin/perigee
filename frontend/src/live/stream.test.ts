import { describe, expect, it, vi } from "vitest";
import { setUnauthorizedHandler } from "../api/client";
import { signIn } from "../test/mockApi";
import { runVitals, type StreamStatus } from "./stream";
import type { LiveEvent } from "./types";

const ev = (event: string, data: object, id?: string) =>
  `${id ? `id: ${id}\n` : ""}event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const HELLO = ev("hello", { mode: "live", poll_s: 2, heartbeat_s: 15, max_s: 300 });
const win = (rr: number, id: string) =>
  ev("window", { session_id: "s", t_start: `2026-11-11T00:0${rr - 10}:00Z`, t_end: "x", rr_a: rr, rr_b: rr, pnr_db: 6, quality: 0.9, motion: false, motion_score: null, presence: true }, id);

/** A streaming response whose body yields the given chunks (split mid-message on purpose). */
function sse(chunks: string[]): Response {
  const enc = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(c) {
        for (const ch of chunks) c.enqueue(enc.encode(ch));
        c.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

interface Seen {
  url: URL;
  lastEventId: string | null;
  auth: string | null;
}

function harness(replies: ((req: Request) => Response | Promise<Response>)[], ctl = new AbortController()) {
  const seen: Seen[] = [];
  const refreshes: unknown[] = [];
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input instanceof Request ? input : new Request(input, init);
      const url = new URL(req.url);
      if (url.pathname === "/api/v1/auth/refresh") {
        refreshes.push(JSON.parse(await req.text()));
        return refreshReply();
      }
      seen.push({ url, lastEventId: req.headers.get("Last-Event-ID"), auth: req.headers.get("Authorization") });
      const r = replies[n++];
      if (!r) {
        ctl.abort(); // test ends when the scripted replies run out
        throw new DOMException("aborted", "AbortError");
      }
      return r(req);
    }),
  );
  let refreshReply = () => new Response(JSON.stringify({ access_token: "at-2", refresh_token: "rt-2" }), { status: 200 });
  const events: LiveEvent[] = [];
  const statuses: StreamStatus[] = [];
  const sleeps: number[] = [];
  const run = (replay?: { sessionId: string; speed: number }) =>
    runVitals({
      replay,
      signal: ctl.signal,
      onEvent: (e) => events.push(e),
      onStatus: (s) => statuses.push(s),
      sleep: async (ms) => {
        sleeps.push(ms);
      },
    });
  return { seen, refreshes, events, statuses, sleeps, run, setRefresh: (f: () => Response) => (refreshReply = f) };
}

describe("runVitals (live)", () => {
  it("bye max_s → reconnects at once with Last-Event-ID; nothing lost or repeated", async () => {
    signIn("at-1", "rt-1");
    const h = harness([
      () => sse([HELLO, win(14, "1-0").slice(0, 25), win(14, "1-0").slice(25), ev("bye", { reason: "max_s" }, "1-0")]),
      () => sse([HELLO, win(15, "2-0")]),
    ]);
    await h.run();
    expect(h.seen.map((s) => s.lastEventId)).toEqual([null, "1-0", "2-0"]);
    expect(h.seen[0].auth).toBe("Bearer at-1");
    const rr = h.events.filter((e) => e.type === "window").map((e) => (e.data as { rr_a: number }).rr_a);
    expect(rr).toEqual([14, 15]);
    expect(h.sleeps[0]).toBe(1000); // only the drop after the 2nd stream (no bye) backs off
    expect(h.seen[0].url.searchParams.toString()).toBe(""); // no token or anything in the URL
  });

  it("a dropped connection backs off exponentially, resetting after a good hello", async () => {
    signIn();
    const h = harness([
      () => new Response("down", { status: 503 }),
      () => new Response("down", { status: 503 }),
      () => sse([HELLO]),
      () => new Response("down", { status: 503 }),
    ]);
    await h.run();
    expect(h.sleeps).toEqual([1000, 2000, 1000, 2000]);
    expect(h.statuses.map((s) => s.state)).toContain("reconnecting");
  });

  it("bye unauthorized → refreshes the token, then reconnects with the new one", async () => {
    signIn("at-1", "rt-1");
    const h = harness([() => sse([HELLO, ev("bye", { reason: "unauthorized" })]), () => sse([HELLO])]);
    await h.run();
    expect(h.refreshes).toEqual([{ refresh_token: "rt-1" }]);
    expect(h.seen[1].auth).toBe("Bearer at-2");
  });

  it("bye unauthorized and the refresh fails → signs out and stops", async () => {
    signIn("at-1", "rt-1");
    const out = vi.fn();
    setUnauthorizedHandler(out);
    const h = harness([() => sse([HELLO, ev("bye", { reason: "unauthorized" })])]);
    h.setRefresh(() => new Response("{}", { status: 401 }));
    await h.run();
    expect(out).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("ahm.access")).toBeNull();
    expect(h.statuses.at(-1)).toEqual({ state: "error", detail: "signed out" });
    expect(h.seen).toHaveLength(1);
    setUnauthorizedHandler(() => {});
  });
});

describe("runVitals (replay)", () => {
  it("sends replay_session and speed, never Last-Event-ID, and stops at end", async () => {
    signIn();
    const h = harness([
      () =>
        sse([
          ev("hello", { mode: "replay", session_id: "sess-1", speed: 600, events: 1 }),
          win(14, "1"),
          ev("end", { events: 1 }),
        ]),
    ]);
    await h.run({ sessionId: "sess-1", speed: 600 });
    expect(h.seen).toHaveLength(1);
    expect(h.seen[0].url.searchParams.get("replay_session")).toBe("sess-1");
    expect(h.seen[0].url.searchParams.get("speed")).toBe("600");
    expect(h.seen[0].lastEventId).toBeNull();
    expect(h.statuses.at(-1)).toEqual({ state: "ended" });
  });

  it("a 404 (not your session) stops with the server's message, no retry", async () => {
    signIn();
    const h = harness([
      () => new Response(JSON.stringify({ error: "not_found", message: "unknown session" }), { status: 404 }),
    ]);
    await h.run({ sessionId: "nope", speed: 10 });
    expect(h.seen).toHaveLength(1);
    expect(h.statuses.at(-1)).toEqual({ state: "error", detail: "unknown session" });
  });
});
