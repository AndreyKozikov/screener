"""Репозиторий для работы с таблицей bond_ratings.

Содержит класс BondRatingsRepository для CRUD-операций с детальными рейтингами
облигаций. Все операции выполняются через SQLAlchemy/SQLModel.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlmodel import Session, create_engine

from config.paths import DB_PATH


class BondRatingsRepository:
    """Репозиторий для работы с таблицей bond_ratings.

    Обеспечивает upsert рейтингов облигаций и выборку по bond_id или secid.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует репозиторий.

        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется backend/db/bonds.db.
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

    def upsert_ratings_for_bond(
        self,
        bond_id: int,
        ratings: List[Dict[str, Any]],
    ) -> int:
        """Удаляет старые рейтинги облигации и вставляет новые.

        Использует транзакцию: DELETE по bond_id, затем INSERT для каждой записи.
        Гарантирует идемпотентность при повторном вызове.

        Args:
            bond_id: Идентификатор облигации (bonds.id).
            ratings: Список словарей с полями agency_id, rating_level_name, rating_date.

        Returns:
            Количество вставленных записей.

        Raises:
            Exception: При ошибке работы с БД (транзакция откатывается).
        """
        if not ratings:
            self.logger.debug("Нет рейтингов для bond_id=%s", bond_id)
            return 0

        # Дедупликация по (agency_id, rating_date) — MOEX может вернуть дубликаты
        seen: Dict[tuple, Dict[str, Any]] = {}
        for r in ratings:
            agency_id = r.get("agency_id")
            if agency_id is None:
                continue
            rating_date = r.get("rating_date") or ""
            if isinstance(rating_date, str) and len(rating_date) > 19:
                rating_date = rating_date[:19]
            key = (agency_id, rating_date)
            seen[key] = r
        deduped = list(seen.values())

        delete_stmt = text("DELETE FROM bond_ratings WHERE bond_id = :bond_id")
        insert_stmt = text("""
            INSERT INTO bond_ratings (bond_id, agency_id, rating_level_name, rating_date)
            VALUES (:bond_id, :agency_id, :rating_level_name, :rating_date)
        """)

        with Session(self._engine) as session:
            session.execute(delete_stmt, {"bond_id": bond_id})
            count = 0
            for r in deduped:
                agency_id = r.get("agency_id")
                if agency_id is None:
                    continue
                rating_level_name = (r.get("rating_level_name") or "").strip() or ""
                rating_date = r.get("rating_date") or ""
                if isinstance(rating_date, str) and len(rating_date) > 19:
                    rating_date = rating_date[:19]  # YYYY-MM-DD HH:MM:SS
                session.execute(
                    insert_stmt,
                    {
                        "bond_id": bond_id,
                        "agency_id": agency_id,
                        "rating_level_name": rating_level_name,
                        "rating_date": rating_date or None,
                    },
                )
                count += 1
            session.commit()
        return count

    def get_ratings_by_bond_id(self, bond_id: int) -> List[Dict[str, Any]]:
        """Возвращает рейтинги облигации по bond_id.

        Args:
            bond_id: Идентификатор облигации (bonds.id).

        Returns:
            Список словарей с полями agency_id, rating_level_name, rating_date,
            agency_name_short_ru (из rating_agency).
        """
        stmt = text("""
            SELECT br.agency_id, br.rating_level_name, br.rating_date, ra.agency_name_short_ru
            FROM bond_ratings br
            LEFT JOIN rating_agency ra ON ra.agency_id = br.agency_id
            WHERE br.bond_id = :bond_id
        """)
        with Session(self._engine) as session:
            rows = session.execute(stmt, {"bond_id": bond_id}).fetchall()
        return [
            {
                "agency_id": row[0],
                "rating_level_name": row[1] or "",
                "rating_date": row[2] or "",
                "agency_name_short_ru": row[3] or "",
            }
            for row in rows
        ]

    def get_ratings_by_secid(self, secid: str) -> List[Dict[str, Any]]:
        """Возвращает рейтинги облигации по SECID.

        Выполняет JOIN bonds и bond_ratings. Берётся первая облигация с данным secid
        (могут быть несколько boardid).

        Args:
            secid: Идентификатор ценной бумаги.

        Returns:
            Список словарей с полями agency_id, rating_level_name, rating_date,
            agency_name_short_ru. Пустой список, если облигация не найдена.
        """
        stmt = text("""
            SELECT br.agency_id, br.rating_level_name, br.rating_date, ra.agency_name_short_ru
            FROM bond_ratings br
            JOIN bonds b ON b.id = br.bond_id
            LEFT JOIN rating_agency ra ON ra.agency_id = br.agency_id
            WHERE b.secid = :secid
            LIMIT 100
        """)
        with Session(self._engine) as session:
            rows = session.execute(stmt, {"secid": secid}).fetchall()
        return [
            {
                "agency_id": row[0],
                "rating_level_name": row[1] or "",
                "rating_date": row[2] or "",
                "agency_name_short_ru": row[3] or "",
            }
            for row in rows
        ]

    def get_agency_name_short_ru_by_agency_id(self, agency_id: int) -> Optional[str]:
        """Возвращает название агентства (agency_name_short_ru) по agency_id из rating_agency.

        Args:
            agency_id: agency_id из bond_ratings / rating_agency.

        Returns:
            Строка названия или None, если не найдено.
        """
        stmt = text(
            "SELECT agency_name_short_ru FROM rating_agency WHERE agency_id = :agency_id LIMIT 1"
        )
        try:
            with Session(self._engine) as session:
                row = session.execute(stmt, {"agency_id": agency_id}).fetchone()
                if row and row[0]:
                    return (row[0] or "").strip() or None
                return None
        except Exception as e:
            self.logger.warning("Ошибка при получении agency_name_short_ru для agency_id=%s: %s", agency_id, e)
            return None

    def get_all_latest_ratings_map(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает словарь рейтингов по всем облигациям (secid -> all_ratings).

        Выполняет один SQL-запрос с JOIN bond_ratings, bonds и rating_agency.
        Структура результата совместима с форматом, ранее загружаемым из bonds_rating.json,
        для подмешивания рейтингов в DataLoader и выбора наихудшего рейтинга.

        Returns:
            Словарь: ключ — secid, значение — словарь с ключом "all_ratings"
            (список словарей рейтингов с полями agency_id, rating_level_name,
            rating_date, agency_name_short_ru, rating_level_name_short_ru).
        """
        stmt = text("""
            SELECT b.secid, br.agency_id, br.rating_level_name, br.rating_date, ra.agency_name_short_ru
            FROM bond_ratings br
            JOIN bonds b ON b.id = br.bond_id
            LEFT JOIN rating_agency ra ON ra.agency_id = br.agency_id
        """)
        with Session(self._engine) as session:
            rows = session.execute(stmt).fetchall()

        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            secid = row[0]
            if not secid:
                continue
            agency_name_short_ru = (row[4] or "").strip()
            # Совместимость со старым форматом: только рейтинги с заполненным агентством
            if not agency_name_short_ru:
                continue
            rating_level_name = (row[2] or "").strip()
            rating_record = {
                "agency_id": row[1],
                "rating_level_name": rating_level_name,
                "rating_date": row[3] or "",
                "agency_name_short_ru": agency_name_short_ru,
                "rating_level_name_short_ru": rating_level_name,
            }
            if secid not in result:
                result[secid] = {"all_ratings": []}
            # Дедупликация по agency_id: один рейтинг на агентство для данного secid
            existing_agency_ids = {r["agency_id"] for r in result[secid]["all_ratings"]}
            if row[1] not in existing_agency_ids:
                result[secid]["all_ratings"].append(rating_record)
        return result
