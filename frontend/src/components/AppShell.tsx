import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useAuth } from "../auth/AuthProvider";
import { TABS } from "../routes/tabs";

export function AppShell() {
  const { me, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  const swipeStart=useRef<{x:number;y:number}|null>(null);
  // After a tab change, move focus to the new page so keyboard and screen-reader users
  // land on its content (not on the first load).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
  }, [pathname]);
  function onTouchStart(event:React.TouchEvent<HTMLElement>) {
    const target=event.target as Element;
    if(event.touches.length!==1||target.closest("a,button,input,select,textarea,label,summary,[role=button]")){
      swipeStart.current=null;
      return;
    }
    const touch=event.touches[0];
    swipeStart.current={x:touch.clientX,y:touch.clientY};
  }
  function onTouchEnd(event:React.TouchEvent<HTMLElement>) {
    const start=swipeStart.current;
    swipeStart.current=null;
    if(!start)return;
    const touch=event.changedTouches[0],dx=touch.clientX-start.x,dy=touch.clientY-start.y;
    if(Math.abs(dx)<72||Math.abs(dy)>52)return;
    const index=TABS.findIndex(tab=>tab.path===pathname);
    const destination=TABS[index+(dx<0?1:-1)];
    if(destination)navigate(destination.path);
  }
  return (
    <div className="shell">
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <span className="brand"><span className="brand-mark" aria-hidden="true">✦</span>Perigee</span>
        {me?.is_synthetic && <span className="badge">Simulated data</span>}
        <span className="spacer" />
        <span className="muted who">{me?.display_name || me?.email}</span>
        <NavLink className="tab settings-shortcut" to="/settings" aria-label="Settings">⚙ <span>Settings</span></NavLink>
        <button type="button" className="ghost" onClick={() => void logout()}>Log out</button>
      </header>
      <nav className="tabs" aria-label="Sections. Tap a tab or swipe across a screen to switch">
        {TABS.map((t) => (
          <NavLink key={t.path} to={t.path} end={t.path === "/"} className="tab">
            <span className="tab-icon" aria-hidden="true">{t.icon}</span>
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>
      <main id="main" ref={main} tabIndex={-1} aria-label={TABS.find((t) => t.path === pathname)?.label}
        onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        <div className="screen-transition" key={pathname}><Outlet /></div>
      </main>
    </div>
  );
}
