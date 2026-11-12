import { describe, expect, it } from "vitest";
import { type SseMessage, SseParser } from "./sse";

// Exactly what backend/services/live.py writes, plus a heartbeat and CRLF line endings.
const STREAM =
  'event: hello\ndata: {"mode":"live","poll_s":2}\n\n' +
  ": ping\n\n" +
  'id: 12-3\r\nevent: window\r\ndata: {"rr_a":14.2,"note":"µ°✓"}\r\n\r\n' +
  'id: 12-4\nevent: heart\ndata: {"hr_bpm":61}\n\n' +
  'event: bye\ndata: {"reason":"max_s"}\n\n';

const EXPECTED: SseMessage[] = [
  { event: "hello", data: '{"mode":"live","poll_s":2}', id: null },
  { event: "window", data: '{"rr_a":14.2,"note":"µ°✓"}', id: "12-3" },
  { event: "heart", data: '{"hr_bpm":61}', id: "12-4" },
  { event: "bye", data: '{"reason":"max_s"}', id: "12-4" }, // id persists until changed
];

describe("SseParser", () => {
  it("parses a whole stream", () => {
    const p = new SseParser();
    expect(p.feed(STREAM)).toEqual(EXPECTED);
    expect(p.lastEventId).toBe("12-4");
    expect(p.comments).toBe(1);
  });

  it("gives the same messages for a 2-chunk split at EVERY position (mid-line, mid-field, inside CRLF)", () => {
    for (let i = 0; i <= STREAM.length; i++) {
      const p = new SseParser();
      const got = [...p.feed(STREAM.slice(0, i)), ...p.feed(STREAM.slice(i))];
      expect(got, `split at ${i}`).toEqual(EXPECTED);
    }
  });

  it("handles one character per chunk", () => {
    const p = new SseParser();
    expect([...STREAM].flatMap((c) => p.feed(c))).toEqual(EXPECTED);
  });

  it("handles bytes split inside multi-byte UTF-8 characters", () => {
    const bytes = new TextEncoder().encode(STREAM);
    for (const size of [1, 2, 3, 5, 7]) {
      const p = new SseParser();
      const got: SseMessage[] = [];
      for (let i = 0; i < bytes.length; i += size) got.push(...p.feedBytes(bytes.slice(i, i + size)));
      expect(got, `byte chunks of ${size}`).toEqual(EXPECTED);
    }
  });

  it("joins multi-line data, ignores events without data, unknown fields and bad retry", () => {
    const p = new SseParser();
    const out = p.feed("event: x\n\ndata: a\ndata: b\nfoo: bar\nretry: soon\n\nretry: 2500\ndata:no-space\n\n");
    expect(out).toEqual([
      { event: "message", data: "a\nb", id: null },
      { event: "message", data: "no-space", id: null },
    ]);
    expect(p.retryMs).toBe(2500);
  });

  it("keeps an incomplete trailing message until its blank line arrives", () => {
    const p = new SseParser();
    expect(p.feed('event: window\ndata: {"a":1}\n')).toEqual([]);
    expect(p.feed("\n")).toEqual([{ event: "window", data: '{"a":1}', id: null }]);
  });
});
