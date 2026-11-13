import { useEffect, useState } from "react";
import { api, errorText } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { Consents } from "../components/Consents";
import { DeleteAccount, ExportData } from "../components/DataControls";

const REDUCE_MOTION_KEY = "settings.reduce-motion";

export function Settings() {
  const { me, reloadMe, logout } = useAuth();
  const [displayName, setDisplayName] = useState(me?.display_name ?? "");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [motionSaved, setMotionSaved] = useState(false);

  useEffect(() => {
    setDisplayName(me?.display_name ?? "");
  }, [me?.display_name]);

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
    const { error, response } = await api.PATCH("/api/v1/me", {
      body: { display_name: displayName.trim() || null },
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
    <div className="settings-grid">
      <section className="card glass settings-section" aria-labelledby="settings-profile-title">
        <h2 id="settings-profile-title">Profile</h2>
        <p className="muted">Signed in as {me?.email ?? ""}</p>
        <form className="settings-form" onSubmit={saveProfile}>
          <label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} autoComplete="name" /></label>
          <div className="settings-actions"><button type="submit" disabled={profileBusy}>{profileBusy ? "Saving…" : "Save profile"}</button><span className="settings-saved" role="status">{profileSaved ? "Saved" : ""}</span></div>
          <p className="error" role="alert">{profileError}</p>
        </form>
      </section>

      <section className="card glass settings-section" aria-labelledby="settings-consents-title">
        <h2 id="settings-consents-title">Consents</h2>
        <Consents />
      </section>

      <section className="card glass settings-section" aria-labelledby="settings-data-title">
        <h2 id="settings-data-title">Data</h2>
        <ExportData />
        <hr />
        <DeleteAccount />
      </section>

      <section className="card glass settings-section" aria-labelledby="settings-accessibility-title">
        <h2 id="settings-accessibility-title">Accessibility</h2>
        <label className="settings-switch-row"><span>Reduce motion</span><input type="checkbox" role="switch" checked={reduceMotion} onChange={(event) => changeReducedMotion(event.target.checked)} /></label>
        <span className="settings-saved" role="status">{motionSaved ? "Saved" : ""}</span>
        <p className="muted">Stop animated effects throughout the app.</p>
      </section>

      <section className="card glass settings-section" aria-labelledby="settings-companion-title">
        <h2 id="settings-companion-title">Companion</h2>
        <button type="button" className="ghost" disabled>Coming soon</button>
      </section>

      <section className="card glass settings-section" aria-labelledby="settings-signout-title">
        <h2 id="settings-signout-title">Sign out</h2>
        <p className="muted">Sign out of this device.</p>
        <button type="button" className="ghost" onClick={() => void logout()}>Sign out</button>
      </section>
    </div>
  );
}

function applyReducedMotion(enabled: boolean) {
  const root = document.documentElement;
  root.dataset.reduceMotion = String(enabled);
  root.dataset.reduceTransparency = String(enabled);
  root.classList.toggle("settings-reduced-motion", enabled);
}
