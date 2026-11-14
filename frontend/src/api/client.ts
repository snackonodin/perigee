import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { TodayOut } from "./types";
import { tokens } from "./tokens";

const REFRESH_PATH = "/api/v1/auth/refresh";

let onUnauthorized: () => void = () => {};

const TODAY_PATH = "/api/v1/today";
const NIGHTS_PATH = "/api/v1/nights";

/** TODO(api): Keep an empty contract-shaped view while the API is unavailable. */
function todayUnavailableMock(): Response {
  const body: TodayOut & { context_engine: null } = {
    date: new Date().toISOString().slice(0, 10),
    baselines: [],
    checkins_consent: false,
    flags: [],
    latest_night: null,
    safety_screen_required: false,
    missing_safety_item: null,
    pending_checkins: [],
    sync_status: { state: "api_mock" },
    context_engine: null,
  };
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json", "X-TODO-API-Mock": "true" },
  });
}

/** TODO(api): Keep an empty contract-shaped night list while the API is unavailable. */
function nightsUnavailableMock(): Response {
  return new Response("[]", {
    status: 200,
    headers: { "Content-Type": "application/json", "X-TODO-API-Mock": "true" },
  });
}

function apiMockFor(req: Request): (() => Response) | undefined {
  if (req.method !== "GET") return undefined;
  const path=new URL(req.url).pathname;
  return path===TODAY_PATH?todayUnavailableMock:path===NIGHTS_PATH?nightsUnavailableMock:undefined;
}

/** AuthProvider registers what happens when a request stays 401 (session over). */
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

let refreshing: Promise<boolean> | null = null;

/** One refresh at a time: concurrent 401s share the same rotation. */
function refreshOnce(): Promise<boolean> {
  refreshing ??= (async () => {
    const rt = tokens.refresh;
    if (!rt) return false;
    try {
      const res = await fetch(new URL(REFRESH_PATH, window.location.origin), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) return false;
      tokens.set(await res.json());
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

/** Rotate the tokens (shared with concurrent callers). For streams that learn mid-stream
 *  that the token expired (SSE `bye: unauthorized`). */
export function refreshSession(): Promise<boolean> {
  return refreshOnce();
}

/** End the session: forget the tokens and hand over to AuthProvider (back to /login). */
export function endSession(): void {
  tokens.clear();
  onUnauthorized();
}

function withAuth(req: Request): Request {
  const r = new Request(req);
  const at = tokens.access;
  if (at) r.headers.set("Authorization", `Bearer ${at}`);
  return r;
}

/** fetch for openapi-fetch: bearer token, one refresh + retry on 401, then sign-out. */
export async function authFetch(input: Request): Promise<Response> {
  const isAuthRoute = new URL(input.url).pathname.startsWith("/api/v1/auth/");
  const mock = apiMockFor(input);
  const retry = input.clone();
  let res: Response;
  try {
    res = await fetch(withAuth(input));
  } catch (error) {
    if (mock) return mock();
    throw error;
  }
  if (mock && res.status >= 500) return mock();
  if (res.status !== 401 || isAuthRoute) return res;
  if (await refreshOnce()) {
    const again = await fetch(withAuth(retry));
    if (again.status !== 401) return again;
  }
  tokens.clear();
  onUnauthorized();
  return res;
}

// Same origin: the API serves this app. window.location.origin also gives tests (jsdom)
// absolute URLs.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: authFetch,
});

/** Human text for an API error body (ErrorOut) or a network failure. */
export function errorText(error: unknown, status?: number, retryAfter?: string | null): string {
  if (status === 429) {
    const mins = Math.max(1, Math.ceil(Number(retryAfter ?? 60) / 60));
    return `Too many failed sign-ins. Try again in about ${mins} minute${mins === 1 ? "" : "s"}.`;
  }
  const code = error && typeof error === "object" && "error" in error ? (error as { error: unknown }).error : undefined;
  if (code === "demo_full") return "The demo is full right now.";
  if (code === "signup_closed") return "Sign-ups are closed for this demo.";
  if (error && typeof error === "object" && "message" in error) {
    const e = error as { message: string; fields?: string[] };
    return e.fields?.length ? `Please check: ${e.fields.join(", ")}` : e.message;
  }
  return "Cannot reach the server. Is the API running?";
}
