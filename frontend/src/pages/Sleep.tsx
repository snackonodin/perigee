import { plainHeadline, plainMessage } from "../components/advisory";
import { useState } from "react";
import { api } from "../api/client";
import type { BaselineOut, NightOut, TodayOut } from "../api/types";
import { useLoad } from "../api/useLoad";
import { fmt } from "../components/format";
import { LoadState } from "../components/LoadState";
import { NightsTable } from "../components/NightsTable";
import { useChartWidth } from "../components/useChartWidth";
import { RrTrend } from "../components/RrTrend";
import { SleepArc } from "../components/SleepArc";
import { StatusChip, type Status } from "../components/StatusChip";
import { Icon } from "../components/icons";
import "./Sleep.css";

const DAYS = 28;
type SleepToday = TodayOut & { context_engine?: {
  scores_and_metrics?: { phys_level?: number };
  user_facing_advisory?: { headline?:string; personality_tailored_message?:string };
  flight_surgeon_briefing_snippet?:string;
} | null };

function levelStatus(level?:number):Status { return level==null?"none":level>=2?"alert":level===1?"watch":"normal"; }

function SleepTimeline({ nights, days = DAYS }: { nights: NightOut[]; days?: number }) {
  const [box,W]=useChartWidth<HTMLElement>(720);
  const H=220,L=42,R=14,T=14,B=30;
  const end=Date.now(), start=end-(days-1)*86_400_000;
  const dates=Array.from({length:days},(_,i)=>new Date(start+i*86_400_000).toISOString().slice(0,10));
  const values=nights.filter(n=>n.valid).map(n=>n.presence_hours);
  if (!values.length) return <div className="sleep-empty-inline"><div className="ghost-ticks" aria-hidden="true">{dates.map(d=><i key={d}/>)}</div><span className="meta-label ghost-tonight" aria-hidden="true">Tonight</span><p className="vital-empty"><Icon name="sleep" size={24}/><span>No valid nights in this window yet.</span></p></div>;
  const maxHours=Math.max(8,Math.ceil(Math.max(...values)/4)*4);
  const x=(index:number)=>L+(index/Math.max(days-1,1))*(W-L-R);
  const y=(hours:number)=>T+(1-Math.min(hours,maxHours)/maxHours)*(H-T-B);
  const latest=dates.map(date=>nights.find(n=>n.date===date&&n.valid)).filter((n):n is NightOut=>!!n).at(-1);
  return <figure className="sleep-timeline" ref={box}><svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="sleep-timeline-title sleep-timeline-desc">
    <title id="sleep-timeline-title">Nightly sensed rest over {days} days</title>
    <desc id="sleep-timeline-desc">{values.length} valid nights. Bars show hours present overnight; missing bars are nights without a valid signal.</desc>
    {[0,.5,1].map((f,i)=>{const yy=y(maxHours*f);return <g key={i}><line className="gridline" x1={L} x2={W-R} y1={yy} y2={yy}/><text className="label" x={L-7} y={yy+4} textAnchor="end">{fmt(maxHours*f,0)} h</text></g>;})}
    <line className="axis" x1={L} x2={W-R} y1={H-B} y2={H-B}/>
    <text className="label" x={L} y={H-8}>{new Date(start).toISOString().slice(5,10)}</text>
    <text className="label" x={W-R} y={H-8} textAnchor="end">{new Date(end).toISOString().slice(5,10)}</text>
    {dates.map((date,i)=>{const n=nights.find(item=>item.date===date&&item.valid);const isLatest=!!n&&n.id===latest?.id;return <g key={date}><rect aria-label={`${date}: ${n?`${fmt(n.presence_hours,1)} hours, recorded`:"No reading; no valid signal"}`} className={isLatest?"sleep-bar sleep-bar-latest":n?"sleep-bar":"sleep-bar-empty"} x={x(i)-3} y={n?y(n.presence_hours):H-B-2} width="6" height={n?Math.max(1,H-B-y(n.presence_hours)):2}><title>{`${date}: ${n?`${fmt(n.presence_hours,1)} hours present`:"No reading"}`}</title></rect></g>;})}
  </svg><div className="sleep-last-night-label">{latest&&<span>Last night · {latest.date}</span>}<span>Each bar shows sensed presence; no sleep stages are available.</span></div>
  <table className="sleep-visually-hidden"><caption>Presence by night</caption><thead><tr><th>Date</th><th>Presence</th><th>Status</th></tr></thead><tbody>{dates.map(date=>{const n=nights.find(item=>item.date===date&&item.valid);return <tr key={date}><td>{date}</td><td>{n?`${fmt(n.presence_hours,1)} hours`:"No reading"}</td><td>{n?"Recorded":"No valid signal"}</td></tr>;})}</tbody></table></figure>;
}

function BreathingTile({ latest, baseline }: { latest?: NightOut; baseline?: BaselineOut }) {
  const value=latest?.rr_med;
  const low=baseline?.median!=null&&baseline.mad!=null?baseline.median-baseline.mad:undefined;
  const high=baseline?.median!=null&&baseline.mad!=null?baseline.median+baseline.mad:undefined;
  const spread=low!=null&&high!=null?Math.max(high-low,1):undefined;
  const position=typeof value==="number"&&low!=null&&spread!=null?Math.max(2,Math.min(98,((value-(low-spread))/(3*spread))*100)):undefined;
  if(value==null)return <section className="card sleep-metric" aria-labelledby="rr-tile-title"><h2 id="rr-tile-title">Night breathing rate</h2><p className="section-meta">Latest valid night</p>
    <p className="vital-empty"><Icon name="breath" size={24}/><span>Your night breathing rate appears after your first full night near the sensor.</span></p></section>;
  return <section className="card sleep-metric" aria-labelledby="rr-tile-title"><h2 id="rr-tile-title">Night breathing rate</h2><p className="section-meta">Latest valid night</p>
    <strong className="sleep-metric-value">{fmt(value)}<small>br/min</small></strong>
    {position!=null?<><div className="sleep-baseline" aria-label={`Personal median range ${fmt(low)} to ${fmt(high)}`}><div className="sleep-baseline-band"/><span className="sleep-baseline-marker" style={{left:`${position}%`}}/></div><div className="sleep-baseline-caption"><span>{fmt(low)}</span><span>Your median ± MAD range</span><span>{fmt(high)}</span></div></>:<p className="muted">Your personal range will appear as valid nights build.</p>}
    <p className="footnote">The shaded range is your own median ± MAD. A difference is described as unusual for you.</p>
  </section>;
}

function Regularity({ nights }: { nights: NightOut[] }) {
  const lastSeven=nights.filter(n=>n.valid).sort((a,b)=>a.date.localeCompare(b.date)).slice(-7);
  const recent=lastSeven.filter(n=>n.midsleep);
  const newest=recent.at(-1)?.midsleep;
  if(recent.length<2)return <section className="card regularity-card" aria-labelledby="regularity-title"><h2 id="regularity-title">Regularity</h2>
    <p className="vital-empty"><Icon name="clock" size={24}/><span>Your rhythm shows after two nights with a midsleep time.</span></p></section>;
  return <section className="card regularity-card" aria-labelledby="regularity-title"><h2 id="regularity-title">Regularity</h2>
    <p>{`${recent.length} of the latest ${lastSeven.length} valid nights include a midsleep estimate.`}</p>
    {newest&&<p className="muted">Latest midsleep: {new Date(newest).toISOString().slice(11,16)} UTC</p>}
  </section>;
}

export function Sleep() {
  const [detailsOpen,setDetailsOpen]=useState(false);
  const end=new Date(), start=new Date(end.getTime()-(DAYS-1)*86_400_000);
  const from=start.toISOString().slice(0,10),to=end.toISOString().slice(0,10);
  const nights=useLoad(()=>api.GET("/api/v1/nights",{params:{query:{from,to}}}),[from,to]);
  const today=useLoad(()=>api.GET("/api/v1/today"));
  const baseline=today.data?.baselines.find(b=>b.feature==="rr_med");
  const sleepToday=today.data as SleepToday|undefined;
  const level=sleepToday?.context_engine?.scores_and_metrics?.phys_level??sleepToday?.flags[0]?.phys_level;
  const latestValid=[...(nights.data??[])].filter(n=>n.valid).sort((a,b)=>a.date.localeCompare(b.date)).at(-1);
  const sleepAdvisory=sleepToday?.context_engine?.user_facing_advisory;
  const explanation=plainMessage(sleepAdvisory?.personality_tailored_message)??plainHeadline(sleepAdvisory?.headline)??"The API did not include a sleep note.";
  const validCount=nights.data?.filter(n=>n.valid).length;
  const status=levelStatus(level);
  return <div className="sleep-page"><header className="page-heading"><div><h1>Sleep</h1><p>Night by night, compared with your own recent pattern.</p></div>{status!=="none"&&<StatusChip state={status}/>}</header>
    {sleepToday?.sync_status?.state==="api_mock"&&<p className="api-mock-note" role="status">API unavailable · empty preview only; no sleep readings are being shown.</p>}
    {nights.apiMock&&<p className="api-mock-note" role="status">API unavailable · empty preview only; no night records are being shown.</p>}
    <div className="sleep-bento">
      <div className="sleep-bento-arc"><SleepArc night={latestValid} status={status} explanation={explanation}/></div>
      <BreathingTile latest={latestValid} baseline={baseline}/>
      {nights.data?<Regularity nights={nights.data}/>:<section className="card regularity-card"><h2>Regularity</h2><p className="muted">Available when the recent nights load.</p></section>}
      <section className="card wide sleep-hero" data-pet-perch aria-labelledby="timeline-heading"><div className="row"><div><h2 id="timeline-heading">Time present overnight</h2></div><span className="telemetry nights-count">{validCount??"—"} / {DAYS} nights with readings</span></div>
        <LoadState state={nights} label="nightly timeline">{data=><SleepTimeline nights={data}/>}</LoadState></section>
      {(validCount??0)>0&&<section className="card wide sleep-trend-card" data-pet-perch aria-labelledby="rr-trend-title"><h2 id="rr-trend-title">Breathing-rate trend</h2><LoadState state={nights} label="breathing trend">{data=><RrTrend nights={data} baseline={baseline} days={DAYS}/>}</LoadState>
        {today.error&&<p className="muted">Personal baseline could not be loaded. Showing night data without its band.</p>}
      </section>}
      <section className="card wide sleep-details"><button className="sleep-details-toggle" type="button" aria-expanded={detailsOpen} aria-controls="sleep-night-details" onClick={()=>setDetailsOpen(v=>!v)}><span>Night-by-night details</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>{detailsOpen&&<div id="sleep-night-details" className="sleep-night-table">{nights.data&&<NightsTable nights={nights.data}/>}</div>}</section>
    </div></div>;
}
