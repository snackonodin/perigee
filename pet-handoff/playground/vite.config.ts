/// <reference types="vitest/config" />
// Same compiler settings and versions as the host app (frontend/). No backend, no proxy.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist", emptyOutDir: true, assetsInlineLimit: 0 },
  server: { host: "127.0.0.1" },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/test-setup.ts"], passWithNoTests: true },
});
