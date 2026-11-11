from __future__ import annotations

import secrets

import pytest

from backend.config import get_settings


@pytest.fixture(autouse=True)
def _strong_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """HS256 wants >= 32 bytes; the settings default is a short dev key."""
    monkeypatch.setattr(get_settings(), "secret_key", secrets.token_urlsafe(48))


@pytest.fixture
def engine(tmp_path):
    # TEMPORARY imports: backend.db / backend.models at merge.
    from tests.api._tmp_db import init_db
    from tests.api._tmp_models import Base

    eng = init_db(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    from tests.api._tmp_db import SessionLocal

    s = SessionLocal()
    yield s
    s.close()
