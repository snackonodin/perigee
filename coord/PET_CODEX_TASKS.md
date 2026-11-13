# PET_CODEX_TASKS.md: Codex prompts for the companion pet

Run the tasks in order A → B → C, one Codex run each, after FRONTEND_TASKS Task 1 has
landed (it adds the tokens and the empty `#companion-slot`).

---

## Task A: Static faces + 7 expressions + gallery page

```text
You are Codex, implementing a spec. You make no design decisions.
Read only coord/PET_SPEC.md and coord/DESIGN.md plus these files. Do not open other files.

Files you may create:
- frontend/src/companion/companion.css
- frontend/src/companion/characters.tsx
- frontend/src/companion/CompanionFace.tsx
- frontend/src/pages/CompanionGallery.tsx
Files you may edit:
- frontend/src/App.tsx (only to add the dev-only route below)
Read-only: frontend/src/theme/tokens.css.
Never touch backend/, engine/, waiwai1/, tests/, frontend/src/safety/ or any other file.
No images, no new npm packages, no external fonts. Pure CSS + inline SVG, colors only via
var(--token) from tokens.css.

Build:
1. characters.tsx exports CHARACTERS = [
     {id:"nimbus", name:"Nimbus", personality:"A soft-spoken little cloud who is never in a hurry."},
     {id:"pip",    name:"Pip",    personality:"A cheerful sprout-egg who loves small wins."},
     {id:"lumi",   name:"Lumi",   personality:"A thoughtful moon-bun who listens more than talks."}]
   and <CharacterBody id/> as inline SVG in a 72×72 box. Outline: 2px var(--text) at 85% opacity.
   - nimbus: 64×48 var(--mint) rounded rect r24 + three 28px mint circle bumps on top
     (x 8, 22, 34; top −12) merged into ONE path so the outline is continuous; two 10×6 mint
     oval feet 14px apart. Face centered, eyes 18px apart, 20px from top.
   - pip: 56×66 var(--peach) egg (border-radius 50% 50% 46% 46% / 58% 58% 42% 42% as an
     SVG path); a 2×10 var(--teal) stem on top center plus two 10×6 var(--mint) leaves at
     ±30°. Eyes 16px apart, 26px from top. Cheeks var(--alert-soft).
   - lumi: 62×58 var(--lavender) blob (radius 50% 50% 44% 44%); two 14×18 lavender rounded
     triangle ears at ±16px, tips at −10px; a 10px var(--butter) 5-point star above the
     left ear. Eyes 18px apart, 24px from top.
   - Shared: an arm nub 10×14 in the body color on the right side (transform-origin at its
     base), two .pet-eye, one .pet-mouth, two .pet-cheek (9×6 ovals, var(--peach), or
     var(--alert-soft) for pip, 4px below and outside each eye), two .pet-brow.
2. CompanionFace.tsx: <CompanionFace character mood /> renders
   <div class="pet" data-character={id} data-mood={mood} aria-hidden="true">.
3. companion.css: copy exactly the variable block and the .pet-eye/.pet-mouth/.pet-cheek/
   .pet-brow rules from PET_SPEC.md section 2, then one [data-mood="…"] rule per mood that
   sets only the variables listed in the section 2 table (neutral = defaults; happy, calm,
   encouraging, concerned, tired, sleeping). Add transition: 150ms on width, height,
   border-radius, opacity and translate, removed under prefers-reduced-motion.
   .pet-eye::after is a 2px white dot at the top-right, opacity var(--eye-shine).
4. CompanionGallery.tsx: a 3-column (characters) × 7-row (moods) grid, every cell
   labelled "Nimbus · happy", etc., on var(--bg) with var(--surface) cells, radius 16.
   Route /dev/companion in App.tsx, registered only when import.meta.env.DEV is true.

If the spec is ambiguous, pick the simplest option and append to bus/issues_for_claude.md
(file, what was unclear, what you chose).
Verify: cd frontend && npm test && npm run build (both pass; the gallery is not in the prod bundle).
Final step: run `bash bus/post_update.sh` if it exists; if not, append
"post_update.sh missing" to bus/issues_for_claude.md. Stop.

Browser checklist (npm run dev → http://localhost:5173/dev/companion):
[ ] 21 cells: 3 characters × 7 moods, each labelled
[ ] Nimbus is a mint cloud, Pip a peach egg with a sprout, Lumi a lavender bun with ears and a butter star
[ ] happy = ^ ^ eyes + open smile + cheeks; calm = u u eyes; sleeping = closed curves
[ ] concerned shows worried brows and a flat (not frowning) mouth
[ ] tired = half-lidded eyes + small "o" mouth; encouraging = eyes with a white shine
[ ] Pip's cheeks are visible (not peach on peach)
[ ] No image requests in the Network tab; no emoji; no colors outside the tokens
[ ] npm run build output does not include the gallery route
```

---

## Task B: Idle animations, mouse following, perching, touch

```text
You are Codex, implementing a spec. You make no design decisions.
Read only coord/PET_SPEC.md and coord/DESIGN.md plus these files. Do not open other files.

Files you may create:
- frontend/src/companion/movement.ts
- frontend/src/companion/movement.test.ts
- frontend/src/companion/Companion.tsx
Files you may edit:
- frontend/src/companion/companion.css (append animation rules only)
- frontend/src/components/AppShell.tsx (only to render <Companion/> into #companion-slot)
- frontend/src/pages/CompanionGallery.tsx (add a "motion preview" row)
Read-only: frontend/src/companion/CompanionFace.tsx, frontend/src/companion/characters.tsx,
frontend/src/theme/tokens.css.
Never touch backend/, engine/, waiwai1/, tests/, frontend/src/safety/ or any other file.
No new npm packages; use requestAnimationFrame plus CSS. (gsap is allowed only if Task 1
already installed it; otherwise plain rAF.)

Animations (companion.css, exact):
- @keyframes pet-bob: translate 0 0 → 0 -3px → 0 0; 2.4s ease-in-out infinite; while idle only.
- @keyframes pet-blink: eyes scale 1 1 → 1 .1 → 1 1; 160ms ease-in-out, once. JS adds
  .is-blinking after a random 3000–6000ms delay, removes it on animationend and reschedules.
  Skip blinking for happy, calm and sleeping.
- @keyframes pet-breathe: body scale 1 → 1.03 → 1, infinite, ease-in-out, duration from the
  CSS var --breath-period (default 4s; Task C sets it). Sleeping doubles the period.
- @keyframes pet-hop: 0% scale(1.06,.94); 40% translateY(-14px) scale(.96,1.04);
  70% translateY(0) scale(1.04,.96); 100% none. 520ms cubic-bezier(.3,.7,.4,1), once.
- @keyframes pet-wave: arm rotate 0 → -20deg → 14deg → -20deg → 0; 900ms ease-in-out, once.
  Play on first show.
- @keyframes pet-zzz: three SVG <text>"z" glyphs (system font, var(--muted), 10/12/14px)
  translate(0,0)→(8px,-18px), opacity 0→1→0; 2.4s linear infinite, delays 0/.8/1.6s;
  sleeping only.
- prefers-reduced-motion: reduce → none of the above run; static pose.

Movement (movement.ts pure functions + Companion.tsx loop):
- The container is position:fixed in #companion-slot, z-index var(--z-companion),
  pointer-events:none ALWAYS, aria-hidden="true", moved only by transform: translate3d.
- Default position: the corner slot (96×96, inset var(--companion-inset), above the tab
  bar, safe-area aware).
- Fine pointer ((hover:hover) and (pointer:fine)): target = pointer + (56,40). Each frame
  pos += (target-pos)*0.08, speed capped at 900px/s (lerpStep).
  Dead zone: don't update the target while the pointer is within 120px of the last target (inDeadZone).
  Gap: the pet box edge stays ≥24px from the pointer; push directly away by the shortfall (keepGap).
  Avoid: if the pet box intersects the element under the pointer matched by
  closest('a,button,input,select,textarea,label,[role=button],[data-essential]') or any
  [data-essential], nudge to the nearest free side: right, below, left, above (avoidEssential).
  Idle 5000ms with no pointermove or keydown → perch: the closest [data-companion-perch]
  ancestor of the last hovered/focused element, otherwise the perch card nearest the
  viewport center. Spot = (rect.right-72-8, rect.top-72+14) (perchSpot). If that spot is
  off-screen or overlaps [data-essential] → corner slot.
  Pointer leaves the window → corner slot.
- Touch/coarse: stay in the slot. On a tap of a [data-companion-perch] element: pet-hop
  along a 400ms arc to its perch spot, stay 4000ms, hop back. A new tap retargets.
- Always clamp to the viewport with an 8px margin, safe-area insets and the area above the
  tab bar (clampToViewport). Hidden while a [role=dialog][aria-modal=true] is open or on /login.
- Reduced motion: never follow; stay in the slot.
- Clean up rAF, timers and listeners on unmount.
- movement.test.ts covers lerpStep, inDeadZone, keepGap (24px), perchSpot, clampToViewport
  and avoidEssential with plain numbers/rects.

If the spec is ambiguous, pick the simplest option and append to bus/issues_for_claude.md.
Verify: cd frontend && npm test && npm run build.
Final step: run `bash bus/post_update.sh` if it exists; else append "post_update.sh missing"
to bus/issues_for_claude.md. Stop.

Browser checklist (http://localhost:5173/, signed in, desktop):
[ ] The pet bobs gently, blinks at irregular 3–6s intervals and breathes slowly
[ ] Moving the mouse: the pet trails below-right with a soft lag and doesn't jitter on small moves
[ ] Pushing the cursor toward the pet: it keeps away; it never sits on the button you hover
[ ] Every button and link under/near the pet is still clickable (the pet never blocks a click)
[ ] Stop moving for 5s: the pet hops onto the top-right edge of the hovered card
[ ] Move the mouse out of the window: it returns to the bottom-right slot
[ ] Resize to 390px: it stays inside the viewport and never overlaps the tab bar
[ ] DevTools device mode (touch): the pet sits in the corner; tapping a card makes it hop there and back after ~4s
[ ] prefers-reduced-motion: reduce → static pet in the corner, no following, no bob/blink/zzz
[ ] Opening a dialog or the sign-in page hides the pet
```

---

## Task C: Mood mapping, speech bubbles, controls

```text
You are Codex, implementing a spec. You make no design decisions.
Read only coord/PET_SPEC.md and coord/DESIGN.md plus these files. Do not open other files.

Files you may create:
- frontend/src/companion/moodConfig.ts
- frontend/src/companion/moodMapping.ts
- frontend/src/companion/moodMapping.test.ts
- frontend/src/companion/speech.ts
- frontend/src/companion/speech.test.ts
- frontend/src/companion/SpeechBubble.tsx
- frontend/src/companion/CompanionProvider.tsx
- frontend/src/companion/CompanionControls.tsx
Files you may edit:
- frontend/src/companion/Companion.tsx
- frontend/src/companion/companion.css (append bubble + control styles)
- frontend/src/components/AppShell.tsx (wrap in <CompanionProvider>, add the header toggle)
- frontend/src/pages/Settings.tsx (add the "Companion" section only)
Read-only: frontend/src/api/client.ts, frontend/src/api/types.ts,
frontend/src/safety/SafetyProvider.tsx, frontend/src/test/fixtures.ts.
Never edit frontend/src/safety/, backend/, engine/, waiwai1/ or tests/.

SAFETY (hard): the pet hides whenever the safety screen is open or a response returned
crisis:true this session. Detect this read-only from what SafetyProvider exposes. If it
exposes nothing usable, hide the pet whenever any [role=dialog][aria-modal=true] is open,
and log the gap to bus/issues_for_claude.md. Never route safety content through the pet.

1. Data: CompanionProvider fetches GET /api/v1/today with the existing api client on mount
   and every 10 minutes, and reads only `context_engine`. A 401, network error or 5xx →
   treat context_engine as missing. Never log the payload.
2. moodConfig.ts (all marked // PLACEHOLDER: see TUNING.md request):
   FATIGUE_TIRED=65, MOOD_HAPPY_BELOW=50, IDLE_PERCH_MS=5000, SLEEP_IDLE_MS=120000,
   BUBBLE_MS=5000, BUBBLE_MIN_GAP_MS=60000, MAX_WORDS=12, HOP_HAPPY_MS=4000.
3. moodMapping.ts: mapMood(ce, flags) → Mood | "hidden", a pure function. First match wins:
   1 flags.safetyOpen || flags.crisisThisSession || ce?.safety_status?.crisis_override_triggered → "hidden"
   2 ce.scores_and_metrics.mental_level >= 2 || ce.scores_and_metrics.clinical_floor_breached → "calm" + quiet=true
   3 !ce || ce.scores_and_metrics.night_quality_status === "NO_ESTIMATE" → "neutral"
   4 phys_level >= 2 → "concerned"
   5 phys_level === 1 || mental_level === 1 → "encouraging"
   6 mental_indices.fatigue_alertness >= FATIGUE_TIRED → "tired"
   7 mental_indices.mood_wellbeing < MOOD_HAPPY_BELOW → "happy"
   8 else "calm"
   Return {mood, quiet}. Overlays in Companion.tsx: idle ≥ SLEEP_IDLE_MS → "sleeping" until
   the next input; a non-crisis check-in submitted → "happy" + pet-hop for HOP_HAPPY_MS
   (skipped when quiet). Set --breath-period from
   dashboard_visualization_data.dual_axis_timeline_point.respiration_bpm: 60/bpm clamped
   to 2–10s, or 4s if null.
   moodMapping.test.ts: one test per rule, plus missing nested fields (no crash → neutral).
4. speech.ts: copy the PET_SPEC.md section 6 line table exactly (5 lines × 7 moods), plus
   the intro "Hi, I'm {name}, a friendly guide, not a therapist." shown once per device.
   say(text) returns false and shows nothing if: muted, quiet, safety hidden, a check-in
   question is open or a text input is focused, < BUBBLE_MIN_GAP_MS since the last bubble,
   > MAX_WORDS words, or the text matches
   /\d|diagnos|depress|anxiety|disorder|crisis|suicid|score|streak|level|alert/i.
   Speak once per mood change (random line, never the same line twice in a row).
   speech.test.ts covers every guard and that every table line passes the guard.
5. SpeechBubble.tsx: var(--surface), radius 16, var(--shadow-2), var(--fs-small),
   var(--text), max-width 200px, a tail pointing at the pet, pet-bubble-pop in
   (220ms cubic-bezier(.2,.8,.2,1)) and a 150ms fade out after BUBBLE_MS; no scaling under
   reduced motion. Text is mirrored to one aria-live="polite" region only when speech is on.
6. Public API via useCompanion() and window.companion: setMood(name), say(text) → boolean,
   perchTo(elementId), setCharacter(id), show(), hide(), setMuted(bool), and a readonly
   state {mood, character, visible, muted}. setMood is an override until the next data refresh.
7. Controls:
   - AppShell header (top right, never the bottom-right corner): a 44×44 inline-SVG paw
     button, aria-label "Hide companion"/"Show companion", aria-pressed.
   - Settings "Companion" section: a "Show companion" switch; a character picker of 3
     radio cards (face in neutral, name, personality); a "Speech bubbles" switch.
   - Persist visible/character/muted in localStorage keys companion.visible,
     companion.character and companion.muted, every access wrapped in try/catch.
     Defaults: true, "nimbus", false.
   - Hiding stops all timers and the rAF loop.

If the spec is ambiguous, pick the simplest option and append to bus/issues_for_claude.md.
If a needed API field is missing, use the rule-3 fallback (neutral) and log file, field and
the repro command.
Verify: cd frontend && npm test && npm run build.
Final step: run `bash bus/post_update.sh` if it exists; else append "post_update.sh missing"
to bus/issues_for_claude.md. Stop.

Browser checklist (http://localhost:5173/, signed in):
[ ] First visit: the intro bubble names the pet and says it's a guide, not a therapist; it never appears again after reload
[ ] With fixture context_engine steady → calm/happy face; phys_level 1 → encouraging; phys_level 2 → concerned
[ ] Fixture with mental_level 2 or clinical_floor_breached → calm face and NO bubbles at all
[ ] Trigger the safety screen (PHQ-9 item 9 non-zero): the pet disappears, and the safety screen is unchanged
[ ] No bubble ever contains a number, score, level or clinical word
[ ] At most one bubble per minute; no bubble while answering a check-in question
[ ] Leave the page idle 2 min → sleeping face with zzz; moving the mouse wakes it
[ ] Header paw button hides/shows the pet; keyboard + screen reader announce its state
[ ] Settings: picking Pip/Lumi swaps the character instantly and survives reload
[ ] Speech switch off → no bubbles and nothing announced
[ ] window.companion.say("your score is 5") returns false in the console
```
