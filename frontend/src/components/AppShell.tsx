import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import Lenis from "lenis";
import { useAuth } from "../auth/AuthProvider";
import { TABS } from "../routes/tabs";
import { Icon, ROUTE_ICON } from "./icons";
import { BRAND } from "../brand";

/** Header name: display name, else the e-mail's local part, else "Crew member" (never the full address). */
export function crewName(displayName?:string|null,email?:string|null):string {
  const name=displayName?.trim(); if(name)return name;
  const local=email?.split("@")[0]?.trim(); return local||"Crew member";
}

export function AppShell() {
  const { me, logout } = useAuth();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  const swipeStart=useRef<{x:number;y:number}|null>(null);
  useEffect(() => {
    if(!window.matchMedia)return;
    const media=window.matchMedia("(prefers-reduced-motion: reduce)");
    if(media.matches)return;
    const lenis=new Lenis({lerp:0.12,autoRaf:false});
    let frame=0;
    const tick=(time:number)=>{lenis.raf(time);frame=requestAnimationFrame(tick);};
    frame=requestAnimationFrame(tick);
    const safetyObserver=new MutationObserver(()=>{document.querySelector(".safety")?lenis.stop():lenis.start();});
    safetyObserver.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["class"]});
    return()=>{safetyObserver.disconnect();cancelAnimationFrame(frame);lenis.destroy();};
  },[]);
  useEffect(()=>{
    const mainElement=main.current?.querySelector(".screen-transition");
    if(!mainElement||!window.matchMedia||window.matchMedia("(prefers-reduced-motion: reduce)").matches)return;
    mainElement.classList.remove("glass-in");
    void mainElement.getBoundingClientRect();
    mainElement.classList.add("glass-in");
  },[pathname]);
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
  const tabIndex=TABS.findIndex(t=>t.path===pathname);
  const nav=useRef<HTMLElement>(null);
  const [pill,setPill]=useState<{x:number;w:number}|null>(null);
  // Measure the active tab so the sliding pill matches its real box at any width.
  useLayoutEffect(()=>{
    const measure=()=>{const el=nav.current?.querySelector<HTMLElement>('a.tab[aria-current="page"]');setPill(el?{x:el.offsetLeft,w:el.offsetWidth}:null);};
    measure();
    window.addEventListener("resize",measure);
    return()=>window.removeEventListener("resize",measure);
  },[pathname]);
  return (
    <div className="shell">
      <div className="aurora-backdrop" aria-hidden="true"><i/><i/><i/><i/></div>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <span className="brand"><span className="brand-mark" aria-hidden="true"><BrandIcon/></span>{BRAND}</span>
        {me?.is_synthetic && <span className="sim-chip telemetry" data-short="Sim"><span className="sim-chip-text">Simulated data</span></span>}
        <span className="spacer" />
        <span className="muted who" title={me?.email}>{crewName(me?.display_name,me?.email)}</span>
        <NavLink className="header-link" to="/monitor" aria-label="Monitor"><Icon name="monitor" size={22}/><span className="header-link-label">Monitor</span></NavLink>
        <NavLink className="header-link" to="/settings" aria-label="Settings"><Icon name="settings" size={22}/><span className="header-link-label">Settings</span></NavLink>
        <button type="button" className="ghost header-logout" aria-label="Log out" onClick={() => void logout()}><Icon name="logout" size={20}/><span className="header-link-label">Log out</span></button>
      </header>
      <nav ref={nav} className="tabs glass" aria-label="Sections. Tap a tab or swipe across a screen to switch">
        {tabIndex>=0&&pill&&<span className="tab-indicator" aria-hidden="true" style={{"--pill-x":`${pill.x}px`,"--pill-w":`${pill.w}px`} as CSSProperties}/>}
        {TABS.map((t) => (
          <NavLink key={t.path} to={t.path} end={t.path === "/"} className="tab">
            <span className="tab-icon" aria-hidden="true"><Icon name={ROUTE_ICON[t.path]} size={22}/></span>
            <span>{t.label}</span>
          </NavLink>
        ))}
      </nav>
      <main id="main" ref={main} tabIndex={-1} aria-label={TABS.find((t) => t.path === pathname)?.label}
        onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        <div className="screen-transition" key={pathname}><Outlet /></div>
      </main>
      <div id="companion-slot" aria-hidden="true" />
    </div>
  );
}

function BrandIcon(){return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M5 13c3-6 6 6 9 0s5 0 5-2"/></svg>;}
