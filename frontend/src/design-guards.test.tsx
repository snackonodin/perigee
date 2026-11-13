import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { SafetyProvider, useSafety } from "./safety/SafetyProvider";
import { SAFETY_FALLBACK } from "./safety/safety";
import { instruments, me, today } from "./test/fixtures";
import { mockApi, signIn } from "./test/mockApi";
import tokensCss from "./theme/tokens.css?raw";

// shell.css is not in vitest's CSS include list, so read it as text instead of ?raw.
const shellCss = readFileSync(resolve(process.cwd(), "src/theme/shell.css"), "utf8");

/** Innermost CSS rules as written (selector, declarations); at-rule wrappers are skipped. */
function rules(css: string): { selector: string; decls: string }[] {
  const out: { selector: string; decls: string }[] = [];
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) out.push({ selector: m[1].trim(), decls: m[2] });
  return out;
}

function tokenHex(name: string): string {
  const m = tokensCss.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  if (!m) throw new Error(`no token --${name}`);
  return m[1];
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(fg: string, bg: string): number {
  const [hi, lo] = [luminance(tokenHex(fg)), luminance(tokenHex(bg))].sort((a, b) => b - a);
  return (hi + 0.05) / (lo + 0.05);
}

const PASTELS = ["mint", "sky", "peach", "lavender", "butter", "alert-soft"];

// ---------------------------------------------------------------- (a) safety screen stays plain and on top

function Raise() {
  const { showSafety } = useSafety();
  return <button onClick={() => showSafety(SAFETY_FALLBACK)}>raise</button>;
}

describe("safety screen guard", () => {
  it("has no glass class or backdrop filter and no animation class", () => {
    render(
      <SafetyProvider>
        <Raise />
      </SafetyProvider>,
    );
    fireEvent.click(screen.getByText("raise"));
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.className).not.toMatch(/glass|animate|pulse|float|fade/i);
    const box = dialog.querySelector(".safety-box") as HTMLElement;
    expect(box.className).not.toMatch(/glass/);
    for (const el of [dialog, box]) {
      const inline = el.getAttribute("style") ?? "";
      expect(inline).not.toMatch(/backdrop-filter|animation/);
    }
  });

  it("CSS keeps every .safety rule opaque, unanimated and above all z layers", () => {
    const safetyRules = rules(shellCss).filter((r) => r.selector.includes(".safety"));
    expect(safetyRules.length).toBeGreaterThan(0);
    for (const rule of safetyRules) {
      expect(rule.decls).not.toMatch(/backdrop-filter/);
      if (/(^|;)\s*animation\s*:/.test(rule.decls)) expect(rule.decls).toMatch(/animation\s*:\s*none/);
    }
    const overlay = safetyRules.find((r) => /(^|,)\s*\.safety\s*(,|$)/.test(r.selector));
    expect(overlay?.decls).toMatch(/z-index\s*:\s*var\(--z-safety\)/);

    const zTokens = [...tokensCss.matchAll(/--z-[a-z]+:\s*(\d+)/g)].map((m) => Number(m[1]));
    expect(zTokens.length).toBeGreaterThan(0);
    expect(tokensCss).toMatch(/--z-safety:\s*1000\b/);
    expect(Math.max(...zTokens)).toBe(1000);
  });
});

// ---------------------------------------------------------------- (b) reduce motion / transparency are honoured

describe("reduce motion and transparency guards", () => {
  it("the app setting turns off animations on everything", () => {
    const rule = rules(shellCss).find((r) => r.selector.startsWith('html[data-reduce-motion="true"] *'));
    expect(rule).toBeTruthy();
    expect(rule!.decls).toMatch(/animation\s*:\s*none\s*!important/);
    expect(rule!.decls).toMatch(/transition\s*:\s*none\s*!important/);
  });

  it("the app setting makes glass surfaces solid", () => {
    const glassRules = rules(shellCss).filter((r) => r.selector.includes('html[data-reduce-transparency="true"]'));
    expect(glassRules.length).toBeGreaterThan(0);
    for (const rule of glassRules) {
      expect(rule.decls).toMatch(/background\s*:\s*var\(--surface\)/);
      expect(rule.decls).toMatch(/backdrop-filter\s*:\s*none/);
    }
  });

  it("the OS preferences are honoured too", () => {
    expect(shellCss).toMatch(/@media\s*\(prefers-reduced-motion:\s*reduce\)/);
    expect(shellCss).toMatch(/@media\s*\(prefers-reduced-transparency:\s*reduce\)/);
  });
});

// ---------------------------------------------------------------- (c) the new accent is readable, never on pastel

describe("accent --uv guard", () => {
  it("is at least 4.5:1 on surface and background", () => {
    expect(tokenHex("uv").toUpperCase()).toBe("#5B4BDB");
    expect(ratio("uv", "surface")).toBeGreaterThanOrEqual(4.5);
    expect(ratio("uv", "bg")).toBeGreaterThanOrEqual(4.5);
  });

  it("is never used as a text colour on a pastel fill", () => {
    for (const rule of rules(shellCss)) {
      if (!/color\s*:\s*var\(--uv\)/.test(rule.decls)) continue;
      const fill = rule.decls.match(/background(?:-color)?\s*:\s*var\(--([a-z-]+)\)/)?.[1];
      if (fill) expect(PASTELS.includes(fill), `${rule.selector} puts --uv text on --${fill}`).toBe(false);
    }
  });
});

// ---------------------------------------------------------------- (d) no diagnostic wording in rendered pages

const BANNED = /\b(depress\w*|anxiety disorder|disorder|diagnos\w*)\b/i;

function visibleText(el: HTMLElement): string {
  const copy = el.cloneNode(true) as HTMLElement;
  copy.querySelectorAll(".instrument-official").forEach((n) => n.remove());
  return (copy.textContent ?? "").replace(/not a diagnosis/gi, "");
}

describe("no diagnosis words in UI copy", () => {
  beforeEach(() => {
    vi.useRealTimers();
    signIn();
    mockApi({
      "GET /api/v1/me": { body: me },
      "GET /api/v1/today": { body: today },
      "GET /api/v1/nights": { body: [] },
      "GET /api/v1/instruments": { body: instruments },
      "GET /api/v1/me/consents": { body: {} },
    });
  });

  it.each(["/", "/sleep", "/body", "/persona", "/checkin", "/briefing", "/consent", "/settings", "/monitor"])(
    "%s shows no diagnostic wording",
    async (path) => {
      const { container, unmount } = render(<App initialPath={path} />);
      await screen.findByRole("navigation", { name: /^Sections/ });
      await screen.findByRole("main");
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 50));
      });
      const text = visibleText(container);
      expect(text).not.toMatch(BANNED);
      unmount();
    },
  );
});
