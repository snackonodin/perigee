"""tools/ops shell scripts, run against throwaway git repos in tmp_path.

Regression: check_merge.sh once reported "tests=FAIL(0f/0e/0p) (no summary)" when it
picked a python without pytest; it must now stop with a clear error (exit 2), and when
pytest prints no summary it must show the tail of pytest's output.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from csi_core.config import ROOT

OPS = ROOT / "tools" / "ops"
VENV = Path(sys.executable).parent.parent  # the venv running these tests
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo with space"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "tools/ops").mkdir(parents=True)
    for name in ("_lib.sh", "check_merge.sh", "merge_ready.sh", "metrics.sh", "board.py",
                 "lessons.py"):
        shutil.copy2(OPS / name, r / "tools/ops" / name)
    _write(r / ".gitignore", "local.flag\n__pycache__/\n")
    _write(r / "pkg/__init__.py", "")
    _write(r / "pkg/x.py", "X = 1\n")
    # a warning in the summary line, like the real suite's StarletteDeprecationWarning
    _write(r / "tests/test_a.py",
           "import warnings\n\n\ndef test_ok():\n    warnings.warn('w', DeprecationWarning)\n")
    _write(r / "docs/ops/board.yaml",
           "owners:\n  f4: {session: s-f4, branches: [feat/csi-core]}\n"
           "  cf: {session: s-cf, branches: [feat/surveys]}\ntasks:\n"
           "- {id: CORE-1, title: a, owner: f4, branch: feat/csi-core, state: review,"
           " blockers: [], done_when: x, sha: null}\n")
    _write(r / "docs/ops/lessons.yaml",
           "lessons:\n- {id: L1, created: '2026-11-11', surfaced: s, symptom: s, cause: c,"
           " guard: g, status: open}\n")
    _write(r / "pkg/y.py", "Y = [1,2]\n")  # unformatted on main
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    _git(r, "checkout", "-qb", "feat/csi-core")
    _write(r / "pkg/x.py", "X = 2\n")
    _write(r / "pkg/y.py", "Y = [1, 2]\n")  # the branch only reformats it (L3)
    _write(r / "tests/test_b.py",
           "from pathlib import Path\n\nfrom pkg.x import X\n\n\n"
           "def test_local():\n    assert not (X == 2 and Path('local.flag').exists())\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "CORE-1: x2")
    _git(r, "checkout", "-q", "main")
    return r


def _run(repo: Path, script: str, *args: str, venv: Path = VENV,
         extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "BASE_BRANCH")}
    env["VENV"] = str(venv)
    env.update(extra_env or {})
    return subprocess.run(["bash", str(repo / "tools/ops" / script), *args], cwd=repo, env=env,
                          capture_output=True, text=True, timeout=120)


def _fake_venv(tmp_path: Path, body: str) -> Path:
    v = tmp_path / "fakevenv"
    _write(v / "bin/python", "#!/bin/sh\n" + body)
    (v / "bin/python").chmod(0o755)
    return v


def test_check_merge_ok_parses_summary_with_warnings(repo: Path) -> None:
    p = _run(repo, "check_merge.sh", "feat/csi-core")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "MERGE OK feat/csi-core" in p.stdout
    assert "tests=pass(2) (2 passed, 1 warning" in p.stdout
    assert _git(repo, "worktree", "list").count("\n") == 0  # scratch worktree removed


def test_check_merge_python_without_pytest_is_an_error_not_a_test_failure(
    repo: Path, tmp_path: Path
) -> None:
    fake = _fake_venv(tmp_path, "exit 1\n")
    p = _run(repo, "check_merge.sh", "feat/csi-core", venv=fake)
    assert p.returncode == 2
    assert "has no pytest" in p.stderr
    assert "MERGE FAIL" not in p.stdout


def test_check_merge_no_summary_prints_tail(repo: Path, tmp_path: Path) -> None:
    fake = _fake_venv(tmp_path, 'case "$*" in *"import pytest"*) exit 0;; esac\n'
                                "echo 'collection exploded: boom-marker'\nexit 1\n")
    p = _run(repo, "check_merge.sh", "feat/csi-core", venv=fake)
    assert p.returncode == 1
    assert "tests=ERROR(no summary)" in p.stdout
    assert "boom-marker" in p.stdout


def test_check_merge_reports_conflict(repo: Path) -> None:
    _write(repo / "pkg/x.py", "X = 3\n")
    _git(repo, "commit", "-qam", "conflicting")
    p = _run(repo, "check_merge.sh", "feat/csi-core")
    assert p.returncode == 1
    assert "MERGE CONFLICT" in p.stdout and "pkg/x.py" in p.stdout


def test_merge_ready_green_moves_board_and_broadcasts(repo: Path) -> None:
    p = _run(repo, "merge_ready.sh", "feat/csi-core")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "MERGED feat/csi-core" in p.stdout
    assert "BROADCAST: main moved to" in p.stdout
    board = (repo / "docs/ops/board.yaml").read_text()
    assert "state: done" in board
    assert _git(repo, "status", "--porcelain") == ""
    assert _git(repo, "log", "-1", "--format=%s").startswith("board: CORE-1 → done")


def _add_flaky_test(repo: Path) -> None:
    """On the branch: a test that passes on its first run (check_merge's dry run) and
    fails on every later run (merge_ready's check of the merge commit): a flaky test."""
    _git(repo, "checkout", "-q", "feat/csi-core")
    _write(repo / "tests/test_flaky.py",
           "import os\nfrom pathlib import Path\n\n\ndef test_flaky():\n"
           "    p = Path(os.environ['FLAKY_COUNTER'])\n"
           "    n = int(p.read_text()) if p.exists() else 0\n"
           "    p.write_text(str(n + 1))\n    assert n == 0\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "CORE-1: flaky test")
    _git(repo, "checkout", "-q", "main")


def test_merge_ready_red_after_merge_auto_reverts_and_records_lesson(
    repo: Path, tmp_path: Path
) -> None:
    _add_flaky_test(repo)
    env = {"FLAKY_COUNTER": str(tmp_path / "counter")}
    p = _run(repo, "merge_ready.sh", "feat/csi-core", extra_env=env)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "REVERTED" in p.stdout and "test_flaky" in p.stdout
    assert "git revert --no-edit" in p.stdout
    assert (repo / "pkg/x.py").read_text() == "X = 1\n"
    subjects = _git(repo, "log", "--format=%s", "-4").splitlines()
    assert subjects[0].startswith("lessons: stub for reverted merge of feat/csi-core")
    assert subjects[2].startswith('Revert "Merge feat/csi-core')
    assert "state: doing" in (repo / "docs/ops/board.yaml").read_text()
    assert "LESSON: stub added" in p.stdout
    lessons = yaml.safe_load((repo / "docs/ops/lessons.yaml").read_text())["lessons"]
    stub = lessons[-1]
    assert stub["id"] == "L2" and stub["status"] == "open"
    assert stub["key"] == "red:tests/test_flaky.py::test_flaky"
    assert stub["origin"]["branch"] == "feat/csi-core" and stub["origin"]["source"] == "merge_ready"
    assert stub["origin"]["failing"] == ["FAILED tests/test_flaky.py::test_flaky"]
    assert "L2" in (repo / "docs/ops/LESSONS.md").read_text()
    assert _git(repo, "status", "--porcelain") == ""

    # the owner re-applies per PROTOCOL §3 (git won't re-merge reverted commits); the same
    # failure again is a recurrence of L2, not a new lesson
    revert_sha = _git(repo, "log", "-1", "--format=%h", "--grep=^Revert ")
    _git(repo, "checkout", "-q", "feat/csi-core")
    _git(repo, "rebase", "-q", "main")
    _git(repo, "revert", "--no-edit", revert_sha)
    _git(repo, "checkout", "-q", "main")
    (tmp_path / "counter").unlink()
    p = _run(repo, "merge_ready.sh", "feat/csi-core", extra_env=env)
    assert p.returncode == 1, p.stdout + p.stderr
    lessons = yaml.safe_load((repo / "docs/ops/lessons.yaml").read_text())["lessons"]
    assert [le["id"] for le in lessons] == ["L1", "L2"]
    assert len(lessons[-1]["recurrences"]) == 1


def test_merge_ready_ignores_untracked_files_in_main(repo: Path) -> None:
    """L1: untracked or ignored files in main's checkout must not decide a merge."""
    (repo / "local.flag").write_text("")  # ignored file: test_local fails if it is seen
    _write(repo / "junk/broken.py", "def (:\n")  # untracked, not even valid python
    _write(repo / "tests/test_untracked.py", "def test_x():\n    assert False\n")
    shutil.copy2(repo / ".gitignore", repo / ".gitignore.bak")
    with (repo / ".git/info/exclude").open("a") as fh:  # keep main 'clean' for the dirty check
        fh.write("junk/\ntests/test_untracked.py\n.gitignore.bak\n")
    p = _run(repo, "merge_ready.sh", "feat/csi-core")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "MERGED feat/csi-core" in p.stdout


def test_check_merge_warns_on_reformat_outside_ownership(repo: Path) -> None:
    """L3: pkg/y.py is only reformatted on the branch; pkg/x.py has a real change."""
    p = _run(repo, "check_merge.sh", "feat/csi-core")
    assert p.returncode == 0, p.stdout + p.stderr
    block = p.stdout.split("WARN  reformat-only changes outside owned paths")[1]
    block = block.split("WARN  outside owned paths")[0]
    assert "pkg/y.py" in block and "pkg/x.py" not in block


def test_merge_ready_refuses_dirty_main(repo: Path) -> None:
    (repo / "stray.txt").write_text("x")
    p = _run(repo, "merge_ready.sh", "feat/csi-core")
    assert p.returncode == 1 and "dirty" in p.stdout
    assert _git(repo, "rev-list", "--count", "main") == "1"


def test_metrics_reports_lessons(repo: Path, tmp_path: Path) -> None:
    _add_flaky_test(repo)
    _run(repo, "merge_ready.sh", "feat/csi-core",
         extra_env={"FLAKY_COUNTER": str(tmp_path / "counter")})  # RED: adds lesson L2
    p = _run(repo, "metrics.sh")
    assert p.returncode == 0, p.stdout + p.stderr
    assert "reverts=1" in p.stdout
    assert ("lessons: lessons=2 open=2 closed=0 recurrences=0 recurred=0 "
            "mean_hours_to_guard=None") in p.stdout


# ---------------------------------------------------------------- LOOP-2: frontend checks

FAKE_NPM = """#!/bin/sh
# fake npm: `npm ci ...` builds node_modules in cwd and logs the call
echo "npm $* @ $(pwd)" >> "$FAKE_LOG"
[ -n "$FAKE_NPM_MISS" ] && { echo "npm error code ENOTCACHED" >&2; exit 1; }
mkdir -p node_modules/.bin && echo ok > node_modules/marker
"""

FAKE_NPX = """#!/bin/sh
# fake npx: `npx --no-install tsc|vitest ...`, run in frontend/
echo "npx $* @ $(pwd)" >> "$FAKE_LOG"
[ -f node_modules/marker ] || { echo "node_modules missing" >&2; exit 1; }
case "$2" in
  tsc)
    if grep -rl TYPE_ERROR src >/dev/null 2>&1; then
      f=$(grep -rl TYPE_ERROR src | head -1); echo "$f(1,1): error TS2322: bad type"; exit 2; fi ;;
  vitest)
    if grep -rl TEST_FAIL src >/dev/null 2>&1; then
      f=$(grep -rl TEST_FAIL src | head -1); echo " FAIL  $f > it breaks"; exit 1; fi
    if [ -n "$FLAKY_COUNTER" ] && grep -rl FLAKY src >/dev/null 2>&1; then
      n=$(cat "$FLAKY_COUNTER" 2>/dev/null || echo 0); echo $((n + 1)) > "$FLAKY_COUNTER"
      if [ "$n" -gt 0 ]; then echo " FAIL  src/flaky.test.tsx > flaky"; exit 1; fi
    fi
    echo " Tests  1 passed (1)" ;;
esac
"""


@pytest.fixture()
def fe_env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "fakebin"
    _write(bin_dir / "npm", FAKE_NPM)
    _write(bin_dir / "npx", FAKE_NPX)
    for f in ("npm", "npx"):
        (bin_dir / f).chmod(0o755)
    return {"NPM": str(bin_dir / "npm"), "NPX": str(bin_dir / "npx"),
            "FAKE_LOG": str(tmp_path / "fake.log"), "ASTRO_NODE_CACHE": str(tmp_path / "nodecache")}


def _frontend_branch(repo: Path, name: str, extra: dict[str, str] | None = None) -> None:
    _git(repo, "checkout", "-q", "-b", name, "main")
    _write(repo / "frontend/package.json", '{"name": "fe", "private": true}\n')
    _write(repo / "frontend/package-lock.json", '{"lockfileVersion": 3}\n')
    _write(repo / "frontend/src/ok.test.tsx", "// fine\n")
    for path, text in (extra or {}).items():
        _write(repo / path, text)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"{name}: frontend")
    _git(repo, "checkout", "-q", "main")


def _log(env: dict[str, str]) -> list[str]:
    p = Path(env["FAKE_LOG"])
    return p.read_text().splitlines() if p.exists() else []


def test_check_merge_skips_frontend_when_untouched(repo: Path, fe_env: dict[str, str]) -> None:
    p = _run(repo, "check_merge.sh", "feat/csi-core", extra_env=fe_env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "frontend=n/a" in p.stdout
    assert _log(fe_env) == []


def test_check_merge_runs_frontend_with_cache_outside_repo(
    repo: Path, fe_env: dict[str, str]
) -> None:
    _frontend_branch(repo, "feat/frontend")
    p = _run(repo, "check_merge.sh", "feat/frontend", extra_env=fe_env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "frontend=pass" in p.stdout and "MERGE OK feat/frontend" in p.stdout
    log = _log(fe_env)
    assert [line.split(" @ ")[0] for line in log] == [
        "npm ci --ignore-scripts --offline --no-audit --no-fund",
        "npx --no-install tsc --noEmit",
        "npx --no-install vitest run",
    ]
    cache = Path(fe_env["ASTRO_NODE_CACHE"])
    (key_dir,) = [d for d in cache.iterdir() if not d.name.startswith(".")]
    assert len(key_dir.name) == 64 and (key_dir / "node_modules/marker").exists()
    assert not (repo / "frontend").exists()  # nothing written into the main checkout
    # same lockfile: the cached node_modules is reused, npm ci does not run again
    p = _run(repo, "check_merge.sh", "feat/frontend", extra_env=fe_env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert sum(line.startswith("npm ci") for line in _log(fe_env)) == 1


@pytest.mark.parametrize("marker,res,shown", [
    ("TYPE_ERROR", "FAIL(tsc)", "error TS2322"),
    ("TEST_FAIL", "FAIL(vitest)", "FAIL  src/bad.test.tsx"),
])
def test_check_merge_fails_on_frontend_errors(
    repo: Path, fe_env: dict[str, str], marker: str, res: str, shown: str
) -> None:
    _frontend_branch(repo, "feat/frontend", {"frontend/src/bad.test.tsx": f"// {marker}\n"})
    p = _run(repo, "check_merge.sh", "feat/frontend", extra_env=fe_env)
    assert p.returncode == 1, p.stdout + p.stderr
    assert f"frontend={res}" in p.stdout and shown in p.stdout
    assert "MERGE FAIL feat/frontend" in p.stdout


def test_check_merge_offline_npm_ci_miss_is_a_clear_failure(
    repo: Path, fe_env: dict[str, str]
) -> None:
    _frontend_branch(repo, "feat/frontend")
    p = _run(repo, "check_merge.sh", "feat/frontend", extra_env={**fe_env, "FAKE_NPM_MISS": "1"})
    assert p.returncode == 1, p.stdout + p.stderr
    assert "frontend=FAIL(npm ci)" in p.stdout
    assert "Run `npm ci` in frontend/ once" in p.stdout
    cache = Path(fe_env["ASTRO_NODE_CACHE"])
    assert not [d for d in cache.iterdir() if not d.name.startswith(".")]  # no half-built cache


def test_merge_ready_frontend_red_reverts_and_records_lesson(
    repo: Path, fe_env: dict[str, str], tmp_path: Path
) -> None:
    _frontend_branch(repo, "feat/frontend", {"frontend/src/flaky.test.tsx": "// FLAKY\n"})
    env = {**fe_env, "FLAKY_COUNTER": str(tmp_path / "counter")}
    p = _run(repo, "merge_ready.sh", "feat/frontend", extra_env=env)
    assert p.returncode == 1, p.stdout + p.stderr
    assert "RED: tests=pass" in p.stdout and "frontend=FAIL(vitest)" in p.stdout
    assert "REVERTED" in p.stdout
    assert not (repo / "frontend").exists()  # the revert removed it from main
    lessons = yaml.safe_load((repo / "docs/ops/lessons.yaml").read_text())["lessons"]
    stub = lessons[-1]
    assert stub["key"] == "red:frontend:vitest:src/flaky.test.tsx"
    assert "frontend=FAIL(vitest)" in stub["symptom"]
    assert stub["origin"]["failing"] == ["FAIL  src/flaky.test.tsx > flaky"]


def test_merge_ready_green_with_frontend(repo: Path, fe_env: dict[str, str]) -> None:
    _frontend_branch(repo, "feat/frontend")
    p = _run(repo, "merge_ready.sh", "feat/frontend", extra_env=fe_env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "MERGED feat/frontend" in p.stdout and "frontend=pass" in p.stdout
