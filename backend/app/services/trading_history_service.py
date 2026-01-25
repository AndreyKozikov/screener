"""
Сервис скачивания истории торгов по облигациям с API Мосбиржи.
Данные сохраняются в bonds_trading_history.json (ключ — secid).
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


MOEX_HISTORY_URL = (
    "https://iss.moex.com/iss/history/engines/stock/markets/bonds"
    "/securities/{secid}.json"
)
HISTORY_FILENAME = "bonds_trading_history.json"
DEFAULT_FROM_DATE = date(2000, 1, 1)  # дата начала загрузки при отсутствии файла или данных по облигации


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s or s == "0000-00-00":
        return None
    try:
        return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


class TradingHistoryService:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def _history_path(self) -> Path:
        return self.data_dir / HISTORY_FILENAME

    def _load_all_secids(self) -> List[str]:
        """Загружает из bonds.json все SECID облигаций (из securities.data)."""
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
        """
        Читает bonds_trading_history.json.
        По каждому secid хранится только секция history: columns (заголовки), data (данные).
        Формат: { secid: { "columns": [...], "data": [[...], ...] } }.
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
        """
        Сохраняет в bonds_trading_history.json только данные из секции history:
        columns — заголовки таблицы, data — строки. Ни metadata, ни cursor не сохраняются.
        """
        path = self._history_path()
        raw = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        path.write_bytes(raw)

    def _last_tradedate(self, history: Dict[str, Any]) -> Optional[date]:
        """Последняя дата торгов в истории (максимальная TRADEDATE)."""
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
        """
        Определяет from, till и признак «дописываем».
        Возвращает (from_YYYY_MM_DD, till_YYYY_MM_DD, is_append).
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
        """Формирует URL запроса к MOEX history API."""
        base = MOEX_HISTORY_URL.format(secid=secid)
        params = {"from": from_, "till": till, "start": start}
        return f"{base}?{urlencode(params)}"

    def _fetch_moex_page(
        self, secid: str, from_: str, till: str, start: int
    ) -> Dict[str, Any]:
        """Один запрос к MOEX history API."""
        url = self._build_moex_url(secid, from_, till, start)
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=60) as resp:
            raw = resp.read()
        return orjson.loads(raw)

    def _parse_history_response(
        self, payload: Dict[str, Any]
    ) -> Tuple[List[str], List[List[Any]], int, int, int]:
        """
        Из ответа MOEX извлекает history (columns, data) и history.cursor
        (INDEX, TOTAL, PAGESIZE).
        Возвращает (columns, data, index, total, pagesize).
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
        """Объединяет старую и новую историю по TRADEDATE, убирает дубликаты, сортирует."""
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
        """
        Скачивает историю торгов по всем облигациям из bonds.json.
        Список secid берётся из файла. При отсутствии файла или данных
        по облигации стартуем с DEFAULT_FROM_DATE (2000-01-01).
        Возвращает: updated, failed, total, errors.
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
    global _trading_history_service
    _trading_history_service = TradingHistoryService(Path(data_dir))


def get_trading_history_service() -> TradingHistoryService:
    if _trading_history_service is None:
        raise RuntimeError(
            "TradingHistoryService не инициализирован. "
            "Вызовите init_trading_history_service при старте приложения."
        )
    return _trading_history_service
