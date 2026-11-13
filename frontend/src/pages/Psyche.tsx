import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { CheckinOut, Instrument } from "../api/types";
import { useLoad } from "../api/useLoad";
import { CheckinForm } from "../components/CheckinForm";
import { CheckinCalendar } from "../components/CheckinCalendar";
import { IndexCards } from "../components/IndexCards";
import { LoadState } from "../components/LoadState";
import { QuestionnaireList } from "../components/QuestionnaireList";
import { friendlyName, officialName } from "../components/instrumentNames";
import { Reveal, TitleReveal } from "../components/motion";
import "./Checkin.css";

export function Psyche() {
  const [params,setParams]=useSearchParams();
  const selected=params.get("instrument");
  const list=useLoad(()=>api.GET("/api/v1/instruments"));
  const now=new Date();
  const from=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),1)).toISOString().slice(0,10);
  const to=now.toISOString().slice(0,10);
  const history=useLoad(()=>api.GET("/api/v1/checkins",{params:{query:{from,to}}}),[from,to]);
  const inst=useLoad(()=>selected
    ?api.GET("/api/v1/instruments/{instrument_id}",{params:{path:{instrument_id:selected}}})
    :Promise.resolve({data:undefined}),[selected]);
  const close=()=>{setParams({});history.reload();};
  if(selected)return <div className="screen-page checkin-focused">
    <header className="page-heading app-page-heading"><button type="button" className="ghost checkin-back" onClick={close}><span aria-hidden="true">←</span> All check-ins</button><div><p className="eyebrow">Your private reflection</p><h1>{friendlyName(selected,(inst.data as Instrument|undefined)?.name)}</h1><p>Take this one card at a time.</p>{officialName(selected,(inst.data as Instrument|undefined)?.name)&&<p className="instrument-official">{officialName(selected,(inst.data as Instrument|undefined)?.name)}</p>}</div></header>
    <section className="checkin-question-panel glass"><LoadState state={inst} label="the check-in">{definition=><CheckinForm key={selected} instrument={definition as unknown as Instrument} onDone={close}/>}</LoadState></section>
  </div>;
  return <div className="checkin-page"><header className="page-heading"><div><p className="eyebrow">A moment for you · private check-in</p><TitleReveal text="Check-in"/><p>One card at a time. Answer what feels right for today.</p></div></header>
    <Reveal className="checkin-bento">
      <div className="checkin-bento-cal"><LoadState state={history} label="your check-in calendar">{items=><CheckinCalendar checkins={items as CheckinOut[]}/>}</LoadState></div>
      <div className="checkin-stack"><section className="card glass daily-checkin-card" aria-labelledby="daily-title"><p className="eyebrow">Small daily reflection</p><h2 id="daily-title">A quick check-in</h2>
        <LoadState state={list} label="daily check-ins">{items=><QuestionnaireList items={items} dailyOnly completedIds={(history.data??[]).filter(c=>c.date===to).map(c=>c.instrument_id)} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
      <section className="card glass checkin-index-history" aria-labelledby="weekly-title"><p className="eyebrow">Your own history</p><h2 id="weekly-title">Weekly patterns</h2><p className="muted checkin-weekly-lead">Questionnaire summaries over time, never a comparison with others.</p><IndexCards instruments={list.data??[]}/></section></div>
      <section className="card glass wide other-checkins-card" aria-labelledby="other-title"><p className="eyebrow">When you are ready · optional</p><h2 id="other-title">More reflections</h2>
        <LoadState state={list} label="questionnaires">{items=><QuestionnaireList items={items} completedIds={(history.data??[]).filter(c=>c.date===to).map(c=>c.instrument_id)} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
    </Reveal></div>;
}
