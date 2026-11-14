import type { NightOut } from "../api/types";
import { StatusChip, type Status } from "./StatusChip";

function fraction(night:NightOut) {
  const start=Date.parse(night.onset??""),middle=Date.parse(night.midsleep??""),end=Date.parse(night.wake??"");
  if(!Number.isFinite(start)||!Number.isFinite(middle)||!Number.isFinite(end)||end<=start)return null;
  return Math.max(0,Math.min(1,(middle-start)/(end-start)));
}

export function SleepArc({night,status,explanation,coverage}:{night?:NightOut;status:Status;explanation:string;coverage?:number}) {
  if(!night?.valid)return <section className="sleep-arc-card glass sleep-arc-empty" aria-labelledby="sleep-arc-title">
    <div className="sleep-arc-heading"><h2 id="sleep-arc-title">Sleep summary</h2></div>
    <div className="sleep-arc-stage"><svg className="sleep-arc" viewBox="0 0 200 118" aria-hidden="true"><path className="sleep-arc-track ghost" d="M18 100 A82 82 0 0 1 182 100"/></svg><span className="meta-label sleep-arc-wait">Awaiting first night</span></div>
    <p className="vital-empty"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 15.5A8 8 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z"/></svg><span>Your night appears here, onset to wake, after your first full night near the sensor.</span></p></section>;
  const at=fraction(night),x=at==null?null:18+164*at,y=at==null?null:100-Math.sin(Math.PI*at)*82;
  const partial=coverage!=null&&coverage<1;
  return <section className="sleep-arc-card glass" aria-labelledby="sleep-arc-title">
    <div className="sleep-arc-heading"><h2 id="sleep-arc-title">Time present overnight</h2><p className="section-meta">Last night · <span className="telemetry">{night.date}</span></p></div>
    <svg className="sleep-arc" viewBox="0 0 200 118" role="img" aria-label={`${fmtHours(night.presence_hours)} present, ${time(night.onset)} to ${time(night.wake)} UTC${at==null?"":"; midsleep marked on arc"}`}>
      <path className="sleep-arc-track" d="M18 100 A82 82 0 0 1 182 100"/>
      <path className={`sleep-arc-value${partial?"":" draw-once"}`} pathLength={258} d="M18 100 A82 82 0 0 1 182 100" strokeDasharray={partial?`${Math.max(0,Math.min(1,coverage!))*258} 258`:undefined}/>
      {partial&&<path className="sleep-arc-uncovered" d="M18 100 A82 82 0 0 1 182 100" strokeDasharray={`${(1-coverage!)*258} 258`} strokeDashoffset={`${-coverage!*258}`}/>}
      {x!=null&&y!=null&&<circle className="sleep-arc-midpoint" cx={x} cy={y} r="5"/>}
    </svg>
    <div className="sleep-arc-metrics"><strong>{typeof night.presence_hours==="number"?<>{night.presence_hours.toFixed(1)}<small>h</small></>:"No reading"}</strong><span>present overnight</span></div>
    <div className="sleep-arc-times"><span><small>Onset</small>{time(night.onset)}</span><span><small>Midsleep</small>{night.midsleep?time(night.midsleep):"No reading"}</span><span><small>Wake</small>{time(night.wake)}</span></div>
    {partial&&<p className="sleep-coverage-label">Partial coverage</p>}
    {status!=="none"&&<StatusChip state={status}/>}<p className="sleep-arc-explanation">{explanation}</p>
  </section>;
}
function time(value:string|null|undefined) { return value?new Date(value).toISOString().slice(11,16):"No reading"; }
function fmtHours(value:number|null|undefined) { return typeof value==="number"?`${value.toFixed(1)} h`:"No reading"; }
