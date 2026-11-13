export function EcgTrace({points,label="Pulse trace"}:{points:readonly {t:number;v:number}[];label?:string}) {
  if(!points.length)return <p className="muted">No reading</p>;
  const vals=points.map(p=>p.v),lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo||1;
  const xy=points.map((p,i)=>`${i/(Math.max(points.length-1,1))*100},${92-(p.v-lo)/span*80}`).join(" ");
  return <figure className="ecg-trace glass-strong"><svg viewBox="0 0 100 100" role="img" aria-label={`${label}: latest ${points.at(-1)?.v}`}><path d="M0 25H100M0 50H100M0 75H100" className="trace-grid"/><polyline key={points.at(-1)?.t} points={xy} fill="none" stroke="var(--text)" strokeWidth="2" vectorEffect="non-scaling-stroke"/><circle cx={xy.split(" ").at(-1)?.split(",")[0]} cy={xy.split(" ").at(-1)?.split(",")[1]} r="3" fill="var(--peach)" stroke="var(--text)"/></svg><figcaption>Experimental estimate, not a medical ECG.</figcaption></figure>;
}
