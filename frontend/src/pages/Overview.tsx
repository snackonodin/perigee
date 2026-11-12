import { Link } from "react-router";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { VitalsTiles } from "../components/VitalsTiles";

type EngineToday = TodayOut & { context_engine?: {
  scores_and_metrics?: { phys_level?: number; mental_level?: number };
  fatigue_and_health_ratings?: { mental_fatigue_score?: number; overall_health_resilience_index?: number };
  user_facing_advisory?: { headline?: string; personality_tailored_message?: string };
} | null };
function level(level?:number) {
  if(level==null)return {name:"Building your picture",icon:"◌",tone:"quiet"};
  if(level>=2)return {name:"Alert",icon:"◌",tone:"high"};
  if(level===1)return {name:"Watch",icon:"◌",tone:"watch"};
  return {name:"Normal",icon:"◌",tone:"usual"};
}
function LevelRing({value}:{value?:number}) {
  const r=63,c=2*Math.PI*r,status=level(value),valid=Number.isFinite(value);
  const fraction=valid?Math.max(1,Math.min(3,Math.max(0,value!)))/3:0;
  return <figure className="today-ring"><svg viewBox="0 0 150 150" role="img" aria-label={valid?`Today's level ${status.name}, level ${value}`:"Today's level is not available"}>
    <circle className="ring-track" cx="75" cy="75" r={r}/><circle className={`ring-value ${status.tone}`} cx="75" cy="75" r={r} strokeDasharray={c} strokeDashoffset={c*(1-fraction)}/>
    <text className="hero-value" x="75" y="72" textAnchor="middle">{valid?value:"—"}</text><text className="hero-label" x="75" y="94" textAnchor="middle">{valid?status.name:"No level"}</text>
  </svg><figcaption className="sr-only">Level is shown with both its number and word.</figcaption></figure>;
}
function QuietMetric({icon,title,value,detail,level:levelValue}:{icon:string;title:string;value:string;detail:string;level?:number}) {
  const status=level(levelValue);
  return <article className="quiet-metric"><div className="quiet-icon" aria-hidden="true">{icon}</div><div className="quiet-copy"><span>{title}</span><strong>{value}</strong><small>{detail}</small>{levelValue!=null&&<span className={`metric-level ${status.tone}`}><i aria-hidden="true">{status.icon}</i>{status.name}</span>}</div></article>;
}
function OrbitIllustration() {
  return <svg className="today-orbit-art" viewBox="0 0 300 220" aria-hidden="true">
    <defs><radialGradient id="perigeeGlow"><stop stopColor="var(--aurora)" stopOpacity=".38"/><stop offset="1" stopColor="var(--aurora)" stopOpacity="0"/></radialGradient><linearGradient id="perigeePlanet" x2="1" y2="1"><stop stopColor="var(--violet)"/><stop offset="1" stopColor="var(--space-3)"/></linearGradient></defs>
    <circle cx="214" cy="108" r="82" fill="url(#perigeeGlow)"/><circle cx="214" cy="108" r="38" fill="url(#perigeePlanet)" stroke="var(--violet)" strokeOpacity=".75"/>
    <path d="M178 119c21 9 48 8 72-4M185 134c19 6 38 4 57-2" fill="none" stroke="var(--aurora)" strokeOpacity=".45"/>
    <ellipse cx="165" cy="110" rx="127" ry="53" transform="rotate(-19 165 110)" fill="none" stroke="var(--aurora)" strokeOpacity=".45" strokeDasharray="2 7"/>
    <path d="m78 83 16-10 22 2 9 10-9 10-22 2-16-10z" fill="var(--space-2)" stroke="var(--aurora)"/><circle cx="99" cy="87" r="5" fill="var(--aurora)"/>
    <path d="M47 54v12m-6-6h12M126 163v10m-5-5h10M268 51v10m-5-5h10" stroke="var(--ink-muted)" strokeOpacity=".7"/>
  </svg>;
}

export function Overview() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  return <LoadState state={load} label="today's personal snapshot">{raw=>{
    const today=raw as EngineToday,engine=today.context_engine,night=today.latest_night;
    const physiology=engine?.scores_and_metrics?.phys_level??today.flags[0]?.phys_level;
    const mental=engine?.scores_and_metrics?.mental_level??today.flags[0]?.mental_level;
    const health=engine?.fatigue_and_health_ratings, baseline=today.baselines.find(b=>b.feature==="rr_med");
    const resilience=health?.overall_health_resilience_index;
    const note=engine?.user_facing_advisory;
    return <div className="screen-page today-page">
      <header className="page-heading app-page-heading"><div className="heading-mark" aria-hidden="true">✦</div><div><p className="eyebrow">Crew quarters · personal log</p><h1>Today</h1><p>{night?`Last signal · ${night.date}`:"Your next quiet check-in"}</p></div><span className={`status-chip ${level(physiology).tone}`}><span aria-hidden="true">{level(physiology).icon}</span>{level(physiology).name}</span></header>
      {load.apiMock&&<p className="api-mock-note" role="status">API unavailable · empty preview; no readings are shown.</p>}
      <section className="today-hero-card" aria-labelledby="today-hero-title"><OrbitIllustration/><div className="today-level-wrap"><LevelRing value={physiology}/></div>
        <div className="today-hero-copy"><p className="eyebrow">Your signal level</p><h2 id="today-hero-title">{resilience==null?"Your picture is taking shape":"Your systems, in context"}</h2>
          <p>{physiology==null?"Personal ranges grow from your own valid nights.":"A small shift can be usual for you; this view follows your own pattern."}</p>
          <div className="today-hero-actions"><span className="hero-resilience">{resilience==null?"Resilience building":<><strong>{Math.round(resilience)}</strong> resilience</>}</span>
            {today.pending_checkins[0]&&<Link className="hero-action" to={`/checkin?instrument=${encodeURIComponent(today.pending_checkins[0].instrument_id)}`}>Check in <span aria-hidden="true">→</span></Link>}
          </div>
        </div>
      </section>
      <section className="today-signal-grid" aria-label="Latest body and check-in signals">
        <VitalsTiles night={night} baseline={baseline}/>
        <QuietMetric icon="✧" title="Mind" value={health?.mental_fatigue_score==null?"—":`${Math.round(health.mental_fatigue_score)} / 100`} detail={health?.mental_fatigue_score==null?"Check-ins add context":"From your recent personal inputs"} level={mental}/>
        <QuietMetric icon="☾" title="Rest" value={night?.valid?`${fmt(night.presence_hours,1)} h`:"—"} detail={night?.valid?`${fmt(night.restless_frac*100,0)}% movement flagged`:"No valid night yet"}/>
      </section>
      <aside className="today-note-card"><span className="note-spark" aria-hidden="true">✧</span><div><p className="eyebrow">A quiet note</p><strong>{note?.headline??"Notice your own rhythm"}</strong><p>{note?.personality_tailored_message??"Your patterns are compared with your own recent baseline."}</p></div></aside>
    </div>;
  }}</LoadState>;
}
