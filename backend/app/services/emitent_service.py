"""Сервис для работы с данными эмитентов из API MOEX.

Этот модуль содержит класс EmitentService для загрузки данных об эмитентах
облигаций из API Московской биржи. Данные возвращаются в оперативную память
и передаются в репозиторий для записи в БД без промежуточного хранения в файлах.
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
    """Сервис для работы с данными эмитентов из API MOEX.

    Класс обеспечивает загрузку данных об эмитентах облигаций из API Московской биржи.
    Данные возвращаются в памяти и передаются в EmitentsRepository для записи в БД.
    Поддерживает получение данных по SECID или ISIN, загрузку рейтингов эмитентов
    и массовое обновление данных для всех облигаций.

    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
        _emitents_repository: Репозиторий для доступа к данным эмитентов в БД.
    """

    def __init__(
        self,
        data_dir: Path,
        emitents_repository: Optional[Any] = None,
    ):
        """Инициализирует сервис для работы с эмитентами.

        Args:
            data_dir: Путь к директории с JSON файлами данных.
            emitents_repository: Репозиторий EmitentsRepository для чтения из БД.
        """
        self.data_dir = data_dir
        self._emitents_repository = emitents_repository

    def get_secid_to_emitent_title_index(self) -> Dict[str, str]:
        """Получает индекс маппинга SECID на название эмитента из БД.

        Создает словарь для быстрого поиска названия эмитента по SECID облигации.
        Используется для фильтрации облигаций по эмитенту в сервисном слое.

        Returns:
            Словарь, где ключ - SECID облигации, значение - название эмитента.
        """
        if self._emitents_repository is None:
            logger.warning("EmitentsRepository не инициализирован, возвращаю пустой индекс")
            return {}
        return self._emitents_repository.get_secid_to_emitent_title_index()

    def get_emitent_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Получает данные эмитента по SECID из БД.

        Args:
            secid: Идентификатор облигации (SECID) для поиска данных эмитента.

        Returns:
            Полные данные эмитента в формате API MOEX или None, если не найдены в БД.
        """
        if self._emitents_repository is None:
            return None
        return self._emitents_repository.get_emitent_data_by_secid(secid)

    def extract_required_fields(self, emitent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлекает только необходимые поля из полного ответа API MOEX.

        Args:
            emitent_data: Полные данные эмитента из ответа API MOEX.

        Returns:
            Словарь с извлеченными полями: is_traded, emitent_title, emitent_inn,
            type, cci_rating_companies.
        """
        return {
            "is_traded": emitent_data.get("is_traded"),
            "emitent_title": emitent_data.get("emitent_title"),
            "emitent_inn": emitent_data.get("emitent_inn"),
            "type": emitent_data.get("type"),
            "cci_rating_companies": emitent_data.get("cci_rating_companies"),
        }

    def fetch_emitent_from_moex(self, secid: str) -> Optional[Dict[str, Any]]:
        """Загружает данные эмитента из API MOEX по SECID без побочных эффектов.

        Выполняет HTTP запрос к API Московской биржи для получения данных об эмитенте
        по SECID облигации. Также загружает рейтинги эмитента по emitent_id.

        Args:
            secid: Идентификатор облигации (SECID) для поиска данных эмитента.

        Returns:
            Полные данные эмитента из ответа API MOEX (словарь со всеми полями,
            включая рейтинги в cci_rating_companies) или None при ошибке.
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
                logger.debug("Fetching ratings for emitent_id=%s", emitent_id_int)
                ratings = self._fetch_emitent_ratings(emitent_id_int)
                if ratings is not None:
                    emitent_info["cci_rating_companies"] = ratings
                    logger.debug("Added %s ratings to emitent data", len(ratings))
            except (ValueError, TypeError) as exc:
                logger.warning("Invalid emitent_id format: %s, error: %s", emitent_id, exc)

        return emitent_info

    def _fetch_emitent_ratings(self, emitent_id: int) -> Optional[List[Dict[str, Any]]]:
        """Загружает рейтинги эмитента из API MOEX по emitent_id.

        Args:
            emitent_id: Идентификатор эмитента для загрузки рейтингов.

        Returns:
            Список словарей с данными рейтингов или None при ошибке.
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
        """Получает данные эмитента по SECID: сначала из БД, при отсутствии — из API MOEX.

        Args:
            secid: Идентификатор облигации (SECID).

        Returns:
            Полные данные эмитента или None, если не найдены ни в БД, ни в API.
        """
        emitent_data = self.get_emitent_by_secid(secid)
        if emitent_data is not None:
            return emitent_data
        return self.fetch_emitent_from_moex(secid)

    async def get_isin_by_secid(self, secid: str) -> Optional[str]:
        """Получает ISIN код облигации по SECID из данных облигаций.

        Args:
            secid: Идентификатор облигации (SECID) для поиска ISIN.

        Returns:
            ISIN код облигации или None, если облигация не найдена.
        """
        loader = get_data_loader()
        details = await loader.get_bond_details()

        if secid not in details:
            return None

        bond_data = details[secid]
        securities = bond_data.get("securities", {})
        return securities.get("ISIN")

    def _fetch_emitent_from_moex_by_secid(self, secid: str) -> Optional[Dict[str, Any]]:
        """Загружает данные эмитента из API MOEX по SECID (вспомогательный метод).

        Используется для массового обновления в refresh_all_emitents.

        Args:
            secid: Идентификатор облигации (SECID).

        Returns:
            Полные данные эмитента из API или None.
        """
        return self.fetch_emitent_from_moex(secid)

    def refresh_all_emitents(
        self, bonds_details: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Обновляет данные эмитентов для всех облигаций, возвращая их в памяти.

        Итерируется по bonds_details, загружает данные эмитентов из API MOEX
        и возвращает словарь {secid: api_response} без записи в файлы.

        Args:
            bonds_details: Словарь {secid: bond_data} с детальной информацией
                об облигациях (ключ SECID используется для запроса к MOEX).

        Returns:
            Словарь с ключами:
            - data: Dict[str, Dict] — {secid: полный ответ API MOEX}
            - total: int — количество облигаций для обработки
            - updated: int — успешно загружено
            - errors: int — ошибки при загрузке
            - skipped: int — пропущено (пустой SECID)
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


# Singleton instance
_emitent_service: Optional[EmitentService] = None


def init_emitent_service(
    data_dir: Path,
    emitents_repository: Optional[Any] = None,
) -> None:
    """Инициализирует singleton экземпляр сервиса эмитентов.

    Args:
        data_dir: Путь к директории с JSON файлами данных.
        emitents_repository: Репозиторий EmitentsRepository для чтения из БД.
    """
    global _emitent_service
    _emitent_service = EmitentService(data_dir=data_dir, emitents_repository=emitents_repository)


def get_emitent_service() -> EmitentService:
    """Получает singleton экземпляр сервиса эмитентов.

    Returns:
        Экземпляр EmitentService.

    Raises:
        RuntimeError: Если сервис не был инициализирован.
    """
    if _emitent_service is None:
        raise RuntimeError("Emitent service not initialized")
    return _emitent_service
