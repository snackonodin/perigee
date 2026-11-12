import type { TabDef } from "./tabs";

// Scaffold page: each tab gets its real screen in a later FE task.
export function Placeholder({ tab }: { tab: TabDef }) {
  return (
    <section className="panel" aria-labelledby="page-title">
      {tab.experimental && (
        <p className="experimental" role="note">
          Experimental: heart rate from Wi-Fi is not validated. Do not rely on it.
        </p>
      )}
      <h1 id="page-title">{tab.label}</h1>
      <p className="muted">
        {tab.live ? "Live view" : "View"} coming in a later frontend task.
      </p>
    </section>
  );
}
