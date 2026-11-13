# TOOLS.md: what you may use

Rule: use only what is listed here as **allowed**, plus plain SVG, CSS and Canvas 2D.
Do not add npm packages. The playground's `package.json` is the full dependency list.

## A. Techniques (required or allowed)

| Tool | Status | How to use it for the pet |
|---|---|---|
| Inline SVG (`viewBox="0 0 256 256"`) | **Required** | One component per species. Group parts as `<g data-part="ear-l">` etc. so the rig can transform them. Use `transform-box: fill-box` + `transform-origin` in CSS for pivots |
| CSS custom properties | **Required** | The rig variables (`--look-x`, `--blink`, ...) live on the pet root element. Parts read them, e.g. `transform: rotate(calc(var(--ear-l) * 14deg))` |
| CSS `@property` | **Required** | Register every rig variable as `<number>` so CSS transitions and keyframes can animate it. Example in the box below |
| `requestAnimationFrame` | **Required** | Only for the frost canvas and for walking. Everything else is CSS keyframes/transitions + timers |
| Canvas 2D (`globalCompositeOperation = "destination-out"`) | **Required** | Frost trail (BRIEF §3) |
| `matchMedia("(prefers-reduced-motion: reduce)")` | **Required** | Combined with the `reducedMotion` prop: either one true ⇒ static pose, no loops, no canvas |
| Page Visibility API (`document.hidden`, `visibilitychange`) | **Required** | Pause the frost rAF and all timers when the tab is hidden |
| SVG `linearGradient` / `radialGradient` | Allowed | The 3-tone shading, blush (radial, soft edge), rim light |
| `clip-path` (SVG `<clipPath>`) | Allowed | Clip shading shapes to the head/body so shade never spills outside |
| `feTurbulence` + `feColorMatrix` | Allowed, **static only** | Fur grain at opacity ≤ 0.12, applied to the head/body group. Never animate it; skip it under 96px rendering (`data-size="sm"`) for speed |
| `mix-blend-mode: soft-light` / `screen` | Allowed | Rim light and frost crystals only |
| `filter: drop-shadow()` | Allowed, **once** | At most one on the pet root. The contact shadow is an ellipse, not a filter |
| `ResizeObserver` | Allowed | Resize the frost canvas backing store |
| Vitest + Testing Library (in playground devDeps) | Allowed | Tests in `src/pet/__tests__/` |

```css
@property --blink { syntax: "<number>"; inherits: true; initial-value: 0; }
.pet [data-part="eyes"] { transform-box: fill-box; transform-origin: center;
  transform: scaleY(calc(1 - .92 * var(--blink))); }
```

## B. References the user suggested earlier (look and feel only)

| Name | Status | Use |
|---|---|---|
| **terminal-pet** (GitHub, Tamagotchi-style pet) | Reference only, not installed | Idea source for a tiny body, idle loops and reacting to small events. No code or art copied |
| **"di-pett"** | Reference only | The user named it alongside terminal-pet as a Tamagotchi/desktop-pet example. **The exact repository could not be confirmed**; do not search for or copy it |
| **GSAP** (greensock/GSAP) | **Not allowed in the pet** | The app does not ship GSAP. Do everything with CSS keyframes, transitions and rAF |
| **Lenis** (smooth scroll) | Not for the pet | App-level scroll only |
| **Vanta** (WebGL fog) + three.js | Not for the pet | Sign-in screen background only; WebGL is over budget for the pet |
| **react-bits** (copy-in MIT components) | Reference only | Its entrance fades inspired the app's CSS fades. Nothing to copy for the pet |
| **Cult UI** | Reference only | Its hover lift + sheen sweep inspired the app's cards; the pet's rim light echoes that sheen |
| **Watermelon UI**, **Skipper UI** | Reference only | Card spacing and small micro-interactions in the app; nothing for the pet |
| Happify, Google Health screenshots | Reference only | Warm, rounded, friendly tone of the app |

## C. Not allowed

Raster images (PNG/JPG/WebP/GIF), Lottie, Rive, WebGL, web fonts, icon fonts, emoji as
art, network requests of any kind, `eval`, any new npm package, any LLM call.
