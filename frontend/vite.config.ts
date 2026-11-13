/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built into backend/static/app and served by the API at / (same origin, fully offline:
// no CDN, fonts bundled from @fontsource). `npm run dev` proxies /api to a local uvicorn.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "../backend/static/app", // relative to this folder (vite root)
    emptyOutDir: true,
    assetsInlineLimit: 0,
  },
  server: {
    host: "127.0.0.1",
    // the app bundles seeds/safety_resources.json (offline safety text) from the repo root
    fs: { allow: [".."] },
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    // keep tokens.css as real text in tests: the contrast test reads it with ?raw
    css: { include: [/tokens\.css/, /shell\.css/] },
  },
});
