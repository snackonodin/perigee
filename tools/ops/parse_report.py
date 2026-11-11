#!/usr/bin/env python3
"""Validate worker report lines (PROTOCOL §1). The one accepted format:

  [<owner>] <ID> <status> sha=<hex7+> tests=<pass|fail> ruff=<pass|fail> — <note, 1-100 chars>

  owner  f4 | b0 | 7a | cf | ops        status  review | blocked | question
  The separator before the note is an em dash (—) with one space either side.

Usage:
  parse_report.py "<line>" ...      or lines on stdin
  --board        also check the ID exists on the board and belongs to <owner>
  --json         print parsed fields as JSON
Prints, per valid line, the board command the coordinator runs next
(e.g. `tools/ops/board.py move CORE-3 review --sha 1a2b3c4`).
Exit: 0 all valid · 1 any invalid. Standard library only (PyYAML for --board).
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass

REPORT_RE = re.compile(
    r"^\[(?P<owner>f4|b0|7a|cf|ops)\] (?P<id>[A-Z]+-\d+) (?P<status>review|blocked|question)"
    r" sha=(?P<sha>[0-9a-f]{7,40}) tests=(?P<tests>pass|fail) ruff=(?P<ruff>pass|fail)"
    r" — (?P<note>.{1,100})$"
)
# Same pattern as a plain string, for copying into prompts and other tools.
REPORT_PATTERN = REPORT_RE.pattern

_PARTS = [
    ("owner", re.compile(r"^\[(f4|b0|7a|cf|ops)\] "), "start with [f4|b0|7a|cf|ops] and a space"),
    ("id", re.compile(r"^[A-Z]+-\d+ "), "task ID like CORE-3, then a space"),
    ("status", re.compile(r"^(review|blocked|question) "), "status review|blocked|question"),
    ("sha", re.compile(r"^sha=[0-9a-f]{7,40} "), "sha=<7-40 lowercase hex>"),
    ("tests", re.compile(r"^tests=(pass|fail) "), "tests=pass|fail (no counts)"),
    ("ruff", re.compile(r"^ruff=(pass|fail) "), "ruff=pass|fail"),
    ("note", re.compile(r"^— .{1,100}$"), "' — ' (em dash) then a 1-100 char note"),
]


def _out(*parts: object, file=None) -> None:
    """CLI output (the project bans print(); see ruff T20)."""
    (file or sys.stdout).write(" ".join(str(p) for p in parts) + "\n")


@dataclass(frozen=True)
class Report:
    owner: str
    id: str
    status: str
    sha: str
    tests: str
    ruff: str
    note: str

    @property
    def board_cmd(self) -> str:
        state = "review" if self.status == "review" else "doing"
        sha = f" --sha {self.sha}" if self.status == "review" else ""
        return f"tools/ops/board.py move {self.id} {state}{sha}"

    @property
    def mergeable(self) -> bool:
        return self.status == "review" and self.tests == "pass" and self.ruff == "pass"


def parse(line: str) -> Report | None:
    m = REPORT_RE.match(line.rstrip("\r\n"))
    return Report(**m.groupdict()) if m else None


def explain(line: str) -> str:
    """Say which field first breaks the format (empty string if the line is valid)."""
    s = line.rstrip("\r\n")
    if parse(s):
        return ""
    rest = s
    for name, rx, hint in _PARTS:
        m = rx.match(rest)
        if not m:
            return f"bad {name}: expected {hint}; got {rest[:30]!r}"
        rest = rest[m.end():]
    return "line does not match the report format"


def check_board(r: Report, tasks: dict[str, dict]) -> str:
    t = tasks.get(r.id)
    if t is None:
        return f"{r.id} is not on the board"
    if t["owner"] != r.owner:
        return f"{r.id} belongs to {t['owner']}, not {r.owner}"
    return ""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    use_board = "--board" in args
    as_json = "--json" in args
    lines = [a for a in args if a not in ("--board", "--json")]
    if any(a in ("-h", "--help") for a in lines):
        _out(__doc__)
        return 0
    if not lines:
        lines = [x for x in sys.stdin.read().splitlines() if x.strip()]
    tasks: dict[str, dict] = {}
    if use_board:
        sys.path.insert(0, __file__.rsplit("/", 1)[0])
        import board

        tasks = board.by_id(board._load_for_list(_NS()))
    bad = 0
    for ln in lines:
        r = parse(ln)
        err = explain(ln) if r is None else (check_board(r, tasks) if use_board else "")
        if err:
            bad += 1
            _out(f"INVALID {err} :: {ln[:80]}")
            continue
        assert r is not None
        if as_json:
            _out(json.dumps({**asdict(r), "board_cmd": r.board_cmd, "mergeable": r.mergeable}))
        else:
            _out(f"OK {r.owner} {r.id} {r.status} mergeable={str(r.mergeable).lower()} "
                  f"→ {r.board_cmd}")
    return 1 if bad else 0


class _NS:  # minimal args object for board._load_for_list
    file = None
    ref = None


if __name__ == "__main__":
    sys.exit(main())
