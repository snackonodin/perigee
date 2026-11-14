// Art budget checks (pet-handoff ACCEPTANCE B1, B5, B6). With PET_RENDER_DIR set it also
// writes a static preview page (all species x moods x sizes) for screenshots.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PetArt } from "../PetArt";
import type { PetMood, Species } from "../types";

const SPECIES: Species[] = ["cat", "fox", "bunny"];
const MOODS: PetMood[] = ["neutral", "happy", "sleeping"];

function svgOf(species: Species, mood: PetMood) {
  const host = document.createElement("div");
  host.innerHTML = renderToStaticMarkup(<PetArt species={species} mood={mood} />);
  return host.querySelector("svg")!;
}

describe.each(SPECIES)("%s art", (species) => {
  it.each(MOODS)("%s: <= 120 elements, strokes >= 4 units, no black, tokens with fallbacks", (mood) => {
    const svg = svgOf(species, mood);
    expect(svg.getAttribute("viewBox")).toBe("0 0 256 256");
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    const all = svg.querySelectorAll("*");
    expect(all.length).toBeLessThanOrEqual(120);
    for (const el of all) {
      const sw = (el as SVGElement).style?.strokeWidth || el.getAttribute("stroke-width");
      if (sw) expect(Number.parseFloat(sw)).toBeGreaterThanOrEqual(4);
      const s = `${el.getAttribute("style") ?? ""} ${el.getAttribute("fill") ?? ""} ${el.getAttribute("stroke") ?? ""}`;
      expect(s).not.toMatch(/#000\b|black/i);
      const colours = s.match(/var\(--[a-z0-9-]+\)/gi) ?? [];
      expect(colours, `var() without fallback in ${s}`).toEqual([]);
    }
    for (const part of ["shadow", "tail", "body", "paws", "head", "ear-l", "ear-r", "eyes", "eye-l", "eye-r", "mouth", "mouth-open", "blush", "rim", "accessories"]) {
      expect(svg.querySelector(`[data-part="${part}"]`), part).not.toBeNull();
    }
  });
});

it("writes a preview page when PET_RENDER_DIR is set", async () => {
  // Node APIs typed loosely: the app tsconfig has no node types (test-only helper).
  const proc = (globalThis as unknown as { process?: { env: Record<string, string | undefined>; cwd(): string } }).process;
  const env = proc?.env;
  const dir = env?.PET_RENDER_DIR;
  if (!dir) return;
  type Fs = { readFileSync(p: string, e: string): string; writeFileSync(p: string, d: string): void; mkdirSync(p: string, o: object): void };
  const { readFileSync, writeFileSync, mkdirSync } = (await import(/* @vite-ignore */ "node:fs" as string)) as Fs;
  const root = `${proc!.cwd()}/src/`;
  const css = ["theme/tokens.css", "pet/rig.css", "pet/pet.css"].map((f) => readFileSync(root + f, "utf8")).join("\n");
  const cells = SPECIES.flatMap((s) => [...MOODS, "petting" as PetMood].map((m) =>
    `<figure>${renderToStaticMarkup(<PetArt species={s} mood={m} size={160} accessories={m === "neutral" ? [] : ["scarf", "star", "moon", "crown"]} />)}<figcaption>${s} · ${m}</figcaption></figure>`));
  const sizes = SPECIES.map((s) => [64, 128].map((z) => `<figure>${renderToStaticMarkup(<PetArt species={s} mood="neutral" size={z} />)}<figcaption>${s} ${z}px</figcaption></figure>`).join("")).join("");
  mkdirSync(dir, { recursive: true });
  writeFileSync(`${dir}/pets.html`, `<!doctype html><meta charset="utf-8"><style>${css}
body{margin:0;padding:16px;background:linear-gradient(135deg,#e6f6ef,#e8f1fb 50%,#f1ecfb);font:12px system-ui}
main{display:grid;grid-template-columns:repeat(4,200px);gap:12px}figure{margin:0;padding:12px;background:rgba(255,255,255,.62);border-radius:16px;display:grid;justify-items:center;gap:6px}
.sizes{display:flex;gap:12px;align-items:end;margin-top:12px;flex-wrap:wrap}</style><main>${cells.join("")}</main><div class="sizes">${sizes}</div>`);
});
