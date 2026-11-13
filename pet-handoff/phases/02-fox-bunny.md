# Phase 02: fox and bunny

**Goal:** two more species on the **same rig and the same `data-part` names** as the cat,
with silhouettes clearly different from the cat at 64px.

**Read first:** BRIEF.md §1, TOKENS.css (fox and bunny palettes), your `species/Cat.tsx`.

## Files

| File | Content |
|---|---|
| `species/Fox.tsx` | `<Fox mood />` |
| `species/Bunny.tsx` | `<Bunny mood />` |
| `species/shared.tsx` | Add fox/bunny gradients and clips (prefixed ids) |
| `PetArt.tsx` | Route `fox` and `bunny` to their components |

## Silhouette rules (what makes them readable at 64px)

| | Fox | Bunny |
|---|---|---|
| Ears | Tall pointed, 0.55× head height, outer 30% in `--pet-fox-tip` (a fill, not an outline) | Two long upright rounded ears, **0.9× head height**, inner `--pet-bunny-inner` |
| Face | Cream muzzle patch (`--pet-fox-cream`) from below the eyes to the chin, cheeks flare outward to points (radius ≥ 6) | Round face, slightly taller than wide, small buck-tooth hint is **not** allowed (keep the "w" mouth) |
| Body | Cream chest bib | Round body, fur `--pet-bunny-fur`, shade `--pet-bunny-shade` |
| Tail | Big brush, 0.8× body height, cream tip 25% | Pom tail, circle r ≈ 18, visible from the side |
| Paws | `--pet-fox-tip` socks | Small ovals |

Same face rules for both: head 55–60% of height, eyes below midline, 2 shines, tiny nose,
"w" mouth, blush, 3-tone shading, rim light, contact shadow, no black outlines.

Ear pivots: put each ear's `transform-origin` at its base center so `--ear-l/r` rotate
naturally. Bunny ears at `--ear-l: -1` should fold outward by 14°, not clip into the head.

## Checks

```bash
npm run check
npm run render     # 9 files; no THIN strokes; <= 120 elements each
```
Silhouette test (no browser needed): in each `out/*-neutral.svg` the ears' highest point
differs: fox ear tips ≈ y 20–30, cat ≈ y 28–40, bunny ≈ y 0–12. Write the three numbers.

## Stop

Stop after this phase. Print: per-species element count, ear-tip y values, head height %.
