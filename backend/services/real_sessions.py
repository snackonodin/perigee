"""Real ESP32 CSI captures from the team's saved tests, for demo accounts only.

seeds/real_sessions/<id>.json describes a capture measured by the host laptop (time,
geometry, operator-count truth, both breathing estimates per window, accuracy) and
<id>.csv is the capture itself, copied unchanged from waiwai1/. Real accounts get
nothing here: these are not their data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import User
from csi_core.config import ROOT

DIR = ROOT / "seeds" / "real_sessions"
_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _is_demo(db: Session, user_id: str) -> bool:
    return bool(db.scalar(select(User.is_synthetic).where(User.id == user_id)))


def list_for(db: Session, user_id: str) -> list[dict[str, Any]]:
    """The saved real captures, newest first; empty for real accounts."""
    if not _is_demo(db, user_id) or not DIR.is_dir():
        return []
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR.glob("*.json"))]
    return sorted(docs, key=lambda d: d["measured_at"], reverse=True)


def capture_path(db: Session, user_id: str, sample_id: str) -> Path | None:
    """The CSV of one saved capture, for a demo account; None otherwise."""
    if not _ID.match(sample_id) or not _is_demo(db, user_id):
        return None
    p = DIR / f"{sample_id}.csv"
    return p if p.is_file() and (DIR / f"{sample_id}.json").is_file() else None
