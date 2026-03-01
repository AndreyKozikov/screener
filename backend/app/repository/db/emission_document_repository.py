"""Репозиторий для таблицы emission_documents.

Содержит только операции доступа к БД: пакетная вставка эмиссионных
документов и удаление записей по emitent_edisclosure_id.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from config.paths import DB_PATH


class EmissionDocumentRepository:
    """CRUD-операции с таблицей emission_documents.

    Бизнес-логика (парсинг HTML, HTTP-запросы) выполняется в сервисном слое.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = DB_PATH
        self.db_path: Path = Path(db_path)
        self._engine: Engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger: logging.Logger = logging.getLogger(__name__)

    def insert_batch(
        self,
        emitent_edisclosure_id: int,
        documents: List[Dict[str, Optional[Union[str, int]]]],
    ) -> int:
        """Вставляет список эмиссионных документов для одного эмитента.

        Перед вставкой удаляет существующие записи для данного
        emitent_edisclosure_id (полная перезапись).

        Args:
            emitent_edisclosure_id: FK на emitent_edisclosure.id.
            documents: Список словарей с ключами doc_type, reg_number,
                date_registration, registering_org, date_ground_publication,
                date_placement, file_url.

        Returns:
            Количество вставленных записей.
        """
        if not documents:
            return 0

        delete_stmt = text(
            "DELETE FROM emission_documents "
            "WHERE emitent_edisclosure_id = :eid"
        )
        insert_stmt = text(
            "INSERT INTO emission_documents ("
            "  emitent_edisclosure_id, doc_type, reg_number,"
            "  date_registration, registering_org,"
            "  date_ground_publication, date_placement, file_url"
            ") VALUES ("
            "  :emitent_edisclosure_id, :doc_type, :reg_number,"
            "  :date_registration, :registering_org,"
            "  :date_ground_publication, :date_placement, :file_url"
            ")"
        )

        inserted: int = 0
        with Session(self._engine) as session:
            session.execute(delete_stmt, {"eid": emitent_edisclosure_id})

            for doc in documents:
                session.execute(insert_stmt, {
                    "emitent_edisclosure_id": emitent_edisclosure_id,
                    "doc_type": doc.get("doc_type") or "",
                    "reg_number": doc.get("reg_number"),
                    "date_registration": doc.get("date_registration"),
                    "registering_org": doc.get("registering_org"),
                    "date_ground_publication": doc.get("date_ground_publication"),
                    "date_placement": doc.get("date_placement"),
                    "file_url": doc.get("file_url"),
                })
                inserted += 1

            session.commit()

        return inserted
