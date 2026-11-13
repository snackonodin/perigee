# ACCEPTANCE.md: self-grade before returning

Mark each line PASS / FAIL / N/A in `STATUS.md` with one line of evidence (command
output, file:line, or what you saw). Items marked **(auto)** are checked by a command.

## A. Build and budget
- [ ] A1 (auto) `npm run check:final` exits 0 (tsc, dialog lint with --require, vitest, build, budget, render).
- [ ] A2 (auto) `check_budget`: src/pet/ < 80 KB gzipped; no raster, font, URL or network call.
- [ ] A3 Only `react` and files inside `src/pet/` are imported by `src/pet/` code.
- [ ] A4 `src/pet/types.ts` exports every name in `contract.d.ts`, unchanged.

## B. Art (phase 01-02)
- [ ] B1 (auto) `npm run render` writes 9 SVGs; no stroke < 4 units; ≤ 120 elements each.
- [ ] B2 Three silhouettes are distinct as a solid shape at 64px (cat: pointed ears + curled tail; fox: tall dark-tipped ears + brush tail; bunny: long ears 0.9× head height).
- [ ] B3 Head = 55-60% of total height (write the measured numbers).
- [ ] B4 Eyes: below head midline, centers ≈ 46% of head width apart, 2 highlights each.
- [ ] B5 Tiny nose, "w" mouth, blush, 3-tone shading, rim light, contact shadow; no black outlines.
- [ ] B6 All colors come from `var(--token, #fallback)` using names in TOKENS.css.
- [ ] B7 All 8 rig variables registered with `@property` and visibly move the right part.

## C. Behavior (phase 03)
- [ ] C1 Blink interval 3-6 s; breathing 4 s (6 s asleep); ear/tail twitches per BRIEF §2.
- [ ] C2 Tap → happy 1200 ms; long press ≥ 600 ms → petting; 3 taps in 1500 ms → playful. Never sad.
- [ ] C3 Keyboard: Enter = tap; Space held = petting.
- [ ] C4 Walks only ≥ 768 px wide, along `[data-pet-perch]` top edges at 60 px/s; sits on the edge; avoids `[data-pet-avoid]`, focused fields and forms.
- [ ] C5 Bedtime window: yawn → curl → dim → z every 2.5 s; stretch on wake.
- [ ] C6 Mood uses only engagement + timeOfDay (grep: no other inputs).
- [ ] C7 Accessories at nightsLogged 3/7/14/30, kept forever; a lower streakDays changes nothing.
- [ ] C8 Reduced motion (prop or media query): static pose, no loops, no walking.

## D. Frost trail (phase 04)
- [ ] D1 Canvas overlay, pointer-events none, backing store 0.5× × min(DPR, 2).
- [ ] D2 Seeded texture tile, tint alpha ≤ 0.55.
- [ ] D3 Ring buffer cap 300; point added every ≥ 6 px; brush radius r0·(1 − age/T), r0 = 28.
- [ ] D4 rAF stops when the buffer is empty or the tab is hidden (unit test on the loop controller).
- [ ] D5 Reduced motion → CSS opacity fade only, no canvas.
- [ ] D6 Frost is below text or on decorative surfaces only.

## E. Dialog (phase 05)
- [ ] E1 (auto) `lint_dialog --require` passes: 13 events × 3 tones, ≥ 6 lines (≥ 10 for quiz_complete, bedtime_near, sleep_start, wake), ≤ 90 chars, unique ids, no banned terms.
- [ ] E2 Picker: tod filter, last-8 avoidance, weighted random, per-event cooldown (unit tests).
- [ ] E3 No line while an input/textarea/select/contenteditable has focus (unit test).
- [ ] E4 Mute and snooze persist in localStorage; every access in try/catch (test with a throwing storage).

## F. Safety and access (phase 06, see SAFETY.md)
- [ ] F1 (auto) `safety.test.tsx`: safetyActive ⇒ empty DOM, 0 timers, 0 rAF, emit() silent; also when flipped mid-life.
- [ ] F2 quiz_complete lines mention only completion/effort.
- [ ] F3 Art `aria-hidden`; tap target is a labelled `<button>`; bubble `role="status"` `aria-live="polite"`.
- [ ] F4 Hide-pet and mute controls: visible, Tab-reachable, ≥ 44×44 px, persisted.
- [ ] F5 Legacy `CompanionFace`, `CHARACTERS`, `LEGACY_CHARACTER_TO_SPECIES` exported and render statically.

## G. Performance (if you have a browser)
- [ ] G1 DevTools Performance, 4× CPU throttle, 10 s idle + walking: p95 frame time < 16.7 ms.
- [ ] G2 Only transform/opacity animate (Rendering → Paint flashing shows no repaint loops outside the canvas).
