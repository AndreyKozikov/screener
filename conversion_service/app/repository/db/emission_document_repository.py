"""Репозиторий для таблицы emission_documents.

Содержит только операции доступа к БД: пакетная вставка эмиссионных
документов и удаление записей по emitent_edisclosure_id.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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

    def get_by_inn_and_reg_number(
        self,
        inn: str,
        reg_number: str,
    ) -> List[Dict[str, Any]]:
        """Возвращает записи emission_documents по ИНН эмитента и рег. номеру облигации.

        Связь: emitents.inn -> emitent_edisclosure -> emission_documents.reg_number.
        Возвращаются только записи с непустым file_url, отсортированные по
        date_registration DESC (новые первыми).

        Args:
            inn: ИНН эмитента.
            reg_number: Регистрационный номер облигации.

        Returns:
            Список словарей с ключами id, file_url и при необходимости date_registration.
        """
        if not inn or not str(inn).strip() or not reg_number or not str(reg_number).strip():
            return []
        inn_trimmed: str = str(inn).strip()
        reg_trimmed: str = str(reg_number).strip()
        query = text(
            "SELECT ed.id, ed.file_url, ed.date_registration "
            "FROM emission_documents ed "
            "JOIN emitent_edisclosure ee ON ed.emitent_edisclosure_id = ee.id "
            "JOIN emitents e ON ee.emitent_id = e.id "
            "WHERE trim(e.inn) = :inn AND trim(ed.reg_number) = :reg_number "
            "AND ed.file_url IS NOT NULL AND trim(ed.file_url) != '' "
            "ORDER BY ed.date_registration DESC"
        )
        with Session(self._engine) as session:
            rows = session.execute(
                query,
                {"inn": inn_trimmed, "reg_number": reg_trimmed},
            ).fetchall()
        return [
            {
                "id": int(row[0]),
                "file_url": str(row[1]).strip() if row[1] else "",
                "date_registration": row[2],
            }
            for row in rows
            if row[0] is not None and row[1]
        ]

    def get_all_documents_by_metadata(self) -> Dict[Tuple[str, str], List[str]]:
        """Возвращает словарь с ключом (inn, reg_number) и значением в виде списка file_url.

        Выбираются только записи с непустым file_url.
        """
        query = text(
            "SELECT trim(e.inn), trim(ed.reg_number), ed.file_url "
            "FROM emission_documents ed "
            "JOIN emitent_edisclosure ee ON ed.emitent_edisclosure_id = ee.id "
            "JOIN emitents e ON ee.emitent_id = e.id "
            "WHERE ed.file_url IS NOT NULL AND trim(ed.file_url) != ''"
        )
        result: Dict[Tuple[str, str], List[str]] = {}
        try:
            with Session(self._engine) as session:
                rows = session.execute(query).fetchall()
            for row in rows:
                if row[0] and row[1] and row[2]:
                    key = (str(row[0]).strip(), str(row[1]).strip())
                    url = str(row[2]).strip()
                    result.setdefault(key, []).append(url)
        except Exception as exc:
            self.logger.error("Failed to fetch all documents by metadata: %s", exc)
        return result

