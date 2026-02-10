"""Сервис для загрузки и управления данными ключевой ставки ЦБ РФ.

Этот модуль содержит класс KeyRateService для инкрементальной загрузки данных
ключевой ставки ЦБ РФ с HTML страницы, парсинга с помощью pandas.read_html,
преобразования в модель DBkeyrate и сохранения в БД через KeyrateRepository.
Данные отдаются на фронтенд из БД без промежуточных файлов.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests
from urllib.parse import urlencode

from app.models import DBkeyrate, KeyrateDTO
from app.repository.db.keyrate_repository import KeyrateRepository
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class KeyRateService:
    """Сервис для работы с данными ключевой ставки ЦБ РФ в БД.

    Обеспечивает инкрементальную загрузку данных ключевой ставки с HTML страницы
    ЦБ РФ, парсинг с помощью pandas.read_html, сохранение в таблицу keyrate через
    KeyrateRepository. Чтение данных — только из БД.

    Attributes:
        CBR_KEYRATE_URL: Базовый URL страницы ключевой ставки ЦБ РФ.
        DEFAULT_START_DATE: Дата по умолчанию для начала загрузки (17.09.2013).
        logger: Логгер для записи событий и ошибок.
    """

    CBR_KEYRATE_URL: str = "https://www.cbr.ru/hd_base/keyrate/"
    """Базовый URL страницы ключевой ставки ЦБ РФ."""

    DEFAULT_START_DATE: date = date(2013, 9, 17)
    """Дата по умолчанию для начала загрузки (17.09.2013)."""

    def __init__(self) -> None:
        """Инициализирует сервис для работы с ключевой ставкой ЦБ РФ.

        Данные хранятся в БД через KeyrateRepository (путь к БД — config.paths.DB_PATH).
        """
        self._repo = KeyrateRepository(db_path=DB_PATH)
        self.logger = get_data_update_logger()

    def _build_url(self, date_from: date, date_to: date) -> str:
        """Формирует URL страницы ключевой ставки ЦБ РФ с параметрами запроса.

        Создает URL для загрузки данных ключевой ставки за указанный диапазон дат.
        Параметры запроса включают даты начала и конца диапазона в формате DD.MM.YYYY.

        Args:
            date_from: Начальная дата диапазона (преобразуется в формат DD.MM.YYYY).
            date_to: Конечная дата диапазона (преобразуется в формат DD.MM.YYYY).

        Returns:
            Полный URL с параметрами запроса для загрузки данных ключевой ставки.
        """
        params = {
            "UniDbQuery.Posted": "True",
            "UniDbQuery.From": date_from.strftime("%d.%m.%Y"),
            "UniDbQuery.To": date_to.strftime("%d.%m.%Y"),
        }
        url = f"{self.CBR_KEYRATE_URL}?{urlencode(params)}"
        self.logger.info("[KEYRATE SERVICE] Built URL: %s", url)
        return url

    def _fetch_and_parse_keyrate(
        self, date_from: date, date_to: date
    ) -> Dict[str, float]:
        """Загружает данные ключевой ставки с HTML страницы ЦБ РФ и парсит их.

        Выполняет HTTP запрос к странице ключевой ставки ЦБ РФ, парсит HTML таблицу
        с помощью pandas.read_html и извлекает данные о ключевой ставке за указанный
        диапазон дат. Обрабатывает русские форматы чисел (запятая как разделитель
        дробной части, пробел как разделитель тысяч).

        Args:
            date_from: Начальная дата диапазона для загрузки данных.
            date_to: Конечная дата диапазона для загрузки данных.

        Returns:
            Словарь с данными ключевой ставки, где ключ — дата в формате YYYY-MM-DD,
            значение — ключевая ставка (float) в процентах.

        Raises:
            RuntimeError: Если не удалось загрузить страницу (сетевая ошибка, таймаут)
                или если не удалось распарсить HTML таблицы.
            ValueError: Если структура таблицы не соответствует ожидаемому формату
                (отсутствуют необходимые колонки "Дата" и "Ставка") или если не удалось
                распарсить даты или значения ставок.
        """
        url = self._build_url(date_from, date_to)
        self.logger.info("[KEYRATE SERVICE] Fetching key rate data from CBR...")

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            self.logger.info(
                "[KEYRATE SERVICE] HTTP response status: %s, content length: %s bytes",
                response.status_code,
                len(response.content),
            )
        except requests.RequestException as exc:
            self.logger.error(
                "[KEYRATE SERVICE] ERROR: Failed to fetch page - %s: %s",
                type(exc).__name__,
                str(exc),
            )
            raise RuntimeError(f"Failed to fetch key rate page: {str(exc)}") from exc

        self.logger.info(
            "[KEYRATE SERVICE] Parsing HTML tables with pandas.read_html..."
        )
        try:
            tables = pd.read_html(
                response.text,
                decimal=",",
                thousands=" ",
            )
            if not tables:
                self.logger.error("[KEYRATE SERVICE] ERROR: No tables found in HTML")
                raise ValueError("No tables found on the page")
            self.logger.info(
                "[KEYRATE SERVICE] Found %s table(s), using first table",
                len(tables),
            )
        except Exception as exc:
            self.logger.error(
                "[KEYRATE SERVICE] ERROR: Failed to parse HTML - %s: %s",
                type(exc).__name__,
                str(exc),
            )
            raise RuntimeError(
                f"Failed to parse HTML tables: {str(exc)}"
            ) from exc

        df = tables[0]
        self.logger.info(
            "[KEYRATE SERVICE] Table shape: %s, columns: %s",
            df.shape,
            list(df.columns),
        )
        df.columns = df.columns.str.lower().str.strip()
        required_columns = {"дата", "ставка"}
        actual_columns = set(df.columns)
        if not required_columns.issubset(actual_columns):
            missing = required_columns - actual_columns
            error_msg = (
                f"Table columns don't match expected format. "
                f"Required columns: {required_columns}, "
                f"Actual columns: {actual_columns}, "
                f"Missing: {missing}"
            )
            self.logger.error("[KEYRATE SERVICE] ERROR: %s", error_msg)
            raise ValueError(error_msg)

        df = df.rename(columns={"дата": "date", "ставка": "key_rate"})
        try:
            df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
        except Exception as exc:
            self.logger.error(
                "[KEYRATE SERVICE] ERROR: Failed to parse dates - %s: %s",
                type(exc).__name__,
                str(exc),
            )
            raise ValueError(f"Failed to parse date column: {str(exc)}") from exc
        try:
            df["key_rate"] = pd.to_numeric(df["key_rate"], errors="coerce")
        except Exception as exc:
            self.logger.error(
                "[KEYRATE SERVICE] ERROR: Failed to parse rates - %s: %s",
                type(exc).__name__,
                str(exc),
            )
            raise ValueError(
                f"Failed to parse key_rate column: {str(exc)}"
            ) from exc

        nan_count = df["key_rate"].isna().sum()
        if nan_count > 0:
            self.logger.warning(
                "[KEYRATE SERVICE] WARNING: Found %s NaN values in key_rate column",
                nan_count,
            )
        df = df.dropna(subset=["date", "key_rate"])

        result = {}
        for _, row in df.iterrows():
            date_obj = row["date"].date()
            rate = float(row["key_rate"])
            result[date_obj.isoformat()] = rate
        self.logger.info(
            "[KEYRATE SERVICE] Successfully parsed %s key rate entries", len(result)
        )
        return result

    def load_keyrate_data(self) -> Dict[str, float]:
        """Загружает данные ключевой ставки из ЦБ РФ инкрементально и сохраняет в БД.

        Запрашивает через репозиторий максимальную дату в таблице keyrate. Если
        таблица пуста — использует DEFAULT_START_DATE. Загружает данные из API за
        период (max_date + 1 день) до текущей даты, преобразует в DBkeyrate и
        сохраняет через репозиторий. Возвращает все данные из БД в формате словаря.

        Returns:
            Словарь со всеми данными ключевой ставки из БД: ключ — дата YYYY-MM-DD,
            значение — ключевая ставка (float) в процентах.

        Raises:
            RuntimeError: Если не удалось загрузить или распарсить данные из ЦБ РФ.
        """
        self.logger.info("[KEYRATE SERVICE] Starting key rate data load...")

        max_date = self._repo.get_max_date()
        if max_date is None:
            date_from = self.DEFAULT_START_DATE
            self.logger.info(
                "[KEYRATE SERVICE] Table empty, using default start date: %s",
                date_from.strftime("%d.%m.%Y"),
            )
        else:
            date_from = max_date + timedelta(days=1)
            self.logger.info(
                "[KEYRATE SERVICE] Using range from DB max date: %s",
                date_from.strftime("%d.%m.%Y"),
            )

        date_to = date.today()
        self.logger.info(
            "[KEYRATE SERVICE] End date: %s", date_to.strftime("%d.%m.%Y")
        )

        if date_from > date_to:
            self.logger.info("[KEYRATE SERVICE] No new data to download")
            return self._repo.get_all_as_dict()

        new_data = self._fetch_and_parse_keyrate(date_from, date_to)
        records = [
            DBkeyrate(
                dt=datetime.strptime(d, "%Y-%m-%d").date(),
                rate=r,
            )
            for d, r in new_data.items()
        ]
        if records:
            self._repo.save_many(records)
            self.logger.info(
                "[KEYRATE SERVICE] Key rate data load completed. "
                "New entries: %s, total from DB",
                len(records),
            )
        else:
            self.logger.info(
                "[KEYRATE SERVICE] No new records from API for period %s..%s",
                date_from.isoformat(),
                date_to.isoformat(),
            )

        records = self._repo.get_by_date_range(from_date=None, till_date=None)
        return {r.dt.isoformat(): r.rate for r in records}

    def get_keyrate_data(self) -> Dict[str, float]:
        """Возвращает все данные ключевой ставки из БД в формате словаря для API.

        Returns:
            Словарь: ключ — дата в формате YYYY-MM-DD, значение — ключевая ставка
            (float) в процентах. Пустой словарь, если таблица пуста.
        """
        records = self._repo.get_by_date_range(from_date=None, till_date=None)
        return {r.dt.isoformat(): r.rate for r in records}

    def get_keyrate_list(
        self,
        from_date: Optional[date] = None,
        till_date: Optional[date] = None,
    ) -> List[KeyrateDTO]:
        """Возвращает список записей ключевой ставки из БД в формате DTO для таблицы.

        Получает записи из репозитория по диапазону дат и преобразует каждую
        запись в KeyrateDTO через model_validate (без ручного маппинга).

        Args:
            from_date: Начальная дата диапазона (включительно). None — без фильтра.
            till_date: Конечная дата диапазона (включительно). None — без фильтра.

        Returns:
            Список KeyrateDTO для отображения в таблице на фронтенде.
        """
        records = self._repo.get_by_date_range(from_date=from_date, till_date=till_date)
        return [KeyrateDTO.model_validate(record) for record in records]


_keyrate_service: Optional[KeyRateService] = None


def init_keyrate_service() -> None:
    """Инициализирует singleton экземпляр сервиса ключевой ставки.

    Создаёт глобальный экземпляр KeyRateService. Данные хранятся в БД.
    Должен быть вызван перед использованием get_keyrate_service().
    """
    global _keyrate_service
    _keyrate_service = KeyRateService()


def get_keyrate_service() -> KeyRateService:
    """Получает singleton экземпляр сервиса ключевой ставки.

    Returns:
        Экземпляр KeyRateService для работы с данными ключевой ставки ЦБ РФ.

    Raises:
        RuntimeError: Если сервис не был инициализирован через init_keyrate_service().
    """
    if _keyrate_service is None:
        raise RuntimeError(
            "KeyRateService not initialized. Call init_keyrate_service() first."
        )
    return _keyrate_service
