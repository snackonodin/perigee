// A small Server-Sent Events parser (WHATWG "event stream interpretation"). Native
// EventSource cannot send an Authorization header, so the app reads the stream with
// fetch + ReadableStream and feeds the text here. Chunks may split anywhere: inside a
// line, inside a field name, between "\r" and "\n", or inside a multi-byte character
// (use feedBytes, which keeps a streaming TextDecoder).

export interface SseMessage {
  event: string; // "message" when the stream gave no event: field
  data: string;
  id: string | null; // the stream's last event id at dispatch time
}

export class SseParser {
  private buf = "";
  private data: string[] = [];
  private event = "";
  private decoder = new TextDecoder();
  /** Last `id:` seen (persists across messages, per spec). Send it as Last-Event-ID. */
  lastEventId: string | null = null;
  /** Reconnection delay requested by the server (`retry:`), in ms. */
  retryMs: number | null = null;
  /** Count of comment lines (": ping" heartbeats). */
  comments = 0;

  feedBytes(chunk: Uint8Array, final = false): SseMessage[] {
    return this.feed(this.decoder.decode(chunk, { stream: !final }));
  }

  feed(text: string): SseMessage[] {
    this.buf += text;
    const out: SseMessage[] = [];
    let start = 0;
    for (let i = 0; i < this.buf.length; i++) {
      const c = this.buf[i];
      if (c !== "\n" && c !== "\r") continue;
      // a "\r" at the very end may be the first half of "\r\n": wait for more input
      if (c === "\r" && i === this.buf.length - 1) break;
      this.line(this.buf.slice(start, i), out);
      if (c === "\r" && this.buf[i + 1] === "\n") i++;
      start = i + 1;
    }
    this.buf = this.buf.slice(start);
    return out;
  }

  private line(line: string, out: SseMessage[]): void {
    if (line === "") {
      if (this.data.length) out.push({ event: this.event || "message", data: this.data.join("\n"), id: this.lastEventId });
      this.data = [];
      this.event = "";
      return;
    }
    if (line.startsWith(":")) {
      this.comments++;
      return;
    }
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "data") this.data.push(value);
    else if (field === "event") this.event = value;
    else if (field === "id" && !value.includes("\0")) this.lastEventId = value;
    else if (field === "retry" && /^\d+$/.test(value)) this.retryMs = Number(value);
  }
}
