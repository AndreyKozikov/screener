"""Сервис пайплайна загрузки и сохранения рейтингов облигаций.

Извлекает облигации из БД, запрашивает рейтинги из API MOEX и сохраняет
результаты в таблицу bond_ratings. Без использования файлов.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from app.repository.db.bond_ratings_repository import BondRatingsRepository
from app.repository.db.bonds_repository import BondsRepository
from config.paths import DB_PATH

MOEX_SECURITIES_URL = "https://iss.moex.com/iss/securities/{secid}.json?iss.json=extended&iss.meta=off"
MOEX_RATINGS_URL = (
    "https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}/"
    "securities/isin_{secid}.json?iss.json=extended&iss.meta=off"
)
MOEX_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
MOEX_TIMEOUT = 30

AGENCY_ID_NO_RATING = -1
AGENCY_ID_AUTO = 0
MOEX_EMITENT_OFZ = 1228


class BondRatingsPipelineService:
    """Пайплайн загрузки рейтингов облигаций из MOEX API и сохранения в БД."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Инициализирует сервис.

        Args:
            db_path: Путь к файлу БД. Если не указан — backend/db/bonds.db.
        """
        self.db_path = db_path or DB_PATH
        self._bonds_repo = BondsRepository(db_path=self.db_path)
        self._ratings_repo = BondRatingsRepository(db_path=self.db_path)
        self.logger = logging.getLogger(__name__)

    def run_pipeline(self) -> Dict[str, int]:
        """Запускает пайплайн обновления рейтингов.

        Извлекает облигации из БД, для каждой определяет moex_emitent_id
        (из БД или API), запрашивает рейтинги из MOEX и сохраняет в bond_ratings.

        Returns:
            Словарь со статистикой: updated, errors, skipped.
        """
        bonds = self._bonds_repo.get_bonds_for_ratings_pipeline()
        total = len(bonds)
        self.logger.info("Запуск пайплайна рейтингов: облигаций для обработки: %s", total)

        updated = 0
        errors = 0
        skipped = 0

        for idx, (bond_id, secid, moex_emitent_id) in enumerate(bonds):
            if (idx + 1) % 100 == 0:
                self.logger.info(
                    "Обработано %s/%s: secid=%s", idx + 1, total, secid
                )
            try:
                emitent_id = moex_emitent_id
                if emitent_id is None:
                    emitent_id = self._fetch_emitent_id_from_moex(secid)
                if emitent_id is None:
                    self._save_empty_rating(bond_id)
                    skipped += 1
                    continue
                if emitent_id == MOEX_EMITENT_OFZ:
                    self._save_ofz_aaa_rating(bond_id)
                    updated += 1
                    continue
                ratings = self._fetch_ratings_from_moex(secid, emitent_id)
                if ratings:
                    self._ratings_repo.upsert_ratings_for_bond(bond_id, ratings)
                    updated += 1
                else:
                    self._save_empty_rating(bond_id)
                    updated += 1
            except Exception as e:
                self.logger.exception(
                    "Ошибка при обработке bond_id=%s secid=%s: %s",
                    bond_id,
                    secid,
                    e,
                )
                errors += 1

        self.logger.info(
            "Пайплайн рейтингов завершён: updated=%s, errors=%s, skipped=%s",
            updated,
            errors,
            skipped,
        )
        return {
            "total_bonds": total,
            "updated": updated,
            "errors": errors,
            "skipped": skipped,
        }

    def _fetch_emitent_id_from_moex(self, secid: str) -> Optional[int]:
        """Запрашивает EMITTER_ID из API MOEX по secid.

        Args:
            secid: Идентификатор ценной бумаги.

        Returns:
            MOEX emitent ID или None при ошибке или отсутствии в ответе.
        """
        url = MOEX_SECURITIES_URL.format(secid=secid)
        try:
            resp = requests.get(
                url,
                headers=MOEX_HEADERS,
                timeout=MOEX_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            self.logger.warning("MOEX API (securities) для %s: %s", secid, e)
            return None

        data = resp.json()
        if not isinstance(data, list) or len(data) < 2:
            return None
        for item in data:
            if isinstance(item, dict) and "description" in item:
                desc = item["description"]
                if not isinstance(desc, list):
                    continue
                for d in desc:
                    if isinstance(d, dict) and d.get("name") == "EMITTER_ID":
                        val = d.get("value")
                        if val is not None:
                            try:
                                return int(val)
                            except (TypeError, ValueError):
                                pass
                        return None
        return None

    def _fetch_ratings_from_moex(
        self,
        secid: str,
        emitent_id: int,
    ) -> List[Dict[str, Any]]:
        """Запрашивает рейтинги облигации из API MOEX.

        Args:
            secid: Идентификатор ценной бумаги.
            emitent_id: MOEX ID эмитента.

        Returns:
            Список словарей с полями agency_id, rating_level_name_short_ru,
            rating_date. Пустой список при ошибке.
        """
        url = MOEX_RATINGS_URL.format(secid=secid, emitent_id=emitent_id)
        try:
            resp = requests.get(
                url,
                headers=MOEX_HEADERS,
                timeout=MOEX_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            self.logger.warning("MOEX API (ratings) для %s: %s", secid, e)
            return []

        data = resp.json()
        raw_list = self._extract_cci_rating_securities(data)
        if not raw_list:
            return []

        result: List[Dict[str, Any]] = []
        for r in raw_list:
            if not isinstance(r, dict):
                continue
            agency_id = r.get("agency_id")
            if agency_id is None:
                continue
            try:
                agency_id = int(agency_id)
            except (TypeError, ValueError):
                continue
            rating_name = (r.get("rating_level_name_short_ru") or "").strip()
            rating_date = r.get("rating_date") or ""
            if isinstance(rating_date, str) and len(rating_date) > 19:
                rating_date = rating_date[:19]
            result.append(
                {
                    "agency_id": agency_id,
                    "rating_level_name": rating_name,
                    "rating_date": rating_date,
                }
            )
        return result

    def _extract_cci_rating_securities(self, data: Any) -> List[Any]:
        """Извлекает cci_rating_securities из ответа MOEX (разные форматы)."""
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "cci_rating_securities" in item:
                    arr = item["cci_rating_securities"]
                    if isinstance(arr, list):
                        return arr
                    if isinstance(arr, dict) and "data" in arr:
                        cols = arr.get("columns", [])
                        rows = arr.get("data", [])
                        return [
                            dict(zip(cols, row))
                            for row in rows
                            if len(row) == len(cols)
                        ]
            potential = [
                x for x in data
                if isinstance(x, dict) and "agency_id" in x
            ]
            if potential:
                return potential
        if isinstance(data, dict) and "cci_rating_securities" in data:
            arr = data["cci_rating_securities"]
            if isinstance(arr, list):
                return arr
            if isinstance(arr, dict) and "data" in arr:
                cols = arr.get("columns", [])
                rows = arr.get("data", [])
                return [
                    dict(zip(cols, row))
                    for row in rows
                    if len(row) == len(cols)
                ]
        return []

    def _save_empty_rating(self, bond_id: int) -> None:
        """Сохраняет пустой рейтинг (agency_id=-1) для облигации."""
        self._ratings_repo.upsert_ratings_for_bond(
            bond_id,
            [
                {
                    "agency_id": AGENCY_ID_NO_RATING,
                    "rating_level_name": "",
                    "rating_date": "",
                }
            ],
        )

    def _save_ofz_aaa_rating(self, bond_id: int) -> None:
        """Сохраняет рейтинг AAA для ОФЗ (agency_id=0)."""
        self._ratings_repo.upsert_ratings_for_bond(
            bond_id,
            [
                {
                    "agency_id": AGENCY_ID_AUTO,
                    "rating_level_name": "AAA",
                    "rating_date": "",
                }
            ],
        )

    def get_ratings_by_secid(self, secid: str) -> List[Dict[str, Any]]:
        """Возвращает рейтинги облигации по SECID из БД.

        Args:
            secid: Идентификатор ценной бумаги.

        Returns:
            Список словарей с полями agency_id, rating_level_name, rating_date,
            agency_name_short_ru.
        """
        return self._ratings_repo.get_ratings_by_secid(secid)
