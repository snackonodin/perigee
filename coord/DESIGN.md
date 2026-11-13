# DESIGN.md: Astronaut Vitals, light pastel theme

Owner: Claude Code (art director). Codex implements and makes no design decisions.
If something here is ambiguous, pick the simplest option and log it in
`bus/issues_for_claude.md` (file, what was unclear, what you chose).

This theme **replaces the old dark space theme completely**: no navy backgrounds,
starfields, neon glows, holographic grids or spacecraft art. The feeling we want is a
calm, trustworthy, happy clinic in daylight. The app is a screening and awareness
tool, not a diagnostic. Visuals must never make a reading look more certain or more
alarming than it is.

## 1. References (structure only, never copy branding or art)

| Reference | Take | Leave |
|---|---|---|
| Google Health phones (`imageref/Screenshot 2026-11-12 at 11.58.17 PM.png`) | Pastel metric tiles, big number + small label, sparkline per card, small status pill ("Good", "In range", "Goal not met"), bottom tab bar, white cards on a pale tinted page | Product name, Google icons, step/workout features |
| Happify.you (`…11.58.27 PM.png`) | Warm soft palette, friendly rounded type, one question per screen, mood calendar with pastel day pills, generous whitespace | Purple full-bleed panels, illustrated people, "choose your problem" framing |
| Game radar (`…11.58.54 PM.png`) | Two overlaid polygons (current vs baseline) for comparing traits | Dark navy, game stat labels |
| Game body/cyberware screen (`…11.59.02 PM.png`) | Body figure with labelled systems and a detail panel on select | Red/black palette, inventory slots, all game art |
| Game trait wheel (`…11.59.10 PM.png`) | Traits arranged on an arc with a big number per trait | Grunge texture, dark mood, game fonts |
| Our current Body map (`…13 at 1.11.06 AM.png`) | The node layout (Mind, Rest, Respiration, Autonomic, Cabin) and "Personal baseline · 28N" framing | Dark grid, glow, monospace HUD caps |
| "20 ways" checklist (`…13 at 6.39.02 PM.png`) | No purple gradients, real icons not emoji, tab title + favicon, one accent, spacing scale, one radius, not Inter, designed empty/loading/error states | — |

## 2. Color tokens

Put these exactly in `frontend/src/theme/tokens.css` under `:root`. Delete every
dark-theme token. No other hex values may appear in component CSS.

```css
:root {
  /* surfaces */
  --bg: #F7FBF9;        /* page */
  --surface: #FFFFFF;   /* cards, sheets, tab bar */
  --line: #E3ECE8;      /* hairlines, card borders, chart grid */

  /* pastel fills (card and chip backgrounds only, never text) */
  --mint: #BFE9D6;
  --sky: #BFE0F5;
  --peach: #FFD9C7;
  --lavender: #D9D0F5;
  --butter: #FFF1B8;
  --alert-soft: #FBD5DA;

  /* ink */
  --text: #1F2A37;
  --muted: #5B6B7A;
  --teal: #1E7F6E;      /* the ONE accent: links, primary button, focus ring, selected tab */

  /* status: raw hues for fills, strokes and icons */
  --ok: #2E9E78;
  --warn: #C98A1B;
  --alert: #D1495B;
  /* status ink: the only status colors allowed for text */
  --ok-ink: #1D6B50;
  --warn-ink: #7A4E00;
  --alert-ink: #A3283A;

  /* companion palette (Codex reported these missing; aliases only, no new hues) */
  --pet-nimbus: var(--mint);
  --pet-pip: var(--peach);
  --pet-lumi: var(--lavender);
  --pet-star: var(--butter);
  --pet-ink: var(--text);
  --pet-outline: rgba(31, 42, 55, .85);   /* --text at 85% */
  --pet-cheek: var(--peach);
  --pet-cheek-on-peach: var(--alert-soft);
  --pet-bubble: var(--surface);
}
```

### Contrast rules (measured, WCAG 2.1)

- `--text` passes on every surface and pastel (9.9 to 14.5:1). Use it for all body text and numbers.
- `--muted` (5.3:1 on bg, 5.5:1 on surface, 4.8:1 on butter) **may only sit on `--bg`, `--surface` or `--butter`**. On mint, sky, peach or lavender it fails (3.7 to 4.2:1), so use `--text` there.
- `--teal` text only on `--bg`/`--surface` (4.7/4.9:1). On pastels it is for icons and strokes only.
- `--ok`, `--warn`, `--alert` are **never used for text**: `--warn` is 2.8:1 and `--ok` 3.2:1. Status text uses the `-ink` tokens, which pass 4.4:1 or better on every fill. Only lavender + ok-ink is 4.37:1, so never put status text on lavender.
- Non-text graphics (chart lines, icons, meter bars) need at least 3:1 against their background. `--warn` fails that, so warn strokes and icons use `--warn-ink`.
- Body text must reach at least 4.5:1 everywhere. Do not lower opacity on text to make it lighter; use `--muted` instead.

### Pastel role map (fixed, so color carries meaning consistently)

| Pastel | Used for |
|---|---|
| mint | Breathing / respiration, and the "Normal" status fill |
| sky | Sleep and rest |
| lavender | Mind / check-ins / persona |
| peach | Heart (experimental estimate) |
| butter | "Watch" status fill, gentle notices, demo/mock banners |
| alert-soft | "Alert" status fill only |

No gradients anywhere, including on charts, buttons or backgrounds. Flat pastel fills only.

## 3. Typography

- Font stack (system, no web-font download; the app must work offline):
  `font-family: ui-rounded, "SF Pro Rounded", "Nunito", "Segoe UI", system-ui, sans-serif;`
  Do not use Inter or any monospace font for UI text.
- All numbers use `font-variant-numeric: tabular-nums;`.
- Sentence case everywhere. No ALL-CAPS labels, no letter-spaced HUD text.

| Token | Size / line-height | Weight | Use |
|---|---|---|---|
| `--fs-display` | 48 / 56 | 700 | Single hero number (e.g. breaths/min on Today) |
| `--fs-h1` | 32 / 40 | 700 | Screen title |
| `--fs-h2` | 24 / 32 | 600 | Section title |
| `--fs-metric` | 28 / 34 | 700 | Number inside a vital card |
| `--fs-h3` | 20 / 28 | 600 | Card title |
| `--fs-body` | 16 / 24 | 400 | Body copy, minimum for paragraphs |
| `--fs-small` | 14 / 20 | 400 | Labels, chips, captions |
| `--fs-tiny` | 12 / 16 | 600 | Chart axis ticks only, never sentences |

Units next to numbers (`br/min`, `bpm`, `h`) use `--fs-small`, `--muted`, 4px gap.

## 4. Spacing, radius, elevation

- **8px scale:** `--s-1: 4px` (icon-to-text gaps only), `--s-2: 8px`, `--s-3: 16px`, `--s-4: 24px`, `--s-5: 32px`, `--s-6: 48px`, `--s-7: 64px`. No other margin or padding values.
- Card padding 16px on phones and 24px at 768px and wider. Gap between cards 16px. Screen side gutter 16px on phones and 32px on wide screens.
- **One radius:** `--radius: 16px` for every container (cards, sheets, inputs, tiles). The only exception is `--radius-pill: 999px` for chips, buttons and tab indicators. Nothing else.
- Shadows (soft, warm-neutral, never dark):
  - `--shadow-1: 0 1px 2px rgba(31,42,55,.04), 0 2px 8px rgba(31,42,55,.05);` for resting cards
  - `--shadow-2: 0 4px 16px rgba(31,42,55,.08);` for hover/press-lifted cards, sheets and popovers
  - Cards also get `border: 1px solid var(--line)` so they stay visible when shadows are faint.
- Layout: single column under 768px; 2-column card grid at 768px and up; max content width 1120px. Never horizontally scroll the page.
- Touch targets are at least 44×44px.

## 5. Status language

The app has exactly three levels, matching the engine's Normal / Watch / Alert.

| Level | Word shown | Icon (inline SVG, no emoji) | Chip fill | Chip text and icon |
|---|---|---|---|---|
| normal | "Normal" | check in a circle | `--mint` | `--ok-ink` |
| watch | "Watch" | eye | `--butter` | `--warn-ink` |
| alert | "Alert" | triangle with "!" | `--alert-soft` | `--alert-ink` |
| none | "No reading" | dash in a circle | `--surface` + `--line` border | `--muted` |

- **Never color alone:** every status shows the word and the icon; color is the third cue.
- Copy is relative to the person's own baseline: "Above your usual range", never "abnormal", "danger", or any diagnosis word.
- Missing data shows "No reading" with a reason. Never show 0, never invent a value, and never keep a stale number without its date.

## 6. Components

All components accept `state: "normal" | "watch" | "alert" | "none"` where relevant
and get it from API data only. Never compute status in the frontend.

### 6.1 Status chip
- A pill (`--radius-pill`) with 4px 12px padding, `--fs-small` 600 text, 16px icon, 4px gap. Height 28px; when the chip is tappable, its hit area is at least 44px.
- Colors per the table in section 5. `role="status"` is not needed on static chips. When a chip's level changes live, the change is announced through one shared `aria-live="polite"` region, not per chip.
- Motion: when the level changes, crossfade fill and text over 250ms. No bounce, pulse or blink at any level, including alert.

### 6.2 Vital card
- Layout: `--surface` card, radius 16, `--shadow-1`, 1px `--line` border, and a 40px pastel icon disc (role color from section 2) in the top-left.
- Content top to bottom: label (`--fs-small`, `--muted`); big number (`--fs-metric`) + unit; 7-night sparkline (48px tall, 2px stroke in the role's darker ink, baseline band as a `--line` filled rect); a footer row with the status chip on the left and "vs your 28-night usual" (`--fs-small`, `--muted`) on the right.
- States:
  - normal: as above.
  - watch: card gets a 4px left inset bar in `--warn-ink` (via `box-shadow: inset 4px 0 0 var(--warn-ink)`); number stays `--text`.
  - alert: inset bar in `--alert-ink`, chip alert, and one plain-language line under the number, taken from the API advisory text when present.
  - none: number replaced by "No reading" (`--fs-h3`, `--muted`), sparkline hidden, reason line ("Sensor offline since 02:10").
  - loading: a skeleton block in `--line`, using shimmer only if motion is allowed.
  - experimental (heart rate): a "Experimental estimate" chip in `--surface`/`--line`/`--muted` next to the label, always visible.
- Whole card is a link when it leads somewhere. The focus ring is 3px `--teal`, offset 2px.

### 6.3 Breathing orb
- A 160px circle (120px under 360px wide) in `--mint`, with a 2px `--teal` ring at 40% opacity. The current rate sits centered in `--fs-display` with "br/min" below it.
- Motion: it scales 0.94 → 1.0 → 0.94 over one breath cycle, with period = 60 / measured breaths per minute, clamped to 2–10s. It uses `ease-in-out` and only `transform` (no layout animation). It is a **visualization of the measured rate**, not a guided breathing exercise; no "breathe in / out" text.
- States:
  - normal: mint fill.
  - watch: butter fill + 2px `--warn-ink` ring + watch chip under the orb.
  - alert: alert-soft fill + 2px `--alert-ink` ring + alert chip. The animation rate stays the measured rate and is never sped up for drama.
  - none: `--surface` fill, dashed `--line` ring, "No reading", no animation.
- Reduced motion: static circle at scale 1.0.

### 6.4 ECG trace (pulse trace)
- Name in UI: "Pulse trace". **Never label it ECG**: it is an experimental Wi-Fi estimate, and copy under it says "Experimental estimate, not a medical ECG."
- It renders only samples the API returns (live `/live/vitals` heart-rate series). It never synthesizes a PQRST waveform or fakes peaks. With no samples it shows the "none" state.
- Visual: 96px tall strip on `--surface` with faint `--line` gridlines every 8px vertically. The line is 2px `--text`; the latest point is a 6px `--peach` dot with a 1px `--text` outline.
- Motion: new samples enter from the right with a 250ms translate. Under reduced motion the strip redraws in place without sliding.
- States: normal/watch/alert change only the chip beside the trace and the latest-point dot outline (`--ok-ink` / `--warn-ink` / `--alert-ink`, 2px), never the line color. "none" shows a flat dashed `--line` and "No reading".

### 6.5 Sleep arc
- A half-circle arc (180°) from sensed onset (left) to wake (right), 12px stroke in `--sky` on a `--line` track, with round caps. Midsleep is a 10px `--surface` dot with a 2px `--teal` outline on the arc.
- The center shows presence hours (`--fs-metric`) and onset → wake times (`--fs-small`, `--muted`).
- Only data the API provides: presence hours, onset, midsleep, wake. **No sleep stages** (the API has none). The API has no coverage field, so draw the arc from onset to wake exactly as given and do not mark partial coverage (decision 2026-11-13; revisit only if the API adds coverage).
- States: the chip under the arc follows the API night status. watch/alert do not recolor the arc, only the chip and a one-line explanation.
- Motion: the arc draws from 0 to its value over 400ms on first view only. Reduced motion shows it instantly.

### 6.6 Signal-quality meter
- Four 6×16px bars, radius pill, 4px gap, followed by a word: "Strong" (4), "Good" (3), "Weak" (2), "Poor" (1), "No signal" (0).
- Filled bars are `--teal`; empty bars are `--line`. The word is `--fs-small` `--text`. The word is always shown (never bars alone).
- Shown only when the API supplies a quality or coverage value; map it with the thresholds the API or config gives. If no field exists, **hide the meter** and log it to `bus/issues_for_claude.md`. Do not derive quality in the frontend.
- Decision 2026-11-13: no meter cutoffs exist. `night.min_quality` in config.yaml is a night-validity gate, not meter bands. Keep the meter hidden on Body and the live tiles until the backend serves a quality category.
- No animation except a 150ms fill change.

### 6.7 Safety screen (existing; restyle only)
- Do **not** change its logic, trigger conditions, text source or acknowledgement gate.
- Visual: full-screen `--surface`; content max 560px centered; `--text` on white; one 40px lavender icon disc holding the existing read-only safety SVG (do not replace it; decision 2026-11-13); contact list as large 56px-high rows with `--teal` action text.
- No pastel decoration, no illustrations, no animation of any kind (it ignores motion tokens). Its focus moves to the heading on open, as today.

### 6.8 Tab bar and shell
- Bottom tab bar on phones (top tabs at 768px and up) on `--surface` with a top 1px `--line` border. Each tab has a line icon + label; the selected tab has `--teal` icon and label plus a pill indicator in `--mint`.
- Page background `--bg`. App title "Astronaut Vitals" in `--fs-h3`. The document `<title>` is "Astronaut Vitals", and the favicon is a simple teal circle with a white breath wave (SVG).
- Mock/demo data banners: `--butter` card with `--warn-ink` text "Showing sample data: live service unavailable".

## 7. Motion tokens

```css
:root {
  --dur-fast: 150ms;   /* hovers, meter fills */
  --dur-base: 250ms;   /* chip crossfade, card lift, tab change */
  --dur-slow: 400ms;   /* first-view chart draw */
  --ease: cubic-bezier(.2, .8, .2, 1);
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}
```

- Animate `transform` and `opacity` only.
- Nothing loops except the breathing orb (and that stops under reduced motion).
- Remove swipe-page transitions longer than `--dur-base`.

### 7.1 Motion libraries (lenis, gsap, vanta, react-bits)

**Revised 2026-11-13:** all core motion (breathing orb, pulse/ECG trace, sleep arc, card
and route transitions) is **plain CSS keyframes + SVG**, with no animation library.
`lenis` (scroll) and `vanta` (sign-in fog) stay approved as optional polish in the
Settings/login task. `gsap` and `react-bits` are reference only: rebuild their effects
in CSS. The table below applies only where a library is still used.

These four libraries are approved, **only for the uses below**. Pin the versions exactly in
`frontend/package.json` (npm, `--save-exact`). Anything not listed here stays plain CSS.
Every use must be disabled under `prefers-reduced-motion: reduce`, and none of them may
run on the safety screen.

| Library | Pin | Why it's added | Allowed use | Never |
|---|---|---|---|---|
| **gsap** (github.com/greensock/GSAP) | `gsap@3.15.0` | One timeline engine for the few non-CSS motions, with reliable reduced-motion handling through `gsap.matchMedia()` | Breathing orb cycle (6.3), sleep arc first draw (6.5), pulse-trace sample slide (6.4), card enter fades | Animating numbers that count up or tick (values appear instantly), ScrollTrigger pinning, any looping motion other than the orb |
| **lenis** (github.com/darkroomengineering/lenis) | `lenis@1.3.27` | Gentle inertial page scroll on long screens (Sleep history, Check-in calendar) | One Lenis instance created in `AppShell`, `lerp: 0.12`, and synced to GSAP's ticker | Running while the safety screen is open (call `lenis.stop()`), under reduced motion (don't create it), or inside scrollable inner panels, which keep native scroll |
| **vanta** (github.com/tengbao/vanta) | `vanta@0.5.24` + `three@0.134.0` | Vanta's last release (2022) targets three r134, so pin that exact three version | **Sign-in screen only:** `VANTA.FOG` behind the form with highlight `--mint`, midtone `--sky`, lowlight `--lavender`, base `--bg`, speed 0.6. Lazy-load it (`import()`) so three.js never ships in the main bundle | Any data screen (Today, Sleep, Check-in, Body, Persona) or the safety screen. If reduced motion is on or WebGL fails, show a flat `--bg` instead. Destroy the effect on unmount |
| **react-bits** (github.com/DavidHDev/react-bits) | Copy source, no npm package | It's a copy-in component collection (MIT), so we vendor only the pieces we use | Copy individual components from its "Animations" set (e.g. `AnimatedContent`, `FadeContent`) into `frontend/src/vendor/react-bits/`, keeping the MIT header and noting the source commit. Use them only for section/card entrance on non-safety screens, restyled with our tokens | Its WebGL/background, cursor, "glitch", "shiny", gradient or text-scramble effects; anything that pulls in a dependency besides `gsap`; animating any health value or status |

Notes:
- Each library adds weight. Check that `npm run build` output stays reasonable, and that
  three.js appears only in the lazy sign-in chunk.
- Remove the `@fontsource-variable/inter` dependency when Task 1 lands (section 3 bans Inter).

## 8. Accessibility rules (all mandatory)

1. Text contrast is at least 4.5:1, using only the pairs allowed in section 2. Large text (24px+, or 18.66px+ bold) still uses the same pairs.
2. Never color alone: status = word + icon + color, charts have labelled axes or direct value labels, calendar days show a marker shape as well as a fill.
3. Respect `prefers-reduced-motion` (section 7). The orb and traces become static.
4. Every interactive element is keyboard reachable in visual order and has a visible 3px `--teal` focus ring (`:focus-visible`).
5. Every chart has a text equivalent (`aria-label` summary or a visually hidden table) stating value, unit, date and status.
6. Every icon is inline SVG with `aria-hidden="true"` when next to a text label, otherwise it gets an `aria-label`. No emoji anywhere.
7. Touch targets are at least 44×44px. The layout works at 320px wide and at 200% zoom without horizontal scrolling.
8. The safety screen is never hidden behind loading states, tabs or animations.

## 9. Empty, loading and error states

- **Empty:** a pastel icon disc + one sentence explaining why + what will make data appear ("Readings appear after your first full night near the sensor.").
- **Loading:** skeleton blocks in `--line` at the final layout size, so nothing jumps. No spinners longer than 1s without text.
- **Error:** a `--surface` card with an `--alert-ink` icon, plain message, and a "Try again" button. A 401 sends the user to sign-in and is never shown as an error card.

## 10. Companion slot (reserved, not designed)

A future floating companion (pet) gets a reserved corner. This section reserves space
only; do not design or build the pet.

- **Area:** bottom-right corner, 96×96px (72×72px under 360px wide), inset 16px from the
  right edge and 16px above the bottom tab bar (or from the viewport bottom where there
  is no tab bar). Respect `env(safe-area-inset-right)` and `env(safe-area-inset-bottom)`.
- **Tokens** (add to `tokens.css`):
  ```css
  :root {
    --companion-size: 96px;
    --companion-inset: 16px;
    --z-base: 0;
    --z-sticky: 100;      /* tab bar, sticky headers */
    --z-companion: 500;   /* the future pet; above content, below everything modal */
    --z-popover: 700;
    --z-modal: 900;
    --z-safety: 1000;     /* safety screen always on top, including above the companion */
  }
  ```
- **Mount point:** `AppShell` renders an empty
  `<div id="companion-slot" aria-hidden="true">` fixed in that corner at `--z-companion`,
  with `pointer-events: none` until a companion exists.
- **Rule: no component may place essential controls in that corner.** Primary buttons,
  submit buttons, safety contacts, tab items, toasts and FABs must sit outside the
  reserved area. Scrollable pages add bottom padding of
  `calc(var(--companion-size) + var(--companion-inset))` so that the final content can
  scroll clear of it.
- The safety screen (`--z-safety`) and modals always cover the slot. The future
  companion must hide while the safety screen is open.
- **Motion exception:** the companion layer is the only place besides the breathing orb
  where looping idle motion (bob, breathe, zzz) is allowed. It stops under reduced motion.
  Full companion spec: coord/PET_SPEC.md, **superseded 2026-11-13 by `pet-handoff/`** (cat, fox,
  bunny; frost trail; offline dialog cache). The pet's mood comes only from engagement and time of
  day, **never** from engine levels, indices or survey results (this replaces PET_SPEC §5).

## 11. Safety screen (priority 1)

- **Trigger: `safety_screen_required === true` on ANY API response body, and nothing
  else.** Never key it off `safety.show`, local answer values or `crisis`. `api/client.ts`
  inspects every JSON response; one `true` locks the app.
- **Fail closed:** a `POST /api/v1/responses` for an instrument with a safety item that
  ends in a network error, a non-JSON body, or a body without a boolean
  `safety_screen_required` also locks the app.
- **Lock:** a full-screen view at `--z-safety`, rendered before any route content on
  every load. **The server is the source of truth:** on every app load the client calls
  `GET /api/v1/today`, whose top-level `safety_screen_required` and `missing_safety_item`
  drive the lock (they stay true until a later clean check-in clears them). A
  `sessionStorage` copy only covers the moment before `/today` answers, or when it is
  unreachable; it never clears a lock that the server reports. Routes, tabs, the back button and deep links all
  render the safety view while the lock is on. The dashboard is unreachable until the
  flag clears.
- **Clears only when the server says so:** `GET /api/v1/today` (or the re-submission
  response) returns `safety_screen_required: false`. There is no close button and no "skip". There is
  an "I've read this" acknowledgement, which only reveals the next step (the missing
  item, or "Return when you're ready"). It does not unlock.
- **Content, top to bottom:** heading "You're not alone", `safety.reason` **verbatim**,
  then `safety.resources` **verbatim** as large 56px rows (`tel:` links when a number
  is present), then the acknowledgement button. When `safety.reason` is empty, use the
  fixed fallback text already in `safety.ts`.
- **Missing item:** when `missing_safety_item` is present, after acknowledgement show
  exactly that one question (text and options from `GET /api/v1/instruments/{id}`), then
  re-submit the full, previously entered answers plus this item to `POST /responses`.
  The response decides whether the lock clears.
- **Look:** `--surface`, `--text`, a 560px column, one lavender icon disc. No
  animation, no pastel decoration, no pet, no Lenis. Focus goes to the heading on open;
  focus is trapped inside; `role="alertdialog"`, `aria-modal="true"`.
- Advisory text anywhere in the app (`context_engine.user_facing_advisory.*`,
  `/guidance` cards) is shown **verbatim**, never rewritten or summarized.

## 12. Page flow (mobile first; desktop at 768px+)

`/login` ↔ `/register` → `/setup` (first run only) → `/` nightly dashboard →
`/night/:date` night detail → `/weekly` weekly check-in + trends → `/settings`.
The safety lock (section 11) overrides every route. Tabs: Tonight · Weekly · Settings
(bottom bar on phones, top bar on desktop). Every page bottom-pads for the companion slot.

**Calibrating rule:** when `today.baselines[].n < 28` (or no baseline exists), every
comparison says **"Calibrating · {n} of 28 nights"** in a `--butter` chip (word + clock
icon). Status chips show "Calibrating" instead of Normal/Watch/Alert, sparklines draw
without the baseline band, and copy says "We're still learning your usual". Never show
z-scores.

| Screen | Mobile layout | Desktop | Components / data | Loading | Empty | Error |
|---|---|---|---|---|---|---|
| Login / Register | Single card centered on `--bg`; email, password, primary button; switch link | Two columns: card left, calm pastel panel right (Vanta fog optional, CSS fallback) | `POST /auth/login`, `/auth/signup`; field errors under inputs | Button spinner + "Signing in…" | — | Plain message from the API `message`, never "error 401" |
| Baseline setup `/setup` | 3 steps, one card each with a progress text "Step 2 of 3": (1) consents (`GET/PUT /me/consents`), (2) name + timezone (`PATCH /me`), (3) "Sleep near the sensor for 28 nights to build your baseline" + optional first weekly check-in | Same cards centered, max 560px | Consents, Stepper, CheckinForm | Skeleton card | — | Retry card |
| Nightly dashboard `/` | Breathing orb hero (last night `latest_night.rr_med`), calibrating/status chip, advisory headline **verbatim**, then cards: Breathing, Sleep (sleep arc), Mind (pending check-ins), Heart (experimental live estimate + pulse trace) | Orb + advisory left column, 2×2 card grid right | `GET /today`, `GET /live/vitals` | Skeleton orb + 4 card skeletons | "Your first night will appear here tomorrow morning." | Error card + retry; 401 → login |
| Night detail `/night/:date` | Back link; sleep arc; breathing vs your usual (rr_med vs baseline median ± MAD band); quality + valid chips; flags with "why" (FlagWhy) | Arc left, metrics right | `GET /nights/{day}`, `GET /flags` | Skeleton | "No reading for this night: {reason}" | Error card |
| Weekly / trends `/weekly` | Weekly check-in prompt card (if pending) → 28-night breathing trend (RrTrend) → presence bars → weekly indices (IndexCards: word + direction, no raw scores) → check-in calendar | Trend full width; indices and calendar side by side | `GET /nights?from&to`, `/indices`, `/checkins`, `/instruments` | Skeletons | "Trends appear after 3 nights." | Error card |
| Settings `/settings` | Sections: Profile, Consents, Data (export/delete via DataControls), Accessibility (reduce motion override), Companion (disabled "Coming soon"), Sign out | Two-column sections | `/me`, `/me/consents`, `/me/export`, `DELETE /me` | Skeleton rows | — | Inline error per section |

Existing pages not in this flow (Body, Persona, Live, CheckinCalendar standalone) stay
reachable from Weekly/Settings links and only receive the token restyle.

## 13. Glass layer (glassmorphism over the pastel theme), added 2026-11-13

The app keeps the light pastel theme and adds frosted-glass surfaces floating over a
soft pastel "aurora" backdrop. It should feel calm, airy and premium, like frosted
panels in a sunlit station module. It is not a neon or dark glass look. This section
overrides earlier rules where they conflict (it replaces the "no gradients" rule only
for the page backdrop).

### 13.1 Tokens (add to tokens.css)
```css
:root {
  --glass: rgba(255, 255, 255, .62);          /* cards, sheets, tab bar */
  --glass-strong: rgba(255, 255, 255, .78);   /* inputs, pulse trace, popovers, dense text */
  --glass-border: rgba(255, 255, 255, .75);
  --glass-edge: rgba(31, 42, 55, .08);        /* outer hairline so the edge is visible on light blobs */
  --glass-highlight: inset 0 1px 0 rgba(255, 255, 255, .9);
  --glass-shadow: 0 8px 32px rgba(31, 42, 55, .10);
  --glass-blur: blur(20px) saturate(140%);
  --teal-ink: #166457;                        /* teal TEXT on glass (6.1:1 worst case) */
}
```
Glass recipe (one utility class `.glass`, used everywhere):
`background: var(--glass); backdrop-filter: var(--glass-blur); -webkit-backdrop-filter: var(--glass-blur);
border: 1px solid var(--glass-border); box-shadow: var(--glass-highlight), 0 0 0 1px var(--glass-edge), var(--glass-shadow);
border-radius: var(--radius);`

### 13.2 Backdrop ("aurora")
- One fixed layer behind the app (`position: fixed; inset: 0; z-index: -1`) on `--bg`,
  with four large blurred blobs: mint (top-left, 60vmax), sky (top-right, 50vmax),
  lavender (bottom-left, 55vmax), peach (bottom-right, 40vmax). Each blob is a
  `radial-gradient(circle, color 0%, transparent 70%)` at 70% opacity. These are the only
  gradients allowed in the app. No purple-to-pink hero gradients, and no gradients on
  cards, buttons, charts or text.
- Motion: the blobs drift slowly (`aurora-drift`, translate ±4vmax, 40s, `ease-in-out`,
  infinite, alternate). They are static under reduced motion. The aurora is GPU-only
  (`transform`), never animating blur.
- **Sign-in only:** `VANTA.FOG` in mint/sky/lavender may replace the CSS aurora (DESIGN
  7.1), lazy-loaded, ≥768px, and not under reduced motion.

### 13.3 Contrast on glass (measured at --glass .62 over the strongest pastel blob)
- `--text` 12.6:1, `--muted` 4.8:1, `--ok-ink` 5.6:1, `--warn-ink` 6.3:1, and `--alert-ink` 6.2:1 all pass.
- `--teal` text is only 4.2:1 on glass, so it fails. **Teal text on glass uses `--teal-ink`.** `--teal` stays for icons, rings and strokes.
- Never use glass below .62 opacity under text. Body copy longer than 2 lines, inputs,
  the pulse trace and popovers use `--glass-strong`.
- **Fallbacks (mandatory):** `@supports not (backdrop-filter: blur(1px))`,
  `@media (prefers-reduced-transparency: reduce)` and `@media (prefers-contrast: more)`
  all switch `.glass` to solid `--surface` with a 1px `--line` border. The Settings
  "Reduce motion" switch also sets `data-reduce-transparency` to the same effect. That rule must sit
  **outside** the `@media` block (it is an app setting, not an OS preference) and cover every
  glass class, not only `.glass`.

### 13.4 Components on glass
| Component | Treatment |
|---|---|
| Vital card / section cards | `.glass`; pastel icon disc stays solid; on hover a 1px lift + `--shadow-2`, and a one-time light sheen sweeping across (a `linear-gradient` mask at 8% white, 600ms, once per hover; none under reduced motion) |
| Tab bar | Floating glass pill (radius-pill) 16px above the bottom edge on phones, a glass top bar on desktop; the selected tab indicator is a solid `--mint` pill that slides 250ms between tabs |
| Breathing orb | A solid mint orb inside a 200px glass ring (`.glass` circle) with a soft inner glow `inset 0 0 40px rgba(191,233,214,.8)`; it still breathes at the measured rate |
| Sleep arc | Arc on a `.glass` card; the track uses `--glass-edge`, the arc stays `--sky` |
| Pulse ("ECG") trace | On `--glass-strong` with faint gridlines; line `--text`; latest dot peach |
| Status / calibrating chips | **Solid fills** (mint / butter / alert-soft / surface), never glass, so status always reads clearly |
| Buttons | Primary: solid `--teal` with white text (4.9:1). Secondary: `.glass` with `--text` label. Never glass-on-glass for text |
| Inputs | `--glass-strong`, 1px `--glass-edge`; focus ring 3px `--teal` |
| Modals / popovers | `--glass-strong` + backdrop dim `rgba(31,42,55,.18)` |
| **Safety screen** | **No glass, no aurora, no blur, no motion.** Solid `--surface` full screen, exactly as in section 11 |
| Companion slot | Unchanged and reserved; not built |

### 13.5 UI from the shared references, mapped to glass
- **Google Health:** big-number + sparkline + pill cards, now as glass cards.
- **Happify:** warm, one question per glass card, pastel calendar pills (solid).
- **Radar / trait wheel / body screen:** drawn as thin `--text`/pastel lines on a glass panel; light, never dark.
- **Watermelon UI:** clean stat-card spacing.
- **Cult UI:** personality in hover lifts and sheen.
- **Skipper UI:** one-off micro-interactions (sliding tab pill, check-in progress fill, orb).
  These are rebuilt in CSS; nothing is installed.
- **Repos:** lenis for gentle scroll (optional); vanta for sign-in fog; gsap and react-bits
  as reference only, their entrance fades rebuilt as CSS `glass-in` (opacity 0→1 +
  translateY 8px→0, 250ms `--ease`, staggered 40ms, first view only).
- **"20 ways" checklist:** still applies. Real SVG icons, one accent, one radius, the
  spacing scale, designed empty/loading/error states, a friendly 404 (a glass card on
  the aurora).

### 13.6 Performance
Use at most about 12 blurred glass surfaces per screen (blur is expensive); long lists use
a single glass container, not glass per row. Test on a phone-width viewport for smooth
scroll.
