"""Репозиторий для таблицы describe_fields.

Чтение описаний полей по секциям (securities, marketdata) для отдачи на фронтенд.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from sqlmodel import Session, create_engine, select

from app.models import DescribeField
from config.paths import DB_PATH


class DescribeRepository:
    """Репозиторий для таблицы describe_fields. Только чтение."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий.

        Args:
            db_path: Путь к файлу БД. Если None — используется DB_PATH.
        """
        if db_path is None:
            db_path = DB_PATH
        self.db_path = Path(db_path)
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger = logging.getLogger(__name__)

    def get_descriptions_formatted(self) -> Dict[str, Dict[str, str]]:
        """Возвращает описания полей, сгруппированные по секциям.

        Структура результата совместима с форматом describe.json и ожиданиями
        фронтенда: { "securities": { "FIELD": "описание", ... }, "marketdata": { ... } }.

        Returns:
            Словарь: секция -> (имя поля -> текст описания).
        """
        result: Dict[str, Dict[str, str]] = {}
        try:
            with Session(self._engine) as session:
                stmt = select(DescribeField).order_by(DescribeField.section, DescribeField.field_name)
                rows = session.exec(stmt).all()
                for row in rows:
                    if row.section not in result:
                        result[row.section] = {}
                    result[row.section][row.field_name] = row.description or ""
        except Exception as e:
            self.logger.warning("get_descriptions_formatted: %s", e)
        return result
