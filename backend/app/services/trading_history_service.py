"""Сервис для загрузки истории торгов по облигациям из API Мосбиржи.

Загружает историю торгов из API Московской биржи и сохраняет её в отдельную
БД history_db.db. Поддерживает многопоточную обработку облигаций:
пагинация по одной облигации — последовательно, запись в БД и обработка
следующей облигации — параллельно.
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import orjson

from app.models import TradingHistoryRecord
from app.repository.db.bonds_repository import BondsRepository
from app.repository.db.trading_history_repository import TradingHistoryRepository
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH, HISTORY_DB_PATH, MOEX_HISTORY_URL


DEFAULT_FROM_DATE: date = date(2000, 1, 1)
"""Дата начала загрузки при отсутствии данных по облигации в БД."""

def _parse_date(s: Optional[str]) -> Optional[date]:
    """Парсит строку даты в объект date.

    Args:
        s: Строка с датой в формате YYYY-MM-DD или None.

    Returns:
        Объект date или None, если строка некорректна или "0000-00-00".
    """
    if not s or s == "0000-00-00":
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _date_str(d: date) -> str:
    """Преобразует объект date в строку формата YYYY-MM-DD."""
    return d.strftime("%Y-%m-%d")


def _safe_float(val: Any) -> Optional[float]:
    """Приводит значение к float; при ошибке возвращает None."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _row_to_record(columns: List[str], row: List[Any]) -> Optional[TradingHistoryRecord]:
    """Преобразует строку ответа API (columns + row) в TradingHistoryRecord.

    Args:
        columns: Список названий колонок (как в ответе MOEX).
        row: Список значений строки.

    Returns:
        TradingHistoryRecord или None, если нет обязательных полей (secid, tradedate, boardid).
    """
    col_index: Dict[str, int] = {str(c).upper(): i for i, c in enumerate(columns)}
    n = len(row)

    def _get(name: str) -> Any:
        idx = col_index.get(name.upper())
        if idx is None or idx >= n:
            return None
        return row[idx]

    secid_raw = _get("SECID")
    tradedate_raw = _get("TRADEDATE")
    boardid_raw = _get("BOARDID")
    if not secid_raw or not tradedate_raw or not boardid_raw:
        return None
    secid = str(secid_raw).strip()[:36]
    boardid = str(boardid_raw).strip()[:12]
    tradedate = _parse_date(str(tradedate_raw) if tradedate_raw else None)
    if not tradedate:
        return None

    def _float(name: str) -> Optional[float]:
        return _safe_float(_get(name))

    def _date(name: str) -> Optional[date]:
        return _parse_date(str(_get(name)) if _get(name) is not None else None)

    return TradingHistoryRecord(
        secid=secid,
        tradedate=tradedate,
        boardid=boardid,
        numtrades=_float("NUMTRADES"),
        value=_float("VALUE"),
        legalcloseprice=_float("LEGALCLOSEPRICE"),
        accint=_float("ACCINT"),
        yieldclose=_float("YIELDCLOSE"),
        open=_float("OPEN"),
        volume=_float("VOLUME"),
        duration=_float("DURATION"),
        yieldatwap=_float("YIELDATWAP"),
        iricpiclose=_float("IRICPICLOSE"),
        couponpercent=_float("COUPONPERCENT"),
        couponvalue=_float("COUPONVALUE"),
        facevalue=_float("FACEVALUE"),
        yieldtooffer=_float("YIELDTOOFFER"),
        yieldlastcoupon=_float("YIELDLASTCOUPON"),
        calloptionyield=_float("CALLOPTIONYIELD"),
        calloptionduration=_float("CALLOPTIONDURATION"),
        zspread=_float("ZSPREAD"),
        buybackdate=_date("BUYBACKDATE"),
        lasttradedate=_date("LASTTRADEDATE"),
        putoptiondate=_date("PUTOPTIONDATE"),
        dateyieldfromissuer=_date("DATEYIELDFROMISSUER"),
        trade_session_date=_date("TRADE_SESSION_DATE"),
    )


class TradingHistoryService:
    """Сервис загрузки истории торгов из API Мосбиржи с сохранением в БД.

    Для каждой облигации загрузка всех страниц (пагинация) выполняется
    последовательно; запись в history_db и запуск обработки следующей
    облигации — параллельно (многопоточность).
    """

    def __init__(
        self,
        data_dir: Path,
        db_path: Optional[Path] = None,
        history_db_path: Optional[Path] = None,
        history_repository: Optional[TradingHistoryRepository] = None,
    ) -> None:
        """Инициализирует сервис истории торгов.

        Args:
            data_dir: Путь к директории данных (для совместимости, не используется для истории).
            db_path: Путь к bonds.db для получения списка SECID.
            history_db_path: Путь к history_db.db. Используется, если history_repository не передан.
            history_repository: Репозиторий для history_db. Если не передан, создаётся по history_db_path.
        """
        self.data_dir = Path(data_dir)
        self.db_path = Path(db_path) if db_path is not None else Path(DB_PATH)
        self._history_repo = history_repository or TradingHistoryRepository(
            db_path=history_db_path or HISTORY_DB_PATH
        )
        self._history_repo.ensure_table_exists()
        self.logger = get_data_update_logger()

    def _load_all_secids(self) -> List[str]:
        """Загружает из таблицы bonds все уникальные SECID облигаций."""
        repo = BondsRepository(db_path=self.db_path)
        return repo.get_all_secids()

    def get_from_till(self, secid: str) -> Tuple[str, str, bool]:
        """Определяет диапазон дат для загрузки истории торгов.

        Берёт последнюю дату из history_db; при отсутствии данных использует
        DEFAULT_FROM_DATE. Возвращает (from_str, till_str, is_append).
        """
        self.logger.info("[TRADING HISTORY] Определение диапазона дат для %s", secid)
        today = date.today()
        last = self._history_repo.get_last_tradedate(secid)

        if not last:
            from_d = DEFAULT_FROM_DATE
            till_d = today
            self.logger.info(
                "[TRADING HISTORY] Первая загрузка %s: from=%s (по умолчанию), till=%s",
                secid, _date_str(from_d), _date_str(till_d),
            )
            return _date_str(from_d), _date_str(till_d), False

        till_d = today
        if last > till_d:
            self.logger.info(
                "[TRADING HISTORY] %s: последняя дата в БД %s > сегодня %s, используем from=%s",
                secid, _date_str(last), _date_str(till_d), _date_str(DEFAULT_FROM_DATE),
            )
            from_d = DEFAULT_FROM_DATE
        else:
            from_d = last + timedelta(days=1)

        if from_d > till_d:
            self.logger.info(
                "[TRADING HISTORY] Нет новых данных для %s: последняя дата %s, till=%s",
                secid, _date_str(last), _date_str(till_d),
            )
            return _date_str(from_d), _date_str(till_d), True
        self.logger.info(
            "[TRADING HISTORY] Дозапись %s: from=%s, till=%s",
            secid, _date_str(from_d), _date_str(till_d),
        )
        return _date_str(from_d), _date_str(till_d), True

    def _build_moex_url(
        self, secid: str, from_: str, till: str, start: int
    ) -> str:
        """Формирует URL запроса к API истории торгов Мосбиржи."""
        base = MOEX_HISTORY_URL.format(secid=secid)
        params = {"from": from_, "till": till, "start": start}
        return f"{base}?{urlencode(params)}"

    def _fetch_moex_page(
        self, secid: str, from_: str, till: str, start: int
    ) -> Dict[str, Any]:
        """Выполняет один HTTP-запрос к API истории торгов Мосбиржи."""
        url = self._build_moex_url(secid, from_, till, start)
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
        return orjson.loads(raw)

    def _parse_history_response(
        self, payload: Dict[str, Any]
    ) -> Tuple[List[str], List[List[Any]], int, int, int]:
        """Извлекает columns, data и cursor (index, total, pagesize) из ответа API."""
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

    def download_history(self, secid: str) -> Dict[str, Any]:
        """Скачивает историю торгов по одной облигации и сохраняет в history_db.

        Пагинация выполняется последовательно; в конце — одна запись в БД.
        Возвращает summary: secid, downloaded, total_records, appended.

        Raises:
            ValueError: Если secid пустой.
            RuntimeError: При ошибке запроса или разбора ответа MOEX.
        """
        self.logger.info("[TRADING HISTORY] Старт загрузки для %s", secid)
        secid = str(secid).strip()
        if not secid:
            raise ValueError("secid не задан")

        from_str, till_str, is_append = self.get_from_till(secid)
        from_d = _parse_date(from_str)
        till_d = _parse_date(till_str)
        if from_d and till_d and from_d > till_d:
            self.logger.info(
                "[TRADING HISTORY] Пропуск %s: нет новых данных (from > till)",
                secid,
            )
            return {
                "secid": secid,
                "downloaded": 0,
                "total_records": 0,
                "appended": is_append,
            }

        n = 0
        all_new_rows: List[List[Any]] = []
        columns: List[str] = []

        while True:
            self.logger.info(
                "[TRADING HISTORY] Запрос %s from=%s till=%s start=%s",
                secid, from_str, till_str, n,
            )
            try:
                payload = self._fetch_moex_page(secid, from_str, till_str, n)
            except URLError as e:
                self.logger.error("[TRADING HISTORY] Ошибка запроса MOEX для %s: %s", secid, e)
                raise RuntimeError(f"Ошибка запроса к MOEX: {e}") from e
            except orjson.JSONDecodeError as e:
                self.logger.error("[TRADING HISTORY] Ошибка разбора JSON для %s: %s", secid, e)
                raise RuntimeError("Некорректный ответ MOEX") from e

            cols, data, index, total, pagesize = self._parse_history_response(payload)
            if cols:
                columns = cols
            all_new_rows.extend(data)

            if total == 0 or pagesize == 0:
                break
            n = n + pagesize
            if n >= total:
                break

        records: List[TradingHistoryRecord] = []
        for row in all_new_rows:
            rec = _row_to_record(columns, row)
            if rec is not None:
                records.append(rec)

        if records:
            try:
                self._history_repo.save_records(records)
            except Exception as e:
                self.logger.error(
                    "[TRADING HISTORY] Ошибка записи в БД для %s: %s",
                    secid, e, exc_info=True,
                )
                raise RuntimeError(f"Ошибка записи в БД: {e}") from e
            self.logger.info(
                "[TRADING HISTORY] Сохранено %s: записей в этом запуске %s",
                secid, len(records),
            )

        return {
            "secid": secid,
            "downloaded": len(records),
            "total_records": len(records),
            "appended": is_append,
        }

    def download_history_all(self) -> Dict[str, Any]:
        """Загружает историю торгов по всем облигациям из таблицы bonds.

        Для каждой облигации: последовательная пагинация, затем запись в БД.
        Облигации обрабатываются параллельно в пуле потоков.

        Returns:
            Словарь: updated, failed, total, errors (список {secid, error}).
        """
        secids = self._load_all_secids()
        total = len(secids)
        updated = 0
        failed = 0
        errors: List[Dict[str, str]] = []
        logger = get_data_update_logger()

        def _log(msg: str) -> None:
            print(msg, file=sys.stderr, flush=True)

        _log(f"[TRADING HISTORY] Старт: обновление истории торгов по {total} облигациям (многопоточность)")

        max_workers = min(32, 4 + (__import__("os").cpu_count() or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_secid = {executor.submit(self.download_history, sid): sid for sid in secids}
            for i, future in enumerate(as_completed(future_to_secid), 1):
                secid = future_to_secid[future]
                try:
                    future.result()
                    updated += 1
                    _log(f"[TRADING HISTORY] [{i}/{total}] {secid} — OK")
                except (ValueError, RuntimeError) as e:
                    failed += 1
                    err_msg = str(e)
                    errors.append({"secid": secid, "error": err_msg})
                    logger.warning("[TRADING HISTORY] Ошибка для %s: %s", secid, e)
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


def init_trading_history_service(
    data_dir: Path,
    db_path: Optional[Path] = None,
    history_db_path: Optional[Path] = None,
) -> None:
    """Инициализирует singleton сервиса истории торгов.

    Args:
        data_dir: Директория данных (для совместимости).
        db_path: Путь к bonds.db. По умолчанию config.paths.DB_PATH.
        history_db_path: Путь к history_db.db. По умолчанию config.paths.HISTORY_DB_PATH.
    """
    global _trading_history_service
    _trading_history_service = TradingHistoryService(
        Path(data_dir),
        db_path=db_path or DB_PATH,
        history_db_path=history_db_path or HISTORY_DB_PATH,
    )


def get_trading_history_service() -> TradingHistoryService:
    """Возвращает singleton экземпляр сервиса истории торгов.

    Raises:
        RuntimeError: Если сервис не инициализирован через init_trading_history_service().
    """
    if _trading_history_service is None:
        raise RuntimeError(
            "TradingHistoryService не инициализирован. "
            "Вызовите init_trading_history_service при старте приложения."
        )
    return _trading_history_service
