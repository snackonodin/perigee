#!/usr/bin/env node
// check_budget.mjs: gzipped size of src/pet/ (excluding __tests__ and *.test.*) must be
// < 80 KB, and the folder must contain no raster images, fonts or network calls.
// Measures source files (an upper bound of the shipped size). Exits 1 on failure.
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, extname } from "node:path";
import { gzipSync } from "node:zlib";

const ROOT = "src/pet";
const LIMIT = 80 * 1024;
const RASTER = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".ico"];
const FONT = [".woff", ".woff2", ".ttf", ".otf", ".eot"];
const NETWORK = /\b(fetch\s*\(|XMLHttpRequest|WebSocket|EventSource|navigator\.sendBeacon|import\s*\(\s*["']https?:)/;
const URLRE = /https?:\/\/(?!www\.w3\.org\/)/; // SVG xmlns is fine

if (!existsSync(ROOT)) { console.error(`check_budget: ${ROOT} missing`); process.exit(1); }

const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) { if (name !== "__tests__") walk(p); continue; }
    if (/\.test\.[tj]sx?$/.test(name)) continue;
    files.push(p);
  }
})(ROOT);

const problems = [];
let concat = "";
for (const f of files) {
  const ext = extname(f).toLowerCase();
  if (RASTER.includes(ext)) problems.push(`raster image not allowed: ${f}`);
  if (FONT.includes(ext)) problems.push(`font file not allowed: ${f}`);
  const text = readFileSync(f, "utf8");
  if (/\.(tsx?|jsx?|mjs)$/.test(f) && NETWORK.test(text)) problems.push(`network call not allowed: ${f}`);
  if (URLRE.test(text)) problems.push(`external URL not allowed: ${f}`);
  if (/data:image\/(png|jpe?g|gif|webp)/i.test(text)) problems.push(`embedded raster not allowed: ${f}`);
  concat += text + "\n";
}
const gz = gzipSync(Buffer.from(concat), { level: 9 }).length;
console.log(`check_budget: ${files.length} files, ${(gz / 1024).toFixed(1)} KB gzipped (limit 80 KB)`);
if (gz >= LIMIT) problems.push(`over budget: ${(gz / 1024).toFixed(1)} KB >= 80 KB`);
if (problems.length) { for (const p of problems) console.error("  - " + p); process.exit(1); }
