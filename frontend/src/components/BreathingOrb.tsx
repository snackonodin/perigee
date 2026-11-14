import { useEffect, useRef } from "react";
import type { Status } from "./StatusChip";
import { useMotionOK } from "./motion";

/**
 * The orb breathes at the person's OWN median rate (pace), not a generic rhythm: inhale 40 %, exhale 60 %.
 * `rate` is the value shown; `pace` (personal median) drives the motion and falls back to `rate`.
 * No motion without a valid rate, under reduced motion, or while the safety screen is open.
 */
export function BreathingOrb({rate,pace,state}:{rate:number|null|undefined;pace?:number|null;state:Status}) {
  const valid=typeof rate==="number"&&rate>0;
  const tempo=typeof pace==="number"&&pace>0?pace:valid?rate!:null;
  const orb=useRef<HTMLDivElement>(null);
  const motion=useMotionOK();
  useEffect(()=>{
    const el=orb.current;
    if(!motion||!tempo||!el)return;
    const period=Math.max(2,Math.min(10,60/tempo));
    let revert=()=>{},alive=true;
    void import("gsap").then(({gsap})=>{
      if(!alive)return;
      const mm=gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)",()=>{
        gsap.timeline({repeat:-1})
          .fromTo(el,{scale:.92},{scale:1,duration:period*.4,ease:"sine.inOut"})
          .to(el,{scale:.92,duration:period*.6,ease:"sine.inOut"});
      });
      revert=()=>mm.revert();
    });
    return()=>{alive=false;revert();};
  },[motion,tempo]);
  return <div className={`breathing-orb ${valid?state:"none"}`} ref={orb} role="img"
    aria-label={!valid?"No breathing reading":`Breathing rate ${rate} breaths per minute`}>
    {valid?<><strong>{rate}</strong><span>br/min</span></>:<span className="meta-label">Awaiting first night</span>}
  </div>;
}
