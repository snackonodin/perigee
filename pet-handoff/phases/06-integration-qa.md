# Phase 06: public API, controls, QA, return

**Goal:** finish the contract (`emit`, legacy exports, controls), pass every acceptance
item, and package the return.

**Read first:** `contract.d.ts`, SAFETY.md (all), ACCEPTANCE.md, RETURN.md.

## Safety (repeat; re-test all of it)
- `safetyActive` ⇒ nothing rendered, no timers, no rAF, no trail, no dialog, `emit()` no-op.
- After it clears: fresh idle, no line for 60 s.
- Mood only from engagement + `timeOfDay`. Never sad, never guilt, never scores.
- Art `aria-hidden`; bubble `aria-live="polite"`; visible keyboard-reachable controls.

## Files (in `src/pet/`)

| File | Content |
|---|---|
| `emit.ts` | Module-level bus: `emit(event)` → normalizes to `PetEvent` (fills `at`), forwards to the mounted `<Pet>` (subscribe/unsubscribe). No-op if no pet is mounted or it is in safety mode. Not queued. |
| `PetControls.tsx` | Two buttons, ≥ 44×44 px, Tab-reachable, labelled: "Hide pet"/"Show pet" and "Mute pet messages"/"Unmute pet messages"; optional "Breathe with me" (BRIEF §2) labelled "Relaxation exercise. Not a medical tool.". State in `localStorage` `pet.hidden`, `pet.dialog.muted` (try/catch). Snooze: "Quiet for 1 hour" sets `pet.dialog.snoozeUntil`. Renders `null` under safety. |
| `CompanionFace.tsx` | Legacy: `CompanionFace({ character, mood })` → `PetArt` with `LEGACY_CHARACTER_TO_SPECIES[character]` and mapped mood (contract comment), static, `aria-hidden`. Also export `CHARACTERS` (ids nimbus/pip/lumi; names "Miso the cat", "Ember the fox", "Clover the bunny"; one-line personalities) and `LEGACY_CHARACTER_TO_SPECIES = { nimbus: "cat", pip: "fox", lumi: "bunny" }`. |
| `Pet.tsx` | Subscribes to `emit`; picks lines via `pickLine` with `toneFor(personaId)`; shows `DialogBubble`; renders `PetControls` next to the pet in corner placement. Emits `first_run` once (`pet.firstRunDone`). Fires `bedtime_near` 30 min before `BEDTIME_START`, `sleep_start`/`wake` on window edges, `idle_long` after 10 min idle. |
| `index.ts` | Exports exactly: `Pet`, `PetControls`, `PetArt`, `emit`, `CompanionFace`, `CHARACTERS`, `LEGACY_CHARACTER_TO_SPECIES`, and `export type *` from `./types`. |
| `__tests__/safety.test.tsx` | Extend: `emit("quiz_complete")` while safetyActive renders no text; controls absent under safety; after flip back, no line within 60 s (fake timers). |
| `__tests__/a11y.test.tsx` | Art has `aria-hidden="true"`; tap button has an accessible name; bubble has `role="status"` + `aria-live="polite"`; both controls focusable with `.focus()` (no extra packages: `@testing-library/user-event` is not installed), and ≥ 44 px via inline style/class. |
| `__tests__/legacy.test.tsx` | `CompanionFace` renders for all 3 characters × 7 legacy moods without timers; `concerned` does not render a sad face (same eyes as `calm`). |
| `__tests__/contract.test.ts` | Type-level: `const p: PetProps = {...}` compiles with exactly the contract fields; `index.ts` exports every name above. |

## Final QA

```bash
npm run check:final        # tsc, lint --require, vitest, build, budget, render: must exit 0
```
Then go through ACCEPTANCE.md item by item and fill STATUS.md (RETURN.md template).
Grep checks to paste into STATUS.md:
```bash
grep -rniE "fetch\(|XMLHttpRequest|https?://" src/pet --include=*.ts --include=*.tsx | grep -v w3.org   # expect nothing
grep -rnE "setTimeout|setInterval" src/pet --include=*.ts --include=*.tsx | grep -v __tests__ | grep -v scheduler.ts  # expect nothing
grep -rniE "score|result|level|status" src/pet/*.tsx src/pet/*.ts   # only type names/comments, no data inputs
```

## Return

Follow RETURN.md exactly: `frontend-src-pet/` + `STATUS.md` → `pet-return.zip`.

## Stop

Stop. Print STATUS.md.
