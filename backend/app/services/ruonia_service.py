"""Сервис для работы с данными индикатора RUONIA от ЦБ РФ.

Этот модуль содержит класс RuoniaService для загрузки данных индикатора RUONIA
(индикатор однодневной ставки межбанковского кредитования) из ЦБ РФ. Данные
загружаются из Excel файла, парсятся и сохраняются в JSON файл.
"""

import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
from urllib.parse import urlencode
import requests

import orjson
import pandas as pd

from app.utils.logger import get_data_update_logger


class RuoniaService:
    """Сервис для работы с данными индикатора RUONIA от ЦБ РФ.
    
    Класс обеспечивает загрузку данных индикатора RUONIA из Excel файла ЦБ РФ,
    парсинг данных с помощью pandas и сохранение в JSON файл. Поддерживает
    инкрементальное обновление данных (загрузка только новых записей с последней даты).
    
    Attributes:
        CBR_RUONIA_BASE_URL: Базовый URL для загрузки Excel файла RUONIA из ЦБ РФ.
        DEFAULT_START_DATE: Дата по умолчанию для начала загрузки данных
            (11.01.2010 - дата начала публикации RUONIA).
        data_dir: Путь к директории с данными.
        ruonia_file: Путь к файлу для хранения данных RUONIA.
        logger: Логгер для записи событий и ошибок.
    """
    
    CBR_RUONIA_BASE_URL: str = "https://www.cbr.ru/Queries/UniDbQuery/DownloadExcel/14315"
    """Базовый URL для загрузки Excel файла RUONIA из ЦБ РФ."""
    
    DEFAULT_START_DATE: date = date(2010, 1, 11)
    """Дата по умолчанию для начала загрузки данных (11.01.2010)."""
    
    def __init__(self, data_dir: Path):
        """Инициализирует сервис для работы с индикатором RUONIA.
        
        Args:
            data_dir: Путь к директории с данными, где будет храниться JSON файл.
        """
        self.data_dir = data_dir
        self.ruonia_file = data_dir / "ruonia.json"
        self.logger = get_data_update_logger()
    
    def _load_ruonia_data(self) -> Dict[str, Dict[str, Any]]:
        """Загружает данные RUONIA из JSON файла.
        
        Загружает данные из файла ruonia.json. Обрабатывает ошибки чтения
        и поврежденные файлы.
        
        Returns:
            Словарь с данными RUONIA, где ключ - дата в формате YYYY-MM-DD,
            значение - словарь с данными строки из Excel файла (все колонки).
            Если файл не существует или поврежден, возвращает пустой словарь
            и создает новый файл.
        """
        self.logger.info(f"[RUONIA SERVICE] Loading RUONIA data from file: {self.ruonia_file}")
        
        if not self.ruonia_file.exists():
            self.logger.info("[RUONIA SERVICE] File does not exist, creating empty file")
            empty_data: Dict[str, Dict[str, Any]] = {}
            self._save_ruonia_data(empty_data)
            return empty_data
        
        try:
            file_size = self.ruonia_file.stat().st_size
            self.logger.info(f"[RUONIA SERVICE] File exists, size: {file_size} bytes")
            
            with open(self.ruonia_file, 'rb') as f:
                data = orjson.loads(f.read())
            
            if not isinstance(data, dict):
                self.logger.warning("[RUONIA SERVICE] Data is not a dictionary, initializing empty dict")
                empty_data: Dict[str, Dict[str, Any]] = {}
                self._save_ruonia_data(empty_data)
                return empty_data
            
            entries_count = len(data)
            self.logger.info(f"[RUONIA SERVICE] Successfully loaded {entries_count} RUONIA entries from file")
            return data
            
        except (orjson.JSONDecodeError, IOError) as exc:
            self.logger.error(f"[RUONIA SERVICE] ERROR: Failed to load file - {type(exc).__name__}: {str(exc)}")
            self.logger.info("[RUONIA SERVICE] Creating fresh empty file")
            empty_data: Dict[str, Dict[str, Any]] = {}
            self._save_ruonia_data(empty_data)
            return empty_data
    
    def _save_ruonia_data(self, data: Dict[str, Dict[str, Any]]) -> None:
        """Сохраняет данные RUONIA в JSON файл.
        
        Записывает данные в файл ruonia.json с форматированием (отступы и перенос строки).
        Создает директорию для файла при необходимости.
        
        Args:
            data: Словарь с данными RUONIA, где ключ - дата в формате YYYY-MM-DD,
                значение - словарь с данными строки из Excel файла.
        """
        entries_count = len(data)
        self.logger.info(f"[RUONIA SERVICE] Saving {entries_count} RUONIA entries to file: {self.ruonia_file}")
        
        serialized = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE,
        )
        
        file_size = len(serialized)
        self.ruonia_file.write_bytes(serialized)
        self.logger.info(f"[RUONIA SERVICE] File saved successfully, size: {file_size} bytes")
    
    def _get_last_date_from_data(self, ruonia_data: Dict[str, Dict[str, Any]]) -> Optional[date]:
        """Получает последнюю (наиболее свежую) дату из существующих данных RUONIA.
        
        Находит максимальную дату среди всех записей в словаре данных. Используется
        для определения начальной даты при инкрементальном обновлении.
        
        Args:
            ruonia_data: Словарь с данными RUONIA, где ключи - даты в формате YYYY-MM-DD.
        
        Returns:
            Объект date с последней датой из данных или None, если данных нет
            или все даты некорректны.
        """
        if not ruonia_data:
            return None
        
        dates = []
        for date_str in ruonia_data.keys():
            try:
                parsed_date = datetime.fromisoformat(date_str).date()
                dates.append(parsed_date)
            except (ValueError, TypeError):
                continue
        
        if not dates:
            return None
        
        last_date = max(dates)
        self.logger.info(f"[RUONIA SERVICE] Last date in existing data: {last_date.isoformat()}")
        return last_date
    
    def _format_date_for_url(self, date_obj: date, format_type: str = "ddmmyyyy") -> str:
        """Форматирует дату для параметров URL.
        
        Преобразует объект date в строку в формате, требуемом API ЦБ РФ для
        различных параметров запроса.
        
        Args:
            date_obj: Объект date для форматирования.
            format_type: Тип формата:
                - "ddmmyyyy": Формат DD.MM.YYYY для параметров From/To
                - "mmddyyyy": Формат MM/DD/YYYY для параметров FromDate/ToDate
        
        Returns:
            Строка с датой в указанном формате.
        
        Raises:
            ValueError: Если указан неизвестный тип формата.
        """
        if format_type == "ddmmyyyy":
            return date_obj.strftime("%d.%m.%Y")
        elif format_type == "mmddyyyy":
            return date_obj.strftime("%m/%d/%Y")
        else:
            raise ValueError(f"Unknown format_type: {format_type}")
    
    def _build_download_url(self, from_date: date, to_date: date) -> str:
        """Формирует URL для загрузки Excel файла RUONIA из ЦБ РФ.
        
        Создает URL для загрузки данных RUONIA за указанный диапазон дат.
        Параметры запроса включают даты начала и конца диапазона в различных форматах
        (DD.MM.YYYY для From/To и MM/DD/YYYY для FromDate/ToDate).
        
        Args:
            from_date: Начальная дата диапазона для загрузки данных.
            to_date: Конечная дата диапазона для загрузки данных.
        
        Returns:
            Полный URL с параметрами запроса для загрузки Excel файла RUONIA.
        """
        params = {
            "Posted": "True",
            "From": self._format_date_for_url(from_date, "ddmmyyyy"),
            "To": self._format_date_for_url(to_date, "ddmmyyyy"),
            "FromDate": self._format_date_for_url(from_date, "mmddyyyy"),
            "ToDate": self._format_date_for_url(to_date, "mmddyyyy"),
            "backUrl": "/hd_base/ruonia/dynamics/?UniDbQuery.Posted=True"
        }
        
        url = self.CBR_RUONIA_BASE_URL + "?" + urlencode(params)
        self.logger.info(f"[RUONIA SERVICE] Built download URL: {url}")
        return url
    
    def _download_excel_file(self, url: str) -> Path:
        """Загружает Excel файл по URL и сохраняет во временный файл.
        
        Выполняет HTTP запрос к указанному URL для загрузки Excel файла RUONIA
        и сохраняет его во временный файл для последующего парсинга.
        
        Args:
            url: URL для загрузки Excel файла RUONIA из ЦБ РФ.
        
        Returns:
            Путь к временному файлу с загруженным Excel файлом.
        
        Raises:
            RuntimeError: Если не удалось загрузить файл (сетевая ошибка, таймаут)
                или если произошла ошибка при сохранении файла.
        
        Note:
            Временный файл должен быть удален после использования. Удаление выполняется
            в методе _parse_excel_file() в блоке finally.
        """
        self.logger.info(f"[RUONIA SERVICE] Downloading Excel file from: {url}")
        
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=60
            )
            
            self.logger.info(f"[RUONIA SERVICE] Download response: status_code={response.status_code}")
            response.raise_for_status()
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_path = Path(temp_file.name)
            
            # Write content to temporary file
            temp_file.write(response.content)
            temp_file.close()
            
            file_size = temp_path.stat().st_size
            self.logger.info(f"[RUONIA SERVICE] Excel file saved to temporary file: {temp_path}, size: {file_size} bytes")
            
            return temp_path
            
        except requests.RequestException as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Download failed - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to download RUONIA Excel file from CBR: {exc}") from exc
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Unexpected error during download - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to download RUONIA Excel file: {exc}") from exc
    
    def _parse_excel_file(self, excel_path: Path) -> Dict[str, Dict[str, Any]]:
        """Парсит Excel файл и преобразует в словарь с DT как ключом.
        
        Загружает Excel файл с помощью pandas.read_excel, извлекает данные из колонки DT
        (дата) и преобразует каждую строку в словарь. Обрабатывает различные форматы дат
        и NaN значения.
        
        Args:
            excel_path: Путь к Excel файлу для парсинга.
        
        Returns:
            Словарь с данными RUONIA, где ключ - дата в формате YYYY-MM-DD (из колонки DT),
            значение - словарь с данными строки (все колонки из Excel файла).
            NaN значения преобразуются в None для JSON сериализации.
        
        Raises:
            RuntimeError: Если не удалось загрузить или распарсить Excel файл.
            ValueError: Если колонка DT отсутствует в Excel файле.
        
        Note:
            После парсинга временный файл автоматически удаляется в блоке finally.
        """
        self.logger.info(f"[RUONIA SERVICE] Parsing Excel file: {excel_path}")
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_path, engine='openpyxl')
            
            self.logger.info(f"[RUONIA SERVICE] Excel file loaded, rows: {len(df)}, columns: {df.columns.tolist()}")
            
            # Check if DT column exists
            if 'DT' not in df.columns:
                raise ValueError("Column 'DT' not found in Excel file")
            
            # Convert to dictionary where key is DT (date) and value is the row data
            result = {}
            
            for _, row in df.iterrows():
                dt_value = row['DT']
                
                # Handle different date formats
                if pd.isna(dt_value):
                    continue
                
                # Convert date to ISO format string
                if isinstance(dt_value, datetime):
                    date_str = dt_value.date().isoformat()
                elif isinstance(dt_value, date):
                    date_str = dt_value.isoformat()
                elif isinstance(dt_value, pd.Timestamp):
                    date_str = dt_value.date().isoformat()
                else:
                    # Try to parse as date string
                    try:
                        parsed_date = pd.to_datetime(dt_value).date()
                        date_str = parsed_date.isoformat()
                    except (ValueError, TypeError):
                        self.logger.warning(f"[RUONIA SERVICE] WARNING: Could not parse date: {dt_value}")
                        continue
                
                # Convert row to dictionary, handling NaN values
                row_dict = {}
                for col in df.columns:
                    value = row[col]
                    # Convert NaN to None for JSON serialization
                    if pd.isna(value):
                        row_dict[col] = None
                    else:
                        # Keep original type for numbers
                        if isinstance(value, (int, float)):
                            row_dict[col] = value
                        elif isinstance(value, (datetime, pd.Timestamp)):
                            row_dict[col] = value.isoformat()
                        elif isinstance(value, date):
                            row_dict[col] = value.isoformat()
                        else:
                            row_dict[col] = str(value)
                
                result[date_str] = row_dict
            
            parsed_count = len(result)
            self.logger.info(f"[RUONIA SERVICE] Successfully parsed {parsed_count} entries from Excel file")
            
            return result
            
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Failed to parse Excel file - {error_type}: {str(exc)}")
            raise RuntimeError(f"Failed to parse RUONIA Excel file: {exc}") from exc
        finally:
            # Clean up temporary file
            try:
                if excel_path.exists():
                    excel_path.unlink()
                    self.logger.info(f"[RUONIA SERVICE] Temporary file deleted: {excel_path}")
            except Exception as exc:
                self.logger.warning(f"[RUONIA SERVICE] WARNING: Could not delete temporary file: {exc}")
    
    def update_ruonia_data(self) -> Dict[str, Any]:
        """Обновляет данные RUONIA путем загрузки из ЦБ РФ и объединения с существующими данными.
        
        Выполняет инкрементальное обновление данных RUONIA. Загружает только новые данные
        с последней даты из существующего файла до текущей даты. Если файл не существует,
        использует дату по умолчанию (11.01.2010) для начала загрузки всех исторических данных.
        
        Последовательность выполнения:
            1. Проверяет существование файла данных
            2. Загружает существующие данные из JSON файла
            3. Определяет date_from (последняя дата в файле + 1 день или дата по умолчанию)
            4. Устанавливает date_to на текущую дату
            5. Загружает Excel файл из ЦБ РФ за диапазон [date_from, date_to]
            6. Парсит Excel файл и извлекает данные
            7. Объединяет новые данные с существующими (новые данные перезаписывают старые)
            8. Сохраняет обновленные данные в файл
        
        Returns:
            Словарь с результатом обновления, содержащий:
            - status: Статус операции ("ok" или "error")
            - message: Сообщение о результате обновления
            - from_date: Начальная дата диапазона загрузки (при успехе)
            - to_date: Конечная дата диапазона загрузки (при успехе)
            - new_entries: Количество новых записей (при успехе)
            - updated_entries: Количество обновленных записей (при успехе)
            - total_entries: Общее количество записей после обновления (при успехе)
            - entries_count: Общее количество записей (если нет новых данных)
            - error: Сообщение об ошибке (при ошибке)
            - updated: Флаг успешного обновления (True или False)
        
        Note:
            Если from_date > to_date (нет новых данных для загрузки), возвращается
            результат с updated=False и сообщением "No new data to download".
        """
        self.logger.info("[RUONIA SERVICE] Starting RUONIA data update")
        
        try:
            # Check if data file exists before starting
            file_exists = self.ruonia_file.exists()
            self.logger.info(f"[RUONIA SERVICE] Data file exists: {file_exists}")
            
            # Load existing data
            existing_data = self._load_ruonia_data()
            
            # Determine date range for download
            last_date = self._get_last_date_from_data(existing_data)
            
            if last_date:
                # Start from next day after last date
                from_date = last_date + timedelta(days=1)
                self.logger.info(f"[RUONIA SERVICE] Using date range from existing data: {from_date.isoformat()}")
            else:
                # File doesn't exist or is empty - start from default date 11.01.2010
                from_date = self.DEFAULT_START_DATE
                if not file_exists:
                    self.logger.info(f"[RUONIA SERVICE] Data file does not exist, using default start date: {from_date.isoformat()}")
                else:
                    self.logger.info(f"[RUONIA SERVICE] No data in file, using default start date: {from_date.isoformat()}")
            
            # End date is today
            to_date = date.today()
            self.logger.info(f"[RUONIA SERVICE] End date: {to_date.isoformat()}")
            
            # Check if we need to download anything
            if from_date > to_date:
                self.logger.info("[RUONIA SERVICE] No new data to download (from_date > to_date)")
                return {
                    'status': 'ok',
                    'message': 'No new data to download',
                    'entries_count': len(existing_data),
                    'updated': False
                }
            
            # Build download URL
            download_url = self._build_download_url(from_date, to_date)
            
            # Download Excel file
            excel_path = self._download_excel_file(download_url)
            
            # Parse Excel file
            new_data = self._parse_excel_file(excel_path)
            
            # Merge with existing data (new data overwrites existing if same date)
            updated_count = 0
            new_count = 0
            
            for date_str, row_data in new_data.items():
                if date_str in existing_data:
                    updated_count += 1
                else:
                    new_count += 1
                existing_data[date_str] = row_data
            
            # Save merged data
            self._save_ruonia_data(existing_data)
            
            total_count = len(existing_data)
            
            self.logger.info(f"[RUONIA SERVICE] Update completed: {new_count} new entries, {updated_count} updated entries, total: {total_count}")
            
            return {
                'status': 'ok',
                'message': 'RUONIA data updated successfully',
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat(),
                'new_entries': new_count,
                'updated_entries': updated_count,
                'total_entries': total_count,
                'updated': True
            }
            
        except Exception as exc:
            error_type = type(exc).__name__
            self.logger.error(f"[RUONIA SERVICE] ERROR: Failed to update RUONIA data - {error_type}: {str(exc)}")
            return {
                'status': 'error',
                'error': str(exc),
                'updated': False
            }
    
    def get_ruonia_data(self) -> Dict[str, Dict[str, Any]]:
        """Получает все данные RUONIA.
        
        Загружает все данные RUONIA из JSON файла и возвращает их в виде словаря.
        
        Returns:
            Словарь с данными RUONIA, где ключ - дата в формате YYYY-MM-DD,
            значение - словарь с данными строки из Excel файла (все колонки).
        """
        return self._load_ruonia_data()


# Singleton instance
_ruonia_service: Optional[RuoniaService] = None


def init_ruonia_service(data_dir: Path) -> None:
    """Инициализирует singleton экземпляр сервиса RUONIA.
    
    Создает глобальный экземпляр RuoniaService с указанной директорией данных.
    Должен быть вызван перед использованием get_ruonia_service().
    
    Args:
        data_dir: Путь к директории с JSON файлами данных.
    """
    global _ruonia_service
    _ruonia_service = RuoniaService(data_dir)


def get_ruonia_service() -> RuoniaService:
    """Получает singleton экземпляр сервиса RUONIA.
    
    Returns:
        Экземпляр RuoniaService для работы с данными индикатора RUONIA.
    
    Raises:
        RuntimeError: Если сервис не был инициализирован через init_ruonia_service().
    """
    if _ruonia_service is None:
        raise RuntimeError("RUONIA service not initialized")
    return _ruonia_service
