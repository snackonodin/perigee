import type { ReactNode } from "react";
import { Link } from "react-router";
import { Spotlight } from "./Spotlight";
import { StatusChip, type Status } from "./StatusChip";
/** `empty`: one sentence saying what will appear and when. When set, the card shows only that (B8). */
export function VitalCard({label,value,unit,state,icon,children,advisory,experimental=false,empty,headingId,to}:{label:string;value?:ReactNode;unit?:string;state?:Status;icon:ReactNode;children?:ReactNode;advisory?:string;experimental?:boolean;empty?:string;headingId?:string;to?:string}) {
  const card=<article className={`vital-card${to?" tile-press has-link":""} glass state-${empty?"none":state}${empty?" vital-card-empty":""}`}>
    <div className="vital-title"><span className="vital-glyph" aria-hidden="true"><svg viewBox="0 0 24 24"><path d={typeof icon==="string"?iconFor(String(icon)):"M5 12h14M12 5v14"}/></svg></span><div className="vital-title-text"><h2 id={headingId}>{label}</h2>{experimental&&<span className="tag-mono" title="Experimental estimate">Experimental</span>}</div></div>
    {empty?<p className="vital-empty"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 8v4l2.5 1.5"/></svg><span>{empty}</span></p>:<>
    <div className="vital-card-value">{value}{unit&&<small>{unit}</small>}</div>
    {advisory&&<p>{advisory}</p>}{children}{state&&<StatusChip state={state}/>}<span className="vital-baseline">vs your 28-night usual</span></>}
    {to&&<Link className="tile-link" to={to} aria-label={`Open ${label}`}/>}
  </article>;
  return to?<Spotlight>{card}</Spotlight>:card;
}
function iconFor(icon:string) { if(icon==="♡")return "M20 8c0 5-8 11-8 11S4 13 4 8a4 4 0 0 1 8-1 4 4 0 0 1 8 1"; if(icon==="≈")return "M4 9c3-5 6 5 9 0s5 1 7 0M4 15c3-5 6 5 9 0s5 1 7 0"; if(icon==="◔")return "M12 3a9 9 0 1 0 9 9h-9zM12 3v9h9"; return "M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16M12 8v5m0 3h.01"; }
