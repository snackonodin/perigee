import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { Instrument } from "../api/types";
import { useLoad } from "../api/useLoad";
import { CheckinForm } from "../components/CheckinForm";
import { QuestionnaireList } from "../components/QuestionnaireList";

export function Psyche() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("instrument");
  const list = useLoad(() => api.GET("/api/v1/instruments"));
  const inst = useLoad(
    () =>
      selected
        ? api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: selected } } })
        : Promise.resolve({ data: undefined }),
    [selected],
  );
  const close = () => setParams({});

  return (
    <div className="grid">
      <section className="card" aria-labelledby="q-title">
        <h2 id="q-title">Questionnaires</h2>
        {list.data ? (
          <QuestionnaireList items={list.data} onStart={(id) => setParams({ instrument: id })} />
        ) : (
          <p className={list.error ? "error" : "muted"}>{list.error ?? "Loading…"}</p>
        )}
      </section>
      {selected && (
        <section className="card wide" aria-labelledby="form-title">
          <h2 id="form-title">{(inst.data as Instrument | undefined)?.name ?? selected}</h2>
          {inst.data ? (
            <CheckinForm key={selected} instrument={inst.data as unknown as Instrument} onDone={close} />
          ) : (
            <p className={inst.error ? "error" : "muted"}>{inst.error ?? "Loading…"}</p>
          )}
          <button type="button" className="link" onClick={close}>Close</button>
        </section>
      )}
    </div>
  );
}
