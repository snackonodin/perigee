import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { api, errorText } from "../api/client";
import type { Instrument, InstrumentSummary } from "../api/types";
import { useAuth } from "../auth/AuthProvider";
import { CheckinForm } from "../components/CheckinForm";
import { NOT_CHECKINS } from "../components/QuestionnaireList";
import { Consents } from "../components/Consents";

export function Setup() {
  const { me, reloadMe } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [displayName, setDisplayName] = useState(me?.display_name ?? "");
  const [stationTime, setStationTime] = useState("");
  const [savedStationOffset, setSavedStationOffset] = useState<number | null>(me?.station_time_offset_min ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCheckin, setShowCheckin] = useState(false);
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [checkinBusy, setCheckinBusy] = useState(false);
  const [checkinError, setCheckinError] = useState<string | null>(null);

  useEffect(() => {
    setSavedStationOffset(me?.station_time_offset_min ?? null);
  }, [me?.station_time_offset_min]);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const stationOffset = stationTime ? stationTimeOffset(stationTime) : null;
    const { error: apiError, response } = await api.PATCH("/api/v1/me", {
      body: { display_name: displayName.trim() || null, station_time_offset_min: stationOffset },
    });
    setBusy(false);
    if (apiError) {
      setError(errorText(apiError, response.status));
      return;
    }
    setSavedStationOffset(stationOffset);
    await reloadMe();
    setStep(3);
  }

  async function loadFirstCheckin() {
    setShowCheckin(true);
    setCheckinBusy(true);
    setCheckinError(null);
    try {
      const { data, error: listError, response } = await api.GET("/api/v1/instruments");
      if (!data?.length) {
        setCheckinError(listError ? errorText(listError, response.status) : "No check-ins are available right now.");
        setCheckinBusy(false);
        return;
      }
      const checkins = data.filter((item: InstrumentSummary) => !NOT_CHECKINS.has(item.id));
      const choice = checkins.find((item: InstrumentSummary) => /week/i.test(item.timeframe ?? "")) ?? checkins[0];
      if (!choice) {
        setCheckinError("No check-ins are available right now.");
        setCheckinBusy(false);
        return;
      }
      const detail = await api.GET("/api/v1/instruments/{instrument_id}", { params: { path: { instrument_id: choice.id } } });
      if (!detail.data) setCheckinError(errorText(detail.error, detail.response.status));
      else setInstrument(detail.data as unknown as Instrument);
    } catch {
      setCheckinError("Cannot reach the server. Please try again.");
    }
    setCheckinBusy(false);
  }

  function finish() {
    try { window.localStorage.setItem("setup.done", "true"); } catch { /* setup can still finish in this session */ }
    navigate("/", { replace: true });
  }

  return (
    <main className="setup-layout">
      <div className="aurora-backdrop" aria-hidden="true"><i /><i /><i /><i /></div>
      <section className="card setup-card" aria-labelledby="setup-title">
        <h1 id="setup-title">Set up your account</h1>
        <p className="setup-progress" role="status">Step {step} of 3</p>
        {step === 1 && <div className="setup-step"><h2>Choose what to store</h2><p className="muted">You can change these preferences any time in Settings.</p><Consents /><button type="button" onClick={() => setStep(2)}>Continue</button></div>}
        {step === 2 && <form className="setup-step setup-form" onSubmit={saveProfile}><h2>Your profile</h2><label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" /></label><label>Station time (optional)<input type="time" value={stationTime} onChange={(event) => setStationTime(event.target.value)} /></label><p className="muted">The time on your station clock now. Leave blank to use UTC, the atomic-time standard the ISS uses.</p>{savedStationOffset !== null && <p className="muted" role="status">Station time = {formatStationOffset(savedStationOffset)}</p>}{savedStationOffset === null && me?.station_time_offset_min === null && <p className="muted" role="status">Station time = UTC</p>}<p className="error" role="alert">{error}</p><div className="setup-actions"><button type="button" className="ghost" onClick={() => setStep(1)}>Back</button><button type="submit" disabled={busy}>{busy ? "Saving…" : "Save and continue"}</button></div><p className="muted">Having trouble saving? You can continue and add your profile details later.</p><button type="button" className="ghost" disabled={busy} onClick={() => setStep(3)}>Continue without saving</button></form>}
        {step === 3 && <div className="setup-step"><h2>Building your baseline</h2><p>Sleep near the sensor for 28 nights to build your baseline.</p><p className="muted">You can also complete your first weekly check-in now, or start later.</p>{!showCheckin && <button type="button" className="ghost" onClick={() => void loadFirstCheckin()}>Start an optional weekly check-in</button>}{checkinBusy && <p className="muted" role="status">Loading check-in…</p>}{checkinError && <p className="error" role="alert">{checkinError}</p>}{instrument && <CheckinForm instrument={instrument} onDone={() => setInstrument(null)} />}<div className="setup-actions"><button type="button" className="ghost" onClick={finish}>Finish later</button><button type="button" onClick={finish}>Finish</button></div></div>}
      </section>
    </main>
  );
}

function stationTimeOffset(value: string): number {
  const [hours, minutes] = value.split(":").map(Number);
  const now = new Date();
  const stationMinutes = hours * 60 + minutes;
  const utcMinutes = now.getUTCHours() * 60 + now.getUTCMinutes();
  let offset = stationMinutes - utcMinutes;
  while (offset < -720) offset += 1440;
  while (offset > 840) offset -= 1440;
  return Math.round(offset / 15) * 15;
}

function formatStationOffset(offset: number): string {
  if (offset === 0) return "UTC";
  const sign = offset > 0 ? "+" : "-";
  const absolute = Math.abs(offset);
  return `UTC${sign}${String(Math.floor(absolute / 60)).padStart(2, "0")}:${String(absolute % 60).padStart(2, "0")}`;
}
