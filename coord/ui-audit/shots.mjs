// coord/ui-audit/shots.mjs: screenshot the running app via Chrome DevTools Protocol (no packages). Usage:
// node shots.mjs <outdir> <access> <refresh> <width> <height> <route...>
import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";

const [out, access, refresh, w, h, ...routes] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const BASE = "http://127.0.0.1:8765";
const port = 9333 + Math.floor(Math.random() * 500);
const chrome = spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
  "--headless=new", `--remote-debugging-port=${port}`, "--no-first-run", "--no-default-browser-check",
  `--user-data-dir=${out}/.profile`, `--window-size=${w},${h}`, "--hide-scrollbars", "about:blank",
], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try { target = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch {}
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0; const pending = new Map();
ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } });
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: +w, height: +h, deviceScaleFactor: 1, mobile: +w < 600 });
await send("Page.navigate", { url: BASE + "/login" }); await sleep(1200);
if (access) await send("Runtime.evaluate", { expression: `sessionStorage.setItem("ahm.access", ${JSON.stringify(access)}); sessionStorage.setItem("ahm.refresh", ${JSON.stringify(refresh)}); localStorage.setItem("setup.done","true");` });
for (const route of routes) {
  await send("Page.navigate", { url: BASE + route }); await sleep(2500);
  const full = await send("Runtime.evaluate", { expression: "Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)", returnByValue: true });
  const height = Math.min(4000, full.result.result.value || +h);
  // Resize the viewport to the full page so fixed layers (backdrop, tab bar) are not cut at the fold.
  await send("Emulation.setDeviceMetricsOverride", { width: +w, height, deviceScaleFactor: 1, mobile: +w < 600 });
  await sleep(400);
  const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: +w, height, scale: 1 } });
  await send("Emulation.setDeviceMetricsOverride", { width: +w, height: +h, deviceScaleFactor: 1, mobile: +w < 600 });
  const name = `${w}${route.replace(/\//g, "_") || "_root"}.png`;
  writeFileSync(`${out}/${name}`, Buffer.from(shot.result.data, "base64"));
  console.log(name, height);
}
ws.close(); chrome.kill();
