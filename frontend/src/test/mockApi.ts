import { vi } from "vitest";

export interface Reply {
  /** A ready-made Response (e.g. a text/event-stream body); wins over the fields below. */
  response?: Response;
  status?: number;
  body?: unknown;
  headers?: Record<string, string>;
}
type Handler = Reply | ((call: Call) => Reply | Promise<Reply>);
export interface Call {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
  auth: string | null;
}

/** Stub global fetch under the real openapi-fetch client + authFetch. Keys: "GET /api/v1/x";
 *  a key may end in "*" to match a prefix. Unknown routes answer 404 ErrorOut. */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Call[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input instanceof Request ? input : new Request(input, init);
    const url = new URL(req.url);
    const text = await req.text();
    const call: Call = {
      method: req.method,
      path: url.pathname,
      query: url.searchParams,
      body: text ? JSON.parse(text) : undefined,
      auth: req.headers.get("Authorization"),
    };
    calls.push(call);
    const key = `${call.method} ${call.path}`;
    const match =
      routes[key] ??
      Object.entries(routes).find(([k]) => k.endsWith("*") && key.startsWith(k.slice(0, -1)))?.[1];
    const reply: Reply = !match
      ? { status: 404, body: { error: "not_found", message: `no mock for ${key}` } }
      : typeof match === "function"
        ? await match(call)
        : match;
    if (reply.response) return reply.response;
    const status = reply.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(reply.body ?? null), {
      status,
      headers: { "Content-Type": "application/json", ...reply.headers },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock, called: (key: string) => calls.filter((c) => `${c.method} ${c.path}` === key) };
}

export function signIn(access = "at-1", refresh = "rt-1"): void {
  sessionStorage.setItem("ahm.access", access);
  sessionStorage.setItem("ahm.refresh", refresh);
}
