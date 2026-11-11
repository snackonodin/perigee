"""Environment settings (secrets, paths). Loaded from .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from csi_core.config import ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    secret_key: str = Field(default="dev-only-insecure-key", min_length=16)
    field_key: str = ""  # Fernet key for red-class fields; required outside tests
    data_dir: Path = Path("~/astro-data")
    database_url: str = "sqlite:///~/astro-data/db/astro.db"
    api_host: str = "127.0.0.1"  # offline demo: localhost only
    api_port: int = 8000
    access_token_minutes: int = 15
    refresh_token_days: int = 14

    @field_validator("data_dir")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return v.expanduser()

    @field_validator("database_url")
    @classmethod
    def _expand_db(cls, v: str) -> str:
        prefix = "sqlite:///"
        if v.startswith(prefix):
            return prefix + str(Path(v[len(prefix) :]).expanduser())
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
