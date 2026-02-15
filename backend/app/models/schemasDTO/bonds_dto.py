"""DTO для отдачи данных облигаций на фронтенд.

Этот модуль содержит легковесные модели для API скринера облигаций.
BondScreenerDTO содержит только поля, необходимые для отображения в таблице;
BONDTYPE и BONDTYPE43 — строковые названия (маппинг из ID выполняется в сервисе).
"""

from datetime import date
from typing import Optional, List, Dict, Any

from pydantic import BaseModel


def round_float_for_api(value: Optional[float]) -> Optional[float]:
    """Округляет float до 2 знаков после запятой для отдачи в API.

    Args:
        value: Значение для округления или None.

    Returns:
        Округлённое значение или None.
    """
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


class BondScreenerDTO(BaseModel):
    """DTO облигации для отображения в таблице скринера на фронтенде.

    Содержит только поля, необходимые для отображения в таблице скринера.
    Все расчётные float-поля отдаются с округлением до 2 знаков после запятой.
    BONDTYPE и BONDTYPE43 — строковые названия (не числовые ID), маппинг из ID
    выполняется в bonds_service с использованием загруженных словарей типов/видов.

    Attributes:
        SECID: Идентификатор ценной бумаги.
        BOARDID: Идентификатор режима торгов.
        SHORTNAME: Краткое наименование облигации.
        SECNAME: Полное наименование ценной бумаги.
        ISIN: ISIN код облигации.
        COUPONPERCENT: Процентная ставка купона.
        MATDATE: Дата погашения облигации.
        STATUS: Статус облигации.
        TRADINGSTATUS: Статус торгов.
        FACEVALUE: Номинальная стоимость.
        PREVPRICE: Текущая/предыдущая цена.
        YIELDATPREVWAPRICE: Доходность к погашению.
        NEXTCOUPON: Дата следующей выплаты купона.
        BOARDNAME: Наименование режима торгов.
        CALLOPTIONDATE: Дата опциона на досрочный выкуп.
        PUTOPTIONDATE: Дата опциона на досрочную продажу.
        ACCRUEDINT: Накопленный купонный доход (НКД).
        COUPONPERIOD: Период купона в днях.
        COUPONVALUE: Сумма купона.
        DURATION: Дюрация в днях.
        DURATIONWAPRICE: Дюрация по средневзвешенной цене в днях.
        CURRENCYID: Валюта расчётов.
        FACEUNIT: Валюта номинала (столбец face_unit таблицы bond, для колонки «Валюта» на фронте).
        LISTLEVEL: Уровень листинга.
        RATING_AGENCY: Название рейтингового агентства.
        RATING_LEVEL: Уровень рейтинга (наихудший).
        RATINGS: Список всех рейтингов облигации.
        BONDTYPE: Тип облигации (строка, не ID).
        BONDTYPE43: Вид облигации (строка, не ID).
        COUPON_YIELD_TO_PRICE: Доходность купона к текущей цене, %.
        COUPON_FREQUENCY: Число выплат купона в год.
        DURATION_YEARS: Дюрация в годах.
    """

    SECID: str
    BOARDID: str
    SHORTNAME: str
    SECNAME: Optional[str] = None
    ISIN: Optional[str] = None
    COUPONPERCENT: Optional[float] = None
    MATDATE: Optional[date] = None
    STATUS: Optional[str] = None
    TRADINGSTATUS: Optional[str] = None
    FACEVALUE: Optional[float] = None
    PREVPRICE: Optional[float] = None
    YIELDATPREVWAPRICE: Optional[float] = None
    NEXTCOUPON: Optional[date] = None
    BOARDNAME: Optional[str] = None
    CALLOPTIONDATE: Optional[date] = None
    PUTOPTIONDATE: Optional[date] = None
    ACCRUEDINT: Optional[float] = None
    COUPONPERIOD: Optional[int] = None
    COUPONVALUE: Optional[float] = None
    DURATION: Optional[float] = None
    DURATIONWAPRICE: Optional[int] = None
    CURRENCYID: Optional[str] = None
    FACEUNIT: Optional[str] = None
    LISTLEVEL: Optional[int] = None
    RATING_AGENCY: Optional[str] = None
    RATING_LEVEL: Optional[str] = None
    RATINGS: Optional[List[Dict[str, Any]]] = None
    BONDTYPE: Optional[str] = None
    BONDTYPE43: Optional[str] = None
    COUPON_YIELD_TO_PRICE: Optional[float] = None
    COUPON_FREQUENCY: Optional[int] = None
    DURATION_YEARS: Optional[float] = None

    class Config:
        """Конфигурация Pydantic модели.

        Attributes:
            from_attributes: Разрешает создание из атрибутов объекта (ORM).
        """
        from_attributes = True


class BondDetailDTO(BaseModel):
    """DTO детальной информации об облигации для модального окна «Детали операции».

    Структура полностью соответствует интерфейсу BondDetail на фронтенде.
    Используется для передачи данных из БД (Bond, BondSecurity, BondMarketData)
    через API в модальное окно детальной информации об облигации.

    Attributes:
        securities: Словарь полей секции securities (идентификация, выпуск, купон,
            сроки). Ключи в UPPERCASE (MOEX API). Значения — примитивы или списки.
        marketdata: Словарь полей секции marketdata (цены, объёмы, активность) или
            None при отсутствии рыночных данных.
        marketdata_yields: Список словарей с расчётами доходности или None.
            Каждый элемент — Record с полями EFFECTIVEYIELD, DURATION и т.д.
        emitent_inn: ИНН эмитента из таблицы emitents (связь через bond.emitent_id).
            None или пустая строка при отсутствии данных об эмитенте.
    """

    securities: Dict[str, Any]
    marketdata: Optional[Dict[str, Any]] = None
    marketdata_yields: Optional[List[Dict[str, Any]]] = None
    emitent_inn: Optional[str] = None

    class Config:
        """Конфигурация Pydantic модели."""
        from_attributes = True
