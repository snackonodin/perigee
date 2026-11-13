# CODEX_FRONTEND_BRIEF.md: start here (Codex kickoff)

Owner: Claude Code (art director). Codex builds `frontend/` from this brief.
The companion pet is **ON HOLD**: build only the empty corner slot, nothing else of it.

## Paste this into Codex

```text
You are Codex, the frontend builder for Astronaut Vitals (NASA Space Apps 2026): a calm,
contactless health screening app for astronauts. It shows breathing and sleep sensed from
Wi-Fi, weekly mental check-ins, and what is unusual for this one person compared with
their own 28-night baseline. It is a screening and awareness tool, not a diagnostic.

Read, in this order and nothing else unless a task names it:
1. coord/CODEX_FRONTEND_BRIEF.md (this file): the vision
2. coord/DESIGN.md: tokens, components, motion, accessibility (the source of truth)
3. coord/FRONTEND_TASKS.md: the 4 build tasks, run in order 1 → 4, one per run
Do NOT read or build coord/PET_SPEC.md or coord/PET_CODEX_TASKS.md (on hold).

You may edit only frontend/. Never touch backend/, engine/, waiwai1/, tests/ or
frontend/src/safety/ logic. When DESIGN.md is unclear, pick the simplest option and log it
in bus/issues_for_claude.md (file, what was unclear, what you chose). Never invent health
data: missing data shows "No reading" with a reason.

Start with FRONTEND_TASKS.md Task 1. Stop after each task, run its browser checklist,
then run `bash bus/post_update.sh` if it exists.
```

## The app I imagine

**Feeling:** a bright morning clinic on a space station. Pale mint-white page, white
cards, soft pastel accents, rounded friendly type, generous space. Calm enough to open
at 3am after a bad night, and trustworthy enough that a flight surgeon would take it
seriously. Nothing blinks, nothing shouts, every number says "compared with your usual".

**Flow:** Sign-in (soft pastel fog) → **Today** (a breathing orb that gently pulses at
last night's measured rate, plus four vital cards: Breathing, Sleep, Mind, Heart
(experimental)) → **Sleep** (an arc from sleep onset to wake plus a 28-night bar
history) → **Check-in** (one big question at a time, a pastel mood-free calendar) →
**Body** (a light, friendly body map with five tappable systems). Bottom tabs on phones,
top tabs on desktop. The safety screen overrides everything, plain and white.

## References to use (and how)

### GitHub repos (approved; exact pins and limits in DESIGN.md 7.1)
| Repo | Use it for |
|---|---|
| greensock/GSAP (`gsap@3.15.0`) | Orb breathing, sleep-arc draw, pulse-trace slide, card entrance, all inside `gsap.matchMedia()` so reduced motion turns them off |
| darkroomengineering/lenis (`lenis@1.3.27`) | Gentle inertial page scroll on Sleep history and the Check-in calendar; one instance in AppShell, synced to GSAP's ticker |
| tengbao/vanta (`vanta@0.5.24` + `three@0.134.0`) | `VANTA.FOG` in mint/sky/lavender behind the sign-in form only, lazy-loaded |
| DavidHDev/react-bits (copy-in, MIT) | `AnimatedContent` / `FadeContent` for section and card entrances; copy into `frontend/src/vendor/react-bits/` with the license header |

### UI kits from the video (inspiration only, no new dependencies)
Watermelon UI, Cult UI and Skipper UI are Tailwind/shadcn-style kits. Do **not** install
them or add Tailwind. Borrow the ideas and rebuild them with our tokens:
- Watermelon UI: clean stat cards and tidy dashboard spacing → our vital cards and grid.
- Cult UI: components "with personality" → small friendly touches (icon discs, soft lift on hover, a satisfying selected answer state).
- Skipper UI: niche micro-interactions → one-off moments only: the orb, the tab pill sliding between tabs, and the check-in progress bar.
- Manus (AI site builder): not used.

### "20 ways to fix a vibe-coded app" checklist (from the video; apply all of it)
No purple gradients (no gradients at all) · real inline-SVG icons, never emoji · tab
title "Astronaut Vitals" + favicon · fewer cards, more room · not Inter (system rounded
stack) · one accent (teal) · the 8px spacing scale · one corner radius (16px; pills for
chips) · rewrite copy in plain, kind sentences · designed empty / loading / error states ·
a friendly 404 page · real error messages · animation only where it means something ·
build from the design system first. Before each task ends, self-audit against this list
and fix what fails (our own `/audit` pass).

### Agent-workflow video (how Codex works with the other agents)
- **Split folders:** Codex owns `frontend/` only.
- **One board:** report in `bus/`, and log problems in `bus/issues_for_claude.md`.
- **Tag the owner:** each note names the file, what failed and the exact command to
  reproduce, addressed to the agent who owns the fix.

### Image references (`imageref/`)
| Image | Take |
|---|---|
| Google Health phones | White cards on a pale page, big number + sparkline + status pill per card, bottom tabs |
| Happify.you | Warmth, rounded type, one question per screen, pastel calendar day pills |
| Game radar | Two overlaid shapes (now vs your usual) for trait comparison, redrawn light |
| Game body / cyberware screen | Body figure with labelled systems and a detail panel on select, redrawn light and friendly |
| Game trait wheel | Traits on an arc with a clear number each, redrawn light |
| Our current dark Body map | Keep the five nodes and layout; drop the dark HUD look |

Copy structure and ideas only, never logos, art, characters or branding.

### UI effects wanted (all disabled under reduced motion; none on the safety screen)
Breathing orb pulse at the measured rate · sleep arc draw-in · pulse trace sliding in
new samples · cards fading/rising in on first view · tab indicator pill sliding · status
chip crossfade · soft card lift on hover · gentle inertial scroll · pastel fog on sign-in.
Not wanted: count-up numbers, glitch or shiny text, cursor effects, parallax, looping
attention-grabbers, or any effect that makes a reading look more alarming.

## Hard rules (repeat of DESIGN.md, non-negotiable)
- Contrast at least 4.5:1, using only the token pairs DESIGN.md allows; status = word + icon + color.
- Respect `prefers-reduced-motion`; keyboard reachable everywhere; 44px targets; no horizontal scroll at 320px.
- The safety screen's logic and text are untouchable; it sits above everything.
- Keep the bottom-right companion corner free of controls (DESIGN.md 10).
