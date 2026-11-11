from __future__ import annotations

import secrets

import pytest

from backend.config import get_settings


@pytest.fixture(autouse=True)
def _strong_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """HS256 wants >= 32 bytes; the settings default is a short dev key."""
    monkeypatch.setattr(get_settings(), "secret_key", secrets.token_urlsafe(48))
