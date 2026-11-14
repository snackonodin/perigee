// Settings -> Companion: choose cat / fox / bunny (localStorage "pet.species"), plus the
// pet's own controls (hide, mute, quiet hour, breathing buddy).
import { useState } from "react";
import { PetArt, PetControls, type Species } from "../pet";
import { useSafetyActive } from "../safety/SafetyProvider";
import { speciesPref } from "./CompanionHost";

const OPTIONS: { id: Species; name: string }[] = [{ id: "cat", name: "Miso the cat" }, { id: "fox", name: "Ember the fox" }, { id: "bunny", name: "Clover the bunny" }];

export function CompanionSettings() {
  const [species, setSpecies] = useState<Species>(speciesPref);
  const safetyActive = useSafetyActive();
  const choose = (s: Species) => {
    setSpecies(s);
    try { localStorage.setItem("pet.species", s); } catch { /* storage unavailable: choice lasts this session */ }
    window.dispatchEvent(new Event("pet-species"));
  };
  return <>
    <fieldset className="companion-picker">
      <legend className="muted">A small crew companion that keeps you company. It never sees your readings or answers.</legend>
      <div className="companion-options">
        {OPTIONS.map((o) => <label key={o.id} className="companion-option" data-selected={species === o.id || undefined}>
          <input type="radio" name="pet-species" value={o.id} checked={species === o.id} onChange={() => choose(o.id)} />
          <PetArt species={o.id} mood={species === o.id ? "happy" : "neutral"} size={72} />
          <span>{o.name}</span>
        </label>)}
      </div>
    </fieldset>
    <PetControls safetyActive={safetyActive} />
  </>;
}
