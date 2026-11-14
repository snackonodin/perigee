import { type FormEvent, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { BRAND } from "../brand";
import { Icon } from "../components/icons";
import "./Login.css";
import { DemoChoice, type DemoBody } from "./DemoChoice";

export function Login({ signup = false }: { signup?: boolean }) {
  const { status, login, demo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demoBusy, setDemoBusy] = useState<"crew" | "profile" | null>(null);
  // signed-out visitors see the demo choice first; the sign-in form is one link away
  const [accountView, setAccountView] = useState(false);
  const [checkingSetup, setCheckingSetup] = useState(false);
  // Hidden once the server says the public demo is off (404/405), for the rest of this tab.
  const [demoOff, setDemoOff] = useState(() => { try { return sessionStorage.getItem("demo.off") === "1"; } catch { return false; } });
  const fogRef = useRef<HTMLDivElement>(null);
  const demoLanding = useRef(false);

  useEffect(() => {
    const host = fogRef.current;
    if (!host || !window.matchMedia || !window.matchMedia("(min-width: 768px)").matches || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let effect: { destroy: () => void } | undefined;
    let disposed = false;
    // Vanta ships without TypeScript declarations; dynamic imports keep it sign-in-only and lazy.
    // @ts-expect-error Vanta's distribution has no declaration file.
    const vantaImport = import("vanta/dist/vanta.fog.min.js");
    // @ts-expect-error Three r134 has no bundled declaration file.
    const threeImport = import("three");
    void Promise.all([threeImport, vantaImport]).then(([three, vanta]) => {
      if (disposed || !host) return;
      const create = (vanta.default ?? vanta) as (options: Record<string, unknown>) => { destroy: () => void };
      const color = (name: string) => Number(`0x${getComputedStyle(document.documentElement).getPropertyValue(name).trim().replace("#", "")}`);
      effect = create({ el: host, THREE: three.default ?? three, highlightColor: color("--mint"), midtoneColor: color("--sky"), lowlightColor: color("--lavender"), baseColor: color("--bg"), speed: 0.6 });
      host.dataset.vanta = "true";
    }).catch(() => undefined);
    return () => { disposed = true; effect?.destroy(); if (host) delete host.dataset.vanta; };
  }, []);

  useEffect(() => {
    if (status !== "signed-in") return;
    let active = true;
    setCheckingSetup(true);
    void (async () => {
      let setupDone = false;
      try { setupDone = window.localStorage.getItem("setup.done") === "true"; } catch { /* use baseline response below */ }
      if (!setupDone) {
        try {
          const { data } = await api.GET("/api/v1/today");
          if (data?.baselines?.length) {
            try { window.localStorage.setItem("setup.done", "true"); } catch { /* baseline remains the source of truth */ }
            setupDone = true;
          }
        } catch { /* no available baseline means continue through first-run setup */ }
      }
      if (active) {
        navigate(demoLanding.current ? "/" : setupDone ? from : "/setup", { replace: true });
        setCheckingSetup(false);
      }
    })();
    return () => { active = false; };
  }, [status, from, navigate]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const message = await login(email.trim(), password, signup);
    setBusy(false);
    if (message) setError(message);
  }

  // A server that says demo access is off (health.demo === false) skips the choice up front.
  useEffect(() => {
    let live = true;
    fetch(new URL("/api/v1/health", window.location.origin)).then((r) => r.json()).then((h: { demo?: boolean }) => {
      if (live && h?.demo === false) setDemoOff(true);
    }).catch(() => { /* unknown: keep the choice; a 404 on choosing falls back to sign-in */ });
    return () => { live = false; };
  }, []);

  async function tryDemo(body?: DemoBody, kind: "crew" | "profile" = "crew") {
    setBusy(true);
    setDemoBusy(kind);
    setError(null);
    demoLanding.current = true;
    const message = await demo(body);
    setBusy(false);
    setDemoBusy(null);
    if (message === "unavailable") {
      setDemoOff(true);
      try { sessionStorage.setItem("demo.off", "1"); } catch { /* hidden for this render only */ }
      demoLanding.current = false;
    } else if (message) { setError(message); demoLanding.current = false; }
  }

  if (!signup && !demoOff && !accountView) return (
    <div className="login-layout demo-layout">
      <div className="aurora-backdrop" aria-hidden="true"><i /><i /><i /><i /></div>
      <DemoChoice busy={demoBusy} error={error} onChoose={(b, k) => void tryDemo(b, k)} onAccount={() => { setError(null); setAccountView(true); }} />
    </div>
  );

  return (
    <div className="login-layout auth-layout">
      <div className="aurora-backdrop" aria-hidden="true"><i /><i /><i /><i /></div>
      <div className="auth-scene" aria-hidden="true"><div ref={fogRef} className="login-fog auth-fog" /><div className="auth-scene-copy"><span className="auth-orbit"><i className="auth-planet"/><span className="satellite spin" style={{"--sat-r":"64px","--sat-period":"18s"} as React.CSSProperties}/></span><p>Your nights, understood.</p><span>Gentle insights for your wellbeing.</span></div></div>
      <main className="login-main auth-main">
        <section className="panel login-card glass auth-card" aria-labelledby="login-title">
          <p className="auth-brand"><span className="brand-mark" aria-hidden="true"><Icon name="brand" size={22}/></span>{BRAND}</p>
          <h1 id="login-title">{signup ? "Create your account" : "Welcome back"}</h1>
          <p className="login-subtitle">{signup ? "Start your private wellbeing log." : "Sign in to continue to your personal log."}</p>
          <form onSubmit={submit}>
            <label>Email<input type="email" required autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
            <label>Password<input type="password" required minLength={signup ? 10 : undefined} autoComplete={signup ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            <button type="submit" disabled={busy || checkingSetup}>{busy ? (signup ? "Creating account…" : "Signing in…") : (signup ? "Create account" : "Sign in")}</button>
            <p className="error" role="alert">{error}</p>
          </form>
          {!signup && !demoOff && (
            <button type="button" className="login-demo" disabled={busy || checkingSetup} onClick={() => { setError(null); setAccountView(false); }}>Back to the demo</button>
          )}
          <p className="login-toggle">{signup ? "Already have an account?" : `New to ${BRAND}?`} <button type="button" className="link" onClick={() => navigate(signup ? "/login" : "/register")}>{signup ? "Sign in" : "Create an account"}</button></p>
          <p className="login-privacy"><span aria-hidden="true">◈</span> Your personal signals stay in your account.</p>
        </section>
      </main>
    </div>
  );
}
