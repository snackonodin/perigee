import { useState } from "react";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { VitalCard } from "../components/VitalCard";
import type { Status } from "../components/StatusChip";
import { Reveal, TitleReveal } from "../components/motion";
import "./Body.css";

type ScanToday=TodayOut&{context_engine?:{
  dashboard_visualization_data?:{dual_axis_timeline_point?:{respiration_bpm?:number|null}};
  fatigue_and_health_ratings?:{mental_fatigue_score?:number|null;physiological_fatigue_score?:number|null};
  scores_and_metrics?:{phys_level?:number;mental_level?:number};
  user_facing_advisory?:{environmental_note?:string|null};
}|null};
const SYSTEMS=["Respiration","Autonomic","Rest","Mind","Cabin"] as const;
type System=typeof SYSTEMS[number];
const DOTS:Record<System,[number,number,number,string]>= {
  Respiration:[187,174,38,"left"],Autonomic:[225,224,342,"right"],Rest:[175,132,52,"left"],Mind:[210,51,342,"right"],Cabin:[210,268,342,"right"],
};
const COLORS:Record<System,string>={Respiration:"mint",Autonomic:"peach",Rest:"sky",Mind:"lavender",Cabin:"butter"};
type Detail={value:string;copy:string;state?:Status;statusLabel:string};
function stateFor(level?:number):Status|undefined { if(level==null)return undefined;if(level>=2)return "alert";return level===1?"watch":"normal"; }
function BodyMap({selected,details,onSelect}:{selected:System;details:Record<System,Detail>;onSelect:(s:System)=>void}) {
  return <div className="body-map">
    <svg className="body-map-svg" viewBox="0 0 400 310" role="img" aria-label="Body map with head, torso, arms and legs. Five buttons select a system.">
      <circle className="body-silhouette" cx="201" cy="45" r="22"/>
      <path className="body-silhouette" d="M178 77c-17 4-30 14-38 28l-26 52 9 6 34-42-8 54 14 32-13 62h14l28-53 14 53h14l-13-62 14-32-8-54 34 42 9-6-26-52c-8-14-21-24-38-28l-8 18-8-18Z"/>
      <path className="body-centerline" d="M201 96v113m-24-73c9-10 16-11 24-4 9-7 16-6 24 4m-43 14c7 9 13 12 19 10m19-10c-7 9-13 12-19 10m-14 42 14 16 14-16"/>
      {SYSTEMS.map(name=>{const [x,y,,side]=DOTS[name],left=side==="left",col=left?118:286,dotEdge=left?x-14:x+14;
        return <g key={name}><line className="body-leader" x1={col} y1={y} x2={dotEdge} y2={y}/><circle className="body-leader-end" cx={col} cy={y} r="2"/><text className="body-map-label" x={left?col-8:col+8} y={y+5} textAnchor={left?"end":"start"}>{name}</text></g>;
      })}
    </svg>
    <div className="body-nodes">{SYSTEMS.map(name=>{const [x,y]=DOTS[name],detail=details[name];return <button key={name} type="button" className={`body-node body-node-${COLORS[name]}${selected===name?" selected":""}`} style={{left:`${x/4}%`,top:`${y/3.1}%`}} aria-label={`${name}, ${detail.statusLabel}`} aria-pressed={selected===name} onClick={()=>onSelect(name)}><span className="sr-only">{name}</span></button>;})}</div>
  </div>;
}

export function Body() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  const [selected,setSelected]=useState<System>("Respiration");
  return <LoadState state={load} label="your systems map">{raw=>{
    const today=raw as ScanToday,engine=today.context_engine,night=today.latest_night;
    const respiration=engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm??night?.rr_med;
    const rrLevel=stateFor(engine?.scores_and_metrics?.phys_level??today.flags[0]?.phys_level);
    const mentalLevel=stateFor(engine?.scores_and_metrics?.mental_level??today.flags[0]?.mental_level);
    const baseline=today.baselines.find(b=>b.feature==="rr_med");
    const mind=engine?.fatigue_and_health_ratings?.mental_fatigue_score;
    const cabinNote=engine?.user_facing_advisory?.environmental_note;
    const details:Record<System,Detail>={
      Respiration:{value:respiration==null?"No reading":`${fmt(respiration)} br/min`,copy:respiration==null?"No breathing estimate is available yet.":"This signal is shown against your own recent breathing range.",state:respiration==null?"none":rrLevel,statusLabel:respiration==null?"No reading":rrLevel??"Status unavailable"},
      Autonomic:{value:night?.rr_var==null?"No reading":fmt(night.rr_var),copy:night?.rr_var==null?"No overnight breathing-variation reading is available.":"Your overnight breathing variation. No separate status is returned for this measure.",statusLabel:night?.rr_var==null?"No reading":"Status unavailable"},
      Rest:{value:night?.valid?`${fmt(night.presence_hours,1)} h`:"No reading",copy:night?.valid?"Sensed presence last night. No separate status is returned for this measure.":"No valid night is available yet.",state:night?.valid?undefined:"none",statusLabel:night?.valid?"Status unavailable":"No reading"},
      Mind:{value:mind==null?"No reading":`${Math.round(mind)} / 100`,copy:"Check-ins add personal context to this part of your picture.",state:mind==null?"none":mentalLevel,statusLabel:mind==null?"No reading":mentalLevel??"Status unavailable"},
      Cabin:{value:"No reading",copy:cabinNote??"Cabin context is not included in this snapshot.",state:"none",statusLabel:"No reading"},
    };
    const current=details[selected];
    return <div className="screen-page body-page">
      <header className="page-heading"><div><p className="eyebrow">Personal systems · your recent signals</p><TitleReveal text="Body"/><p>Choose a system to see the available reading.</p></div></header>
      {load.apiMock&&<p className="api-mock-note" role="status">Showing sample data: live service unavailable</p>}
      <Reveal className="body-layout">
        <section className="body-map-card glass" aria-label="Body systems map"><p className="eyebrow">Five connected systems</p><span className="body-orbit" aria-hidden="true"/><BodyMap selected={selected} details={details} onSelect={setSelected}/></section>
        <section className="body-detail" aria-live="polite" aria-labelledby="body-detail-title" key={selected}>
          {current.value==="No reading"?<VitalCard label={selected} icon={selected} headingId="body-detail-title" empty={current.copy}/>:
          <VitalCard label={selected} value={current.value} icon={selected} state={current.state} headingId="body-detail-title">
            <p>{current.copy}</p>
            {selected==="Respiration"&&baseline?.median!=null&&baseline.mad!=null&&<p className="body-baseline">Personal baseline · 28 nights<br/>{fmt(baseline.median-baseline.mad)}–{fmt(baseline.median+baseline.mad)} br/min (median ± MAD)</p>}
          </VitalCard>}
          <div className="system-switch" role="group" aria-label="Choose a system">{SYSTEMS.map(name=><button key={name} type="button" className={`system-pill system-pill-${COLORS[name]}`} aria-pressed={selected===name} onClick={()=>setSelected(name)}><i aria-hidden="true"/>{name}</button>)}</div>
        </section>
      </Reveal>
    </div>;
  }}</LoadState>;
}
