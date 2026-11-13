# Phase 01: the cat (static art + rig)

**Goal:** a static, cute cat in pure SVG with the 8 rig variables wired to its parts.
No timers, no behavior yet.

**Read first:** BRIEF.md §1 (Art), TOKENS.css (pet palette), TOOLS.md §A,
`reference/cat-head-skeleton.svg`, `contract.d.ts`.

## Files to create or replace (all in `playground/src/pet/`)

| File | Content |
|---|---|
| `types.ts` | Replace the stub with every declaration from `contract.d.ts` as real exports. `declare function emit` / `declare const` lines become comments for now (implemented in phase 06). |
| `species/shared.tsx` | `<PetDefs species />`: gradients, clipPaths and the static `feTurbulence` fur filter (opacity ≤ 0.12). Ids prefixed per species (`cat-`, `fox-`, `bunny-`). |
| `species/Cat.tsx` | `<Cat mood />`: one `<svg viewBox="0 0 256 256" aria-hidden="true">` with groups `data-part` = `shadow, tail, body, paws, head, ear-l, ear-r, eyes, eye-l, eye-r, mouth, mouth-open, blush, rim, accessories`. |
| `rig.css` | `@property` for `--look-x --look-y --blink --breathe --ear-l --ear-r --tail --mouth --squash` (`<number>`, `inherits: true`, initial 0) and the transforms in BRIEF §1. `transform-box: fill-box` + explicit `transform-origin` per part. |
| `pet.css` | Root `.pet` sizing (`width/height: var(--pet-size, 96px)`), imports nothing. |
| `PetArt.tsx` | `export function PetArt({ species, mood, size = 256 }: { species: Species; mood: PetMood; size?: number })`: picks the species component and sets `data-mood`. Only `cat` for now; fox/bunny render the cat until phase 02. |
| `index.ts` | Add `export { PetArt } from "./PetArt";` (keep the existing lines). |

## Exact art targets (viewBox units, sitting pose, total height ≈ 220)

- Head: ellipse ≈ rx 88, ry 76, center (128, 104) → head height 152 of total ≈ 220 = **58%**.
- Body: rounded pear under the head, top hidden behind the head, y ≈ 150–222, width ≈ 120.
- Tail: a curl from the body's right side, 14–18 units thick, ending near (214, 170).
- Paws: two ovals at the bottom front, rx 18 ry 11.
- Face: scale the skeleton's face (eyes, shines, nose, mouth, blush) into the head; eyes
  stay **below** the head midline and **46%** of head width apart.
- Moods for this phase: `neutral` (as skeleton), `happy` (eyes become upward arcs, stroke
  6, `--mouth` 0.6), `sleeping` (eyes = downward arcs, stroke 5, ears −0.3).
  Use `[data-mood="happy"] [data-part="eye-l"] ...` selectors; same element ids in every mood.
- Rim light: 8-unit arc on the head's top-right, `--pet-rim`, opacity .6, `mix-blend-mode: screen`.
- Colors: `var(--pet-cat-fur, #FFF4D6)`, `--pet-cat-shade`, `--pet-cat-deep`, `--pet-cat-inner`, shared `--pet-*`.

## Checks (all must pass)

```bash
npm run check     # exit 0
npm run render    # 9 files in out/, no "THIN strokes", each <= 120 elements
```
Then open `out/cat-neutral.svg` as text and confirm: no `stroke="#000"`, no `stroke-width`
below 4, every `fill` is a `url(#...)` or uses a var with a fallback (via CSS class or style).
If you have a browser: `npm run dev`, view at 64px and 512px (temporarily set `size`).

## Stop

Stop after this phase. Print: files created, element count per render, the measured head
height %, and any assumptions. Do not start phase 02.
