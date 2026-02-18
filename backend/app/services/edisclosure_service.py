"""Сервис для работы с e-disclosure.ru.

Содержит логику вызова методов из edisclosure_utils: поиск компаний по ИНН
и извлечение текстов событий. Эндпоинт вызывает get_accrued_income_by_secid(secid).
"""

from typing import Any, Dict, Optional

from app.services.bonds_service import get_emitent_inn_by_secid, get_reg_number_by_secid
from app.services.trading_history_service import get_trading_history_service
from app.utils.edisclosure_utils import (
    get_accrued_income_event_text,
    search_company_by_inn,
)

_DEFAULT_DATE = "2025-04-24"


class EdisclosureService:
    """Сервис для получения данных с e-disclosure.ru.

    Оркестрирует вызовы search_company_by_inn и get_accrued_income_event_text.
    Использует bonds_service для получения ИНН и регномера по secid,
    TradingHistoryService — для получения наименьшей даты из истории торгов.
    """

    def get_accrued_income_by_secid(self, secid: str) -> Dict[str, Any]:
        """Получает данные начисленных доходов по SECID облигации.

        1. Получает ИНН эмитента и регномер облигации по secid из БД.
        2. Получает наименьшую дату из таблицы истории торгов.
        3. Вызывает _get_accrued_income_by_inn с полученными параметрами.
        4. Возвращает результат для эндпоинта.

        Args:
            secid: Идентификатор ценной бумаги.

        Returns:
            Словарь с ключами companies, events, regnumber.

        Raises:
            ValueError: ИНН эмитента не найден.
        """
        secid = (secid or "").strip()
        if not secid:
            raise ValueError("SECID не указан")

        inn = get_emitent_inn_by_secid(secid)
        if not inn:
            raise ValueError(
                f"ИНН эмитента для облигации {secid} не найден в БД. "
                "Проверьте наличие данных об эмитенте."
            )

        regnumber = get_reg_number_by_secid(secid)

        trading_history_service = get_trading_history_service()
        first_tradedate = trading_history_service.get_first_tradedate(secid)
        date_str = (
            first_tradedate.isoformat()
            if first_tradedate is not None
            else _DEFAULT_DATE
        )

        return self._get_accrued_income_by_inn(
            inn=inn,
            date=date_str,
            regnumber=regnumber,
        )

    def _get_accrued_income_by_inn(
        self,
        inn: str,
        date: str = "2025-04-24",
        regnumber: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получает данные компании по ИНН и тексты событий с e-disclosure.ru.

        Вызывает search_company_by_inn и get_accrued_income_event_text.
        Вся логика вызова edisclosure_utils сосредоточена здесь.

        Args:
            inn: ИНН компании.
            date: Дата в формате YYYY-MM-DD.
            regnumber: Регистрационный номер (опционально, передаётся в utils).

        Returns:
            Словарь с ключами companies, events, regnumber.

        Raises:
            ValueError: Компания не найдена или не удалось получить ID.
        """
        companies = search_company_by_inn(inn)
        if not companies:
            raise ValueError(f"Компания с ИНН {inn} не найдена на e-disclosure.ru")

        company_id = companies[0].get("id")
        if company_id is None:
            raise ValueError("Не удалось получить ID компании из ответа e-disclosure")

        events = get_accrued_income_event_text(
            date=date,
            company_id=company_id,
        )

        return {
            "companies": companies,
            "events": events,
            "regnumber": regnumber,
        }


_edisclosure_service: Optional[EdisclosureService] = None


def get_edisclosure_service() -> EdisclosureService:
    """Возвращает singleton EdisclosureService."""
    global _edisclosure_service
    if _edisclosure_service is None:
        _edisclosure_service = EdisclosureService()
    return _edisclosure_service
