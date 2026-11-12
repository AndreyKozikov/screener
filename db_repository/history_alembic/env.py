"""Alembic environment for the separate bond trading history database."""

import logging.config
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

service_dir = Path(__file__).resolve().parent.parent
project_root = service_dir.parent
for path in (service_dir, project_root):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from db_repository.models.orm.trading_history import TradingHistoryRecord  # noqa: F401

config = context.config
if config.config_file_name is not None:
    try:
        logging.config.fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = SQLModel.metadata


def get_url() -> str:
    """Return the URL of the separate history SQLite database."""
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite"):
        x_args = context.get_x_argument(as_dictionary=True)
        configured_path = x_args.get("db_path")
        if configured_path:
            db_path = Path(configured_path)
        else:
            from db_repository.config.paths import HISTORY_DB_PATH

            db_path = HISTORY_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
    return url


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=StaticPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
