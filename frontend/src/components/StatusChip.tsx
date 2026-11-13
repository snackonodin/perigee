export type Status = "normal" | "watch" | "alert" | "none";
const DISPLAY: Record<Status, { label:string; path:string }> = {
  normal:{label:"Normal",path:"m5 12 4 4L19 6"}, watch:{label:"Watch",path:"M12 5a7 7 0 1 0 0 14a7 7 0 1 0 0-14M12 8v5m0 3h.01"}, alert:{label:"Alert",path:"m12 4 9 16H3zM12 10v4m0 3h.01"}, none:{label:"No reading",path:"M12 4a8 8 0 1 0 0 16a8 8 0 1 0 0-16M8 12h8"},
};
export function StatusChip({ state }: { state:Status }) {
  const item=DISPLAY[state];
  return <span className={`status-chip ${state}`}><svg aria-hidden="true" viewBox="0 0 24 24"><path d={item.path}/></svg>{item.label}</span>;
}
