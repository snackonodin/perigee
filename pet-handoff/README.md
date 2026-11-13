# pet-handoff: build a companion pet (self-contained package)

You are building a small animated companion pet for a web app. This folder is all you
get. You have no access to the app's code, and you do not need it. Everything you need
is here: the spec, the tokens, the TypeScript contract, sample dialog, a starting SVG and
a runnable playground.

## Read in this order (about 25 minutes)

1. `BRIEF.md`: what the product is and the full pet spec. **Read it all once.**
2. `SAFETY.md`: hard rules. They override everything else.
3. `contract.d.ts`: the exact types your code must export.
4. `TOKENS.css`: the only colors, radii and motion values you may use.
5. `TOOLS.md`: the only techniques and libraries you may use.
6. `personas.json`, `dialog/schema.json`, `dialog/seed.json`: voice and data shape.
7. `reference/cat-head-skeleton.svg`: a starting point for the art.
8. `ACCEPTANCE.md`: how your work is graded. `RETURN.md`: how to hand it back.

## Work in phases. Do ONE phase per session, then stop.

| Phase | File | Result |
|---|---|---|
| 1 | `phases/01-cat.md` | Static cat with rig variables |
| 2 | `phases/02-fox-bunny.md` | Fox and bunny on the same rig |
| 3 | `phases/03-behavior.md` | Blinks, breathing, interactions, sleep mode |
| 4 | `phases/04-frost-trail.md` | Frost layer that clears where the pet walks |
| 5 | `phases/05-dialog-cache.md` | Offline dialog cache, picker, lint |
| 6 | `phases/06-integration-qa.md` | Public component, controls, tests, budget, return |

Each phase file is self-contained: goal, inputs, exact files, checks, and "stop". If a
phase fails its checks, fix it before starting the next one. If you are low on context,
finish the current phase cleanly instead of starting the next.

## Setup (once)

```bash
cd playground
npm install          # needs Node >= 24, npm >= 11; versions are pinned
npm run check        # type-check + dialog lint + build + size budget; must pass
npm test             # vitest (jsdom)
npm run render       # writes playground/out/*.svg (static renders, no browser needed)
npm run dev          # optional: open the printed URL if you have a browser
```

All your code goes in `playground/src/pet/`. Nothing else is returned.

## Returning work

See `RETURN.md`: copy `playground/src/pet/` to a folder named `frontend-src-pet/`, add
`STATUS.md`, and zip both. Do not edit any other file in this package.

## If something is unclear

Pick the option that is simpler and safer, write it under "Assumptions" in `STATUS.md`,
and continue. Never weaken a rule in `SAFETY.md` to make something work.
