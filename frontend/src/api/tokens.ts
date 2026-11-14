// Access/refresh tokens live in sessionStorage: gone when the tab closes. Every access is
// wrapped so private mode (storage throws) still works, just without persistence.
const ACCESS = "ahm.access";
const REFRESH = "ahm.refresh";
// A demo visitor's refresh token also lives in localStorage so a return visit (new tab) reuses
// the same private demo copy instead of creating another one (the demo has a visitor cap).
// Only ever a synthetic demo account: a normal sign-in removes it.
const DEMO_REFRESH = "ahm.demo.refresh";

function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeLocal(key: string, value: string | null): void {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: the demo copy lasts as long as this tab */
  }
}

function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch {
    /* storage unavailable: tokens live only in this page */
  }
}

export const tokens = {
  get access(): string | null {
    return read(ACCESS);
  },
  get refresh(): string | null {
    return read(REFRESH) ?? readLocal(DEMO_REFRESH);
  },
  /** True when the current tokens belong to a demo visitor copy. */
  get demo(): boolean {
    return readLocal(DEMO_REFRESH) !== null;
  },
  /** kind: "demo" or "account" on sign-in; omitted on a refresh rotation (keeps the current kind). */
  set(t: { access_token: string; refresh_token: string }, kind?: "demo" | "account"): void {
    write(ACCESS, t.access_token);
    write(REFRESH, t.refresh_token);
    if (kind === "account") writeLocal(DEMO_REFRESH, null);
    else if (kind === "demo" || readLocal(DEMO_REFRESH) !== null) writeLocal(DEMO_REFRESH, t.refresh_token);
  },
  clear(): void {
    write(ACCESS, null);
    write(REFRESH, null);
    writeLocal(DEMO_REFRESH, null);
  },
};
