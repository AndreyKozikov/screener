"""Единственный лаунчер db_repository.

Работает:
- из IDE как обычный script (PyCharm: script path db_repository/run_db_service.py);
- как модуль: python -m db_repository.run_db_service;
- как systemd-служба с ExecStart=/opt/.../python -m db_repository.run_db_service.

Параметры host/port/workers/reload берутся из db_repository/config/config.toml.
Uvicorn получает import-string, поэтому приложение создаётся один раз.
"""

from __future__ import annotations

import sys
from pathlib import Path

# При запуске файла как script из IDE sys.path[0] — db_repository, а пакет
# импортируется как db_repository. Добавляем родительский каталог.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import uvicorn

from db_repository.config.settings import settings


def main() -> None:
    if settings.reload and settings.workers != 1:
        raise SystemExit("reload=true несовместим с workers > 1")

    uvicorn.run(
        "db_repository.main_db:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        workers=settings.workers,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
