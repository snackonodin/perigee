import { type FormEvent, useState } from "react";
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
      <aside className="login-scene" aria-label="A quiet view of the spacecraft beyond Earth">
        <a className="login-brand" href="/" aria-label="Perigee home"><span className="brand-mark" aria-hidden="true">✦</span>Perigee</a>
        <svg className="login-orbit-art" viewBox="0 0 520 420" role="img" aria-labelledby="scene-title scene-desc">
          <title id="scene-title">A small spacecraft in orbit</title><desc id="scene-desc">An original line illustration of a crew capsule, planet, stars, and orbital paths.</desc>
          <circle className="scene-planet" cx="325" cy="198" r="104"/><path className="scene-planet-line" d="M230 180c62 22 119 16 188-13M242 225c62 14 109 10 162-9"/>
          <ellipse className="scene-orbit" cx="268" cy="208" rx="218" ry="115" transform="rotate(-22 268 208)"/>
          <g className="scene-capsule" transform="translate(80 150) rotate(-18)"><path d="M0 26 42 4l52 2 23 21-23 21-52 2Z"/><circle cx="51" cy="27" r="13"/><path d="m95 8 24-13v64L95 46M17 16 5 4M17 38 5 50"/></g>
          <g className="scene-stars" aria-hidden="true"><path d="M105 70v14m-7-7h14M410 95v16m-8-8h16M422 300v12m-6-6h12M130 306v10m-5-5h10"/><circle cx="374" cy="63" r="2"/><circle cx="60" cy="245" r="2"/><circle cx="444" cy="210" r="2"/></g>
        </svg>
        <div className="login-scene-copy"><p className="eyebrow">A little room to reset</p><h2>Your rhythm,<br/>in your own context.</h2><p>Private, personal reflections for life aboard.</p></div>
        <span className="scene-caption">PERSONAL LOG · 28-NIGHT WINDOW</span>
      </aside>
      <main className="login-main">
       <section className="panel login-card" aria-labelledby="login-title">
        <p className="eyebrow">Crew quarters · secure access</p>
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
