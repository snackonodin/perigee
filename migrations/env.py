"""Alembic environment.

- URL: sqlalchemy.url if set (tests), else DATABASE_URL from settings.
- render_as_batch=True: SQLite cannot ALTER most things, so batch mode recreates tables.
- Foreign keys are switched OFF while migrating (batch table copies would otherwise
  cascade-delete child rows) and back ON afterwards.
- Custom column types are rendered as their plain SQL impl so migrations never
  import model code.
"""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.types import TypeDecorator

import backend.models  # noqa: F401  (registers all tables)
from backend.db import default_url, get_engine
from backend.models.base import Base, JSONText, UTCDateTime

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or default_url()


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.String(length=27)"
    if type_ == "type" and isinstance(obj, JSONText):
        return "sa.Text()"
    if type_ == "type" and isinstance(obj, TypeDecorator):
        # e.g. backend.security.EncryptedJSON: store its plain impl (LargeBinary -> BLOB)
        return f"sa.{obj.impl_instance!r}"
    return False


def _configure_kwargs() -> dict[str, Any]:
    return {
        "target_metadata": target_metadata,
        "render_as_batch": True,
        "render_item": render_item,
        "compare_type": True,
    }


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, **_configure_kwargs())
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = get_engine(_url())
    with engine.connect() as connection:
        # exec_driver_sql autobegins a transaction; commit it so Alembic owns the
        # migration transaction (otherwise the work is rolled back on close).
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        context.configure(connection=connection, **_configure_kwargs())
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
