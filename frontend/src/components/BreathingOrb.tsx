import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import type { Status } from "./StatusChip";
export function BreathingOrb({rate,state}:{rate:number|null|undefined;state:Status}) {
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{const el=ref.current;if(!el||rate==null||state==="none"||!window.matchMedia)return;const mm=gsap.matchMedia();mm.add("(prefers-reduced-motion: no-preference)",()=>{const period=Math.max(2,Math.min(10,60/rate));const tween=gsap.to(el,{scale:.94,duration:period/2,yoyo:true,repeat:-1,ease:"sine.inOut",transformOrigin:"center"});return()=>tween.kill();});return()=>mm.revert();},[rate,state]);
  return <div ref={ref} className={`breathing-orb ${state}`} role="img" aria-label={rate==null?"No breathing reading":`Breathing rate ${rate} breaths per minute`}><strong>{rate==null?"No reading":rate}</strong>{rate!=null&&<span>br/min</span>}</div>;
}
