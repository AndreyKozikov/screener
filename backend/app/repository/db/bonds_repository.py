"""Репозиторий для запросов и фильтрации облигаций из базы данных.

Этот модуль содержит класс BondsRepository для выполнения запросов и фильтрации
облигаций из таблицы bonds в SQLite базе данных.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from app.models.filters import BondFilters
from app.repository.db.constants import RATINGS_ORDER
from app.utils.logger import get_data_update_logger


class BondsRepository:
    """Репозиторий для запросов и фильтрации облигаций из базы данных.
    
    Класс обеспечивает выполнение запросов и фильтрацию облигаций из таблицы bonds.
    Отвечает за выборку данных по критериям для фронтэнда скринера.
    
    Основные методы:
        select(): Универсальный метод выборки облигаций с применением фильтров на уровне БД.
        fetch_bonds_raw(): Выполнение SELECT запросов с возвратом сырых данных.
        count(): Подсчет количества облигаций с применением фильтров.
        count_bonds(): Подсчет количества облигаций для API ответов.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """Инициализирует экземпляр репозитория для работы с облигациями.
        
        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется путь по умолчанию: backend/db/bonds.db
        
        Attributes:
            db_path: Путь к файлу базы данных.
            logger: Логгер для записи событий и ошибок.
        """
        if db_path is None:
            # Определяем путь относительно текущего файла
            backend_dir = Path(__file__).parent.parent.parent.parent
            db_path = backend_dir / "db" / "bonds.db"
        
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
    
    def select(
        self,
        filters: Optional[BondFilters] = None,
        *,
        # Прямые параметры для обратной совместимости
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        rating_min: Optional[str] = None,
        rating_max: Optional[str] = None,
        exclude_spob: bool = False,
    ) -> List[Dict[str, Any]]:
        """Универсальный метод для выборки облигаций с динамическим формированием SQL-запроса.
        
        Применяет все фильтры на уровне базы данных для повышения производительности.
        Особое внимание уделено фильтрации по рейтингу, которая реализована через SQL-условия
        с учетом шкалы RATINGS_ORDER и возможных префиксов/суффиксов в значениях рейтингов.
        
        Args:
            filters: Объект BondFilters с параметрами фильтрации. Имеет приоритет над
                прямыми параметрами. Если передан, значения из него используются вместо
                соответствующих прямых параметров.
            coupon_percent_min: Минимальный процент купона для фильтрации.
            coupon_percent_max: Максимальный процент купона для фильтрации.
            yield_to_maturity_min: Минимальная доходность к погашению для фильтрации.
            yield_to_maturity_max: Максимальная доходность к погашению для фильтрации.
            coupon_yield_to_price_min: Минимальная доходность купона к цене для фильтрации.
            coupon_yield_to_price_max: Максимальная доходность купона к цене для фильтрации.
            maturity_date_from: Начальная дата погашения в формате YYYY-MM-DD (включительно).
            maturity_date_to: Конечная дата погашения в формате YYYY-MM-DD (включительно).
            listlevel: Список уровней листинга для фильтрации (например, [1, 2, 3]).
            currency: Список валют для фильтрации (например, ["RUB", "USD", "EUR"]).
            bond_type_ids: Список ID типов облигаций для фильтрации.
            bond_kind_ids: Список ID видов облигаций для фильтрации.
            rating_min: Минимальный рейтинг из шкалы RATINGS_ORDER (например, "AA", "BBB+").
            rating_max: Максимальный рейтинг из шкалы RATINGS_ORDER (например, "AAA", "AA+").
            exclude_spob: Если True, исключает облигации с режимом торгов SPOB.
        
        Returns:
            Список словарей с данными облигаций. Каждый словарь содержит все поля таблицы bonds.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
        """
        # Используем фильтры из объекта, если передан, иначе используем прямые параметры
        if filters is not None:
            coupon_percent_min = filters.coupon_min
            coupon_percent_max = filters.coupon_max
            yield_to_maturity_min = filters.yield_min
            yield_to_maturity_max = filters.yield_max
            coupon_yield_to_price_min = filters.coupon_yield_min
            coupon_yield_to_price_max = filters.coupon_yield_max
            maturity_date_from = filters.matdate_from.isoformat() if filters.matdate_from else None
            maturity_date_to = filters.matdate_to.isoformat() if filters.matdate_to else None
            listlevel = filters.listlevel
            currency = filters.faceunit
            rating_min = filters.rating_min
            rating_max = filters.rating_max
        
        # Формируем динамические WHERE-условия
        where_parts: List[str] = []
        params: List[Any] = []
        
        # Фильтр по проценту купона (диапазон)
        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        
        # Фильтр по доходности к погашению (диапазон)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        
        # Фильтр по доходности купона к цене (диапазон)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        
        # Фильтр по дате погашения (диапазон)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        
        # Фильтр по уровню листинга (IN)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        
        # Фильтр по валюте (IN)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        
        # Фильтр по типу облигации (IN)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        
        # Фильтр по виду облигации (IN)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        
        # Фильтр по рейтингу (специальная логика с учетом шкалы RATINGS)
        # Использует оператор IN с динамическим списком рейтингов из диапазона
        if rating_min is not None or rating_max is not None:
            rating_result = self._build_rating_filter_sql(rating_min, rating_max)
            if rating_result:
                # rating_result - это кортеж (SQL-условие, список параметров)
                rating_sql, rating_params = rating_result
                where_parts.append(rating_sql)
                params.extend(rating_params)
        
        # Фильтр по режиму торгов SPOB
        if exclude_spob:
            where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")
        
        # Формируем финальный SQL-запрос
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        
        # Список колонок (включая boardid)
        base_cols = "secid, boardid, isin, name, rating, current_price, coupon_yield_to_price, yield_to_maturity, face_value, currency, coupon_value, coupon_percent, coupon_frequency, accrued_interest, duration_years, has_put_option, has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date"
        
        sql = f"SELECT {base_cols} FROM bonds WHERE {where_sql}"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                self.logger.debug(f"Выбрано {len(result)} записей из таблицы bonds с применением фильтров")
                return result
        except Exception as e:
            self.logger.error(f"Ошибка при select: {e}", exc_info=True)
            raise
    
    def _build_rating_filter_sql(
        self,
        rating_min: Optional[str],
        rating_max: Optional[str]
    ) -> Optional[Tuple[str, List[str]]]:
        """Формирует SQL-условие для фильтрации по рейтингу с использованием оператора IN.
        
        Использует константу RATINGS_ORDER для определения диапазона рейтингов.
        Правильно обрабатывает случай, когда rating_min может быть больше rating_max
        (пользователь может выбрать диапазон в любом порядке). Формирует SQL-условие
        с использованием оператора IN для фильтрации по диапазону рейтингов.
        
        Args:
            rating_min: Один из граничных рейтингов из шкалы RATINGS_ORDER.
                Может быть как минимальным, так и максимальным в зависимости от порядка выбора.
            rating_max: Другой граничный рейтинг из шкалы RATINGS_ORDER.
                Может быть как минимальным, так и максимальным в зависимости от порядка выбора.
        
        Returns:
            Кортеж из двух элементов:
            - SQL-строка с условием для WHERE (например, "(rating IS NOT NULL AND ... IN (...))")
            - Список параметров с рейтингами из диапазона для оператора IN (в верхнем регистре)
            Или None, если фильтр не применим (оба параметра None или рейтинги не найдены в шкале).
        """
        # Если оба фильтра None, фильтр не применяется
        if rating_min is None and rating_max is None:
            return None
        
        # Определяем индексы границ диапазона в RATINGS_ORDER
        try:
            idx_start = RATINGS_ORDER.index(rating_min.upper()) if rating_min is not None else 0
            idx_end = RATINGS_ORDER.index(rating_max.upper()) if rating_max is not None else len(RATINGS_ORDER) - 1
        except ValueError:
            # Если рейтинг не найден в шкале, не применяем фильтр
            self.logger.warning(f"Рейтинг не найден в шкале RATINGS_ORDER: min={rating_min}, max={rating_max}")
            return None
        
        # Срезаем список (всегда берем от меньшего индекса к большему)
        # Это позволяет корректно обработать случай, когда пользователь выбрал диапазон
        # в обратном порядке (например, от AA- до AA вместо от AA до AA-)
        low = min(idx_start, idx_end)
        high = max(idx_start, idx_end)
        
        # Формируем список рейтингов в диапазоне [low, high] включительно
        ratings_in_range = RATINGS_ORDER[low:high + 1]
        
        if not ratings_in_range:
            return None
        
        # В таблице рейтинги хранятся без префиксов и суффиксов (просто 'AAA', 'AA+', 'AA', и т.д.)
        # Поэтому используем только базовые значения рейтингов
        # Формируем SQL-условие с использованием IN
        # Используем UPPER для case-insensitive сравнения
        # Исключаем NULL и пустые строки
        placeholders = ",".join("?" * len(ratings_in_range))
        sql_condition = f"(rating IS NOT NULL AND TRIM(rating) != '' AND UPPER(TRIM(rating)) IN ({placeholders}))"
        
        # Возвращаем условие и список рейтингов (в верхнем регистре для сравнения)
        rating_params = [rating.upper() for rating in ratings_in_range]
        return (sql_condition, rating_params)

    def fetch_bonds_raw(
        self,
        *,
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        exclude_spob: bool = False,
    ) -> List[Dict[str, Any]]:
        """Выполняет SELECT по таблице bonds с учётом переданных фильтров.
        
        Возвращает сырые строки в виде списка словарей (ключи — имена колонок).
        Применяет фильтры на уровне базы данных для повышения производительности.
        
        Args:
            coupon_percent_min: Минимальный процент купона.
            coupon_percent_max: Максимальный процент купона.
            yield_to_maturity_min: Минимальная доходность к погашению.
            yield_to_maturity_max: Максимальная доходность к погашению.
            coupon_yield_to_price_min: Минимальная доходность купона к цене.
            coupon_yield_to_price_max: Максимальная доходность купона к цене.
            maturity_date_from: Дата погашения от (YYYY-MM-DD).
            maturity_date_to: Дата погашения до (YYYY-MM-DD).
            listlevel: Список уровней листинга для фильтрации.
            currency: Список валют для фильтрации.
            bond_type_ids: Список ID типов облигаций для фильтрации.
            bond_kind_ids: Список ID видов облигаций для фильтрации.
            exclude_spob: Исключить облигации с режимом торгов SPOB.
        
        Returns:
            Список словарей с данными облигаций. Каждый словарь содержит все поля
            таблицы bonds.
        
        Note:
            Не выполняет фильтрацию по рейтингу и эмитенту — это зона ответственности
            сервисного слоя, так как требует дополнительных данных и бизнес-логики.
        """
        where_parts: List[str] = []
        params: List[Any] = []

        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        if exclude_spob:
            where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        base_cols = "secid, boardid, isin, name, rating, current_price, coupon_yield_to_price, yield_to_maturity, face_value, currency, coupon_value, coupon_percent, coupon_frequency, accrued_interest, duration_years, has_put_option, has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date"
        sql = f"SELECT {base_cols} FROM bonds WHERE {where_sql}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Ошибка при fetch_bonds_raw: {e}", exc_info=True)
            raise

    def count(
        self,
        filters: Optional[BondFilters] = None,
        *,
        # Прямые параметры для обратной совместимости
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        rating_min: Optional[str] = None,
        rating_max: Optional[str] = None,
        exclude_spob: bool = False,
    ) -> int:
        """Универсальный метод для подсчета облигаций с применением всех фильтров на уровне БД.
        
        Использует ту же логику фильтрации, что и метод select, но возвращает только
        количество записей вместо самих данных. Применяет все фильтры на уровне базы данных
        для повышения производительности.
        
        Args:
            filters: Объект BondFilters с параметрами фильтрации. Имеет приоритет над
                прямыми параметрами. Если передан, значения из него используются вместо
                соответствующих прямых параметров.
            coupon_percent_min: Минимальный процент купона для фильтрации.
            coupon_percent_max: Максимальный процент купона для фильтрации.
            yield_to_maturity_min: Минимальная доходность к погашению для фильтрации.
            yield_to_maturity_max: Максимальная доходность к погашению для фильтрации.
            coupon_yield_to_price_min: Минимальная доходность купона к цене для фильтрации.
            coupon_yield_to_price_max: Максимальная доходность купона к цене для фильтрации.
            maturity_date_from: Начальная дата погашения в формате YYYY-MM-DD (включительно).
            maturity_date_to: Конечная дата погашения в формате YYYY-MM-DD (включительно).
            listlevel: Список уровней листинга для фильтрации.
            currency: Список валют для фильтрации.
            bond_type_ids: Список ID типов облигаций для фильтрации.
            bond_kind_ids: Список ID видов облигаций для фильтрации.
            rating_min: Минимальный рейтинг из шкалы RATINGS_ORDER.
            rating_max: Максимальный рейтинг из шкалы RATINGS_ORDER.
            exclude_spob: Если True, исключает облигации с режимом торгов SPOB.
        
        Returns:
            Количество облигаций, соответствующих указанным фильтрам.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
        """
        # Используем фильтры из объекта, если передан, иначе используем прямые параметры
        if filters is not None:
            coupon_percent_min = filters.coupon_min
            coupon_percent_max = filters.coupon_max
            yield_to_maturity_min = filters.yield_min
            yield_to_maturity_max = filters.yield_max
            coupon_yield_to_price_min = filters.coupon_yield_min
            coupon_yield_to_price_max = filters.coupon_yield_max
            maturity_date_from = filters.matdate_from.isoformat() if filters.matdate_from else None
            maturity_date_to = filters.matdate_to.isoformat() if filters.matdate_to else None
            listlevel = filters.listlevel
            currency = filters.faceunit
            rating_min = filters.rating_min
            rating_max = filters.rating_max
        
        # Формируем динамические WHERE-условия (та же логика, что и в select)
        where_parts: List[str] = []
        params: List[Any] = []
        
        # Применяем те же фильтры, что и в методе select
        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        
        # Фильтр по рейтингу (используем ту же логику, что и в select)
        if rating_min is not None or rating_max is not None:
            rating_result = self._build_rating_filter_sql(rating_min, rating_max)
            if rating_result:
                # rating_result - это кортеж (SQL-условие, список параметров)
                rating_sql, rating_params = rating_result
                where_parts.append(rating_sql)
                params.extend(rating_params)
        
        if exclude_spob:
            where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")
        
        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        sql = f"SELECT COUNT(*) FROM bonds WHERE {where_sql}"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return int(cursor.fetchone()[0])
        except Exception as e:
            self.logger.error(f"Ошибка при count: {e}", exc_info=True)
            raise

    def count_bonds(
        self,
        *,
        coupon_percent_min: Optional[float] = None,
        coupon_percent_max: Optional[float] = None,
        yield_to_maturity_min: Optional[float] = None,
        yield_to_maturity_max: Optional[float] = None,
        coupon_yield_to_price_min: Optional[float] = None,
        coupon_yield_to_price_max: Optional[float] = None,
        maturity_date_from: Optional[str] = None,
        maturity_date_to: Optional[str] = None,
        listlevel: Optional[List[int]] = None,
        currency: Optional[List[str]] = None,
        bond_type_ids: Optional[List[int]] = None,
        bond_kind_ids: Optional[List[int]] = None,
        exclude_spob: bool = False,
    ) -> int:
        """Возвращает количество записей в bonds с учётом фильтров.
        
        Использует те же фильтры, что и метод fetch_bonds_raw, но возвращает
        только количество записей. Используется для формирования полей total/filtered
        в ответе API.
        
        Args:
            coupon_percent_min: Минимальный процент купона.
            coupon_percent_max: Максимальный процент купона.
            yield_to_maturity_min: Минимальная доходность к погашению.
            yield_to_maturity_max: Максимальная доходность к погашению.
            coupon_yield_to_price_min: Минимальная доходность купона к цене.
            coupon_yield_to_price_max: Максимальная доходность купона к цене.
            maturity_date_from: Дата погашения от (YYYY-MM-DD).
            maturity_date_to: Дата погашения до (YYYY-MM-DD).
            listlevel: Список уровней листинга для фильтрации.
            currency: Список валют для фильтрации.
            bond_type_ids: Список ID типов облигаций для фильтрации.
            bond_kind_ids: Список ID видов облигаций для фильтрации.
            exclude_spob: Исключить облигации с режимом торгов SPOB.
        
        Returns:
            Количество записей в таблице bonds, соответствующих указанным фильтрам.
        """
        where_parts: List[str] = []
        params: List[Any] = []

        if coupon_percent_min is not None:
            where_parts.append("coupon_percent >= ?")
            params.append(coupon_percent_min)
        if coupon_percent_max is not None:
            where_parts.append("coupon_percent <= ?")
            params.append(coupon_percent_max)
        if yield_to_maturity_min is not None:
            where_parts.append("yield_to_maturity >= ?")
            params.append(yield_to_maturity_min)
        if yield_to_maturity_max is not None:
            where_parts.append("yield_to_maturity <= ?")
            params.append(yield_to_maturity_max)
        if coupon_yield_to_price_min is not None:
            where_parts.append("coupon_yield_to_price >= ?")
            params.append(coupon_yield_to_price_min)
        if coupon_yield_to_price_max is not None:
            where_parts.append("coupon_yield_to_price <= ?")
            params.append(coupon_yield_to_price_max)
        if maturity_date_from is not None:
            where_parts.append("maturity_date >= ?")
            params.append(maturity_date_from)
        if maturity_date_to is not None:
            where_parts.append("maturity_date <= ?")
            params.append(maturity_date_to)
        if listlevel is not None and len(listlevel) > 0:
            placeholders = ",".join("?" * len(listlevel))
            where_parts.append(f"listing_level IN ({placeholders})")
            params.extend(listlevel)
        if currency is not None and len(currency) > 0:
            placeholders = ",".join("?" * len(currency))
            where_parts.append(f"currency IN ({placeholders})")
            params.extend(currency)
        if bond_type_ids is not None and len(bond_type_ids) > 0:
            placeholders = ",".join("?" * len(bond_type_ids))
            where_parts.append(f"bond_type IN ({placeholders})")
            params.extend(bond_type_ids)
        if bond_kind_ids is not None and len(bond_kind_ids) > 0:
            placeholders = ",".join("?" * len(bond_kind_ids))
            where_parts.append(f"bond_kind IN ({placeholders})")
            params.extend(bond_kind_ids)
        if exclude_spob:
            where_parts.append("(boardid IS NULL OR UPPER(TRIM(boardid)) != 'SPOB')")

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"
        sql = f"SELECT COUNT(*) FROM bonds WHERE {where_sql}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return int(cursor.fetchone()[0])
        except Exception as e:
            self.logger.error(f"Ошибка при count_bonds: {e}", exc_info=True)
            raise

    def refresh(self, bonds: List[Dict[str, Any]]) -> bool:
        """Создаёт или обновляет таблицу bonds из готовых данных.

        Принимает список уже преобразованных словарей для вставки в таблицу bonds.
        Создаёт таблицу при отсутствии и выполняет INSERT OR REPLACE.

        Args:
            bonds: Список словарей с данными облигаций (ключи — имена колонок таблицы bonds).

        Returns:
            True если операция выполнена успешно, False в случае ошибки.
        """
        data_log = get_data_update_logger()
        try:
            self._ensure_db_directory()
            if not self._table_exists("bonds"):
                data_log.info("[API /bonds/refresh] Таблица bonds не существует, создаём структуру таблицы")
                self.logger.info("Таблица bonds не существует, создаём её")
                self._create_bonds_table()
            else:
                data_log.info("[API /bonds/refresh] Таблица bonds существует, обновляем данные (INSERT OR REPLACE)")
                self.logger.info("Таблица bonds существует, обновляем данные")
            self._insert_or_replace_bonds(bonds)
            data_log.info("[API /bonds/refresh] В таблицу bonds записано записей: %s (база: %s)", len(bonds), self.db_path)
            self.logger.info("Таблица bonds успешно создана/обновлена в базе данных: %s", self.db_path)
            return True
        except Exception as e:
            data_log.error("[API /bonds/refresh] Ошибка при записи в таблицу bonds: %s", e, exc_info=True)
            self.logger.error("Ошибка при создании/обновлении таблицы bonds: %s", e, exc_info=True)
            return False

    def _ensure_db_directory(self) -> None:
        """Создаёт директорию для базы данных, если она не существует."""
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug("Директория для БД проверена/создана: %s", db_dir)

    def _table_exists(self, table_name: str) -> bool:
        """Проверяет существование таблицы в базе данных.

        Args:
            table_name: Имя таблицы для проверки.

        Returns:
            True если таблица существует, False в противном случае.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error("Ошибка при проверке существования таблицы: %s", e)
            return False

    def _create_bonds_table(self) -> None:
        """Создаёт таблицу bonds с заданной структурой.

        Определяет схему таблицы bonds со всеми необходимыми колонками
        для хранения данных об облигациях. Выполняет CREATE TABLE IF NOT EXISTS.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bonds (
            secid TEXT PRIMARY KEY,
            boardid TEXT,
            isin TEXT,
            name TEXT,
            rating TEXT,
            current_price REAL,
            coupon_yield_to_price REAL,
            yield_to_maturity REAL,
            face_value REAL,
            currency TEXT,
            coupon_value REAL,
            coupon_percent REAL,
            coupon_frequency REAL,
            accrued_interest REAL,
            duration_years REAL,
            has_put_option INTEGER,
            has_call_option INTEGER,
            maturity_date TEXT,
            listing_level INTEGER,
            bond_type INTEGER,
            bond_kind INTEGER,
            offer_date TEXT
        )
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
        self.logger.debug("SQL запрос CREATE TABLE для bonds выполнен успешно")

    def _insert_or_replace_bonds(self, bonds: List[Dict[str, Any]]) -> None:
        """Вставляет или заменяет записи в таблице bonds.

        Выполняет массовую вставку данных облигаций в таблицу bonds используя
        INSERT OR REPLACE INTO. Все операции выполняются в рамках одной транзакции.

        Args:
            bonds: Список словарей с данными облигаций для вставки/обновления.
                Каждый словарь должен содержать все поля таблицы bonds.

        Raises:
            Exception: При ошибках вставки данных.
        """
        if not bonds:
            self.logger.warning("Нет данных для вставки")
            return
        insert_sql = """
        INSERT OR REPLACE INTO bonds (
            secid, boardid, isin, name, rating, current_price, coupon_yield_to_price,
            yield_to_maturity, face_value, currency, coupon_value, coupon_percent,
            coupon_frequency, accrued_interest, duration_years, has_put_option,
            has_call_option, maturity_date, listing_level, bond_type, bond_kind, offer_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for bond in bonds:
                    cursor.execute(
                        insert_sql,
                        (
                            bond.get("secid"),
                            bond.get("boardid"),
                            bond.get("isin"),
                            bond.get("name"),
                            bond.get("rating"),
                            bond.get("current_price"),
                            bond.get("coupon_yield_to_price"),
                            bond.get("yield_to_maturity"),
                            bond.get("face_value"),
                            bond.get("currency"),
                            bond.get("coupon_value"),
                            bond.get("coupon_percent"),
                            bond.get("coupon_frequency"),
                            bond.get("accrued_interest"),
                            bond.get("duration_years"),
                            bond.get("has_put_option"),
                            bond.get("has_call_option"),
                            bond.get("maturity_date"),
                            bond.get("listing_level"),
                            bond.get("bond_type"),
                            bond.get("bond_kind"),
                            bond.get("offer_date"),
                        ),
                    )
                conn.commit()
                data_log = get_data_update_logger()
                data_log.info("[API /bonds/refresh] INSERT OR REPLACE в bonds завершён: %s записей", len(bonds))
                self.logger.info("Успешно вставлено/обновлено %s записей в таблицу bonds", len(bonds))
        except Exception as e:
            get_data_update_logger().error("[API /bonds/refresh] Ошибка INSERT в таблицу bonds: %s", e, exc_info=True)
            self.logger.error("Ошибка при вставке данных в таблицу bonds: %s", e, exc_info=True)
            raise
