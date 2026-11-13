# PET_SPEC.md: Companion pet

Owner: Claude Code (art director). Codex implements and makes no design decisions.
It builds on coord/DESIGN.md: tokens (section 2), motion (section 7) and the Companion
slot (section 10). The pet is a small, friendly guide in the style of a Tamagotchi:
a round body, dot eyes, tiny reactions. It is **not** a care game. There is no hunger,
no health bar, no neglect and no death. It never measures, scores or judges the person.

## Assumptions
1. The reference folder is `imageref/`. The terminal-pet / desktop-pet style repos were taken as a style cue (tiny body, dot eyes, idle loops) and not fetched; no code or art is copied.
2. The pet reads only `GET /api/v1/today` → `context_engine` (the latest **non-crisis** engine output; see coord/API_CONTRACT.md), so it never sees crisis output.
3. "Signs of real distress" = `mental_level >= 2` or `clinical_floor_breached == true`, or the safety screen is open. In those cases the pet goes quiet, and the app (not the pet) shows support resources.
4. Mood cut-offs reuse the engine's own levels and its 50 midpoint and 65 level-1 index cut-off. They are not new clinical thresholds. They live in `moodConfig.ts` marked PLACEHOLDER, and a TUNING.md entry is requested.
5. Preferences (visible, character, muted) are per-device, stored in `localStorage` with try/catch. Defaults: visible, Nimbus, speech on.

## 0. References (one line each)
- Google Health phones: white cards, pastel metric tiles, small status pills, bottom tabs. Source of the calm-clinic tone.
- Happify.you: warm rounded illustration style and mood calendar. Source of the friendly-face warmth.
- Dark game radar: two overlaid trait polygons. Not used for the pet.
- Game body/cyberware screen: a glowing figure with labelled systems. Not used for the pet.
- Game trait wheel: five traits on an arc. Not used for the pet.
- Current dark Body map: five nodes on a silhouette. Not used for the pet.
- "20 ways" screenshot: no emoji, one radius, meaningful animation. Applied: the pet is CSS/SVG and moves only with purpose.
- Screen recording: UI-kit and agent-workflow reels. Not used for the pet.

## 1. Characters (choose one; pure CSS + inline SVG, tokens only, no images, fonts or libraries)

Every character fits a 72×72px box inside the 96px slot. Face parts are the same
elements for all three (two `.pet-eye`, one `.pet-mouth`, two `.pet-cheek`, optional
`.pet-brow` ×2), so the expressions in section 2 work on every character. Outlines are
2px `--text` at 85% opacity, which is above 3:1 on every token.

| id | Name | Personality | Shape |
|---|---|---|---|
| `nimbus` | Nimbus | A soft-spoken little cloud who is never in a hurry. | Body: a 64×48px `--mint` rounded rect (`border-radius: 24px`), plus three 28px `--mint` circles along the top edge (at x 8, 22, 34px; top −12px) forming cloud bumps, all with a 2px outline (wrapped in one inline SVG path so the outline is continuous). Feet: two 10×6px `--mint` ovals at the bottom, 14px apart. Face centered, eyes 18px apart, 20px from top. |
| `pip` | Pip | A cheerful sprout-egg who loves small wins. | Body: a 56×66px `--peach` egg (`border-radius: 50% 50% 46% 46% / 58% 58% 42% 42%`), 2px outline. Sprout: an SVG stem 2×10px `--teal` from the top center plus two 10×6px `--mint` leaf ellipses rotated ±30°. Cheeks use `--alert-soft` (peach on peach would vanish). Eyes 16px apart, 26px from top. |
| `lumi` | Lumi | A thoughtful moon-bun who listens more than talks. | Body: a 62×58px `--lavender` circle-ish blob (`border-radius: 50% 50% 44% 44%`), 2px outline. Ears: two 14×18px `--lavender` rounded triangles (SVG) on top at ±16px, tips at −10px. A 10px `--butter` five-point star (SVG) above the left ear. Eyes 18px apart, 24px from top. |

Shared parts: eyes and mouth are `--text`; cheeks are 9×6px ovals in `--peach` (Nimbus,
Lumi) or `--alert-soft` (Pip), placed 4px below and outside each eye. The arm (used for
waving) is one 10×14px body-color rounded nub on the right side, `transform-origin`
at its base.

## 2. Expressions (switched by `data-mood` on `.pet`)

All face parts read CSS variables. Each mood sets only variables, so moods never use
different DOM. Transitions between moods take 150ms on the variables' resulting
properties (none under reduced motion).

```css
.pet { /* neutral defaults */
  --eye-w: 6px; --eye-h: 8px; --eye-r: 50%; --eye-fill: var(--text);
  --eye-bt: 0px; --eye-bb: 0px; --eye-y: 0px; --eye-shine: 0;
  --mouth-w: 10px; --mouth-h: 5px; --mouth-r: 0 0 10px 10px;
  --mouth-fill: transparent; --mouth-bt: 0px; --mouth-bb: 2px; --mouth-b: 0px;
  --cheek-o: 0; --brow-o: 0; --brow-tilt: 0deg;
}
.pet-eye   { width: var(--eye-w); height: var(--eye-h); border-radius: var(--eye-r);
             background: var(--eye-fill); border-top: var(--eye-bt) solid var(--text);
             border-bottom: var(--eye-bb) solid var(--text); translate: 0 var(--eye-y); }
.pet-eye::after { /* 2px white shine, top-right */ opacity: var(--eye-shine); }
.pet-mouth { width: var(--mouth-w); height: var(--mouth-h); border-radius: var(--mouth-r);
             background: var(--mouth-fill); border: var(--mouth-b) solid var(--text);
             border-top: var(--mouth-bt) solid var(--text); border-bottom: var(--mouth-bb) solid var(--text); }
.pet-cheek { opacity: var(--cheek-o); }
.pet-brow  { width: 7px; height: 2px; background: var(--text); border-radius: 2px; opacity: var(--brow-o); }
.pet-brow.left  { rotate: var(--brow-tilt); }
.pet-brow.right { rotate: calc(var(--brow-tilt) * -1); }
```

| Mood | Eyes | Mouth | Cheeks | Variables set |
|---|---|---|---|---|
| neutral | Filled 6×8 ovals | Small smile: 10×5 with a 2px bottom border | Hidden | defaults |
| happy | Upward arcs "^": 10×6, transparent, 2px top border, rounded top | Open smile: 14×7, filled `--text`, radius 0 0 14px 14px | Shown | `--eye-w:10px; --eye-h:6px; --eye-r:10px 10px 0 0; --eye-fill:transparent; --eye-bt:2px; --mouth-w:14px; --mouth-h:7px; --mouth-r:0 0 14px 14px; --mouth-fill:var(--text); --mouth-bb:0px; --cheek-o:.9;` |
| calm | Relaxed closed arcs "u": 10×5, transparent, 2px bottom border | Soft smile 8×3 | Faint | `--eye-w:10px; --eye-h:5px; --eye-r:0 0 10px 10px; --eye-fill:transparent; --eye-bb:2px; --mouth-w:8px; --mouth-h:3px; --cheek-o:.5;` |
| encouraging | Bright filled 7×9 ovals with shine | Smile 12×6 | Medium | `--eye-w:7px; --eye-h:9px; --eye-shine:1; --mouth-w:12px; --mouth-h:6px; --cheek-o:.7;` |
| concerned | Filled 6×8, raised 1px, with worried brows (inner ends up, 12°) | Gentle flat line 8×2, top border (no deep frown) | Hidden | `--eye-y:-1px; --brow-o:1; --brow-tilt:-12deg; --mouth-w:8px; --mouth-h:2px; --mouth-r:2px; --mouth-bb:0px; --mouth-bt:2px;` |
| tired | Half-lidded: 8×4 lower half-ovals with a 2px top lid line | Small "o" 5×5 ring | Faint | `--eye-w:8px; --eye-h:4px; --eye-r:0 0 8px 8px; --eye-bt:2px; --eye-y:2px; --mouth-w:5px; --mouth-h:5px; --mouth-r:50%; --mouth-b:2px; --mouth-bb:2px; --cheek-o:.3;` |
| sleeping | Closed curves: 9×4, transparent, 2px bottom border | Tiny 4×2 line | Faint | `--eye-w:9px; --eye-h:4px; --eye-r:0 0 9px 9px; --eye-fill:transparent; --eye-bb:2px; --eye-y:2px; --mouth-w:4px; --mouth-h:2px; --mouth-r:2px; --cheek-o:.4;` plus `pet-zzz` |

Under `[data-mood="sleeping"]`, blinking stops and the speed of `pet-breathe` halves.

## 3. Animations

| Name | What it does | Duration / easing | Trigger |
|---|---|---|---|
| `pet-bob` | `translate: 0 0 → 0 -3px → 0 0` | 2.4s, `ease-in-out`, infinite | Always while idle (not while moving, hopping or sleeping) |
| `pet-blink` | Eyes `scale: 1 1 → 1 .1 → 1 1` | 160ms, `ease-in-out`, once | JS adds `.is-blinking` after a random delay of 3000–6000ms, removes it on `animationend`, then reschedules. Moods with arc eyes (happy, calm, sleeping) skip blinking |
| `pet-breathe` | Body `scale: 1 → 1.03 → 1` | Period = 60 / `respiration_bpm`, clamped to 2–10s; 4s when there is no reading; `ease-in-out`, infinite | Always. It is a gentle echo of last night's measured rate, not an instruction |
| `pet-hop` | 0% `scale(1.06,.94)` → 40% `translateY(-14px) scale(.96,1.04)` → 70% `translateY(0) scale(1.04,.96)` → 100% rest | 520ms, `cubic-bezier(.3,.7,.4,1)`, once | Perch on touch, happy events |
| `pet-wave` | Arm nub `rotate: 0 → -20deg → 14deg → -20deg → 0` | 900ms, `ease-in-out`, once | First appearance, return after being hidden, the `encouraging` mood starting |
| `pet-zzz` | Three "z" glyphs (inline SVG `<text>`, system font, `--muted`, 10/12/14px) move `translate(0,0)→(8px,-18px)` with `opacity 0→1→0` | 2.4s, `linear`, infinite, staggered 0 / .8 / 1.6s | `sleeping` only |
| `pet-bubble-pop` | Bubble `scale .6 → 1.05 → 1`, `opacity 0 → 1` | 220ms, `cubic-bezier(.2,.8,.2,1)`; exit is an opacity fade over 150ms | Every `say()` |

**Reduced motion** (`prefers-reduced-motion: reduce`): no bob, breathe, blink, zzz, hop
or wave. Expressions switch instantly, bubbles appear without scaling, the pet does not
follow the pointer and stays in the corner slot (static pose). The companion is the only
layer allowed looping motion besides the breathing orb (DESIGN.md section 10 exception).

## 4. Movement

The pet is `position: fixed` in the `#companion-slot` layer at `z-index: var(--z-companion)`.
It always has `pointer-events: none`, so it can never intercept a click or tap. It moves
with `transform: translate3d()` only.

**Fine pointer** (`(hover: hover) and (pointer: fine)`):
- **Follow with lag:** target = pointer + (56px, 40px), trailing below-right. Each
  animation frame, `pos += (target − pos) × 0.08`, with speed capped at 900px/s.
- **Dead zone:** while the pointer stays within 120px of the last target, the target
  doesn't update (no jitter while the person reads or clicks).
- **24px minimum gap:** the pet's box edge must stay at least 24px from the pointer. If
  the pointer closes in, push the pet directly away from the pointer by the shortfall.
- **Don't cover targets:** if the pet's box intersects the interactive element under the
  pointer (`closest('a,button,input,select,textarea,label,[role=button],[data-essential]')`)
  or any `[data-essential]` element, nudge it to the nearest free side (right, then
  below, then left, then above).
- **Perch when idle:** after 5s with no pointer movement or key press, move to the active
  card. That's the closest `[data-companion-perch]` ancestor of the last hovered or
  focused element, otherwise the perch-able card nearest the viewport center. Perch spot:
  sitting on the card's top edge, right side (`x = rect.right − 72 − 8`,
  `y = rect.top − 72 + 14`). If that spot is off-screen or overlaps `[data-essential]`,
  go to the corner slot instead.
- **Pointer leaves the window:** return to the corner slot.

**Touch / coarse pointer:** the pet sits in the corner slot. When the person taps a
`[data-companion-perch]` card, the pet hops (`pet-hop`, moving along a 400ms arc) to that
card's perch spot, stays 4s, then hops back. A second tap elsewhere retargets it.

**Always:**
- Clamp the pet inside the viewport with an 8px margin, the safe-area insets, and never
  over the tab bar.
- Hide the pet (`hidden`) whenever the safety screen, a modal or the sign-in screen is
  showing.
- Keyboard focus counts as activity: the pet perches by the focused card after 5s.

## 5. Mood mapping

Source: `today.context_engine` (output of `waiwai1/engine/api.py` `run()`). Fields used
(all exist in the engine output): `safety_status.crisis_override_triggered`,
`scores_and_metrics.phys_level` (0–3), `scores_and_metrics.mental_level` (0–2),
`scores_and_metrics.clinical_floor_breached`, `scores_and_metrics.night_quality_status`,
`scores_and_metrics.mental_indices.{fatigue_alertness, mood_wellbeing}` (0–100, 50 =
neutral, higher = more burden), and
`dashboard_visualization_data.dual_axis_timeline_point.respiration_bpm`.

Evaluate the rules top to bottom; the first match wins.

| # | Condition | Mood | Speech |
|---|---|---|---|
| 1 | Safety screen open, or any response with `crisis: true` this session, or `crisis_override_triggered` | **hidden** | none |
| 2 | `mental_level >= 2` or `clinical_floor_breached` (distress) | calm | **silent** (no bubbles). The app shows support resources directly (REQUEST in DECISIONS.md) |
| 3 | No `context_engine`, a 401/5xx response, or `night_quality_status == "NO_ESTIMATE"` | neutral | neutral lines |
| 4 | `phys_level >= 2` | concerned | concerned lines |
| 5 | `phys_level == 1` or `mental_level == 1` | encouraging | encouraging lines |
| 6 | `mental_indices.fatigue_alertness >= 65` (PLACEHOLDER: the engine's level-1 cut-off) | tired | tired lines |
| 7 | `mental_indices.mood_wellbeing < 50` (PLACEHOLDER: the engine's neutral midpoint) | happy | happy lines |
| 8 | Otherwise | calm | calm lines |

Overlays (they don't change the data mood, just show briefly and revert):
- No pointer, key or touch input for 120s → `sleeping` until the next input.
- A non-crisis check-in submitted → `happy` + `pet-hop` for 4s. This is skipped if rule 2 applies.

The mapping is a pure function `mapMood(contextEngine, flags) → Mood | "hidden"` with no
side effects. It never shows or passes on numbers.

## 6. Speech

**Tone:** warm, short, present tense, plain words. It reflects how things look relative
to the person's usual, and points to app screens and the support team. It never shows
numbers, scores, levels, quadrant names or clinical words.

**Hard rules:**
- It reflects a supportive reading, never a score or clinical label.
- No guilt, no streaks, no "I missed you", no "your pet is sad because you left".
- No medical, diagnostic or treatment advice, and no suggestion to change medication,
  sleep or exercise.
- The intro line (shown once per device): "Hi, I'm {name}, a friendly guide, not a therapist."
- Distress (rule 2) means silence: the app shows proper support resources itself.
- `say()` drops any text that has a digit or matches
  `/diagnos|depress|anxiety|disorder|crisis|suicid|score|streak|level|alert/i`.
- Bubble limits: at most 12 words, shown 5s, at most one bubble per 60s, none while a
  check-in question is open or a text input is focused. Speech is muted entirely when the
  person turns speech off.

| Mood | Lines (pick one at random, never the same twice in a row) |
|---|---|
| neutral | "Hi there. I'll keep you company today." · "No new readings yet. That's okay." · "Just hanging out in my corner." · "Your Today screen is ready whenever you are." · "I'm here if you want a look around." |
| happy | "Last night looked close to your usual. Nice." · "Thanks for checking in today!" · "Things look steady. Enjoy your day." · "Good to see you!" · "Your readings look settled today." |
| calm | "Steady and quiet. I like that." · "Nothing unusual stands out right now." · "Taking it easy with you." · "Everything looks close to your usual range." · "A calm one so far." |
| encouraging | "A few readings differ a little from usual." · "You're doing the right thing by looking." · "One step at a time." · "Your support team is there if something feels off." · "Want to glance at Sleep together?" |
| concerned | "Some readings are further from your usual." · "Your Today screen has the details." · "Worth a look with your support team." · "I'm staying close by." · "Take your time with this one." |
| tired | "Looks like a heavier day." · "Rest counts too." · "Feeling a bit sleepy myself." · "A slow pace is a fine pace." · "Quiet moments are allowed." |
| sleeping | "Zzz…" · "Mm… wake me anytime." · "Resting my eyes." · "Zzz… still here." · "Dreaming of soft clouds." |

## 7. Controls

- **Header quick toggle:** in the AppShell header (top right, never in the companion
  corner), a 44×44 icon button (inline SVG paw) with `aria-label` "Hide companion" /
  "Show companion" and `aria-pressed`.
- **Settings section "Companion":** a "Show companion" switch, a character picker (three
  radio cards showing each face in `neutral`, with name and one-line personality), and a
  "Speech bubbles" switch (mute). All are keyboard operable with visible focus.
- Preferences persist per device (Assumption 5). Hiding removes the pet and stops all of
  its timers and animation frames.
- The pet never covers essential controls: it has `pointer-events: none`, the
  `[data-essential]` avoidance from section 4, and DESIGN.md section 10 keeps controls out
  of the corner. Screen readers ignore the pet (`aria-hidden="true"`). Speech is mirrored
  to one polite live region only when speech is on.

## 8. File plan and public interface

All in `frontend/` (Codex):

| File | Purpose |
|---|---|
| `src/companion/companion.css` | Character shapes, mood variables, keyframes, reduced-motion overrides |
| `src/companion/characters.tsx` | `CHARACTERS` (id, name, personality) + `<CharacterBody id>` inline SVG |
| `src/companion/CompanionFace.tsx` | `<CompanionFace character mood />` (pure, static) |
| `src/companion/moodConfig.ts` | PLACEHOLDER cut-offs (65, 50), idle 5000ms, sleep 120000ms, bubble limits |
| `src/companion/moodMapping.ts` | `mapMood(contextEngine, flags)`, a pure function |
| `src/companion/speech.ts` | Line table, the `say()` guard regex, rate limiter |
| `src/companion/movement.ts` | Pure helpers: `lerpStep`, `inDeadZone`, `keepGap`, `perchSpot`, `clampToViewport`, `avoidEssential` |
| `src/companion/SpeechBubble.tsx` | Bubble UI (`--surface`, radius 16, `--shadow-2`, `--fs-small`, `--text`) |
| `src/companion/Companion.tsx` | Portals into `#companion-slot`; runs movement, blink and idle timers |
| `src/companion/CompanionProvider.tsx` | React context plus `window.companion` (dev/debug) |
| `src/companion/CompanionControls.tsx` | Header toggle + Settings section |
| `src/companion/*.test.ts` | Vitest tests for `moodMapping`, `speech` guard, `movement` |
| `src/pages/CompanionGallery.tsx` | Dev-only route `/dev/companion` (`import.meta.env.DEV`) |

Public interface (from `useCompanion()`, mirrored on `window.companion`):

```ts
type Mood = "neutral"|"happy"|"calm"|"encouraging"|"concerned"|"tired"|"sleeping";
type CharacterId = "nimbus"|"pip"|"lumi";
interface CompanionApi {
  setMood(name: Mood): void;          // manual override until the next data refresh
  say(text: string): boolean;         // false if muted, quiet (rule 2), rate-limited or blocked by the guard
  perchTo(elementId: string): void;   // perch on #elementId if visible and safe, else stay put
  setCharacter(id: CharacterId): void;
  show(): void; hide(): void;
  setMuted(muted: boolean): void;
  readonly state: { mood: Mood|"hidden"; character: CharacterId; visible: boolean; muted: boolean };
}
```
