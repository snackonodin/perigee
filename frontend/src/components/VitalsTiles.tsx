import type { BaselineOut, NightOut } from "../api/types";
import { fmt } from "./format";
import { useVitals } from "../live/useVitals";
import type { HeartEvent, WindowEvent } from "../live/types";

type Point={t:number;v:number};
function Trace({label,points,color,band}:{label:string;points:Point[];color:string;band?:[number,number]}) {
  const W=240,H=54,P=5;
  const values=points.map(p=>p.v);
  if(band) values.push(...band);
  const lo=Math.min(...values),hi=Math.max(...values),pad=Math.max((hi-lo)*.18,.5);
  const min=lo-pad,max=hi+pad;
  const x=(i:number)=>P+i/Math.max(points.length-1,1)*(W-2*P);
  const y=(v:number)=>P+(1-(v-min)/(max-min))*(H-2*P);
  const line=points.map((p,i)=>`${x(i)},${y(p.v)}`).join(" ");
  return <svg className="vital-trace" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={points.length?`${label} trend, latest ${fmt(points.at(-1)?.v)}`:`${label} trend not available`}>
    {[.25,.75].map(f=><line key={f} className="trace-grid" x1="0" x2={W} y1={P+f*(H-2*P)} y2={P+f*(H-2*P)}/>)}
    {band&&<rect className="trace-band" x="0" y={y(band[1])} width={W} height={Math.max(1,y(band[0])-y(band[1]))}/>}
    {points.length>1&&<polyline points={line} fill="none" stroke={color} strokeWidth="1.5"/>}
    {points.length>0&&<circle cx={x(points.length-1)} cy={y(points.at(-1)!.v)} r="3" fill={color}/>}
  </svg>;
}

function HeartTile({hearts}:{hearts:readonly HeartEvent[]}) {
  const points=hearts.slice(-30).flatMap(h=>h.hr_bpm==null?[]:[{t:Date.parse(h.t_start),v:h.hr_bpm}]);
  const latest=points.at(-1)?.v;
  return <article className="vital-tile heart-tile" aria-label="Experimental heart-rate estimate">
    <div className="vital-title"><span className="vital-glyph heart-glyph" aria-hidden="true">♡</span><div><h2>Heart rate</h2><p>Live estimate · experimental</p></div></div>
    <strong className="vital-number">{latest==null?"—":fmt(latest,0)} <small>bpm</small></strong>
    <Trace label="Experimental heart rate" points={points} color="var(--violet)"/>
    <p className="vital-caption">{latest==null?"Waiting for a live sensor estimate.":"Research estimate only; no thresholds or alerts."}</p>
  </article>;
}

export function VitalsTiles({night,baseline}:{night?:NightOut|null;baseline?:BaselineOut}) {
  const vitals=useVitals({kind:"live"});
  const windows=vitals.windows.slice(-30);
  const liveWindows=windows.filter(w=>w.presence&&w.rr_a!=null);
  const latest=liveWindows.at(-1);
  const respiration=latest?.rr_a??(night?.valid?night.rr_med:null);
  const band: [number,number]|undefined=baseline?.median!=null&&baseline.mad!=null
    ?[baseline.median-baseline.mad,baseline.median+baseline.mad]:undefined;
  const rrPoints:Point[]=liveWindows.flatMap((w:WindowEvent)=>w.rr_a==null?[]:[{t:Date.parse(w.t_start),v:w.rr_a}]);
  const status=vitals.status.state==="open"?"Live signal":vitals.status.state==="connecting"||vitals.status.state==="reconnecting"?"Connecting to sensor":"Latest valid night";
  return <>
    <article className="vital-tile respiration-tile" aria-label="Personal respiration rate">
      <div className="vital-title"><span className="vital-glyph breath-glyph" aria-hidden="true">≈</span><div><h2>Breathing</h2><p>{latest?"Live window":night?.valid?"Latest valid night":"No reading yet"}</p></div></div>
      <strong className="vital-number">{respiration==null?"—":fmt(respiration)} <small>breaths/min</small></strong>
      <Trace label="Breathing rate" points={rrPoints} color="var(--aurora)" band={band}/>
      {band?<div className="vital-range"><span>{fmt(band[0])}</span><span>Your 28-night range</span><span>{fmt(band[1])}</span></div>:<p className="vital-caption">Your personal breathing range is still taking shape.</p>}
      <p className="vital-caption">{status}{latest&&` · quality ${fmt(latest.quality*100,0)}%`}</p>
    </article>
    <HeartTile hearts={vitals.hearts}/>
  </>;
}
