# FRONTEND_TASKS.md: ordered Codex prompts (v2, 2026-11-13; glass layer = DESIGN.md §13)

Owner: Claude Code (art director). Codex builds; Codex makes no design decisions.
This replaces the earlier v1 task list. Run the tasks **in order, one per Codex run**.
They share `frontend/src/theme/shell.css`; each task edits only its own selector prefix.

**Assumptions (art director):**
1. `backend/openapi.json` (exported 2026-11-13) is the contract. The safety lock reads only top-level `safety_screen_required`.
2. `GET /api/v1/today` now carries the server-driven `safety_screen_required` and `missing_safety_item`; `sessionStorage` is only a stopgap until `/today` answers.
3. "Calibrating" comes from `today.baselines[].n < 28`. There is no z-score anywhere in the UI.
4. All core motion is CSS + SVG (DESIGN.md 7.1 revised). Lenis/Vanta are optional polish in Task 6 only. The pet stays ON HOLD: its existing `src/companion/*` files are left untouched and unmounted.
5. First-run setup is detected per device (`localStorage` "setup.done", try/catch) or skipped when a baseline already exists.

Every task ends the same way: `cd frontend && npm test && npm run build` (both pass),
then `bash bus/post_update.sh` if it exists, otherwise append "post_update.sh missing" to
`bus/issues_for_claude.md`. Ambiguity → pick the simplest option and log it to
`bus/issues_for_claude.md` (file, what was unclear, what you chose). Never invent health
data. Never touch `backend/`, `engine/`, `waiwai1/`, `tests/` or `src/companion/`.
**Look for every task:** the glass layer in DESIGN.md §13. Cards, sheets and bars use
`.glass`; chips stay solid; teal text on glass uses `--teal-ink`; the safety screen is never glass.

---

## Task 1: Foundation + safety screen (priority 1)

```text
You are Codex. Read only coord/DESIGN.md, backend/openapi.json and these files.
Implement exactly; make no design decisions.

May edit: frontend/src/theme/tokens.css, frontend/src/theme/shell.css (foundation + .safety-),
frontend/index.html, frontend/package.json, frontend/package-lock.json,
frontend/scripts/gen-api.mjs, frontend/src/api/schema.d.ts, frontend/src/api/client.ts,
frontend/src/safety/SafetyProvider.tsx, frontend/src/safety/safety.ts,
frontend/src/safety/safety.test.tsx, frontend/src/components/AppShell.tsx, frontend/src/App.tsx
May create: frontend/public/favicon.svg, frontend/src/safety/SafetyScreen.tsx,
frontend/src/safety/MissingItemPrompt.tsx, frontend/src/safety/lock.ts
Read-only: frontend/src/api/types.ts, frontend/src/components/CheckinForm.tsx,
frontend/src/test/fixtures.ts, frontend/src/test/mockApi.ts

1. tokens.css = DESIGN.md sections 2 (including the companion palette aliases), 3, 4, 7,
   the 10 z-index tokens and the 13.1 glass tokens, exactly. Add the .glass utility, the
   aurora backdrop (13.2) and all 13.3 fallbacks (no backdrop-filter support,
   prefers-reduced-transparency, prefers-contrast: more → solid surface). Glass cards and
   the floating glass tab bar per 13.4. Delete every dark-theme token. shell.css: remove all
   dark/neon/grid/glow/gradient/monospace-HUD styles; set the page to var(--bg); cards,
   tabs and base type per DESIGN.md. npm uninstall @fontsource-variable/inter and remove
   its import. Title "Astronaut Vitals"; favicon per DESIGN.md 6.8.
2. Regenerate src/api/schema.d.ts from backend/openapi.json (point gen-api.mjs at that file).
3. Safety lock (DESIGN.md 11), the core of this task:
   - client.ts: after every response, if the JSON body has safety_screen_required === true,
     call lock.engage({safety, missing_safety_item}). For POST /api/v1/responses, a network
     error, non-JSON body, or missing boolean field also engages the lock (fail closed).
     NEVER read safety.show, crisis or local answer values to decide.
   - lock.ts: the server is the source of truth. On app load and after every check-in,
     GET /api/v1/today; its top-level safety_screen_required / missing_safety_item set or
     clear the lock. sessionStorage key "safety.lock" (try/catch, in-memory fallback)
     only bridges the moment before /today answers or while it is unreachable; it never
     clears a lock the server reports. API: engage(), syncFromToday(today), current().
   - SafetyProvider/App/AppShell: when locked, render <SafetyScreen> INSTEAD of any route,
     the tabs and the shell, on every load, including deep links and the back button.
   - SafetyScreen: role="alertdialog" aria-modal="true", focus to the heading "You're not
     alone", focus trapped. safety.reason VERBATIM, then safety.resources VERBATIM as 56px
     rows (tel: links when a number is present). No close or skip. An "I've read this"
     button reveals the next step only; it does not unlock. No animation, no pastel
     decoration. Use the fallback text in safety.ts when reason is empty.
   - MissingItemPrompt: if missing_safety_item is set, after acknowledgement show that one
     question (GET /api/v1/instruments/{id}), then POST /api/v1/responses with the
     previously entered answers (kept in memory by CheckinForm's submit via the lock
     payload) plus this item. The response decides: false clears the lock; true keeps it.
     Without a missing item, after acknowledgement show "Return when you're ready. This
     screen stays until your support team or a new check-in clears it."
   - AppShell: add the empty <div id="companion-slot" aria-hidden="true"> (DESIGN.md 10).
4. safety.test.tsx: add tests. The lock engages on safety_screen_required true; it is NOT
   engaged by safety.show:true with safety_screen_required:false; it survives a re-render;
   it fails closed on a network error for POST /responses; the missing-item prompt appears;
   it clears only on a false response.

Browser checklist (http://localhost:5173, signed in; use DevTools or mockApi to return the bodies):
[ ] Whole app is light pastel: no dark areas, gradients, glows or Inter font remain
[ ] Tab title "Astronaut Vitals" + new favicon
[ ] A POST /responses body with safety_screen_required:true → full-screen safety view immediately, before any score
[ ] A body with safety.show:true but safety_screen_required:false → NO safety view
[ ] Reload the page → the safety view still shows first (driven by GET /today); typing /settings in the URL still shows it
[ ] Clear sessionStorage and reload while /today says true → the safety view still shows
[ ] No close or skip; Esc does nothing; Tab cycles inside the dialog; screen reader announces the heading
[ ] Reason and resources text match the API body character for character
[ ] missing_safety_item:"phq9_9" → after "I've read this", exactly that one question appears
[ ] Answering it with a response that returns false → the lock clears and the dashboard shows
[ ] Offline (DevTools) while submitting a PHQ-9 → the safety view shows (fail closed)
[ ] prefers-reduced-motion and normal look identical on this screen (no motion at all)
[ ] Glass: cards and the tab bar are frosted over a soft pastel aurora; text stays crisp and dark
[ ] The safety screen is SOLID white: no glass, blur or aurora behind it
[ ] DevTools > Rendering > prefers-reduced-transparency or prefers-contrast: more → glass turns solid
[ ] The aurora drifts slowly; it is static under prefers-reduced-motion
```

---

## Task 2: Nightly dashboard `/`

```text
You are Codex. Read only coord/DESIGN.md, backend/openapi.json and these files.
Implement exactly; make no design decisions.

May edit: frontend/src/pages/Overview.tsx, frontend/src/components/VitalsTiles.tsx,
frontend/src/components/TodayCard.tsx, frontend/src/routes/tabs.ts, frontend/src/App.tsx (routes only),
frontend/src/theme/shell.css (.dash-, .orb-, .card-, .chip-, .trace-, .arc- only)
May create: frontend/src/components/StatusChip.tsx, VitalCard.tsx, BreathingOrb.tsx,
EcgTrace.tsx, SleepArc.tsx, CalibratingChip.tsx (all in frontend/src/components/)
Read-only: frontend/src/api/client.ts, frontend/src/api/schema.d.ts, frontend/src/live/useVitals.ts,
frontend/src/components/LoadState.tsx, frontend/src/test/fixtures.ts

Build per DESIGN.md 6.1–6.6 and 12 (dashboard row):
- Tabs: Tonight (/) · Weekly (/weekly) · Settings (/settings); bottom bar on phones, top bar at ≥768px.
- Hero: BreathingOrb from today.latest_night.rr_med (pure CSS @keyframes, period = 60/rr
  clamped 2–10s, static under reduced motion) + StatusChip, or CalibratingChip
  "Calibrating · {n} of 28 nights" when the baseline n < 28 or is missing.
- Advisory: today.context_engine.user_facing_advisory.headline and
  personality_tailored_message shown VERBATIM; hidden when absent.
- Cards: Breathing (mint), Sleep (sky, SleepArc from onset/midsleep/wake/presence_hours),
  Mind (lavender, pending_checkins → "Weekly check-in ready" link), Heart (peach,
  "Experimental estimate" chip + EcgTrace from /live/vitals samples only, labelled
  "Pulse trace", with "Experimental estimate, not a medical ECG"). Each card links to
  /night/{date} or /weekly.
- EcgTrace and SleepArc: SVG + CSS only (stroke-dashoffset draw 400ms; new samples slide
  250ms); both static under reduced motion. No numbers that count up.
- States: skeletons at final size; empty "Your first night will appear here tomorrow
  morning."; error card + Try again; 401 → /login.

Browser checklist (http://localhost:5173/):
[ ] Orb pulses gently at the rate shown; static with prefers-reduced-motion: reduce
[ ] With baseline n < 28 every status reads "Calibrating · n of 28 nights" (word + icon, butter chip)
[ ] Advisory headline and message match the API text exactly
[ ] Four cards: Breathing, Sleep (arc onset → wake), Mind, Heart (says Experimental and "Pulse trace", never "ECG" alone)
[ ] Status chips always show word + icon (Normal / Watch / Alert / No reading)
[ ] No data → the empty sentence; API down → error card with Try again; no fake numbers
[ ] 390px: one column, bottom tabs, nothing in the bottom-right corner; 1280px: orb left, 2×2 grid right
[ ] Tab key reaches every card link with a visible teal ring
```

---

## Task 3: Night detail `/night/:date`

```text
You are Codex. Read only coord/DESIGN.md, backend/openapi.json and these files.
Implement exactly; make no design decisions.

May edit: frontend/src/App.tsx (route only), frontend/src/components/FlagWhy.tsx,
frontend/src/components/NightsTable.tsx (rows link to /night/:date),
frontend/src/theme/shell.css (.night- only)
May create: frontend/src/pages/NightDetail.tsx
Read-only: frontend/src/components/SleepArc.tsx, StatusChip.tsx, VitalCard.tsx,
CalibratingChip.tsx, frontend/src/api/client.ts, frontend/src/api/schema.d.ts, frontend/src/test/fixtures.ts

Per DESIGN.md 12 (night detail row): a back link "← Tonight"; title = a friendly date
("Tuesday 10 Nov"); SleepArc; a "Breathing vs your usual" card with rr_med and the
baseline median ± MAD as a labelled band (or Calibrating); "valid" and "quality" as
chips with words; flags for that date from GET /api/v1/flags, each with FlagWhy
("Why am I seeing this?") using message text verbatim. Data: GET /api/v1/nights/{day}
(array; use the first valid row). Empty: "No reading for this night" + reason from
quality/valid. Error card + retry.

Browser checklist (open a night from the dashboard or /night/2026-11-10):
[ ] Back link returns to Tonight; the browser back button works
[ ] Arc + breathing card + chips render; the baseline band is labelled in words
[ ] Under 28 nights: Calibrating chip instead of a status
[ ] An invalid night explains why, with no numbers invented
[ ] Flag "why" text matches the API; it expands with Enter/Space
[ ] 390px no horizontal scroll; 1280px arc left, metrics right
```

---

## Task 4: Weekly check-in + trends `/weekly`

```text
You are Codex. Read only coord/DESIGN.md, backend/openapi.json and these files.
Implement exactly; make no design decisions.

May edit: frontend/src/App.tsx (route only), frontend/src/components/RrTrend.tsx,
frontend/src/components/IndexCards.tsx, frontend/src/components/IndexCards.css,
frontend/src/components/CheckinCalendar.tsx, frontend/src/components/QuestionnaireList.tsx,
frontend/src/components/CheckinForm.tsx (presentation only; submit must keep going through
api/client.ts so the safety lock sees every response), frontend/src/theme/shell.css (.weekly- only)
May create: frontend/src/pages/Weekly.tsx
Read-only: frontend/src/safety/lock.ts, frontend/src/api/client.ts, frontend/src/api/schema.d.ts,
frontend/src/components/CalibratingChip.tsx, frontend/src/test/fixtures.ts

Order on the page: pending weekly check-in card (opens CheckinForm: one question per card,
56px option buttons, "Question 3 of 9" progress text) → 28-night breathing trend
(RrTrend, flat lines, labelled baseline band or Calibrating) → presence-hours bars
(--sky, last night --teal + "Last night" label) → weekly indices (IndexCards: band word
+ direction arrow + word; no raw numbers) → check-in calendar (pastel pills by entry
type + marker shapes + legend; no mood inferred). Data: GET /nights?from&to, /indices,
/checkins, /instruments. Empty: "Trends appear after 3 nights." Error card per section.

Browser checklist (http://localhost:5173/weekly):
[ ] Check-in shows one question at a time with large answers and text progress
[ ] Submitting a PHQ-9 whose response has safety_screen_required:true → the safety screen takes over at once
[ ] Trend + bars render; "Last night" is labelled, not only colored
[ ] Index cards show words and arrows, never raw scores
[ ] Calendar legend explains each marker shape; no mood words
[ ] Each section shows its own empty/error state independently
[ ] 390px no horizontal scroll; keyboard can complete the whole check-in
```

---

## Task 5: Settings `/settings`

```text
You are Codex. Read only coord/DESIGN.md, backend/openapi.json and these files.
Implement exactly; make no design decisions.

May edit: frontend/src/pages/Settings.tsx, frontend/src/components/Consents.tsx,
frontend/src/components/DataControls.tsx, frontend/src/theme/shell.css (.settings- only)
Read-only: frontend/src/api/client.ts, frontend/src/api/schema.d.ts, frontend/src/auth/AuthProvider.tsx,
frontend/src/test/fixtures.ts

Sections as cards: Profile (GET/PATCH /me: display name, timezone) · Consents
(GET/PUT /me/consents; each a labelled switch with a one-line plain explanation) · Data
(export via GET /me/export as a download; delete via DELETE /me behind a confirm dialog
that requires typing DELETE) · Accessibility (a "Reduce motion" switch that adds
data-reduce-motion on <html>; CSS treats it like prefers-reduced-motion; stored in
localStorage with try/catch) · Companion (disabled row "Coming soon") · Sign out.
Inline error per section; skeleton rows while loading.

Browser checklist (http://localhost:5173/settings):
[ ] Each section saves independently and shows "Saved" text, not only a color
[ ] Consent switches have visible labels and explanations; the keyboard toggles them
[ ] Export downloads a file; delete needs typed confirmation
[ ] The Reduce motion switch stops the orb, arc and trace app-wide and survives a reload
[ ] Companion row is visibly disabled and says "Coming soon"
[ ] 390px no horizontal scroll; 1280px two-column sections
```

---

## Task 6: Login, register, baseline setup

```text
You are Codex. Read only coord/DESIGN.md, backend/openapi.json and these files.
Implement exactly; make no design decisions.

May edit: frontend/src/pages/Login.tsx, frontend/src/auth/AuthProvider.tsx,
frontend/src/App.tsx (routes only), frontend/src/theme/shell.css (.auth-, .setup- only),
frontend/package.json + package-lock.json (only if adding vanta@0.5.24 + three@0.134.0, exact)
May create: frontend/src/pages/Register.tsx, frontend/src/pages/Setup.tsx
Read-only: frontend/src/components/Consents.tsx, frontend/src/components/CheckinForm.tsx,
frontend/src/api/client.ts, frontend/src/api/schema.d.ts

Login/Register per DESIGN.md 12: a single centered card on mobile; on desktop the card on
the left and a calm pastel panel on the right (CSS soft blobs in mint/sky/lavender; an
optional lazy-loaded VANTA.FOG only on ≥768px, not under reduced motion, destroyed on
unmount). Remove all spacecraft art. Errors use the API message text.
Setup /setup (first run: localStorage "setup.done" absent and no baseline): 3 step cards
with "Step n of 3": consents → name + timezone → "Sleep near the sensor for 28 nights to
build your baseline" + optional first weekly check-in. Finish sets setup.done and goes to /.

Browser checklist:
[ ] /login and /register: light, one card, readable errors from the API
[ ] Desktop shows the pastel panel; reduced motion shows the static CSS version; three.js loads only here
[ ] A first sign-in goes to /setup; steps say "Step n of 3"; Finish lands on Tonight
[ ] A returning user skips setup
[ ] A safety lock still takes over even during setup (submit a PHQ-9 with the flag)
[ ] 390px no horizontal scroll; every control ≥44px and keyboard reachable
```
