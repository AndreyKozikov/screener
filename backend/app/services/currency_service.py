"""Сервис для работы с курсами валют от ЦБ РФ.

Этот модуль содержит класс CurrencyService для инкрементальной загрузки
курсов валют из API ЦБ РФ, преобразования в модель DBcurrencyrate и
сохранения в БД через CurrencyrateRepository. Данные отдаются на фронтенд
из БД без промежуточных файлов.
"""

import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Dict, List, Optional, Any

import requests

from app.models.currencyrate import DBcurrencyrate
from app.repository.db.currencyrate_repository import CurrencyrateRepository
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


class CurrencyService:
    """Сервис для работы с курсами валют от ЦБ РФ в БД.

    Обеспечивает инкрементальную загрузку курсов валют из API ЦБ РФ за период
    (max_date + 1 день) до текущей даты, преобразование в DBcurrencyrate и
    сохранение в таблицу currencyrate через CurrencyrateRepository. Чтение
    данных — только из БД.

    Attributes:
        INTERESTED_CURRENCIES: Список кодов валют (EUR, USD, CNY).
        CBR_BASE_URL: Базовый URL API ЦБ РФ для получения курсов валют.
        DEFAULT_START_DATE: Начальная дата для загрузки при пустой таблице.
        logger: Логгер для записи событий и ошибок.
    """

    INTERESTED_CURRENCIES: List[str] = ["EUR", "USD", "CNY"]
    """Список кодов валют, которые интересуют приложение."""

    CBR_BASE_URL: str = "https://www.cbr.ru/scripts/XML_daily.asp"
    """Базовый URL API ЦБ РФ для получения курсов валют."""

    DEFAULT_START_DATE: date = date(2003, 1, 1)
    """Начальная дата для загрузки при пустой таблице currencyrate."""

    def __init__(self) -> None:
        """Инициализирует сервис для работы с курсами валют.

        Данные хранятся в БД через CurrencyrateRepository (путь к БД — config.paths.DB_PATH).
        """
        self._repo = CurrencyrateRepository(db_path=DB_PATH)
        self.logger = get_data_update_logger()

    def _fetch_rates_from_cbr(self, target_date: date) -> Dict[str, Any]:
        """Загружает курсы валют из API ЦБ РФ для указанной даты.

        Выполняет HTTP запрос к API Центрального банка РФ для получения курсов
        валют на указанную дату. Парсит XML ответ и извлекает курсы для
        интересующих валют (EUR, USD, CNY). Рассчитывает курс за 1 единицу
        валюты с учетом номинала.

        Args:
            target_date: Дата для получения курсов валют.

        Returns:
            Словарь с данными о курсах валют, содержащий:
            - date: Дата в формате YYYY-MM-DD
            - source_date: Дата из ответа API ЦБ РФ (атрибут Date элемента ValCurs)
            - rates: Словарь с курсами валют (ключ — код валюты), значение — словарь
              с полями code, rate, nominal, original_value.

        Raises:
            RuntimeError: Если не удалось загрузить данные или распарсить XML.
        """
        date_str = target_date.strftime("%d/%m/%Y")
        url = f"{self.CBR_BASE_URL}?date_req={date_str}"

        try:
            response = requests.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=30,
            )
            response.raise_for_status()
            content = response.content
            try:
                xml_text = content.decode("windows-1251")
            except UnicodeDecodeError:
                xml_text = content.decode("utf-8")

            root = ET.fromstring(xml_text)
            val_curs_date = root.get("Date", "")

            rates = {}
            for valute in root.findall("Valute"):
                char_code = valute.find("CharCode")
                value = valute.find("Value")
                nominal = valute.find("Nominal")

                if char_code is not None and value is not None:
                    code = char_code.text
                    value_str = value.text.replace(",", ".") if value.text else "0"
                    nominal_val = (
                        int(nominal.text) if nominal is not None and nominal.text else 1
                    )
                    try:
                        rate_value = float(value_str) / nominal_val
                        if code in self.INTERESTED_CURRENCIES:
                            rates[code] = {
                                "code": code,
                                "rate": rate_value,
                                "nominal": nominal_val,
                                "original_value": value.text or "",
                            }
                    except (ValueError, TypeError):
                        pass

            return {
                "date": target_date.isoformat(),
                "source_date": val_curs_date,
                "rates": rates,
            }
        except requests.RequestException as exc:
            self.logger.error(
                "[CURRENCY SERVICE] ERROR: API request failed - %s: %s",
                type(exc).__name__,
                str(exc),
            )
            raise RuntimeError(
                f"Failed to fetch currency rates from CBR API: {exc}"
            ) from exc
        except ET.ParseError as exc:
            self.logger.error(
                "[CURRENCY SERVICE] ERROR: Failed to parse XML - %s", str(exc)
            )
            raise RuntimeError(
                f"Failed to parse XML response from CBR API: {exc}"
            ) from exc

    def _api_dict_to_db(self, api_dict: Dict[str, Any]) -> DBcurrencyrate:
        """Преобразует ответ API ЦБ РФ (одна дата) в модель DBcurrencyrate.

        Args:
            api_dict: Словарь с полями date (YYYY-MM-DD), source_date, rates.

        Returns:
            Объект DBcurrencyrate для сохранения в БД.
        """
        target_date = date.fromisoformat(api_dict["date"])
        rates = api_dict.get("rates") or {}
        usd = rates.get("USD", {})
        eur = rates.get("EUR", {})
        cny = rates.get("CNY", {})

        return DBcurrencyrate(
            dt=target_date,
            source_date=api_dict.get("source_date", ""),
            usd_rate=usd.get("rate"),
            usd_nominal=usd.get("nominal"),
            usd_original_value=usd.get("original_value"),
            eur_rate=eur.get("rate"),
            eur_nominal=eur.get("nominal"),
            eur_original_value=eur.get("original_value"),
            cny_rate=cny.get("rate"),
            cny_nominal=cny.get("nominal"),
            cny_original_value=cny.get("original_value"),
        )

    def _db_to_api_dict(self, row: DBcurrencyrate) -> Dict[str, Any]:
        """Преобразует запись DBcurrencyrate в формат ответа API (date, source_date, rates).

        Args:
            row: Запись из таблицы currencyrate.

        Returns:
            Словарь с полями date, source_date, rates для отдачи на фронтенд.
        """
        rates = {}
        if row.usd_rate is not None:
            rates["USD"] = {
                "code": "USD",
                "rate": row.usd_rate,
                "nominal": row.usd_nominal or 1,
                "original_value": row.usd_original_value or "",
            }
        if row.eur_rate is not None:
            rates["EUR"] = {
                "code": "EUR",
                "rate": row.eur_rate,
                "nominal": row.eur_nominal or 1,
                "original_value": row.eur_original_value or "",
            }
        if row.cny_rate is not None:
            rates["CNY"] = {
                "code": "CNY",
                "rate": row.cny_rate,
                "nominal": row.cny_nominal or 1,
                "original_value": row.cny_original_value or "",
            }
        return {
            "date": row.dt.isoformat(),
            "source_date": row.source_date or "",
            "rates": rates,
        }

    def _load_incremental(self) -> None:
        """Загружает курсы валют из API ЦБ РФ инкрементально и сохраняет в БД.

        Получает максимальную дату из таблицы currencyrate. Если таблица пуста —
        использует DEFAULT_START_DATE. Запрашивает данные из API за период
        (max_date + 1 день) до текущей даты, преобразует в DBcurrencyrate и
        сохраняет через репозиторий.
        """
        max_date = self._repo.get_max_date()
        if max_date is None:
            date_from = self.DEFAULT_START_DATE
        else:
            date_from = max_date + timedelta(days=1)
        date_to = date.today()

        if date_from > date_to:
            self.logger.info("[CURRENCY SERVICE] Incremental load: no new dates to download")
            return

        self.logger.info(
            "[CURRENCY SERVICE] Incremental load started: period %s..%s",
            date_from.isoformat(),
            date_to.isoformat(),
        )

        records: List[DBcurrencyrate] = []
        skipped = 0
        current = date_from
        while current <= date_to:
            try:
                api_data = self._fetch_rates_from_cbr(current)
                records.append(self._api_dict_to_db(api_data))
            except RuntimeError:
                skipped += 1
            current += timedelta(days=1)

        if records:
            self._repo.save_many(records)
            self.logger.info(
                "[CURRENCY SERVICE] Incremental load completed: saved %s entries",
                len(records),
            )
            if skipped:
                self.logger.warning(
                    "[CURRENCY SERVICE] Skipped %s date(s) due to API errors",
                    skipped,
                )
        else:
            self.logger.info(
                "[CURRENCY SERVICE] Incremental load completed: no new records for period %s..%s",
                date_from.isoformat(),
                date_to.isoformat(),
            )
            if skipped:
                self.logger.warning(
                    "[CURRENCY SERVICE] All %s date(s) failed (API errors)",
                    skipped,
                )

    def get_rates(
        self, target_date: Optional[date] = None, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Получает курсы валют для указанной даты из БД.

        При force_refresh выполняет инкрементальную загрузку из API ЦБ РФ,
        затем читает из БД. Иначе читает из БД: сначала по точной дате, при
        отсутствии — ближайшую предыдущую запись с датой <= target_date. Если
        записей нет — возвращает структуру с пустым rates.

        Args:
            target_date: Дата для получения курсов. Если не указана — сегодня.
            force_refresh: Если True, перед чтением выполняется инкрементальная
                загрузка из API ЦБ РФ.

        Returns:
            Словарь с полями date, source_date, rates для отдачи на фронтенд.
        """
        if target_date is None:
            target_date = date.today()

        if force_refresh:
            self._load_incremental()

        row = self._repo.get_by_date(target_date)
        if row is None:
            row = self._repo.get_latest_on_or_before(target_date)
        if row is None:
            return {
                "date": target_date.isoformat(),
                "source_date": "",
                "rates": {},
            }
        return self._db_to_api_dict(row)

    def refresh_rates(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """Принудительно обновляет курсы валют: инкрементальная загрузка из API и ответ по дате.

        Выполняет инкрементальную загрузку из API ЦБ РФ (период от max_date+1
        до сегодня), сохраняет в БД, затем возвращает результат для указанной
        даты (количество курсов и статус).

        Args:
            target_date: Дата для отчёта. Если не указана — сегодня.

        Returns:
            Словарь с полями status, date, rates_count, error (при ошибке), updated.
        """
        if target_date is None:
            target_date = date.today()

        target_date_str = target_date.isoformat()
        self.logger.info("[CURRENCY SERVICE] Refresh started for date: %s", target_date_str)

        try:
            self._load_incremental()
            row = self._repo.get_by_date(target_date)
            if row is None:
                row = self._repo.get_latest_on_or_before(target_date)
            rates_count = 0
            if row is not None:
                d = self._db_to_api_dict(row)
                rates_count = len(d.get("rates", {}))
            self.logger.info(
                "[CURRENCY SERVICE] Refresh completed: %s rates for date %s",
                rates_count,
                target_date_str,
            )
            return {
                "status": "ok",
                "date": target_date_str,
                "rates_count": rates_count,
                "updated": True,
            }
        except Exception as exc:
            self.logger.error(
                "[CURRENCY SERVICE] ERROR: Failed to refresh rates - %s: %s",
                type(exc).__name__,
                str(exc),
            )
            return {
                "status": "error",
                "date": target_date_str,
                "error": str(exc),
                "updated": False,
            }


_currency_service: Optional[CurrencyService] = None


def init_currency_service() -> None:
    """Инициализирует singleton экземпляр сервиса курсов валют.

    Создаёт глобальный экземпляр CurrencyService. Данные хранятся в БД.
    """
    global _currency_service
    _currency_service = CurrencyService()


def get_currency_service() -> CurrencyService:
    """Получает singleton экземпляр сервиса курсов валют.

    Returns:
        Экземпляр CurrencyService для работы с курсами валют.

    Raises:
        RuntimeError: Если сервис не был инициализирован через init_currency_service().
    """
    if _currency_service is None:
        raise RuntimeError("Currency service not initialized")
    return _currency_service
