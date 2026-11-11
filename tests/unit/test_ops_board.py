"""tools/ops/board.py: validation, next-task selection, move, render, CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from csi_core.config import ROOT
from tools.ops import board


def _board(*tasks: dict) -> dict:
    owners = {o: {"session": f"s-{o}", "branches": [f"feat/{o}"]} for o in ("f4", "b0")}
    rows = []
    for t in tasks:
        row = {"title": "t", "branch": f"feat/{t['owner']}", "blockers": [], "done_when": "x",
               "sha": None, **t}
        rows.append(row)
    return {"owners": owners, "tasks": rows}


def test_repo_board_is_valid() -> None:
    data = board.load(file=ROOT / "docs/ops/board.yaml")
    assert board.validate(data) == []
    ids = [t["id"] for t in data["tasks"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    ("task", "msg"),
    [
        ({"id": "A-1", "owner": "f4", "state": "nope"}, "bad state"),
        ({"id": "A-1", "owner": "zz", "state": "todo"}, "unknown owner"),
        ({"id": "A-1", "owner": "f4", "state": "todo", "blockers": ["B-9"]}, "not a task"),
        ({"id": "A-1", "owner": "f4", "state": "todo", "blockers": ["A-1"]}, "blocks itself"),
    ],
)
def test_validate_rejects(task: dict, msg: str) -> None:
    errs = board.validate(_board(task))
    assert any(msg in e for e in errs), errs


def test_validate_rejects_duplicates_and_missing_keys() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "todo"},
                  {"id": "A-1", "owner": "f4", "state": "todo"})
    del data["tasks"][1]["done_when"]
    errs = board.validate(data)
    assert any("duplicate" in e for e in errs)
    assert any("missing `done_when`" in e for e in errs)


def test_next_resumes_doing_first() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "todo"},
                  {"id": "A-2", "owner": "f4", "state": "doing"})
    t, why = board.next_task(data, "f4")
    assert (t["id"], why) == ("A-2", "resume")


def test_next_skips_blocked_and_other_owners() -> None:
    data = _board({"id": "B-1", "owner": "b0", "state": "todo"},
                  {"id": "A-1", "owner": "f4", "state": "todo", "blockers": ["B-1"]},
                  {"id": "A-2", "owner": "f4", "state": "todo"})
    t, _ = board.next_task(data, "f4")
    assert t["id"] == "A-2"


def test_next_done_blocker_is_satisfied() -> None:
    data = _board({"id": "B-1", "owner": "b0", "state": "done"},
                  {"id": "A-1", "owner": "f4", "state": "todo", "blockers": ["B-1"]})
    assert board.next_task(data, "f4")[0]["id"] == "A-1"


def test_same_owner_review_blocker_counts_but_other_owner_review_does_not() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "review"},
                  {"id": "B-1", "owner": "b0", "state": "review"},
                  {"id": "A-2", "owner": "f4", "state": "todo", "blockers": ["A-1"]},
                  {"id": "A-3", "owner": "f4", "state": "todo", "blockers": ["B-1"]})
    assert board.next_task(data, "f4")[0]["id"] == "A-2"
    data["tasks"][2]["state"] = "done"
    t, why = board.next_task(data, "f4")
    assert t is None and "A-3 waits on B-1" in why


def test_exclude_advances_past_just_reported_task() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "doing"},
                  {"id": "A-2", "owner": "f4", "state": "todo", "blockers": ["A-1"]})
    assert board.next_task(data, "f4")[0]["id"] == "A-1"
    assert board.next_task(data, "f4", {"A-1"})[0]["id"] == "A-2"


def test_external_blocker_never_satisfied() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "todo",
                   "blockers": ["user supplies scripts"]})
    t, why = board.next_task(data, "f4")
    assert t is None and "user supplies scripts" in why


def test_move_sets_state_sha_and_time() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "review"})
    t = board.move(data, "A-1", "done", sha="abc1234", now="2026-01-01T00:00:00Z")
    assert (t["state"], t["sha"], t["times"]["done"]) == ("done", "abc1234",
                                                         "2026-01-01T00:00:00Z")
    with pytest.raises(board.BoardError):
        board.move(data, "A-1", "finished")
    with pytest.raises(board.BoardError):
        board.move(data, "Z-9", "done")


def test_save_roundtrip_and_refuses_invalid(tmp_path: Path) -> None:
    f = tmp_path / "board.yaml"
    data = _board({"id": "A-1", "owner": "f4", "state": "todo"})
    board.save(data, f)
    assert f.read_text().startswith("# Task board")
    assert board.load(file=f) == data
    data["tasks"][0]["state"] = "bogus"
    with pytest.raises(board.BoardError):
        board.save(data, f)
    assert board.load(file=f)["tasks"][0]["state"] == "todo"


def test_render_has_every_state_and_escapes_pipes() -> None:
    data = _board({"id": "A-1", "owner": "f4", "state": "todo", "title": "a | b"},
                  {"id": "A-2", "owner": "f4", "state": "done", "sha": "abc1234"})
    md = board.render(data)
    for state in board.STATES:
        assert f"## {state} (" in md
    assert "a \\| b" in md
    assert "GENERATED" in md


def test_owner_branches_supports_list_and_legacy() -> None:
    assert board.owner_branches({"branches": ["a", "b"]}) == ["a", "b"]
    assert board.owner_branches({"branch": "a"}) == ["a"]
    assert board.owner_branches({}) == []


def test_cli_next_move_render(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "board.yaml"
    board.save(_board({"id": "A-1", "owner": "f4", "state": "todo"},
                      {"id": "A-2", "owner": "f4", "state": "todo", "blockers": ["A-1"]}), f)
    assert board.main(["--file", str(f), "list", "--owner", "f4", "--next"]) == 0
    assert capsys.readouterr().out.startswith("next: A-1")
    assert board.main(["--file", str(f), "move", "A-1", "review", "--sha", "abc1234"]) == 0
    capsys.readouterr()
    assert board.main(["--file", str(f), "list", "--owner", "f4", "--next"]) == 0
    assert capsys.readouterr().out.startswith("next: A-2")
    assert board.main(["--file", str(f), "list", "--owner", "b0", "--next"]) == 3
    assert board.main(["--file", str(f), "render"]) == 0
    assert (tmp_path / "BOARD.md").exists()
    saved = yaml.safe_load(f.read_text())
    assert saved["tasks"][0]["sha"] == "abc1234"


def test_diff_count_counts_changed_added_removed() -> None:
    a = _board({"id": "A-1", "owner": "f4", "state": "todo"},
               {"id": "A-2", "owner": "f4", "state": "todo"})
    b = _board({"id": "A-1", "owner": "f4", "state": "review"},
               {"id": "A-3", "owner": "f4", "state": "todo"})
    assert board.diff_count(a, a) == 0
    assert board.diff_count(a, b) == 3


def test_list_warns_on_uncommitted_moves(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    committed = _board({"id": "A-1", "owner": "f4", "state": "todo"})
    local = _board({"id": "A-1", "owner": "f4", "state": "review"})

    def fake_load(file=None, ref=None):
        return committed if ref else local

    monkeypatch.setattr(board, "load", fake_load)
    assert board.main(["list", "--owner", "f4"]) == 0
    out = capsys.readouterr()
    assert "uncommitted moves: 1" in out.err and "todo" in out.out
    assert board.main(["list", "--worktree", "--owner", "f4"]) == 0
    out = capsys.readouterr()
    assert "review" in out.out and "uncommitted" not in out.err
