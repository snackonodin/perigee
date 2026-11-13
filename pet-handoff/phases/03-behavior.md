# Phase 03: behavior

**Goal:** the pet comes alive: breathing, blinks, twitches, interactions, walking and
sleep mode, all driven by the rig variables. Plus the safety rule from day one.

**Read first:** BRIEF.md §2 (all the numbers), SAFETY.md (S1, S3, S4.5).

## Safety (repeat of SAFETY.md, non-negotiable)
- `safetyActive === true` ⇒ `<Pet>` returns `null`; **no timers, no rAF, no listeners**.
  Clear everything in the effect cleanup that runs when the flag turns true.
- Mood comes only from engagement + `timeOfDay`. No other input exists. Never sad.
- No line of text in this phase (dialog is phase 05).

## Files (in `src/pet/`)

| File | Content |
|---|---|
| `petConfig.ts` | All numbers from BRIEF §2 as named constants: `BLINK_MIN_MS=3000`, `BLINK_MAX_MS=6000`, `BREATH_AWAKE_S=4`, `BREATH_ASLEEP_S=6`, `TAP_MAX_MS=300`, `TAP_MAX_MOVE_PX=8`, `LONG_PRESS_MS=600`, `PET_MAX_MS=5000`, `POKE_COUNT=3`, `POKE_WINDOW_MS=1500`, `WALK_MIN_WIDTH_PX=768`, `WALK_SPEED_PX_S=60`, `WALK_IDLE_MS=20000`, `WALK_COOLDOWN_MS=45000`, `BEDTIME_START="22:00"`, `BEDTIME_END="06:30"`, `ACCESSORY_NIGHTS=[3,7,14,30]`. Comment: "pet behavior timing, not health thresholds". |
| `behavior.ts` | **Pure** state machine, no DOM, no timers: `reduce(state, event, now) → state`. States: `idle, happy, petting, playful, yawning, stretching, walking, sitting, sleepy, sleeping, waking`. Events: `tick, tap, pressStart, pressEnd, poke, idleFor, enterBedtime, leaveBedtime, perchFound, arrived`. Output includes target rig values. |
| `scheduler.ts` | The ONLY place that creates timers. `createScheduler()` returns `{ after(ms, fn), every(minMs, maxMs, fn), clearAll(), count() }`. Random intervals use an injectable `random()` (tests pass a seeded one). |
| `useRig.ts` | Hook that writes rig variables to the root element's `style` (`el.style.setProperty("--blink", "1")`), never via React state per frame. |
| `useInteractions.ts` | Pointer + keyboard → behavior events (thresholds from `petConfig`). |
| `walk.ts` | Pure helpers: `perchTargets(rects, viewport)`, `stepToward(pos, target, speed, dt)`, `avoids(rect, avoidRects)`. Walk only when `innerWidth >= 768` and not reduced motion. |
| `accessories.ts` | `unlocked(nightsLogged) → ("scarf"|"star"|"moon"|"crown")[]`, union with what `localStorage["pet.accessories"]` already holds (try/catch), then saved. Never removes. |
| `Pet.tsx` | Composes the above: `PetArt` + rig + scheduler. Corner placement uses `position: fixed; right: var(--companion-inset,16px); bottom: var(--companion-inset,16px); z-index: var(--z-companion,500)`. Hit area: a `<button aria-label="Pet {petName}">` ≥ 64×64 wrapping the `aria-hidden` art. |
| `pet.css` | Keyframes for blink, breathe, twitch, yawn, stretch, hop (squash/stretch), petting sway, curl, z-float. Durations from BRIEF §2. `@media (prefers-reduced-motion: reduce)` and `[data-reduced="true"]` ⇒ `animation: none` everywhere. |
| `__tests__/behavior.test.ts` | tap → happy then back to idle after 1200 ms; 3 pokes in 1500 ms → playful; long press → petting, released at 5000 ms max; bedtime → sleeping; no transition ever yields a "sad" state. |
| `__tests__/accessories.test.ts` | 3/7/14/30 unlock; a later smaller `nightsLogged` keeps earned items; throwing storage does not crash. |
| `__tests__/safety.test.tsx` | SAFETY.md S1 test (render with safetyActive; flip mid-life). Use `vi.useFakeTimers()`, `vi.getTimerCount()`, and `vi.spyOn(window, "requestAnimationFrame")`. |

## Checks

```bash
npm run check && npm test
```
All three test files pass. With a browser, `npm run dev`: blink every 3–6 s, breathing
visible but subtle, tap/long-press/3-poke work, toggling "Safety screen open" removes the
pet instantly, toggling "Reduced motion" freezes it in a neutral pose.

## Stop

Stop after this phase. Print: test counts, the list of states, and how you verified the
timer count is 0 under safety.
