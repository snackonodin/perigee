import type { CheckinOut } from "../api/types";

const DAY_LABELS=["M","T","W","T","F","S","S"];
function dateKey(year:number,month:number,day:number) {
  return new Date(Date.UTC(year,month,day)).toISOString().slice(0,10);
}
function dayKind(checkins:CheckinOut[]) {
  const daily=checkins.some(c=>c.instrument_id.startsWith("daily_")||c.slot==="am"||c.slot==="pm");
  const questionnaire=checkins.some(c=>!c.instrument_id.startsWith("daily_")&&c.slot!=="am"&&c.slot!=="pm");
  return daily&&questionnaire?"both":daily?"daily":questionnaire?"questionnaire":"";
}
export function CheckinCalendar({ checkins, now = new Date() }: { checkins:CheckinOut[]; now?:Date }) {
  const year=now.getUTCFullYear(),month=now.getUTCMonth();
  const first=new Date(Date.UTC(year,month,1));
  const offset=(first.getUTCDay()+6)%7;
  const daysInMonth=new Date(Date.UTC(year,month+1,0)).getUTCDate();
  const cells=Array.from({length:42},(_,i)=>i-offset+1);
  const weeks=Array.from({length:6},(_,week)=>cells.slice(week*7,week*7+7));
  const byDate=new Map<string,CheckinOut[]>();
  checkins.forEach(c=>byDate.set(c.date,[...(byDate.get(c.date)??[]),c]));
  const monthName=new Intl.DateTimeFormat("en",{month:"long",timeZone:"UTC"}).format(first);
  return <section className="card checkin-calendar" aria-labelledby="checkin-calendar-title">
    <div className="row"><div><p className="eyebrow">Your month</p><h2 id="checkin-calendar-title">Check-in calendar</h2></div><span className="pill">{monthName} {year}</span></div>
    <p className="muted">Dots mark check-ins you chose to record. They do not grade or infer your mood.</p>
    <div className="calendar-grid" role="grid" aria-label={`${monthName} ${year} check-in calendar`}>
      <div className="calendar-weekdays" role="row">{DAY_LABELS.map((label,i)=><span className="calendar-weekday" role="columnheader" key={`${label}${i}`}>{label}</span>)}</div>
      <div className="calendar-weeks" role="rowgroup">{weeks.map((week,wi)=><div className="calendar-week" role="row" key={wi}>{week.map((day,di)=>{
        const i=wi*7+di;
        const inMonth=day>=1&&day<=daysInMonth;
        const key=inMonth?dateKey(year,month,day):"";
        const entries=key?(byDate.get(key)??[]):[];
        const kind=dayKind(entries);
        const isToday=inMonth&&key===dateKey(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate());
        const dateLabel=inMonth?`${monthName} ${day}, ${year}`:"Outside this month";
        const entryLabel=entries.length?`${entries.length} check-in${entries.length===1?"":"s"}`:"no check-in recorded";
        return <div key={i} className={`${inMonth?"calendar-day":"calendar-day outside"}${isToday?" today":""}`} role="gridcell" aria-label={inMonth?`${dateLabel}, ${entryLabel}`:undefined}>
          {inMonth&&<><span>{day}</span>{kind&&<span className={`calendar-dot ${kind}`} aria-hidden="true"/>}</>}
        </div>;
      })}</div>)}</div>
    </div>
    <ul className="calendar-legend" aria-label="Calendar legend"><li><i className="calendar-dot daily"/>Daily check-in · dot</li><li><i className="calendar-dot questionnaire"/>Questionnaire · ring</li><li><i className="calendar-dot both"/>Both · square</li></ul>
  </section>;
}
