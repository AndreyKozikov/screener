"""Автоматизация миграций Alembic при запуске приложения.

Скрипт выполняет применение миграций (alembic upgrade head) при старте приложения
в отдельном процессе, чтобы избежать блокировок и конфликтов импортов.
Если скриптов миграций нет (папка versions пуста), upgrade не выполняется.
"""

import logging
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from config.paths import BACKEND_DIR as _BACKEND_DIR

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


def _has_migration_scripts() -> bool:
    """Проверяет, есть ли в alembic/versions хотя бы один скрипт миграции."""
    versions_dir = _BACKEND_DIR / "alembic" / "versions"
    if not versions_dir.is_dir():
        return False
    return any(versions_dir.glob("*.py"))  # только .py, без __init__ и т.п.


def run_migrations() -> None:
    """Применяет неприменённые миграции (alembic upgrade head) в отдельном процессе.

    Запуск через subprocess устраняет зависания из-за импортов app/config
    при загрузке env.py в том же процессе, что и приложение.
    Обработка «can't locate revision»: сначала stamp base, затем upgrade head.
    """
    logger = logging.getLogger(__name__)
    config_path = _BACKEND_DIR / "alembic.ini"
    if not config_path.exists():
        logger.warning("alembic.ini не найден: %s — миграции пропущены", config_path)
        return
    if not _has_migration_scripts():
        logger.info("Скриптов миграций нет (alembic/versions пуста) — upgrade пропущен")
        return

    def _run_alembic(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "alembic"] + list(args),
            cwd=str(_BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=60,
        )

    print("[STARTUP] alembic upgrade head start", flush=True)
    proc = _run_alembic("upgrade", "head")
    if proc.returncode != 0:
        out, err = proc.stdout or "", proc.stderr or ""
        combined = out + err
        err_lower = combined.lower()
        if "can't locate revision" in err_lower or "multiple head revisions" in err_lower:
            logger.info(
                "Ревизия в БД отсутствует в скриптах; выполняем stamp base + upgrade head"
            )
            _run_alembic("stamp", "base")
            proc2 = _run_alembic("upgrade", "head")
            if proc2.returncode == 0:
                print("[STARTUP] alembic stamp base + upgrade head done", flush=True)
            elif "already exists" in (proc2.stdout or "" + proc2.stderr or "").lower():
                _run_alembic("stamp", "head")
                print("[STARTUP] alembic stamp head done", flush=True)
            else:
                logger.error("Ошибка миграций после stamp base: %s\n%s", proc2.stdout, proc2.stderr)
                raise RuntimeError(f"Alembic upgrade failed: {proc2.stderr or proc2.stdout}")
        elif "table bonds already exists" in err_lower or "already exists" in err_lower:
            logger.info("Таблица уже существует; помечаем миграции как применённые (stamp head)")
            _run_alembic("stamp", "head")
            print("[STARTUP] alembic stamp head done", flush=True)
        else:
            logger.error("Ошибка миграций Alembic: %s\n%s", proc.stdout, proc.stderr)
            raise RuntimeError(f"Alembic upgrade failed: {proc.stderr or proc.stdout}")
    else:
        print("[STARTUP] alembic upgrade head done", flush=True)
    logger.info("Миграции Alembic применены (upgrade head)")


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
    alembic_cfg = Config(str(config_path))
    try:
        command.revision(alembic_cfg, message=message, autogenerate=True)
        logger.info("Ревизия создана (revision --autogenerate -m %s)", message)
    except Exception as e:
        logger.error("Ошибка при создании ревизии: %s", e, exc_info=True)
        raise
