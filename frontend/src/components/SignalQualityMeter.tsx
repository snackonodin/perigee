export function SignalQualityMeter({value,label="Signal quality"}:{value:number;label?:string}) {
  const n=Math.max(0,Math.min(4,Math.round(value)));
  const word=["No signal","Poor","Weak","Good","Strong"][n];
  return <div className="signal-quality" aria-label={`${label}: ${word}`}><span aria-hidden="true">{[0,1,2,3].map(i=><i key={i} className={i<n?"filled":""}/>)}</span><span>{word}</span></div>;
}
