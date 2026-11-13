# FRONTEND_V3: bugs, proportions, and the "Orbit Pop" look

Owner of `frontend/`: **claude-fe** (the Claude Code session that replaced Codex, tmux pane
`astro-app-97`). Coordinator: **claude** (this repo's main session). Tests: **opencode**.
Written 2026-11-14 from a live screenshot audit: `coord/ui-audit/before/*.png` (1440 and 390 wide).
Re-shoot any time: see "Screenshots" at the end.

Rules that still hold (do not break them for looks): DESIGN.md §8 accessibility, §11 safety
screen (solid, no glass, no animation, z 1000), §13 glass fallbacks, no diagnosis words, no
numbers counting up, flags before values on Monitor, pet slot bottom-right kept clear.

---

## P0: bugs (fix first, one commit each)

| # | Where | What is wrong (seen in the audit) | Fix |
|---|---|---|---|
| B1 | `/persona` | The trait circles render as raw black SVG blobs; labels overlap ("OpennessNot supplied"); the page has **no stylesheet** | Give Persona its own CSS (or restyle the component): trait arc/wheel per §5 below, labels never overlap, "Not supplied" as a muted chip |
| B2 | All pages | The pastel aurora is `position:absolute` / viewport-tall: below 900 px the backdrop stops and a flat band shows (Today, Sleep, Check-in, Setup) | Backdrop `position:fixed; inset:0; z-index:-1`, one layer for the whole app |
| B3 | `/monitor` | The tab bar highlights **Today** while you are on Monitor | Active state from the route; Monitor and Settings are header links, so no tab is active there |
| B4 | Mobile header | At 390 px only "Log out" shows; **Monitor and Settings are unreachable** | Put Monitor + Settings in the header as icon buttons (44 px), or in an overflow menu |
| B5 | Icons | Briefing, Consent and Settings all use the same sparkle "✧"; tab icons are text glyphs | One consistent inline-SVG icon set (1.75 px stroke, 24 px box), distinct per destination |
| B6 | `/setup` step 1 | Checkbox sits **above** its label; labels are raw keys title-cased ("Checkins", "Raw Csi") | Switch rows: label + one-line help left, switch right; human labels ("Daily check-ins", "Raw sensor recordings") |
| B7 | `/checkin` | Instrument names show diagnostic wording ("Generalized Anxiety Disorder-2", "Patient Health Questionnaire-9") | Friendly display names in the UI ("Two quick worry questions", "Mood, nine questions", "Wellbeing, five questions"); keep the official id in a small muted line only on the detail sheet |
| B8 | Today, Body | Same fact repeated 3× in one card (big "No reading" + chip "No reading" + "No reading") and empty hairlines under Breathing | One empty state per card: icon + one sentence + (optional) one action |
| B9 | `/body` | "Respiration" heading twice; labels far from their dots (Rest, Cabin on a foot); figure is small | Wait for the new body art (OpenCode, below); meanwhile one heading, leader lines that connect label to dot |
| B10 | `/login` | Verify after the server fix (`a9823fa`): deep links now return the app | Re-shoot `/login`, `/register`, `/setup` |

## P1: proportions (what reads "off")

1. **One page grid.** Max width 1200 px, 12 columns, 24 px gutters; side padding 16 px (phone) /
   32 px (tablet) / 48 px (desktop). Today the column is ~985 px with large dead margins.
2. **One page header pattern.** Eyebrow (12 px mono caps) → title → one-line lead, left
   aligned. Optional right slot for one chip. No icon floating far left with the title centered
   (Check-in and Persona do this now).
3. **Type scale (fixed steps, no in-between sizes):** display 56/60, h1 40/44, h2 28/32,
   h3 20/26, body 16/24, small 14/20, micro 12/16 mono caps. "No reading" is **body**, never h1.
4. **Numbers are the heroes:** metric values 48–72 px tabular numerals with the unit at 40 %
   size beside them. Labels are small.
5. **Cards by content, not equal boxes.** Use a bento grid (below); a card is as tall as its
   content; no card taller than its content by more than 24 px.
6. **Spacing steps only:** 4, 8, 12, 16, 24, 32, 48, 64. Card padding 24 (20 on phone).
7. **Hero orb on Today** must stay inside its card (now it bleeds left) and shrink to 160 px on phone.
8. **Buttons:** one primary per view. Monitor's three equal green pills become three
   selectable tiles (icon, title, duration, one line) with one Start button.

---

## P2: the new look, "Orbit Pop" (funky, modern, still calm)

A space crew app: mission-console precision + soft pastel glass + a little play. Not a
generic health dashboard.

**Signature elements**
- **Orbit motif:** thin concentric rings and a small moving "satellite" dot as the visual
  language: around the breathing orb, behind page titles (very faint), as progress rings
  (calibration, session timer), as the active-tab indicator.
- **Mission telemetry microcopy:** eyebrows and metadata in a monospaced, uppercase, tracked
  style (`MET 03:21:09`, `STATION TIME UTC+00:00`, `NIGHT 14 / 28`). Body copy stays friendly.
- **Bento layout:** Today = a bento grid (one 2×2 hero tile, mixed 1×1 and 2×1 tiles), not a
  vertical stack of equal cards.
- **Pop accents:** keep the mint/sky/lavender/peach pastels; add ONE saturated accent,
  **Ultraviolet `#5B4BDB`** (measured 6.0:1 on white and 5.8:1 on `--bg`; white text on it 6.0:1; as text it fails on lavender 4.1:1 and sky 4.4:1, so never text on pastel fills), for focus moments only: the active
  tab pill, primary buttons on Monitor, the orbit dot. Teal stays for links/success ink.
- **Grain + glow:** a 3 % noise overlay on the backdrop (CSS, SVG `feTurbulence` data-URI) and a
  soft colored glow under the hero tile. No neon, no dark mode for now.
- **Type:** bundle two variable fonts offline: **Space Grotesk** (display, numbers) and
  **JetBrains Mono** (telemetry microcopy) via `@fontsource-variable/*`; body stays the system
  rounded stack. Pin exact versions; say why in the commit (offline app, no CDN).

**Meaningful motion catalog (each has a reason; all off under reduced motion)**

| Motion | Where | Why it means something | Tool |
|---|---|---|---|
| Breathing orb paced at the person's **own** median rate (inhale/exhale) | Today hero | Shows the measured rhythm, not decoration | GSAP timeline (`gsap.matchMedia` for reduced motion) |
| Sleep arc draws onset → wake once | Sleep | Reads as the night passing | GSAP / CSS `stroke-dashoffset` |
| Calibration + session **progress ring** with orbiting dot | Monitor | Shows time left; the dot is the satellite motif | CSS conic-gradient + rAF |
| Session status as a **"dynamic island" pill** that morphs Connecting → Calibrating → Running → Done | Monitor header | State change is the information | Cult UI idea (rebuilt in CSS), `@property` width/radius |
| **Sliding active-tab pill** (shared layout) | Tab bar | Where you are and where you went | Skipper UI idea, FLIP in ~30 lines |
| Cursor **spotlight** + sheen on glass tiles (desktop only) | Bento tiles | Invites tapping a tile | react-bits `SpotlightCard` (copy-in, MIT header kept) + Cult sheen |
| Staggered tile **enter** (40 ms steps, 8 px rise) | Every page, first view | Groups content | react-bits `AnimatedContent` or GSAP stagger |
| Title **split-reveal** (words, 250 ms) | Page titles | Calm, one-time | react-bits `SplitText` (copy-in) |
| Body map **pulse ring** on the selected system | Body | Ties the panel to the figure | CSS keyframes |
| Inertial scroll | Long pages | Feel | Lenis (already in AppShell) |
| Fog backdrop | Login/Register only | Arrival moment | Vanta FOG (already in Login) |

Never animated: numbers (no count-up), status chips, the safety screen, anything while a form
field has focus.

**UI tips to apply everywhere**
- Empty states teach: icon + one sentence of what will appear + when ("after your first full
  night near the sensor"). One per card.
- Skeletons match the final layout (no spinners in cards).
- Chips are words + icon, never color alone.
- Every tile has one clear tap target; the whole tile is the button.
- Hover/press: lift 2 px + shadow step + 150 ms; press scales 0.98.

---

## Body pane art (OpenCode is generating it)

OpenCode delivers to `frontend/src/assets/body/`: `astronaut-front.webp` (1024×1536,
transparent), `astronaut-front@0.5x.webp`, `astronaut-front.svg` if vector is possible, and
`anchors.json` with the five hotspot positions as fractions of the image (Mind, Respiration,
Rest, Autonomic, Cabin). Build the Body map so hotspots read `anchors.json`; until the art
lands, keep the current SVG and fix B9.

---

## Work order and speed

1. claude-fe: B1–B10 (small commits), then P1 grid/header/type tokens in `tokens.css` +
   `shell.css`, then Orbit Pop per page: Today → Monitor → Sleep → Body → Check-in → Persona →
   Settings/Login.
2. Use parallel subagents only for independent pages, each in its own files; one owner for
   `tokens.css`/`shell.css` at a time.
3. After each page: `npm run build`, `npx vitest run`, re-shoot that page (390 + 1440),
   commit by path, `bash bus/post_update.sh claude-fe`.
4. Tests that break because the DOM changed: update them in the same commit if the change is
   only markup/classes; never weaken safety or a11y assertions. Ask opencode for anything
   bigger.

## Talking to each other

- Feed: `bash coord/say.sh claude-fe claude "..."` and read `coord/FEED.md`.
- Blockers: append to `bus/issues_for_claude.md` and post `blocked: ...` on the feed.
- Direct: the coordinator also messages the claude-fe session directly.

## Screenshots

The app must be running (`python run_app.py`, port 8765). Get a token for a review account,
then:
```
node coord/ui-audit/shots.mjs coord/ui-audit/after <access> <refresh> 1440 900 / /sleep /body /monitor
node coord/ui-audit/shots.mjs coord/ui-audit/after <access> <refresh> 390 844 / /body /monitor
```
The script marks setup as done for the review account. Review accounts use
`@example.invalid` emails; delete them with `DELETE /api/v1/me` when finished.
