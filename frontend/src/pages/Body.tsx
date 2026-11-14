import { useState } from "react";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { VitalCard } from "../components/VitalCard";
import type { Status } from "../components/StatusChip";
import "./Body.css";
import { BodyPanel, type Region, type Status as RegionState, type SystemInfo } from "../body/BodyPanel";
import { baselineState, type BaselineState } from "../body/baselineState";

type ScanToday=TodayOut&{context_engine?:{
  dashboard_visualization_data?:{dual_axis_timeline_point?:{respiration_bpm?:number|null}};
  fatigue_and_health_ratings?:{mental_fatigue_score?:number|null;physiological_fatigue_score?:number|null};
  scores_and_metrics?:{phys_level?:number;mental_level?:number};
  user_facing_advisory?:{environmental_note?:string|null};
}|null};
const SYSTEMS=["Respiration","Autonomic","Rest","Mind","Cabin"] as const;
type System=typeof SYSTEMS[number];
const MEANING:Record<System,string>={
  Respiration:"How you breathe overnight, against your own usual range.",
  Autonomic:"How much your breathing varies overnight, compared with your own nights.",
  Rest:"Time sensed near the sensor overnight.",
  Mind:"Context from your check-ins and questionnaires.",
  Cabin:"The room around you: notes about the environment, not your body.",
};
const COLORS:Record<System,string>={Respiration:"mint",Autonomic:"peach",Rest:"sky",Mind:"lavender",Cabin:"butter"};
type Detail={unit?:string;value:string;copy:string;state?:Status;statusLabel:string};
const REGION:Record<System,Region>={Respiration:"respiration",Autonomic:"autonomic",Rest:"rest",Mind:"mind",Cabin:"cabin"};
/** usual -> normal (teal), changed -> watch (amber), none -> no status */
const asStatus=(b:BaselineState):Status|undefined=>b==="changed"?"watch":b==="usual"?"normal":undefined;
const SYSTEM_OF=Object.fromEntries(SYSTEMS.map(n=>[REGION[n],n])) as Record<Region,System>;
/** Engine level -> the figure's baseline-relative state. A value without a comparison stays grey. */
function regionInfo(d:Detail):SystemInfo {
  if(d.value==="No reading")return d.copy==="No cabin sensor connected."?{state:"none",reading:d.copy}:{state:"none"};
  const reading=d.unit?`${d.value} ${d.unit}`:d.value;
  const state:RegionState|undefined=d.state==="normal"?"usual":d.state==="watch"||d.state==="alert"?"changed":undefined;
  return state?{state,reading}:{state:"none",reading,label:"Not compared yet"};
}
// Body never shows red: any change from usual reads amber ("watch").
function stateFor(level?:number):Status|undefined { if(level==null)return undefined;return level>=1?"watch":"normal"; }
export function Body() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  const [selected,setSelected]=useState<System>("Respiration");
  return <LoadState state={load} label="your systems map">{raw=>{
    const today=raw as ScanToday,engine=today.context_engine,night=today.latest_night;
    const respiration=engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm??night?.rr_med;
    // latest night vs the person's own usual, with the engine's own cut-off (no frontend thresholds)
    const rrLevel=asStatus(baselineState(today,["rr_med"]));
    const restLevel=asStatus(baselineState(today,["presence_hours","restless_frac"]));
    const mentalLevel=stateFor(engine?.scores_and_metrics?.mental_level??today.flags[0]?.mental_level);
    const baseline=today.baselines.find(b=>b.feature==="rr_med");
    const mind=engine?.fatigue_and_health_ratings?.mental_fatigue_score;
    const details:Record<System,Detail>={
      Respiration:{value:respiration==null?"No reading":fmt(respiration),unit:respiration==null?undefined:"br/min",copy:respiration==null?"No breathing estimate is available yet.":"This signal is shown against your own recent breathing range.",state:respiration==null?"none":rrLevel,statusLabel:respiration==null?"No reading":rrLevel??"Status unavailable"},
      Autonomic:{value:night?.rr_var==null?"No reading":fmt(night.rr_var),copy:night?.rr_var==null?"No overnight breathing-variation reading is available.":"Your overnight breathing variation. No separate status is returned for this measure.",statusLabel:night?.rr_var==null?"No reading":"Status unavailable"},
      Rest:{value:night?.valid?fmt(night.presence_hours,1):"No reading",unit:night?.valid?"h":undefined,copy:night?.valid?"Time sensed near the sensor last night, with how restless the night was, compared with your own usual.":"No valid night is available yet.",state:night?.valid?restLevel:"none",statusLabel:!night?.valid?"No reading":restLevel==="watch"?"Changed from your usual":restLevel==="normal"?"Usual":"Not compared yet"},
      Mind:{value:mind==null?"No reading":"From your check-ins",unit:undefined,copy:"Check-ins add personal context to this part of your picture.",state:mind==null?"none":mentalLevel,statusLabel:mind==null?"No reading":mentalLevel??"Status unavailable"},
      Cabin:{value:"No reading",copy:"No cabin sensor connected.",state:"none",statusLabel:"No reading"},
    };
    const current=details[selected];
    const nightsIn=Math.min(28,baseline?.n??0);
    const footer=<><p className="system-meaning">{MEANING[selected]}</p><div className="system-usual"><span className="meta-label">Personal baseline</span><span>{selected==="Cabin"?"Not compared":nightsIn>=28?"Baseline ready":`Building · ${nightsIn} / 28 nights`}</span></div></>;
    return <div className="screen-page body-page">
      <header className="page-heading"><div><h1>Body</h1><p>Choose a system to see the available reading.</p></div></header>
      {load.apiMock&&<p className="api-mock-note" role="status">Showing sample data: live service unavailable</p>}
      <div className="body-layout">
        <section className="body-map-card body-panel-card" aria-label="Body systems map">
          <div className="body-panel"><BodyPanel heartRate={null} breathRate={baseline?.median??respiration??null}
            systems={Object.fromEntries(SYSTEMS.map(n=>[REGION[n],regionInfo(details[n])]))}
            activeRegion={REGION[selected]} onSelect={r=>setSelected(SYSTEM_OF[r])}/></div>
        </section>
        <section className="body-detail" data-pet-perch aria-live="polite" aria-labelledby="body-detail-title" key={selected}>
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
