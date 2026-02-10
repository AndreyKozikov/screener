"""Alembic environment configuration.

URL базы данных задаётся относительно env.py (db/bonds.db).
Для выполнения готовых миграций (upgrade) импорт моделей app не нужен —
так избегаем блокировок и тяжёлых зависимостей при загрузке env.py.
Для autogenerate нужно импортировать модели вручную перед генерацией.
"""

import logging.config
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

config = context.config
if config.config_file_name is not None:
    try:
        logging.config.fileConfig(config.config_file_name)
    except Exception:
        pass

# Для upgrade достаточно метаданных; для autogenerate модели должны быть
# зарегистрированы в SQLModel.metadata — импортируем модели с table=True.
from app.models import DBcurrencyrate, DBkeyrate, DBruonia  # noqa: F401

target_metadata = SQLModel.metadata


def get_url() -> str:
    """Возвращает URL базы данных без импорта config (избегаем config.settings/pydantic_settings)."""
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite"):
        # Путь к БД считаем относительно env.py (alembic/env.py -> backend/)
        backend_dir = Path(__file__).resolve().parent.parent
        db_path = backend_dir / "db" / "bonds.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
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
