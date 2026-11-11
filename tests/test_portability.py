"""The app must run on any device: no machine-specific paths in tracked files."""

import re
import subprocess

import pytest

from csi_core.config import ROOT, get_config, resolve_estimator

FORBIDDEN = re.compile(
    r"(/Users/|/home/[a-z]|[A-Za-z]:\\\\Users|GoogleDrive|CloudStorage|astro-worktrees|\.venvs/)"
)
CHECKED_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".json", ".sh", ".cfg", ".ini", ".example"}


def _tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [f for f in out.splitlines() if any(f.endswith(s) for s in CHECKED_SUFFIXES)]


def test_no_machine_specific_paths() -> None:
    offenders = []
    for rel in _tracked_files():
        if rel == "tests/test_portability.py":
            continue
        text = (ROOT / rel).read_text(errors="ignore")
        for n, line in enumerate(text.splitlines(), 1):
            if FORBIDDEN.search(line):
                offenders.append(f"{rel}:{n}: {line.strip()[:80]}")
    assert not offenders, "machine-specific paths found:\n" + "\n".join(offenders)


def test_estimator_specs_are_modules_not_paths() -> None:
    est = get_config().estimators
    for spec in (est.breath, est.heart, est.motion):
        assert "/" not in spec and "\\" not in spec and ":" in spec


def test_resolve_estimator_rejects_bad_specs() -> None:
    assert resolve_estimator("json:dumps")({"a": 1}) == '{"a": 1}'
    for bad in ("json", "json:", ":dumps", "json:not_there"):
        with pytest.raises(ValueError):
            resolve_estimator(bad)
