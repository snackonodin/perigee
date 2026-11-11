from __future__ import annotations

import io
import logging

import pytest

from backend.logging import REDACTED, RedactionFilter, configure_logging

SECRETS = [
    "hunter2-very-secret",
    "eyJhbGciOi.tok.sig",
    "Sertraline",
    "50mg",
    "Jane Doe",
    "felt anxious today",
]


@pytest.fixture
def capture():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s %(meta)s"))
    handler.addFilter(RedactionFilter())
    log = logging.getLogger("test.redaction")
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)
    log.propagate = False
    yield log, buf
    log.removeHandler(handler)


def _emit_all(log: logging.Logger) -> None:
    m = {"meta": "-"}
    log.info("login password=%s", "hunter2-very-secret", extra=m)
    log.info("payload %s", {"email": "a@x.io", "password": "hunter2-very-secret"}, extra=m)
    log.info("%(refresh_token)s issued", {"refresh_token": "eyJhbGciOi.tok.sig"}, extra=m)
    log.info({"answers": {"q1": 3}, "note": "felt anxious today"}, extra=m)
    log.info("med", extra={"meta": {"medication_name": "Sertraline", "dose": "50mg"}})
    log.info("Authorization: Bearer eyJhbGciOi.tok.sig", extra=m)
    log.info('json {"display_name": "Jane Doe", "user_id": "u-1"}', extra=m)
    log.warning("profile name='Jane Doe' dose=50mg", extra=m)
    log.info("nested %s", [{"answers": [1, 2]}, {"note": "felt anxious today"}], extra=m)


def test_no_secrets_in_output(capture) -> None:
    log, buf = capture
    _emit_all(log)
    out = buf.getvalue()
    for s in SECRETS:
        assert s not in out, s
    assert out.count(REDACTED) >= 9
    # non-sensitive context is kept
    assert "a@x.io" in out and "u-1" in out and "login" in out


def test_sensitive_extra_attribute_is_redacted(capture) -> None:
    log, buf = capture
    log.info("x", extra={"meta": "-", "password": "hunter2-very-secret"})
    rec_text = buf.getvalue()
    assert "hunter2" not in rec_text


def test_configure_logging_installs_filter_once() -> None:
    root = logging.getLogger()
    saved = list(root.handlers)
    buf = io.StringIO()
    for h in saved:
        root.removeHandler(h)
    h = logging.StreamHandler(buf)
    root.addHandler(h)
    try:
        configure_logging()
        configure_logging()
        assert sum(isinstance(f, RedactionFilter) for f in h.filters) == 1
        logging.getLogger("backend.anything").info("signup password=%s", "hunter2-very-secret")
        assert "hunter2" not in buf.getvalue() and REDACTED in buf.getvalue()
    finally:
        root.removeHandler(h)
        for old in saved:
            root.addHandler(old)
