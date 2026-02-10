"""Сервис для работы с данными индикатора RUONIA от ЦБ РФ.

Этот модуль содержит класс RuoniaService для инкрементальной загрузки данных
индикатора RUONIA из API ЦБ РФ, преобразования в модель DBruonia и сохранения
в БД через RuoniaRepository. Данные отдаются на фронтенд из БД без промежуточных файлов.
"""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from urllib.parse import urlencode

from app.models import DBruonia, RuoniaDataResponse, RuoniaDTO
from app.repository.db.ruonia_repository import RuoniaRepository
from app.utils.logger import get_data_update_logger
from config.paths import DB_PATH


def _db_to_dto(row: Any) -> RuoniaDTO:
    """Преобразует запись БД (DBruonia или Row) в DTO для фронтенда (RuoniaDTO)."""
    # SQLAlchemy может вернуть Row с одной колонкой — сущностью; извлекаем её
    obj = row[0] if hasattr(row, "__getitem__") and hasattr(row, "__len__") and len(row) == 1 else row
    dt_val = getattr(obj, "dt", None)
    return RuoniaDTO(
        date_stavki=dt_val.isoformat() if dt_val else "",
        stavka_ruonia=getattr(obj, "ruo", None),
        volume_ruonia=getattr(obj, "vol", None),
        count_deals=getattr(obj, "T", None),
        min_rate=getattr(obj, "MinRate", None),
        percentile_25=getattr(obj, "Percentile25", None),
        percentile_75=getattr(obj, "Percentile75", None),
        max_rate=getattr(obj, "MaxRate", None),
    )


def _row_dict_to_db_ruonia(date_str: str, row_data: Dict[str, Any]) -> Optional[DBruonia]:
    """Преобразует одну запись из парсера Excel в модель DBruonia.

    Args:
        date_str: Дата в формате YYYY-MM-DD (ключ из словаря парсера).
        row_data: Словарь строки из Excel (ruo, vol, T, C, MinRate, Percentile25,
            Percentile75, MaxRate, StatusXML, DateUpdate).

    Returns:
        Объект DBruonia или None, если дату не удалось распарсить.
    """
    try:
        if "T" in date_str:
            dt_val = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        else:
            dt_val = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return DBruonia(
        dt=dt_val,
        ruo=row_data.get("ruo") if isinstance(row_data.get("ruo"), (int, float)) else None,
        vol=row_data.get("vol") if isinstance(row_data.get("vol"), (int, float)) else None,
        T=row_data.get("T") if isinstance(row_data.get("T"), (int, float)) else None,
        C=row_data.get("C") if isinstance(row_data.get("C"), (int, float)) else None,
        MinRate=row_data.get("MinRate") if isinstance(row_data.get("MinRate"), (int, float)) else None,
        Percentile25=row_data.get("Percentile25") if isinstance(row_data.get("Percentile25"), (int, float)) else None,
        Percentile75=row_data.get("Percentile75") if isinstance(row_data.get("Percentile75"), (int, float)) else None,
        MaxRate=row_data.get("MaxRate") if isinstance(row_data.get("MaxRate"), (int, float)) else None,
        StatusXML=row_data.get("StatusXML") if isinstance(row_data.get("StatusXML"), (int, float)) else None,
        DateUpdate=str(row_data["DateUpdate"]) if row_data.get("DateUpdate") is not None else None,
    )


class RuoniaService:
    """Сервис для инкрементальной загрузки и хранения данных RUONIA в БД.

    Загружает данные из Excel API ЦБ РФ за период (max_date + 1 день) до текущей даты,
    сохраняет в таблицу ruonia через RuoniaRepository. Чтение данных — только из БД.

    Attributes:
        CBR_RUONIA_BASE_URL: Базовый URL для загрузки Excel RUONIA из ЦБ РФ.
        DEFAULT_START_DATE: Дата по умолчанию для начала загрузки (11.01.2010).
        data_dir: Путь к директории данных (оставлен для совместимости, не используется).
        logger: Логгер для записи событий и ошибок.
    """

    CBR_RUONIA_BASE_URL: str = "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/14315"
    """Базовый URL для загрузки Excel файла RUONIA из ЦБ РФ."""

    DEFAULT_START_DATE: date = date(2010, 1, 11)
    """Дата по умолчанию для начала загрузки (11.01.2010)."""

    def __init__(self, data_dir: Path) -> None:
        """Инициализирует сервис RUONIA с репозиторием БД.

        Args:
            data_dir: Путь к директории данных (сохраняется для совместимости
                с init_ruonia_service; хранение данных — в БД).
        """
        self.data_dir = data_dir
        self._repo = RuoniaRepository(db_path=DB_PATH)
        self.logger = get_data_update_logger()

    def _format_date_for_url(self, date_obj: date, format_type: str = "ddmmyyyy") -> str:
        """Форматирует дату для параметров URL API ЦБ РФ.

        Args:
            date_obj: Объект date для форматирования.
            format_type: "ddmmyyyy" (DD.MM.YYYY) или "mmddyyyy" (MM/DD/YYYY).

        Returns:
            Строка с датой в указанном формате.

        Raises:
            ValueError: Если указан неизвестный format_type.
        """
        if format_type == "ddmmyyyy":
            return date_obj.strftime("%d.%m.%Y")
        if format_type == "mmddyyyy":
            return date_obj.strftime("%m/%d/%Y")
        raise ValueError(f"Unknown format_type: {format_type}")

    def _build_download_url(self, from_date: date, to_date: date) -> str:
        """Формирует URL для загрузки Excel RUONIA за диапазон дат.

        Args:
            from_date: Начальная дата диапазона.
            to_date: Конечная дата диапазона.

        Returns:
            Полный URL с параметрами запроса.
        """
        params = {
            "Posted": "True",
            "From": self._format_date_for_url(from_date, "ddmmyyyy"),
            "To": self._format_date_for_url(to_date, "ddmmyyyy"),
            "FromDate": self._format_date_for_url(from_date, "mmddyyyy"),
            "ToDate": self._format_date_for_url(to_date, "mmddyyyy"),
            "backUrl": "/hd_base/ruonia/dynamics/?UniDbQuery.Posted=True",
        }
        url = self.CBR_RUONIA_BASE_URL + "?" + urlencode(params)
        self.logger.info("[RUONIA SERVICE] Built download URL: %s", url)
        return url

    def _download_excel_file(self, url: str) -> Path:
        """Загружает Excel по URL и сохраняет во временный файл.

        Args:
            url: URL для загрузки Excel RUONIA.

        Returns:
            Путь к временному файлу.

        Raises:
            RuntimeError: При ошибке загрузки или записи файла.
        """
        self.logger.info("[RUONIA SERVICE] Downloading Excel from: %s", url)
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=60,
            )
            response.raise_for_status()
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            temp_path = Path(temp_file.name)
            temp_file.write(response.content)
            temp_file.close()
            self.logger.info("[RUONIA SERVICE] Excel saved to temp file: %s", temp_path)
            return temp_path
        except requests.RequestException as exc:
            self.logger.error("[RUONIA SERVICE] Download failed: %s", exc)
            raise RuntimeError(f"Failed to download RUONIA Excel from CBR: {exc}") from exc
        except Exception as exc:
            self.logger.error("[RUONIA SERVICE] Unexpected error during download: %s", exc)
            raise RuntimeError(f"Failed to download RUONIA Excel: {exc}") from exc

    def _parse_excel_file(self, excel_path: Path) -> Dict[str, Dict[str, Any]]:
        """Парсит Excel и возвращает словарь {date_iso: row_dict}.

        NaN преобразуются в None. Временный файл удаляется в finally.

        Args:
            excel_path: Путь к Excel файлу.

        Returns:
            Словарь с ключом YYYY-MM-DD и значением — словарь полей строки.

        Raises:
            RuntimeError: При ошибке парсинга.
            ValueError: Если колонка DT отсутствует.
        """
        self.logger.info("[RUONIA SERVICE] Parsing Excel: %s", excel_path)
        try:
            df = pd.read_excel(excel_path, engine="openpyxl")
            self.logger.info("[RUONIA SERVICE] Excel loaded, rows: %s, columns: %s", len(df), df.columns.tolist())
            if "DT" not in df.columns:
                raise ValueError("Column 'DT' not found in Excel file")
            result: Dict[str, Dict[str, Any]] = {}
            for _, row in df.iterrows():
                dt_value = row["DT"]
                if pd.isna(dt_value):
                    continue
                if isinstance(dt_value, datetime):
                    date_str = dt_value.date().isoformat()
                elif isinstance(dt_value, date):
                    date_str = dt_value.isoformat()
                elif isinstance(dt_value, pd.Timestamp):
                    date_str = dt_value.date().isoformat()
                else:
                    try:
                        date_str = pd.to_datetime(dt_value).date().isoformat()
                    except (ValueError, TypeError):
                        self.logger.warning("[RUONIA SERVICE] Skip unparseable date: %s", dt_value)
                        continue
                row_dict: Dict[str, Any] = {}
                for col in df.columns:
                    value = row[col]
                    if pd.isna(value):
                        row_dict[col] = None
                    elif isinstance(value, (datetime, pd.Timestamp)):
                        row_dict[col] = value.isoformat()
                    elif isinstance(value, date):
                        row_dict[col] = value.isoformat()
                    elif isinstance(value, (int, float)):
                        row_dict[col] = value
                    else:
                        row_dict[col] = str(value)
                result[date_str] = row_dict
            self.logger.info("[RUONIA SERVICE] Parsed %s entries from Excel", len(result))
            return result
        except Exception as exc:
            self.logger.error("[RUONIA SERVICE] Parse failed: %s", exc)
            raise RuntimeError(f"Failed to parse RUONIA Excel: {exc}") from exc
        finally:
            try:
                if excel_path.exists():
                    excel_path.unlink()
                    self.logger.info("[RUONIA SERVICE] Temp file deleted: %s", excel_path)
            except Exception as exc:
                self.logger.warning("[RUONIA SERVICE] Could not delete temp file: %s", exc)

    def update_ruonia_data(self) -> Dict[str, Any]:
        """Обновляет данные RUONIA инкрементально: загружает из API и сохраняет в БД.

        Берёт максимальную дату из таблицы ruonia через репозиторий; если таблица пуста —
        использует DEFAULT_START_DATE. Запрашивает данные за период (max_date + 1 день)
        до текущей даты, парсит Excel, преобразует в DBruonia и сохраняет через репозиторий.

        Returns:
            Словарь с полями: status ("ok" | "error"), message, from_date, to_date,
            new_entries, updated_entries, total_entries, entries_count, error, updated.
        """
        self.logger.info("[RUONIA SERVICE] Starting RUONIA data update")
        try:
            max_date = self._repo.get_max_date()
            if max_date is not None:
                from_date = max_date + timedelta(days=1)
                self.logger.info("[RUONIA SERVICE] Using range from DB max date: %s", from_date.isoformat())
            else:
                from_date = self.DEFAULT_START_DATE
                self.logger.info("[RUONIA SERVICE] Table empty, using default start date: %s", from_date.isoformat())
            to_date = date.today()
            self.logger.info("[RUONIA SERVICE] End date: %s", to_date.isoformat())
            if from_date > to_date:
                self.logger.info("[RUONIA SERVICE] No new data to download")
                return {
                    "status": "ok",
                    "message": "No new data to download",
                    "entries_count": self._repo.get_count(),
                    "updated": False,
                }
            download_url = self._build_download_url(from_date, to_date)
            excel_path = self._download_excel_file(download_url)
            new_data = self._parse_excel_file(excel_path)
            records: List[DBruonia] = []
            for date_str, row_data in new_data.items():
                model = _row_dict_to_db_ruonia(date_str, row_data)
                if model is not None:
                    records.append(model)
            if not records:
                return {
                    "status": "ok",
                    "message": "No new records to save",
                    "entries_count": self._repo.get_count(),
                    "updated": False,
                }
            ok = self._repo.save_many(records)
            if not ok:
                return {"status": "error", "error": "Repository save_many failed", "updated": False}
            existing_before = self._repo.get_max_date()
            new_count = len(records)
            updated_count = 0
            if existing_before is not None and from_date <= existing_before:
                updated_count = min(len(records), 1)
            total_count = self._repo.get_count()
            self.logger.info(
                "[RUONIA SERVICE] Update completed: %s new, total %s",
                new_count,
                total_count,
            )
            return {
                "status": "ok",
                "message": "RUONIA data updated successfully",
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat(),
                "new_entries": new_count,
                "updated_entries": updated_count,
                "total_entries": total_count,
                "updated": True,
            }
        except Exception as exc:
            self.logger.error("[RUONIA SERVICE] Update failed: %s", exc)
            return {"status": "error", "error": str(exc), "updated": False}

    def get_ruonia_data(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> RuoniaDataResponse:
        """Возвращает данные RUONIA из БД по диапазону дат в формате DTO для фронтенда.

        Параметры date_from и date_to в формате DD.MM.YYYY. Если не переданы —
        фильтр по соответствующей границе не применяется.

        Args:
            date_from: Начальная дата диапазона (DD.MM.YYYY) или None.
            date_to: Конечная дата диапазона (DD.MM.YYYY) или None.

        Returns:
            RuoniaDataResponse с полями data (список RuoniaDTO), count, date_from, date_to.
        """
        from_d: Optional[date] = None
        to_d: Optional[date] = None
        if date_from:
            try:
                from_d = datetime.strptime(date_from, "%d.%m.%Y").date()
            except ValueError:
                from_d = None
        if date_to:
            try:
                to_d = datetime.strptime(date_to, "%d.%m.%Y").date()
            except ValueError:
                to_d = None
        rows = self._repo.get_by_date_range(date_from=from_d, date_to=to_d)
        dto_list = [_db_to_dto(r) for r in rows]
        return RuoniaDataResponse(
            data=dto_list,
            count=len(dto_list),
            date_from=date_from,
            date_to=date_to,
        )

    def export_markdown(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> str:
        """Формирует Markdown-таблицу с данными RUONIA за указанный диапазон дат.

        Использует get_ruonia_data для выборки; если записей нет, возвращает пустую таблицу
        с заголовком.

        Args:
            date_from: Начальная дата (DD.MM.YYYY) или None.
            date_to: Конечная дата (DD.MM.YYYY) или None.

        Returns:
            Строка с Markdown (заголовок и таблица).
        """
        response = self.get_ruonia_data(date_from=date_from, date_to=date_to)
        header_cols = [
            "Дата ставки",
            "Ставка RUONIA, % годовых",
            "Объем сделок RUONIA, млрд руб.",
            "Количество сделок, ед.",
            "Минимальная процентная ставка, % годовых",
            "25-й процентиль по процентным ставкам, % годовых",
            "75-й процентиль по процентным ставкам, % годовых",
            "Максимальная процентная ставка, % годовых",
        ]
        lines = ["# Ставка RUONIA", ""]
        lines.append("| " + " | ".join(header_cols) + " |")
        lines.append("| " + " | ".join(["---"] * len(header_cols)) + " |")
        for dto in response.data:
            row = dto.model_dump(by_alias=True)
            row_values = []
            for k in header_cols:
                v = row.get(k)
                if v is None:
                    row_values.append("")
                elif isinstance(v, (int, float)):
                    row_values.append(f"{v:.4f}")
                else:
                    row_values.append(str(v))
            lines.append("| " + " | ".join(row_values) + " |")
        lines.append("")
        return "\n".join(lines)


_ruonia_service: Optional[RuoniaService] = None


def init_ruonia_service(data_dir: Path) -> None:
    """Инициализирует глобальный экземпляр RuoniaService.

    Должен быть вызван перед использованием get_ruonia_service().

    Args:
        data_dir: Путь к директории данных (для совместимости; данные хранятся в БД).
    """
    global _ruonia_service
    _ruonia_service = RuoniaService(data_dir)


def get_ruonia_service() -> RuoniaService:
    """Возвращает глобальный экземпляр RuoniaService.

    Returns:
        Экземпляр RuoniaService.

    Raises:
        RuntimeError: Если сервис не инициализирован (init_ruonia_service не вызван).
    """
    if _ruonia_service is None:
        raise RuntimeError("RUONIA service not initialized")
    return _ruonia_service
