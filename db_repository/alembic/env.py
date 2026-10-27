"""Alembic environment configuration.

URL базы данных задаётся относительно env.py (db/bonds.db).
Для выполнения готовых миграций (upgrade) импорт моделей app не нужен —
так избегаем блокировок и тяжёлых зависимостей при загрузке env.py.
Для autogenerate нужно импортировать модели вручную перед генерацией.
"""

import logging.config
import sys
from pathlib import Path

service_dir = Path(__file__).resolve().parent.parent
project_root = service_dir.parent
for path in (service_dir, project_root):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

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
from db_repository.models.bond import Bond, BondMarketData, BondMarketDataYield, BondSecurity  # noqa: F401
from db_repository.models.bond_emitent import BondEmitent  # noqa: F401
from db_repository.models.emitent import Emitent  # noqa: F401
from db_repository.models.inflations import InflationData, InflationExpectations  # noqa: F401
from db_repository.models.ipc import Ipc, IpcWeekly  # noqa: F401
from db_repository.models.ratings import BondRating, EmitentRating, RatingAgency  # noqa: F401
from db_repository.models.orm.bond_float_params import BondFloatParams  # noqa: F401
from db_repository.models.orm.currencyrate import DBcurrencyrate  # noqa: F401
from db_repository.models.orm.describe import DescribeField  # noqa: F401
from db_repository.models.orm.emission_document import EmissionDocument  # noqa: F401
from db_repository.models.orm.emitent_edisclosure import EmitentEdisclosure  # noqa: F401
from db_repository.models.orm.event_detail import EventDetail  # noqa: F401
from db_repository.models.orm.forecast import (  # noqa: F401
    Forecast, ForecastBalance, ForecastIndicatorName, ForecastMainIndicators,
)
from db_repository.models.orm.kbd import DBkbd  # noqa: F401
from db_repository.models.orm.keyrate import DBkeyrate  # noqa: F401
from db_repository.models.orm.ruonia import DBruonia  # noqa: F401
from db_repository.models.orm.trading_history import TradingHistoryRecord  # noqa: F401

target_metadata = SQLModel.metadata


def get_url() -> str:
    """Возвращает URL базы данных без импорта config (избегаем config.settings/pydantic_settings)."""
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite"):
        from db_repository.config.paths import DB_PATH

        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DB_PATH}"
    return url


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
