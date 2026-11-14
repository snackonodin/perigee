// Hide pet, mute pet messages, quiet for 1 hour, and the optional breathing buddy.
// Each control is a real button, Tab-reachable, at least 44x44 px. Nothing under safety.
import type { CSSProperties } from "react";
import { petStore, usePetPrefs } from "./store";

const MIN: CSSProperties = { minWidth: 44, minHeight: 44 };

export function PetControls({ safetyActive = false, onHiddenChange, breathe = true }: { safetyActive?: boolean; onHiddenChange?: (hidden: boolean) => void; breathe?: boolean }) {
  const { hidden, muted, snoozedUntil } = usePetPrefs();
  if (safetyActive) return null;
  const snoozed = snoozedUntil > Date.now();
  const toggleHidden = () => { petStore.setHidden(!hidden); onHiddenChange?.(!hidden); };
  return <div className="pet-controls" role="group" aria-label="Companion controls">
    <button type="button" className="pet-control" style={MIN} onClick={toggleHidden}>{hidden ? "Show pet" : "Hide pet"}</button>
    <button type="button" className="pet-control" style={MIN} aria-pressed={muted} onClick={() => petStore.setMuted(!muted)}>{muted ? "Unmute pet messages" : "Mute pet messages"}</button>
    <button type="button" className="pet-control" style={MIN} aria-pressed={snoozed} onClick={() => (snoozed ? petStore.unsnooze() : petStore.snooze())}>{snoozed ? "End quiet hour" : "Quiet for 1 hour"}</button>
    {breathe && !hidden && <button type="button" className="pet-control" style={MIN} aria-describedby="pet-breathe-note" onClick={() => petStore.startBuddy()}>Breathe with me</button>}
    {breathe && !hidden && <small id="pet-breathe-note" className="pet-control-note">Relaxation exercise. Not a medical tool.</small>}
  </div>;
}
