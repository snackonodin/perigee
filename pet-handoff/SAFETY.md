# SAFETY.md: hard rules (override everything else)

The people using this app may be exhausted, stressed or in crisis. The app has a
separate **safety screen** that shows support contacts. The pet must never get in its
way and must never sound like a doctor, a judge or a coach.

## S1. Safety screen: the pet disappears completely

When `safetyActive === true`:

1. `<Pet>` returns `null`: no SVG, no canvas, no bubble, no controls.
2. **No timers** (setTimeout/setInterval), **no requestAnimationFrame**, no listeners
   beyond the React tree. Clear all of them in the same commit that sees the flag.
3. **No trail**: the frost canvas is unmounted and its buffer cleared.
4. **No dialog**: `emit()` is a no-op and nothing is queued for later.
5. When the flag goes back to false, the pet starts fresh (idle, no "welcome back" line
   for at least 60 s, no reference to what happened).
6. Required test (`src/pet/__tests__/safety.test.tsx`): with fake timers, render
   `<Pet safetyActive />` → `container.innerHTML === ""`, `vi.getTimerCount() === 0`,
   `requestAnimationFrame` spy called 0 times; then flip a mounted pet to
   `safetyActive` → the same three checks pass, and `emit("app_open")` renders no text.

## S2. Words

1. After a check-in ("quiz"), acknowledge **completion and effort only**. Never mention
   answers, scores, results, levels, "how you did", or anything "high/low/better/worse".
2. **No medical or diagnostic language.** Banned (lint enforces, case-insensitive):
   diagnosis, diagnose, depression, depressed, anxiety, anxious, disorder, illness,
   disease, risk, score, result, symptom, patient, treatment, therapy, therapist,
   clinical, medication, medicine, pill, dose, doctor, suicide, suicidal, self-harm, harm,
   kill, die, death, insomnia, apnea, heart rate, bpm, breathing rate, alert, warning,
   level, normal, abnormal, healthy, unhealthy.
3. **No pressure or instruction:** no "you should", "you must", "you need to", "make
   sure", "don't forget", "try to sleep", "go to bed", "get some sleep".
4. **No guilt:** never mention missed nights, gaps, broken or lost streaks, "where were
   you", "I missed you", "you left me", or the pet being sad, lonely, hungry or sick.
5. **Never restate or reword the app's own guidance** text. The pet has its own small
   script only (the dialog cache).
6. The breathing buddy is labeled "Relaxation exercise. Not a medical tool." and makes
   no claim about benefits.

## S3. Mood and data

1. The pet's mood comes only from engagement (tap, petting, app open, check-in
   completed) and `timeOfDay`.
2. The pet never receives or reads scores, vitals, survey answers, results or the
   engine's Watch/Alert status. Do not add props, fetches or globals for them.
3. A broken streak removes nothing and triggers nothing. Accessories, once earned, stay.

## S4. Access

1. All pet art: `aria-hidden="true"`. The tap target is a `<button>` with
   `aria-label="Pet {petName}"`.
2. Dialog bubble: `role="status"` with `aria-live="polite"`; one line at a time; auto-hide
   after 6 s; never steals focus.
3. Visible controls, reachable by keyboard (Tab), each ≥ 44×44 px: **Hide pet** and
   **Mute pet messages**. Their state persists (`localStorage`, try/catch). A hidden
   pet shows only a small "Show pet" button.
4. Never cover a focused element, a form, or anything marked `data-pet-avoid`.
5. Reduced motion (prop or media query): static pose, no loops, no walking, no canvas
   trail; dialog still works.
