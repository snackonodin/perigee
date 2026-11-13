#!/usr/bin/env node
// lint_dialog.mjs: checks the pet dialog cache. Exits 1 on any failure.
// Usage: node scripts/lint_dialog.mjs [--require] [--partial] [file]
//   default file: src/pet/dialog/cache.json
//   --require  fail if the file does not exist (phase 05 and later)
//   --partial  skip coverage minimums (used to lint ../dialog/seed.json)
import { existsSync, readFileSync } from "node:fs";

const args = process.argv.slice(2);
const REQUIRE = args.includes("--require");
const PARTIAL = args.includes("--partial");
const file = args.find((a) => !a.startsWith("--")) ?? "src/pet/dialog/cache.json";

const EVENTS = ["first_run", "app_open", "welcome_back", "quiz_start", "quiz_complete", "bedtime_near",
  "sleep_start", "wake", "night_logged", "streak_milestone", "idle_long", "pet_tap", "goodbye"];
const TONES = ["warm", "quiet", "bright"];
const TODS = ["morning", "day", "evening", "night", "any"];
const MIN = { quiz_complete: 10, bedtime_near: 10, sleep_start: 10, wake: 10 };
const DEFAULT_MIN = 6;
const MAX_LEN = 90;

// Whole-word / phrase matches, case-insensitive. Keep in sync with SAFETY.md S2.
const BANNED = [
  "diagnosis", "diagnose", "diagnosed", "depression", "depressed", "anxiety", "anxious", "disorder",
  "illness", "disease", "risk", "risks", "score", "scores", "result", "results", "symptom", "symptoms",
  "patient", "treatment", "therapy", "therapist", "clinical", "medication", "medications", "medicine",
  "pill", "pills", "dose", "doctor", "suicide", "suicidal", "self-harm", "harm", "kill", "die", "death",
  "insomnia", "apnea", "heart rate", "bpm", "breathing rate", "alert", "warning", "level", "levels",
  "normal", "abnormal", "healthy", "unhealthy",
  "you should", "you must", "you need to", "should have", "make sure", "don't forget", "do not forget",
  "try to sleep", "go to bed", "get some sleep", "go to sleep",
  "missed", "you missed", "i missed you", "where were you", "you left", "streak broken", "broke your streak",
  "lost your streak", "sad", "lonely", "hungry", "sick",
];
const bannedRe = BANNED.map((t) => [t, new RegExp(`(^|[^a-z])${t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z]|$)`, "i")]);

const errors = [];
const err = (m) => errors.push(m);

if (!existsSync(file)) {
  if (REQUIRE) { console.error(`lint_dialog: ${file} not found`); process.exit(1); }
  console.log(`lint_dialog: ${file} not found yet (created in phase 05). Skipping.`);
  process.exit(0);
}

let data;
try { data = JSON.parse(readFileSync(file, "utf8")); }
catch (e) { console.error(`lint_dialog: ${file} is not valid JSON: ${e.message}`); process.exit(1); }

const ids = new Set();
let count = 0;
for (const [event, tones] of Object.entries(data)) {
  if (event.startsWith("_")) continue;
  if (!EVENTS.includes(event)) { err(`unknown event "${event}"`); continue; }
  for (const [tone, lines] of Object.entries(tones)) {
    if (!TONES.includes(tone)) { err(`${event}: unknown tone "${tone}"`); continue; }
    if (!Array.isArray(lines)) { err(`${event}.${tone}: must be an array`); continue; }
    for (const line of lines) {
      count++;
      const where = `${event}.${tone} ${line?.id ?? "(no id)"}`;
      const keys = Object.keys(line ?? {}).sort().join(",");
      if (keys !== "id,text,tod,weight") err(`${where}: keys must be exactly id,text,tod,weight (got ${keys})`);
      if (typeof line.id !== "string" || !new RegExp(`^${event}\\.${tone}\\.[0-9]{2}$`).test(line.id))
        err(`${where}: id must be "${event}.${tone}.NN"`);
      if (ids.has(line.id)) err(`${where}: duplicate id`);
      ids.add(line.id);
      if (typeof line.text !== "string" || line.text.trim().length < 2) { err(`${where}: empty text`); continue; }
      const shown = line.text.replaceAll("{petName}", "Clover");
      if (shown.length > MAX_LEN) err(`${where}: ${shown.length} chars > ${MAX_LEN}`);
      if (/\{(?!petName\})[^}]*\}/.test(line.text)) err(`${where}: only {petName} placeholder allowed`);
      if (!TODS.includes(line.tod)) err(`${where}: tod must be one of ${TODS.join("|")}`);
      if (!Number.isInteger(line.weight) || line.weight < 1 || line.weight > 5) err(`${where}: weight must be integer 1..5`);
      for (const [term, re] of bannedRe) if (re.test(line.text)) err(`${where}: banned term "${term}" in "${line.text}"`);
      if ((line.text.match(/!/g) ?? []).length > 1) err(`${where}: at most one "!"`);
      if (tone === "quiet" && line.text.includes("!")) err(`${where}: quiet tone uses no "!"`);
    }
  }
}

if (!PARTIAL) {
  for (const event of EVENTS) {
    for (const tone of TONES) {
      const n = data?.[event]?.[tone]?.length ?? 0;
      const min = MIN[event] ?? DEFAULT_MIN;
      if (n < min) err(`coverage: ${event}.${tone} has ${n} lines, needs >= ${min}`);
    }
  }
}

if (errors.length) {
  console.error(`lint_dialog: ${errors.length} problem(s) in ${file}`);
  for (const e of errors.slice(0, 200)) console.error("  - " + e);
  process.exit(1);
}
console.log(`lint_dialog: OK (${count} lines, ${ids.size} unique ids) in ${file}`);
