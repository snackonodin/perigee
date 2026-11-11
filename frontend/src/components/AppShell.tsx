import { NavLink, Outlet } from "react-router";
import { useAuth } from "../auth/AuthProvider";
import { TABS } from "../routes/tabs";

export function AppShell() {
  const { me, logout } = useAuth();
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Astronaut Health Monitor</span>
        {me?.is_synthetic && <span className="badge">Synthetic data</span>}
        <span className="spacer" />
        <span className="muted who">{me?.display_name || me?.email}</span>
        <button type="button" className="ghost" onClick={() => void logout()}>Log out</button>
      </header>
      <nav className="tabs" aria-label="Sections">
        {TABS.map((t) => (
          <NavLink key={t.path} to={t.path} end={t.path === "/"} className="tab">
            {t.label}
          </NavLink>
        ))}
      </nav>
      <main>
        <Outlet />
      </main>
      <p className="muted footnote">Screening and awareness tool, not a diagnosis.</p>
    </div>
  );
}
