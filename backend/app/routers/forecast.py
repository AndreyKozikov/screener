"""Роутеры для работы с прогнозными данными.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с прогнозными данными. Включает endpoints для получения списка доступных дат,
данных прогноза для конкретной даты, экспорта данных в JSON и загрузки файла прогноза (.md).
После сохранения .md файл передаётся в ForecastService для парсинга и записи в БД.
"""

import json
import re
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from fastapi.responses import Response

from app.models.schemasDTO.forecast_dto import ForecastDatesResponse
from app.services.forecast_service import get_forecast_service

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _get_data_dir() -> Path:
    """Путь к директории backend/app/data."""
    return Path(__file__).resolve().parent.parent / "data"




def _get_forecast_path() -> Path:
    """Получает путь к файлу прогнозных данных.
    
    Returns:
        Путь к файлу forecast_251024.json в директории data проекта.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    json_path = project_root / "data" / "forecast_251024.json"
    return json_path


def _load_forecast_data() -> dict:
    """Загружает прогнозные данные из JSON файла.
    
    Загружает данные из файла forecast_251024.json и возвращает их в виде словаря.
    
    Returns:
        Словарь с прогнозными данными из JSON файла.
    
    Raises:
        HTTPException: Если файл не существует (статус 404) или если произошла
            ошибка при чтении файла (статус 500).
    """
    json_path = _get_forecast_path()
    
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="forecast_251024.json file not found")
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=f"Error reading forecast data: {str(e)}")


ALLOWED_FORECAST_EXTENSION = ".pdf"


@router.post("/upload")
async def upload_forecast_pdf(file: UploadFile = File(..., description="PDF file with Bank of Russia forecast (.pdf)")):
    """Загружает файл прогноза в формате PDF, конвертирует в Markdown и сохраняет данные в БД.

    Принимает только файлы с расширением .pdf. Имя файла sanitize-ится.
    """
    if not file.filename or not file.filename.lower().endswith(ALLOWED_FORECAST_EXTENSION):
        raise HTTPException(
            status_code=400,
            detail=f"Разрешён только формат PDF (.pdf). Получено: {file.filename or 'без имени'}",
        )
    safe_name = re.sub(r"[^\w.\-]", "_", file.filename)
    if not safe_name.lower().endswith(ALLOWED_FORECAST_EXTENSION):
        safe_name = safe_name.rstrip("_") + ALLOWED_FORECAST_EXTENSION
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    dest = data_dir / safe_name
    try:
        content = await file.read()
        dest.write_bytes(content)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка записи файла: {str(e)}")

    try:
        get_forecast_service().process_pdf_and_save(safe_name)
    except PdfConversionConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Сервис конвертации недоступен: {str(e)}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    md_filename = Path(safe_name).stem + ".md"
    return {"filename": safe_name, "md_file": md_filename, "saved_to": str(dest)}


@router.get("/dates", response_model=ForecastDatesResponse)
async def get_available_dates() -> ForecastDatesResponse:
    """Возвращает список дат, по которым в БД доступны прогнозы (для выпадающего списка на фронте).

    Данные запрашиваются у сервиса: репозиторий отдаёт сырые даты из таблицы forecast,
    сервис формирует DTO со строками YYYY-MM-DD, отсортированными от новых к старым.
    """
    return get_forecast_service().get_available_dates()


@router.get("/data")
async def get_forecast_data(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format. If not provided, returns latest available date.")
):
    """Получает прогнозные данные для указанной даты.
    
    Загружает прогнозные данные из БД. Если дата не указана, возвращает данные
    для последней доступной даты.
    
    Args:
        date: Дата в формате YYYY-MM-DD для получения прогнозных данных.
            Если не указана, используется последняя доступная дата.
    
    Returns:
        Словарь с прогнозными данными, содержащий:
        - date: Дата в формате YYYY-MM-DD
        - names: Словарь с маппингом названий полей (ключ "названия" из файла)
        - data: Данные прогноза для указанной даты
    
    Raises:
        HTTPException: Если файл прогнозных данных не найден (статус 404),
            если данные для указанной даты не найдены (статус 404),
            или если произошла ошибка при чтении файла (статус 500).
    """
    try:
        return get_forecast_service().get_forecast_data(date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/export/json")
async def export_forecast_json(
    dates: Optional[str] = Query(None, description="Comma-separated dates in YYYY-MM-DD format. If not provided, exports latest available date.")
):
    """Экспортирует прогнозные данные в формате JSON.
    
    Экспортирует прогнозные данные для указанных дат в формате JSON с русскими
    названиями полей. Возвращает файл для скачивания.
    
    Args:
        dates: Строка с датами через запятую в формате YYYY-MM-DD для экспорта.
            Если не указана, экспортируется последняя доступная дата.
    
    Returns:
        HTTP Response с JSON файлом для скачивания, содержащим:
        - Ключи верхнего уровня: даты в формате YYYY-MM-DD
        - Для каждой даты:
          - дата_заседания: Дата заседания
          - дата_публикации: Дата публикации
          - основные_показатели: Словарь с основными показателями по годам
            (ключи - русские названия полей из маппинга)
          - платёжный_баланс: Словарь с показателями платежного баланса по годам
            (ключи - русские названия полей из маппинга)
    
    Raises:
        HTTPException: Если файл прогнозных данных не найден (статус 404),
            если данные для указанной даты не найдены (статус 404),
            или если произошла ошибка при чтении файла (статус 500).
    
    Note:
        Имя файла формируется автоматически: forecast_YYYY_MM_DD.json для одной даты
        или forecast_N_dates.json для нескольких дат.
    """
    data = _load_forecast_data()
    names = data.get("названия", {})
    main_names = names.get("основные_показатели", {})
    balance_names = names.get("платёжный_баланс", {})
    
    # Parse dates parameter
    if dates:
        date_list = [d.strip() for d in dates.split(",") if d.strip()]
    else:
        # If no dates provided, get the latest
        available_dates = [key for key in data.keys() if key != "названия" and key.startswith("20")]
        if not available_dates:
            raise HTTPException(status_code=404, detail="No forecast data available")
        available_dates.sort(reverse=True)
        date_list = [available_dates[0]]
    
    # Validate all dates exist
    for date in date_list:
        if date not in data:
            raise HTTPException(status_code=404, detail=f"Forecast data for date {date} not found")
    
    # Build export structure
    export_data = {}
    
    for date in date_list:
        date_data = data[date]
        date_export = {
            "дата_заседания": date_data.get("дата_заседания"),
            "дата_публикации": date_data.get("дата_публикации"),
            "основные_показатели": {},
            "платёжный_баланс": {},
        }
        
        # Process main indicators
        main_indicators = date_data.get("основные_показатели", [])
        if main_indicators:
            years = sorted(set([ind["год"] for ind in main_indicators]))
            for year in years:
                year_data = next((ind for ind in main_indicators if ind["год"] == year), None)
                if year_data:
                    year_dict = {}
                    for key, value in year_data.items():
                        if key == "год":
                            continue
                        if key in main_names:
                            field_name = main_names[key]
                            year_dict[field_name] = value
                    if year_dict:
                        date_export["основные_показатели"][str(year)] = year_dict
        
        # Process balance indicators
        balance_indicators = date_data.get("платёжный_баланс", [])
        if balance_indicators:
            years = sorted(set([ind["год"] for ind in balance_indicators]))
            for year in years:
                year_data = next((ind for ind in balance_indicators if ind["год"] == year), None)
                if year_data:
                    year_dict = {}
                    for key, value in year_data.items():
                        if key == "год":
                            continue
                        if key in balance_names:
                            field_name = balance_names[key]
                            year_dict[field_name] = value
                    if year_dict:
                        date_export["платёжный_баланс"][str(year)] = year_dict
        
        export_data[date] = date_export
    
    # Convert to JSON string
    json_text = json.dumps(export_data, ensure_ascii=False, indent=2)
    
    # Return as downloadable file
    if len(date_list) == 1:
        filename = f"forecast_{date_list[0].replace('-', '_')}.json"
    else:
        filename = f"forecast_{len(date_list)}_dates.json"
    
    return Response(
        content=json_text,
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

