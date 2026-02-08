"""Репозиторий для работы с таблицей emitents и emitent_ratings.

Принимает данные из API MOEX в памяти, извлекает уникальные эмитенты по inn,
выполняет UPSERT в таблицу emitents, сохраняет рейтинги эмитентов в emitent_ratings
и возвращает маппинг secid -> emitent_id (id из БД).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlmodel import Session, create_engine, select

from app.models.emitent import Emitent
from app.utils.logger import get_data_update_logger
from config.paths import DATA_DIR, DB_PATH


class EmitentsRepository:
    """Репозиторий для работы с эмитентами облигаций."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        data_dir: Optional[Path] = None,
    ):
        """Инициализирует репозиторий.

        Args:
            db_path: Путь к файлу БД. По умолчанию — backend/db/bonds.db.
            data_dir: Директория с данными. По умолчанию — backend/app/data.
        """
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._engine = create_engine(
            f"sqlite:///{self.db_path.resolve()}",
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self.logger = logging.getLogger(__name__)

    def convert_api_data_to_models(
        self,
        api_data: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, List[Dict[str, Any]]]]:
        """Преобразует данные из API MOEX в модели для записи в БД.

        Выполняет ту же логику парсинга, что была в parse_bonds_emitent_json,
        но работает с данными в памяти без обращения к файлам.

        Args:
            api_data: Словарь {secid: полный ответ API MOEX} из EmitentService.refresh_all_emitents.

        Returns:
            Кортеж:
            - Список уникальных эмитентов (словари с moex_id, inn, okpo, title, type).
            - Маппинг secid -> inn для построения secid -> emitent_id после upsert.
            - Маппинг inn -> cci_rating_companies (рейтинги).
        """
        if not isinstance(api_data, dict) or not api_data:
            return [], {}, {}

        unique_by_inn: Dict[str, Dict[str, Any]] = {}
        secid_to_inn: Dict[str, str] = {}

        for secid, entry in api_data.items():
            if not isinstance(entry, dict):
                continue

            inn = entry.get("emitent_inn")
            if inn is None or str(inn).strip() == "":
                continue

            inn_str = str(inn).strip()
            secid_to_inn[secid] = inn_str

            if inn_str not in unique_by_inn:
                moex_id = entry.get("emitent_id")
                if moex_id is not None and not isinstance(moex_id, int):
                    try:
                        moex_id = int(moex_id)
                    except (TypeError, ValueError):
                        moex_id = None

                okpo = entry.get("emitent_okpo")
                if okpo is not None:
                    okpo = str(okpo).strip() or None

                title = entry.get("emitent_title")
                if title is not None:
                    title = str(title).strip() or None

                bond_type = entry.get("type")
                if bond_type is not None:
                    bond_type = str(bond_type).strip() or None

                cci_rating_companies = entry.get("cci_rating_companies")
                if not isinstance(cci_rating_companies, list):
                    cci_rating_companies = []

                unique_by_inn[inn_str] = {
                    "moex_id": moex_id,
                    "inn": inn_str,
                    "okpo": okpo,
                    "title": title,
                    "type": bond_type,
                    "cci_rating_companies": cci_rating_companies,
                }

        emitents_list = [
            {k: v for k, v in e.items() if k != "cci_rating_companies"}
            for e in unique_by_inn.values()
        ]
        inn_to_ratings: Dict[str, List[Dict[str, Any]]] = {
            inn: (unique_by_inn[inn].get("cci_rating_companies") or [])
            for inn in unique_by_inn
        }

        self.logger.debug(
            "Из данных API извлечено %s уникальных эмитентов (по inn), %s secid",
            len(emitents_list),
            len(secid_to_inn),
        )
        return emitents_list, secid_to_inn, inn_to_ratings

    def _get_rating_agency_pk_map(self, session: Session) -> Dict[int, int]:
        """Строит маппинг agency_id из MOEX (ключ) -> id из rating_agency (значение)."""
        result = session.execute(text("SELECT agency_id, id FROM rating_agency")).fetchall()
        return {int(row[0]): int(row[1]) for row in result}

    def _parse_rating_date(self, value: Any) -> Optional[str]:
        """Приводит значение даты рейтинга к строке для SQLite DATETIME."""
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None

    def upsert_emitent_ratings(
        self,
        emitent_id: int,
        cci_rating_companies: List[Dict[str, Any]],
    ) -> bool:
        """Сохраняет рейтинги эмитента из cci_rating_companies в emitent_ratings (UPSERT)."""
        if not cci_rating_companies:
            return True
        stmt = text("""
            INSERT INTO emitent_ratings (
                emitent_id, agency_id, rating_level_name, rating_date, rating_publicate_date
            )
            VALUES (
                :emitent_id, :agency_id, :rating_level_name, :rating_date, :rating_publicate_date
            )
            ON CONFLICT(emitent_id, agency_id) DO UPDATE SET
                rating_level_name = excluded.rating_level_name,
                rating_date = excluded.rating_date,
                rating_publicate_date = excluded.rating_publicate_date
        """)
        try:
            with Session(self._engine) as session:
                agency_pk_map = self._get_rating_agency_pk_map(session)
                for item in cci_rating_companies:
                    if not isinstance(item, dict):
                        continue
                    json_agency_id = item.get("agency_id")
                    if json_agency_id is None:
                        continue
                    try:
                        json_agency_id = int(json_agency_id)
                    except (TypeError, ValueError):
                        continue
                    agency_pk = agency_pk_map.get(json_agency_id)
                    if agency_pk is None:
                        self.logger.debug(
                            "Пропуск рейтинга: agency_id=%s не найден в rating_agency",
                            json_agency_id,
                        )
                        continue
                    rating_level_name = item.get("rating_level_name_short_ru") or item.get("rating_level_name")
                    if rating_level_name is not None:
                        rating_level_name = str(rating_level_name).strip() or None
                    rating_date = self._parse_rating_date(item.get("rating_date"))
                    rating_publicate_date = self._parse_rating_date(item.get("rating_publicate_date"))
                    session.execute(
                        stmt,
                        {
                            "emitent_id": emitent_id,
                            "agency_id": agency_pk,
                            "rating_level_name": rating_level_name,
                            "rating_date": rating_date,
                            "rating_publicate_date": rating_publicate_date,
                        },
                    )
                session.commit()
            return True
        except Exception as e:
            self.logger.warning("Ошибка при сохранении emitent_ratings для emitent_id=%s: %s", emitent_id, e)
            return False

    def refresh(self, api_data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """UPSERT эмитентов в БД и рейтингов в emitent_ratings.

        Принимает данные напрямую от EmitentService.refresh_all_emitents (ключ "data").
        Выполняет convert_api_data_to_models, UPSERT в emitents, upsert рейтингов,
        возвращает маппинг secid -> emitent_id. Использует транзакции для атомарности.

        Args:
            api_data: Словарь {secid: полный ответ API MOEX} или None (возвращает {}).

        Returns:
            Словарь {secid: emitent_id}. Пустой при отсутствии данных или ошибке.
        """
        if api_data is None or not api_data:
            self.logger.debug("Нет данных API для сохранения эмитентов")
            return {}

        emitents_list, secid_to_inn, inn_to_ratings = self.convert_api_data_to_models(api_data)
        if not emitents_list:
            return {}

        data_log = get_data_update_logger()

        stmt = text("""
            INSERT INTO emitents (moex_id, inn, okpo, title, type)
            VALUES (:moex_id, :inn, :okpo, :title, :type)
            ON CONFLICT(inn) DO UPDATE SET
                moex_id = excluded.moex_id,
                okpo = excluded.okpo,
                title = excluded.title,
                type = excluded.type
        """)

        try:
            with Session(self._engine) as session:
                for e in emitents_list:
                    session.execute(stmt, e)
                session.commit()

            inn_to_id: Dict[str, int] = {}
            with Session(self._engine) as sess:
                rows = sess.exec(select(Emitent.inn, Emitent.id)).all()
                for inn, eid in rows:
                    if inn is not None:
                        inn_to_id[inn] = eid or 0

            ratings_count = 0
            for inn, emitent_id in inn_to_id.items():
                ratings = inn_to_ratings.get(inn, [])
                if ratings:
                    if self.upsert_emitent_ratings(emitent_id, ratings):
                        ratings_count += 1

            secid_to_emitent_id: Dict[str, int] = {}
            for secid, inn in secid_to_inn.items():
                if inn in inn_to_id:
                    secid_to_emitent_id[secid] = inn_to_id[inn]

            data_log.info(
                "[API /emitent/refresh] В таблицу emitents записано: %s эмитентов, "
                "маппинг secid->id: %s записей, рейтинги обновлены для %s эмитентов",
                len(emitents_list),
                len(secid_to_emitent_id),
                ratings_count,
            )
            self.logger.info(
                "Emitents: upsert %s записей, маппинг secid->emitent_id: %s, "
                "emitent_ratings для %s эмитентов",
                len(emitents_list),
                len(secid_to_emitent_id),
                ratings_count,
            )
            return secid_to_emitent_id

        except Exception as e:
            data_log.error(
                "[API /emitent/refresh] Ошибка при записи в emitents: %s",
                e,
                exc_info=True,
            )
            self.logger.error("Ошибка при сохранении emitents: %s", e, exc_info=True)
            return {}

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
            JOIN emitents e ON b.emitent_id = e.id
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
                    SELECT ra.agency_id, er.rating_level_name, er.rating_date, er.rating_publicate_date
                    FROM emitent_ratings er
                    JOIN rating_agency ra ON er.agency_id = ra.id
                    WHERE er.emitent_id = :emitent_id
                """)
                rating_rows = session.execute(ratings_stmt, {"emitent_id": emitent_id_db}).fetchall()

                cci_rating_companies: List[Dict[str, Any]] = []
                for r in rating_rows:
                    agency_id, rating_level_name, rating_date, rating_publicate_date = r
                    cci_rating_companies.append({
                        "agency_id": agency_id,
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

    def get_secid_to_emitent_title_index(self) -> Dict[str, str]:
        """Возвращает маппинг SECID облигации -> название эмитента из БД."""
        stmt = text("""
            SELECT b.secid, e.title
            FROM bonds b
            JOIN emitents e ON b.emitent_id = e.id
            WHERE e.title IS NOT NULL AND trim(e.title) != ''
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt).fetchall()
                return {str(row[0]): str(row[1]).strip() for row in rows if row[0] and row[1]}
        except Exception as e:
            self.logger.warning("Ошибка при чтении secid->title: %s", e)
            return {}

    def get_secid_to_bondtype_map(self) -> Dict[str, str]:
        """Возвращает маппинг SECID облигации -> тип облигации (type) из БД."""
        stmt = text("""
            SELECT b.secid, e.type
            FROM bonds b
            JOIN emitents e ON b.emitent_id = e.id
            WHERE e.type IS NOT NULL AND trim(e.type) != ''
        """)
        try:
            with Session(self._engine) as session:
                rows = session.execute(stmt).fetchall()
                return {str(row[0]): str(row[1]).strip() for row in rows if row[0] and row[1]}
        except Exception as e:
            self.logger.warning("Ошибка при чтении secid->bondtype: %s", e)
            return {}
