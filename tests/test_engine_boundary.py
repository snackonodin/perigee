"""Keep Context Engine scoring in its declared entry point."""

from __future__ import annotations

import ast
from pathlib import Path

from csi_core.config import ROOT


BACKEND_ROOT = ROOT / "backend"
DEMO_ROOT = ROOT / "waiwai1" / "demo"
ENGINE_PATH = (ROOT / "waiwai1" / "engine").resolve()


def _sources(roots):
    for root in roots:
        for path in root.rglob("*.py"):
            if ENGINE_PATH in path.resolve().parents:
                continue
            yield path
        for path in root.rglob("*.js"):
            yield path


def test_backend_and_demo_delegate_to_context_engine_run():
    def delegated(roots):
        calls = []
        for path in _sources(roots):
            if path.suffix != ".py":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            imported = any(
                isinstance(node, ast.ImportFrom) and node.module == "engine.api"
                and any(alias.name == "run" for alias in node.names)
                for node in ast.walk(tree)
            )
            called = any(
                isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "run"
                for node in ast.walk(tree)
            )
            if imported and called:
                calls.append(path)
        return calls

    assert delegated((BACKEND_ROOT,)), "main backend must call engine.api.run(payload)"
    assert delegated((DEMO_ROOT,)), "Context Engine demo must call engine.api.run(payload)"


def test_context_engine_constants_and_state_math_are_not_copied_into_app():
    forbidden = ("cusum_s_t + z - 0.5", "1.4826 * max(mad, 0.40)")
    for path in _sources((BACKEND_ROOT, DEMO_ROOT)):
        source = path.read_text(encoding="utf-8")
        for snippet in forbidden:
            assert snippet not in source, f"Context Engine math copied into {path}: {snippet}"
