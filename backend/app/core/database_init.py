"""Автоматизация миграций Alembic при запуске приложения.

Скрипт выполняет применение миграций (alembic upgrade head) при старте приложения,
чтобы структура таблицы bonds в bonds.db соответствовала модели Bond.
Опционально можно выполнить autogenerate для создания новой ревизии при изменении модели.
"""

import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from config.paths import BACKEND_DIR as _BACKEND_DIR

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def run_migrations() -> None:
    """Применяет все неприменённые миграции (alembic upgrade head).

    Вызывается из main.py при старте приложения. Обеспечивает актуальность
    структуры БД (таблица bonds) без ручного запуска alembic.

    Raises:
        Exception: При ошибке выполнения миграций (логируется и пробрасывается).
    """
    logger = logging.getLogger(__name__)
    config_path = _BACKEND_DIR / "alembic.ini"
    if not config_path.exists():
        logger.warning("alembic.ini не найден: %s — миграции пропущены", config_path)
        return
    try:
        alembic_cfg = Config(str(config_path))
        command.upgrade(alembic_cfg, "head")
        logger.info("Миграции Alembic применены (upgrade head)")
    except Exception as e:
        err_msg = str(e).lower()
        if "table bonds already exists" in err_msg:
            logger.info(
                "Таблица bonds уже существует (создана ранее); помечаем миграции как применённые (stamp head)"
            )
            command.stamp(alembic_cfg, "head")
        else:
            logger.error("Ошибка при применении миграций Alembic: %s", e, exc_info=True)
            raise


def run_autogenerate(message: str = "auto") -> None:
    """Создаёт новую ревизию на основе изменений в моделях (alembic revision --autogenerate).

    Вызывать вручную при изменении модели Bond для генерации файла миграции.
    После генерации при следующем запуске приложения run_migrations() применит новую ревизию.

    Args:
        message: Сообщение для ревизии (по умолчанию "auto").
    """
    logger = logging.getLogger(__name__)
    config_path = _BACKEND_DIR / "alembic.ini"
    if not config_path.exists():
        logger.warning("alembic.ini не найден: %s", config_path)
        return
    try:
        alembic_cfg = Config(str(config_path))
        command.revision(alembic_cfg, message=message, autogenerate=True)
        logger.info("Ревизия создана (revision --autogenerate -m %s)", message)
    except Exception as e:
        logger.error("Ошибка при создании ревизии: %s", e, exc_info=True)
        raise
