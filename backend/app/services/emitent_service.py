"""Модуль для работы с данными эмитентов через API Московской биржи (MOEX).

Обеспечивает загрузку, обновление и маппинг информации об эмитентах облигаций.
Включает механизмы получения кредитных рейтингов эмитентов и синхронизации этих данных
с локальной базой данных приложения.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson
import requests

from app.services.data_loader import get_data_loader
from app.utils.logger import get_data_update_logger

logger = get_data_update_logger()


class EmitentService:
    """Сервис управления данными эмитентов.

    Класс инкапсулирует бизнес-логику взаимодействия с API MOEX для получения
    подробной информации об организациях-эмитентах, включая их ИНН, официальные
    названия и актуальные кредитные рейтинги.

    Attributes:
        data_dir (Path): Путь к директории с конфигурационными файлами.
        _emitents_repository (Optional[EmitentsRepository]): Репозиторий для работы с БД.
    """

    def __init__(
        self,
        data_dir: Path,
        emitents_repository: Optional[Any] = None,
    ):
        """Инициализирует экземпляр сервиса эмитентов.

        Args:
            data_dir (Path): Путь к директории с конфигурационными файлами.
            emitents_repository (Optional[Any]): Репозиторий для взаимодействия с БД.
        """
        self.data_dir = data_dir
        self._emitents_repository = emitents_repository

    def get_secid_to_emitent_title_index(self) -> Dict[str, str]:
        """Строит карту соответствия SECID и названия эмитента.

        Используется для быстрого поиска названия организации при фильтрации в скринере.

        Returns:
            Dict[str, str]: Словарь {SECID: Название_эмитента}.
        """
        if self._emitents_repository is None:
            logger.warning("EmitentsRepository не инициализирован, возвращаю пустой индекс")
            return {}
        return self._emitents_repository.get_secid_to_emitent_title_index()

    def get_emitent_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Извлекает данные эмитента для конкретной бумаги из базы данных.

        Args:
            secid (str): Идентификатор облигации.

        Returns:
            Optional[Dict[str, Any]]: Словарь с данными эмитента или None.
        """
        if self._emitents_repository is None:
            return None
        return self._emitents_repository.get_emitent_data_by_secid(secid)

    def extract_required_fields(self, emitent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Фильтрует сырые данные API, оставляя только необходимые поля.

        Args:
            emitent_data (Dict[str, Any]): Полный ответ от API MOEX.

        Returns:
            Dict[str, Any]: Словарь с ключевыми характеристиками эмитента.
        """
        return {
            "is_traded": emitent_data.get("is_traded"),
            "emitent_title": emitent_data.get("emitent_title"),
            "emitent_inn": emitent_data.get("emitent_inn"),
            "type": emitent_data.get("type"),
            "cci_rating_companies": emitent_data.get("cci_rating_companies"),
        }

    def fetch_emitent_from_moex(self, secid: str) -> Optional[Dict[str, Any]]:
        """Запрашивает актуальную информацию об эмитенте напрямую из MOEX ISS API.

        Args:
            secid (str): Идентификатор облигации.

        Returns:
            Optional[Dict[str, Any]]: Структурированные данные эмитента, включая рейтинги.
        """
        url = f"https://iss.moex.com/iss/securities.json?q={secid}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

        try:
            with urlopen(request, timeout=30) as response:
                raw_payload = response.read()
        except URLError as exc:
            logger.warning("Failed to fetch emitent data from MOEX: %s", exc)
            return None

        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            logger.warning("Invalid JSON response from MOEX: %s", exc)
            return None

        securities = payload.get("securities", {})
        columns = securities.get("columns", [])
        data = securities.get("data", [])

        if not data:
            return None

        secid_idx = columns.index("secid") if "secid" in columns else None
        if secid_idx is None:
            return None

        secid_normalized = (secid or "").strip().upper()
        matching_row = None
        for row in data:
            if len(row) > secid_idx and (row[secid_idx] or "").strip().upper() == secid_normalized:
                matching_row = row
                break

        if matching_row is None:
            return None

        emitent_info: Dict[str, Any] = {}
        for idx, column_name in enumerate(columns):
            if idx < len(matching_row):
                emitent_info[column_name] = matching_row[idx]

        emitent_id = emitent_info.get("emitent_id")
        if emitent_id is not None:
            try:
                emitent_id_int = int(emitent_id)

                ratings = self._fetch_emitent_ratings(emitent_id_int)
                if ratings is not None:
                    emitent_info["cci_rating_companies"] = ratings

            except (ValueError, TypeError) as exc:
                logger.warning("Invalid emitent_id format: %s, error: %s", emitent_id, exc)

        return emitent_info

    def _fetch_emitent_ratings(self, emitent_id: int) -> Optional[List[Dict[str, Any]]]:
        """Загружает историю кредитных рейтингов эмитента.

        Args:
            emitent_id (int): Внутренний ID эмитента на MOEX.

        Returns:
            Optional[List[Dict[str, Any]]]: Список рейтингов от различных агентств.
        """
        url = f"https://iss.moex.com/iss/cci/rating/companies/ecbd_{emitent_id}.json?iss.json=extended&iss.meta=off"

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=30,
            )
            response.raise_for_status()
            json_data = response.json()

            if not isinstance(json_data, list) or len(json_data) < 2:
                logger.debug("Unexpected JSON structure for ratings")
                return None

            for item in json_data:
                if isinstance(item, dict) and "cci_rating_companies" in item:
                    ratings_data = item["cci_rating_companies"]
                    if isinstance(ratings_data, list):
                        logger.debug("Found %s rating entries for emitent_id=%s", len(ratings_data), emitent_id)
                        return ratings_data
                    return None

            logger.debug("Could not find cci_rating_companies in JSON response")
            return None

        except requests.RequestException as exc:
            logger.warning("Failed to fetch emitent ratings from MOEX: %s", exc)
            return None
        except Exception as exc:
            logger.warning("Error processing emitent ratings: %s", exc)
            return None

    def get_or_fetch_emitent(self, secid: str) -> Optional[Dict[str, Any]]:
        """Обеспечивает получение данных эмитента с приоритетом локальной БД.

        Args:
            secid (str): Идентификатор облигации.

        Returns:
            Optional[Dict[str, Any]]: Данные эмитента.
        """
        emitent_data = self.get_emitent_by_secid(secid)
        if emitent_data is not None:
            return emitent_data
        return self.fetch_emitent_from_moex(secid)

    async def get_isin_by_secid(self, secid: str) -> Optional[str]:
        """Определяет ISIN код облигации по её SECID.

        Args:
            secid (str): Идентификатор облигации.

        Returns:
            Optional[str]: Международный код ISIN.
        """
        loader = get_data_loader()
        details = await loader.get_bond_details()

        if secid not in details:
            return None

        bond_data = details[secid]
        securities = bond_data.get("securities", {})
        return securities.get("ISIN")

    def _fetch_emitent_from_moex_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Вспомогательный метод для загрузки эмитента."""
        return self.fetch_emitent_from_moex(secid)


    def refresh_all_emitents(
        self, bonds_details: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Выполняет массовое обновление данных эмитентов для списка облигаций.

        Args:
            bonds_details (Dict[str, Dict]): Детальные данные облигаций для обработки.

        Returns:
            Dict[str, Any]: Результаты обновления со статистикой.
        """
        total_bonds = len(bonds_details)
        updated_count = 0
        error_count = 0
        skipped_count = 0
        api_data: Dict[str, Dict[str, Any]] = {}

        logger.info(
            "[Emitent Refresh] Starting update for %s bonds from MOEX API",
            total_bonds,
        )

        processed = 0
        for secid, bond_data in bonds_details.items():
            processed += 1

            try:
                if not (secid or "").strip():
                    skipped_count += 1
                    logger.info("[%s/%s] SKIPPED: empty SECID", processed, total_bonds)
                    continue

                url = f"https://iss.moex.com/iss/securities.json?q={secid}"
                logger.info("[%s/%s] Processing: %s | URL: %s", processed, total_bonds, secid, url)
                
                emitent_data = self._fetch_emitent_from_moex_by_secid(secid)
                if emitent_data is not None:
                    api_data[secid] = emitent_data
                    updated_count += 1
                    
                    emitent_title = emitent_data.get("emitent_title", "N/A")
                    ratings_count = len(emitent_data.get("cci_rating_companies", []))
                    logger.info(
                        "[%s/%s] ✓ SUCCESS: %s | Emitent: %s | Ratings: %s",
                        processed,
                        total_bonds,
                        secid,
                        emitent_title[:50] if emitent_title else "N/A",
                        ratings_count,
                    )
                else:
                    error_count += 1
                    logger.warning(
                        "[%s/%s] ✗ FAILED: %s | No data from MOEX",
                        processed,
                        total_bonds,
                        secid,
                    )

            except Exception as exc:
                error_count += 1
                logger.error(
                    "[%s/%s] ✗ ERROR: %s | %s: %s",
                    processed,
                    total_bonds,
                    secid,
                    type(exc).__name__,
                    exc,
                )

        logger.info(
            "[Emitent Refresh] Completed: total=%s, updated=%s, errors=%s, skipped=%s",
            total_bonds,
            updated_count,
            error_count,
            skipped_count,
        )

        return {
            "data": api_data,
            "total": total_bonds,
            "updated": updated_count,
            "errors": error_count,
            "skipped": skipped_count,
        }

    def refresh_emitents_for_secids(
        self,
        secids: List[str],
        db_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Актуализирует данные об эмитентах для заданных идентификаторов и связывает их с бумагами.

        Args:
            secids (List[str]): Список SECID для обновления.
            db_path (Optional[Path]): Путь к базе данных.

        Returns:
            Dict[str, Any]: Статистика по количеству обработанных и связанных записей.
        """
        from config.paths import DB_PATH as DEFAULT_DB_PATH

        path = db_path if db_path is not None else DEFAULT_DB_PATH
        if not secids:
            return {
                "total": 0,
                "updated": 0,
                "errors": 0,
                "skipped": 0,
                "bonds_linked": 0,
            }
        bonds_details = {secid: {} for secid in secids if (secid or "").strip()}
        result = self.refresh_all_emitents(bonds_details)
        api_data = result.get("data") or {}
        summary = {
            "total": result.get("total", 0),
            "updated": result.get("updated", 0),
            "errors": result.get("errors", 0),
            "skipped": result.get("skipped", 0),
            "bonds_linked": 0,
        }
        if not api_data:
            return summary
        from app.repository.db.bonds_repository import BondsRepository
        from app.repository.db.emitents_repository import EmitentsRepository

        emitents_repo = EmitentsRepository(db_path=path, data_dir=self.data_dir)
        secid_to_emitent_id = emitents_repo.refresh(api_data)
        if secid_to_emitent_id:
            bonds_repo = BondsRepository(db_path=path)
            updated_rows = bonds_repo.update_emitent_ids(secid_to_emitent_id)
            summary["bonds_linked"] = updated_rows
        return summary


# Singleton instance
_emitent_service: Optional[EmitentService] = None


def init_emitent_service(
    data_dir: Path,
    emitents_repository: Optional[Any] = None,
) -> None:
    """Инициализирует глобальный синглтон сервиса эмитентов.

    Args:
        data_dir (Path): Путь к директории данных.
        emitents_repository (Optional[Any]): Репозиторий эмитентов.
    """
    global _emitent_service
    _emitent_service = EmitentService(data_dir=data_dir, emitents_repository=emitents_repository)


def get_emitent_service() -> EmitentService:
    """Возвращает инициализированный экземпляр сервиса эмитентов.

    Returns:
        EmitentService: Глобальный сервис.

    Raises:
        RuntimeError: Если сервис не был проинициализирован.
    """
    if _emitent_service is None:
        raise RuntimeError("Emitent service not initialized")
    return _emitent_service
