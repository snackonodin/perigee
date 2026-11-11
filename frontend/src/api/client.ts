import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { tokens } from "./tokens";

const REFRESH_PATH = "/api/v1/auth/refresh";

let onUnauthorized: () => void = () => {};

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

function withAuth(req: Request): Request {
  const r = new Request(req);
  const at = tokens.access;
  if (at) r.headers.set("Authorization", `Bearer ${at}`);
  return r;
}

/** fetch for openapi-fetch: bearer token, one refresh + retry on 401, then sign-out. */
export async function authFetch(input: Request): Promise<Response> {
  const isAuthRoute = new URL(input.url).pathname.startsWith("/api/v1/auth/");
  const retry = input.clone();
  const res = await fetch(withAuth(input));
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
  if (error && typeof error === "object" && "message" in error) {
    const e = error as { message: string; fields?: string[] };
    return e.fields?.length ? `Please check: ${e.fields.join(", ")}` : e.message;
  }
  return "Cannot reach the server. Is the API running?";
}
