"""tools/ops/lessons.py: lessons.yaml source of truth, guard-checked close, render, stats."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tools.ops import lessons as L


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / "docs/ops/prompts").mkdir(parents=True)
    (r / "tests/unit").mkdir(parents=True)
    (r / "tests/unit/test_guard.py").write_text("def test_it_holds():\n    assert True\n")
    (r / "pyproject.toml").write_text('[tool.ruff]\nextend-exclude = ["junk"]\n')
    (r / "config.yaml").write_text("baseline:\n  mad_floor: 0.5\n")
    rule = "- Format only files you changed (L3).\n"
    (r / "docs/ops/prompts/worker.md").write_text("## Rules\n" + rule)
    (r / "notes.md").write_text("- Format only files you changed (L3).\n")
    L.save({"lessons": [{"id": "L1", "created": "2026-11-11T00:00:00Z", "surfaced": "s",
                         "symptom": "x", "cause": "c", "guard": "g", "status": "open"}]},
           r / L.REL)
    return r


def _file(repo: Path) -> Path:
    return repo / L.REL


def test_add_numbers_and_records_origin(repo: Path) -> None:
    data = L.load(_file(repo))
    le, created = L.add(data, surfaced="merge_ready (X-1)", symptom="RED", key="red:t::a",
                        source="merge_ready", branch="feat/x", sha="abc1234",
                        failing=["FAILED t::a"], now="2026-11-12T10:00:00Z")
    assert created and le["id"] == "L2" and le["status"] == "open"
    assert le["origin"] == {"at": "2026-11-12T10:00:00Z", "source": "merge_ready",
                            "branch": "feat/x", "sha": "abc1234", "failing": ["FAILED t::a"]}
    assert "TODO" in le["cause"] and "TODO" in le["guard"]


def test_same_key_is_a_recurrence_and_reopens_a_closed_lesson(repo: Path) -> None:
    data = L.load(_file(repo))
    le, _ = L.add(data, surfaced="s", symptom="flaky", key="flaky:t::b", source="stress")
    L.close(data, le["id"], ["test:tests/unit/test_guard.py::test_it_holds"], repo)
    again, created = L.add(data, surfaced="s", symptom="flaky", key="flaky:t::b",
                           source="stress", sha="def5678")
    assert not created and again is le
    assert le["status"] == "open" and le["reopened"]  # the guard did not hold
    assert le["recurrences"][0]["sha"] == "def5678"
    assert [x["id"] for x in data["lessons"]] == ["L1", "L2"]


@pytest.mark.parametrize("ref", [
    "test:tests/unit/test_guard.py",
    "test:tests/unit/test_guard.py::test_it_holds",
    "config:pyproject.toml:tool.ruff.extend-exclude",
    "config:config.yaml:baseline.mad_floor",
    "rule:docs/ops/prompts/worker.md:Format only files you changed (L3).",
])
def test_close_accepts_existing_guards(repo: Path, ref: str) -> None:
    data = L.load(_file(repo))
    le = L.close(data, "L1", [ref], repo, now="2026-11-11T05:00:00Z")
    assert le["status"] == "closed" and le["guard_refs"] == [ref]
    L.save(data, _file(repo))  # a closed lesson with refs validates


@pytest.mark.parametrize("ref,why", [
    ("test:tests/unit/test_missing.py", "not found"),
    ("test:tests/unit/test_guard.py::test_nope", "defines no test"),
    ("test:pkg/not_a_test.py", "not found under tests/"),
    ("config:pyproject.toml:tool.ruff.nope", "has no key"),
    ("config:config.yaml:baseline", None),  # a section is a key too: accepted below
    ("config:missing.toml:a", "not found"),
    ("rule:docs/ops/prompts/worker.md:a rule nobody wrote", "does not contain"),
    ("rule:notes.md:Format only files you changed (L3).", "rule refs must point at"),
    ("rule:docs/ops/prompts/worker.md:   ", "does not contain"),
    ("guess:anything", "unknown guard kind"),
])
def test_close_refuses_missing_guards(repo: Path, ref: str, why: str | None) -> None:
    data = L.load(_file(repo))
    if why is None:
        assert L.check_ref(ref, repo) is None
        return
    with pytest.raises(L.LessonError, match="refusing to close L1") as e:
        L.close(data, "L1", [ref], repo)
    assert why in str(e.value)
    assert data["lessons"][0]["status"] == "open"


def test_close_needs_a_guard_and_a_known_id(repo: Path) -> None:
    data = L.load(_file(repo))
    with pytest.raises(L.LessonError, match="at least one"):
        L.close(data, "L1", [], repo)
    with pytest.raises(L.LessonError, match="no lesson L9"):
        L.close(data, "L9", ["test:tests/unit/test_guard.py"], repo)


def test_validate_rejects_closed_without_refs_and_bad_ids() -> None:
    errs = L.validate({"lessons": [
        {"id": "L1", "created": "x", "surfaced": "s", "symptom": "s", "cause": "c",
         "guard": "g", "status": "closed"},
        {"id": "X2", "created": "x", "surfaced": "s", "symptom": "s", "cause": "c",
         "guard": "g", "status": "weird"},
    ]})
    assert any("closed without guard_refs" in e for e in errs)
    assert any("id must look like" in e for e in errs)
    assert any("bad status" in e for e in errs)


def test_stats_and_render(repo: Path) -> None:
    data = L.load(_file(repo))
    L.close(data, "L1", ["config:config.yaml:baseline.mad_floor"], repo, now="2026-11-11T06:00:00Z")
    le, _ = L.add(data, surfaced="s", symptom="a | b", key="k", now="2026-11-11T07:00:00Z")
    L.add(data, surfaced="s", symptom="again", key="k")
    s = L.stats(data)
    assert s == {"lessons": 2, "open": 1, "closed": 1, "recurrences": 1, "recurred": 1,
                 "mean_hours_to_guard": 6.0}
    md = L.render(data)
    assert "2 lessons · 1 open · 1 closed · 1 recurrences · mean time to guard: 6.0 h" in md
    assert "## open (1)" in md and "## closed (1)" in md
    assert "a \\| b" in md  # pipes escaped in table cells
    assert "`config:config.yaml:baseline.mad_floor`" in md


def test_cli_add_close_render_and_exit_codes(repo: Path, capsys) -> None:
    f = str(_file(repo))
    assert L.main(["--file", f, "add", "--surfaced", "s", "--symptom", "boom", "--key", "k1"]) == 0
    assert "added L2" in capsys.readouterr().out
    assert L.main(["--file", f, "add", "--surfaced", "s", "--symptom", "boom", "--key", "k1"]) == 0
    assert "recurrence #1 of L2" in capsys.readouterr().out
    assert L.main(["--file", f, "close", "L2", "--guard", "test:tests/unit/nope.py"]) == 1
    assert "refusing to close L2" in capsys.readouterr().err
    assert L.main(["--file", f, "close", "L2", "--guard",
                   "test:tests/unit/test_guard.py::test_it_holds"]) == 0
    assert capsys.readouterr().out.startswith("closed L2: test:")
    md =(repo / "docs/ops/LESSONS.md").read_text()
    assert "## closed (1)" in md and "L2" in md
    saved = yaml.safe_load(_file(repo).read_text())
    assert saved["lessons"][1]["status"] == "closed"
    assert _file(repo).read_text().startswith("# Lessons: SOURCE OF TRUTH")
    assert L.main(["--file", f, "list", "--status", "open", "--format", "tsv"]) == 0
    assert capsys.readouterr().out.startswith("L1\topen\t")


def test_repo_lessons_file_is_valid_and_rendered() -> None:
    """The committed lessons.yaml validates, every closed guard still resolves, and
    LESSONS.md matches what render() produces (nobody hand-edited it)."""
    data = L.load()
    for le in data["lessons"]:
        for ref in le.get("guard_refs") or []:
            assert L.check_ref(ref, L.REPO) is None, (le["id"], ref)
    assert (L.REPO / "docs/ops/LESSONS.md").read_text(encoding="utf-8") == L.render(data)
