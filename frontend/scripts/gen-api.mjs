// npm run gen:api: dump the backend's OpenAPI schema (no server needed) and generate
// src/api/schema.d.ts with openapi-typescript. Python: $PYTHON, else the active venv,
// else python3 on PATH. Nothing machine-specific is written.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(here, "..");
const repo = resolve(frontend, "..");
const python =
  process.env.PYTHON ||
  (process.env.VIRTUAL_ENV ? join(process.env.VIRTUAL_ENV, "bin", "python") : "python3");

const dump =
  "import json; from backend.main import create_app; " +
  "print(json.dumps(create_app(with_lifespan=False).openapi(), indent=2, sort_keys=True))";
const spec = execFileSync(python, ["-c", dump], { cwd: repo, encoding: "utf8", maxBuffer: 64e6 });
const specPath = join(frontend, "openapi.json");
writeFileSync(specPath, spec);
execFileSync(
  join(frontend, "node_modules", ".bin", "openapi-typescript"),
  [specPath, "-o", join(frontend, "src", "api", "schema.d.ts")],
  { cwd: frontend, stdio: "inherit" },
);
