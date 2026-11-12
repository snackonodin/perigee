import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "../auth/AuthProvider";
import { TABS } from "../routes/tabs";

export function AppShell() {
  const { me, logout } = useAuth();
  const { pathname } = useLocation();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  // After a tab change, move focus to the new page so keyboard and screen-reader users
  // land on its content (not on the first load).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
  }, [pathname]);
  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <span className="brand">Astronaut Health Monitor</span>
        {me?.is_synthetic && <span className="badge">Simulated data</span>}
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
      <main id="main" ref={main} tabIndex={-1} aria-label={TABS.find((t) => t.path === pathname)?.label}>
        <Outlet />
      </main>
      <p className="muted footnote">Screening and awareness tool, not a diagnosis.</p>
    </div>
  );
}
