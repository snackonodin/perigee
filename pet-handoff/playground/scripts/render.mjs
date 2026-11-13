#!/usr/bin/env node
// render.mjs: renders each species to static SVG text in out/ (no browser needed), and
// fails if any stroke-width is below 4 viewBox units (a hairline at 64px).
// Uses Vite's SSR loader, so TSX works without extra tools.
// Usage: npm run render
import { mkdirSync, writeFileSync } from "node:fs";
import { createServer } from "vite";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const server = await createServer({
  server: { middlewareMode: true }, appType: "custom", logLevel: "error",
  ssr: { external: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime"] },
});
let failed = false;
try {
  const pet = await server.ssrLoadModule("/src/pet/index.ts");
  if (typeof pet.PetArt !== "function") {
    console.log("render: src/pet/index.ts does not export PetArt yet (phase 01 adds it). Skipping.");
  } else {
    mkdirSync("out", { recursive: true });
    for (const species of ["cat", "fox", "bunny"]) {
      for (const mood of ["neutral", "happy", "sleeping"]) {
        const svg = renderToStaticMarkup(React.createElement(pet.PetArt, { species, mood }));
        const file = `out/${species}-${mood}.svg`;
        writeFileSync(file, svg.includes("xmlns=") ? svg : svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"'));
        const thin = [...svg.matchAll(/stroke-width="([\d.]+)"/g)].map((m) => Number(m[1])).filter((w) => w > 0 && w < 4);
        const count = (svg.match(/<(path|circle|ellipse|rect|polygon|line|g|use)\b/g) ?? []).length;
        console.log(`${file}: ${svg.length} bytes, ${count} elements${thin.length ? `, THIN strokes: ${thin.join(",")}` : ""}`);
        if (thin.length) failed = true;
        if (count > 120) { console.log(`  over 120 elements`); failed = true; }
      }
    }
  }
} finally {
  await server.close();
}
process.exit(failed ? 1 : 0);
