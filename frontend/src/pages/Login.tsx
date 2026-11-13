import { type FormEvent, useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { useAuth } from "../auth/AuthProvider";

export function Login() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [signup, setSignup] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fogRef=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const host=fogRef.current;
    if(!host||!window.matchMedia||!window.matchMedia("(min-width: 768px)").matches||window.matchMedia("(prefers-reduced-motion: reduce)").matches)return;
    let effect:{destroy:()=>void}|undefined,disposed=false;
    // Vanta ships without TypeScript declarations; the dynamic import keeps its renderer lazy.
    // @ts-expect-error Vanta's distribution has no declaration file.
    const vantaImport=import("vanta/dist/vanta.fog.min.js");
    // @ts-expect-error Three r134 has no bundled declaration file.
    const threeImport=import("three");
    void Promise.all([threeImport,vantaImport]).then(([three,vanta])=>{
      if(disposed||!host)return;
      const create=(vanta.default??vanta) as (options:Record<string,unknown>)=>{destroy:()=>void};
      const color=(name:string)=>Number(`0x${getComputedStyle(document.documentElement).getPropertyValue(name).trim().replace("#","")}`);
      effect=create({el:host,THREE:three.default??three,highlightColor:color("--mint"),midtoneColor:color("--sky"),lowlightColor:color("--lavender"),baseColor:color("--bg"),speed:0.6});
      host.dataset.vanta="true";
    }).catch(()=>undefined);
    return()=>{disposed=true;effect?.destroy();if(host)delete host.dataset.vanta;};
  },[]);

  if (status === "signed-in") return <Navigate to={from} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const err = await login(email.trim(), password, signup);
    setBusy(false);
    if (err) setError(err);
    else navigate(from, { replace: true });
  }

  return (
    <div className="login-layout">
      <div className="aurora-backdrop" aria-hidden="true"><i/><i/><i/><i/></div>
      <main className="login-main">
       <div ref={fogRef} className="login-fog" aria-hidden="true" />
       <section className="panel login-card glass" aria-labelledby="login-title">
        <p className="eyebrow">Private health companion</p>
        <h1 id="login-title">{signup ? "Create your account" : "Welcome back"}</h1>
        <p className="login-subtitle">{signup ? "Set up your private crew profile." : "Sign in to continue to your personal log."}</p>
        <form onSubmit={submit}>
          <label>
            Email
            <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Password
            <input
              type="password"
              required
              minLength={signup ? 10 : undefined}
              autoComplete={signup ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button type="submit" disabled={busy}>
            {signup ? "Create account" : "Sign in"}
          </button>
          <p className="error" role="alert">
            {error}
          </p>
        </form>
        <p className="login-toggle">{signup ? "Already have a profile?" : "New to Perigee?"} <button type="button" className="link" onClick={() => setSignup(!signup)}>{signup ? "Sign in" : "Create an account"}</button></p>
        <p className="login-privacy"><span aria-hidden="true">◈</span> Your personal signals stay in your account.</p>
      </section>
      </main>
    </div>
  );
}
