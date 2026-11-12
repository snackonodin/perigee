import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { api, errorText, setUnauthorizedHandler } from "../api/client";
import { tokens } from "../api/tokens";
import type { MeOut } from "../api/types";

type Status = "checking" | "signed-in" | "signed-out";

interface AuthState {
  status: Status;
  me: MeOut | null;
  /** Returns an error message, or null on success. */
  login(email: string, password: string, signup?: boolean): Promise<string | null>;
  logout(): Promise<void>;
  reloadMe(): Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState<Status>(tokens.access || tokens.refresh ? "checking" : "signed-out");
  const [me, setMe] = useState<MeOut | null>(null);

  const signedOut = useCallback(() => {
    tokens.clear();
    setMe(null);
    setStatus("signed-out");
  }, []);

  const reloadMe = useCallback(async () => {
    const { data } = await api.GET("/api/v1/me");
    if (data) {
      setMe(data);
      setStatus("signed-in");
    } else {
      signedOut();
    }
  }, [signedOut]);

  // A request that stays 401 after a refresh attempt ends the session: back to login.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      signedOut();
      navigate("/login", { replace: true });
    });
    return () => setUnauthorizedHandler(() => {});
  }, [navigate, signedOut]);

  useEffect(() => {
    if (status === "checking") void reloadMe();
  }, [status, reloadMe]);

  const login = useCallback(
    async (email: string, password: string, signup = false) => {
      const body = { email, password };
      const { data, error, response } = signup
        ? await api.POST("/api/v1/auth/signup", { body })
        : await api.POST("/api/v1/auth/login", { body });
      if (!data) return errorText(error, response?.status, response?.headers.get("Retry-After"));
      tokens.set(data);
      await reloadMe();
      return null;
    },
    [reloadMe],
  );

  const logout = useCallback(async () => {
    const rt = tokens.refresh;
    signedOut();
    if (rt) await api.POST("/api/v1/auth/logout", { body: { refresh_token: rt } }).catch(() => {});
    navigate("/login", { replace: true });
  }, [navigate, signedOut]);

  const value = useMemo(() => ({ status, me, login, logout, reloadMe }), [status, me, login, logout, reloadMe]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/** Renders children only when signed in; otherwise redirects to /login. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "checking") return <p className="muted shell">Loading…</p>;
  if (status === "signed-out") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}
