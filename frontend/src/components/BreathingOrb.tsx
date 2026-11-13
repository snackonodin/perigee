import type { CSSProperties } from "react";
import type { Status } from "./StatusChip";
export function BreathingOrb({rate,state}:{rate:number|null|undefined;state:Status}) {
  const valid=typeof rate==="number"&&rate>0;
  const period=valid?Math.max(2,Math.min(10,60/rate!)):4;
  return <div className="breathing-orb-ring glass"><div className={`breathing-orb ${state}`} style={{"--breath-period":`${period}s`} as CSSProperties} role="img" aria-label={!valid?"No breathing reading":`Breathing rate ${rate} breaths per minute`}><strong>{!valid?"No reading":rate}</strong>{valid&&<span>br/min</span>}</div></div>;
}
