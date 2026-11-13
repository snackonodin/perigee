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
  if(selected)return <div className="screen-page checkin-focused">
    <header className="page-heading app-page-heading"><button type="button" className="ghost checkin-back" onClick={close}><span aria-hidden="true">←</span> All check-ins</button><div><p className="eyebrow">Your private reflection</p><h1>{(inst.data as Instrument|undefined)?.name??selected}</h1><p>Take this one card at a time.</p></div></header>
    <section className="checkin-question-panel"><LoadState state={inst} label="the check-in">{definition=><CheckinForm key={selected} instrument={definition as unknown as Instrument} onDone={close}/>}</LoadState></section>
  </div>;
  return <div className="checkin-page"><header className="page-heading"><span className="checkin-mark" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 4h14v16H5zM8 8h8M8 12h8M8 16h5"/></svg></span><div><p className="eyebrow">A moment for you · private check-in</p><h1>Check-in</h1><p>One card at a time. Answer what feels right for today.</p></div><span className="pill">Your log</span></header>
    <div className="grid checkin-grid">
      <LoadState state={history} label="your check-in calendar">{items=><CheckinCalendar checkins={items as CheckinOut[]}/>}</LoadState>
      <section className="card daily-checkin-card" aria-labelledby="daily-title"><p className="eyebrow">Small daily reflection</p><h2 id="daily-title">A quick check-in</h2>
        <LoadState state={list} label="daily check-ins">{items=><QuestionnaireList items={items} dailyOnly completedIds={(history.data??[]).filter(c=>c.date===to).map(c=>c.instrument_id)} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
      <section className="card wide other-checkins-card" aria-labelledby="other-title"><div className="row"><div><p className="eyebrow">When you are ready</p><h2 id="other-title">More reflections</h2></div><span className="pill">Optional</span></div>
        <LoadState state={list} label="questionnaires">{items=><QuestionnaireList items={items} completedIds={(history.data??[]).filter(c=>c.date===to).map(c=>c.instrument_id)} onStart={id=>setParams({instrument:id})}/>}</LoadState>
      </section>
      <details className="card wide checkin-index-history"><summary>Weekly patterns</summary><p className="muted">Questionnaire summaries over time. These are your own history, not a comparison with others.</p><IndexCards instruments={list.data??[]}/></details>
    </div></div>;
}
