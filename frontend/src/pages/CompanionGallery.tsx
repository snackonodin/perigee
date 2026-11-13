import "../companion/companion.css";
import { CHARACTERS } from "../companion/characters";
import { CompanionFace, type Mood } from "../companion/CompanionFace";

const MOODS: Mood[] = ["neutral", "happy", "calm", "encouraging", "concerned", "tired", "sleeping"];

export function CompanionGallery() {
  return <main className="pet-gallery">
    <h1>Companion expressions</h1>
    <p>Static character and expression preview.</p>
    <div className="pet-gallery-grid">
      {MOODS.map((mood) => CHARACTERS.map((character) => <article className="pet-gallery-cell" key={`${character.id}-${mood}`}>
        <CompanionFace character={character.id} mood={mood} />
        <span>{character.name} · {mood}</span>
      </article>))}
    </div>
  </main>;
}
