import { useState } from "react";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { VitalsTiles } from "../components/VitalsTiles";

type ScanToday=TodayOut&{context_engine?:{
  dashboard_visualization_data?:{dual_axis_timeline_point?:{respiration_bpm?:number}};
  fatigue_and_health_ratings?:{mental_fatigue_score?:number;physiological_fatigue_score?:number};
  scores_and_metrics?:{phys_level?:number;mental_level?:number};
  user_facing_advisory?:{environmental_note?:string|null};
}|null};
const SYSTEMS=["Respiration","Autonomic","Rest","Mind","Cabin"] as const;
type System=typeof SYSTEMS[number];
const DOTS:Record<System,[number,number,number,string]>={
  Respiration:[187,174,38,"left"],Autonomic:[225,224,342,"right"],Rest:[175,132,52,"left"],Mind:[210,51,342,"right"],Cabin:[210,268,342,"right"],
};
function ScanSvg({selected,onSelect}:{selected:System;onSelect:(s:System)=>void}) {
  return <svg className="body-hologram" viewBox="0 0 400 310" role="group" aria-label="Interactive body systems hologram">
    <defs>
      <linearGradient id="holoBody" x1="0" x2="1" y1="0" y2="1"><stop stopColor="var(--aurora)" stopOpacity=".2"/><stop offset=".52" stopColor="var(--violet)" stopOpacity=".17"/><stop offset="1" stopColor="var(--aurora)" stopOpacity=".06"/></linearGradient>
      <radialGradient id="holoCore"><stop stopColor="var(--aurora)" stopOpacity=".32"/><stop offset="1" stopColor="var(--aurora)" stopOpacity="0"/></radialGradient>
      <filter id="holoBlur"><feGaussianBlur stdDeviation="5"/></filter>
      <pattern id="holoGrid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0v18" fill="none" stroke="var(--aurora)" strokeOpacity=".08" strokeWidth=".6"/></pattern>
    </defs>
    <rect x="8" y="8" width="384" height="294" rx="22" fill="url(#holoGrid)"/>
    <ellipse cx="203" cy="164" rx="119" ry="111" fill="none" stroke="var(--violet)" strokeOpacity=".18" strokeDasharray="3 8"/>
    <ellipse cx="203" cy="164" rx="94" ry="130" fill="none" stroke="var(--aurora)" strokeOpacity=".15" transform="rotate(23 203 164)"/>
    <circle cx="205" cy="167" r="82" fill="url(#holoCore)" filter="url(#holoBlur)"/>
    <circle cx="201" cy="45" r="22" fill="url(#holoBody)" stroke="var(--aurora)" strokeOpacity=".9" strokeWidth="1.4"/>
    <path className="holo-silhouette" d="M178 77c-17 4-30 14-38 28l-26 52 9 6 34-42-8 54 14 32-13 62h14l28-53 14 53h14l-13-62 14-32-8-54 34 42 9-6-26-52c-8-14-21-24-38-28l-8 18-8-18Z"/>
    <path className="holo-inner" d="M201 96v113m-24-73c9-10 16-11 24-4 9-7 16-6 24 4m-43 14c7 9 13 12 19 10m19-10c-7 9-13 12-19 10m-14 42 14 16 14-16"/>
    <path className="holo-circuit" d="M172 115h-12v27m69-27h14v27M178 190h-16v17m77-17h15v17M201 80v16"/>
    {SYSTEMS.map(name=>{const [x,y,labelX,side]=DOTS[name],endX=side==="left"?labelX+70:labelX-12;
      return <g key={name} className={selected===name?"holo-hotspot selected":"holo-hotspot"} role="button" tabIndex={0} aria-pressed={selected===name} aria-label={`Open ${name} system`} onClick={()=>onSelect(name)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(name);}}}>
        <line x1={x} y1={y} x2={endX} y2={y}/><circle cx={x} cy={y} r="5"/><circle className="hotspot-halo" cx={x} cy={y} r="10"/>
        <text x={labelX} y={y-8} textAnchor={side==="left"?"start":"end"}>{name.toUpperCase()}</text>
      </g>;
    })}
    <text className="scan-label" x="20" y="285">PERSONAL SIGNAL MAP</text><text className="scan-label" x="380" y="285" textAnchor="end">SELECT A NODE</text>
  </svg>;
}
function stateFor(level?:number) {
  if(level==null)return {word:"Building",tone:"quiet"};
  if(level>=2)return {word:"Alert",tone:"high"};
  return level===1?{word:"Watch",tone:"watch"}:{word:"Normal",tone:"usual"};
}
export function Body() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  const [selected,setSelected]=useState<System>("Respiration");
  return <LoadState state={load} label="your systems scan">{raw=>{
    const today=raw as ScanToday,engine=today.context_engine,night=today.latest_night;
    const level=engine?.scores_and_metrics?.phys_level??today.flags[0]?.phys_level;
    const rr=engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm??night?.rr_med;
    const baseline=today.baselines.find(b=>b.feature==="rr_med");
    const detail:Record<System,{value:string;copy:string;level?:number}>={
      Respiration:{value:rr==null?"—":`${fmt(rr)} /min`,copy:rr==null?"No valid breathing estimate is available yet.":"This signal is shown against your own recent breathing range.",level},
      Autonomic:{value:night?.rr_var==null?"—":fmt(night.rr_var),copy:night?.rr_var==null?"No overnight breathing-variation signal is available.":"Your overnight breathing variation; this view does not interpret it as a diagnosis."},
      Rest:{value:night?.valid?`${fmt(night.presence_hours,1)} h`:"—",copy:night?.valid?`${fmt(night.restless_frac*100,0)}% movement flagged in the sensed period.`:"No valid night is available yet."},
      Mind:{value:engine?.fatigue_and_health_ratings?.mental_fatigue_score==null?"—":`${Math.round(engine.fatigue_and_health_ratings.mental_fatigue_score)} / 100`,copy:"Check-ins add personal context to this part of your picture.",level:engine?.scores_and_metrics?.mental_level},
      Cabin:{value:engine?.user_facing_advisory?.environmental_note?"Note available":"—",copy:engine?.user_facing_advisory?.environmental_note??"Cabin context is not included in this snapshot."},
    };
    const current=detail[selected],status=stateFor(current.level);
    return <div className="screen-page body-page">
      <header className="page-heading app-page-heading"><div className="heading-mark" aria-hidden="true">⌁</div><div><p className="eyebrow">Personal systems · holographic scan</p><h1>Body</h1><p>Tap a signal node to open its panel.</p></div><span className={`status-chip ${status.tone}`}><span aria-hidden="true">◌</span>{status.word}</span></header>
      {load.apiMock&&<p className="api-mock-note" role="status">API unavailable · empty preview; no readings are shown.</p>}
      <div className="body-console">
        <section className="holo-panel" aria-label="Body systems map"><div className="holo-panel-top"><span>SYS / 05</span><span>PERSONAL BASELINE · 28N</span></div><ScanSvg selected={selected} onSelect={setSelected}/>
          <div className="system-selector" aria-label="Choose system">{SYSTEMS.map(name=><button type="button" key={name} className={selected===name?"system-node active":"system-node"} aria-pressed={selected===name} onClick={()=>setSelected(name)}>{name}</button>)}</div>
        </section>
        <section className="body-inspector" aria-live="polite" aria-labelledby="system-title">
          <article className="system-detail-card"><div className="inspector-index"><span>0{SYSTEMS.indexOf(selected)+1}</span><span className={`status-chip ${status.tone}`}><i aria-hidden="true">◌</i>{status.word}</span></div>
            <p className="eyebrow">Selected system</p><h2 id="system-title">{selected}</h2><strong className="system-detail-value">{current.value}</strong><p>{current.copy}</p>
            {selected==="Respiration"&&baseline?.median!=null&&baseline.mad!=null&&<p className="muted">Your 28-night range: {fmt(baseline.median-baseline.mad)}–{fmt(baseline.median+baseline.mad)} breaths/min</p>}
          </article>
          <div className="body-vitals-grid"><VitalsTiles night={night} baseline={baseline}/></div>
        </section>
      </div>
    </div>;
  }}</LoadState>;
}
