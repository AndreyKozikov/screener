"""Репозиторий для работы с базой данных кривой бескупонной доходности (KBD).

Этот модуль содержит класс DBkbd для работы с таблицей kbd в SQLite базе данных.
Обеспечивает создание, обновление и запросы данных о кривой бескупонной доходности.
"""

import sqlite3
import logging
import csv
import math
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime


class DBkbd:
    """Репозиторий для работы с базой данных кривой бескупонной доходности (KBD).
    
    Класс обеспечивает работу с таблицей kbd в SQLite базе данных.
    Отвечает за создание, обновление и запросы данных о кривой бескупонной доходности.
    
    Основные методы:
        refresh(): Создание или обновление таблицы kbd из CSV файла (миграции).
        get_kbd_data(): Извлечение сырых данных из таблицы kbd с фильтрацией по дате.
    
    Attributes:
        column_mapping: Словарь маппинга русских заголовков CSV на английские названия столбцов БД.
    
    Note:
        Обеспечивает полную синхронизацию данных кривой бескупонной доходности между CSV-источником
        и SQLite базой данных с гарантией целостности и актуальности информации.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Инициализирует экземпляр репозитория для работы с кривой бескупонной доходности.
        
        Args:
            db_path: Путь к файлу базы данных SQLite. Если не указан,
                используется путь по умолчанию: backend/db/bonds.db
        
        Attributes:
            db_path: Путь к файлу базы данных.
            logger: Логгер для записи событий и ошибок.
            column_mapping: Словарь маппинга русских заголовков CSV на английские столбцы БД.
        """
        if db_path is None:
            # Определяем путь относительно текущего файла
            backend_dir = Path(__file__).parent.parent.parent
            db_path = str(backend_dir / "db" / "bonds.db")
        
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
        # Маппинг русских заголовков на английские столбцы
        self.column_mapping = {
            "Дата": "date",
            "Время": "time",
            "Срок 0.25 лет": "term_0_25",
            "Срок 0.5 лет": "term_0_5",
            "Срок 0.75 лет": "term_0_75",
            "Срок 1.0 лет": "term_1_0",
            "Срок 2.0 лет": "term_2_0",
            "Срок 3.0 лет": "term_3_0",
            "Срок 5.0 лет": "term_5_0",
            "Срок 7.0 лет": "term_7_0",
            "Срок 10.0 лет": "term_10_0",
            "Срок 15.0 лет": "term_15_0",
            "Срок 20.0 лет": "term_20_0",
            "Срок 30.0 лет": "term_30_0"
        }
    
    def refresh(self, table_name: str) -> None:
        """Создает или обновляет таблицу kbd в базе данных из CSV файла.
        
        Выполняет полную синхронизацию данных кривой бескупонной доходности между CSV-источником
        (zerocupon.csv) и SQLite базой данных. Загружает данные, преобразует их и сохраняет в БД
        в рамках одной транзакции.
        
        Последовательность выполнения:
            1. Установить соединение с базой данных
            2. Проверить существование таблицы kbd
            3. Если таблица не существует — создать её
            4. Загрузить данные из backend/app/data/zerocupon.csv
            5. Преобразовать данные для каждой записи с применением column_mapping
            6. Выполнить INSERT OR REPLACE INTO для всех записей в транзакции
            7. Зафиксировать транзакцию
            8. При ошибке выполнить rollback и пробросить исключение
        
        Args:
            table_name: Имя таблицы для работы в БД. Должно быть "kbd".
        
        Raises:
            FileNotFoundError: Если CSV файл zerocupon.csv не найден.
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
                    self._create_kbd_table(conn)
                else:
                    self.logger.info(f"Таблица {table_name} существует, обновляем данные")
                
                # Загружаем данные из CSV
                raw_data = self._load_csv_data()
                if not raw_data:
                    self.logger.warning("CSV файл пуст или не содержит данных")
                    return
                
                self.logger.info(f"Загружено {len(raw_data)} записей из CSV-файла")
                
                # Преобразуем данные
                transformed_records = []
                for raw_record in raw_data:
                    try:
                        transformed = self._transform_kbd_data(raw_record)
                        if transformed:
                            transformed_records.append(transformed)
                    except Exception as e:
                        self.logger.warning(
                            f"Ошибка при преобразовании данных KBD "
                            f"(date={raw_record.get('Дата', 'unknown')}, "
                            f"time={raw_record.get('Время', 'unknown')}): {e}"
                        )
                        continue
                
                self.logger.info(f"Преобразовано {len(transformed_records)} записей")
                
                # Вставляем или заменяем записи в транзакции
                self._insert_or_replace_kbd(conn, transformed_records)
                
                self.logger.info(
                    f"Таблица {table_name} успешно создана/обновлена в базе данных: {self.db_path}"
                )
        except FileNotFoundError as e:
            self.logger.error(f"Ошибка при загрузке данных из CSV: {str(e)}", exc_info=True)
            raise
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при работе с базой данных: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка при синхронизации KBD: {str(e)}", exc_info=True)
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
    
    def _create_kbd_table(self, conn: sqlite3.Connection) -> None:
        """Создает таблицу kbd с указанной структурой.
        
        Определяет схему таблицы kbd со всеми необходимыми колонками
        для хранения данных о кривой бескупонной доходности. Выполняет CREATE TABLE IF NOT EXISTS.
        
        Args:
            conn: Соединение с базой данных SQLite.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при создании таблицы.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS kbd (
            date DATE NOT NULL,
            time TIME NOT NULL,
            term_0_25 REAL,
            term_0_5 REAL,
            term_0_75 REAL,
            term_1_0 REAL,
            term_2_0 REAL,
            term_3_0 REAL,
            term_5_0 REAL,
            term_7_0 REAL,
            term_10_0 REAL,
            term_15_0 REAL,
            term_20_0 REAL,
            term_30_0 REAL,
            PRIMARY KEY (date, time)
        )
        """
        
        try:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            conn.commit()
            self.logger.info("Таблица kbd успешно создана")
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при создании таблицы kbd: {e}", exc_info=True)
            raise
    
    def _load_csv_data(self) -> List[Dict[str, str]]:
        """Загружает данные из backend/app/data/zerocupon.csv.
        
        Читает CSV файл с разделителем точка с запятой и преобразует его в список словарей.
        Пропускает пустые строки. Ключи словарей соответствуют русским заголовкам CSV файла.
        
        Returns:
            Список словарей с данными из CSV. Каждый словарь содержит данные одной строки,
            где ключи - русские заголовки столбцов (могут содержать BOM символ).
        
        Raises:
            FileNotFoundError: Если файл zerocupon.csv не найден.
        """
        # Определяем путь к файлу относительно текущего файла
        backend_dir = Path(__file__).parent.parent.parent
        data_dir = backend_dir / "app" / "data"
        csv_path = data_dir / "zerocupon.csv"
        
        if not csv_path.exists():
            error_msg = f"Файл zerocupon.csv не найден: {csv_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            records = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    # Пропускаем пустые строки
                    if not any(row.values()):
                        continue
                    records.append(row)
            
            return records
        except Exception as e:
            error_msg = f"Ошибка при загрузке данных из {csv_path}: {e}"
            self.logger.error(error_msg, exc_info=True)
            raise
    
    def _transform_kbd_data(self, raw_data: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Преобразует данные из CSV в формат таблицы базы данных.
        
        Выполняет преобразование сырых данных из CSV формата в формат, пригодный
        для вставки в таблицу kbd. Применяет column_mapping для преобразования русских
        заголовков в английские названия столбцов. Преобразует даты и время в стандартные
        форматы SQLite и числовые поля в REAL, используя NULL для пустых значений.
        
        Args:
            raw_data: Словарь с сырыми данными из CSV. Ключи - русские заголовки,
                могут содержать BOM символ (\ufeff) в начале. Должен содержать
                обязательные поля "Дата" и "Время".
        
        Returns:
            Словарь с преобразованными данными для вставки в таблицу kbd или None,
            если отсутствуют обязательные поля "Дата" или "Время", или если дата
            имеет неверный формат.
        """
        # Нормализуем ключи, убирая BOM символ (\ufeff) если он есть
        normalized_data = {}
        for key, value in raw_data.items():
            # Убираем BOM символ из начала ключа
            normalized_key = key.lstrip('\ufeff')
            normalized_data[normalized_key] = value
        
        # Извлекаем обязательные поля для составного ключа
        date_value = normalized_data.get("Дата")
        time_value = normalized_data.get("Время")
        
        if not date_value or not time_value:
            self.logger.warning(
                f"Пропущена запись KBD: отсутствует date или time. "
                f"Данные: {raw_data}"
            )
            return None
        
        # Преобразуем дату из формата DD.MM.YYYY в формат YYYY-MM-DD (стандартный формат SQLite DATE)
        date_str = date_value.strip() if date_value else None
        date_formatted = None
        if date_str:
            try:
                # Парсим дату из формата DD.MM.YYYY
                date_obj = datetime.strptime(date_str, "%d.%m.%Y")
                # Преобразуем в формат YYYY-MM-DD для SQLite DATE
                date_formatted = date_obj.strftime("%Y-%m-%d")
            except ValueError as e:
                self.logger.warning(
                    f"Неверный формат даты в записи KBD: {date_str}. "
                    f"Ожидается формат DD.MM.YYYY. Ошибка: {e}"
                )
                return None
        
        # Преобразуем время в формат HH:MM:SS (стандартный формат SQLite TIME)
        time_str = time_value.strip() if time_value else None
        time_formatted = None
        if time_str:
            try:
                # Парсим время из различных возможных форматов
                # Может быть HH:MM:SS или просто HH:MM
                if len(time_str.split(':')) == 2:
                    # Формат HH:MM, добавляем секунды
                    time_obj = datetime.strptime(time_str, "%H:%M")
                    time_formatted = time_obj.strftime("%H:%M:%S")
                elif len(time_str.split(':')) == 3:
                    # Формат HH:MM:SS
                    time_obj = datetime.strptime(time_str, "%H:%M:%S")
                    time_formatted = time_obj.strftime("%H:%M:%S")
                else:
                    # Пытаемся распарсить как есть
                    time_formatted = time_str
            except ValueError as e:
                self.logger.warning(
                    f"Неверный формат времени в записи KBD: {time_str}. "
                    f"Ожидается формат HH:MM или HH:MM:SS. Ошибка: {e}"
                )
                # Используем исходное значение, если не удалось распарсить
                time_formatted = time_str
        
        # Преобразуем данные с применением маппинга
        transformed = {
            "date": date_formatted,
            "time": time_formatted,
        }
        
        # Преобразуем числовые поля
        for russian_col, english_col in self.column_mapping.items():
            if russian_col in ["Дата", "Время"]:
                continue  # Уже обработаны выше
            
            value = normalized_data.get(russian_col, "").strip()
            if not value:
                transformed[english_col] = None
            else:
                try:
                    # Заменяем запятую на точку для корректного парсинга
                    value = value.replace(",", ".")
                    float_value = float(value)
                    # Проверяем на NaN и inf
                    if math.isnan(float_value) or math.isinf(float_value):
                        transformed[english_col] = None
                    else:
                        transformed[english_col] = float_value
                except (ValueError, TypeError):
                    transformed[english_col] = None
        
        return transformed
    
    def _insert_or_replace_kbd(self, conn: sqlite3.Connection, records: List[Dict[str, Any]]) -> None:
        """Вставляет или заменяет записи используя INSERT OR REPLACE INTO.
        
        Выполняет массовую вставку данных кривой бескупонной доходности в таблицу kbd
        используя INSERT OR REPLACE INTO. Все операции выполняются в рамках одной транзакции
        с явным commit или rollback при ошибках.
        
        Args:
            conn: Соединение с базой данных SQLite.
            records: Список словарей с данными для вставки/обновления. Каждый словарь
                должен содержать все поля таблицы kbd.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
                При ошибке выполняется rollback транзакции.
        """
        if not records:
            self.logger.warning("Нет данных для вставки")
            return
        
        insert_sql = """
        INSERT OR REPLACE INTO kbd (
            date, time, term_0_25, term_0_5, term_0_75, term_1_0,
            term_2_0, term_3_0, term_5_0, term_7_0, term_10_0,
            term_15_0, term_20_0, term_30_0
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            cursor = conn.cursor()
            inserted_count = 0
            
            for record in records:
                cursor.execute(insert_sql, (
                    record.get("date"),
                    record.get("time"),
                    record.get("term_0_25"),
                    record.get("term_0_5"),
                    record.get("term_0_75"),
                    record.get("term_1_0"),
                    record.get("term_2_0"),
                    record.get("term_3_0"),
                    record.get("term_5_0"),
                    record.get("term_7_0"),
                    record.get("term_10_0"),
                    record.get("term_15_0"),
                    record.get("term_20_0"),
                    record.get("term_30_0"),
                ))
                inserted_count += 1
            
            # Фиксируем транзакцию
            conn.commit()
            self.logger.info(f"Успешно вставлено/обновлено {inserted_count} записей в таблицу kbd")
        except sqlite3.Error as e:
            # Выполняем rollback при ошибке
            conn.rollback()
            self.logger.error(f"Ошибка при вставке данных в таблицу kbd: {e}", exc_info=True)
            raise
    
    def get_kbd_data(self, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[Dict[str, Any]]:
        """Извлекает сырые данные из таблицы kbd с фильтрацией по дате.
        
        Выполняет SELECT запрос к таблице kbd с опциональной фильтрацией по диапазону дат.
        Преобразует даты из формата DD.MM.YYYY (входной формат) в YYYY-MM-DD (формат БД).
        Результаты отсортированы по дате в порядке убывания (от новых к старым).
        
        Args:
            date_from: Начальная дата диапазона в формате DD.MM.YYYY (включительно).
                Если None, фильтр не применяется (выбираются все записи до date_to).
            date_to: Конечная дата диапазона в формате DD.MM.YYYY (включительно).
                Если None, фильтр не применяется (выбираются все записи от date_from).
        
        Returns:
            Список словарей с данными из таблицы kbd. Каждый словарь содержит все поля
            таблицы (date, time, term_0_25, term_0_5, и т.д.). Результаты отсортированы
            по date DESC (от новых к старым). Если таблица не существует, возвращает
            пустой список.
        
        Raises:
            sqlite3.Error: Если произошла ошибка при работе с базой данных.
        """
        if not self._table_exists("kbd"):
            self.logger.warning("Таблица kbd не существует, get_kbd_data возвращает []")
            return []
        
        # Базовый SQL запрос
        sql = "SELECT * FROM kbd"
        conditions = []
        params = []
        
        # Добавляем фильтрацию по дате
        # Даты в БД хранятся в формате YYYY-MM-DD (тип DATE)
        if date_from:
            try:
                # Преобразуем DD.MM.YYYY в YYYY-MM-DD
                date_from_dt = datetime.strptime(date_from, "%d.%m.%Y")
                date_from_sql = date_from_dt.strftime("%Y-%m-%d")
                conditions.append("date >= ?")
                params.append(date_from_sql)
            except ValueError:
                self.logger.warning(f"Неверный формат date_from: {date_from}, пропускаем фильтр")
        
        if date_to:
            try:
                # Преобразуем DD.MM.YYYY в YYYY-MM-DD
                date_to_dt = datetime.strptime(date_to, "%d.%m.%Y")
                date_to_sql = date_to_dt.strftime("%Y-%m-%d")
                conditions.append("date <= ?")
                params.append(date_to_sql)
            except ValueError:
                self.logger.warning(f"Неверный формат date_to: {date_to}, пропускаем фильтр")
        
        # Добавляем условия WHERE если есть фильтры
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        # Добавляем сортировку
        sql += " ORDER BY date DESC"
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
                self.logger.debug(f"Выбрано {len(result)} записей из таблицы kbd (фильтры: date_from={date_from}, date_to={date_to})")
                return result
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка при get_kbd_data: {e}", exc_info=True)
            raise