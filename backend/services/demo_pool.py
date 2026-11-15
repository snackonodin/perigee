"""Per-visitor demo accounts: a private copy of the synthetic demo persona, capped.

The public demo (Space Apps: no login) must not let visitors see each other's quiz or
check-in answers, so each POST /auth/demo makes a fresh synthetic user with a copy of the
template persona's rows (settings.demo_email). Copying is fast (no synthesis or pipeline
run). New ids for every copied row; foreign keys are remapped; nothing on disk is shared.
"""

from __future__ import annotations

import secrets
import uuid
from typing import Any

from sqlalchemy import Table, func, insert, select
from sqlalchemy.orm import Session

from backend import security
from backend.models import Base, User

VISITOR_PREFIX = "demo-"
VISITOR_DOMAIN = "@example.invalid"
# Not copied: credentials, history, and anything that points at files on disk.
SKIP_TABLES = frozenset({"refresh_tokens", "audit_log", "raw_files"})


class DemoFull(Exception):
    """The visitor cap is reached."""


def is_visitor(email: str) -> bool:
    return email.startswith(VISITOR_PREFIX) and email.endswith(VISITOR_DOMAIN)


def visitor_count(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.is_synthetic.is_(True),
            User.email.like(f"{VISITOR_PREFIX}%{VISITOR_DOMAIN}"),
        )
    ) or 0


def _user_tables() -> list[Table]:
    return [
        t
        for t in Base.metadata.sorted_tables  # parents before children
        if "user_id" in t.c and t.name not in SKIP_TABLES
    ]


def _fk_targets(t: Table) -> dict[str, str]:
    """column name -> referenced table name, for single-column foreign keys."""
    return {fk.parent.name: fk.column.table.name for fk in t.foreign_keys}


def create_visitor(db: Session, cap: int) -> tuple[str, str]:
    """A new empty synthetic visitor account (id, email), within the cap. Caller commits."""
    if cap > 0 and visitor_count(db) >= cap:
        raise DemoFull
    new_uid = str(uuid.uuid4())
    email = f"{VISITOR_PREFIX}{secrets.token_hex(6)}{VISITOR_DOMAIN}"
    db.add(
        User(
            id=new_uid,
            email=email,
            # random, never shown: the account is reachable only through its own tokens
            password_hash=security.hash_password(secrets.token_urlsafe(32)),
            is_synthetic=True,
        )
    )
    db.flush()
    return new_uid, email


def clone_user(db: Session, template_id: str, cap: int) -> str:
    """Create a visitor copy of ``template_id``; returns the new user id. Caller commits."""
    new_uid, _ = create_visitor(db, cap)
    id_map: dict[str, dict[Any, Any]] = {"users": {template_id: new_uid}}
    copied = {t.name for t in _user_tables()}
    for t in _user_tables():
        rows = db.execute(select(t).where(t.c.user_id == template_id)).mappings().all()
        if not rows:
            continue
        pk = [c.name for c in t.primary_key.columns]
        fks = _fk_targets(t)
        own = id_map.setdefault(t.name, {})
        out = []
        for r in rows:
            row = dict(r)
            for col in pk:
                own[row[col]] = new_id = str(uuid.uuid4())
                row[col] = new_id
            for col, target in fks.items():
                if col in pk or row.get(col) is None:
                    continue
                if target in id_map and row[col] in id_map[target]:
                    row[col] = id_map[target][row[col]]
                elif target in copied or target == "users":
                    row[col] = None  # points at a row we did not copy
            if t.name == "sessions" and "raw_path" in row:
                row["raw_path"] = ""  # never share (or later delete) the template's files
            if t.name == "profiles":
                settings = dict(row.get("settings") or {})
                for k in ("traits", "traits_source", "traits_at"):
                    settings.pop(k, None)  # each visitor takes the quiz themselves
                row["settings"] = settings
            out.append(row)
        db.execute(insert(t), out)
    return new_uid


def stats(db: Session) -> dict[str, int]:
    """Aggregate demo numbers only (no ids, no emails): visitor copies that exist now, and
    every demo sign-in ever started (audit rows survive account deletion, anonymised)."""
    from backend.models import AuditLog

    started = db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action == "auth.demo_login")
    ) or 0
    return {"visitors_now": visitor_count(db), "demo_sessions_started": started}
