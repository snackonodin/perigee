import { api } from "../api/client";
import type { BaselineOut, NightOut, TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { NightsTable } from "../components/NightsTable";
import { RrTrend } from "../components/RrTrend";

const DAYS = 28;
type SleepToday = TodayOut & { context_engine?: {
  scores_and_metrics?: { phys_level?: number };
} | null };

function LevelPill({level}:{level?:number}) {
  const status=level==null?{name:"Building your picture",tone:"quiet"}:level>=2?{name:"Alert",tone:"high"}:level===1?{name:"Watch",tone:"watch"}:{name:"Normal",tone:"usual"};
  return <span className={`status-chip ${status.tone}`}><span aria-hidden="true">◌</span>{status.name}</span>;
}

function SleepTimeline({ nights, days = DAYS }: { nights: NightOut[]; days?: number }) {
  const valid=nights.filter(n=>n.valid).sort((a,b)=>a.date.localeCompare(b.date));
  if (!valid.length) return <div className="chart-empty"><p className="muted">No valid nights in this window yet.</p></div>;
  const W=720,H=220,L=42,R=14,T=14,B=30;
  const end=Date.now(), start=end-(days-1)*86_400_000;
  const maxHours=Math.max(8,Math.ceil(Math.max(...valid.map(n=>n.presence_hours))/4)*4);
  const x=(date:string)=>L+((Date.parse(`${date}T00:00:00Z`)-start)/(end-start))*(W-L-R);
  const y=(hours:number)=>T+(1-Math.min(hours,maxHours)/maxHours)*(H-T-B);
  const last=valid[valid.length-1];
  return <figure className="sleep-timeline"><svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="sleep-timeline-title sleep-timeline-desc">
    <title id="sleep-timeline-title">Nightly sensed rest over {days} days</title>
    <desc id="sleep-timeline-desc">{valid.length} valid nights. Bars show hours present overnight; missing bars are nights without a valid signal.</desc>
    {[0,.5,1].map((f,i)=>{const yy=y(maxHours*f);return <g key={i}><line className="gridline" x1={L} x2={W-R} y1={yy} y2={yy}/><text className="label" x={L-7} y={yy+4} textAnchor="end">{fmt(maxHours*f,0)} h</text></g>;})}
    <line className="axis" x1={L} x2={W-R} y1={H-B} y2={H-B}/>
    <text className="label" x={L} y={H-8}>{new Date(start).toISOString().slice(5,10)}</text>
    <text className="label" x={W-R} y={H-8} textAnchor="end">{new Date(end).toISOString().slice(5,10)}</text>
    {valid.map(n=><rect key={n.id} className={n.id===last.id?"sleep-bar latest":"sleep-bar"} x={x(n.date)-4} y={y(n.presence_hours)} width="8" height={Math.max(1,H-B-y(n.presence_hours))} rx="4"><title>{`${n.date}: ${fmt(n.presence_hours,1)} hours present`}</title></rect>)}
  </svg><figcaption className="muted">Each bar is sensed time present, not a sleep-stage estimate. Gaps indicate nights without a valid signal.</figcaption></figure>;
}

function BreathingTile({ latest, baseline }: { latest?: NightOut; baseline?: BaselineOut }) {
  const value=latest?.rr_med;
  const low=baseline?.median!=null&&baseline.mad!=null?baseline.median-baseline.mad:undefined;
  const high=baseline?.median!=null&&baseline.mad!=null?baseline.median+baseline.mad:undefined;
  const spread=low!=null&&high!=null?Math.max(high-low,1):undefined;
  const position=typeof value==="number"&&low!=null&&spread!=null?Math.max(2,Math.min(98,((value-(low-spread))/(3*spread))*100)):undefined;
  return <section className="card sleep-metric" aria-labelledby="rr-tile-title"><p className="eyebrow">Breathing · latest valid night</p><h2 id="rr-tile-title">Night breathing rate</h2>
    <strong className="sleep-metric-value">{value==null?"—":`${fmt(value)} /min`}</strong>
    {position!=null?<><div className="baseline-track" aria-label={`Personal range ${fmt(low)} to ${fmt(high)}`}><span className="baseline-marker" style={{left:`${position}%`}}/></div><div className="baseline-caption"><span>{fmt(low)}</span><span>Your 28-night range</span><span>{fmt(high)}</span></div></>:<p className="muted">Your personal range will appear as valid nights build.</p>}
    <p className="footnote">The shaded range is your own median ± MAD. A difference is described as unusual for you.</p>
  </section>;
}

function Regularity({ nights }: { nights: NightOut[] }) {
  const lastSeven=nights.filter(n=>n.valid).sort((a,b)=>a.date.localeCompare(b.date)).slice(-7);
  const recent=lastSeven.filter(n=>n.midsleep);
  const newest=recent.at(-1)?.midsleep;
  return <section className="card regularity-card" aria-labelledby="regularity-title"><p className="eyebrow">Your rhythm</p><h2 id="regularity-title">Regularity</h2>
    <strong className="sleep-metric-value">{recent.length<2?"Building":"Recent midsleep"}</strong>
    <p>{recent.length<2?"Two or more valid midsleep times are needed to show a personal pattern.":`${recent.length} of the latest ${lastSeven.length} valid nights include a midsleep estimate.`}</p>
    {newest&&<p className="muted">Latest midsleep: {new Date(newest).toISOString().slice(11,16)} UTC</p>}
  </section>;
}

export function Sleep() {
  const end=new Date(), start=new Date(end.getTime()-(DAYS-1)*86_400_000);
  const from=start.toISOString().slice(0,10),to=end.toISOString().slice(0,10);
  const nights=useLoad(()=>api.GET("/api/v1/nights",{params:{query:{from,to}}}),[from,to]);
  const today=useLoad(()=>api.GET("/api/v1/today"));
  const baseline=today.data?.baselines.find(b=>b.feature==="rr_med");
  const sleepToday=today.data as SleepToday|undefined;
  const level=sleepToday?.context_engine?.scores_and_metrics?.phys_level??sleepToday?.flags[0]?.phys_level;
  const latestValid=[...(nights.data??[])].filter(n=>n.valid).sort((a,b)=>a.date.localeCompare(b.date)).at(-1);
  return <><header className="page-heading"><div><p className="eyebrow">Rest cycle · your personal log</p><h1>Sleep</h1><p>Night by night, compared with your own recent pattern.</p></div><LevelPill level={level}/></header>
    {sleepToday?.sync_status?.state==="api_mock"&&<p className="api-mock-note" role="status">API unavailable · empty preview only; no sleep readings are being shown.</p>}
    {nights.apiMock&&<p className="api-mock-note" role="status">API unavailable · empty preview only; no night records are being shown.</p>}
    <div className="grid sleep-grid"><section className="card wide sleep-hero" aria-labelledby="timeline-heading"><div className="row"><div><p className="eyebrow">28-night view</p><h2 id="timeline-heading">Time present overnight</h2></div><span className="pill">{nights.data?.filter(n=>n.valid).length??"—"} valid nights</span></div>
      <LoadState state={nights} label="nightly timeline">{data=><SleepTimeline nights={data}/>}</LoadState></section>
      <BreathingTile latest={latestValid} baseline={baseline}/>
      {nights.data?<Regularity nights={nights.data}/>:<section className="card regularity-card"><p className="eyebrow">Your rhythm</p><h2>Regularity</h2><p className="muted">Available when the recent nights load.</p></section>}
      <section className="card wide sleep-trend-card" aria-labelledby="rr-trend-title"><p className="eyebrow">Personal signal</p><h2 id="rr-trend-title">Breathing-rate trend</h2><LoadState state={nights} label="breathing trend">{data=><RrTrend nights={data} baseline={baseline} days={DAYS}/>}</LoadState>
        {today.error&&<p className="muted">Personal baseline could not be loaded. Showing night data without its band.</p>}
      </section>
      <details className="card wide sleep-details"><summary>Night-by-night details</summary>{nights.data&&<NightsTable nights={nights.data}/>}</details>
    </div></>;
}
