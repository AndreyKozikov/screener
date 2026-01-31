"""Утилиты для обработки данных купонов облигаций.

Модуль содержит функции для очистки строк UTF-8, извлечения полей купона
для таблицы БД и преобразования строк из БД в формат фронтенда.
"""

from typing import Any, Dict

# Поля купона для таблицы coupons в БД (совпадают с полями фронтенда)
COUPON_STORAGE_FIELDS = (
    "coupondate", "recorddate", "startdate",
    "initialfacevalue", "facevalue", "faceunit",
    "value", "valueprc", "value_rub",
)


def clean_string_value(value: Any) -> Any:
    """Очищает строковые значения для обеспечения валидной UTF-8 кодировки.

    Рекурсивно обрабатывает структуры данных (словари, списки) и очищает все
    строковые значения, удаляя суррогатные пары, которые вызывают ошибки
    кодировки UTF-8.

    Args:
        value: Значение для очистки. Может быть строкой, словарем, списком
            или другим типом данных. Для словарей и списков выполняется
            рекурсивная обработка всех элементов.

    Returns:
        Очищенное значение с валидными UTF-8 строками. Для словарей и списков
        возвращается новая структура с очищенными значениями. Для других типов
        (int, float, bool, None) возвращается исходное значение без изменений.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value.encode("utf-8").decode("utf-8")
            return value
        except (UnicodeEncodeError, UnicodeDecodeError):
            return (
                value.encode("utf-8", errors="replace")
                .decode("utf-8", errors="replace")
            )
    if isinstance(value, dict):
        return {k: clean_string_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_string_value(item) for item in value]
    return value


def extract_coupon_for_storage(coupon: Dict[str, Any]) -> Dict[str, Any]:
    """Извлекает из ответа MOEX только поля, нужные для таблицы coupons в БД.

    Args:
        coupon: Словарь с данными купона из API MOEX.

    Returns:
        Словарь только с полями: coupondate, recorddate, startdate,
        initialfacevalue, facevalue, faceunit, value, valueprc, value_rub.
    """
    return {k: coupon.get(k) for k in COUPON_STORAGE_FIELDS}


def to_frontend_coupon(row: Dict[str, Any]) -> Dict[str, Any]:
    """Приводит строку из БД к формату, ожидаемому фронтендом.

    Удаляет поле secid, так как оно используется только для группировки
    и не входит в интерфейс Coupon на фронтенде.

    Args:
        row: Словарь с данными купона из БД (включая secid).

    Returns:
        Словарь с полями купона без secid.
    """
    return {k: v for k, v in row.items() if k != "secid"}
