"""Репозиторий для работы с базой данных купонов облигаций.

Этот модуль содержит класс DBCoupon для работы с таблицей coupons в SQLite базе данных.
Обеспечивает создание, обновление и запросы данных о купонах облигаций.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import orjson


class DBCoupon:
    """Репозиторий для работы с базой данных купонов облигаций.
    
    Класс обеспечивает работу с таблицей coupons в SQLite базе данных.
    Отвечает за создание, обновление и запросы данных о купонах облигаций.
    
    Основные методы:
        refresh(): Создание или обновление таблицы coupons из JSON файлов (миграции).
        fetch_coupons_raw(): Выполнение SELECT запросов с возвратом сырых данных о купонах.
    
    Note:
        Обеспечивает полную синхронизацию данных купонов облигаций между JSON-источниками
        и SQLite базой данных с гарантией целостности и актуальности информации.
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
            # Определяем путь относительно текущего файла
            backend_dir = Path(__file__).parent.parent.parent
            db_path = str(backend_dir / "db" / "bonds.db")
        
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
    
    def refresh(self, table_name: str) -> None:
        """Создает или обновляет таблицу coupons в базе данных из JSON файлов.
        
        Выполняет полную синхронизацию данных купонов облигаций между JSON-источником
        (coupons_data.json) и SQLite базой данных. Загружает данные, преобразует их
        и сохраняет в БД в рамках одной транзакции.
        
        Последовательность выполнения:
            1. Установить соединение с базой данных
            2. Проверить существование таблицы coupons
            3. Если таблица не существует — создать её
            4. Загрузить данные из coupons_data.json
            5. Преобразовать данные для каждой записи
            6. Выполнить INSERT OR REPLACE INTO для всех записей в транзакции
            7. Зафиксировать транзакцию
            8. При ошибке выполнить rollback и пробросить исключение
        
        Args:
            table_name: Имя таблицы для работы в БД. Должно быть "coupons".
        
        Raises:
            FileNotFoundError: Если JSON файл coupons_data.json не найден.
            orjson.JSONDecodeError: Если JSON файл некорректен или поврежден.
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
        """
        try:
            # Создаём директорию для БД, если она не существует
            self._ensure_db_directory()
            
            # Устанавливаем соединение с базой данных
            with sqlite3.connect(self.db_path) as conn:
                # Проверяем существование таблицы
                if not self._table_exists(table_name):
                    self.logger.info(f"Таблица {table_name} не существует, создаём её")
                    self._create_coupons_table(conn)
                else:
                    self.logger.info(f"Таблица {table_name} существует, обновляем данные")
                
                # Загружаем данные из JSON
                coupons_data = self._load_json_data()
                if not coupons_data:
                    self.logger.warning("JSON файл пуст или не содержит данных о купонах")
                    return
                
                self.logger.info(f"Загружено {len(coupons_data)} записей купонов из JSON-файла")
                
                # Преобразуем данные
                transformed_coupons = []
                for raw_coupon in coupons_data:
                    try:
                        transformed = self._transform_coupon_data(raw_coupon)
                        if transformed:
                            transformed_coupons.append(transformed)
                    except Exception as e:
                        self.logger.warning(
                            f"Ошибка при преобразовании данных купона "
                            f"(secid={raw_coupon.get('secid', 'unknown')}, "
                            f"coupondate={raw_coupon.get('coupondate', 'unknown')}): {e}"
                        )
                        continue
                
                self.logger.info(f"Преобразовано {len(transformed_coupons)} записей купонов")
                
                # Вставляем или заменяем записи в транзакции
                self._insert_or_replace_coupons(conn, transformed_coupons)
                
                self.logger.info(
                    f"Таблица {table_name} успешно создана/обновлена в базе данных: {self.db_path}"
                )
        except (FileNotFoundError, orjson.JSONDecodeError) as e:
            self.logger.error(f"Ошибка при загрузке данных из JSON: {str(e)}", exc_info=True)
            raise
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при работе с базой данных: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при синхронизации купонов: {str(e)}", exc_info=True)
            raise
    
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
        """Создает таблицу coupons с указанной структурой.
        
        Определяет схему таблицы coupons со всеми необходимыми колонками
        для хранения данных о купонах облигаций. Выполняет CREATE TABLE IF NOT EXISTS.
        
        Args:
            conn: Соединение с базой данных SQLite.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при создании таблицы.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS coupons (
            secid TEXT NOT NULL,
            coupondate DATE,
            recorddate DATE,
            startdate DATE,
            initialfacevalue INTEGER,
            facevalue INTEGER,
            faceunit TEXT,
            value REAL,
            valueprc REAL,
            value_rub REAL,
            PRIMARY KEY (secid, coupondate)
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
    
    def _load_json_data(self) -> List[Dict[str, Any]]:
        """Загружает данные из coupons_data.json.
        
        Извлекает данные о купонах из структуры {"bonds": {"SECID": {"coupons": [...]}}}
        и преобразует их в плоский список словарей, добавляя secid к каждому купону.
        
        Returns:
            Список словарей с данными купонов. Каждый словарь содержит secid и данные купона.
        
        Raises:
            FileNotFoundError: Если файл coupons_data.json не найден.
            orjson.JSONDecodeError: Если JSON файл некорректен или поврежден.
        """
        # Определяем путь к файлу относительно текущего файла
        backend_dir = Path(__file__).parent.parent.parent
        data_dir = backend_dir / "app" / "data"
        coupons_path = data_dir / "coupons_data.json"
        
        if not coupons_path.exists():
            error_msg = f"Файл coupons_data.json не найден: {coupons_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            with open(coupons_path, 'rb') as f:
                data = orjson.loads(f.read())
            
            # Извлекаем данные о купонах из структуры {"bonds": {"SECID": {"coupons": [...]}}}
            bonds_data = data.get("bonds", {})
            coupons_list = []
            
            for secid, bond_data in bonds_data.items():
                if not isinstance(bond_data, dict):
                    continue
                
                coupons = bond_data.get("coupons", [])
                if not isinstance(coupons, list):
                    continue
                
                # Добавляем secid к каждому купону
                for coupon in coupons:
                    if isinstance(coupon, dict):
                        coupon_with_secid = coupon.copy()
                        coupon_with_secid["secid"] = secid
                        coupons_list.append(coupon_with_secid)
            
            return coupons_list
        except orjson.JSONDecodeError as e:
            error_msg = f"Ошибка при декодировании JSON файла {coupons_path}: {e}"
            self.logger.error(error_msg)
            raise
        except Exception as e:
            error_msg = f"Ошибка при загрузке данных из {coupons_path}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise
    
    def _transform_coupon_data(self, raw_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Преобразует JSON данные в формат таблицы с обработкой отсутствующих полей.
        
        Выполняет преобразование сырых данных купона из JSON формата в формат,
        пригодный для вставки в таблицу coupons. Обрабатывает отсутствующие поля
        и преобразует даты в формат YYYY-MM-DD.
        
        При отсутствии полей в JSON:
            - Для текстовых полей используется None (NULL)
            - Для числовых полей используется 0
            - Для полей дат (coupondate, recorddate, startdate) используется None
              или преобразование в формат DATE (YYYY-MM-DD)
        
        Args:
            raw_data: Словарь с сырыми данными купона из JSON. Должен содержать
                обязательные поля "secid" и "coupondate".
        
        Returns:
            Словарь с преобразованными данными для вставки в таблицу coupons или None,
            если отсутствуют обязательные поля secid или coupondate.
        """
        # Извлекаем обязательные поля для составного ключа
        secid = raw_data.get("secid")
        coupondate_str = raw_data.get("coupondate")
        
        if not secid or not coupondate_str:
            self.logger.warning(
                f"Пропущена запись купона: отсутствует secid или coupondate. "
                f"Данные: {raw_data}"
            )
            return None
        
        # Преобразуем даты из строк в объекты date, затем обратно в строки для хранения в БД
        # SQLite хранит DATE как TEXT в формате YYYY-MM-DD
        def parse_date(date_str: Optional[str]) -> Optional[str]:
            """Преобразует строку даты в формат YYYY-MM-DD для хранения в БД.
            
            Поддерживает различные форматы входных дат: YYYY-MM-DD, DD.MM.YYYY, YYYY/MM/DD.
            
            Args:
                date_str: Строка с датой в одном из поддерживаемых форматов.
            
            Returns:
                Строка с датой в формате YYYY-MM-DD или None, если дата не может быть распознана.
            """
            if not date_str:
                return None
            try:
                # Парсим дату из строки (может быть в разных форматах)
                if isinstance(date_str, str):
                    # Пробуем разные форматы
                    for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"]:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt).date()
                            return parsed_date.isoformat()  # Возвращаем в формате YYYY-MM-DD
                        except ValueError:
                            continue
                    # Если не удалось распарсить, возвращаем как есть (если уже в формате YYYY-MM-DD)
                    return date_str if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-' else None
                return None
            except Exception:
                return None
        
        # Преобразуем данные с обработкой отсутствующих полей
        transformed = {
            "secid": secid,
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
        
        return transformed
    
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
            secid, coupondate, recorddate, startdate, initialfacevalue,
            facevalue, faceunit, value, valueprc, value_rub
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            cursor = conn.cursor()
            inserted_count = 0
            
            for coupon in coupons:
                cursor.execute(insert_sql, (
                    coupon.get("secid"),
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
        if not self._table_exists("coupons"):
            self.logger.warning("Таблица coupons не существует, fetch_coupons_raw возвращает []")
            return []
        
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
        
        # Формируем SQL запрос динамически
        sql = """
        SELECT 
            secid, coupondate, recorddate, startdate, initialfacevalue,
            facevalue, faceunit, value, valueprc, value_rub
        FROM coupons
        """
        
        conditions = []
        params = []
        
        # Фильтрация по secid
        if secids and len(secids) > 0:
            placeholders = ",".join("?" * len(secids))
            conditions.append(f"secid IN ({placeholders})")
            params.extend(secids)
        
        # Фильтрация по датам
        # coupondate хранится как DATE в формате YYYY-MM-DD
        if from_date:
            conditions.append("coupondate >= ?")
            params.append(from_date)
        
        if till_date:
            conditions.append("coupondate <= ?")
            params.append(till_date)
        
        # Добавляем условия WHERE если есть фильтры
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        # Добавляем сортировку
        sql += " ORDER BY secid, coupondate"
        
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


