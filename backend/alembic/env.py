"""Alembic environment configuration.

Использует SQLModel.metadata и модель Bond для автогенерации миграций.
URL базы данных задаётся относительно корня backend (db/bonds.db).
"""

import logging.config
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

# Импорт Bond регистрирует таблицу bonds в SQLModel.metadata
from app.models.bond import Bond  # noqa: F401

config = context.config
if config.config_file_name is not None:
    try:
        logging.config.fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = SQLModel.metadata


def get_url() -> str:
    """Возвращает URL базы данных из config.paths."""
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite"):
        from config.paths import DB_PATH
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DB_PATH}"
    return url or "sqlite:///db/bonds.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=StaticPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
