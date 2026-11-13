import { Link } from "react-router";
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
function status(level?:number):Status { if(level==null)return "none"; if(level>=2)return "alert"; if(level===1)return "watch"; return "normal"; }

export function Overview() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  return <LoadState state={load} label="today's personal snapshot">{raw=>{
    const today=raw as EngineToday,engine=today.context_engine,night=today.latest_night;
    const physiology=engine?.scores_and_metrics?.phys_level??today.flags[0]?.phys_level;
    const mental=engine?.scores_and_metrics?.mental_level??today.flags[0]?.mental_level;
    const health=engine?.fatigue_and_health_ratings,baseline=today.baselines.find(b=>b.feature==="rr_med");
    const respiration=engine?.dashboard_visualization_data?.dual_axis_timeline_point?.respiration_bpm??(night?.valid?night.rr_med:null);
    const advisory=engine?.user_facing_advisory;
    const resilience=health?.overall_health_resilience_index;
    return <div className="screen-page today-page">
      <header className="page-heading"><div><p className="eyebrow">Your personal snapshot</p><h1>Today</h1><p>{night?`Last signal · ${night.date}`:"Your next quiet check-in"}</p></div></header>
      {load.apiMock&&<p className="api-mock-note" role="status">Showing sample data: live service unavailable</p>}
      <section className="today-hero-card glass" aria-labelledby="today-hero-title">
        <BreathingOrb rate={respiration} state={status(physiology)}/>
        <div className="today-hero-copy"><p className="eyebrow">Breathing · your recent pattern</p><h2 id="today-hero-title">{respiration==null?"Your picture is taking shape":"Your breathing, in context"}</h2>
          <p>{respiration==null?"Readings appear after a full night near the sensor.":"Compared with your own recent nights."}</p>
          <div className="today-hero-actions"><span className="hero-resilience">{resilience==null?"Personal picture building":<><strong>{Math.round(resilience)}</strong> resilience index</>}</span>
            {today.pending_checkins[0]&&<Link className="hero-action" to={`/checkin?instrument=${encodeURIComponent(today.pending_checkins[0].instrument_id)}`}>Check in <span aria-hidden="true">→</span></Link>}
          </div>
        </div>
      </section>
      <section className="today-signal-grid" aria-label="Latest body and check-in signals">
        <VitalsTiles night={night} baseline={baseline} status={status(physiology)}/>
        <VitalCard label="Mind and check-ins" value={health?.mental_fatigue_score==null?"No reading":`${Math.round(health.mental_fatigue_score)} / 100`} icon="◌" state={health?.mental_fatigue_score==null?"none":status(mental)}>
          <p className="vital-caption">{health?.mental_fatigue_score==null?"Check-ins add context over time.":"From your recent personal inputs."}</p>
        </VitalCard>
        <VitalCard label="Rest" value={night?.valid?fmt(night.presence_hours,1):"No reading"} unit={night?.valid?"h":undefined} icon="◔" state={night?.valid?undefined:"none"}>
          <p className="vital-caption">{night?.valid?"Sensed presence last night.":"Readings appear after a full night near the sensor."}</p>
        </VitalCard>
      </section>
      <aside className="today-note-card glass-strong"><span aria-hidden="true">✧</span><div><p className="eyebrow">A quiet note</p><strong>{advisory?.headline??"Notice your own rhythm"}</strong><p>{advisory?.personality_tailored_message??"Your patterns are compared with your own recent baseline."}</p></div></aside>
    </div>;
  }}</LoadState>;
}
