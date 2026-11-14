import { CHARACTERS, CompanionFace, PetArt, type Mood, type PetMood, type Species } from "../pet";
import "./CompanionGallery.css";

const MOODS: Mood[] = ["neutral", "happy", "calm", "encouraging", "concerned", "tired", "sleeping"];
const PET_MOODS: PetMood[] = ["neutral", "happy", "calm", "playful", "sleepy", "sleeping", "petting"];
const SPECIES: Species[] = ["cat", "fox", "bunny"];

/** Dev-only preview: the new species in every mood, plus the legacy CompanionFace mapping. */
export function CompanionGallery() {
  return <main className="pet-gallery">
    <h1>Companion expressions</h1>
    <p>Static species and expression preview (dev only).</p>
    <div className="pet-gallery-grid">
      {SPECIES.map((s) => PET_MOODS.map((m) => <article className="pet-gallery-cell" key={`${s}-${m}`}>
        <PetArt species={s} mood={m} size={120} /><span>{s} · {m}</span></article>))}
    </div>
    <h2>Legacy names</h2>
    <div className="pet-gallery-grid">
      {MOODS.map((mood) => CHARACTERS.map((c) => <article className="pet-gallery-cell" key={`${c.id}-${mood}`}>
        <CompanionFace character={c.id} mood={mood} /><span>{c.name} · {mood}</span></article>))}
    </div>
  </main>;
}
