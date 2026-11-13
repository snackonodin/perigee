# FRONTEND_TASKS.md: Codex prompts for the pastel redesign

Owner: Claude Code (art director). Run the tasks **in order 1 → 4**, one at a time:
they share `frontend/src/theme/shell.css`, and later tasks build on Task 1's tokens and
components. Paste one prompt per Codex run.

Screens not covered here (Persona, Settings, and the Sign-in form beyond its Task 1 background) pick up the new tokens
automatically. Any hard-coded dark colors left on them get their own task later; Codex
logs them to `bus/issues_for_claude.md` and does not fix them now.

---

## Task 1: Foundation + Today screen

```text
You are Codex, implementing a design spec. You make no design decisions.
Read only coord/DESIGN.md and these files. Do not open any other file.

Files you may edit:
- frontend/src/theme/tokens.css
- frontend/src/theme/shell.css
- frontend/src/components/AppShell.tsx
- frontend/src/pages/Overview.tsx
- frontend/src/components/VitalsTiles.tsx
- frontend/src/components/IndexCards.tsx
- frontend/src/components/RrTrend.tsx
- frontend/index.html (title + favicon link only)
- frontend/package.json, frontend/package-lock.json (only the dependency changes in DESIGN.md 7.1)
- frontend/src/pages/Login.tsx (only to add the Vanta FOG background per DESIGN.md 7.1 and remove the spacecraft art)
Files you may create:
- frontend/src/vendor/react-bits/* (copied components per DESIGN.md 7.1)
- frontend/public/favicon.svg
- frontend/src/components/StatusChip.tsx
- frontend/src/components/VitalCard.tsx
- frontend/src/components/BreathingOrb.tsx
- frontend/src/components/EcgTrace.tsx
- frontend/src/components/SignalQualityMeter.tsx
Read-only (you may read, never edit): frontend/src/api/types.ts, frontend/src/test/fixtures.ts.
Never touch backend/, engine/, waiwai1/, tests/, frontend/src/safety/, or any other file.

Goal: replace the dark space theme with the light pastel theme in coord/DESIGN.md
and rebuild the Today screen with it.

Steps:
1. tokens.css: replace all tokens with DESIGN.md sections 2, 3, 4 and 7 exactly.
   Delete every dark-theme token. Add the reduced-motion block from section 7.
2. shell.css: remove starfield/glow/grid/gradient/neon/monospace-HUD styles. Restyle
   the page background, the cards and the tab bar per sections 4 and 6.8. Use only
   tokens; no raw hex.
3. Build StatusChip (6.1), VitalCard (6.2), BreathingOrb (6.3), EcgTrace (6.4, UI label
   "Pulse trace", never "ECG") and SignalQualityMeter (6.6) as small presentational
   components. They take data via props and never compute status.
4. Overview.tsx (Today): the hero is the BreathingOrb with the latest respiration rate.
   Below it, a grid of VitalCards: Breathing (mint), Sleep (sky), Mind/check-in
   (lavender), Heart (peach, with the "Experimental estimate" chip) plus the Pulse trace
   inside the Heart card. Status and advisory text come only from the API fields the page
   already reads (today.context_engine and /live/vitals). Keep the existing API calls,
   the 401 handling and the labelled TODO(api) mock fallback; restyle the mock banner per
   6.8.
5. AppShell.tsx: tab bar per 6.8 with inline-SVG line icons (no emoji). Keep routes and
   swipe navigation, but transitions must be at most --dur-base and must respect
   reduced motion.
6. index.html + favicon.svg: title "Astronaut Vitals"; favicon per 6.8.
7. Show the signal-quality meter only if an existing API field supplies quality or
   coverage. If none exists, do not show it, and log that.
8. Libraries per DESIGN.md 7.1: in frontend/, run npm install --save-exact gsap@3.15.0
   lenis@1.3.27 vanta@0.5.24 three@0.134.0 and npm uninstall @fontsource-variable/inter.
   GSAP drives the orb, trace and card-enter motion via gsap.matchMedia. Create one Lenis
   instance in AppShell (skipped under reduced motion, stopped while the safety screen is
   open). Add the Vanta FOG background on Login only, lazy-loaded. Copy only the listed
   react-bits components into frontend/src/vendor/react-bits/ with their MIT header.
9. Companion slot per DESIGN.md 10: add the z-index tokens, the empty #companion-slot in
   AppShell, and the bottom padding on scrolling pages. Keep every control out of that
   corner.

If DESIGN.md is ambiguous, pick the simplest option and append to
bus/issues_for_claude.md: file, what was unclear, what you chose.
If an API field you need does not exist, do not invent data: show the "none" state and
log file, missing field, and the exact command to reproduce to bus/issues_for_claude.md.

Verify: cd frontend && npm test && npm run build. Both must pass.
Final step: run `bash bus/post_update.sh` if it exists. If it does not, append
"post_update.sh missing" to bus/issues_for_claude.md. Then stop.

Browser checklist (http://localhost:5173/, signed in):
[ ] Page background is pale mint-white; no dark/navy area, gradient, starfield or glow remains
[ ] Breathing orb shows rate + "br/min" and gently scales; it is static with DevTools > Rendering > prefers-reduced-motion: reduce
[ ] Each vital card shows label, number, unit, sparkline, status chip with word + icon
[ ] Watch and alert fixtures show the inset bar + chip word; nothing blinks or pulses
[ ] Heart card says "Experimental estimate", and the trace is labelled "Pulse trace", not ECG
[ ] Missing data shows "No reading" with a reason, never 0
[ ] Tab title "Astronaut Vitals" and the new favicon are visible
[ ] At 390px wide: one column, no horizontal scroll; at 1280px: two-column grid
[ ] Tab through the page: every control has a visible teal focus ring, in visual order
[ ] No emoji anywhere; all text is readable (spot-check muted text is not on a pastel card)
[ ] Sign-in shows the soft pastel fog; with reduced motion on, it's a flat background
[ ] Network tab: three.js loads only on the sign-in page, not on Today
[ ] Smooth scroll is off with reduced motion; nothing sits in the bottom-right companion corner at 390px or 1280px
```

---

## Task 2: Sleep screen

```text
You are Codex, implementing a design spec. You make no design decisions.
Read only coord/DESIGN.md and these files. Do not open any other file.

Files you may edit:
- frontend/src/pages/Sleep.tsx
- frontend/src/theme/shell.css (only rules whose selectors start with .sleep-)
Files you may create:
- frontend/src/components/SleepArc.tsx
Read-only: frontend/src/components/StatusChip.tsx, frontend/src/components/VitalCard.tsx,
frontend/src/theme/tokens.css, frontend/src/api/types.ts, frontend/src/test/fixtures.ts.
Never touch backend/, engine/, waiwai1/, tests/, frontend/src/safety/, or any other file.

Goal: restyle Sleep in the pastel theme using the sky role color.

Steps:
1. Build SleepArc per DESIGN.md 6.5 (presence hours, onset, midsleep, wake; no sleep
   stages; dashed segment for partial coverage).
2. Sleep.tsx top: SleepArc for the latest night plus its StatusChip and one-line
   explanation from the API.
3. Below: the 28-night presence bars as flat --sky bars (no gradient), with the latest
   night in --teal plus a "Last night" text label. The personal breathing median ± MAD is
   a --line band with a text label. Each bar gets an aria-label (date, hours, status), and
   there is a visually hidden table of the same data.
4. Nightly detail rows: VitalCard-style rows; the expand/collapse control is a button with
   aria-expanded.
5. Keep the existing /nights call, the 401 behavior and the labelled TODO(api) empty
   fallback; restyle the notice as the butter banner (6.8).
6. Empty state per DESIGN.md 9.

Ambiguity → simplest option, logged to bus/issues_for_claude.md (file, what was unclear,
what you chose). Missing API field → "none" state, logged with file, field and repro
command. Never invent values.

Verify: cd frontend && npm test && npm run build. Both must pass.
Final step: run `bash bus/post_update.sh` if it exists. If it does not, append
"post_update.sh missing" to bus/issues_for_claude.md. Then stop.

Browser checklist (http://localhost:5173/sleep, signed in):
[ ] Arc runs onset → wake with a midsleep dot; partial coverage is dashed and labelled
[ ] No sleep stages appear anywhere
[ ] 28 bars are flat sky blue; last night is teal AND says "Last night"
[ ] Baseline band has a text label, not just a shaded area
[ ] Status chip shows word + icon; watch/alert never recolor the arc
[ ] Arc draw animation is skipped with prefers-reduced-motion: reduce
[ ] Empty range shows the empty state, not a blank chart
[ ] 390px: no horizontal scroll, bars still tappable (≥44px hit area per row/column group)
[ ] Expand/collapse works with Enter/Space and announces expanded state
```

---

## Task 3: Check-in screen (+ safety screen visuals)

```text
You are Codex, implementing a design spec. You make no design decisions.
Read only coord/DESIGN.md and these files. Do not open any other file.

Files you may edit:
- frontend/src/pages/Psyche.tsx
- frontend/src/components/CheckinForm.tsx
- frontend/src/components/CheckinCalendar.tsx
- frontend/src/components/QuestionnaireList.tsx
- frontend/src/theme/shell.css (only rules whose selectors start with .checkin-, .calendar-, .questionnaire- or .safety-)
Read-only: frontend/src/safety/SafetyProvider.tsx, frontend/src/components/StatusChip.tsx,
frontend/src/theme/tokens.css, frontend/src/api/types.ts, frontend/src/test/fixtures.ts.
Never edit frontend/src/safety/ or any file not listed. Never touch backend/, engine/,
waiwai1/, tests/.

SAFETY RULE (hard): do not change when the safety screen opens, what it says, its
acknowledgement gate, its focus handling, or the fail-closed handling of missing
crisis/safety fields in CheckinForm. You may change only class names' CSS for the safety
screen (DESIGN.md 6.7). If a visual change seems to need a logic change, stop and log it
instead.

Goal: restyle Check-in in the pastel theme using the lavender role color.

Steps:
1. Question view: one question per card on --surface, the question in --fs-h2, and
   answer choices as full-width 56px-high option buttons (radius 16, --line border;
   selected = --lavender fill + 2px --teal border + check icon). Progress is "Question 3
   of 9" text plus a thin --teal bar.
2. Questionnaire list: VitalCard-style rows with a lavender icon disc, the name, and
   "Due today" / "Done" chips (word + icon).
3. Calendar: day cells with pastel pills like the Happify reference, keyed by entry type
   only (no mood is inferred). Each entry type also has a distinct marker shape (dot,
   ring, square) and a legend. Today has a --teal outline.
4. Remove the orbit illustration and any dark/space art.
5. Safety screen visuals per DESIGN.md 6.7 via .safety- CSS only: white, calm, no
   decoration, no animation.

Ambiguity → simplest option, logged to bus/issues_for_claude.md. Never invent data.

Verify: cd frontend && npm test && npm run build. Both must pass.
Final step: run `bash bus/post_update.sh` if it exists. If it does not, append
"post_update.sh missing" to bus/issues_for_claude.md. Then stop.

Browser checklist (http://localhost:5173/checkin, signed in):
[ ] One question per card; answers are large buttons, and the selected one shows fill + border + check
[ ] Progress reads as text, not just a bar
[ ] Calendar legend explains each marker; markers differ by shape, not only color
[ ] No mood words are inferred on the calendar
[ ] Answer the PHQ-9 item 9 with any non-zero option: the safety screen opens immediately, full-screen
[ ] Safety screen: white, plain, no animation, contacts readable, focus lands on the heading, cannot dismiss without acknowledgement
[ ] Same behavior with prefers-reduced-motion on and off
[ ] Keyboard only: can answer every question and reach Submit
[ ] 390px: no horizontal scroll, option buttons ≥44px tall
```

---

## Task 4: Body screen

```text
You are Codex, implementing a design spec. You make no design decisions.
Read only coord/DESIGN.md and these files. Do not open any other file.

Files you may edit:
- frontend/src/pages/Body.tsx
- frontend/src/theme/shell.css (only rules whose selectors start with .body-)
Read-only: frontend/src/components/StatusChip.tsx, frontend/src/components/VitalCard.tsx,
frontend/src/components/SignalQualityMeter.tsx, frontend/src/theme/tokens.css,
frontend/src/api/types.ts, frontend/src/test/fixtures.ts.
Never touch backend/, engine/, waiwai1/, tests/, frontend/src/safety/, or any other file.

Goal: turn the dark holographic body scan into a light, friendly body map.

Steps:
1. Keep the five nodes and their data: Mind (lavender), Rest (sky), Respiration (mint),
   Autonomic (peach), Cabin (butter). Keep the existing node positions and the selection
   behavior.
2. Figure: a simple rounded silhouette with a --surface fill, 2px --line stroke, no
   glow, no grid, no dashed HUD rings, and no monospace or ALL-CAPS labels.
3. Nodes: 20px discs in the role pastel with a 2px --text outline; the selected node gets
   a 3px --teal ring. Each node is a <button> with an aria-label (system, status word).
   Leader lines are 1px --line to sentence-case labels; each label carries a small
   StatusChip.
4. Selecting a node opens a detail card beside the figure (below it under 768px), styled
   as a VitalCard with that system's values, the SignalQualityMeter if data exists, and
   the "Personal baseline · 28 nights" caption.
5. Systems with no data show "No reading" and a reason, never a fabricated value.
6. Selection change: the detail card crossfades over --dur-base; instant under reduced
   motion.

Ambiguity → simplest option, logged to bus/issues_for_claude.md. Never invent data.

Verify: cd frontend && npm test && npm run build. Both must pass.
Final step: run `bash bus/post_update.sh` if it exists. If it does not, append
"post_update.sh missing" to bus/issues_for_claude.md. Then stop.

Browser checklist (http://localhost:5173/body, signed in):
[ ] No dark background, grid, glow or HUD styling remains
[ ] Five nodes in their role pastels, each labelled in sentence case with a status chip (word + icon)
[ ] Tab to each node; Enter/Space selects it, and the detail card updates
[ ] Selected node shows a teal ring, not only a color change
[ ] Systems without data say "No reading" with a reason
[ ] Detail card sits below the figure at 390px with no horizontal scroll; beside it at 1280px
[ ] Crossfade is off with prefers-reduced-motion: reduce
[ ] The figure stays in proportion when the window is resized
```
