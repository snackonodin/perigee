import type { ReactNode } from "react";
import { StatusChip, type Status } from "./StatusChip";
export function VitalCard({label,value,unit,state,icon,children,advisory,experimental=false}:{label:string;value:ReactNode;unit?:string;state?:Status;icon:ReactNode;children?:ReactNode;advisory?:string;experimental?:boolean}) {
  return <article className={`vital-card glass state-${state}`}>
    <div className="vital-title"><span className="vital-glyph" aria-hidden="true"><svg viewBox="0 0 24 24"><path d={typeof icon==="string"?iconFor(String(icon)):"M5 12h14M12 5v14"}/></svg></span><div><h2>{label}</h2>{experimental&&<span className="experimental">Experimental estimate</span>}</div></div>
    <div className="vital-card-value">{value}{unit&&<small>{unit}</small>}</div>
    {advisory&&<p>{advisory}</p>}{children}{state&&<StatusChip state={state}/>}<span className="vital-baseline">vs your 28-night usual</span>
  </article>;
}
function iconFor(icon:string) { if(icon==="♡")return "M20 8c0 5-8 11-8 11S4 13 4 8a4 4 0 0 1 8-1 4 4 0 0 1 8 1"; if(icon==="≈")return "M4 9c3-5 6 5 9 0s5 1 7 0M4 15c3-5 6 5 9 0s5 1 7 0"; if(icon==="◔")return "M12 3a9 9 0 1 0 9 9h-9zM12 3v9h9"; return "M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16M12 8v5m0 3h.01"; }
