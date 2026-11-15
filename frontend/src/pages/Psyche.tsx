import { BODY_CABIN, bodyCabinLayout } from "../components/bodyCabinLayout";
import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { CheckinOut, Instrument } from "../api/types";
import { useLoad } from "../api/useLoad";
import { CheckinForm } from "../components/CheckinForm";
import { CheckinCalendar } from "../components/CheckinCalendar";
import { LoadState } from "../components/LoadState";
import { QuestionnaireList } from "../components/QuestionnaireList";
import { friendlyName, officialName } from "../components/instrumentNames";
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
    <header className="page-heading app-page-heading"><button type="button" className="ghost checkin-back" onClick={close}><span aria-hidden="true">←</span> All check-ins</button><div><h1>{friendlyName(selected,(inst.data as Instrument|undefined)?.name)}</h1><p>Take this one card at a time.</p>{officialName(selected,(inst.data as Instrument|undefined)?.name)&&<p className="instrument-official">{officialName(selected,(inst.data as Instrument|undefined)?.name)}</p>}</div></header>
    <section className="checkin-question-panel" data-pet-avoid><LoadState state={inst} label="the check-in">{definition=><CheckinForm key={selected} instrument={definition as unknown as Instrument} onDone={close} {...(selected===BODY_CABIN?bodyCabinLayout:{})}/>}</LoadState></section>
  </div>;
  return <div className="checkin-page"><header className="page-heading"><div><h1>Check-in</h1><p>One card at a time. Answer what feels right for today.</p></div></header>
    <div className="checkin-bento">
      <div className="checkin-bento-cal"><LoadState state={history} label="your check-in calendar">{items=><CheckinCalendar checkins={items as CheckinOut[]}/>}</LoadState></div>
      <div className="checkin-stack"><section className="card daily-checkin-card" aria-labelledby="daily-title"><h2 id="daily-title">A quick check-in</h2>
        <LoadState state={list} label="daily check-ins">{items=><QuestionnaireList items={items} dailyOnly completedIds={(history.data??[]).filter(c=>c.date===to).map(c=>c.instrument_id)} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
      <section className="card checkin-index-history" data-pet-perch aria-labelledby="weekly-title"><h2 id="weekly-title">Weekly patterns</h2><p className="muted checkin-weekly-lead">Your check-ins are part of tonight's reading. They are compared only with your own past answers, never with anyone else.</p></section></div>
      <section className="card wide other-checkins-card" data-pet-perch aria-labelledby="other-title"><h2 id="other-title">More reflections</h2>
        <LoadState state={list} label="questionnaires">{items=><QuestionnaireList items={items} completedIds={(history.data??[]).filter(c=>c.date===to).map(c=>c.instrument_id)} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
    </div></div>;
}
