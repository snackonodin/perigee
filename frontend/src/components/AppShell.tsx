import { useEffect, useRef, type CSSProperties } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router";
import Lenis from "lenis";
import { useAuth } from "../auth/AuthProvider";
import { TABS } from "../routes/tabs";

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
  return (
    <div className="shell">
      <div className="aurora-backdrop" aria-hidden="true"><i/><i/><i/><i/></div>
      <a className="skip" href="#main">Skip to content</a>
      <header className="topbar">
        <span className="brand"><span className="brand-mark" aria-hidden="true"><BrandIcon/></span>Astronaut Vitals</span>
        {me?.is_synthetic && <span className="badge">Simulated data</span>}
        <span className="spacer" />
        <span className="muted who">{me?.display_name || me?.email}</span>
        <NavLink className="tab settings-shortcut" to="/settings" aria-label="Settings"><span className="tab-icon" aria-hidden="true"><NavIcon path="/settings"/></span><span>Settings</span></NavLink>
        <button type="button" className="ghost" onClick={() => void logout()}>Log out</button>
      </header>
      <nav className="tabs glass" aria-label="Sections. Tap a tab or swipe across a screen to switch">
        <span className="tab-indicator" aria-hidden="true" style={{"--tab-index":Math.max(0,TABS.findIndex(t=>t.path===pathname)),"--tab-count":TABS.length} as CSSProperties}/>
        {TABS.map((t) => (
          <NavLink key={t.path} to={t.path} end={t.path === "/"} className="tab">
            <span className="tab-icon" aria-hidden="true"><NavIcon path={t.path}/></span>
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

function NavIcon({path}:{path:string}) {
  const d=path==="/"?"M3 11 12 4l9 7M5 10v10h14V10M9 20v-6h6v6":path==="/sleep"?"M20 15.5A8 8 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z":path==="/persona"?"M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8ZM4 21a8 8 0 0 1 16 0":path==="/body"?"M12 3v4m0 0a3 3 0 1 0 0 6m0-6a3 3 0 1 1 0 6m0 0v8M6 14l-2 4m14-4 2 4":path==="/checkin"?"M5 4h14v16H5zM8 8h8M8 12h8M8 16h5":"M12 3l2 6 6 3-6 2-2 7-2-7-6-2 6-3z";
  return <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={d}/></svg>;
}
function BrandIcon(){return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M5 13c3-6 6 6 9 0s5 0 5-2"/></svg>;}
