# Phase 04: the frost trail

**Goal:** a frost layer on the pet's stage that clears where the pet walks and re-forms
from the trail edges inward over T seconds.

**Read first:** BRIEF.md §3 (exact algorithm), TOKENS.css (frost tokens), SAFETY.md S1.

## Safety (repeat)
- `safetyActive` ⇒ the canvas is **unmounted**, the buffer is cleared, rAF is cancelled.
- Reduced motion ⇒ no canvas at all; CSS opacity fade (600 ms) only.
- Frost never sits on top of text. Tint alpha **≤ 0.55** (AA contrast depends on it).

## Files (in `src/pet/frost/`)

| File | Content |
|---|---|
| `prng.ts` | `mulberry32(seed) → () => number` (seed 7 for the texture). |
| `texture.ts` | `makeFrostTile(size = 256, seed = 7): HTMLCanvasElement` (or `OffscreenCanvas` when available): fill `#EAF4FB` at α 0.55, ~3% noise pixels (white, α 0–0.08), 40 crystal strokes (white, α 0.25, 1–3 branches, length 6–18 px, lineWidth 1). Created once and cached per page. |
| `trailBuffer.ts` | Pure ring buffer: `createTrail(cap = 300)`, `add(x, y, now, minStep = 6)`, `prune(now, T)`, `points()`, `size()`, `clear()`. When full, overwrite the oldest. |
| `loop.ts` | `createFrostLoop({ draw, isHidden, raf, caf })`: starts rAF only when `size() > 0` and `!isHidden()`, stops when the buffer empties or the tab is hidden; listens to `visibilitychange`. Injectable `raf/caf` for tests. |
| `FrostTrail.tsx` | `<FrostTrail active={!safetyActive && !reducedMotion} stageRef T={30} r0={28} />`: canvas `position:absolute; inset:0; pointer-events:none`, backing store = CSS size × 0.5 × `Math.min(devicePixelRatio, 2)` (ResizeObserver). Each frame: `drawImage`/pattern the tile over the canvas, then `globalCompositeOperation = "destination-out"` and a radial-gradient brush per point, radius `r0·(1 − age/T)` (scaled by the backing ratio), alpha `1 − age/T`; reset to `source-over`. |
| `frost.css` | `.frost-fallback` for reduced motion: a static frost-tinted layer that fades to 0 and back over 600 ms when the pet passes. |
| `__tests__/trail.test.ts` | cap 300 overwrite; min step 6 px; prune drops `age ≥ T`; radius formula at age 0, T/2, T. |
| `__tests__/loop.test.ts` | rAF not requested while empty; requested after `add`; cancelled after the last prune; not requested while hidden; resumes on visible. |

Wire it in `Pet.tsx`: when `placement="stage"` and walking, add the pet's foot position
to the trail each frame of the walk. `T` and `r0` come from `petConfig.ts`
(`FROST_REFORM_S = 30`, allowed 20–40; `FROST_BRUSH_R0 = 28`).

## Checks

```bash
npm run check && npm test
```
With a browser, in DevTools → Performance (4× CPU slowdown): while the trail is empty,
no rAF callbacks fire; while it is closing, frames stay under 16.7 ms.

## Stop

Stop after this phase. Print: test counts, the canvas backing size at DPR 1, 2 and 3 for
a 1000×600 stage (expected 500×300, 1000×600, 1000×600), and the texture's tint alpha.
