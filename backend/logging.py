"""Log redaction: red-class values never reach a log line.

``RedactionFilter`` scrubs a record before it is formatted:
- dict arguments, dict messages and ``extra=`` fields: any key that contains a
  sensitive fragment (password, token, answers, note, name, dose, ...) has its value replaced;
- the final message text: ``key=value``, ``key: value`` and ``"key": "value"`` pairs with a
  sensitive key, and ``Bearer <token>``, are replaced.

Over-redaction is fine (``filename`` is hidden too); leaks are not.
Attach it to handlers (filters on a logger do not apply to child loggers), or call
``configure_logging()`` once at startup.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_FRAGMENTS: tuple[str, ...] = (
    "password",
    "passwd",
    "token",
    "secret",
    "authorization",
    "cookie",
    "answer",
    "note",
    "name",
    "dose",
    "medication",
    "field_key",
)

_FRAG = "|".join(re.escape(f) for f in SENSITIVE_FRAGMENTS)
_PAIR_RE = re.compile(
    rf"""(?ix)
    (?P<key>[\w.-]*(?:{_FRAG})[\w.-]*)      # a key containing a sensitive fragment
    (?P<sep>["']?\s*[=:]\s*)                # = or : (optionally after a closing quote)
    (?P<val>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\[[^\]]*\]|\{{[^}}]*\}}|[^\s,;&)}}]+)
    """
)
_BEARER_RE = re.compile(r"(?i)\b(bearer\s+)[\w.~+/=-]+")

# Attributes every LogRecord has; anything else came in through ``extra=``.
_STD_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def is_sensitive_key(key: object) -> bool:
    k = str(key).lower()
    return any(f in k for f in SENSITIVE_FRAGMENTS)


def redact(obj: Any) -> Any:
    """Return a copy of obj with sensitive keys' values replaced, recursively."""
    if isinstance(obj, Mapping):
        return {k: (REDACTED if is_sensitive_key(k) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list | tuple | set | frozenset):
        return type(obj)(redact(v) for v in obj) if not isinstance(obj, tuple) else tuple(
            redact(v) for v in obj
        )
    if isinstance(obj, str):
        return scrub_text(obj)
    return obj


def scrub_text(s: str) -> str:
    # Bearer first: "Authorization: Bearer x" would otherwise redact only the word "Bearer".
    s = _BEARER_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", s)
    return _PAIR_RE.sub(lambda m: f"{m['key']}{m['sep']}{REDACTED}", s)


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # 1. structured parts
        if isinstance(record.msg, Mapping):
            record.msg = redact(record.msg)
        if isinstance(record.args, Mapping):
            record.args = redact(record.args)
        elif isinstance(record.args, tuple):
            record.args = tuple(
                redact(a) if isinstance(a, Mapping | list | tuple) else a for a in record.args
            )
        for attr, value in list(record.__dict__.items()):
            if attr in _STD_ATTRS:
                continue
            if is_sensitive_key(attr):
                setattr(record, attr, REDACTED)
            else:
                setattr(record, attr, redact(value))
        # 2. the rendered text (catches values passed as plain %s arguments)
        try:
            message = record.getMessage()
        except Exception:  # bad format string: drop args rather than risk a leak
            message = str(record.msg)
        record.msg = scrub_text(message)
        record.args = None
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Root logging with redaction on every root handler. Safe to call twice."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)
    for h in root.handlers:
        if not any(isinstance(f, RedactionFilter) for f in h.filters):
            h.addFilter(RedactionFilter())
