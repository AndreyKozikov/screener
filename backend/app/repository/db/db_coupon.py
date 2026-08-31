"""Репозиторий для работы с базой данных купонов облигаций.

Этот модуль содержит класс DBCoupon для работы с таблицей coupons в SQLite базе данных.
Обеспечивает создание, обновление и запросы данных о купонах облигаций.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.utils.coupon_utils import COUPON_STORAGE_FIELDS
from config.paths import DB_PATH


class DBCoupon:
    """Репозиторий для работы с базой данных купонов облигаций.

    Класс обеспечивает работу с таблицей coupons в SQLite базе данных.
    Отвечает за создание, обновление и запросы данных о купонах облигаций.
    Единственный источник истины для купонов — таблица coupons; чтение/запись
    только через БД (без JSON-файлов).

    Основные методы:
        has_coupons_for_secid(): Проверка наличия купонов для облигации в БД.
        save_coupons_bulk(): Массовая вставка/обновление купонов (после API MOEX).
        fetch_coupons_raw(): SELECT с фильтрами по secids и датам.
        fetch_coupons_for_frontend(): Выборка полей для фронтенда по secids.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Инициализирует экземпляр репозитория для работы с купонами.

        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется путь по умолчанию: backend/db/bonds.db

        Attributes:
            db_path: Путь к файлу базы данных.
            logger: Логгер для записи событий и ошибок.
        """
        if db_path is None:
            db_path = str(DB_PATH)
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)

    def has_coupons_for_secid(self, secid: str) -> bool:
        """Проверяет, есть ли в БД хотя бы один купон для облигации с указанным secid.

        Используется для проверки актуальности данных перед загрузкой из API MOEX.

        Args:
            secid: Идентификатор облигации (SECID).

        Returns:
            True если в таблице coupons есть записи для данной облигации, иначе False.
        """
        if not secid or not str(secid).strip():
            return False
        if not self._table_exists("coupons"):
            return False
        sql = """
        SELECT 1 FROM coupons c
        INNER JOIN bonds b ON b.id = c.bond_id
        WHERE b.secid = ?
        LIMIT 1
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (secid.strip(),))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            self.logger.debug("has_coupons_for_secid(%s): %s", secid, e)
            return False

    def refresh(self, table_name: str, secid_to_id: Optional[Dict[str, int]] = None) -> None:
        """Создаёт таблицу coupons, если её нет. Данные не загружаются из файлов.

        Источник данных купонов — только API MOEX и save_coupons_bulk. Вызов
        нужен для миграций/скриптов, чтобы гарантировать наличие таблицы.

        Args:
            table_name: Имя таблицы (должно быть "coupons").
            secid_to_id: Не используется; оставлен для совместимости вызовов.
        """
        if table_name != "coupons":
            self.logger.warning("refresh: ожидается table_name='coupons', получено %s", table_name)
            return
        try:
            self._ensure_db_directory()
            with sqlite3.connect(self.db_path) as conn:
                if not self._table_exists(table_name):
                    self._create_coupons_table(conn)
                    self.logger.info("Таблица coupons создана: %s", self.db_path)
        except sqlite3.Error as e:
            self.logger.error("Ошибка при refresh(coupons): %s", e, exc_info=True)
            raise

    def save_coupons_bulk(self, records: List[Dict[str, Any]]) -> None:
        """Вставляет или заменяет купоны напрямую с уже известным bond_id.

        Не выполняет запросов к bonds — bond_id должен быть передан в каждой
        записи. Используется после загрузки облигаций одним запросом и получения
        купонов из API.

        Args:
            records: Список словарей с полями bond_id и полями купона
                (coupondate, recorddate, startdate, initialfacevalue, facevalue,
                faceunit, value, valueprc, value_rub). coupondate обязателен.

        Raises:
            sqlite3.Error: При ошибке работы с БД.
        """
        if not records:
            self.logger.warning("save_coupons_bulk: нет записей для вставки")
            return
        self._ensure_db_directory()
        with sqlite3.connect(self.db_path) as conn:
            if not self._table_exists("coupons"):
                self._create_coupons_table(conn)
            self._insert_or_replace_coupons(conn, records)
        self.logger.info(f"save_coupons_bulk: вставлено/обновлено {len(records)} записей")
    
    def _ensure_db_directory(self) -> None:
        """Создает директорию для базы данных, если она не существует.
        
        Проверяет наличие родительской директории для файла базы данных
        и создает её при необходимости. Используется перед созданием таблиц.
        """
        db_dir = self.db_path.parent
        db_dir.mkdir(parents=True, exist_ok=True)
        self.logger.debug(f"Директория для БД проверена/создана: {db_dir}")
    
    def _table_exists(self, table_name: str) -> bool:
        """Проверяет существование таблицы в базе данных через запрос к sqlite_master.
        
        Args:
            table_name: Имя таблицы для проверки.
        
        Returns:
            True если таблица существует, False в противном случае.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table_name,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Ошибка при проверке существования таблицы: {e}")
            return False
    
    def _create_coupons_table(self, conn: sqlite3.Connection) -> None:
        """Создает таблицу coupons с bond_id (FK на bonds.id).

        Схема управляется миграциями Alembic; метод используется при отсутствии
        таблицы (например, после чистой установки). PK: (bond_id, coupondate).

        Args:
            conn: Соединение с базой данных SQLite.

        Raises:
            sqlite3.Error: Если произошла ошибка при создании таблицы.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS coupons (
            bond_id INTEGER NOT NULL REFERENCES bonds(id) ON DELETE CASCADE,
            coupondate DATE,
            recorddate DATE,
            startdate DATE,
            initialfacevalue INTEGER,
            facevalue INTEGER,
            faceunit TEXT,
            value REAL,
            valueprc REAL,
            value_rub REAL,
            PRIMARY KEY (bond_id, coupondate)
        )
        """
        try:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            self.logger.info("Таблица coupons успешно создана")
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при создании таблицы coupons: {e}", exc_info=True)
            raise
    
    def _transform_coupon_data(
        self,
        raw_data: Dict[str, Any],
        secid_to_id: Optional[Dict[str, int]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Преобразует JSON/API данные в формат таблицы (bond_id + поля купона).

        При наличии secid_to_id подставляет bond_id по secid. Даты приводятся
        к формату YYYY-MM-DD.

        Args:
            raw_data: Словарь с полями secid (или bond_id) и coupondate и др.
            secid_to_id: Маппинг secid → bonds.id; при отсутствии ожидается bond_id в raw_data.

        Returns:
            Словарь с bond_id и полями купона для вставки или None при отсутствии ключей.
        """
        def parse_date(date_str: Optional[str]) -> Optional[str]:
            if not date_str:
                return None
            try:
                if isinstance(date_str, str):
                    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"]:
                        try:
                            return datetime.strptime(date_str, fmt).date().isoformat()
                        except ValueError:
                            continue
                    if len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-":
                        return date_str
                return None
            except Exception:
                return None

        bond_id = raw_data.get("bond_id")
        secid = raw_data.get("secid")
        if bond_id is None and secid_to_id and secid:
            bond_id = secid_to_id.get(secid)
        if bond_id is None:
            self.logger.warning(
                "Пропущена запись купона: нет bond_id (secid=%s). Данные: %s",
                secid or "?",
                raw_data,
            )
            return None

        coupondate_str = raw_data.get("coupondate")
        if not coupondate_str:
            self.logger.warning("Пропущена запись купона: отсутствует coupondate. Данные: %s", raw_data)
            return None

        return {
            "bond_id": int(bond_id),
            "coupondate": parse_date(coupondate_str),
            "recorddate": parse_date(raw_data.get("recorddate")),
            "startdate": parse_date(raw_data.get("startdate")),
            "initialfacevalue": raw_data.get("initialfacevalue") if raw_data.get("initialfacevalue") is not None else 0,
            "facevalue": raw_data.get("facevalue") if raw_data.get("facevalue") is not None else 0,
            "faceunit": raw_data.get("faceunit") if raw_data.get("faceunit") else None,
            "value": raw_data.get("value") if raw_data.get("value") is not None else 0.0,
            "valueprc": raw_data.get("valueprc") if raw_data.get("valueprc") is not None else 0.0,
            "value_rub": raw_data.get("value_rub") if raw_data.get("value_rub") is not None else 0.0,
        }
    
    def _insert_or_replace_coupons(self, conn: sqlite3.Connection, coupons: List[Dict[str, Any]]) -> None:
        """Вставляет или заменяет записи используя INSERT OR REPLACE INTO.
        
        Выполняет массовую вставку данных купонов в таблицу coupons используя
        INSERT OR REPLACE INTO. Все операции выполняются в рамках одной транзакции
        с явным commit или rollback при ошибках.
        
        Args:
            conn: Соединение с базой данных SQLite.
            coupons: Список словарей с данными купонов для вставки/обновления.
                Каждый словарь должен содержать все поля таблицы coupons.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
                При ошибке выполняется rollback транзакции.
        """
        if not coupons:
            self.logger.warning("Нет данных для вставки")
            return
        
        insert_sql = """
        INSERT OR REPLACE INTO coupons (
            bond_id, coupondate, recorddate, startdate, initialfacevalue,
            facevalue, faceunit, value, valueprc, value_rub
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            cursor = conn.cursor()
            inserted_count = 0
            for coupon in coupons:
                cursor.execute(insert_sql, (
                    coupon.get("bond_id"),
                    coupon.get("coupondate"),
                    coupon.get("recorddate"),
                    coupon.get("startdate"),
                    coupon.get("initialfacevalue"),
                    coupon.get("facevalue"),
                    coupon.get("faceunit"),
                    coupon.get("value"),
                    coupon.get("valueprc"),
                    coupon.get("value_rub"),
                ))
                inserted_count += 1
            
            # Фиксируем транзакцию
            conn.commit()
            self.logger.info(f"Успешно вставлено/обновлено {inserted_count} записей в таблицу coupons")
        except sqlite3.Error as e:
            # Выполняем rollback при ошибке
            conn.rollback()
            self.logger.error(f"Ошибка при вставке данных в таблицу coupons: {e}", exc_info=True)
            raise
    
    def fetch_coupons_raw(
        self, 
        secids: Optional[List[str]] = None, 
        from_date: Optional[str] = None, 
        till_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Выполняет SELECT по таблице coupons с динамической фильтрацией.
        
        Возвращает сырые строки в виде списка словарей (ключи — имена колонок).
        Применяет фильтры на уровне базы данных для повышения производительности.
        
        Логика работы фильтров по датам:
            - Если from_date не задан (None), метод отбирает все записи от начала
              истории до till_date включительно
            - Если till_date не задан (None), метод отбирает все записи начиная
              с from_date до конца истории
            - Если оба параметра заданы, метод отбирает записи в указанном диапазоне
              [from_date, till_date] включительно
            - Если оба параметра не заданы, метод возвращает все записи для указанного secid
        
        Args:
            secids: Список идентификаторов облигаций (secid) для выборки купонов.
                Если None или пустой список, фильтрация по secid не применяется.
            from_date: Начальная дата диапазона в формате YYYY-MM-DD (включительно).
                Если None, фильтр не применяется.
            till_date: Конечная дата диапазона в формате YYYY-MM-DD (включительно).
                Если None, фильтр не применяется.
        
        Returns:
            Список словарей с данными купонов. Каждый словарь содержит все поля таблицы coupons.
            Результаты отсортированы по secid и coupondate. Если таблица не существует,
            возвращает пустой список.
        
        Raises:
            ValueError: Если формат даты некорректен (не соответствует YYYY-MM-DD).
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
        """

        # Валидация и нормализация дат
        if from_date:
            try:
                # Проверяем формат даты и нормализуем
                datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Неверный формат from_date: {from_date}. Ожидается YYYY-MM-DD")
        
        if till_date:
            try:
                # Проверяем формат даты и нормализуем
                datetime.strptime(till_date, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Неверный формат till_date: {till_date}. Ожидается YYYY-MM-DD")
        
        # JOIN с bonds для фильтра по secid и возврата secid в результате
        sql = """
        SELECT
            c.bond_id, c.coupondate, c.recorddate, c.startdate, c.initialfacevalue,
            c.facevalue, c.faceunit, c.value, c.valueprc, c.value_rub,
            b.secid
        FROM coupons c
        INNER JOIN bonds b ON b.id = c.bond_id
        """
        conditions = []
        params: List[Any] = []

        if secids and len(secids) > 0:
            placeholders = ",".join("?" * len(secids))
            conditions.append(f"b.secid IN ({placeholders})")
            params.extend(secids)
        if from_date:
            conditions.append("c.coupondate >= ?")
            params.append(from_date)
        if till_date:
            conditions.append("c.coupondate <= ?")
            params.append(till_date)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY b.secid, c.coupondate"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                
                # Формируем информативное сообщение для логирования
                filter_info = []
                if secids and len(secids) > 0:
                    filter_info.append(f"secids={len(secids)}")
                if from_date:
                    filter_info.append(f"from={from_date}")
                if till_date:
                    filter_info.append(f"till={till_date}")
                
                filter_str = ", ".join(filter_info) if filter_info else "без фильтров"
                self.logger.debug(f"Выбрано {len(result)} записей купонов ({filter_str})")
                return result
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при fetch_coupons_raw: {e}", exc_info=True)
            raise

    def fetch_coupons_for_frontend(
        self,
        secids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Выбирает из БД только поля купона, ожидаемые фронтендом.

        Выполняет SELECT только нужных колонок. Возвращает сырые данные
        без преобразований. Секid включён для группировки при batch-запросах.

        Args:
            secids: Список SECID для выборки. Если None или пусто — без фильтра.

        Returns:
            Список словарей: secid + coupondate, recorddate, startdate,
            initialfacevalue, facevalue, faceunit, value, valueprc, value_rub.
            Без иных полей. Сортировка: secid, coupondate.
        """
        if not self._table_exists("coupons"):
            self.logger.warning("Таблица coupons не существует, fetch_coupons_for_frontend возвращает []")
            return []

        cols = ", ".join(f"c.{f}" for f in ("bond_id",) + COUPON_STORAGE_FIELDS) + ", b.secid"
        sql = f"SELECT {cols} FROM coupons c INNER JOIN bonds b ON b.id = c.bond_id"
        conditions = []
        params = []

        if secids and len(secids) > 0:
            placeholders = ",".join("?" * len(secids))
            conditions.append(f"b.secid IN ({placeholders})")
            params.extend(secids)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY b.secid, c.coupondate"

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при fetch_coupons_for_frontend: {e}", exc_info=True)
            raise

