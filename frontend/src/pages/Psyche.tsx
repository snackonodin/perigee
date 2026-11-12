import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { CheckinOut, Instrument } from "../api/types";
import { useLoad } from "../api/useLoad";
import { CheckinForm } from "../components/CheckinForm";
import { CheckinCalendar } from "../components/CheckinCalendar";
import { IndexCards } from "../components/IndexCards";
import { LoadState } from "../components/LoadState";
import { QuestionnaireList } from "../components/QuestionnaireList";

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
  if(selected)return <div className="screen-page focused-checkin">
    <header className="page-heading app-page-heading"><button type="button" className="ghost back-checkin" onClick={close}><span aria-hidden="true">←</span> All check-ins</button><div><p className="eyebrow">Your private reflection</p><h1>{(inst.data as Instrument|undefined)?.name??selected}</h1><p>Take this one card at a time.</p></div></header>
    <section className="focused-question-panel"><LoadState state={inst} label="the check-in">{definition=><CheckinForm key={selected} instrument={definition as unknown as Instrument} onDone={close}/>}</LoadState></section>
  </div>;
  return <><header className="page-heading"><div><p className="eyebrow">A moment for you · private check-in</p><h1>Check-in</h1><p>One card at a time. Answer what feels right for today.</p></div></header>
    <div className="grid checkin-grid">
      <LoadState state={history} label="your check-in calendar">{items=><CheckinCalendar checkins={items as CheckinOut[]}/>}</LoadState>
      <section className="card daily-checkin-card" aria-labelledby="daily-title"><p className="eyebrow">Small daily reflection</p><h2 id="daily-title">A quick check-in</h2>
        <LoadState state={list} label="daily check-ins">{items=><QuestionnaireList items={items} dailyOnly onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
      <section className="card wide other-checkins-card" aria-labelledby="other-title"><div className="row"><div><p className="eyebrow">When you are ready</p><h2 id="other-title">More reflections</h2></div><span className="pill">Optional</span></div>
        <LoadState state={list} label="questionnaires">{items=><QuestionnaireList items={items} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
      <details className="card wide index-history"><summary>Weekly patterns</summary><p className="muted">Questionnaire summaries over time. These are your own history, not a comparison with others.</p><IndexCards instruments={list.data??[]}/></details>
    </div></>;
}
