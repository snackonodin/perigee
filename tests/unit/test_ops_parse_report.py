"""tools/ops/parse_report.py: the one accepted worker report format."""

from __future__ import annotations

import pytest

from tools.ops import parse_report as pr

GOOD = "[f4] CORE-3 review sha=20abffa tests=pass ruff=pass — read_rotating + capture_stats"


def test_valid_line_parses() -> None:
    r = pr.parse(GOOD)
    assert r is not None
    assert (r.owner, r.id, r.status, r.sha, r.tests, r.ruff) == (
        "f4", "CORE-3", "review", "20abffa", "pass", "pass")
    assert r.note == "read_rotating + capture_stats"
    assert r.mergeable
    assert r.board_cmd == "tools/ops/board.py move CORE-3 review --sha 20abffa"
    assert pr.explain(GOOD) == ""


@pytest.mark.parametrize("owner", ["f4", "b0", "7a", "cf", "ops"])
@pytest.mark.parametrize("status", ["review", "blocked", "question"])
def test_all_owners_and_statuses(owner: str, status: str) -> None:
    assert pr.parse(f"[{owner}] X-1 {status} sha=abcdef0 tests=fail ruff=pass — n")


def test_blocked_is_not_mergeable_and_maps_to_doing() -> None:
    r = pr.parse("[b0] DB-5 blocked sha=2a0a12e tests=pass ruff=pass — blocked on CORE-7")
    assert r is not None and not r.mergeable
    assert r.board_cmd == "tools/ops/board.py move DB-5 doing"


def test_failing_review_is_not_mergeable() -> None:
    r = pr.parse("[cf] SUR-4 review sha=abcdef0 tests=fail ruff=pass — wip")
    assert r is not None and not r.mergeable


@pytest.mark.parametrize(
    ("line", "field"),
    [
        ("[ca] CORE-3 review sha=20abffa tests=pass ruff=pass — x", "owner"),
        ("[f4] core-3 review sha=20abffa tests=pass ruff=pass — x", "id"),
        ("[f4] CORE-3 done sha=20abffa tests=pass ruff=pass — x", "status"),
        ("[f4] CORE-3 review sha=20ABFFA tests=pass ruff=pass — x", "sha"),
        ("[f4] CORE-3 review sha=20abf tests=pass ruff=pass — x", "sha"),
        ("[f4] CORE-3 review sha=20abffa tests=pass(27) ruff=pass — x", "tests"),
        ("[f4] CORE-3 review sha=20abffa tests=pass ruff=ok — x", "ruff"),
        ("[f4] CORE-3 review sha=20abffa tests=pass ruff=pass - x", "note"),
        ("[f4] CORE-3 review sha=20abffa tests=pass ruff=pass — ", "note"),
        ("[f4] CORE-3 review sha=20abffa tests=pass ruff=pass — " + "x" * 101, "note"),
    ],
)
def test_invalid_lines_name_the_bad_field(line: str, field: str) -> None:
    assert pr.parse(line) is None
    assert pr.explain(line).startswith(f"bad {field}")


def test_trailing_newline_ok_but_extra_text_not() -> None:
    assert pr.parse(GOOD + "\n")
    assert pr.parse("hi " + GOOD) is None


def test_board_check_owner_mismatch() -> None:
    r = pr.parse(GOOD)
    assert r is not None
    assert pr.check_board(r, {"CORE-3": {"owner": "f4"}}) == ""
    assert "belongs to b0" in pr.check_board(r, {"CORE-3": {"owner": "b0"}})
    assert "not on the board" in pr.check_board(r, {})


def test_cli_exit_codes(capsys: pytest.CaptureFixture[str]) -> None:
    assert pr.main([GOOD]) == 0
    assert "OK f4 CORE-3" in capsys.readouterr().out
    assert pr.main([GOOD, "garbage"]) == 1
    assert "INVALID" in capsys.readouterr().out
