"""Роутеры для работы с кривой бескупонной доходности (БКДЦТ).

Этот модуль содержит роутеры FastAPI для обработки HTTP запросов, связанных
с данными кривой бескупонной доходности от Мосбиржи. Включает endpoints для
получения данных с фильтрацией по датам, экспорта данных в форматах JSON и
Markdown.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.kbd_service import get_kbd_service
from app.models import KbdDataResponse

router = APIRouter(prefix="/api/zerocupon", tags=["zerocupon"])
"""Роутер FastAPI для обработки запросов к API кривой бескупонной доходности."""

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

    data = await asyncio.to_thread(
        kbd_service.get_kbd_data_formatted,
        date_from=date_from,
        date_to=date_to,
    )
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
    dtos = await asyncio.to_thread(
        kbd_service.get_kbd_data_formatted,
        date_from=date_from,
        date_to=date_to,
    )
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
    dtos = await asyncio.to_thread(
        kbd_service.get_kbd_data_formatted,
        date_from=date_from,
        date_to=date_to,
    )
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
