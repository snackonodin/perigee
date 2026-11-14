import { useState } from "react";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { VitalCard } from "../components/VitalCard";
import type { Status } from "../components/StatusChip";
import "./Body.css";
import anchors from "../assets/body/anchors.json";

type ScanToday=TodayOut&{context_engine?:{
  dashboard_visualization_data?:{dual_axis_timeline_point?:{respiration_bpm?:number|null}};
  fatigue_and_health_ratings?:{mental_fatigue_score?:number|null;physiological_fatigue_score?:number|null};
  scores_and_metrics?:{phys_level?:number;mental_level?:number};
  user_facing_advisory?:{environmental_note?:string|null};
}|null};
const SYSTEMS=["Respiration","Autonomic","Rest","Mind","Cabin"] as const;
type System=typeof SYSTEMS[number];
type Anchor={x:number;y:number;side:"left"|"right"};
const W=400,H=310;
// Hotspots are data (assets/body/anchors.json) so the user's figure image can drop in.
const DOTS=Object.fromEntries(SYSTEMS.map(n=>{const a=(anchors as unknown as Record<string,Anchor>)[n];return [n,[a.x*W,a.y*H,a.side]];})) as Record<System,[number,number,"left"|"right"]>;
const MEANING:Record<System,string>={
  Respiration:"How you breathe overnight, against your own usual range.",
  Autonomic:"How much your breathing varies overnight, compared with your own nights.",
  Rest:"Time sensed near the sensor overnight.",
  Mind:"Context from your check-ins and questionnaires.",
  Cabin:"The room around you: notes about the environment, not your body.",
};
const COLORS:Record<System,string>={Respiration:"mint",Autonomic:"peach",Rest:"sky",Mind:"lavender",Cabin:"butter"};
type Detail={unit?:string;value:string;copy:string;state?:Status;statusLabel:string};
function stateFor(level?:number):Status|undefined { if(level==null)return undefined;if(level>=2)return "alert";return level===1?"watch":"normal"; }
function BodyMap({selected,details,onSelect}:{selected:System;details:Record<System,Detail>;onSelect:(s:System)=>void}) {
  return <div className="body-map">
    <svg className="body-map-svg" viewBox="0 0 400 310" role="img" aria-label="Body map with head, torso, arms and legs. Five buttons select a system.">
      <circle className="body-silhouette" cx="201" cy="45" r="22"/>
      <path className="body-silhouette" d="M178 77c-17 4-30 14-38 28l-26 52 9 6 34-42-8 54 14 32-13 62h14l28-53 14 53h14l-13-62 14-32-8-54 34 42 9-6-26-52c-8-14-21-24-38-28l-8 18-8-18Z"/>
      <path className="body-centerline" d="M201 96v113m-24-73c9-10 16-11 24-4 9-7 16-6 24 4m-43 14c7 9 13 12 19 10m19-10c-7 9-13 12-19 10m-14 42 14 16 14-16"/>
      {SYSTEMS.map(name=>{const [x,y,side]=DOTS[name],left=side==="left",col=left?118:286,outside=left?x<col:x>col,dotEdge=left?x-14:x+14;
        if(outside)return <g key={name}><text className="body-map-label" x={left?x-18:x+18} y={y+5} textAnchor={left?"end":"start"}>{name}</text></g>;
        return <g key={name}><line className="body-leader" x1={col} y1={y} x2={dotEdge} y2={y}/><circle className="body-leader-end" cx={col} cy={y} r="2"/><text className="body-map-label" x={left?col-8:col+8} y={y+5} textAnchor={left?"end":"start"}>{name}</text></g>;
      })}
    </svg>
    <div className="body-nodes">{SYSTEMS.map(name=>{const [x,y]=DOTS[name],detail=details[name];return <button key={name} type="button" className={`body-node body-node-${COLORS[name]}${selected===name?" selected":""}`} style={{left:`${x/W*100}%`,top:`${y/H*100}%`}} aria-label={`${name}, ${detail.statusLabel}`} aria-pressed={selected===name} onClick={()=>onSelect(name)}><span className="sr-only">{name}</span></button>;})}</div>
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
      Respiration:{value:respiration==null?"No reading":fmt(respiration),unit:respiration==null?undefined:"br/min",copy:respiration==null?"No breathing estimate is available yet.":"This signal is shown against your own recent breathing range.",state:respiration==null?"none":rrLevel,statusLabel:respiration==null?"No reading":rrLevel??"Status unavailable"},
      Autonomic:{value:night?.rr_var==null?"No reading":fmt(night.rr_var),copy:night?.rr_var==null?"No overnight breathing-variation reading is available.":"Your overnight breathing variation. No separate status is returned for this measure.",statusLabel:night?.rr_var==null?"No reading":"Status unavailable"},
      Rest:{value:night?.valid?fmt(night.presence_hours,1):"No reading",unit:night?.valid?"h":undefined,copy:night?.valid?"Sensed presence last night. No separate status is returned for this measure.":"No valid night is available yet.",state:night?.valid?undefined:"none",statusLabel:night?.valid?"Status unavailable":"No reading"},
      Mind:{value:mind==null?"No reading":String(Math.round(mind)),unit:mind==null?undefined:"/ 100",copy:"Check-ins add personal context to this part of your picture.",state:mind==null?"none":mentalLevel,statusLabel:mind==null?"No reading":mentalLevel??"Status unavailable"},
      Cabin:{value:"No reading",copy:cabinNote??"Cabin context is not included in this snapshot.",state:"none",statusLabel:"No reading"},
    };
    const current=details[selected];
    const nightsIn=Math.min(28,baseline?.n??0);
    const footer=<><p className="system-meaning">{MEANING[selected]}</p><div className="system-usual"><span className="meta-label">Personal baseline</span><span>{selected==="Cabin"?"Not compared":nightsIn>=28?"Baseline ready":`Building · ${nightsIn} / 28 nights`}</span></div></>;
    return <div className="screen-page body-page">
      <header className="page-heading"><div><h1>Body</h1><p>Choose a system to see the available reading.</p></div></header>
      {load.apiMock&&<p className="api-mock-note" role="status">Showing sample data: live service unavailable</p>}
      <div className="body-layout">
        <section className="body-map-card" aria-label="Body systems map"><span className="body-orbit" aria-hidden="true"/><BodyMap selected={selected} details={details} onSelect={setSelected}/></section>
        <section className="body-detail" aria-live="polite" aria-labelledby="body-detail-title" key={selected}>
          <div className="system-switch" role="group" aria-label="Choose a system">{SYSTEMS.map(name=><button key={name} type="button" className={`system-pill system-pill-${COLORS[name]}`} aria-pressed={selected===name} onClick={()=>setSelected(name)}><i aria-hidden="true"/>{name}</button>)}</div>
          {current.value==="No reading"?<VitalCard label={selected} icon={selected} headingId="body-detail-title" empty={current.copy} footer={footer}/>:
          <VitalCard label={selected} value={current.value} unit={current.unit} icon={selected} state={current.state} headingId="body-detail-title" footer={footer}>
            <p>{current.copy}</p>
            {selected==="Respiration"&&baseline?.median!=null&&baseline.mad!=null&&<p className="body-baseline">Your usual range<br/>{fmt(baseline.median-baseline.mad)}–{fmt(baseline.median+baseline.mad)} br/min (median ± MAD)</p>}
          </VitalCard>}
        </section>
      </div>
    </div>;
  }}</LoadState>;
}
