from datetime import date, datetime
from typing import List

def compute_event_years(first_tradedate_str: str) -> List[int]:
    """Определяет временной диапазон для поиска документов (от года даты - 1 до текущего)."""
    try:
        trade_date: date = datetime.strptime(first_tradedate_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        print("Ошибка парсинга даты, берем текущий год", first_tradedate_str)
        current_year: int = date.today().year
        return [current_year - 1, current_year]

    # Начинаем поиск на 1 год раньше года в дате, чтобы захватить регистрацию и размещение
    trade_year: int = trade_date.year
    start_year: int = trade_year - 1
    print("Начальный год", start_year)

    current_year = date.today().year
    print("Текущий год", current_year)
    # Возвращаем все годы от (год в дате - 1) до текущего включительно
    return list(range(start_year, current_year + 1))