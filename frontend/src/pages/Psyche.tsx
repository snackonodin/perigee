import { useSearchParams } from "react-router";
import { api } from "../api/client";
import type { Instrument } from "../api/types";
import { useLoad } from "../api/useLoad";
import { CheckinForm } from "../components/CheckinForm";
import { LoadState } from "../components/LoadState";
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
      <section className="card wide" aria-labelledby="q-title">
        <h2 id="q-title">Questionnaires</h2>
        <LoadState state={list} label="questionnaires">
          {(items) => <QuestionnaireList items={items} onStart={(id) => setParams({ instrument: id })} />}
        </LoadState>
      </section>
      {selected && (
        <section className="card wide" aria-labelledby="form-title">
          <h2 id="form-title">{(inst.data as Instrument | undefined)?.name ?? selected}</h2>
          <LoadState state={inst} label="the questionnaire">
            {(def) => <CheckinForm key={selected} instrument={def as unknown as Instrument} onDone={close} />}
          </LoadState>
          <button type="button" className="link" onClick={close}>Close</button>
        </section>
      )}
    </div>
  );
}
