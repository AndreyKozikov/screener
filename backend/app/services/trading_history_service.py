"""Сервис для загрузки истории торгов по облигациям из API Мосбиржи.

Этот модуль содержит класс TradingHistoryService для загрузки истории торгов
по облигациям из API Московской биржи. Данные сохраняются в bonds_trading_history.json
(ключ — secid) и обновляются инкрементально.
"""

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import orjson

from app.utils.logger import get_data_update_logger
from config.paths import HISTORY_JSON, MOEX_HISTORY_URL


DEFAULT_FROM_DATE: date = date(2000, 1, 1)
"""Дата начала загрузки при отсутствии файла или данных по облигации."""


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Парсит строку даты в объект date.
    
    Преобразует строку с датой в формате YYYY-MM-DD в объект date.
    Обрабатывает некорректные значения и специальное значение "0000-00-00".
    
    Args:
        s: Строка с датой в формате YYYY-MM-DD или None.
    
    Returns:
        Объект date или None, если строка некорректна, пуста или равна "0000-00-00".
    """
    if not s or s == "0000-00-00":
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _date_str(d: date) -> str:
    """Преобразует объект date в строку формата YYYY-MM-DD.
    
    Args:
        d: Объект date для преобразования.
    
    Returns:
        Строка с датой в формате YYYY-MM-DD.
    """
    return d.strftime("%Y-%m-%d")


class TradingHistoryService:
    """Сервис для загрузки истории торгов по облигациям из API Мосбиржи.
    
    Класс обеспечивает загрузку истории торгов по облигациям из API Московской биржи,
    сохранение данных в JSON файл и инкрементальное обновление данных. Поддерживает
    загрузку истории для одной облигации или массовую загрузку для всех облигаций
    из bonds.json.
    
    Attributes:
        data_dir: Путь к директории с JSON файлами данных.
    """
    
    def __init__(self, data_dir: Path):
        """Инициализирует сервис для работы с историей торгов.
        
        Args:
            data_dir: Путь к директории с JSON файлами данных.
        """
        self.data_dir = Path(data_dir)

    def _history_path(self) -> Path:
        """Получает путь к файлу истории торгов.
        
        Returns:
            Путь к файлу bonds_trading_history.json в директории данных.
        """
        return self.data_dir / HISTORY_JSON

    def _load_all_secids(self) -> List[str]:
        """Загружает из bonds.json все SECID облигаций.
        
        Загружает файл bonds.json и извлекает все уникальные SECID из секции
        securities.data. Используется для массовой загрузки истории торгов.
        
        Returns:
            Отсортированный список уникальных SECID облигаций. Если файл не существует
            или колонка SECID отсутствует, возвращает пустой список.
        """
        path = self.data_dir / "bonds.json"
        with open(path, "rb") as f:
            data = orjson.loads(f.read())
        sec = data.get("securities", {})
        columns = sec.get("columns", [])
        rows = sec.get("data", [])
        try:
            idx_secid = columns.index("SECID")
        except ValueError:
            return []
        out: List[str] = []
        for row in rows:
            if len(row) <= idx_secid:
                continue
            s = row[idx_secid]
            if s and str(s).strip():
                out.append(str(s).strip())
        return sorted(set(out))

    def load_history_file(self) -> Dict[str, Dict[str, Any]]:
        """Читает bonds_trading_history.json.
        
        Загружает данные истории торгов из файла bonds_trading_history.json.
        По каждому secid хранится только секция history: columns (заголовки) и data (данные).
        Метаданные и курсор не сохраняются.
        
        Returns:
            Словарь с данными истории торгов, где ключ - SECID облигации, значение -
            словарь с ключами:
            - columns: Список названий колонок таблицы истории
            - data: Список списков с данными строк истории торгов
            Если файл не существует или некорректен, возвращает пустой словарь.
        """
        path = self._history_path()
        if not path.exists():
            return {}
        with open(path, "rb") as f:
            data = orjson.loads(f.read())
        if not isinstance(data, dict):
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            # Только history: columns и data
            cols = v.get("columns")
            rows = v.get("data")
            if isinstance(cols, list) and isinstance(rows, list):
                out[k] = {"columns": cols, "data": rows}
        return out

    def save_history_file(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Сохраняет данные истории торгов в bonds_trading_history.json.
        
        Записывает данные в файл bonds_trading_history.json с форматированием
        (отступы и перенос строки). Сохраняет только данные из секции history:
        columns (заголовки таблицы) и data (строки). Метаданные и курсор не сохраняются.
        
        Args:
            data: Словарь с данными истории торгов, где ключ - SECID облигации,
                значение - словарь с ключами "columns" и "data".
        """
        path = self._history_path()
        raw = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        path.write_bytes(raw)

    def _last_tradedate(self, history: Dict[str, Any]) -> Optional[date]:
        """Получает последнюю дату торгов в истории.
        
        Находит максимальную дату торгов (TRADEDATE) среди всех записей в истории.
        Используется для определения начальной даты при инкрементальном обновлении.
        
        Args:
            history: Словарь с данными истории торгов, содержащий ключи "columns"
                и "data".
        
        Returns:
            Объект date с последней датой торгов или None, если колонка TRADEDATE
            отсутствует или история пуста.
        """
        cols = history.get("columns") or []
        data_rows = history.get("data") or []
        try:
            idx = cols.index("TRADEDATE")
        except ValueError:
            return None
        last: Optional[date] = None
        for row in data_rows:
            if len(row) <= idx:
                continue
            d = _parse_date(row[idx])
            if d and (last is None or d > last):
                last = d
        return last

    def get_from_till(
        self, secid: str
    ) -> Tuple[str, str, bool]:
        """Определяет диапазон дат для загрузки истории торгов.
        
        Определяет начальную (from) и конечную (till) даты для загрузки истории торгов
        и признак дописывания данных (is_append). Если данных нет, использует
        DEFAULT_FROM_DATE как начальную дату. Если данные есть, начинает с последней
        даты торгов + 1 день.
        
        Args:
            secid: Идентификатор облигации (SECID) для определения диапазона дат.
        
        Returns:
            Кортеж из трех элементов:
            - from_YYYY_MM_DD: Начальная дата диапазона в формате YYYY-MM-DD
            - till_YYYY_MM_DD: Конечная дата диапазона в формате YYYY-MM-DD (текущая дата)
            - is_append: Флаг дописывания данных (True если данные существуют, False если первая загрузка)
        
        Note:
            Если последняя дата в истории больше текущей даты (битая/будущая дата),
            используется DEFAULT_FROM_DATE как начальная дата.
        """
        logger = get_data_update_logger()
        today = date.today()
        all_history = self.load_history_file()
        existing = all_history.get(secid)

        if not existing or not (existing.get("data")):
            # Данных нет: from = DEFAULT_FROM_DATE, till = текущая дата
            from_d = DEFAULT_FROM_DATE
            till_d = today
            logger.info(
                f"[TRADING HISTORY] Первая загрузка {secid}: "
                f"from={_date_str(from_d)} (по умолчанию), till={_date_str(till_d)}"
            )
            return _date_str(from_d), _date_str(till_d), False

        # Данные есть: from = последняя дата торгов + 1 день, till = текущая дата.
        # Если last > today (битая/будущая дата в истории), игнорируем last и берём DEFAULT_FROM_DATE.
        last = self._last_tradedate(existing)
        till_d = today
        if not last or last > till_d:
            from_d = DEFAULT_FROM_DATE
            if last and last > till_d:
                logger.info(
                    f"[TRADING HISTORY] {secid}: последняя дата в истории {_date_str(last)} > "
                    f"сегодня {_date_str(till_d)}, используем from={_date_str(from_d)}"
                )
        else:
            from_d = last + timedelta(days=1)
        if from_d > till_d:
            logger.info(
                f"[TRADING HISTORY] Нет новых данных для {secid}: "
                f"последняя дата {_date_str(last)}, till={_date_str(till_d)}"
            )
            return _date_str(from_d), _date_str(till_d), True
        logger.info(
            f"[TRADING HISTORY] Дозапись {secid}: "
            f"from={_date_str(from_d)}, till={_date_str(till_d)}"
        )
        return _date_str(from_d), _date_str(till_d), True

    def _build_moex_url(
        self, secid: str, from_: str, till: str, start: int
    ) -> str:
        """Формирует URL запроса к API истории торгов Мосбиржи.
        
        Создает URL для загрузки истории торгов по облигации с параметрами пагинации.
        
        Args:
            secid: Идентификатор облигации (SECID) для запроса истории.
            from_: Начальная дата диапазона в формате YYYY-MM-DD.
            till: Конечная дата диапазона в формате YYYY-MM-DD.
            start: Смещение для пагинации (номер первой записи для загрузки).
        
        Returns:
            Полный URL с параметрами запроса для загрузки истории торгов.
        """
        base = MOEX_HISTORY_URL.format(secid=secid)
        params = {"from": from_, "till": till, "start": start}
        return f"{base}?{urlencode(params)}"

    def _fetch_moex_page(
        self, secid: str, from_: str, till: str, start: int
    ) -> Dict[str, Any]:
        """Выполняет один запрос к API истории торгов Мосбиржи.
        
        Выполняет HTTP GET запрос к API Мосбиржи для получения одной страницы
        истории торгов по облигации с указанными параметрами пагинации.
        
        Args:
            secid: Идентификатор облигации (SECID) для запроса истории.
            from_: Начальная дата диапазона в формате YYYY-MM-DD.
            till: Конечная дата диапазона в формате YYYY-MM-DD.
            start: Смещение для пагинации (номер первой записи для загрузки).
        
        Returns:
            Словарь с ответом API Мосбиржи в формате JSON, содержащий секции
            history и history.cursor.
        
        Raises:
            URLError: Если не удалось выполнить HTTP запрос (сетевая ошибка, таймаут).
            orjson.JSONDecodeError: Если ответ не является валидным JSON.
        """
        url = self._build_moex_url(secid, from_, till, start)
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
        return orjson.loads(raw)

    def _parse_history_response(
        self, payload: Dict[str, Any]
    ) -> Tuple[List[str], List[List[Any]], int, int, int]:
        """Извлекает данные истории торгов из ответа API Мосбиржи.
        
        Парсит ответ API Мосбиржи и извлекает данные из секций history (columns, data)
        и history.cursor (INDEX, TOTAL, PAGESIZE) для управления пагинацией.
        
        Args:
            payload: Словарь с ответом API Мосбиржи в формате JSON.
        
        Returns:
            Кортеж из пяти элементов:
            - columns: Список названий колонок таблицы истории
            - data: Список списков с данными строк истории торгов
            - index: Текущий индекс пагинации (INDEX из cursor)
            - total: Общее количество записей (TOTAL из cursor)
            - pagesize: Размер страницы (PAGESIZE из cursor)
            Если секция cursor отсутствует или некорректна, возвращает (columns, data, 0, 0, 0).
        """
        hist = payload.get("history") or {}
        cols = list(hist.get("columns") or [])
        data = list(hist.get("data") or [])

        cur = payload.get("history.cursor") or {}
        cur_data = (cur.get("data") or [[]])[0]
        cur_cols = cur.get("columns") or []
        try:
            idx_i = cur_cols.index("INDEX")
            idx_t = cur_cols.index("TOTAL")
            idx_p = cur_cols.index("PAGESIZE")
        except ValueError:
            index, total, pagesize = 0, 0, 0
        else:
            index = int(cur_data[idx_i]) if len(cur_data) > idx_i else 0
            total = int(cur_data[idx_t]) if len(cur_data) > idx_t else 0
            pagesize = int(cur_data[idx_p]) if len(cur_data) > idx_p else 0

        return cols, data, index, total, pagesize

    def _merge_and_sort(
        self,
        existing_columns: List[str],
        existing_data: List[List[Any]],
        new_columns: List[str],
        new_data: List[List[Any]],
    ) -> Tuple[List[str], List[List[Any]]]:
        """Объединяет старую и новую историю торгов, убирает дубликаты и сортирует.
        
        Объединяет существующие и новые данные истории торгов по дате торгов (TRADEDATE),
        удаляет дубликаты (по TRADEDATE) и сортирует результат по дате торгов.
        
        Args:
            existing_columns: Список названий колонок существующей истории.
            existing_data: Список списков с данными существующей истории.
            new_columns: Список названий колонок новой истории.
            new_data: Список списков с данными новой истории.
        
        Returns:
            Кортеж из двух элементов:
            - columns: Список названий колонок (из existing_columns)
            - merged_data: Отсортированный список списков с объединенными данными
              без дубликатов по TRADEDATE
            Если колонка TRADEDATE отсутствует, возвращает объединенные данные без сортировки.
        """
        try:
            idx = existing_columns.index("TRADEDATE")
        except ValueError:
            return existing_columns, existing_data + new_data

        seen: set = set()
        out: List[List[Any]] = []
        for row in existing_data + new_data:
            if len(row) <= idx:
                out.append(row)
                continue
            key = row[idx]
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        out.sort(key=lambda r: (r[idx] if len(r) > idx else ""))
        return existing_columns, out

    def download_history(self, secid: str) -> Dict[str, Any]:
        """
        Скачивает историю торгов по облигации, объединяет с имеющейся и сохраняет.
        Возвращает summary: { "secid", "downloaded", "total_records", "appended" }.
        """
        logger = get_data_update_logger()
        secid = str(secid).strip()
        if not secid:
            raise ValueError("secid не задан")

        from_str, till_str, is_append = self.get_from_till(secid)
        all_history = self.load_history_file()
        existing = all_history.get(secid) or {}
        existing_cols = existing.get("columns") or []
        existing_data = list(existing.get("data") or [])

        # Проверка «нет новых данных»
        from_d = _parse_date(from_str)
        till_d = _parse_date(till_str)
        if from_d and till_d and from_d > till_d:
            url = self._build_moex_url(secid, from_str, till_str, 0)
            print(
                f"[TRADING HISTORY] URL (пропуск, нет новых данных): {url}",
                file=sys.stderr,
                flush=True,
            )
            return {
                "secid": secid,
                "downloaded": 0,
                "total_records": len(existing_data),
                "appended": is_append,
            }

        n = 0
        all_new_rows: List[List[Any]] = []
        columns: List[str] = []

        while True:
            logger.info(
                f"[TRADING HISTORY] Запрос {secid} from={from_str} till={till_str} start={n}"
            )
            url = self._build_moex_url(secid, from_str, till_str, n)
            print(f"[TRADING HISTORY] URL: {url}", file=sys.stderr, flush=True)
            try:
                payload = self._fetch_moex_page(secid, from_str, till_str, n)
            except URLError as e:
                logger.error(f"[TRADING HISTORY] Ошибка запроса MOEX: {e}")
                raise RuntimeError(f"Ошибка запроса к MOEX: {e}") from e
            except orjson.JSONDecodeError as e:
                logger.error(f"[TRADING HISTORY] Ошибка разбора JSON: {e}")
                raise RuntimeError("Некорректный ответ MOEX") from e

            cols, data, index, total, pagesize = self._parse_history_response(
                payload
            )
            if cols:
                columns = cols
            all_new_rows.extend(data)

            if total == 0 or pagesize == 0:
                break
            n = n + pagesize
            if n >= total:
                break

        if is_append and existing_cols and all_new_rows:
            columns, merged = self._merge_and_sort(
                existing_cols, existing_data, columns, all_new_rows
            )
        elif is_append and existing_cols:
            merged = existing_data
            columns = existing_cols
        else:
            merged = all_new_rows
            if not columns and all_new_rows:
                raise RuntimeError(
                    "MOEX не вернул columns для history; невозможно сохранить."
                )

        # В файл пишем только history: columns + data (без metadata, cursor и т.п.)
        record = {"columns": columns, "data": merged}
        all_history[secid] = record
        self.save_history_file(all_history)
        logger.info(
            f"[TRADING HISTORY] Сохранено {secid}: записей {len(merged)}, "
            f"загружено в этом запуске {len(all_new_rows)}"
        )

        return {
            "secid": secid,
            "downloaded": len(all_new_rows),
            "total_records": len(merged),
            "appended": is_append,
        }

    def download_history_all(self) -> Dict[str, Any]:
        """Загружает историю торгов по всем облигациям из bonds.json.
        
        Выполняет массовую загрузку истории торгов для всех облигаций из файла bonds.json.
        Список SECID извлекается из секции securities.data. Для каждой облигации выполняется
        инкрементальная загрузка (при отсутствии данных стартует с DEFAULT_FROM_DATE).
        
        Returns:
            Словарь с результатом массовой загрузки, содержащий:
            - updated: Количество успешно обновленных облигаций
            - failed: Количество облигаций с ошибками при загрузке
            - total: Общее количество облигаций для обработки
            - errors: Список словарей с ошибками, каждый содержит:
              - secid: Идентификатор облигации с ошибкой
              - error: Сообщение об ошибке
        
        Note:
            Ошибки при загрузке отдельных облигаций не прерывают процесс.
            Все ошибки собираются и возвращаются в списке errors.
        """
        logger = get_data_update_logger()
        secids = self._load_all_secids()
        total = len(secids)
        updated = 0
        failed = 0
        errors: List[Dict[str, str]] = []

        def _log(msg: str) -> None:
            print(msg, file=sys.stderr, flush=True)

        _log(f"[TRADING HISTORY] Старт: обновление истории торгов по {total} облигациям")

        for i, secid in enumerate(secids, 1):
            try:
                self.download_history(secid)
                updated += 1
                _log(f"[TRADING HISTORY] [{i}/{total}] {secid} — OK")
            except (ValueError, RuntimeError) as e:
                failed += 1
                err_msg = str(e)
                errors.append({"secid": secid, "error": err_msg})
                logger.warning(f"[TRADING HISTORY] Ошибка для {secid}: {e}")
                _log(f"[TRADING HISTORY] [{i}/{total}] {secid} — ОШИБКА: {err_msg}")

        summary = (
            f"[TRADING HISTORY] Готово: обновлено {updated}, ошибок {failed}, всего {total}"
        )
        _log(summary)
        logger.info(summary)

        return {
            "updated": updated,
            "failed": failed,
            "total": total,
            "errors": errors,
        }


_trading_history_service: Optional[TradingHistoryService] = None


def init_trading_history_service(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр сервиса истории торгов.
    
    Создает глобальный экземпляр TradingHistoryService с указанной директорией данных.
    Должен быть вызван перед использованием get_trading_history_service().
    
    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _trading_history_service
    _trading_history_service = TradingHistoryService(Path(data_dir))


def get_trading_history_service() -> TradingHistoryService:
    """Получает singleton экземпляр сервиса истории торгов.
    
    Returns:
        Экземпляр TradingHistoryService для работы с историей торгов по облигациям.
    
    Raises:
        RuntimeError: Если сервис не был инициализирован через init_trading_history_service().
    """
    if _trading_history_service is None:
        raise RuntimeError(
            "TradingHistoryService не инициализирован. "
            "Вызовите init_trading_history_service при старте приложения."
        )
    return _trading_history_service
