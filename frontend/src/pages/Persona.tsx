import { api } from "../api/client";
import { useLoad } from "../api/useLoad";
import { LoadState } from "../components/LoadState";
import type { TodayOut } from "../api/types";

type PersonaToday = TodayOut & { context_engine?: { dashboard_visualization_data?: {
  radar_traits?: Record<string, number>;
  radar_traits_baseline?: Record<string, number>;
  persona_matrix?: { stability_score?: number; agency_score?: number; quadrant_name?: string };
} } | null };
const TRAITS = [
  { key: "O", name: "Openness", descriptor: "Curious" },
  { key: "C", name: "Conscientiousness", descriptor: "Steady" },
  { key: "E", name: "Extraversion", descriptor: "Expressive" },
  { key: "A", name: "Agreeableness", descriptor: "Considerate" },
  { key: "N", name: "Neuroticism", descriptor: "Sensitive" },
];
const clamp = (n: number) => Math.max(4, Math.min(20, n));
function point(i: number, value: number, max: number, cx = 120, cy = 112, radius = 78) {
  const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2;
  const r = (clamp(value) - 4) / 16 * radius * (max === 20 ? 1 : 1);
  return `${cx + Math.cos(angle) * r},${cy + Math.sin(angle) * r}`;
}
function Radar({ values, baseline }: { values: number[]; baseline?: number[] }) {
  const polygon = values.map((v, i) => point(i, v, 20)).join(" ");
  const base = baseline?.map((v, i) => point(i, v, 20)).join(" ");
  return <figure className="persona-radar"><svg viewBox="0 0 240 224" role="img" aria-labelledby="radar-title radar-desc">
    <title id="radar-title">Your personality profile</title><desc id="radar-desc">Five trait dials show your current profile on a four to twenty scale.</desc>
    {[.33,.66,1].map((scale) => <polygon key={scale} className="radar-grid" points={TRAITS.map((_,i)=>{
      const angle=Math.PI*2*i/5-Math.PI/2; return `${120+Math.cos(angle)*78*scale},${112+Math.sin(angle)*78*scale}`;
    }).join(" ")} />)}
    {TRAITS.map((trait,i)=>{const angle=Math.PI*2*i/5-Math.PI/2;return <line key={trait.key} className="radar-axis" x1="120" y1="112" x2={120+Math.cos(angle)*78} y2={112+Math.sin(angle)*78}/>;})}
    {base && <polygon className="radar-baseline" points={base} />}
    <polygon className="radar-shape" points={polygon} />
    {values.map((v,i)=>{const [x,y]=point(i,v,20).split(",");return <circle key={i} className="radar-dot" cx={x} cy={y} r="3.5"/>;})}
  </svg><figcaption>Your profile is shown on a personal 4–20 scale. {baseline ? "The outline marks your own prior profile." : "Trait history is not included in this snapshot."}</figcaption></figure>;
}
function Dial({ name, descriptor, value, index }: {name:string;descriptor:string;value:number;index:number}) {
  const r=31, c=2*Math.PI*r, fill=(clamp(value)-4)/16;
  return <div className="trait-dial"><svg viewBox="0 0 76 76" role="img" aria-label={`${name}: ${value} of 20`}>
    <circle className="dial-track" cx="38" cy="38" r={r}/><circle className="dial-fill" cx="38" cy="38" r={r} strokeDasharray={c} strokeDashoffset={c*(1-fill)} style={{transform:`rotate(${index*18-90}deg)`}}/>
    <text x="38" y="43" textAnchor="middle">{value}</text></svg><strong>{name}</strong><span>{descriptor}</span></div>;
}
export function Persona() {
  const load=useLoad(()=>api.GET("/api/v1/today"));
  return <LoadState state={load} label="your persona profile">{(raw)=>{
    const today=raw as PersonaToday, data=today.context_engine?.dashboard_visualization_data;
    const traits=data?.radar_traits ?? {}, valid=TRAITS.map(t=>traits[t.key]).filter((v):v is number=>typeof v==="number"&&Number.isFinite(v));
    const vals=TRAITS.map(t=>typeof traits[t.key]==="number"?traits[t.key]:12);
    const complete=valid.length===5, baseline=data?.radar_traits_baseline;
    const baselineValues=baseline && TRAITS.every(t=>typeof baseline[t.key]==="number") ? TRAITS.map(t=>baseline[t.key]) : undefined;
    const matrix=data?.persona_matrix;
    return <><header className="page-heading"><div><p className="eyebrow">Personal profile · private to you</p><h1>Persona</h1><p>Patterns in how you describe yourself, without ranking or labels.</p></div></header>
      <div className="grid"><section className="card persona-arc"><div><p className="eyebrow">Five traits</p><h2>Your arc</h2><p className="muted">Each dial uses the 4–20 scale from your profile.</p></div>
        <div className="dial-row">{TRAITS.map((t,i)=><Dial key={t.key} name={t.name} descriptor={t.descriptor} value={vals[i]} index={i}/>)}</div>
        {!complete&&<p className="muted">Your full profile is not available in this snapshot.</p>}</section>
        <section className="card persona-radar-card"><p className="eyebrow">Your pattern</p><h2>You now, in your own context</h2>{complete?<Radar values={vals} baseline={baselineValues}/>:<p className="muted">A complete profile will appear when all five trait values are available.</p>}
          {matrix&&<div className="persona-quadrant"><span>Profile quadrant</span><strong>{matrix.quadrant_name ?? "Building your picture"}</strong><p>Stability {matrix.stability_score ?? "—"} · Agency {matrix.agency_score ?? "—"}</p></div>}
          <details><summary>Profile details</summary><p>Trait values describe your own responses. They are not a health score.</p></details></section></div></>;
  }}</LoadState>;
}
