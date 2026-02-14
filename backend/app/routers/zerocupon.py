"""Роутеры для работы с кривой бескупонной доходности (БКДЦТ).

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными кривой бескупонной доходности от Мосбиржи. Включает endpoints для
получения данных с фильтрацией по датам, экспорта данных в форматах JSON и
Markdown, а также обновления данных из API Мосбиржи.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.utils.logger import get_data_update_logger
from app.repository.db.db_kbd import KbdRepository
from app.services.kbd_service import get_kbd_service
from app.models import DBkbd, KbdDataResponse
from config.paths import DB_PATH

router = APIRouter(prefix="/api/zerocupon", tags=["zerocupon"])
"""Роутер FastAPI для обработки запросов к API кривой бескупонной доходности."""

# Маппинг period из API (годы) в поля модели DBkbd
_API_PERIOD_TO_TERM = {
    0.25: "term_0_25", 0.5: "term_0_5", 0.75: "term_0_75", 1.0: "term_1_0",
    2.0: "term_2_0", 3.0: "term_3_0", 5.0: "term_5_0", 7.0: "term_7_0",
    10.0: "term_10_0", 15.0: "term_15_0", 20.0: "term_20_0", 30.0: "term_30_0",
}


def _api_yields_to_dbkbd(
    date_obj: datetime,
    time_str: str,
    yields_data: List[Dict[str, Any]],
) -> Optional[DBkbd]:
    """Преобразует ответ API Мосбиржи (yearyields) в одну запись DBkbd."""
    date_sql = date_obj.strftime("%Y-%m-%d")
    # Время в формате HH:MM:SS
    if " " in time_str:
        time_str = time_str.split(" ")[-1]
    if len(time_str.split(":")) == 2:
        time_str = time_str + ":00"
    kwargs: Dict[str, Any] = {"date": date_sql, "time": time_str}
    for key in _API_PERIOD_TO_TERM.values():
        kwargs[key] = None
    for item in yields_data:
        period = item.get("period")
        value = item.get("value")
        if period in _API_PERIOD_TO_TERM and value is not None:
            try:
                kwargs[_API_PERIOD_TO_TERM[period]] = float(value)
            except (TypeError, ValueError):
                pass
    return DBkbd(**kwargs)


@router.get("/data", response_model=KbdDataResponse)
async def get_zerocupon_data(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
):
    """Получает данные кривой бескупонной доходности с фильтрацией по диапазону дат.
    
    Загружает из БД только колонки для фронта (без срока 30 лет), фильтрует выходные.
    По умолчанию — данные за последний год.
    """
    kbd_service = get_kbd_service()
    if not kbd_service:
        raise HTTPException(
            status_code=503,
            detail="KBD service is not initialized. Please ensure the database is available."
        )
    if not date_from and not date_to:
        one_year_ago = datetime.now() - timedelta(days=365)
        date_from = one_year_ago.strftime("%d.%m.%Y")
        date_to = datetime.now().strftime("%d.%m.%Y")

    data = kbd_service.get_kbd_data_formatted(date_from=date_from, date_to=date_to)
    return KbdDataResponse(
        data=data,
        count=len(data),
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/download")
async def download_zerocupon_json(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
):
    """Скачивает данные кривой бескупонной доходности в формате JSON. Данные из БД."""
    kbd_service = get_kbd_service()
    if not kbd_service:
        raise HTTPException(status_code=503, detail="KBD service is not initialized.")
    if not date_from and not date_to:
        one_year_ago = datetime.now() - timedelta(days=365)
        date_from = one_year_ago.strftime("%d.%m.%Y")
        date_to = datetime.now().strftime("%d.%m.%Y")
    dtos = kbd_service.get_kbd_data_formatted(date_from=date_from, date_to=date_to)
    periods = [0.25, 0.5, 0.75, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]
    term_to_period = {"term_0_25": "0.25", "term_0_5": "0.5", "term_0_75": "0.75", "term_1_0": "1.0",
                      "term_2_0": "2.0", "term_3_0": "3.0", "term_5_0": "5.0", "term_7_0": "7.0",
                      "term_10_0": "10.0", "term_15_0": "15.0", "term_20_0": "20.0"}
    data_records = []
    for dto in dtos:
        yield_curve = {}
        for term_attr, period_key in term_to_period.items():
            val = getattr(dto, term_attr, None)
            if val is not None:
                yield_curve[period_key] = val
        data_records.append({
            "date": dto.date,
            "time": dto.time,
            "yield_curve": yield_curve,
        })
    metadata = {
        "title": "Кривая бескупонной доходности",
        "description": "Данные кривой бескупонной доходности (БКДЦТ) с различными сроками до погашения",
        "date_from": date_from or "автоматически (последний год)",
        "date_to": date_to or "автоматически (сегодня)",
        "record_count": len(data_records),
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "periods": periods,
    }
    field_descriptions = {
        "date": "Дата расчета кривой доходности в формате DD.MM.YYYY",
        "time": "Время расчета (если доступно)",
        "yield_curve": "Словарь значений доходности по срокам до погашения (в годах). Ключи - сроки в годах, значения - доходность в процентах годовых",
    }
    export_data = {"metadata": metadata, "field_descriptions": field_descriptions, "data": data_records}
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    filename = "zerocupon"
    if date_from or date_to:
        if date_from:
            filename += f"_{date_from.replace('.', '-')}"
        if date_to:
            filename += f"_{date_to.replace('.', '-')}"
    else:
        filename += "_last_year"
    filename += ".json"
    return Response(
        content=json_str,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/download/markdown")
async def download_zerocupon_markdown(
    date_from: Optional[str] = Query(None, description="Start date in DD.MM.YYYY format"),
    date_to: Optional[str] = Query(None, description="End date in DD.MM.YYYY format"),
):
    """Скачивает данные кривой бескупонной доходности в формате Markdown. Данные из БД."""
    kbd_service = get_kbd_service()
    if not kbd_service:
        raise HTTPException(status_code=503, detail="KBD service is not initialized.")
    if not date_from and not date_to:
        one_year_ago = datetime.now() - timedelta(days=365)
        date_from = one_year_ago.strftime("%d.%m.%Y")
        date_to = datetime.now().strftime("%d.%m.%Y")
    dtos = kbd_service.get_kbd_data_formatted(date_from=date_from, date_to=date_to)
    period_cols = ["Срок 0.25 лет", "Срок 0.5 лет", "Срок 0.75 лет", "Срок 1.0 лет", "Срок 2.0 лет",
                   "Срок 3.0 лет", "Срок 5.0 лет", "Срок 7.0 лет", "Срок 10.0 лет", "Срок 15.0 лет", "Срок 20.0 лет"]
    header_cols = ["Дата", "Время"] + period_cols
    markdown_lines = [
        "# Кривая бескупонной доходности (БКДЦТ)",
        "",
        "## Метаданные",
        "",
        f"- **Период данных:** {date_from or 'автоматически (последний год)'} - {date_to or 'автоматически (сегодня)'}",
        f"- **Количество записей:** {len(dtos)}",
        f"- **Дата экспорта:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Данные",
        "",
        "| " + " | ".join(header_cols) + " |",
        "| " + " | ".join(["---"] * len(header_cols)) + " |",
    ]
    for dto in dtos:
        row = [dto.date or "", dto.time or ""]
        for attr in ["term_0_25", "term_0_5", "term_0_75", "term_1_0", "term_2_0", "term_3_0",
                     "term_5_0", "term_7_0", "term_10_0", "term_15_0", "term_20_0"]:
            v = getattr(dto, attr, None)
            row.append(f"{v:.4f}" if v is not None else "")
        markdown_lines.append("| " + " | ".join(row) + " |")
    markdown_lines.extend([
        "",
        "## Описание",
        "",
        "Данные кривой бескупонной доходности (БКДЦТ) с различными сроками до погашения.",
        "",
        "- **Дата:** Дата расчета кривой доходности",
        "- **Время:** Время расчета (если доступно)",
        "- **Срок X.Y лет:** Доходность для срока до погашения X.Y лет (в процентах годовых)",
        "",
    ])
    filename = "zerocupon"
    if date_from or date_to:
        if date_from:
            filename += f"_{date_from.replace('.', '-')}"
        if date_to:
            filename += f"_{date_to.replace('.', '-')}"
    else:
        filename += "_last_year"
    filename += ".md"
    return Response(
        content="\n".join(markdown_lines),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _parse_jsonp_response(text: str) -> Dict[str, Any]:
    """Парсит JSONP ответ от API Мосбиржи.
    
    Удаляет обертку JSON_CALLBACK и извлекает JSON данные.
    
    Args:
        text: Текст JSONP ответа от API Мосбиржи.
    
    Returns:
        Словарь с распарсенными JSON данными.
    
    Raises:
        ValueError: Если не удалось распарсить JSON данные.
    """
    # Remove JSON_CALLBACK wrapper: JSON_CALLBACK(...) -> ...
    # Match pattern: JSON_CALLBACK( ... )
    match = re.match(r'^\s*JSON_CALLBACK\s*\((.*)\)\s*$', text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # If no wrapper, try to parse as-is
        json_str = text
    
    # Parse JSON
    try:
        data = json.loads(json_str)
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {str(e)}")


def _fetch_zerocupon_data_for_date(target_date: datetime) -> Optional[List[Dict[str, Any]]]:
    """Загружает данные кривой бескупонной доходности из API Мосбиржи для указанной даты.
    
    Выполняет HTTP запрос к API Мосбиржи для получения данных кривой доходности
    за указанную дату. Парсит JSONP ответ и извлекает данные yearyields.
    
    Args:
        target_date: Дата для загрузки данных кривой доходности.
    
    Returns:
        Список словарей с данными доходности по периодам, или None если запрос
        не удался или данные недоступны. Каждый словарь содержит:
        - period: Период до погашения (в годах)
        - value: Значение доходности (в процентах годовых)
        - tradetime: Время торгов
    """
    logger = get_data_update_logger()
    # Format date as YYYY-MM-DD
    date_str = target_date.strftime("%Y-%m-%d")
    url = f"https://iss.moex.com/iss/engines/stock/zcyc.jsonp?iss.meta=off&iss.json=extended&callback=JSON_CALLBACK&lang=ru&iss.only=yearyields&date={date_str}"
    logger.info(f"[REFRESH ZEROCOUPON] Fetching data from API: {url}")
    
    try:
        # Use httpx in sync mode for this function (will be called in thread)
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            
            # Parse JSONP response
            data = _parse_jsonp_response(response.text)
            
            # Extract yearyields from the nested structure
            if isinstance(data, list) and len(data) >= 2:
                # Data structure: [{"charsetinfo": ...}, {"yearyields": [...]}]
                for item in data:
                    if isinstance(item, dict) and "yearyields" in item:
                        return item["yearyields"]
            
            return None
    except Exception as e:
        logger.error(f"[REFRESH ZEROCOUPON] Error fetching data for {date_str} from {url}: {e}")
        return None


def refresh_zerocupon_data() -> Dict[str, Any]:
    """Пайплайн: скачивание данных из API Мосбиржи → преобразование в формат БД → сохранение в БД.
    
    Определяет диапазон дат по последней записи в таблице kbd, загружает данные из API
    по каждой дате (только будни), преобразует в DBkbd и сохраняет через KbdRepository.
    """
    logger = get_data_update_logger()
    api_base_url = "https://iss.moex.com/iss/engines/stock/zcyc.jsonp"
    logger.info(f"[REFRESH ZEROCOUPON] Starting zerocupon data refresh (API → DB)")
    logger.info(f"[REFRESH ZEROCOUPON] API endpoint: {api_base_url}")
    repo = KbdRepository(db_path=DB_PATH)
    last_date = repo.get_last_kbd_date()
    logger.info(f"[REFRESH ZEROCOUPON] Last date in DB: {last_date.strftime('%Y-%m-%d') if last_date else 'None'}")
    if last_date:
        start_date = last_date + timedelta(days=1)
    else:
        start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now() - timedelta(days=1)
    logger.info(f"[REFRESH ZEROCOUPON] Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    if start_date > end_date:
        logger.info("[REFRESH ZEROCOUPON] Data is up to date, no refresh needed")
        return {
            "status": "ok",
            "message": "Data is up to date",
            "last_date": last_date.strftime("%d.%m.%Y") if last_date else None,
            "dates_fetched": 0,
        }
    records: List[DBkbd] = []
    dates_fetched = 0
    dates_failed = 0
    current_date = start_date
    while current_date <= end_date:
        if current_date.weekday() < 5:
            yields_data = _fetch_zerocupon_data_for_date(current_date)
            if yields_data and len(yields_data) > 0:
                time_str = yields_data[0].get("tradetime", "18:49:59")
                row = _api_yields_to_dbkbd(current_date, time_str, yields_data)
                if row:
                    records.append(row)
                    dates_fetched += 1
                    logger.info(f"[REFRESH ZEROCOUPON] Fetched data for {current_date.strftime('%Y-%m-%d')}")
            else:
                dates_failed += 1
                logger.warning(f"[REFRESH ZEROCOUPON] No data for {current_date.strftime('%Y-%m-%d')}")
        current_date += timedelta(days=1)
    if records:
        repo.save_kbd_records(records)
    result = {
        "status": "ok",
        "message": f"Fetched {dates_fetched} dates, {dates_failed} failed",
        "last_date": last_date.strftime("%d.%m.%Y") if last_date else None,
        "start_date": start_date.strftime("%d.%m.%Y"),
        "end_date": end_date.strftime("%d.%m.%Y"),
        "dates_fetched": dates_fetched,
        "dates_failed": dates_failed,
    }
    logger.info(f"[REFRESH ZEROCOUPON] Refresh completed: {result}")
    return result


@router.post("/refresh")
async def refresh_zerocupon(
    update_zero_coupon_curve: bool = Query(False, description="Update zero coupon curve data in database after file save")
):
    """Обновляет данные кривой бескупонной доходности: API → преобразование → сохранение в БД."""
    logger = get_data_update_logger()
    logger.info("[API /zerocupon/refresh] Received request to refresh zerocupon data")
    try:
        result = await asyncio.to_thread(refresh_zerocupon_data)
        result["database_updated"] = True
        return result
    except Exception as e:
        logger.error("[API /zerocupon/refresh] ERROR: %s - %s", type(e).__name__, str(e))
        raise HTTPException(status_code=500, detail=f"Error refreshing zerocupon data: {str(e)}")

