# PET_BUILD: build the companion pet inside the app (claude-fe, after the current polish)

Owner: **claude-fe**. Coordinator: claude. Written 2026-11-14 on the user's request ("prepare and
code the app-pet too, with all the context, prerequisites and UI references").

The full pet spec already exists as a self-contained package: **`pet-handoff/`**. Build from it.
This file adds only what is specific to building it **inside this app** instead of the playground.

## 1. Read first (in this order)

1. `pet-handoff/README.md`, `BRIEF.md` (product context + art, behavior, frost trail, dialog, budget)
2. `pet-handoff/SAFETY.md`: the hard rules. They win every conflict.
3. `pet-handoff/contract.d.ts`: `PetProps`, `PetContext`, `PetEvent`, `emit()`, legacy exports
4. `pet-handoff/TOKENS.css` (glass + pet palette + frost tokens), `TOOLS.md` (allowed techniques +
   the user's UI references), `personas.json` (3 tones), `dialog/schema.json`, `dialog/seed.json`
5. `pet-handoff/reference/cat-head-skeleton.svg`: the art anchor
6. `pet-handoff/ACCEPTANCE.md`: self-grade against it at the end
7. App context: `coord/DESIGN.md` §10 (companion slot) and §15 (Orbit Pop), and `coord/FRONTEND_V3.md`
   (motion catalog)

## 2. Prerequisites (do these first, small commits)

1. **Read-only safety signal.** `SafetyProvider` exposes only `showSafety()`. Add a read-only
   `active: boolean` to the context value (true while the safety screen is open), plus a
   `useSafetyActive()` hook. **No change** to safety logic, triggers, text or the acknowledgement gate.
   Add a test: the flag is true while the screen is shown and false after acknowledgement.
2. **Pet tokens.** Add the NEW pet tokens from `pet-handoff/TOKENS.css` (species palettes, shared pet,
   frost) to `frontend/src/theme/tokens.css`, under a `/* pet */` comment. App tokens stay unchanged.
3. **Folder.** Build in `frontend/src/pet/` (contract names exactly as in `contract.d.ts`). Keep
   `src/companion/` working until §5's swap; then re-export the legacy names from `src/pet/`.

## 3. Where each PetContext field comes from in this app

| Field | Source | Notes |
|---|---|---|
| `species` | Settings → Companion: picker cat / fox / bunny, `localStorage["pet.species"]` (try/catch), default `cat` | Replace the "Coming soon" row |
| `personaId` | `GET /api/v1/today` → `context_engine.dashboard_visualization_data.persona_matrix.quadrant_name`: "Autonomous Pioneer" → `autonomous_pioneer`, "Dynamic Explorer" → `dynamic_explorer`, "Internal Deliberator" → `internal_deliberator`, "Steady Anchor" → `steady_anchor`; "Unspecified" or missing → `default` | Personality only. Never read scores, levels or status from that object |
| `timeOfDay` | **Station time**: `GET /me` → `station_time_offset_min` (null = UTC). morning 05–12, day 12–17, evening 17–22, night 22–05, all in station time | Bedtime window `22:00–06:30` is also station time |
| `safetyActive` | `useSafetyActive()` from prerequisite 1 | Pet renders nothing while true |
| `reducedMotion` | `html[data-reduce-motion="true"]` (Settings switch) OR `prefers-reduced-motion` | |
| `nightsLogged` | Count of valid nights from `GET /api/v1/nights` (same number the Sleep page shows) | Lifetime total; drives accessories 3/7/14/30 |
| `streakDays` | Consecutive valid nights ending last night, from the same list | Only for the milestone line; a break changes nothing |

## 4. Events to emit from the app (`emit(name)`)

| Event | When |
|---|---|
| `first_run` | Once ever (pet sets `pet.firstRunDone`) |
| `app_open` | AppShell mount |
| `welcome_back` | AppShell mount when last visit was more than 24 h ago (`pet.lastSeen`) |
| `quiz_start` | A questionnaire or check-in sheet opens |
| `quiz_complete` | `POST /responses` succeeded **and** `safety_screen_required === false`. Never on a safety response |
| `night_logged` | `today.latest_night.date` is newer than `pet.lastNight` |
| `streak_milestone` | `streakDays` reaches 3, 7, 14 or 30 (once each) |
| `bedtime_near` / `sleep_start` / `wake` / `idle_long` / `pet_tap` / `goodbye` | Fired by the pet itself (BRIEF §2, phase 06) |

Never pass a score, value, status, answer or result in an event.

## 5. Placement in the app

- Portal into `#companion-slot` (already in AppShell; 96 px, bottom-right, `--z-companion` 500, below
  the safety screen at 1000). On screens 768 px and wider, `placement="stage"` lets the pet walk on cards marked
  `data-pet-perch` (add the attribute to the Today, Sleep and Check-in glass tiles) and avoid `data-pet-avoid`
  (forms, the Monitor start panel, dialogs).
- Frost trail: only on those perch tiles, under the text (BRIEF §3); tint alpha at most 0.55.
- Controls (hide pet, mute messages, snooze 1 h, optional "Breathe with me"): in Settings →
  Companion, and as a small 44 px button next to the pet.
- Swap: `/dev/companion` gallery shows the new species; remove `src/companion/` only after the
  legacy exports are re-exported from `src/pet/` and its tests pass.

## 6. UI references the user gave (use them, rebuilt in our own code)

- **Tamagotchi / desktop pets:** `terminal-pet` and "di-pett" (the user's names; the exact repo is unconfirmed). Use them for a
  tiny body, idle loops and reacting to small events. No code or art copied.
- **react-bits** (vendored in `src/vendor/react-bits/`, MIT + Commons Clause): the bubble pop uses the
  AnimatedContent feel; SplitText is not for the pet.
- **GSAP** (now in the app, pinned 3.15.0): **allowed for the pet's timelines** (hop, yawn, stretch,
  walk), always through `gsap.matchMedia()` for reduced motion and killed on unmount and under
  `safetyActive`. It does not count toward the pet's 80 KB budget, because the app already ships it.
  (`pet-handoff/TOOLS.md` forbids GSAP only because the external playground does not have it.)
- **Lenis** smoothing: use the lerp idea (`0.12`) for eye/head look-follow.
- **Vanta** fog softness: inspires the frost texture. Never WebGL in the pet.
- **Cult UI** sheen: the rim light sweep on tap. **Skipper UI**: petting micro-interactions.
  **Watermelon UI**: bubble spacing.
- **CSS art** (technique only): Lynn Fisher *A Single Div*, Diana Smith *Pure CSS Francine*,
  Jhey Tompkins and Ana Tudor CodePens, Josh Comeau's shadows article, CSSBattle economy.
- **The user's screenshots** in `imageref/` (11 files): Google Health and Happify warmth, the "20 ways"
  checklist. Look at them before drawing.

## 7. Order (one commit each; build + vitest + screenshots at 390 and 1440 each time)

1. Prerequisites 1–3
2. `pet-handoff/phases/01-cat.md` → `02-fox-bunny.md` → `03-behavior.md` → `04-frost-trail.md` →
   `05-dialog-cache.md` (run `pet-handoff/playground/scripts/lint_dialog.mjs` against
   `src/pet/dialog/cache.json`) → `06-integration-qa.md`, all inside `frontend/src/pet/`
3. Wire §3–§5, Settings → Companion, swap out `src/companion/`
4. Self-grade `pet-handoff/ACCEPTANCE.md`; post `done: pet` with the sha list

## 8. Never

- The pet never sees scores, vitals, survey answers, results or Watch/Alert status.
- No medical words, no "you should", no guilt about missed nights, no pressure about sleep
  (`lint_dialog.mjs` enforces this).
- Nothing renders or runs while `safetyActive` is true.
- No raster images, network calls or external fonts in `src/pet/`.
