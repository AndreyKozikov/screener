"""Репозиторий для таблицы emitent_edisclosure.

Содержит только операции доступа к БД: выборка emitent_id, уже имеющих
маппинг, upsert пары (emitent_id, edisclosure_id) и получение списка
эмитентов с приоритетом по отсутствию эмиссионных документов.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine, select

from app.models.entities.emitent_edisclosure import EmitentEdisclosure
from config.paths import DB_PATH


class EmitentEdisclosureRepository:
    """Репозиторий для CRUD-операций с таблицей emitent_edisclosure.

    Только доступ к БД. Бизнес-логика (поиск компании по ИНН и т.д.)
    выполняется в сервисном слое.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий.

        Args:
            db_path: Путь к файлу БД. Если не указан — config.paths.DB_PATH.
        """
        if db_path is None:
            db_path = DB_PATH
        self.db_path: Path = Path(db_path)
        self._engine: Engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger: logging.Logger = logging.getLogger(__name__)

    def get_existing_emitent_ids(self) -> Set[int]:
        """Возвращает множество emitent_id, уже присутствующих в emitent_edisclosure."""
        with Session(self._engine) as session:
            rows = session.exec(
                select(EmitentEdisclosure.emitent_id)
            ).all()
        return set(rows)

    def get_edisclosure_id_by_emitent_id(self, emitent_id: int) -> Optional[int]:
        """Возвращает edisclosure_id (ID компании на e-disclosure.ru) по emitent_id.

        Args:
            emitent_id: FK на emitents.id.

        Returns:
            edisclosure_id или None, если маппинг отсутствует.
        """
        with Session(self._engine) as session:
            row = session.exec(
                select(EmitentEdisclosure.edisclosure_id).where(
                    EmitentEdisclosure.emitent_id == emitent_id
                )
            ).first()
        return int(row) if row is not None else None

    def get_emitents_ordered_by_missing_docs(
        self, limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Возвращает список эмитентов e-disclosure с приоритетом по отсутствию документов.

        Сначала эмитенты, у которых в emission_documents нет записей,
        затем остальные (по возрастанию количества документов).

        Args:
            limit: Максимальное количество записей. None — все.

        Returns:
            Список словарей {"id": int, "edisclosure_id": int}.
        """
        query: str = (
            "SELECT ee.id, ee.edisclosure_id "
            "FROM emitent_edisclosure ee "
            "LEFT JOIN ("
            "  SELECT emitent_edisclosure_id, COUNT(*) AS doc_count "
            "  FROM emission_documents "
            "  GROUP BY emitent_edisclosure_id"
            ") dc ON ee.id = dc.emitent_edisclosure_id "
            "ORDER BY COALESCE(dc.doc_count, 0) ASC"
        )
        params: Dict[str, Any] = {}
        if limit is not None:
            query += " LIMIT :limit"
            params["limit"] = limit

        with Session(self._engine) as session:
            rows = session.execute(text(query), params).fetchall()

        return [
            {"id": int(row[0]), "edisclosure_id": int(row[1])}
            for row in rows
        ]

    def upsert_mapping(self, emitent_id: int, edisclosure_id: int) -> None:
        """Вставляет или обновляет запись в emitent_edisclosure.

        При существующем emitent_id обновляет edisclosure_id (ON CONFLICT).
        """
        stmt = text(
            "INSERT INTO emitent_edisclosure (emitent_id, edisclosure_id) "
            "VALUES (:emitent_id, :edisclosure_id) "
            "ON CONFLICT(emitent_id) DO UPDATE SET "
            "edisclosure_id = excluded.edisclosure_id"
        )
        with Session(self._engine) as session:
            session.execute(stmt, {"emitent_id": emitent_id, "edisclosure_id": edisclosure_id})
            session.commit()
