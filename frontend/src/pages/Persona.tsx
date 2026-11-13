import { useState } from "react";
import "./Persona.css";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { TodayOut } from "../api/types";

type PersonaToday = TodayOut & { context_engine?: { dashboard_visualization_data?: {
  radar_traits?: Record<string, number>; radar_traits_baseline?: Record<string, number>;
  persona_matrix?: { stability_score?: number; agency_score?: number; quadrant_name?: string };
} } | null };
const TRAITS = [
  { key: "O", name: "Openness", descriptor: "Curious", color: "#a78bfa", note: "Ideas, novelty and possibility" },
  { key: "C", name: "Conscientiousness", descriptor: "Steady", color: "#5eead4", note: "Structure, follow-through and care" },
  { key: "E", name: "Extraversion", descriptor: "Expressive", color: "#f5b544", note: "Energy from engagement and activity" },
  { key: "A", name: "Agreeableness", descriptor: "Considerate", color: "#7dd3fc", note: "Cooperation, trust and compassion" },
  { key: "N", name: "Neuroticism", descriptor: "Sensitive", color: "#fda4af", note: "Sensitivity to stress and uncertainty" },
];
const clamp = (n: number) => Math.max(4, Math.min(20, n));
function point(i: number, value: number, cx = 120, cy = 112, radius = 78) {
  const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2;
  const r = (clamp(value) - 4) / 16 * radius;
  return `${cx + Math.cos(angle) * r},${cy + Math.sin(angle) * r}`;
}
function Radar({ values, baseline }: { values: number[]; baseline?: number[] }) {
  const polygon = values.map((v, i) => point(i, v)).join(" ");
  const base = baseline?.map((v, i) => point(i, v)).join(" ");
  return <figure className="persona-radar"><svg viewBox="0 0 240 224" role="img" aria-labelledby="radar-title radar-desc">
    <defs><linearGradient id="personaFill" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#5eead4" stopOpacity=".58"/><stop offset="1" stopColor="#a78bfa" stopOpacity=".44"/></linearGradient><filter id="personaGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
    <title id="radar-title">Your personality profile</title><desc id="radar-desc">Five trait values on your personal four to twenty scale.</desc>
    {[.33,.66,1].map(scale => <polygon key={scale} className="radar-grid" points={TRAITS.map((_,i)=>{const a=Math.PI*2*i/5-Math.PI/2;return `${120+Math.cos(a)*78*scale},${112+Math.sin(a)*78*scale}`;}).join(" ")} />)}
    {TRAITS.map((trait,i)=>{const a=Math.PI*2*i/5-Math.PI/2;return <line key={trait.key} className="radar-axis" x1="120" y1="112" x2={120+Math.cos(a)*78} y2={112+Math.sin(a)*78}/>;})}
    {base&&<polygon className="radar-baseline" points={base}/>}
    <polygon className="radar-shape" points={polygon} style={{fill:"url(#personaFill)"}} filter="url(#personaGlow)" />
    {values.map((v,i)=>{const [x,y]=point(i,v).split(",");return <circle key={TRAITS[i].key} className="radar-dot" cx={x} cy={y} r="4" style={{fill:TRAITS[i].color}}/>;})}
  </svg><figcaption>Your profile uses your own 4–20 scale. {baseline ? "The violet outline is your prior profile." : "No prior trait profile is available for comparison."}</figcaption></figure>;
}
function Dial({ name, descriptor, value, color, selected, onClick }: {name:string;descriptor:string;value?:number;color:string;selected:boolean;onClick:()=>void}) {
  const r=30, c=2*Math.PI*r, fill=value==null?0:(clamp(value)-4)/16;
  return <button type="button" className={`trait-dial ${selected?"selected":""}`} aria-pressed={selected} onClick={onClick} style={{"--dial-color":color} as React.CSSProperties}>
    <svg viewBox="0 0 76 76" aria-hidden="true"><circle className="dial-track" cx="38" cy="38" r={r}/><circle className="dial-fill" cx="38" cy="38" r={r} strokeDasharray={c} strokeDashoffset={c*(1-fill)} style={{transform:"rotate(-90deg)"}}/><text x="38" y="43" textAnchor="middle">{value??"—"}</text></svg><strong>{name}</strong><span className={value==null?"trait-missing":undefined}>{value==null?"Not supplied":descriptor}</span>
  </button>;
}
export function Persona() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  const [selected,setSelected]=useState("O");
  return <LoadState state={load} label="your persona profile">{raw=>{
    const today=raw as PersonaToday, data=today.context_engine?.dashboard_visualization_data;
    const traits=data?.radar_traits??{};
    const vals=TRAITS.map(t=>typeof traits[t.key]==="number"&&Number.isFinite(traits[t.key])?traits[t.key]:undefined);
    const complete=vals.every((v):v is number=>v!==undefined);
    const baseline=data?.radar_traits_baseline;
    const baselineValues=baseline&&TRAITS.every(t=>typeof baseline[t.key]==="number"&&Number.isFinite(baseline[t.key]))?TRAITS.map(t=>baseline[t.key]):undefined;
    const active=TRAITS.find(t=>t.key===selected)??TRAITS[0], value=vals[TRAITS.indexOf(active)];
    const matrix=data?.persona_matrix;
    return <div className="persona-page"><header className="persona-head"><div><p className="eyebrow">Personal profile · private to you</p><h1>Persona</h1><p>Your traits, in your own words and context.</p></div><span className="persona-scale">4–20 scale</span></header>
      {today.sync_status?.state==="api_mock"&&<p className="api-mock-note" role="status">API unavailable · empty preview; no trait values are shown.</p>}
      <div className="persona-layout"><section className="persona-arc-panel"><div className="persona-section-title"><div><p className="eyebrow">Five traits</p><h2>Your character arc</h2></div></div>
        <div className="dial-row">{TRAITS.map((t,i)=><Dial key={t.key} name={t.name} descriptor={t.descriptor} value={vals[i]} color={t.color} selected={t.key===selected} onClick={()=>setSelected(t.key)}/>)}</div>
        <div className="trait-popover" key={active.key} style={{"--dial-color":active.color} as React.CSSProperties}><span className="popover-glyph" aria-hidden="true">{active.key}</span><div><p className="eyebrow">{active.descriptor} · {active.name}</p><strong>{value??"Not supplied"}{value!=null&&<small> / 20</small>}</strong><p>{value==null?"This response is not part of the available profile.":active.note}</p></div><div className="trait-meter" aria-label={value==null?"No value supplied":`${active.name}: ${value} of 20`}><i style={{width:value==null?"0%":`${((clamp(value)-4)/16)*100}%`}}/></div></div>
        <p className="persona-footnote">Trait values reflect your own responses. They are not a health score or a ranking.</p>
      </section><section className="persona-radar-panel"><div className="persona-section-title"><div><p className="eyebrow">You now · your 28-night context</p><h2>Personal pattern</h2></div></div>
        {complete?<Radar values={vals as number[]} baseline={baselineValues}/>:<div className="radar-empty"><svg viewBox="0 0 120 120" aria-hidden="true"><polygon points="60,12 106,45 88,100 32,100 14,45"/><polygon points="60,36 83,52 74,80 46,80 37,52"/></svg><p>A complete profile will appear when all five trait values are available.</p><small>Missing traits stay blank; no estimate is filled in.</small></div>}
        {matrix&&<div className="persona-quadrant"><span>Profile quadrant</span><strong>{matrix.quadrant_name??"Building your picture"}</strong><p>Stability {matrix.stability_score??"—"} · Agency {matrix.agency_score??"—"}</p></div>}
      </section></div>
    </div>;
  }}</LoadState>;
}
