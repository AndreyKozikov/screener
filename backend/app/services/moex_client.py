"""Клиент для загрузки данных с биржи MOEX по HTTP.

Этот модуль содержит класс MoexClient для выполнения сетевых запросов
к API MOEX и первичной обработки ошибок (сеть, таймаут, некорректный JSON).
"""

from typing import Any, Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson

from app.utils.coupon_utils import clean_string_value, extract_coupon_for_storage
from app.utils.logger import get_data_update_logger

BONDIZATION_BASE_URL = "https://iss.moex.com/iss/securities/{secid}/bondization.json"


class MoexClient:
    """Клиент для загрузки данных с биржи MOEX по HTTP.

    Выполняет HTTP GET запросы к указанному URL, возвращает распарсенный JSON.
    Обрабатывает сетевые ошибки и ошибки парсинга JSON.

    Attributes:
        timeout: Таймаут запроса в секундах (по умолчанию 30).
        user_agent: Заголовок User-Agent для запроса.
    """

    def __init__(self, timeout: int = 30, user_agent: str = "Mozilla/5.0"):
        """Инициализирует клиент MOEX.

        Args:
            timeout: Таймаут HTTP запроса в секундах.
            user_agent: Значение заголовка User-Agent.
        """
        self.timeout = timeout
        self.user_agent = user_agent
        self._logger = get_data_update_logger()

    def fetch_bonds_json(self, url: str) -> Dict[str, Any]:
        """Загружает JSON данные об облигациях по указанному URL.

        Выполняет HTTP GET запрос, читает тело ответа и парсит JSON.
        При сетевой ошибке или некорректном JSON возбуждает RuntimeError.

        Args:
            url: URL для загрузки (например, MOEX bonds API).

        Returns:
            Словарь с данными в формате MOEX (секции securities, marketdata,
            marketdata_yields и т.д.).

        Raises:
            RuntimeError: Если не удалось выполнить запрос (URLError, таймаут)
                или если ответ не является валидным JSON.
        """
        self._logger.info(f"[MOEX] Загрузка данных с {url}")
        request = Request(url, headers={"User-Agent": self.user_agent})

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_payload = response.read()
            self._logger.info(f"[MOEX] Загружено {len(raw_payload)} байт")
        except URLError as exc:
            self._logger.error(f"[MOEX] Ошибка загрузки с {url}: {exc}")
            raise RuntimeError(f"Failed to download bonds data: {exc}") from exc

        try:
            payload = orjson.loads(raw_payload)
            self._logger.info("[MOEX] JSON успешно распарсен")
            return payload
        except orjson.JSONDecodeError as exc:
            self._logger.error(f"[MOEX] Некорректный JSON: {exc}")
            raise RuntimeError(
                "Received invalid JSON while refreshing bonds data"
            ) from exc

    def fetch_coupons(self, secid: str) -> Dict[str, Any]:
        """Загружает данные о купонах облигации из API MOEX.

        Выполняет HTTP GET к bondization API. Парсит ответ и возвращает
        структурированные данные (coupons, amortizations, offers).
        Обрабатывает сетевые ошибки и некорректный JSON.

        Args:
            secid: Идентификатор облигации (SECID) для загрузки данных.

        Returns:
            Словарь с ключами: coupons, amortizations, offers.
            coupons — список словарей с данными купонов.
            amortizations — список, создается из первого купона.
            offers — пустой список (API не возвращает оферты).

        Raises:
            RuntimeError: При сетевой ошибке, таймауте или некорректном формате ответа.
        """
        url = (
            f"{BONDIZATION_BASE_URL.format(secid=secid)}"
            "?iss.json=extended&iss.meta=off&iss.only=coupons&lang=ru&limit=unlimited"
        )
        request = Request(url, headers={"User-Agent": self.user_agent})

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_payload = response.read()
        except URLError as exc:
            raise RuntimeError(
                f"Failed to download coupons data for {secid}: {exc}"
            ) from exc

        try:
            payload = orjson.loads(raw_payload)
        except orjson.JSONDecodeError as exc:
            raise RuntimeError(
                f"Received invalid JSON for {secid}: {exc}"
            ) from exc

        result: Dict[str, List[Dict[str, Any]]] = {
            "amortizations": [],
            "coupons": [],
            "offers": [],
        }

        if not isinstance(payload, list) or len(payload) < 2:
            raise RuntimeError(
                f"Unexpected API response format for {secid}: "
                "expected array with at least 2 elements"
            )

        coupons_data = payload[1].get("coupons", [])
        if not isinstance(coupons_data, list):
            raise RuntimeError(
                f"Unexpected coupons format for {secid}: "
                f"expected array, got {type(coupons_data).__name__}"
            )

        first_coupon_raw = None
        for coupon_dict in coupons_data:
            copy = coupon_dict.copy() if isinstance(coupon_dict, dict) else coupon_dict
            cleaned = clean_string_value(copy)
            result["coupons"].append(extract_coupon_for_storage(cleaned))
            if first_coupon_raw is None:
                first_coupon_raw = cleaned

        if first_coupon_raw is not None:
            amort_entry = {
                "isin": first_coupon_raw.get("isin"),
                "name": first_coupon_raw.get("name"),
                "issuevalue": first_coupon_raw.get("issuevalue"),
                "secid": first_coupon_raw.get("secid") or secid,
                "primary_boardid": first_coupon_raw.get("primary_boardid"),
                "facevalue": first_coupon_raw.get("facevalue"),
                "initialfacevalue": first_coupon_raw.get("initialfacevalue"),
                "faceunit": first_coupon_raw.get("faceunit"),
            }
            result["amortizations"].append(clean_string_value(amort_entry))

        return result
