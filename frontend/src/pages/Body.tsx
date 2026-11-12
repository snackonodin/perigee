import { useState } from "react";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import { fmt } from "../components/format";

type ScanToday = TodayOut & { context_engine?: {
  dashboard_visualization_data?: { dual_axis_timeline_point?: { respiration_bpm?: number } };
  fatigue_and_health_ratings?: { mental_fatigue_score?: number; physiological_fatigue_score?: number };
  scores_and_metrics?: { phys_level?: number; mental_level?: number };
  user_facing_advisory?: { environmental_note?: string | null };
} | null };
const SYSTEMS = ["Respiration", "Autonomic", "Rest", "Mind", "Cabin"] as const;
type System = typeof SYSTEMS[number];
function ScanSvg({selected,onSelect}:{selected:System;onSelect:(s:System)=>void}) {
  const dots:Record<System,[number,number]>={Respiration:[116,104],Autonomic:[117,147],Rest:[117,61],Mind:[116,39],Cabin:[117,188]};
  return <svg className="body-scan-svg" viewBox="0 0 234 230" role="group" aria-label="Systems scan hotspots">
    <path className="scan-outline" d="M117 20c-16 0-25 12-25 27v13l-15 12-9 38 11 4 11-28 2 50-17 56 12 4 25-45 24 45 12-4-17-56 2-50 11 28 11-4-9-38-15-12V47c0-15-9-27-24-27Z"/>
    {SYSTEMS.map(name=>{const [x,y]=dots[name];return <g key={name} className={selected===name?"scan-hotspot selected":"scan-hotspot"} role="button" tabIndex={0} aria-label={`Show ${name} details`} onClick={()=>onSelect(name)} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();onSelect(name);}}}>
      <line x1={x} y1={y} x2="222" y2={y}/><circle cx={x} cy={y} r="6"/><text x="226" y={y+4}>{name}</text>
    </g>;})}
  </svg>;
}
export function Body() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  const [selected,setSelected]=useState<System>("Respiration");
  return <LoadState state={load} label="your systems scan">{raw=>{
    const today=raw as ScanToday, engine=today.context_engine, night=today.latest_night;
    const rr=engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm ?? night?.rr_med;
    const details:Record<System,{value:string;copy:string}>={
      Respiration:{value:rr==null?"—":`${fmt(rr)} breaths/min`,copy:rr==null?"No breathing signal is available for this night.":"Compare this with your own breathing pattern on the Sleep screen."},
      Autonomic:{value:night?.rr_var==null?"—":fmt(night.rr_var),copy:night?.rr_var==null?"Autonomic variation is not available in this snapshot.":"Your overnight breathing variation, shown without a diagnostic interpretation."},
      Rest:{value:night?`${fmt(night.presence_hours,1)} h present`:"—",copy:night?`${fmt(night.restless_frac*100,0)}% movement flagged during the sensed period.`:"No valid overnight rest record is available."},
      Mind:{value:engine?.fatigue_and_health_ratings?.mental_fatigue_score==null?"—":`${Math.round(engine.fatigue_and_health_ratings.mental_fatigue_score)} / 100`,copy:engine?.scores_and_metrics?.mental_level==null?"Check-ins add context to this part of your picture.":`Signal level ${engine.scores_and_metrics.mental_level}; interpreted against your own pattern.`},
      Cabin:{value:engine?.user_facing_advisory?.environmental_note?"Note available":"No cabin note",copy:engine?.user_facing_advisory?.environmental_note??"Cabin environment data is not included in this snapshot."},
    };
    const current=details[selected];
    return <><header className="page-heading"><div><p className="eyebrow">Personal systems · latest available night</p><h1>Body</h1><p>A quiet scan of signals, always in the context of your own baseline.</p></div></header>
      {today.sync_status?.state === "api_mock"&&<p className="api-mock-note" role="status">API unavailable · empty preview only; no system readings are being shown.</p>}
      <div className="grid body-grid"><section className="card body-scan-card"><p className="eyebrow">Systems scan</p><h2>Choose a system to explore</h2><p className="muted">Select a marked point on the scan or use the labelled controls.</p>
        <p className="sr-only" id="scan-summary">Five system areas are available: Respiration, Autonomic, Rest, Mind, and Cabin. Selected: {selected}.</p>
        <ScanSvg selected={selected} onSelect={setSelected}/><div className="scan-controls" aria-label="Choose a system">{SYSTEMS.map(s=><button type="button" key={s} className={selected===s?"scan-choice active":"scan-choice"} aria-pressed={selected===s} onClick={()=>setSelected(s)}>{s}</button>)}</div>
        <p className="footnote">The scan is a navigation aid. It does not diagnose or rank your systems.</p></section>
        <section className="card scan-detail" aria-live="polite" aria-labelledby="scan-detail-title"><p className="eyebrow">Selected system</p><h2 id="scan-detail-title">{selected}</h2><strong className="scan-value">{current.value}</strong><p>{current.copy}</p>
          {selected==="Mind"&&engine?.fatigue_and_health_ratings?.physiological_fatigue_score!=null&&<p className="muted">Related body signal: {Math.round(engine.fatigue_and_health_ratings.physiological_fatigue_score)} / 100</p>}
          <p className="muted">Only fields returned by your current personal snapshot are shown.</p></section></div></>;
  }}</LoadState>;
}
