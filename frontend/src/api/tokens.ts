// Access/refresh tokens live in sessionStorage: gone when the tab closes. Every access is
// wrapped so private mode (storage throws) still works, just without persistence.
const ACCESS = "ahm.access";
const REFRESH = "ahm.refresh";

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
    return read(REFRESH);
  },
  set(t: { access_token: string; refresh_token: string }): void {
    write(ACCESS, t.access_token);
    write(REFRESH, t.refresh_token);
  },
  clear(): void {
    write(ACCESS, null);
    write(REFRESH, null);
  },
};
