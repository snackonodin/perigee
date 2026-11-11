"""FR18: the self-harm item always shows the safety screen, synchronously."""

import pytest

from backend.schemas.contracts import SafetyResult
from backend.services import surveys


def _phq9_answers(item9: int) -> dict[str, int]:
    answers = {f"phq9_{i}": 0 for i in range(1, 9)}
    answers["phq9_9"] = item9
    return answers


def test_phq9_item9_is_the_only_trigger() -> None:
    phq9 = surveys.get_seed_instrument("phq9")
    triggers = {it["key"]: it["safety_trigger"] for it in phq9["items"] if "safety_trigger" in it}
    assert triggers == {"phq9_9": {"min_value": 1}}


@pytest.mark.parametrize("value", [1, 2, 3])
def test_item9_positive_shows_safety(value: int) -> None:
    res = surveys.safety_check(surveys.get_seed_instrument("phq9"), _phq9_answers(value))
    assert isinstance(res, SafetyResult)
    assert res.show is True
    assert res.reason
    joined = " ".join(res.resources).lower()
    assert "flight surgeon" in joined and "emergency number" in joined


def test_item9_zero_does_not_show() -> None:
    res = surveys.safety_check(surveys.get_seed_instrument("phq9"), _phq9_answers(0))
    assert res == SafetyResult(show=False)


def test_item9_alone_still_triggers() -> None:
    # Partial or otherwise invalid submissions must still trigger.
    res = surveys.safety_check(surveys.get_seed_instrument("phq9"), {"phq9_9": 1})
    assert res.show


def test_out_of_range_or_odd_value_triggers() -> None:
    phq9 = surveys.get_seed_instrument("phq9")
    assert surveys.safety_check(phq9, {"phq9_9": 99}).show
    assert surveys.safety_check(phq9, {"phq9_9": "yes"}).show  # type: ignore[dict-item]


def test_instruments_without_trigger_never_show() -> None:
    for name in ("phq2", "gad2", "who5", "daily_am", "daily_pm"):
        inst = surveys.get_seed_instrument(name)
        answers = {it["key"]: max(o["value"] for o in it["options"]) for it in inst["items"]}
        assert surveys.safety_check(inst, answers).show is False


def test_fallback_resources_when_seed_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(surveys, "SEEDS_DIR", tmp_path)
    surveys._safety_resources.cache_clear()
    try:
        res = surveys.safety_check(surveys.get_seed_instrument("phq9"), {"phq9_9": 2})
        assert res.show and res.resources
    finally:
        surveys._safety_resources.cache_clear()


def test_safety_check_is_sync() -> None:
    import inspect

    assert not inspect.iscoroutinefunction(surveys.safety_check)


def test_safety_check_works_with_db_and_worker_absent() -> None:
    """Run in a fresh interpreter where SQLAlchemy, the models and the job runner
    cannot be imported at all. safety_check must still return show=True."""
    import subprocess
    import sys
    import textwrap
    from pathlib import Path

    code = textwrap.dedent(
        """
        import sys
        for mod in ("sqlalchemy", "backend.db", "backend.models",
                    "backend.services.runs", "backend.deps"):
            sys.modules[mod] = None  # any import of these raises ImportError
        from backend.services import surveys
        inst = surveys.get_seed_instrument("phq9")
        res = surveys.safety_check(inst, {"phq9_9": 1})
        assert res.show and res.resources, res
        assert not any(m.startswith("sqlalchemy") and sys.modules[m] is not None
                       for m in list(sys.modules))
        sys.stdout.write("OK")
        """
    )
    root = Path(__file__).resolve().parents[2]
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=root, capture_output=True, text=True, timeout=60
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout == "OK"
