# RETURN.md: how to hand the work back

Return exactly two things, zipped together as `pet-return.zip`:

```
pet-return.zip
├── frontend-src-pet/     ← a copy of playground/src/pet/ (all files, including __tests__/)
└── STATUS.md
```

`frontend-src-pet/` is dropped into the app **verbatim** as `frontend/src/pet/`. So:

1. Code in it imports only `react` and its own files (relative paths). No imports from
   `../mockContext`, `../tokens.css`, the playground, or any other package.
2. CSS lives in `src/pet/pet.css`, imported by `Pet.tsx`. Every token use has a fallback:
   `var(--pet-cat-fur, #FFF4D6)`.
3. Tests live in `src/pet/__tests__/` and use only `vitest` and `@testing-library/react`.
4. Do not change anything outside `src/pet/` and do not return other files. Changes to
   `main.tsx` or `playground.css` for your own testing are fine but stay with you.

## Commands

```bash
cd playground
npm run check:final                       # must exit 0
mkdir -p ../../return && rm -rf ../../return/*
cp -R src/pet ../../return/frontend-src-pet
# write ../../return/STATUS.md (template below), then:
cd ../../return && zip -r pet-return.zip frontend-src-pet STATUS.md
```

No `zip` command? Any zip tool is fine, or return the folder as is.

## STATUS.md template

```markdown
# Pet STATUS

Phases done: 01 02 03 04 05 06   (cross out any not done)
check:final: PASS/FAIL (paste the last 15 lines)
Budget: NN.N KB gzipped
Render: 9 SVGs, max elements NN, thinnest stroke N units

## Acceptance (ACCEPTANCE.md)
A1 PASS - ...
... one line per item ...

## Assumptions (decisions I made because something was unclear)
1. ...

## Known gaps
1. ...
```
