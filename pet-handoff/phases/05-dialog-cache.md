# Phase 05: dialog cache and picker

**Goal:** an offline line library in the pet's voice, a picker that chooses well, and a
bubble that never nags. No AI at runtime.

**Read first:** BRIEF.md §4, SAFETY.md S2 (banned terms and rules), `personas.json`
(tones), `dialog/schema.json`, `dialog/seed.json` (voice anchors).

## Safety (repeat)
- After `quiz_complete`: completion and effort only. Never answers, results or "how you did".
- No medical words, no "you should", no guilt about missed nights, no pressure about sleep.
  `sleep_start`/`bedtime_near` lines talk about **the pet** getting cozy, not the person.
- Never reword the app's guidance. `safetyActive` ⇒ nothing is picked or shown.

## Files (in `src/pet/dialog/`)

| File | Content |
|---|---|
| `cache.json` | All 13 events × 3 tones. **≥ 6 lines each; ≥ 10 for `quiz_complete`, `bedtime_near`, `sleep_start`, `wake`.** Start by copying all 27 lines from `dialog/seed.json` verbatim. ≈ 300 lines total. ≤ 90 chars. Ids `<event>.<tone>.NN`. Mix `tod` values so every event has at least 2 `any` lines per tone. |
| `picker.ts` | `pickLine(cache, event, tone, tod, now, deps) → DialogLine | null`. Filter `tod === current || "any"`; drop ids in the last-8 list (`pet.dialog.recent`); weighted random with injectable `random`; if all are filtered out, reset the recent list and retry once. Cooldowns in `petConfig.ts`: `DIALOG_COOLDOWN_MS = { default: 120000, pet_tap: 20000, idle_long: 600000, app_open: 300000 }`. Return `null` when muted, snoozed (`now < snoozeUntil`), a form field has focus, or safety is active. Every `localStorage` access in try/catch. |
| `toneFor.ts` | `toneFor(personaId) → Tone` from `personas.json` (copy the mapping as a constant; do not import the JSON from outside `src/pet/`). |
| `DialogBubble.tsx` | `role="status"`, `aria-live="polite"`, one line, auto-hide 6000 ms (timer via `scheduler.ts`, never a bare setTimeout), glass style (`--glass`, `--glass-border`, radius 16, `--fs-small`, `--text`), max-width 240 px, above the pet, never focusable. `{petName}` replaced. |
| `__tests__/picker.test.ts` | tod filtering; last-8 avoidance; weighting (seeded random, 1000 draws, a weight-3 line ≈ 3× a weight-1 line ±20%); cooldown; focus guard (focus an `<input>` → null); throwing `localStorage` → still works; muted → null. |

## Voice guide (in addition to personas.json)
- The pet talks about itself, the glass, the frost, stars, naps, stretching.
- Effort words allowed: thanks, done, finished, nice effort, took care, showed up.
- `welcome_back` must not imply absence was bad: "Hi again" yes; "I missed you" no.
- `streak_milestone` celebrates the count gently (3/7/14/30 nights) and never mentions
  what happens if it ends.
- `goodbye`: warm and short. No "come back soon"-style pressure.

## Checks

```bash
node scripts/lint_dialog.mjs --require     # must print OK
npm run check && npm test
```

## Stop

Stop after this phase. Print: total lines, lines per event (min/max), test counts, and
3 random sample lines per tone.
