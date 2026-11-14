import { useState } from "react";
import "./Persona.css";
import { Reveal, TitleReveal } from "../components/motion";
import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { Instrument } from "../api/types";
import { CheckinForm } from "../components/CheckinForm";

const QUIZ_ID = "mini_ipip";
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
    <defs><linearGradient id="personaFill" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#5eead4" stopOpacity=".58"/><stop offset="1" stopColor="#a78bfa" stopOpacity=".44"/></linearGradient></defs>
    <title id="radar-title">Your personality profile</title><desc id="radar-desc">Five trait values on your personal four to twenty scale.</desc>
    {[.33,.66,1].map(scale => <polygon key={scale} className="radar-grid" points={TRAITS.map((_,i)=>{const a=Math.PI*2*i/5-Math.PI/2;return `${120+Math.cos(a)*78*scale},${112+Math.sin(a)*78*scale}`;}).join(" ")} />)}
    {TRAITS.map((trait,i)=>{const a=Math.PI*2*i/5-Math.PI/2;return <line key={trait.key} className="radar-axis" x1="120" y1="112" x2={120+Math.cos(a)*78} y2={112+Math.sin(a)*78}/>;})}
    {base&&<polygon className="radar-baseline" points={base}/>}
    <polygon className="radar-shape" points={polygon} style={{fill:"url(#personaFill)"}} />
    {values.map((v,i)=>{const [x,y]=point(i,v).split(",");return <circle key={TRAITS[i].key} className="radar-dot" cx={x} cy={y} r="4" style={{fill:TRAITS[i].color}}/>;})}
  </svg><figcaption>Your profile uses your own 4–20 scale.{baseline ? " The violet outline is your prior profile." : ""}</figcaption></figure>;
}
function Dial({ name, descriptor, value, color, selected, onClick, showMissing }: {name:string;descriptor:string;value?:number;color:string;selected:boolean;onClick:()=>void;showMissing:boolean}) {
  const r=30, c=2*Math.PI*r, fill=value==null?0:(clamp(value)-4)/16;
  return <button type="button" className={`trait-dial ${selected?"selected":""}`} aria-pressed={selected} onClick={onClick} style={{"--dial-color":color} as React.CSSProperties}>
    <svg viewBox="0 0 76 76" aria-hidden="true"><circle className="dial-track" cx="38" cy="38" r={r}/><circle className="dial-fill" cx="38" cy="38" r={r} strokeDasharray={c} strokeDashoffset={c*(1-fill)} style={{transform:"rotate(-90deg)"}}/>{value!=null&&<circle className="dial-sat" r="4" cx={38+r*Math.cos(2*Math.PI*fill-Math.PI/2)} cy={38+r*Math.sin(2*Math.PI*fill-Math.PI/2)}/>}<text x="38" y="43" textAnchor="middle">{value??"–"}</text></svg><strong>{name}</strong>{value!=null?<span>{descriptor}</span>:showMissing&&<span className="trait-missing">Not supplied</span>}
  </button>;
}
/** The personality questions, loaded on demand and sent like any survey. Not a check-in. */
function PersonaQuiz({ onFinished, onCancel }: { onFinished(): void; onCancel(): void }) {
  const quiz = useLoad(() => api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: QUIZ_ID } } }));
  return <section className="persona-quiz" aria-labelledby="persona-quiz-title">
    <div className="persona-section-title"><h2 id="persona-quiz-title">Personality questions</h2>
      <p className="muted">20 short statements, about 2 minutes. There are no right or wrong answers.</p></div>
    <LoadState state={quiz} label="the personality questions">{instrument =>
      <CheckinForm instrument={instrument as unknown as Instrument} submitLabel="See my traits" onSubmitted={onFinished}/>}</LoadState>
    <button type="button" className="link persona-quiz-cancel" onClick={onCancel}>Cancel</button>
  </section>;
}

export function Persona() {
  const load=useLoad(()=>api.GET("/api/v1/persona"));
  const [selected,setSelected]=useState("O");
  const [quizOpen,setQuizOpen]=useState(false);
  const head=<header className="persona-head"><div><TitleReveal text="Persona"/><p>Your traits, in your own words. Private to you.</p></div><span className="persona-scale">4–20 scale</span></header>;
  if (quizOpen) return <div className="persona-page">{head}<PersonaQuiz onCancel={()=>setQuizOpen(false)} onFinished={()=>{ setQuizOpen(false); load.reload(); }}/></div>;
  return <LoadState state={load} label="your persona profile">{persona=>{
    const traits=persona.available?persona.traits:{};
    const vals=TRAITS.map(t=>typeof traits[t.key]==="number"&&Number.isFinite(traits[t.key])?traits[t.key]:undefined);
    const complete=vals.every((v):v is number=>v!==undefined);
    const none=vals.every(v=>v===undefined);
    const active=TRAITS.find(t=>t.key===selected)??TRAITS[0], value=vals[TRAITS.indexOf(active)];
    const matrix=persona.available?persona.persona_matrix:null;
    const take=<button type="button" className="persona-take" onClick={()=>setQuizOpen(true)}>Take the personality questions (2 min)</button>;
    return <div className="persona-page">{head}
      <Reveal className="persona-layout"><section className="persona-arc-panel"><div className="persona-section-title"><h2>Five traits</h2></div>
        {none&&<div className="persona-none"><p>Your traits appear after the personality questions.</p>{take}</div>}
        <div className="dial-row">{TRAITS.map((t,i)=><Dial key={t.key} name={t.name} descriptor={t.descriptor} value={vals[i]} color={t.color} selected={t.key===selected} onClick={()=>setSelected(t.key)} showMissing={!none}/>)}</div>
        {!none&&<div className="trait-popover" key={active.key} style={{"--dial-color":active.color} as React.CSSProperties}><span className="popover-glyph" aria-hidden="true">{active.key}</span><div><p className="trait-popover-name">{active.descriptor} · {active.name}</p>{value!=null&&<strong>{value}<small> / 20</small></strong>}<p>{value==null?`No ${active.name.toLowerCase()} value is in your profile yet.`:active.note}</p></div>{value!=null&&<div className="trait-meter" aria-label={`${active.name}: ${value} of 20`}><i style={{width:`${((clamp(value)-4)/16)*100}%`}}/></div>}</div>}
        <p className="persona-footnote">Trait values reflect your own answers. They are not a health score or a ranking, and no trait is better than another.</p>
        {!none&&<button type="button" className="link persona-retake" onClick={()=>setQuizOpen(true)}>Retake the personality questions</button>}
      </section><section className="persona-radar-panel"><div className="persona-section-title"><h2>Personal pattern</h2></div>
        {complete?<Radar values={vals as number[]}/>:<div className="radar-empty"><svg viewBox="0 0 120 120" aria-hidden="true"><polygon points="60,12 106,45 88,100 32,100 14,45"/><polygon points="60,36 83,52 74,80 46,80 37,52"/></svg><p>Your pattern appears when all five traits are available.</p></div>}
        {matrix&&<div className="persona-quadrant"><span>Profile quadrant</span><strong>{matrix.quadrant_name}</strong><p>Stability {matrix.stability_score} · Agency {matrix.agency_score}</p></div>}
      </section></Reveal>
    </div>;
  }}</LoadState>;
}
