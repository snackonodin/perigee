# Pet: self-grade against pet-handoff/ACCEPTANCE.md (2026-11-14, claude-fe)

Built inside the app (`frontend/src/pet/`), not the playground, so the playground's
`npm run check:final` is replaced by the app's own checks: `npx tsc --noEmit`,
`npx vitest run`, `npm run build`, and `node ../pet-handoff/playground/scripts/lint_dialog.mjs --require src/pet/dialog/cache.json`.

Commits: 2d89f47 prerequisites · d84f558 phase 01 · 75098f8 phase 02 · 147f15c phase 03 ·
4703dc7 phase 04 · e990161 phase 05 · 0a8a8ba phase 06 · 5db30b7 app wiring.

## A. Build and budget
- A1 PASS: tsc clean; vitest 25 files / 175 tests; vite build OK; dialog lint OK.
- A2 PASS: src/pet (no tests) = 30.8 KB gzipped (< 80 KB); no raster, font, URL or fetch (grep empty).
- A3 PASS: non-test files import only `react`, `react-dom` (createPortal for the frost canvas) and files in src/pet.
- A4 PASS: types.ts is contract.d.ts verbatim; `declare` lines are comments pointing at emit.ts / CompanionFace.tsx.

## B. Art
- B1 PASS: art.test.tsx — 3 species x 3 moods, <= 120 elements, every stroke >= 4, no black, every var() has a fallback.
- B2 PASS: preview render at 64 px: cat pointed ears + curl tail; fox dark-tipped ears + brush tail; bunny long ears + pom tail.
- B3 PASS: cat 128/215 = 59.5%; fox 124/219 = 57%; bunny head 136 of ~236 incl. ears = 58%.
- B4 PASS: Face() places eyes 57% down the head, centres 46% of head width apart, eye width 14%, two shines.
- B5 PASS: 5% nose, 11% "w" mouth (stroke 4.5), radial blush .55, 3 tones, rim light .55, contact shadow, no outlines.
- B6 PASS: every colour is `var(--token, #fallback)` from TOKENS.css (test enforces fallbacks).
- B7 PASS (static) / NOT VERIFIED (live): all 8 variables registered with @property in rig.css and wired to parts; seen in static mood renders, not frame-checked live.

## C. Behavior
- C1 PASS by config + code: blink 3-6 s (15% double), breathing 4 s / 6 s asleep, ear twitch 5-12 s, cat sway 3.2 s, fox flick 8-15 s, bunny wiggle 10-20 s.
- C2 PASS: behavior.test.ts (tap -> happy 1200 ms, long press -> petting max 5 s, 3 taps in 1.5 s -> playful, no sad state over 2000 random events).
- C3 PASS by code (useInteractions: Enter = tap, Space held 600 ms = petting); no keyboard test without user-event.
- C4 PARTIAL: walk.ts helpers (>= 768 px, perch top edges, avoid boxes, 60 px/s) and data-pet-perch / data-pet-avoid wired; the walk itself was not observed in a browser (screenshots are static).
- C5 PARTIAL: yawn -> sleeping -> z every 2.5 s, tap wakes, re-sleep after 30 s, stretch on leaving: unit-tested in behavior.ts; not observed live. Bedtime = timeOfDay "night" (22:00-05:00 station time) because the contract gives the pet no clock; the host fires bedtime_near at 21:30.
- C6 PASS: moodOf(state, timeOfDay) only; CompanionHost reads only quadrant_name from the engine output.
- C7 PASS: accessories.test.ts (3/7/14/30, kept after a lower count, throwing storage OK).
- C8 PASS: reduced prop or media query -> data-reduced, all animation/transition none, no loops, no walking, no frost canvas.

## D. Frost trail
- D1 PASS: fixed canvas, pointer-events none, backing 0.5 x min(DPR, 2) (trail.test: 500x300, 1000x600, 1000x600).
- D2 PASS: mulberry32 seed 7, tint alpha min(.55, FROST_TINT_ALPHA).
- D3 PASS: trail.test (cap 300 overwrite, >= 6 px, prune at age >= T, r0 (1 - age/T), r0 28, T 30).
- D4 PASS: loop.test (no frame while empty, stops after last prune, paused while hidden, resumes on visible).
- D5 PASS: not mounted under reduced motion.
- D6 PASS: canvas is portalled under the page content (z-index -1 after the backdrop), clipped to perch tiles; cards and text paint above it.

## E. Dialog
- E1 PASS: lint --require OK, 282 lines, 282 unique ids, 6-10 per event/tone.
- E2 PASS: picker.test (tod, last 8, weighting ratio 1.6-2.4 for 2:1, cooldown).
- E3 PASS: picker.test focus guard.
- E4 PASS: picker.test / a11y.test (mute + snooze persisted; throwing storage still works).

## F. Safety and access
- F1 PASS: safety.test.tsx (empty DOM, 0 timers, 0 rAF, emit silent, controls absent; also flipped mid-life; no line for 60 s after).
- F2 PASS: quiz_complete lines thank for completion/effort only; host emits it only when safety_screen_required === false and no local trigger (asserted in src/safety/safety.test.tsx).
- F3 PASS: a11y.test (art aria-hidden, "Pet {name}" button, bubble role=status aria-live=polite, not focusable).
- F4 PASS: a11y.test (Hide, Mute, Quiet hour, Breathe: buttons, focusable, >= 44 px, persisted); also in Settings -> Companion and a 44 px options button by the pet.
- F5 PASS: legacy.test (3 characters x 7 moods, no timers, concerned = calm).

## G. Performance
- G1 NOT MEASURED: no DevTools profiling run in this session.
- G2 NOT MEASURED: by construction only transform/opacity/rig variables animate; paint flashing not checked.

## Assumptions
- GSAP not used: CSS keyframes + the scheduler were enough, and they keep the safety test simple.
- Look-follow uses a CSS transition on --look-x/y instead of a per-frame lerp, so rAF stays limited to frost and walking.
- "goodbye" is in the cache but not fired: there is no visible moment for it (hiding the pet removes it at once).
