#!/usr/bin/env python3
"""Fresh-DB app and Context Engine test/report loop."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "loop" / "reports"
BUGS = ROOT / "loop" / "BUGS.md"


def command(
    args: list[str], *, env: dict[str, str], timeout: int = 120, cwd: Path = ROOT
) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def isolated_env(data: Path) -> dict[str, str]:
    from cryptography.fernet import Fernet

    env = dict(os.environ)
    env.update(
        SECRET_KEY=secrets.token_hex(32),
        FIELD_KEY=Fernet.generate_key().decode(),
        DATA_DIR=str(data),
        DATABASE_URL=f"sqlite:///{data / 'astro.db'}",
        ASTRO_DISABLE_WORKER="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    return env


def wait_health(base: str, process: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited early; see {log_path}")
        try:
            with urlopen(f"{base}/api/v1/health", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.2)
    raise RuntimeError(f"server health timeout; see {log_path}")


def start_app(data: Path, temp: Path):
    data.mkdir(parents=True, exist_ok=True)
    env = isolated_env(data)
    schema = command(
        [
            sys.executable,
            "-c",
            "from backend.db import init_db\nfrom backend.models import Base\n"
            "engine = init_db(); Base.metadata.create_all(engine); engine.dispose()\n",
        ],
        env=env,
    )
    if schema.returncode:
        raise RuntimeError(f"fresh schema setup failed:\n{schema.stdout}\n{schema.stderr}")
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    log_path = temp / "server.log"
    log = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_health(base, process, log_path)
        return process, log, base, env, log_path
    except Exception:
        process.terminate()
        process.wait(timeout=10)
        log.close()
        raise


def http_probe(base: str) -> list[str]:
    failures = []
    for path, expected in (("/api/v1/health", 200), ("/api/v1/version", 200), ("/demo/", 200)):
        try:
            with urlopen(f"{base}{path}", timeout=4) as response:
                if response.status != expected:
                    failures.append(f"GET {path}: expected {expected}, got {response.status}")
        except Exception as exc:  # report endpoint crashes as a loop failure
            failures.append(f"GET {path}: {type(exc).__name__}: {exc}")
    return failures


def run_checks(
    env: dict[str, str], base: str, seed: int, n: int, temp: Path
) -> tuple[list[str], dict, int]:
    failures: list[str] = []
    api_steps = 0
    focused = command(
        [sys.executable, "-m", "pytest", "-q", "tests/safety", "tests/test_engine_boundary.py",
         "tests/api/test_health.py", "tests/api/test_demo_page.py"],
        env=env,
        timeout=90,
    )
    if focused.returncode:
        failed_cases = [line.strip() for line in focused.stdout.splitlines() if line.startswith("FAILED ")]
        failures.extend(f"focused pytest failed: {case}" for case in failed_cases)
        if not failed_cases:
            failures.append("focused pytest failed:\n" + focused.stdout[-3000:] + focused.stderr[-1000:])

    if shutil.which("curl"):
        flow = command(
            ["bash", "tests/e2e/curl_flow.sh"],
            env={**env, "BASE_URL": base, "PYTHON": sys.executable},
            timeout=90,
        )
        api_steps = sum(
            line.startswith(("PASS ", "FAIL ", "SKIP ")) for line in flow.stdout.splitlines()
        )
        if flow.returncode:
            failures.append("API curl flow failed:\n" + flow.stdout[-3500:] + flow.stderr[-1500:])
    else:
        failures.append("API curl flow unavailable: curl is not installed")

    fuzz_json = temp / "fuzz.json"
    fuzz = command(
        [sys.executable, "evals/fuzz_eval.py", "--seed", str(seed), "--n", str(n), "--out", str(fuzz_json)],
        env={**env, "PYTHONPATH": str(ROOT / "waiwai1")},
        timeout=100,
        cwd=ROOT / "waiwai1",
    )
    if fuzz.returncode:
        failures.append("fuzz evaluator crashed:\n" + fuzz.stdout[-3000:] + fuzz.stderr[-2000:])
        result = {"seed": seed, "n": n, "violations": -1, "fitness": None}
    else:
        result = json.loads(fuzz_json.read_text(encoding="utf-8"))
        if result["violations"]:
            failures.append(f"fuzz violations={result['violations']} by_rule={result['by_rule']}")
    result["api_steps"] = api_steps
    return failures, result, api_steps


def append_bugs(failures: list[str], seed: int, iteration: int) -> None:
    if not failures:
        return
    BUGS.parent.mkdir(parents=True, exist_ok=True)
    if not BUGS.exists():
        BUGS.write_text("# Open loop bugs\n\nFailures are evidence-led; close only with a regression guard.\n", encoding="utf-8")
    current = BUGS.read_text(encoding="utf-8")
    for failure in failures:
        title = re.sub(r"\s+", " ", failure.splitlines()[0])[:180]
        key = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if f"<!-- {key} -->" in current:
            continue
        entry = (
            f"\n## OPEN: {title}\n\n<!-- {key} -->\n"
            f"- First seen: iteration {iteration}, seed {seed}.\n"
            f"- Reproduce: python loop/run_loop.py --smoke --seed {seed}\n"
            f"- Evidence: {failure[:1200]}\n"
            "- Attempts: 0/3.\n"
        )
        with BUGS.open("a", encoding="utf-8") as handle:
            handle.write(entry)
        current += entry


def bug_summary() -> tuple[int, int, int]:
    if not BUGS.exists():
        return 0, 0, 0
    text = BUGS.read_text(encoding="utf-8")
    fixed = len(re.findall(r"^## FIXED:", text, re.MULTILINE))
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    open_sections = [section for section in sections if section.startswith("## OPEN:")]
    open_count = len(open_sections)
    exhausted = sum(bool(re.search(r"Attempts:\s*3/3", section)) for section in open_sections)
    return fixed, open_count, exhausted


def write_report(iteration: int, seed: int, cases: int, fuzz: dict, failures: list[str], app_failures: list[str]) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = REPORTS / f"{stamp}-iteration-{iteration:02d}.md"
    lines = [
        f"# Loop iteration {iteration}",
        "",
        f"- Timestamp: {stamp}",
        f"- Seed: {seed}",
        f"- Generated fuzz payloads: {fuzz.get('n', 0)}; fuzz seed: {fuzz.get('seed', seed)}",
        f"- Cases counted: {cases}",
        f"- Fuzz fitness: {fuzz.get('fitness')}; violations: {fuzz.get('violations')}",
        "- Coverage spaces: authenticated app health/version/demo assets; Context Engine generated payloads and stateful spec probes in fuzz_eval; focused safety/delegation tests.",
        "- Not covered here: browser rendering, physical CSI hardware, direct UI walk, Context Engine persisted user/night state.",
        f"- Status: {'FAIL' if failures or app_failures else 'PASS'}",
        "",
        "## App probes",
        *(f"- {item}" for item in (app_failures or ["All probes returned expected status."])),
        "",
        "## Failures",
        *(f"- {item[:1400]}" for item in (failures or ["None."])),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--budget-min", type=float, default=60)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--seed", type=int, default=7101)
    args = parser.parse_args()
    if args.iterations < 1 or args.budget_min <= 0:
        parser.error("iterations and budget must be positive")
    iterations = 1 if args.smoke else args.iterations
    n = 20 if args.smoke else 300
    budget = min(args.budget_min * 60, 110) if args.smoke else args.budget_min * 60
    started = time.monotonic()
    clean_streak = 0
    saw_failure = False
    previous_fitness: float | None = None
    totals = {"cases": 0, "fixed": 0, "open": 0, "iterations": 0}
    stop_reason = "iteration limit"

    for iteration in range(1, iterations + 1):
        if time.monotonic() - started >= budget:
            stop_reason = "time budget"
            break
        seed = args.seed + (iteration - 1) * 104729
        failures: list[str] = []
        app_failures: list[str] = []
        infrastructure_failures: list[str] = []
        with tempfile.TemporaryDirectory(prefix="astro-loop-") as tmp_name:
            temp = Path(tmp_name)
            data = temp / "data"
            try:
                process, log, base, env, server_log = start_app(data, temp)
                try:
                    app_failures = http_probe(base)
                    checks, fuzz, api_steps = run_checks(env, base, seed, n, temp)
                    failures.extend(checks)
                    if previous_fitness is not None and fuzz.get("fitness") is not None and fuzz["fitness"] < previous_fitness:
                        failures.append(f"fuzz fitness dropped: {previous_fitness} -> {fuzz['fitness']}")
                    if fuzz.get("fitness") is not None:
                        previous_fitness = fuzz["fitness"]
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                    log.close()
                if any(x in server_log.read_text(encoding="utf-8", errors="replace") for x in ("Traceback", "ERROR")):
                    app_failures.append("server log contains ERROR or traceback; inspect iteration temp logs (not retained)")
            except Exception as exc:
                infrastructure_failures.append(f"iteration setup error: {type(exc).__name__}: {exc}")
                fuzz = {"seed": seed, "n": 0, "fitness": None, "violations": -1}

        totals["iterations"] += 1
        case_count = n + 10 + fuzz.get("api_steps", 0) if fuzz.get("n", 0) else 0
        totals["cases"] += case_count
        if failures or app_failures or fuzz.get("violations", 1) > 0:
            clean_streak = 0
            saw_failure = True
        else:
            clean_streak += 1
        report = write_report(iteration, seed, case_count, fuzz, failures + infrastructure_failures, app_failures)
        append_bugs(failures + app_failures, seed, iteration)
        print(f"iteration={iteration} seed={seed} cases={case_count} violations={fuzz.get('violations')} report={report.relative_to(ROOT)}")
        if infrastructure_failures:
            stop_reason = "runtime environment unavailable"
            saw_failure = True
            break
        totals["fixed"], totals["open"], exhausted = bug_summary()
        if exhausted >= 3:
            stop_reason = "three bugs exhausted their fix attempts"
            break
        if clean_streak >= 3:
            stop_reason = "three consecutive clean full iterations"
            break
        if time.monotonic() - started >= budget:
            stop_reason = "time budget"
            break

    totals["fixed"], totals["open"], _ = bug_summary()
    print(json.dumps({**totals, "stop_reason": stop_reason, "smoke": args.smoke}, sort_keys=True))
    return 0 if not saw_failure and totals["iterations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
