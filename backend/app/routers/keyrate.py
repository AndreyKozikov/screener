"""Роутеры для работы с данными ключевой ставки ЦБ РФ.

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными ключевой ставки Центрального банка Российской Федерации. Включает
endpoints для загрузки данных из ЦБ РФ, получения данных с фильтрацией по датам
и экспорта данных в формате Markdown.
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from typing import Dict, Any, Optional, List

from app.services.keyrate_service import get_keyrate_service
from app.utils.logger import get_data_update_logger

router = APIRouter(prefix="/api/keyrate", tags=["keyrate"])
"""Роутер FastAPI для обработки запросов к API ключевой ставки."""




@router.post("/load")
async def load_keyrate_data() -> Dict[str, float]:
    """Загружает данные ключевой ставки с HTML страницы ЦБ РФ и сохраняет в JSON файл.
    
    Выполняет инкрементальное обновление данных ключевой ставки. Загружает только
    новые данные с последней даты из существующего файла до текущей даты.
    
    Последовательность выполнения:
        1. Загружает существующие данные из JSON файла (если существует)
        2. Определяет начальную дату:
           - Если файл существует и содержит данные: использует последнюю дату из файла
           - Если файл не существует или поврежден: использует дату по умолчанию (17.09.2013)
        3. Устанавливает конечную дату на текущую дату
        4. Загружает новые данные с HTML страницы ЦБ РФ
        5. Парсит HTML таблицы используя pandas.read_html с decimal="," и thousands=" "
        6. Валидирует структуру таблицы (проверяет наличие колонок "Дата" и "Ставка")
        7. Объединяет новые данные с существующими
        8. Сохраняет обновленные данные в JSON файл
    
    Returns:
        Словарь со всеми данными ключевой ставки, где ключ - дата в формате YYYY-MM-DD,
        значение - ключевая ставка (float) в процентах.
    
    Raises:
        HTTPException: Если формат таблицы не соответствует ожидаемому (статус 400),
            если не удалось загрузить данные из ЦБ РФ (статус 502),
            или если произошла другая ошибка (статус 500).
    """
    logger = get_data_update_logger()
    logger.info("[API /keyrate/load] Request received to load key rate data")
    
    try:
        keyrate_service = get_keyrate_service()
        
        logger.info("[API /keyrate/load] Starting key rate data load...")
        result = await asyncio.to_thread(keyrate_service.load_keyrate_data)
        
        entries_count = len(result)
        logger.info(
            f"[API /keyrate/load] Success: Loaded {entries_count} key rate entries"
        )
        
        return result
        
    except ValueError as exc:
        logger.error(f"[API /keyrate/load] ERROR: ValueError - {str(exc)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse key rate data: {str(exc)}"
        ) from exc
    except RuntimeError as exc:
        logger.error(f"[API /keyrate/load] ERROR: RuntimeError - {str(exc)}")
        raise HTTPException(
            status_code=502,
            detail=str(exc)
        ) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /keyrate/load] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load key rate data: {str(exc)}"
        ) from exc


@router.get("/data")
async def get_keyrate_data(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
) -> Dict[str, Any]:
    """Получает данные ключевой ставки с фильтрацией по диапазону дат.
    
    Загружает данные ключевой ставки из JSON файла и применяет фильтрацию по
    диапазону дат, если указаны параметры date_from и date_to.
    
    Args:
        date_from: Начальная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
        date_to: Конечная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
    
    Returns:
        Если фильтры не указаны (date_from и date_to равны None):
            Словарь с данными ключевой ставки, где ключ - дата в формате YYYY-MM-DD,
            значение - ключевая ставка (float) в процентах.
        
        Если фильтры указаны:
            Словарь с отфильтрованными данными, содержащий:
            - data: Список словарей с записями, каждая содержит:
              - Дата: Дата в формате YYYY-MM-DD
              - Ключевая ставка, % годовых: Значение ключевой ставки
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
    logger.info(f"[API /keyrate/data] Request received, date_from={date_from}, date_to={date_to}")
    
    try:
        keyrate_service = get_keyrate_service()
        
        logger.info("[API /keyrate/data] Getting key rate data...")
        all_data = await asyncio.to_thread(keyrate_service._load_keyrate_data)
        
        # If no filters, return dictionary directly (for getKeyRateData API)
        if date_from is None and date_to is None:
            entries_count = len(all_data)
            logger.info(f"[API /keyrate/data] Success: Returning {entries_count} key rate entries as dictionary")
            return all_data
        
        # Convert dictionary to array of records, filtering by date
        records: List[Dict[str, Any]] = []
        
        for date_key, rate_value in all_data.items():
            # Parse date from key (format: YYYY-MM-DD)
            try:
                record_date = datetime.strptime(date_key, "%Y-%m-%d")
            except ValueError:
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
            
            # Create record
            record = {
                "Дата": date_key,
                "Ключевая ставка, % годовых": rate_value,
            }
            
            records.append(record)
        
        # Sort by date descending (most recent first)
        records.sort(key=lambda x: x["Дата"], reverse=True)
        
        entries_count = len(records)
        logger.info(f"[API /keyrate/data] Success: Retrieved {entries_count} key rate entries (filtered from {len(all_data)})")
        
        return {
            "data": records,
            "count": entries_count,
            "date_from": date_from,
            "date_to": date_to,
        }
        
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.error(f"[API /keyrate/data] ERROR: RuntimeError - {str(exc)}")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(f"[API /keyrate/data] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get key rate data: {str(exc)}"
        ) from exc


@router.get("/download/markdown")
async def download_keyrate_markdown(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
) -> Response:
    """Скачивает данные ключевой ставки в формате Markdown.
    
    Загружает данные ключевой ставки из JSON файла, применяет фильтрацию по
    диапазону дат (если указаны) и возвращает данные в формате Markdown таблицы
    для скачивания.
    
    Args:
        date_from: Начальная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
        date_to: Конечная дата диапазона в формате DD.MM.YYYY (включительно).
            Если не указана, фильтр не применяется.
    
    Returns:
        HTTP Response с Markdown файлом для скачивания, содержащим:
        - Заголовок "# Ключевая ставка ЦБ"
        - Таблицу Markdown с колонками:
          - Дата: Дата в формате YYYY-MM-DD
          - Ключевая ставка, % годовых: Значение ключевой ставки (форматируется
            с 2 знаками после запятой)
        Записи отсортированы по дате в порядке убывания (от новых к старым).
    
    Raises:
        HTTPException: Если формат даты некорректен (статус 400),
            если данные не найдены для указанного диапазона дат (статус 404),
            или если произошла ошибка при генерации Markdown (статус 500).
    
    Note:
        Имя файла формируется автоматически: keyrate_DD-MM-YYYY_DD-MM-YYYY.md для
        фильтрованных данных или keyrate_all.md для всех данных.
    """
    logger = get_data_update_logger()
    logger.info(f"[API /keyrate/download/markdown] Request received, date_from={date_from}, date_to={date_to}")
    
    try:
        keyrate_service = get_keyrate_service()
        all_data = await asyncio.to_thread(keyrate_service._load_keyrate_data)
        
        # Convert dictionary to array of records, filtering by date (same logic as /data)
        records: List[Dict[str, Any]] = []
        
        for date_key, rate_value in all_data.items():
            try:
                record_date = datetime.strptime(date_key, "%Y-%m-%d")
            except ValueError:
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
                "Дата": date_key,
                "Ключевая ставка, % годовых": rate_value,
            }
            
            records.append(record)
        
        # Sort by date descending
        records.sort(key=lambda x: x["Дата"], reverse=True)
        
        if not records:
            raise HTTPException(status_code=404, detail="No data found for the specified date range")
        
        # Build markdown content
        markdown_lines = []
        
        # Header
        markdown_lines.append("# Ключевая ставка ЦБ")
        markdown_lines.append("")
        
        # Column headers
        header_cols = [
            "Дата",
            "Ключевая ставка, % годовых",
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
                    # Format numbers with 2 decimal places
                    try:
                        num_val = float(val)
                        row_values.append(f"{num_val:.2f}")
                    except (ValueError, TypeError):
                        row_values.append(str(val))
            markdown_lines.append("| " + " | ".join(row_values) + " |")
        
        markdown_lines.append("")
        
        # Convert to string
        markdown_content = "\n".join(markdown_lines)
        
        # Generate filename
        filename = "keyrate"
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
        logger.error(f"[API /keyrate/download/markdown] ERROR: {error_type} - {str(exc)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Markdown: {str(exc)}"
        ) from exc
