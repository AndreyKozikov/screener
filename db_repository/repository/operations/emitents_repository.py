"""Репозиторий для чтения данных из таблиц emitents и emitent_ratings."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlmodel import Session, create_engine

from db_repository.config.paths import DB_PATH


class EmitentsRepository:
    """Репозиторий для работы с эмитентами облигаций."""

    def __init__(self, db_path: Optional[Path] = None):
        """Инициализирует репозиторий.

        Args:
            db_path: Путь к файлу БД. По умолчанию — backend/db/bonds.db.
        """
        self.db_path = Path(db_path) if db_path else DB_PATH
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger = logging.getLogger(__name__)

    def get_emitent_data_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Получает данные эмитента по SECID облигации из БД в формате API MOEX.

        Восстанавливает структуру данных эмитента (emitent_title, emitent_inn, type,
        cci_rating_companies) из таблиц emitents и emitent_ratings.

        Args:
            secid: SECID облигации.

        Returns:
            Словарь в формате API MOEX или None, если данные не найдены.
        """
        stmt = text("""
            SELECT e.id, e.moex_id, e.inn, e.okpo, e.title, e.type
            FROM bonds b
            JOIN bond_emitents be ON be.secid = b.secid
            JOIN emitents e ON be.emitent_id = e.id
            WHERE b.secid = :secid
        """)
        try:
            with Session(self._engine) as session:
                row = session.execute(stmt, {"secid": secid}).fetchone()
                if row is None:
                    return None

                emitent_id_db = row[0]
                moex_id = row[1]
                inn = row[2]
                okpo = row[3]
                title = row[4]
                bond_type = row[5]

                ratings_stmt = text("""
                    SELECT ra.agency_id, ra.agency_name_short_ru, er.rating_level_name, er.rating_date, er.rating_publicate_date
                    FROM emitent_ratings er
                    JOIN rating_agency ra ON er.agency_id = ra.id
                    WHERE er.emitent_id = :emitent_id
                """)
                rating_rows = session.execute(ratings_stmt, {"emitent_id": emitent_id_db}).fetchall()

                cci_rating_companies: List[Dict[str, Any]] = []
                for r in rating_rows:
                    agency_id, agency_name_short_ru, rating_level_name, rating_date, rating_publicate_date = r
                    cci_rating_companies.append({
                        "agency_id": agency_id,
                        "agency_name_short_ru": (agency_name_short_ru or "").strip() or None,
                        "rating_level_name_short_ru": rating_level_name,
                        "rating_level_name": rating_level_name,
                        "rating_date": str(rating_date) if rating_date else None,
                        "rating_publicate_date": str(rating_publicate_date) if rating_publicate_date else None,
                    })

                return {
                    "emitent_id": moex_id,
                    "emitent_inn": inn,
                    "emitent_okpo": okpo,
                    "emitent_title": title,
                    "type": bond_type,
                    "cci_rating_companies": cci_rating_companies,
                }
        except Exception as e:
            self.logger.warning("Ошибка при чтении emitent по secid=%s: %s", secid, e)
            return None

    def get_all_emitent_titles(self) -> List[str]:
        """Возвращает отсортированный список уникальных названий эмитентов из БД.

        Используется как fallback для API списка эмитентов, когда кэш облигаций пуст
        (например, после деплоя до первого обновления облигаций).

        Returns:
            Отсортированный список непустых названий эмитентов.
        """
        stmt = text("""
            SELECT DISTINCT e.title
            FROM emitents e
            WHERE e.title IS NOT NULL AND trim(e.title) != ''
            ORDER BY e.title
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt).fetchall()
                return [str(row[0]).strip() for row in rows if row[0]]
        except Exception as e:
            self.logger.warning("Ошибка при чтении списка эмитентов: %s", e)
            return []

    def get_emitents_with_inn(self) -> List[Dict[str, Any]]:
        """Возвращает список эмитентов с непустым ИНН: [{"id": int, "inn": str}, ...]."""
        stmt = text(
            "SELECT id, inn FROM emitents "
            "WHERE inn IS NOT NULL AND trim(inn) != ''"
        )
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt).fetchall()
            return [{"id": int(row[0]), "inn": str(row[1]).strip()} for row in rows if row[0] is not None and row[1]]
        except Exception as e:
            self.logger.warning("Ошибка при чтении эмитентов с ИНН: %s", e)
            return []

    def get_emitent_id_by_inn(self, inn: str) -> Optional[int]:
        """Возвращает id эмитента из таблицы emitents по ИНН.

        Args:
            inn: ИНН эмитента (без лишних пробелов).

        Returns:
            id записи в emitents или None, если не найдено.
        """
        if not inn or not str(inn).strip():
            return None
        inn_trimmed: str = str(inn).strip()
        stmt = text("SELECT id FROM emitents WHERE trim(inn) = :inn LIMIT 1")
        try:
            with Session(self._engine) as session:
                row = session.execute(stmt, {"inn": inn_trimmed}).fetchone()
            return int(row[0]) if row and row[0] is not None else None
        except Exception as e:
            self.logger.warning("Ошибка при получении emitent_id по ИНН %s: %s", inn_trimmed, e)
            return None

    def get_secid_to_emitent_title_index(self) -> Dict[str, str]:
        """Возвращает маппинг SECID облигации -> название эмитента из БД."""
        stmt = text("""
            SELECT b.secid, e.title
            FROM bonds b
            JOIN bond_emitents be ON be.secid = b.secid
            JOIN emitents e ON be.emitent_id = e.id
            WHERE e.title IS NOT NULL AND trim(e.title) != ''
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt).fetchall()
                return {str(row[0]): str(row[1]).strip() for row in rows if row[0] and row[1]}
        except Exception as e:
            self.logger.warning("Ошибка при чтении secid->title: %s", e)
            return {}

