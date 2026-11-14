import { useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { CompanionSettings } from "../components/CompanionSettings";
import { Consents } from "../components/Consents";
import { DeleteAccount, ExportData } from "../components/DataControls";
import { Reveal, TitleReveal } from "../components/motion";

const REDUCE_MOTION_KEY = "settings.reduce-motion";

export function Settings() {
  const { me, reloadMe } = useAuth();
  const [displayName, setDisplayName] = useState(me?.display_name ?? "");
  const [stationTime, setStationTime] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [motionSaved, setMotionSaved] = useState(false);

  useEffect(() => {
    setDisplayName(me?.display_name ?? "");
  }, [me?.display_name]);

  useEffect(() => {
    setStationTime("");
  }, [me?.station_time_offset_min]);

  useEffect(() => {
    let enabled = false;
    try {
      enabled = window.localStorage.getItem(REDUCE_MOTION_KEY) === "true";
    } catch {
      // The switch still works for this page view when storage is unavailable.
    }
    setReduceMotion(enabled);
    applyReducedMotion(enabled);
  }, []);

  async function saveProfile(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileBusy(true);
    setProfileError(null);
    setProfileSaved(false);
    const stationOffset = stationTime ? stationTimeOffset(stationTime) : null;
    const { error, response } = await api.PATCH("/api/v1/me", {
      body: { display_name: displayName.trim() || null, station_time_offset_min: stationOffset },
    });
    setProfileBusy(false);
    if (error) {
      setProfileError(errorText(error, response.status));
      return;
    }
    await reloadMe();
    setProfileSaved(true);
  }

  function changeReducedMotion(enabled: boolean) {
    setReduceMotion(enabled);
    applyReducedMotion(enabled);
    setMotionSaved(true);
    try {
      window.localStorage.setItem(REDUCE_MOTION_KEY, String(enabled));
    } catch {
      // Preference applies to the current page even when storage is unavailable.
    }
  }

  return (
    <div className="settings-page">
    <header className="page-heading"><div><TitleReveal text="Settings"/><p>Profile, what is stored, and how the app moves.</p></div></header>
    <Reveal className="settings-grid">
      <div className="settings-col">
      <section className="card glass settings-section" aria-labelledby="settings-profile-title">
        <h2 id="settings-profile-title">Profile</h2>
        <p className="muted">Signed in as {me?.email ?? ""}</p>
        <form className="settings-form" onSubmit={saveProfile}>
          <label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" /></label>
          <label>Station time (optional)<input type="time" value={stationTime} onChange={(event) => setStationTime(event.target.value)} /></label>
          <p className="settings-station" role="status"><span className="tag-chip">Saved · Station time = {formatStationOffset(me?.station_time_offset_min ?? 0)}</span></p>
          <p className="muted">The time on your station clock now. Leave blank to use UTC, the atomic-time standard the ISS uses.</p>
          <div className="settings-actions"><button type="submit" disabled={profileBusy}>{profileBusy ? "Saving…" : "Save profile"}</button><span className="settings-saved" role="status">{profileSaved ? "Saved" : ""}</span></div>
          <p className="error" role="alert">{profileError}</p>
        </form>
      </section>
      <section className="card glass settings-section" aria-labelledby="settings-data-title">
        <h2 id="settings-data-title">Data</h2>
        <ExportData />
        <hr />
        <DeleteAccount />
      </section>
      <section className="card glass settings-section" aria-labelledby="settings-companion-title">
        <h2 id="settings-companion-title">Companion</h2>
        <CompanionSettings />
      </section>
      </div>
      <div className="settings-col">
      <section className="card glass settings-section" aria-labelledby="settings-consents-title">
        <h2 id="settings-consents-title">Consents</h2>
        <Consents />
      </section>
      <section className="card glass settings-section" aria-labelledby="settings-accessibility-title">
        <h2 id="settings-accessibility-title">Accessibility</h2>
        <label className="settings-switch-row consent-switch-row"><span className="settings-consent-copy"><span className="consent-label">Reduce motion</span><span className="muted">Stop animated effects and see-through surfaces throughout the app.</span><span className="settings-saved" role="status">{motionSaved ? "Saved" : ""}</span></span><input type="checkbox" role="switch" aria-label="Reduce motion" checked={reduceMotion} onChange={(event) => changeReducedMotion(event.target.checked)} /></label>
      </section>
      </div>





    </Reveal>
    </div>
  );
}

function stationTimeOffset(value: string): number {
  const [hours, minutes] = value.split(":").map(Number);
  const now = new Date();
  let offset = hours * 60 + minutes - (now.getUTCHours() * 60 + now.getUTCMinutes());
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

function applyReducedMotion(enabled: boolean) {
  const root = document.documentElement;
  root.dataset.reduceMotion = String(enabled);
  root.dataset.reduceTransparency = String(enabled);
  root.classList.toggle("settings-reduced-motion", enabled);
}
