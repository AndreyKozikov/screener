"""Роутеры для работы с данными индикатора RUONIA.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными индикатора RUONIA (индикатор однодневной ставки межбанковского кредитования)
от ЦБ РФ. Включает endpoints для получения данных с фильтрацией по датам,
экспорта данных в формате Markdown и обновления данных из ЦБ РФ.
"""

import asyncio
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Dict, Any, Optional, List
import json

from app.services.ruonia_service import get_ruonia_service
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/ruonia", tags=["ruonia"])
"""Роутер FastAPI для обработки запросов к API индикатора RUONIA."""




@router.get("/data")
async def get_ruonia_data(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
) -> Dict[str, Any]:
    """Получает данные RUONIA с фильтрацией по диапазону дат.
    
    Загружает данные RUONIA из JSON файла и применяет фильтрацию по диапазону дат,
    если указаны параметры date_from и date_to. Преобразует данные в формат с русскими
    названиями колонок для удобства отображения на фронтенде.
    
    Args:
        date_from: Начальная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
        date_to: Конечная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
    
    Returns:
        Словарь с отфильтрованными данными RUONIA, содержащий:
        - data: Список словарей с записями, каждая содержит:
          - Дата ставки: Дата в формате YYYY-MM-DD
          - Ставка RUONIA, % годовых: Значение ставки RUONIA
          - Объем сделок RUONIA, млрд руб.: Объем сделок
          - Количество сделок, ед.: Количество сделок
          - Минимальная процентная ставка, % годовых: Минимальная ставка
          - 25-й процентиль по процентным ставкам, % годовых: 25-й процентиль
          - 75-й процентиль по процентным ставкам, % годовых: 75-й процентиль
          - Максимальная процентная ставка, % годовых: Максимальная ставка
        - count: Количество записей после фильтрации
        - date_from: Начальная дата фильтра (если указана)
        - date_to: Конечная дата фильтра (если указана)
        Записи отсортированы по дате в порядке убывания (от новых к старым).
    
    Raises:
        HTTPException: Если формат даты некорректен (статус 400),
            если произошла ошибка при загрузке данных (статус 502),
            или если произошла другая ошибка (статус 500).
    """
    logger = get_data_update_logger()
    logger.info(f"[API /ruonia/data] Request received, date_from={date_from}, date_to={date_to}")
    
    try:
        ruonia_service = get_ruonia_service()
        
        logger.info("[API /ruonia/data] Getting RUONIA data...")
        all_data = await asyncio.to_thread(ruonia_service.get_ruonia_data)
        
        # Convert dictionary to array of records, filtering by date
        records: List[Dict[str, Any]] = []
        
        for date_key, row_data in all_data.items():
            # Parse date from key (format: YYYY-MM-DD)
            try:
                record_date = datetime.strptime(date_key, "%Y-%m-%d")
            except ValueError:
                # Try to parse DT field from row_data if date_key is not in ISO format
                dt_value = row_data.get("DT")
                if dt_value:
                    if isinstance(dt_value, str):
                        try:
                            record_date = datetime.strptime(dt_value, "%Y-%m-%d")
                        except ValueError:
                            continue
                    elif isinstance(dt_value, datetime):
                        record_date = dt_value
                    else:
                        continue
                else:
                    continue
            
            # Filter by date_from
            if date_from:
                try:
                    date_from_dt = datetime.strptime(date_from, "%d.%m.%Y")
                    if record_date < date_from_dt:
                        continue
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_from format. Use DD.MM.YYYY")
            
            # Filter by date_to
            if date_to:
                try:
                    date_to_dt = datetime.strptime(date_to, "%d.%m.%Y")
                    # Include the end date (set time to end of day)
                    date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                    if record_date > date_to_dt:
                        continue
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_to format. Use DD.MM.YYYY")
            
            # Create record with Russian column names
            record = {
                "Дата ставки": date_key if isinstance(date_key, str) else record_date.strftime("%Y-%m-%d"),
                "Ставка RUONIA, % годовых": row_data.get("ruo"),
                "Объем сделок RUONIA, млрд руб.": row_data.get("vol"),
                "Количество сделок, ед.": row_data.get("T"),
                "Минимальная процентная ставка, % годовых": row_data.get("MinRate"),
                "25-й процентиль по процентным ставкам, % годовых": row_data.get("Percentile25"),
                "75-й процентиль по процентным ставкам, % годовых": row_data.get("Percentile75"),
                "Максимальная процентная ставка, % годовых": row_data.get("MaxRate"),
            }
            
            records.append(record)
        
        # Sort by date descending (most recent first)
        records.sort(key=lambda x: x["Дата ставки"], reverse=True)
        
        entries_count = len(records)
        logger.info(f"[API /ruonia/data] Success: Retrieved {entries_count} RUONIA entries (filtered from {len(all_data)})")
        
        return {
            "data": records,
            "count": entries_count,
            "date_from": date_from,
            "date_to": date_to,
        }
        
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.error(f"[API /ruonia/data] ERROR: RuntimeError - {str(exc)}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /ruonia/data] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get RUONIA data: {str(exc)}"
        ) from exc


@router.get("/download/markdown")
async def download_ruonia_markdown(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
) -> Response:
    """Скачивает данные RUONIA в формате Markdown.
    
    Загружает данные RUONIA из JSON файла, применяет фильтрацию по диапазону дат
    (если указаны) и возвращает данные в формате Markdown таблицы для скачивания.
    
    Args:
        date_from: Начальная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
        date_to: Конечная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
    
    Returns:
        HTTP Response с Markdown файлом для скачивания, содержащим:
        - Заголовок "# Ставка RUONIA"
        - Таблицу Markdown с колонками:
          - Дата ставки: Дата в формате YYYY-MM-DD
          - Ставка RUONIA, % годовых: Значение ставки (форматируется с 4 знаками после запятой)
          - Объем сделок RUONIA, млрд руб.: Объем сделок
          - Количество сделок, ед.: Количество сделок
          - Минимальная процентная ставка, % годовых: Минимальная ставка
          - 25-й процентиль по процентным ставкам, % годовых: 25-й процентиль
          - 75-й процентиль по процентным ставкам, % годовых: 75-й процентиль
          - Максимальная процентная ставка, % годовых: Максимальная ставка
        Записи отсортированы по дате в порядке убывания (от новых к старым).
    
    Raises:
        HTTPException: Если формат даты некорректен (статус 400),
            если данные не найдены для указанного диапазона дат (статус 404),
            или если произошла ошибка при генерации Markdown (статус 500).
    
    Note:
        Имя файла формируется автоматически: ruonia_DD-MM-YYYY_DD-MM-YYYY.md для
        фильтрованных данных или ruonia_all.md для всех данных.
    """
    logger = get_data_update_logger()
    logger.info(f"[API /ruonia/download/markdown] Request received, date_from={date_from}, date_to={date_to}")
    
    try:
        ruonia_service = get_ruonia_service()
        all_data = await asyncio.to_thread(ruonia_service.get_ruonia_data)
        
        # Convert dictionary to array of records, filtering by date (same logic as /data)
        records: List[Dict[str, Any]] = []
        
        for date_key, row_data in all_data.items():
            try:
                record_date = datetime.strptime(date_key, "%Y-%m-%d")
            except ValueError:
                dt_value = row_data.get("DT")
                if dt_value:
                    if isinstance(dt_value, str):
                        try:
                            record_date = datetime.strptime(dt_value, "%Y-%m-%d")
                        except ValueError:
                            continue
                    elif isinstance(dt_value, datetime):
                        record_date = dt_value
                    else:
                        continue
                else:
                    continue
            
            if date_from:
                try:
                    date_from_dt = datetime.strptime(date_from, "%d.%m.%Y")
                    if record_date < date_from_dt:
                        continue
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_from format. Use DD.MM.YYYY")
            
            if date_to:
                try:
                    date_to_dt = datetime.strptime(date_to, "%d.%m.%Y")
                    date_to_dt = date_to_dt.replace(hour=23, minute=59, second=59)
                    if record_date > date_to_dt:
                        continue
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_to format. Use DD.MM.YYYY")
            
            record = {
                "Дата ставки": date_key if isinstance(date_key, str) else record_date.strftime("%Y-%m-%d"),
                "Ставка RUONIA, % годовых": row_data.get("ruo"),
                "Объем сделок RUONIA, млрд руб.": row_data.get("vol"),
                "Количество сделок, ед.": row_data.get("T"),
                "Минимальная процентная ставка, % годовых": row_data.get("MinRate"),
                "25-й процентиль по процентным ставкам, % годовых": row_data.get("Percentile25"),
                "75-й процентиль по процентным ставкам, % годовых": row_data.get("Percentile75"),
                "Максимальная процентная ставка, % годовых": row_data.get("MaxRate"),
            }
            
            records.append(record)
        
        # Sort by date descending
        records.sort(key=lambda x: x["Дата ставки"], reverse=True)
        
        if not records:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")
        
        # Build markdown content
        markdown_lines = []
        
        # Header
        markdown_lines.append("# Ставка RUONIA")
        markdown_lines.append("")
        
        # Column headers
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
        markdown_lines.append("| " + " | ".join(header_cols) + " |")
        markdown_lines.append("| " + " | ".join(["---"] * len(header_cols)) + " |")
        
        # Table rows
        for record in records:
            row_values = []
            for col in header_cols:
                val = record.get(col)
                if val is None:
                    row_values.append("")
                else:
                    # Format numbers with 4 decimal places
                    try:
                        num_val = float(val)
                        row_values.append(f"{num_val:.4f}")
                    except (ValueError, TypeError):
                        row_values.append(str(val))
            markdown_lines.append("| " + " | ".join(row_values) + " |")
        
        markdown_lines.append("")
        
        # Convert to string
        markdown_content = "\n".join(markdown_lines)
        
        # Generate filename
        filename = "ruonia"
        if date_from or date_to:
            if date_from:
                filename += f"_{date_from.replace('.', '-')}"
            if date_to:
                filename += f"_{date_to.replace('.', '-')}"
        else:
            filename += "_all"
        filename += ".md"
        
        return Response(
            content=markdown_content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /ruonia/download/markdown] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Markdown: {str(exc)}"
        ) from exc


@router.post("/refresh")
async def refresh_ruonia_data() -> Dict[str, Any]:
    """Принудительно обновляет данные RUONIA из ЦБ РФ путем загрузки Excel файла.
    
    Выполняет инкрементальное обновление данных RUONIA. Загружает только новые данные
    с даты после последней записи в существующих данных (или с даты по умолчанию
    11.01.2010, если данных нет) до текущей даты.
    
    Returns:
        Словарь с результатом обновления, содержащий:
        - status: Статус операции ("ok" или "error")
        - message: Сообщение о результате обновления
        - from_date: Начальная дата диапазона загрузки (при успехе)
        - to_date: Конечная дата диапазона загрузки (при успехе)
        - new_entries: Количество новых записей (при успехе)
        - updated_entries: Количество обновленных записей (при успехе)
        - total_entries: Общее количество записей после обновления (при успехе)
        - error: Сообщение об ошибке (при ошибке)
        - updated: Флаг успешного обновления (True или False)
    
    Raises:
        HTTPException: Если произошла ошибка при обновлении данных (статус 500).
    
    Note:
        Если from_date > to_date (нет новых данных для загрузки), возвращается
        результат с updated=False и сообщением "No new data to download".
    """
    logger = get_data_update_logger()
    logger.info("[API /ruonia/refresh] Received request to refresh RUONIA data")
    
    try:
        ruonia_service = get_ruonia_service()
        
        logger.info("[API /ruonia/refresh] Refreshing RUONIA data...")
        result = await asyncio.to_thread(ruonia_service.update_ruonia_data)
        
        logger.info(f"[API /ruonia/refresh] Refresh completed: {result}")
        
        return result
        
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /ruonia/refresh] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh RUONIA data: {str(exc)}"
        ) from exc
