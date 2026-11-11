import { NavLink, Outlet } from "react-router";
import { TABS } from "../routes/tabs";

export function AppShell() {
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Astronaut Health Monitor</span>
        <span className="badge">Synthetic data</span>
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
      <p className="muted" style={{ fontSize: "var(--fs-1)", marginTop: "var(--gap-4)" }}>
        Screening and awareness tool, not a diagnosis.
      </p>
    </div>
  );
}
