"""Клиент для загрузки данных с биржи MOEX по HTTP.

Этот модуль содержит класс MoexClient для выполнения сетевых запросов
к API MOEX и первичной обработки ошибок (сеть, таймаут, некорректный JSON).
"""

from typing import Any, Dict, List, Optional

import logging
from conversion_service.app.utils.coupon_utils import clean_string_value, extract_coupon_for_storage
from conversion_service.app.utils.moex_http import MoexHttpClient, get_moex_http_client
from conversion_service.config.paths import MOEX_BONDIZATION_BASE_URL, MOEX_COUPONS_QUERY


class MoexClient:
    """Клиент для загрузки данных с биржи MOEX по HTTP.

    Выполняет HTTP GET запросы к указанному URL, возвращает распарсенный JSON.
    Обрабатывает сетевые ошибки и ошибки парсинга JSON.

    Attributes:
        _http: Общий HTTP-клиент MOEX с лимитом частоты и ретраями.
    """

    def __init__(self, http_client: Optional[MoexHttpClient] = None):
        """Инициализирует клиент MOEX.

        Args:
            http_client: Общий HTTP-клиент MOEX; по умолчанию берется синглтон процесса.
        """
        self._http = http_client or get_moex_http_client()
        self._logger = logging.getLogger(__name__)


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
        url = f"{MOEX_BONDIZATION_BASE_URL.format(secid=secid)}{MOEX_COUPONS_QUERY}"

        try:
            payload = self._http.get_json(url)
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed to download coupons data for {secid}: {exc}"
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
