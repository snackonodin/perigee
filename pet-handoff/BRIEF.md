# BRIEF: the companion pet

## 0. The product (read first)

1. The app is a contactless sleep and wellbeing monitor for astronauts and crews on long missions.
2. A small Wi-Fi device senses breathing and movement at night; nobody wears a sensor.
3. Once a week the person answers a short wellbeing check-in (a "quiz").
4. The app compares each person with their own past ("unusual for you"), never with others.
5. It is a screening and awareness tool. It does not diagnose, treat or advise.
6. The UI is light pastel glassmorphism: frosted white cards over a soft mint/sky/lavender/peach backdrop.
7. A safety screen appears when a check-in shows the person may need support. It covers everything.
8. The pet is a friendly companion that makes the app feel warm. It is not a care game: no hunger, no health bar, no death.
9. People using this app may be tired, stressed or low. A careless word from a cute character can hurt.
10. That is why the pet never comments on health, scores or results, never pressures, never guilts.

## 1. Art

**Three species** with silhouettes you can tell apart at 64px: **cat** (pointed ears,
round cheeks, curled tail), **fox** (tall pointed ears with dark tips, cream muzzle and
chest, big brush tail with cream tip), **bunny** (two long upright ears 0.9× head height,
round body, pom tail).

**Format:** pure inline SVG + CSS custom-property rig. Vector only, no raster, no fonts.
One `viewBox="0 0 256 256"` per species. Must look crisp at 64, 128, 256 and 512 CSS px
and at DPR 1, 2 and 3.

**No hairlines:** at 64px a viewBox unit is 0.25 CSS px, so every stroke is **≥ 4
units** wide. No shape thinner than 4 units unless it is a fill with no stroke and you
accept it vanishing at 64px.

**Cute proportions (numbers, not adjectives):**

| Part | Rule |
|---|---|
| Head | 55–60% of the pet's total height (sitting pose) |
| Eyes | Large: each eye ≈ 13–15% of head width. Wide-set: centers ≈ 46% of head width apart. **Below** the head's vertical midline (eye center ≈ 55–60% down the head) |
| Highlights | Two per eye: big circle r ≈ 35% of eye radius at upper-right; small r ≈ 15% at lower-left. Pure white |
| Nose | Tiny: width ≈ 5% of head width, rounded triangle |
| Mouth | "w" shape directly under the nose, total width ≈ 11% of head width, stroke 4–5 units, round caps |
| Blush | Soft ellipses under the outer eye corners, `--pet-blush`, opacity 0.55, blurred edges (radial gradient, not a filter) |
| Forms | Rounded everywhere. No sharp corners except ear tips (radius ≥ 6 units) |
| Shading | 3 tones per species: base, shade (lower/back), deep (crevices) — see TOKENS.css |
| Rim light | A faint 6–10 unit arc on the top-right edge in `--pet-rim` (the glass tint), opacity 0.5–0.7 |
| Contact shadow | Ellipse under the pet, `--pet-shadow`, ≈ 70% of body width, 8–12 units tall |
| Outlines | **No black outlines.** Separate shapes by tone. If a separation line is needed, use the "deep" tone, ≥ 4 units |

Techniques to explore (see TOOLS.md): layered linear/radial gradients, `feTurbulence`
fur texture at opacity ≤ 0.12 (static, never animated), `clip-path` for shading inside the
head, `mix-blend-mode: soft-light` for the rim, `filter: drop-shadow` on the whole pet at
most once, CSS `@property` to make rig variables animatable.

**60 fps on a mid phone:** animate only `transform` and `opacity` driven by the rig
variables. Never animate filters, gradients or path data. ≤ 120 SVG elements per species.

**Rig variables** (register each with `@property`, `syntax: "<number>"`, `inherits: true`):

| Variable | Range | Default | Drives |
|---|---|---|---|
| `--look-x` | −1…1 | 0 | pupils move ±6 units, head group translates ±4 units |
| `--look-y` | −1…1 | 0 | pupils ±4 units, head ±2 units |
| `--blink` | 0…1 | 0 | eye group `scaleY(1 − 0.92·blink)` around eye center |
| `--breathe` | 0…1 | 0 | body `scaleY(1 + 0.025·b)`, `scaleX(1 − 0.01·b)`, origin bottom center |
| `--ear-l`, `--ear-r` | −1…1 | 0 | rotate each ear ±14° around its base |
| `--tail` | −1…1 | 0 | rotate tail ±22° around its root |
| `--mouth` | 0…1 | 0 | 0 = closed "w", 1 = open (yawn/happy); scale the open-mouth shape in |
| `--squash` | −1…1 | 0 | whole pet `scaleY(1 − 0.12·s)`, `scaleX(1 + 0.08·s)`, origin bottom center; negative = stretch |

## 2. Behavior

| Behavior | Numbers |
|---|---|
| Breathing | `--breathe` sine 0→1→0. Period 4.0 s awake, 6.0 s asleep |
| Blink | Every uniform(3000, 6000) ms. Close 60 ms, open 80 ms. 15% chance of a double blink |
| Ear twitch | One ear, every uniform(5, 12) s, 220 ms, to ±0.6 and back |
| Tail | Cat: slow sway ±0.3, 3.2 s. Fox: flick to 0.8 every 8–15 s. Bunny: wiggle ±0.4 ×3, 300 ms, every 10–20 s |
| Yawn | 1400 ms (`--mouth` 0→1→0, eyes half closed). At most once per 60 s idle; twice as likely in the bedtime window |
| Stretch | 1800 ms (`--squash` −0.4 hold, front low). After 45 s idle, or on wake |
| Head tilt | 600 ms, ±10°, on tap (50% chance) |
| Squash & stretch | Anticipation 120 ms squash 0.6 → jump stretch −0.5, 220 ms → land squash 0.4, 100 ms → settle 0, 200 ms |

**Interactions** (hit area 64×64 CSS px minimum, centered on the pet):

- **Tap** (pointer up < 300 ms, moved < 8 px) → **happy**: eyes become "^ ^" arcs, `--mouth` 0.8, a small hop, 1200 ms.
- **Long press** (≥ 600 ms) → **petting**: eyes closed and content, both ears −0.5, a gentle sway while held, max 5 s.
- **Poke ×3** (3 taps within 1500 ms) → **playful**: a pounce/spin, 900 ms. **Never sad, never annoyed.**
- Keyboard: the pet's button is focusable; Enter = tap, Space held 600 ms = petting.

**Walking:** on screens ≥ 768 px wide, after 20 s idle (and at most once per 45 s), the
pet walks along the **top edge** of a glass panel marked `data-pet-perch` at 60 px/s
and **sits on the card edge** (legs dangling, 1 s settle). It never walks over an element
with `data-pet-avoid`, a focused element, or any form. Below 768 px it stays in its corner
slot (96×96 px, bottom-right, 16 px inset).

**Sleep mode:** inside the bedtime window (default 22:00–06:30 local, in `petConfig.ts`):
yawn → curl up (1200 ms) → dim (opacity 0.85) → slow "z" every 2.5 s, rising 24 px and
fading over 2 s. At the window's end: stretch (1800 ms) → awake. A tap on a sleeping pet:
slow blink and stretch, then back to sleep after 30 s if still in the window.

**Breathing buddy (optional):** a "Breathe with me" button in the pet controls. It paces
4 s in / 6 s out with `--breathe`, for at most 10 cycles. The label reads "Relaxation
exercise. Not a medical tool." It stops at once if `safetyActive` becomes true.

**Mood source:** only engagement (taps, petting, app opens, a check-in completed) and
`timeOfDay`. **Never** engine status, scores, vitals or survey answers.
Moods: `neutral`, `happy`, `calm`, `playful`, `sleepy`, `sleeping`, `petting`.

**Streaks:** a broken streak changes nothing visible and triggers no line. Accessories
unlock from `nightsLogged` (a lifetime total that never decreases) at 3, 7, 14 and 30
nights: scarf, star clip, moon pin, flower crown. Once earned, they are kept forever.

## 3. Frost trail (signature feature)

Glass surfaces carry a faint frost layer. Where the pet walks, it clears a soft trail; the
frost re-forms **from the trail edges inward** over T seconds (default 30, range 20–40,
in `petConfig.ts`).

Implementation (follow exactly):

1. One `<canvas>` overlay per pet stage, `position:absolute; inset:0; pointer-events:none`.
2. Backing store at **0.5×** CSS size × `min(devicePixelRatio, 2)`.
3. Pre-render a frost **texture tile** (256×256 offscreen canvas) once: fill `--frost-tint`
   at alpha 0.55 (never higher), add fine noise (≈ 3% of pixels, white, alpha 0–0.08),
   draw 40 crystal strokes (white, alpha 0.25, 1–3 short branches each) from a **seeded**
   PRNG (mulberry32, seed 7) so it looks the same every load.
4. Trail = **ring buffer** of `{x, y, born}` points, cap **300**. Add a point only when the
   pet moved ≥ 6 CSS px since the last one.
5. Each frame, **only while the buffer is non-empty**: draw the texture as a pattern over
   the whole canvas, then with `globalCompositeOperation = "destination-out"` stamp a
   soft radial brush per point with radius `r0 · (1 − age/T)` (r0 = 28 CSS px) and alpha
   `1 − age/T`. Drop points with `age ≥ T`. Redrawing the texture every frame means no
   alpha builds up over time.
6. Stop `requestAnimationFrame` when the buffer is empty or `document.hidden` is true;
   restart on the next point or `visibilitychange`.
7. `prefers-reduced-motion: reduce` → no canvas trail; the frost layer just fades
   out and back in with a 600 ms CSS opacity transition when the pet passes.
8. Frost sits **below text** (z-order) or only on decorative pet-stage surfaces. With
   tint alpha ≤ 0.55, measured contrast at full frost stays AA: text 13.1:1, muted
   4.94:1, teal-ink 6.3:1, status inks ≥ 5.8:1. Do not raise the alpha.

## 4. Dialog cache (offline, static, no AI at runtime)

`src/pet/dialog/cache.json` = events × tones × lines (schema: `dialog/schema.json`).
Line = `{ id, text, tod: "morning"|"day"|"evening"|"night"|"any", weight }`.

Events: `first_run, app_open, welcome_back, quiz_start, quiz_complete, bedtime_near,
sleep_start, wake, night_logged, streak_milestone, idle_long, pet_tap, goodbye`.
Tones (3): `warm`, `quiet`, `bright` (see `personas.json`).

- ≥ 6 lines per event per tone; ≥ 10 for `quiz_complete`, `bedtime_near`, `sleep_start`, `wake`.
- ≤ 90 characters. Optional `{petName}` placeholder. Ids unique, format `<event>.<tone>.<nn>`.
- `picker.ts`: filter by `tod` (or `any`), skip the last 8 shown ids (stored in
  `localStorage` key `pet.dialog.recent`, every access in try/catch), weighted random,
  per-event cooldown (`petConfig.ts`), never show while a form field has focus, respect
  persisted mute (`pet.dialog.muted`) and snooze (`pet.dialog.snoozeUntil`, epoch ms).
- `lint_dialog.mjs` (provided in `playground/scripts/`): length, unique ids, coverage,
  banned terms; exits non-zero on failure. Your cache must pass it unchanged.

## 5. Safety (also in SAFETY.md; it wins any conflict)

`safetyActive === true` ⇒ the pet renders nothing, runs no timers, no trail, no dialog.
After a quiz the pet acknowledges completion and effort only. No medical or diagnostic
words, no "you should", no guilt about missed nights, no pressure about sleep. Never
reword engine advice. Art is `aria-hidden`; dialog uses `aria-live="polite"`; visible,
keyboard-reachable hide-pet and mute-dialog controls.

## 6. Budget

All of `src/pet/` (without tests) **< 80 KB gzipped** (checked by `npm run check`). No
raster images, no network calls, no external fonts. Only the tools in TOOLS.md plus plain
SVG, CSS and Canvas 2D.
