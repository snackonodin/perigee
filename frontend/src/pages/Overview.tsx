import type { CSSProperties } from "react";
import { Link } from "react-router";
import { useAuth } from "../auth/AuthProvider";
import { plainHeadline, plainMessage } from "../components/advisory";
import { Icon } from "../components/icons";
import "./Today.css";
import { api } from "../api/client";
import type { TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { VitalsTiles } from "../components/VitalsTiles";
import { BreathingOrb } from "../components/BreathingOrb";
import { VitalCard } from "../components/VitalCard";
import type { Status } from "../components/StatusChip";

type EngineToday = TodayOut & { context_engine?: {
  scores_and_metrics?: { phys_level?: number; mental_level?: number };
  fatigue_and_health_ratings?: { mental_fatigue_score?: number; overall_health_resilience_index?: number };
  dashboard_visualization_data?: { dual_axis_timeline_point?: { respiration_bpm?: number|null } };
  user_facing_advisory?: { headline?: string; personality_tailored_message?: string };
} | null };
/** Nights in the personal baseline window (DESIGN: 28-night baseline). */
const BASELINE_NIGHTS=28;
function stationLabel(offset?:number|null):string { if(!offset)return "UTC"; const a=Math.abs(offset); return `UTC${offset>0?"+":"-"}${String(Math.floor(a/60)).padStart(2,"0")}:${String(a%60).padStart(2,"0")}`; }
function stationClock(offset?:number|null):string { const d=new Date(Date.now()+(offset??0)*60000); return `${String(d.getUTCHours()).padStart(2,"0")}:${String(d.getUTCMinutes()).padStart(2,"0")}`; }
function status(level?:number):Status { if(level==null)return "none"; if(level>=2)return "alert"; if(level===1)return "watch"; return "normal"; }

export function Overview() {
  const { me }=useAuth();
  const load=useLoad(()=>api.GET("/api/v1/today"));
  return <LoadState state={load} label="today's personal snapshot">{raw=>{
    const today=raw as EngineToday,engine=today.context_engine,night=today.latest_night;
    const physiology=engine?.scores_and_metrics?.phys_level??today.flags[0]?.phys_level;
    const mental=engine?.scores_and_metrics?.mental_level??today.flags[0]?.mental_level;
    const health=engine?.fatigue_and_health_ratings,baseline=today.baselines.find(b=>b.feature==="rr_med");
    const respiration=engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm??(night?.valid?night.rr_med:null);
    const advisory=engine?.user_facing_advisory;
    const resilience=health?.overall_health_resilience_index;
    const pace=baseline?.median??null;
    const nights=Math.max(0,Math.min(BASELINE_NIGHTS,baseline?.n??0));
    const pending=today.pending_checkins[0];
    return <div className="screen-page today-page">
      <header className="page-heading"><div><h1>Today</h1><p>{night?`Last signal · ${night.date}`:"Your next quiet check-in"}</p></div></header>
      {load.apiMock&&<p className="api-mock-note" role="status">Showing sample data: live service unavailable</p>}
      <div className="today-bento">
        <section className="today-hero-card bento-hero" data-pet-perch aria-labelledby="today-hero-title">
          <div className="hero-orb-stage orbit" style={{"--orbit-inset":"-18px"} as CSSProperties}>
            <BreathingOrb rate={respiration} pace={pace} state={status(physiology)}/>
            <span className="satellite" style={{"--sat-a":`${-90+nights/BASELINE_NIGHTS*360}deg`} as CSSProperties} aria-hidden="true"/>
          </div>
          <div className="today-hero-copy"><h2 id="today-hero-title">{respiration==null?"Your picture is taking shape":"Your breathing, in context"}</h2>
            <p>{respiration==null?"Readings appear after a full night near the sensor.":"Compared with your own recent nights."}</p>
            {pending&&<div className="today-hero-actions"><Link className="hero-action" to={`/checkin?instrument=${encodeURIComponent(pending.instrument_id)}`}>Check in <span aria-hidden="true">→</span></Link></div>}
          </div>
          <dl className="tonight-panel" aria-label="Tonight">
            <div><dt className="meta-label">Station time</dt><dd>{stationClock(me?.station_time_offset_min)}<small>{stationLabel(me?.station_time_offset_min)}</small></dd></div>
            <div><dt className="meta-label">In your baseline</dt><dd>{nights}<small> / {BASELINE_NIGHTS}</small></dd>
              <span className="nights-track" aria-hidden="true"><i style={{width:`${nights/BASELINE_NIGHTS*100}%`}}/></span></div>
            <div><dt className="meta-label">Resilience index</dt><dd>{resilience==null?"—":Math.round(resilience)}<small> / 100</small></dd>
              <span className="tonight-caption">{resilience==null?"Builds with your first nights":"From your recent nights and check-ins"}</span></div>
            <div><dt className="meta-label">Next check-in</dt><dd className="tonight-next">{pending?(pending.slot==="pm"?"Evening":"Morning"):"None due"}</dd></div>
          </dl>
        </section>
        <VitalsTiles night={night} baseline={baseline} status={status(physiology)}/>
        {health?.mental_fatigue_score==null?<VitalCard label="Mind and check-ins" icon="◌" to="/checkin" empty="Your check-ins add context here after the first few days."/>:
        <VitalCard label="Mind and check-ins" to="/checkin" value={`${Math.round(health.mental_fatigue_score)} / 100`} icon="◌" state={status(mental)}>
          <p className="vital-caption">From your recent personal inputs.</p>
        </VitalCard>}
        {night?.valid?<VitalCard label="Rest" to="/sleep" value={fmt(night.presence_hours,1)} unit="h" icon="◔">
          <p className="vital-caption">Sensed presence last night.</p>
        </VitalCard>:<VitalCard label="Rest" icon="◔" to="/sleep" empty="Time at rest appears after your first full night near the sensor."/>}
        <aside className="today-note-card bento-wide" data-pet-perch><span className="note-glyph" aria-hidden="true"><Icon name="briefing" size={20}/></span><div><strong>{plainHeadline(advisory?.headline)??"Notice your own rhythm"}</strong><p>{plainMessage(advisory?.personality_tailored_message)??"Your patterns are compared with your own recent baseline."}</p></div></aside>
      </div>
    </div>;
  }}</LoadState>;
}
